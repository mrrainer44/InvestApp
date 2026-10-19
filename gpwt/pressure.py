"""Presja kupujących z notowań sesyjnych (cały rynek, nie tylko zgłoszone transakcje).

Dla każdej sesji: CLV = ((zamknięcie - minimum) - (maksimum - zamknięcie)) / (maksimum - minimum), od -1 (zamknięcie
na minimum dnia - przeważali sprzedający) do +1 (na maksimum - kupujący). Przepływ pieniądza dnia = CLV x obrót.
  - linia akumulacji/dystrybucji (A/D) = suma narastająca przepływów,
  - CMF (Chaikin Money Flow) z N sesji = suma przepływów / suma obrotów, od -1 do +1.

Dane: tabela ohlc - codziennie z notowań Biznesradar (GPW i NewConnect), historia GPW z archiwum gpw.pl.
"""
import logging
from datetime import date, timedelta

from . import http
from .ofe import parse_session_full

log = logging.getLogger("gpwt.pressure")

ARCHIVE_XLS = "https://www.gpw.pl/archiwum-notowan?fetch=1&type=10&instrument=&date={d}"
MIN_SESSIONS = 15


def clv(o):
    h, l, c = o["high"], o["low"], o["close"]
    if h is None or l is None or c is None or h <= l:
        return 0.0
    return ((c - l) - (h - c)) / (h - l)


def cmf(rows):
    """rows: sesje (dict z high/low/close/turnover). None przy zbyt małej liczbie sesji."""
    if len(rows) < MIN_SESSIONS:
        return None
    tot = sum(r["turnover"] or 0 for r in rows)
    return sum(clv(r) * (r["turnover"] or 0) for r in rows) / tot if tot else None


def series(con, ticker, start=None):
    q = "SELECT date, open, high, low, close, volume, turnover FROM ohlc WHERE ticker=?"
    p = [ticker]
    if start:
        q += " AND date>=?"
        p.append(start)
    return [dict(r) for r in con.execute(q + " ORDER BY date", p)]


def all_cmf(con, sessions=(21, 63)):
    """{ticker: {21: cmf, 63: cmf}} dla listy spółek - ostatnie N sesji każdej spółki."""
    start = (date.today() - timedelta(days=int(max(sessions) * 1.6) + 10)).isoformat()
    by = {}
    for r in con.execute("SELECT ticker, date, high, low, close, turnover FROM ohlc WHERE date>=? ORDER BY ticker, date",
                         (start,)):
        by.setdefault(r["ticker"], []).append(r)
    return {t: {n: cmf(rows[-n:]) if len(rows) >= n * 0.7 else None for n in sessions} for t, rows in by.items()}


def _ticker_map(con):
    by_isin, by_short = {}, {}
    for r in con.execute("SELECT ticker, short_name, isin FROM companies"):
        if r["isin"]:
            by_isin.setdefault(r["isin"], r["ticker"])
        if r["short_name"]:
            by_short.setdefault(r["short_name"], r["ticker"])
    return by_isin, by_short


def backfill(con, days=400, stats=None):
    """Historia sesji GPW z archiwum gpw.pl (jedno zapytanie na sesję) dla dni, których jeszcze nie mamy."""
    by_isin, by_short = _ticker_map(con)
    have = {r[0] for r in con.execute(
        "SELECT o.date FROM ohlc o JOIN companies c ON c.ticker=o.ticker WHERE c.market='GPW' "
        "GROUP BY o.date HAVING COUNT(*) > 100")}
    today = date.today()
    todo = [today - timedelta(days=i) for i in range(days, -1, -1)]
    todo = [d for d in todo if d.weekday() < 5 and d.isoformat() not in have]
    fetched = 0
    log.info("[sesje] Historia notowań GPW: %s dni do pobrania z archiwum gpw.pl", len(todo))
    for n, d in enumerate(todo, 1):
        rows = parse_session_full(http.get(ARCHIVE_XLS.format(d=d.strftime("%d-%m-%Y")), binary=True))
        if rows:
            batch = []
            for r in rows:
                t = by_isin.get(r["isin"]) or by_short.get(r["name"])
                if t and r["turnover"]:
                    batch.append((t, d.isoformat(), r["open"], r["high"], r["low"], r["close"], r["volume"],
                                  r["turnover"]))
            con.executemany("INSERT OR IGNORE INTO ohlc VALUES(?,?,?,?,?,?,?,?)", batch)
            con.commit()
            fetched += 1
        if n % 25 == 0:
            log.info("      sesje: %s/%s", n, len(todo))
    if stats is not None:
        stats["ohlc_sessions"] = fetched
    return fetched
