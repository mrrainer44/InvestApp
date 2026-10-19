"""Zmiany stanu posiadania inwestorów i ich szacowana wartość w złotych.

Źródła zmian (kolumna changes.source):
  art69      - zawiadomienia o zmianie udziału (próg 5%, 10%...) - dane z formularza KNF
  mar        - transakcje insiderów (art. 19 MAR) - z ceną transakcji
  fundusze   - różnice w portfelach OFE/TFI/DFE (sprawozdania funduszy, akcjonariat < 5%)
  akcjonariat- różnice w głównych akcjonariuszach (>5%) między kolejnymi odczytami
  wz         - różnice między listami akcjonariuszy z walnych zgromadzeń (najmniej dokładne)

Wartość = zmiana liczby akcji x kurs zamknięcia z dnia zdarzenia (albo cena z formularza MAR).
To szacunek - faktyczna cena transakcji (np. w ABB, poza sesją) może się różnić.
"""
import difflib
import json
import logging
import re
import time
from datetime import date, timedelta

from . import biznesradar as br
from .util import ascii_fold, iso_week, norm_investor

log = logging.getLogger("gpwt.flows")

FUND_RE = ("ofe", "tfi", "dfe", "ppk", "pte", "fio", "fiz")


def _ins(con, **c):
    con.execute(
        """INSERT OR IGNORE INTO changes(date, ticker, investor, investor_norm, shares_before, shares_after,
           delta, price, price_src, value, source, espi_id, excluded, note)
           VALUES(:date,:ticker,:investor,:investor_norm,:shares_before,:shares_after,:delta,:price,
                  :price_src,:value,:source,:espi_id,:excluded,:note)""",
        {"shares_before": None, "shares_after": None, "price": None, "price_src": None, "value": None,
         "espi_id": 0, "excluded": 0, "note": None, **c})


