"""Średni termin (miesiące): momentum z trendem, rotacja sektorowa i zakupy funduszy.

  momentum  - średnia zmiana kursu z 3 i 6 miesięcy (63 i 126 sesji); domyślnie tylko spółki w trendzie
              wzrostowym (SMA50 nad SMA200 i kurs nad SMA200) i płynne (średni obrót z 20 sesji od progu),
  sektory   - zmiana z 1 i 3 miesięcy ważona kapitalizacją, na tle WIG, i odsetek spółek sektora nad SMA200,
  fundusze  - OFE, TFI, PPK: ile funduszy zwiększyło, a ile zmniejszyło udział w spółce w oknie (struktury portfeli
              OFE, zawiadomienia art. 69, akcjonariat), saldo wartości.
To zestawienia do dalszej analizy, nie rekomendacje.
"""
from datetime import date, timedelta

from . import technicals
from .flows import FUND_RE

_FUND_WORDS = ("fundusz", "tfi", "ofe", "ppk", "pte", "dfe", "fio", "fiz", "pension", "investment fund")


def _is_fund(norm, name):
    s = f"{norm or ''} {(name or '').lower()}"
    return any(t in (norm or "").split() for t in FUND_RE) or any(w in s for w in _FUND_WORDS)


def momentum(tech, min_turn=100_000, min_nc=30_000, trend_only=True, n=25):
    rows = [x for x in tech["rows"].values() if x["mom"] is not None and (x["avg20"] or 0) >= (
        min_nc if x["market"] == "NC" else min_turn)]
    if trend_only:
        rows = [x for x in rows if x["trend"] and x["vs200"] is not None and x["vs200"] > 0]
    rows.sort(key=lambda x: -x["mom"])
    keep = ("ticker", "name", "market", "sector", "close", "chg", "ret_1m", "ret_3m", "ret_6m", "rs_3m", "rs_6m", "mom",
            "vs50", "vs200", "trend", "new_high52", "avg20")
    return [{k: x.get(k) for k in keep} for x in rows[:n]], len(rows)


def sectors(tech, min_turn=20_000):
    groups = {}
    for x in tech["rows"].values():
        if not x["sector"] or (x["avg20"] or 0) < min_turn:
            continue
        groups.setdefault(x["sector"], []).append(x)
    w = tech["wig"]
    out = []
    for sec, xs in groups.items():
        if len(xs) < 3:
            continue
        row = {"sector": sec, "n": len(xs)}
        for k in ("1m", "3m"):
            v = [(x[f"ret_{k}"], x["mcap"] or 0) for x in xs if x[f"ret_{k}"] is not None]
            tot = sum(m for _, m in v)
            row[f"ret_{k}"] = sum(r * m for r, m in v) / tot if tot else None
            row[f"rs_{k}"] = (row[f"ret_{k}"] - w[f"ret_{k}"]) if row[f"ret_{k}"] is not None and w.get(f"ret_{k}") is not None else None
        a = [x for x in xs if x["vs200"] is not None]
        row["above200"] = sum(x["vs200"] > 0 for x in a) / len(a) * 100 if a else None
        best = sorted((x for x in xs if x["ret_1m"] is not None), key=lambda x: -x["ret_1m"])
        row["leaders"] = [x["ticker"] for x in best[:3]]
        out.append(row)
    out.sort(key=lambda r: -(r["rs_1m"] if r["rs_1m"] is not None else -999))
    return out


def funds(con, tech, days=365, n=25):
    start = (date.today() - timedelta(days=days)).isoformat()
    by = {}
    for r in con.execute("SELECT ticker, investor, investor_norm, delta, value, date, source FROM changes "
                         "WHERE excluded=0 AND date>=? AND source IN ('fundusze','art69','akcjonariat')", (start,)):
        if not _is_fund(r["investor_norm"], r["investor"]):
            continue
        g = by.setdefault(r["ticker"], {"ticker": r["ticker"], "up": set(), "down": set(), "value": 0.0, "last": r["date"],
                                        "unpriced": 0})
        (g["up"] if r["delta"] > 0 else g["down"]).add(r["investor_norm"])
        g["value"] += r["value"] or 0
        g["unpriced"] += r["value"] is None
        g["last"] = max(g["last"], r["date"])
    rows = []
    for t, g in by.items():
        x = tech["rows"].get(t) or {}
        rows.append({"ticker": t, "name": x.get("name"), "funds_up": len(g["up"]), "funds_down": len(g["down"]),
                     "value": g["value"], "unpriced": g["unpriced"], "last": g["last"], "ret_3m": x.get("ret_3m"),
                     "trend": x.get("trend"), "mcap": x.get("mcap"),
                     "value_pct_mcap": g["value"] / x["mcap"] * 100 if x.get("mcap") else None})
    buy = sorted((r for r in rows if r["funds_up"] > r["funds_down"]), key=lambda r: (-(r["funds_up"] - r["funds_down"]), -r["value"]))
    sell = sorted((r for r in rows if r["funds_down"] > r["funds_up"]), key=lambda r: (-(r["funds_down"] - r["funds_up"]), r["value"]))
    return buy[:n], sell[:n]


def summary(con, min_turn=100_000, min_nc=30_000, trend_only=True, fund_days=365):
    tech = technicals.compute(con)
    mom, n_mom = momentum(tech, min_turn, min_nc, trend_only)
    buy, sell = funds(con, tech, fund_days)
    return {"date": tech["day"], "sessions": tech.get("sessions"), "wig": tech["wig"], "momentum": mom, "n_momentum": n_mom,
            "trend_only": trend_only, "min_turnover": min_turn, "min_nc": min_nc, "sectors": sectors(tech),
            "funds_buy": buy, "funds_sell": sell, "fund_days": fund_days}
