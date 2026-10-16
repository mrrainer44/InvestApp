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
from datetime import date, timedelta

from . import biznesradar as br
from .util import iso_week, norm_investor

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
        for i, f in enumerate(p.get("forms", [])):
            if f.get("delta") in (None, 0) or not f.get("investor"):
                continue
            d = f.get("event_date") or row["ts"][:10]
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
            src = "wz" if s["source"] == "WZ" else (
                "fundusze" if any(t in s["holder_norm"].split() for t in FUND_RE) else "akcjonariat")
            _ins(con, date=s["date_upd"], ticker=s["ticker"], investor=s["holder"], investor_norm=s["holder_norm"],
                 shares_before=p["shares"], shares_after=s["shares"], delta=s["shares"] - p["shares"],
                 source=src, note=f"odczyt {p['date_upd']} -> {s['date_upd']}")
            n["chg_snap"] += 1
        prev = (key, s)

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
    return {"prices_filled": filled, "price_histories_fetched": fetched}


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
