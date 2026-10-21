"""Podsumowanie sesji: co się dziś wydarzyło na GPW i NewConnect.

  - szerokość rynku: ile spółek rośnie / spada, osobno dla płynnych (obrót >= próg), i jaki obrót stoi za każdą stroną,
  - najwięksi zwycięzcy i przegrani wśród płynnych spółek - w dniu odcięcia dywidendy ze zmianą skorygowaną o dywidendę,
  - skoki obrotu względem średniej z 20 sesji,
  - transakcje insiderów (MAR) i zmiany znacznych pakietów (art. 69) z ostatnich 1 / 5 / 20 sesji, także zsumowane
    na spółkę (liczy się seria zakupów, a nie pojedyncze zawiadomienie),
  - ważne komunikaty (wezwania, skup akcji własnych),
  - "Moje spółki" (portfel z zakładki Moje spółki albo spółki zaznaczone w wybranej własnej kolumnie) z sygnałami.
Próg płynności jest osobny dla GPW i NewConnect (na NC obroty są o rząd wielkości mniejsze).

Sygnały to podpowiedzi, co warto obejrzeć - nie rekomendacje kupna ani sprzedaży.
"""
import statistics

from . import espi as espi_mod
from . import pressure, technicals

IMPORTANT = ("art69", "mar", "wezwanie", "skup", "wz_lista")


def _dates(con):
    rows = [r[0] for r in con.execute("SELECT DISTINCT date FROM quotes ORDER BY date DESC LIMIT 2")]
    return (rows[0] if rows else None), (rows[1] if len(rows) > 1 else None)


def session_days(con, n, before=None):
    """n ostatnich dni sesyjnych (z archiwum notowań - tabela quotes zaczyna się dopiero od startu aplikacji)."""
    q = "SELECT date FROM ohlc " + ("WHERE date<? " if before else "") +         "GROUP BY date HAVING COUNT(*) > 100 ORDER BY date DESC LIMIT ?"
    days = [r[0] for r in con.execute(q, (before, n) if before else (n,))]
    for r in con.execute("SELECT DISTINCT date FROM quotes ORDER BY date DESC LIMIT ?", (n,)):  # dzisiejsza sesja w toku
        if r[0] not in days and (not before or r[0] < before):
            days.append(r[0])
    return sorted(days, reverse=True)[:n]


def _avg_turnover(con, day, sessions=20):
    """Średni obrót z `sessions` poprzednich sesji (dni bez handlu spółką liczone jako 0)."""
    days = [r[0] for r in con.execute(
        "SELECT date FROM ohlc WHERE date<? GROUP BY date HAVING COUNT(*) > 100 ORDER BY date DESC LIMIT ?",
        (day, sessions))]
    if not days:
        return {}
    q = ",".join("?" * len(days))
    return {r[0]: r[1] / len(days) for r in con.execute(
        f"SELECT ticker, SUM(turnover) FROM ohlc WHERE date IN ({q}) GROUP BY ticker", days)}


def _breadth(rows):
    up = [r for r in rows if r["traded"] and (r["chg"] or 0) > 0]
    down = [r for r in rows if r["traded"] and (r["chg"] or 0) < 0]
    flat = [r for r in rows if r["traded"] and not r["chg"]]
    chg = [r["chg"] for r in rows if r["traded"] and r["chg"] is not None]
    return {"up": len(up), "down": len(down), "flat": len(flat), "none": sum(1 for r in rows if not r["traded"]),
            "up_turnover": sum(r["turnover"] or 0 for r in up), "down_turnover": sum(r["turnover"] or 0 for r in down),
            "median_change": statistics.median(chg) if chg else None}


