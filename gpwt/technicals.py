"""Wskaźniki techniczne każdej spółki z notowań sesyjnych (tabela ohlc) - wspólne dla Sesji, tabeli Spółki,
zakładki Trendy i szerokości rynku.

Kalendarz sesji = dni z notowaniami ponad 100 spółek. W dni, w które spółka nie miała transakcji, kurs zamknięcia
uzupełniamy ostatnim znanym (tak liczą średnie serwisy giełdowe). Dzisiejsza sesja: kurs z ostatniego pobrania
(w trakcie sesji - bieżący), otwarcie/maksimum/minimum z notowań Biznesradar.

  sma50 / sma200       - średnie z 50 i 200 sesji (bez dzisiejszej), trend = SMA50 nad SMA200,
  max52 / min52        - najwyższy / najniższy kurs z 250 poprzednich sesji (min. 200 sesji historii),
  max63                - najwyższy kurs z 63 poprzednich sesji (3 miesiące; dla NewConnect z krótszą historią),
  gap                  - luka: otwarcie powyżej maksimum (lub poniżej minimum) poprzedniej sesji spółki
                         i czy została domknięta tego samego dnia,
  ret_1m/3m/6m         - zmiana kursu z 21/63/126 sesji; rs_* = ta zmiana minus zmiana WIG w tym samym czasie,
  avg20 / ratio        - średni obrót z 20 sesji i dzisiejszy obrót jako jego krotność.
Wynik jest zapamiętywany do następnego pobrania (zmiana najnowszej sesji albo zakończonego pobrania).
"""
import threading

_cache = {"key": None, "data": None}
_lock = threading.Lock()


def _sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def calendar(con):
    return [r[0] for r in con.execute("SELECT date FROM ohlc GROUP BY date HAVING COUNT(*) > 100 ORDER BY date")]


def _ret(closes, n, now):
    return (now / closes[-n] - 1) * 100 if now and len(closes) >= n and closes[-n] else None


def compute(con):
    key = (con.execute("SELECT MAX(date) FROM quotes").fetchone()[0],
           con.execute("SELECT MAX(finished) FROM runs").fetchone()[0],
           con.execute("SELECT COUNT(*) FROM ohlc").fetchone()[0])
    with _lock:
        if _cache["key"] == key:
            return _cache["data"]
    data = _compute(con)
    with _lock:
        _cache.update(key=key, data=data)
    return data


def _compute(con):
    cal = calendar(con)
    day = con.execute("SELECT MAX(date) FROM quotes").fetchone()[0]
    if not cal or not day:
        return {"day": day, "wig": {}, "rows": {}}
    past = [d for d in cal if d < day]
    prev_day = past[-1] if past else None
    quotes = {r["ticker"]: r for r in con.execute(
        "SELECT q.ticker, q.close, q.change_pct, q.volume, q.turnover, c.market, c.sector, c.full_name, c.short_name, "
        "c.shares FROM quotes q JOIN companies c ON c.ticker=q.ticker WHERE q.date=?", (day,))}
    today = {r["ticker"]: r for r in con.execute("SELECT * FROM ohlc WHERE date=?", (day,))}
    hist = {}
    for r in con.execute("SELECT ticker, date, high, low, close, turnover FROM ohlc WHERE date<? ORDER BY date", (day,)):
        hist.setdefault(r["ticker"], []).append(r)

    # WIG: zmiany z 21/63/126 sesji (zamknięcia z archiwum gpw.pl) i dzisiejsza (bieżąca z Biznesradar)
    wig = [r[0] for r in con.execute("SELECT close FROM index_ohlc WHERE name='WIG' AND date<? ORDER BY date", (day,))]
    live = con.execute("SELECT value, change_pct, ts FROM market_live WHERE key='WIG'").fetchone()
    wig_now = live["value"] if live and live["ts"][:10] == day else (
        con.execute("SELECT close FROM index_ohlc WHERE name='WIG' AND date=?", (day,)).fetchone() or [None])[0]
    wig_info = {"chg": (wig_now / wig[-1] - 1) * 100 if wig_now and wig else None,
                **{f"ret_{k}": _ret(wig, n, wig_now) for k, n in (("1m", 21), ("3m", 63), ("6m", 126))}}

    last20 = set(past[-20:])
    rows = {}
    for t, q in quotes.items():
        h = hist.get(t, [])
        if not q["close"]:
            continue
        by = {r["date"]: r for r in h}
        closes, highs, lows, last, first = [], [], [], None, h[0]["date"] if h else None
        for d in past:
            if first is None or d < first:
                continue
            if d in by:
                last = by[d]
            if last is None:  # pierwsza transakcja spółki wypadła poza kalendarzem sesji
                continue
            closes.append(last["close"])
            highs.append(last["high"] or last["close"])
            lows.append(last["low"] or last["close"])
        close = q["close"]
        o = today.get(t)
        hi = (o["high"] if o and o["high"] else close)
        lo = (o["low"] if o and o["low"] else close)
        sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
        n = len(closes)
        x = {"ticker": t, "name": q["full_name"] or q["short_name"], "market": q["market"], "sector": q["sector"],
             "close": close, "chg": q["change_pct"], "turnover": q["turnover"], "traded": bool(q["volume"]),
             "mcap": close * q["shares"] if q["shares"] else None, "hist": n,
             "sma50": sma50, "sma200": sma200,
             "vs50": (close / sma50 - 1) * 100 if sma50 else None,
             "vs200": (close / sma200 - 1) * 100 if sma200 else None,
             "trend": (sma50 > sma200) if sma50 and sma200 else None,
             "max52": max(highs[-250:]) if n >= 200 else None, "min52": min(lows[-250:]) if n >= 200 else None,
             "max63": max(highs[-63:]) if n >= 40 else None}
        x["new_high52"] = bool(x["max52"] and hi > x["max52"])
        x["new_low52"] = bool(x["min52"] and lo < x["min52"])
        x["new_high63"] = bool(x["max63"] and hi > x["max63"])
        turn20 = sum(r["turnover"] or 0 for r in h if r["date"] in last20)
        x["avg20"] = turn20 / 20 if past else None
        x["ratio"] = (q["turnover"] / x["avg20"]) if x["avg20"] and q["turnover"] else None
        for k, nn in (("1m", 21), ("3m", 63), ("6m", 126)):
            x[f"ret_{k}"] = _ret(closes, nn, close)
            x[f"rs_{k}"] = (x[f"ret_{k}"] - wig_info[f"ret_{k}"]) if x[f"ret_{k}"] is not None and \
                wig_info[f"ret_{k}"] is not None else None
        x["rs_day"] = (q["change_pct"] - wig_info["chg"]) if q["change_pct"] is not None and wig_info["chg"] is not None \
            and x["traded"] else None
        x["mom"] = (x["ret_3m"] + x["ret_6m"]) / 2 if x["ret_3m"] is not None and x["ret_6m"] is not None else None
        # luka: poprzednia sesja spółki = poprzednia sesja rynku (inaczej "luka" to tylko brak handlu)
        p = by.get(prev_day)
        if o and o["open"] and p and p["high"] and p["low"]:
            if o["open"] > p["high"] * 1.005:
                x["gap"] = {"dir": "up", "size": (o["open"] / p["high"] - 1) * 100, "filled": lo <= p["high"]}
            elif o["open"] < p["low"] * 0.995:
                x["gap"] = {"dir": "down", "size": (o["open"] / p["low"] - 1) * 100, "filled": hi >= p["low"]}
        rows[t] = x
    return {"day": day, "prev_day": prev_day, "sessions": len(past), "wig": wig_info, "rows": rows}