def similar_investor(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def rebuild_changes(con):
    n = {"chg_art69": 0, "chg_mar": 0, "chg_snap": 0}
    # --- ESPI: art. 69 i MAR ---
    for row in con.execute("SELECT id, ticker, ts, category, parsed FROM espi WHERE fetched=1 AND ticker IS NOT NULL "
                           "AND category IN ('art69','mar')").fetchall():
        p = json.loads(row["parsed"] or "{}")
        seen = set()
        for i, f in enumerate(p.get("forms", [])):
            if f.get("delta") in (None, 0) or not f.get("investor"):
                continue
            sig = (norm_investor(f["investor"]), f["delta"], f.get("shares_after"))
            if sig in seen:
                continue  # to samo zawiadomienie w treści raportu i w załączniku
            seen.add(sig)
            # data zdarzenia nie może być późniejsza niż publikacja raportu (literówki w formularzach, np. 2029)
            d = min(f.get("event_date") or row["ts"][:10], row["ts"][:10])
            base = dict(date=d, ticker=row["ticker"], investor=f["investor"],
                        investor_norm=norm_investor(f["investor"]), delta=f["delta"],
                        source=row["category"], espi_id=row["id"] * 10 + i)
            if row["category"] == "art69":
                _ins(con, **base, shares_before=f.get("shares_before"), shares_after=f.get("shares_after"),
                     note=f.get("kind"))
                n["chg_art69"] += 1
            else:
                price = f.get("price")
                not_shares = f.get("is_shares") is False
                note = " / ".join(x for x in (f.get("position"), f.get("kind")) if x)
                if not_shares:
                    note += f" [instrument: {f.get('instrument')} - nie akcje, wykluczone z sum]"
                _ins(con, **base, price=price, price_src="MAR" if price else None,
                     value=(f["delta"] * price) if price else None, excluded=1 if not_shares else 0, note=note)
                n["chg_mar"] += 1

    # --- różnice w kolejnych odczytach akcjonariatu ---
    snaps = con.execute("SELECT * FROM holdings_snap ORDER BY ticker, holder_norm, source, date_upd").fetchall()
    prev = None
    for s in snaps:
        key = (s["ticker"], s["holder_norm"], s["source"])
        if prev and prev[0] == key and s["date_upd"] != prev[1]["date_upd"] and s["shares"] != prev[1]["shares"]:
            p = prev[1]
            before, note = p["shares"], f"odczyt {p['date_upd']} -> {s['date_upd']}"
            if s["source"] == "OFE":
                note = f"struktura portfela OFE {p['date_upd']} -> {s['date_upd']}"
                k = split_factor(con, s["ticker"], p["date_upd"], s["date_upd"])
                if k != 1:
                    before = p["shares"] * k
                    note += f" (podział akcji x{k:g} uwzględniony)"
                # struktury OFE podają wartość, liczba akcji = wartość / kurs - pomijamy szum zaokrągleń
                if before and abs(s["shares"] - before) / before < 0.005:
                    prev = (key, s)
                    continue
            src = "wz" if s["source"] == "WZ" else (
                "fundusze" if any(t in s["holder_norm"].split() for t in FUND_RE) else "akcjonariat")
            _ins(con, date=s["date_upd"], ticker=s["ticker"], investor=s["holder"], investor_norm=s["holder_norm"],
                 shares_before=before, shares_after=s["shares"], delta=s["shares"] - before, source=src, note=note)
            n["chg_snap"] += 1
        prev = (key, s)

    # ta sama zmiana OFE z akcjonariatu Biznesradar i ze struktury portfela -> liczymy raz (struktura)
    ofe = con.execute("SELECT ticker, investor_norm, date FROM changes WHERE note LIKE 'struktura portfela OFE%'").fetchall()
    for c in con.execute("SELECT id, ticker, investor_norm, date FROM changes WHERE source='fundusze' "
                         "AND note LIKE 'odczyt%' AND excluded=0").fetchall():
        if any(o["ticker"] == c["ticker"] and o["investor_norm"] == c["investor_norm"]
               and abs((date.fromisoformat(o["date"]) - date.fromisoformat(c["date"][:10])).days) <= 10 for o in ofe):
            con.execute("UPDATE changes SET excluded=1, note=note||' [duplikat struktury OFE]' WHERE id=?", (c["id"],))

    # --- deduplikacja: zmiana z akcjonariatu/WZ, która jest już w zawiadomieniu art. 69 ---
    art = con.execute("SELECT ticker, investor_norm, date, delta FROM changes WHERE source='art69'").fetchall()
    by_t = {}
    for a in art:
        by_t.setdefault(a["ticker"], []).append(a)
    for c in con.execute("SELECT id, ticker, investor_norm, date, delta FROM changes "
                         "WHERE source IN ('akcjonariat','wz') AND excluded=0").fetchall():
        for a in by_t.get(c["ticker"], []):
            dd = abs((date.fromisoformat(c["date"][:10]) - date.fromisoformat(a["date"][:10])).days)
            if dd <= 60 and (a["delta"] > 0) == (c["delta"] > 0) and similar_investor(a["investor_norm"], c["investor_norm"]):
                con.execute("UPDATE changes SET excluded=1, note=COALESCE(note,'')||' [duplikat art69]' WHERE id=?",
                            (c["id"],))
                break
    con.commit()
    return n


def split_factor(con, ticker, d1, d2):
    """Podział (lub scalenie) akcji między datami: jednodniowy skok surowego kursu zamknięcia o całkowitą
    krotność (np. 502 -> 49,61 zł = split 1:10). Zwraca k (10 przy splicie 1:10, 0.1 przy scaleniu 10:1)
    albo 1. Wymaga dziennych kursów w price_history (ofe.ensure_daily_prices dociąga je dla podejrzanych spółek)."""
    rows = con.execute("SELECT date, close FROM price_history WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
                       (ticker, (date.fromisoformat(d1) - timedelta(days=5)).isoformat(), d2)).fetchall()
    k = 1
    for a, b in zip(rows, rows[1:]):
        if not (a["close"] and b["close"]):
            continue
        if (date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days > 5:
            continue  # tylko sąsiednie sesje - luka w danych to nie split
        r = a["close"] / b["close"]
        for ratio, sign in ((r, 1), (1 / r, -1)):
            n = round(ratio)
            if n >= 2 and abs(ratio - n) / n < 0.12:
                k = k * n if sign == 1 else k / n
    return k


def price_on(con, ticker, d):
    r = con.execute("SELECT close FROM price_history WHERE ticker=? AND date<=? AND date>=? ORDER BY date DESC LIMIT 1",
                    (ticker, d, (date.fromisoformat(d) - timedelta(days=10)).isoformat())).fetchone()
    return r["close"] if r else None


def fill_prices(con, max_tickers=80):
    todo = con.execute("SELECT id, ticker, date, delta FROM changes WHERE price IS NULL").fetchall()
    missing = {}
    filled = 0
    for c in todo:
        p = price_on(con, c["ticker"], c["date"][:10])
        if p is None:
            missing.setdefault(c["ticker"], []).append(c)
            continue
        con.execute("UPDATE changes SET price=?, price_src='zamknięcie', value=delta*? WHERE id=?", (p, p, c["id"]))
        filled += 1
    con.commit()  # nie trzymamy blokady zapisu bazy w trakcie pobierania historii kursów
    fetched = 0
    for ticker, rows in list(missing.items())[:max_tickers]:
        slug = con.execute("SELECT slug FROM companies WHERE ticker=?", (ticker,)).fetchone()
        if not slug or not slug["slug"]:
            continue
        need = min(r["date"][:10] for r in rows)
        for page in range(1, 15):
            hist = br.fetch_price_history(slug["slug"], page)
            if not hist:
                break
            con.executemany("INSERT OR IGNORE INTO price_history VALUES(?,?,?)", [(ticker, d, v) for d, v in hist])
            if min(d for d, _ in hist) <= need:
                break
        fetched += 1
        for c in rows:
            p = price_on(con, ticker, c["date"][:10])
            if p is not None:
                con.execute("UPDATE changes SET price=?, price_src='zamknięcie', value=delta*? WHERE id=?",
                            (p, p, c["id"]))
                filled += 1
        con.commit()
    con.commit()
    return {"prices_filled": filled, "price_histories_fetched": fetched}


# instytucje finansowe spoza nazewnictwa OFE/TFI (np. fundusz suwerenny Norwegii)
_INSTITUTIONS = re.compile(r"norges bank|blackrock|vanguard|fidelity|invesco|templeton|schroders|aberdeen|"
                           r"asset management|investment management|\bfunds?\b|fundusz|capital group|"
                           r"jpmorgan|goldman sachs|morgan stanley|state street|dimensional", re.I)
_matcher = {"m": None, "at": 0.0}


def _company_matcher(con):
    """ofe.Matcher (nazwa -> ticker) do rozpoznania akcji własnych; budowany raz na kilka godzin."""
    if _matcher["m"] is None or time.monotonic() - _matcher["at"] > 6 * 3600:
        from .ofe import Matcher
        _matcher["m"], _matcher["at"] = Matcher(con), time.monotonic()
    return _matcher["m"]


def holder_kind(holder, holder_norm, ticker, matcher=None):
    """owners = właściciele, funds = fundusze i instytucje, rest = akcje własne spółki."""
    if any(t in holder_norm.split() for t in FUND_RE) or _INSTITUTIONS.search(ascii_fold(holder)):
        return "funds"
    if "akcje wlasne" in holder_norm or "own shares" in holder_norm:
        return "rest"
    if matcher:
        from .ofe import _key
        words = set(_key(holder).split())
        # spółka jako własny akcjonariusz: "X-Trade Brokers S.A." w "X-Trade Brokers Dom Maklerski"
        if words and sum(len(w) for w in words) >= 4 and any(
                words <= set(n.split()) for n in matcher.names_of.get(ticker, ())):
            return "rest"
    return "owners"


def holder_groups(con, ticker):
    """Ostatni odczyt akcjonariatu (Biznesradar) w trzech grupach: właściciele, fundusze, pozostali
    (akcje własne + wyliczony akcjonariat rozproszony = 100% minus znane udziały)."""
    rows = con.execute(
        "SELECT h.holder, h.holder_norm, h.pct, h.shares, h.date_upd FROM holdings_snap h JOIN "
        "(SELECT holder_norm, MAX(date_upd) d FROM holdings_snap WHERE ticker=? AND source='BR' GROUP BY holder_norm) m "
        "ON h.holder_norm=m.holder_norm AND h.date_upd=m.d WHERE h.ticker=? AND h.source='BR' ORDER BY h.pct DESC",
        (ticker, ticker)).fetchall()
    if not rows:
        return []
    m = _company_matcher(con)
    groups = {k: [] for k in ("owners", "funds", "rest")}
    for r in rows:
        groups[holder_kind(r["holder"], r["holder_norm"], ticker, m)].append(
            {"holder": r["holder"], "pct": r["pct"], "shares": r["shares"], "date_upd": r["date_upd"]})
    known = sum(r["pct"] or 0 for r in rows)
    total_shares = (con.execute("SELECT shares FROM companies WHERE ticker=?", (ticker,)).fetchone() or [None])[0]
    if known < 100:
        free = round(100 - known, 2)
        groups["rest"].append({"holder": "Akcjonariat rozproszony (wyliczony: 100% minus znane udziały)",
                               "pct": free, "shares": round(total_shares * free / 100) if total_shares else None,
                               "date_upd": None, "computed": True})
    labels = {"owners": "Właściciele", "funds": "Fundusze (OFE, TFI, DFE i inne instytucje)",
              "rest": "Pozostały akcjonariat"}
    out = []
    for k, members in groups.items():
        if not members:
            continue
        dates = [x["date_upd"] for x in members if x["date_upd"]]
        out.append({"key": k, "label": labels[k], "members": members,
                    "pct": round(sum(x["pct"] or 0 for x in members), 2),
                    "shares": sum(x["shares"] or 0 for x in members) or None,
                    "date_from": min(dates) if dates else None, "date_to": max(dates) if dates else None})
    return out


def aliases(con):
    return {r["alias_norm"]: r["canonical"] for r in con.execute("SELECT * FROM investor_aliases")}


def investor_flows(con, period="week", sources=None, start=None, end=None):
    """Agregacja: inwestor x okres -> kupno, sprzedaż, saldo (PLN), liczba zmian, spółki."""
    sources = sources or ["art69", "mar", "fundusze", "akcjonariat"]
    q = (f"SELECT * FROM changes WHERE excluded=0 AND source IN ({','.join('?' * len(sources))})")
    params = list(sources)
    if start:
        q += " AND date>=?"
        params.append(start)
    if end:
        q += " AND date<=?"
        params.append(end)
    al = aliases(con)
    groups = {}
    for c in con.execute(q, params).fetchall():
        name = al.get(c["investor_norm"]) or c["investor"]
        per = iso_week(c["date"]) if period == "week" else c["date"][:7]
        g = groups.setdefault((name, per), {"investor": name, "period": per, "buy": 0.0, "sell": 0.0,
                                            "net": 0.0, "n": 0, "unpriced": 0, "tickers": set(),
                                            "sources": set(), "investor_norm": c["investor_norm"]})
        g["n"] += 1
        g["tickers"].add(c["ticker"])
        g["sources"].add(c["source"])
        if c["value"] is None:
            g["unpriced"] += 1
            continue
        if c["value"] >= 0:
            g["buy"] += c["value"]
        else:
            g["sell"] += -c["value"]
        g["net"] += c["value"]
    out = []
    for g in groups.values():
        g["tickers"] = ", ".join(sorted(g["tickers"]))
        g["sources"] = ", ".join(sorted(g["sources"]))
        out.append(g)
    out.sort(key=lambda x: abs(x["net"]), reverse=True)
    out.sort(key=lambda x: x["period"], reverse=True)
    return out