def summary(con, min_turnover=100_000, market="", watch_key=None, top=12, min_nc=30_000, insider_sessions=1):
    day, prev = _dates(con)
    if not day:
        return {"date": None}
    as_of = con.execute("SELECT MAX(finished) FROM runs WHERE status='ok' AND kind IN ('daily','weekly','quick')"
                        ).fetchone()[0]
    avg = _avg_turnover(con, day)
    cmf = pressure.all_cmf(con)
    tech_all = technicals.compute(con)
    tech, wig_chg = tech_all["rows"], tech_all["wig"].get("chg")
    exdiv = {}
    if prev:  # ostatni dzień z prawem do dywidendy = poprzednia sesja -> dziś kurs bez dywidendy
        for r in con.execute("SELECT ticker, SUM(dps) dps FROM dividends WHERE last_day=? AND dps>0 GROUP BY ticker",
                             (prev,)):
            exdiv[r["ticker"]] = r["dps"]

    rows = []
    for r in con.execute(
            "SELECT q.ticker, q.close, q.change_pct, q.volume, q.turnover, c.market, c.short_name, c.full_name, "
            "c.shares FROM quotes q JOIN companies c ON c.ticker=q.ticker WHERE q.date=?", (day,)):
        if market and r["market"] != market:
            continue
        chg, close = r["change_pct"], r["close"]
        x = {"ticker": r["ticker"], "name": r["full_name"] or r["short_name"], "market": r["market"],
             "close": close, "chg": chg, "turnover": r["turnover"], "traded": bool(r["volume"]),
             "avg20": avg.get(r["ticker"]), "cmf21": (cmf.get(r["ticker"]) or {}).get(21),
             "mcap": close * r["shares"] if close and r["shares"] else None}
        x["ratio"] = (x["turnover"] / x["avg20"]) if x["avg20"] and x["turnover"] else None
        dps = exdiv.get(r["ticker"])
        if dps and close and chg is not None and chg > -100:
            prev_close = close / (1 + chg / 100)
            x["exdiv"] = {"dps": dps, "pct": dps / prev_close * 100,
                          "adj_chg": (close + dps) / prev_close * 100 - 100}
        x["chg_eff"] = x["exdiv"]["adj_chg"] if "exdiv" in x else chg
        tx = tech.get(r["ticker"]) or {}
        x["breakout"] = "52" if tx.get("new_high52") else "63" if tx.get("new_high63") else None
        x["gap"] = tx.get("gap") if tx.get("gap") and abs(tx["gap"]["size"]) >= 1 else None
        x["rs_day"] = (x["chg_eff"] - wig_chg) if x["chg_eff"] is not None and wig_chg is not None and x["traded"] else None
        x["trend"], x["vs200"] = tx.get("trend"), tx.get("vs200")
        rows.append(x)
    by = {x["ticker"]: x for x in rows}
    liquid = [x for x in rows if x["traded"]
              and (x["turnover"] or 0) >= (min_nc if x["market"] == "NC" else min_turnover)]

    # komunikaty i zmiany stanu posiadania od zamknięcia poprzedniej sesji
    since = f"{prev} 17:00" if prev else day
    espi_rows = [dict(r) for r in con.execute(
        "SELECT id, ticker, ts, title, category FROM espi WHERE ts>? ORDER BY ts DESC", (since,))]
    if market:
        espi_rows = [e for e in espi_rows if e["ticker"] in by]
    counts = {}
    for e in espi_rows:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    ds = session_days(con, insider_sessions + 1)
    since_h = f"{ds[-1]} 17:00" if len(ds) > insider_sessions else since
    holders = [dict(r) for r in con.execute(
        "SELECT c.ticker, c.investor, c.investor_norm, c.delta, c.price, c.value, c.source, c.date, c.shares_after, "
        "c.note, e.ts, e.title FROM changes c JOIN espi e ON e.id=c.espi_id/10 WHERE c.source IN ('mar','art69') "
        "AND c.excluded=0 AND e.ts>? ORDER BY ABS(COALESCE(c.value, 0)) DESC", (since_h,))]
    if market:
        holders = [h for h in holders if h["ticker"] in by]
    for h in holders:
        q = by.get(h["ticker"])
        h["chg"] = q["chg_eff"] if q else None
        h["name"] = q["name"] if q else None
    # przesunięcia akcji między powiązanymi podmiotami (np. do fundacji rodzinnej): kupno i sprzedaż znoszą się
    gross, net = {}, {}
    for h in holders:
        gross[h["ticker"]] = gross.get(h["ticker"], 0) + abs(h["delta"])
        net[h["ticker"]] = net.get(h["ticker"], 0) + h["delta"]
    transfer = {t for t in gross if len([h for h in holders if h["ticker"] == t]) > 1
                and abs(net[t]) <= 0.05 * gross[t] / 2}
    for h in holders:
        h["transfer"] = h["ticker"] in transfer
    # seria na spółkę: ile zakupów i sprzedaży, ilu różnych osób, saldo akcji i wartości
    series = {}
    for h in holders:
        if h["transfer"]:
            continue
        g = series.setdefault(h["ticker"], {"ticker": h["ticker"], "name": h["name"], "chg": h["chg"], "buys": 0,
                                            "sells": 0, "people": set(), "net": 0.0, "value": 0.0, "unpriced": 0,
                                            "last": h["ts"], "sources": set()})
        g["buys" if h["delta"] > 0 else "sells"] += 1
        g["people"].add(h["investor_norm"])
        g["net"] += h["delta"]
        g["value"] += h["value"] or 0
        g["unpriced"] += h["value"] is None
        g["last"] = max(g["last"], h["ts"])
        g["sources"].add(h["source"])
    series = sorted(({**g, "people": len(g["people"]), "sources": sorted(g["sources"])} for g in series.values()),
                    key=lambda g: -abs(g["value"]))

    events = {}
    for t in transfer:
        events.setdefault(t, []).append({"kind": "transfer", "text": "Przesunięcie akcji między powiązanymi podmiotami "
                                                                     "(np. do fundacji rodzinnej) - saldo ok. zera"})
    for h in holders:
        if h["transfer"]:
            continue
        who = "Insider" if h["source"] == "mar" else "Akcjonariusz (art. 69)"
        verb = "kupił" if h["delta"] > 0 else "sprzedał"
        val = f", ok. {_money(abs(h['value']))}" if h["value"] else ""
        events.setdefault(h["ticker"], []).append(
            {"kind": "insider_buy" if h["delta"] > 0 else "insider_sell",
             "text": f"{who}: {h['investor']} {verb} {abs(h['delta']):,.0f} akcji{val}".replace(",", " ")})
    for e in espi_rows:
        e["tags"] = espi_mod.keywords(e["title"])
        if e["category"] in ("wezwanie", "skup"):
            events.setdefault(e["ticker"], []).append(
                {"kind": e["category"], "text": ("Wezwanie: " if e["category"] == "wezwanie" else "Skup akcji: ")
                 + _subject(e["title"])})
        for tag in ("umowa", "wyniki", "emisja"):
            if tag in e["tags"]:
                events.setdefault(e["ticker"], []).append({"kind": f"espi_{tag}", "text": _subject(e["title"])})

    def signals(x):
        s = list(events.get(x["ticker"], []))
        if x.get("breakout") and (x["ratio"] or 0) >= 2:
            s.append({"kind": "breakout", "text": f"Wybicie do nowego maksimum z {'52 tygodni' if x['breakout'] == '52' else '3 miesięcy'}"
                                                  f" przy obrocie {x['ratio']:.1f}x średniej"})
        if x.get("gap"):
            g = x["gap"]
            s.append({"kind": "gap_up" if g["dir"] == "up" else "gap_down",
                      "text": f"Luka {'wzrostowa' if g['dir'] == 'up' else 'spadkowa'} {g['size']:+.1f}% - "
                              + ("domknięta w trakcie sesji" if g["filled"] else "niedomknięta")})
        if x.get("rs_day") is not None and wig_chg is not None and wig_chg <= -0.5 and (x["chg_eff"] or 0) >= 2:
            s.append({"kind": "rs", "text": f"Rośnie w spadkowy dzień: {x['chg_eff']:+.1f}% przy WIG {wig_chg:+.2f}%"})
        if "exdiv" in x:
            d = x["exdiv"]
            s.append({"kind": "exdiv", "text": f"Dzień odcięcia dywidendy {d['dps']:.2f} zł ({d['pct']:.1f}%) - "
                                               f"po doliczeniu dywidendy zmiana {d['adj_chg']:+.2f}%"})
        c, ratio = x["chg_eff"], x["ratio"]
        if c is not None and ratio and ratio >= 2 and abs(c) >= 5:
            s.append({"kind": "move_down" if c < 0 else "move_up",
                      "text": f"{'Spadek' if c < 0 else 'Wzrost'} {c:+.1f}% przy obrocie {ratio:.1f}x średniej"})
        elif ratio and ratio >= 3 and (x["turnover"] or 0) >= 20_000:
            s.append({"kind": "volume", "text": f"Obrót {ratio:.1f}x średniej z 20 sesji"})
        if x["cmf21"] is not None and abs(x["cmf21"]) >= 0.25:
            s.append({"kind": "press_up" if x["cmf21"] > 0 else "press_down",
                      "text": ("Akumulacja" if x["cmf21"] > 0 else "Dystrybucja")
                      + f" w ostatnich 30 dniach (presja {x['cmf21']:+.2f})"})
        return s

    def pub(x):
        return {k: x.get(k) for k in ("ticker", "name", "market", "close", "chg", "chg_eff", "turnover", "avg20",
                                      "ratio", "cmf21", "exdiv", "mcap", "breakout", "gap", "rs_day", "trend",
                                      "vs200")} | {"signals": signals(x)}

    movers = sorted((x for x in liquid if x["chg_eff"] is not None), key=lambda x: x["chg_eff"])
    spikes = sorted((x for x in liquid if x["ratio"] and x["ratio"] >= 2), key=lambda x: -x["ratio"])
    breakouts = sorted((x for x in liquid if x["breakout"] and (x["ratio"] or 0) >= 2), key=lambda x: -(x["ratio"] or 0))
    gaps = sorted((x for x in liquid if x["gap"]), key=lambda x: -abs(x["gap"]["size"]))
    rs = sorted((x for x in liquid if x["rs_day"] is not None), key=lambda x: -x["rs_day"])

    watch = None
    held = [r[0] for r in con.execute("SELECT DISTINCT ticker FROM positions WHERE closed IS NULL")]
    if (watch_key or "").startswith("__portfolio") or (not watch_key and held):
        pid = (watch_key or "").partition(":")[2]  # "__portfolio" = wszystkie portfele, "__portfolio:3" = jeden
        row = con.execute("SELECT name FROM portfolios WHERE id=?", (pid,)).fetchone() if pid else None
        tick = [r[0] for r in con.execute("SELECT DISTINCT ticker FROM positions WHERE closed IS NULL"
                                          + (" AND portfolio_id=?" if row else ""), (pid,) if row else ())]
        watch = {"key": watch_key or "__portfolio", "label": row["name"] if row else "Portfel",
                 "rows": sorted((pub(by[t]) for t in tick if t in by), key=lambda x: -len(x["signals"]))}
    elif watch_key:
        col = con.execute("SELECT key, label, type FROM custom_columns WHERE key=?", (watch_key,)).fetchone()
        if col:
            tick = [r[0] for r in con.execute("SELECT ticker FROM custom_values WHERE key=? AND value NOT IN "
                                              "('', 'false', '0', 'null')", (watch_key,))]
            watch = {"key": col["key"], "label": col["label"],
                     "rows": sorted((pub(by[t]) for t in tick if t in by), key=lambda x: -len(x["signals"]))}

    return {
        "date": day, "prev_date": prev, "as_of": as_of, "since": since, "min_turnover": min_turnover, "min_nc": min_nc,
        "market": market, "insider_sessions": insider_sessions, "since_holders": since_h, "series": series[:30],
        "has_portfolio": bool(held),
        "portfolios": [dict(r) for r in con.execute("SELECT id, name FROM portfolios ORDER BY id")],
        "breadth": {"all": _breadth(rows), "liquid": _breadth(liquid)},
        "gainers": [pub(x) for x in reversed(movers[-top:]) if (x["chg_eff"] or 0) > 0],
        "losers": [pub(x) for x in movers[:top] if (x["chg_eff"] or 0) < 0],
        "spikes": [pub(x) for x in spikes[:top]],
        "exdiv": [pub(x) for x in rows if "exdiv" in x],
        "holders": holders[:60],
        "espi": {"counts": counts, "total": len(espi_rows),
                 "important": [e for e in espi_rows if e["category"] in ("wezwanie", "skup", "wz_lista")][:30],
                 "tagged": [{**e, "chg": by[e["ticker"]]["chg_eff"] if e["ticker"] in by else None}
                            for e in espi_rows if e["tags"]][:60]},
        "breakouts": [pub(x) for x in breakouts[:top]], "gaps": [pub(x) for x in gaps[:top]],
        "rs_top": [pub(x) for x in rs[:8]], "rs_bottom": [pub(x) for x in rs[-8:][::-1]], "wig_chg": wig_chg,
        "watch": watch,
        "watch_columns": [dict(r) for r in con.execute("SELECT key, label, type FROM custom_columns ORDER BY label")],
    }


def _subject(title):
    return title.split(")", 1)[1].strip() if ")" in (title or "") else (title or "")


def _money(v):
    if v >= 1e6:
        return f"{v / 1e6:.1f} mln zł".replace(".", ",")
    if v >= 1e3:
        return f"{v / 1e3:.0f} tys. zł"
    return f"{v:.0f} zł"

