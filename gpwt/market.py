"""Kontekst rynku: indeksy, szerokość rynku GPW i wskaźniki makro.

Źródła (legalne, bez obchodzenia zabezpieczeń):
  - indeksy w trakcie sesji: strony notowań Biznesradar (/notowania/WIG20 itd.),
  - zamknięcia indeksów do średnich SMA50/SMA200: archiwum notowań gpw.pl (tabela index_ohlc),
  - szerokość rynku GPW (odsetek spółek nad SMA50/SMA200, nowe maksima i minima 52-tygodniowe): tabela ohlc
    z archiwum gpw.pl; kursy uzupełniane do przodu w dni bez handlu,
  - kursy walut i cena złota: API NBP (api.nbp.pl, kursy średnie tabeli A, publikowane ok. 11:45 w dni robocze),
  - ropa i miedź: strony notowań surowców Bankier.pl.
Rentowności polskich obligacji nie mają darmowego, dziennego źródła, które wolno pobierać automatycznie - pomijamy.
"""
import json
import logging
import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from . import http
from .util import num

log = logging.getLogger("gpwt.market")

# klucz w archiwum gpw.pl -> (nazwa, adres na Biznesradar)
INDICES = {"WIG": ("WIG", "WIG"), "WIG20": ("WIG20", "WIG20"), "MWIG40": ("mWIG40", "mWIG40"),
           "SWIG80": ("sWIG80", "SWIG80"), "NCINDEX": ("NCIndex", "NCIndex")}
FX = {"USD": "USD/PLN", "EUR": "EUR/PLN", "CHF": "CHF/PLN", "GBP": "GBP/PLN"}
COMMODITIES = {"ROPA": "Ropa naftowa (USD/bbl)", "MIEDZ": "Miedź (USD/t)"}
NBP = "https://api.nbp.pl/api"


# ---------------- pobieranie ----------------

def _br_index(slug):
    html = http.get(f"/notowania/{slug}")
    if not html:
        return None
    s = BeautifulSoup(html, "lxml")
    a, p, t = s.select_one("span.q_ch_act"), s.select_one("span.q_ch_per"), s.select_one("time.q_ch_date")
    if not a:
        return None
    return {"value": num(a.get_text(strip=True)), "change_pct": num(p.get_text(strip=True)) if p else None,
            "time": t.get_text(strip=True) if t else None}


def _bankier_commodity(symbol):
    html = http.get(f"https://www.bankier.pl/inwestowanie/profile/quote.html?symbol={symbol}")
    if not html:
        return None
    box = BeautifulSoup(html, "lxml").select_one(".o-quotes-profile-header-box")
    if not box:
        return None
    price = box.select_one(".o-quotes-profile-header-box__price")
    chg = box.select_one(".a-quote-item.-percentage-change")
    when = re.search(r"(\d{2})\.(\d{2})\.(\d{4}),?\s+(\d{2}:\d{2})", box.get_text(" ", strip=True))
    val = num(re.sub(r"[^\d,.\-\s]", "", price.get_text(" ", strip=True)).replace(" ", "")) if price else None
    return {"value": val, "change_pct": num(chg.get_text(strip=True)) if chg else None,
            "ts": f"{when.group(3)}-{when.group(2)}-{when.group(1)} {when.group(4)}" if when else None}


def _store(con, key, day, value, change=None, ts=None, source=None):
    con.execute("INSERT OR REPLACE INTO macro_daily VALUES(?,?,?,?,?,?)", (key, day, value, change, ts, source))


def _nbp_fx(con, days):
    """Kursy średnie NBP (tabela A); API zwraca maks. 93 dni na zapytanie."""
    end = date.today()
    start = end - timedelta(days=days)
    n = 0
    while start <= end:
        stop = min(start + timedelta(days=90), end)
        raw = http.get(f"{NBP}/exchangerates/tables/A/{start}/{stop}/?format=json")
        for tab in json.loads(raw) if raw and raw.lstrip().startswith("[") else []:
            for r in tab["rates"]:
                if r["code"] in FX:
                    _store(con, f"FX_{r['code']}", tab["effectiveDate"], r["mid"], source="NBP")
                    n += 1
        start = stop + timedelta(days=1)
    raw = http.get(f"{NBP}/cenyzlota/{end - timedelta(days=min(days, 90))}/{end}/?format=json")
    for r in json.loads(raw) if raw and raw.lstrip().startswith("[") else []:
        _store(con, "GOLD", r["data"], r["cena"], source="NBP")
    return n


def collect(con, stats=None):
    """Indeksy (w trakcie sesji), waluty i złoto z NBP, ropa i miedź. Ok. 9 zapytań."""
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="minutes")
    for key, (_, slug) in INDICES.items():
        q = _br_index(slug)
        if q and q["value"]:
            con.execute("INSERT OR REPLACE INTO market_live VALUES(?,?,?,?,?)",
                        (key, q["value"], q["change_pct"], f"{today} {q['time'] or ''}".strip(), now))
    have_fx = con.execute("SELECT COUNT(*) FROM macro_daily WHERE key='FX_USD'").fetchone()[0]
    n_fx = _nbp_fx(con, 7 if have_fx > 200 else 400)  # przy pierwszym razie historia ok. roku
    for sym in COMMODITIES:
        c = _bankier_commodity(sym)
        if c and c["value"]:
            _store(con, sym, (c["ts"] or today)[:10], c["value"], c["change_pct"], c["ts"], "Bankier")
    con.commit()
    if stats is not None:
        stats["market_fx_rows"] = n_fx


# ---------------- wyliczenia ----------------

def _sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def _calendar(con):
    return [r[0] for r in con.execute("SELECT date FROM ohlc GROUP BY date HAVING COUNT(*) > 100 ORDER BY date")]


def breadth(con):
    """Spółki GPW: odsetek nad SMA50 i SMA200, nowe maksima/minima 52-tyg. (zamknięcia uzupełniane do przodu)."""
    cal = _calendar(con)
    if len(cal) < 60:
        return None
    today_q = {r["ticker"]: r for r in con.execute(
        "SELECT q.ticker, q.close, q.date, c.full_name, c.short_name FROM quotes q JOIN companies c ON c.ticker=q.ticker "
        "WHERE c.market='GPW' AND q.date=(SELECT MAX(date) FROM quotes)")}
    last_day = max(today_q[t]["date"] for t in today_q) if today_q else cal[-1]
    hist = {}
    for r in con.execute("SELECT o.ticker, o.date, o.high, o.low, o.close FROM ohlc o JOIN companies c ON c.ticker=o.ticker "
                         "WHERE c.market='GPW' AND o.date<? ORDER BY o.date", (last_day,)):
        hist.setdefault(r["ticker"], {})[r["date"]] = (r["high"], r["low"], r["close"])
    past = [d for d in cal if d < last_day]
    today_ohlc = {r["ticker"]: r for r in con.execute("SELECT ticker, high, low, close FROM ohlc WHERE date=?", (last_day,))}
    out = {"n": 0, "above50": 0, "above200": 0, "n200": 0, "highs": [], "lows": [], "date": last_day,
           "sessions": len(past)}
    for t, rows in hist.items():
        q = today_q.get(t)
        if not q or not q["close"] or len(rows) < 20:
            continue
        closes, highs, lows, last = [], [], [], None
        for d in past:  # dni bez handlu: kurs z ostatniej transakcji
            if d in rows:
                last = rows[d]
            if last:
                closes.append(last[2])
                highs.append(last[0] or last[2])
                lows.append(last[1] or last[2])
        close = q["close"]
        sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
        if sma50:
            out["n"] += 1
            out["above50"] += close > sma50
        if sma200:
            out["n200"] += 1
            out["above200"] += close > sma200
        if len(highs) >= 200:  # nowe maksimum/minimum 52 tygodni (250 sesji, min. 200 sesji historii)
            o = today_ohlc.get(t)
            hi = (o["high"] if o and o["high"] else close)
            lo = (o["low"] if o and o["low"] else close)
            name = q["full_name"] or q["short_name"]
            if hi > max(highs[-250:]):
                out["highs"].append({"ticker": t, "name": name, "close": close, "prev_max": max(highs[-250:])})
            elif lo < min(lows[-250:]):
                out["lows"].append({"ticker": t, "name": name, "close": close, "prev_min": min(lows[-250:])})
    out["pct50"] = out["above50"] / out["n"] * 100 if out["n"] else None
    out["pct200"] = out["above200"] / out["n200"] * 100 if out["n200"] else None
    return out


def indices(con):
    out = []
    for key, (name, _) in INDICES.items():
        rows = [r for r in con.execute("SELECT date, close FROM index_ohlc WHERE name=? ORDER BY date", (key,))]
        live = con.execute("SELECT value, change_pct, ts FROM market_live WHERE key=?", (key,)).fetchone()
        if not rows and not live:
            continue
        closes = [r["close"] for r in rows]
        last_date = rows[-1]["date"] if rows else None
        today = date.today().isoformat()
        # w trakcie sesji (i po niej, zanim archiwum gpw.pl ma dzisiejsze zamknięcie) - bieżąca wartość z Biznesradar
        use_live = live and live["value"] and live["ts"][:10] == today and (not last_date or last_date < today)
        value = live["value"] if use_live else (closes[-1] if closes else None)
        base = closes if use_live else closes[:-1]
        chg = live["change_pct"] if use_live else ((closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else None)
        sma50, sma200 = _sma(base, 50), _sma(base, 200)
        out.append({"key": key, "name": name, "value": value, "change_pct": chg,
                    "as_of": live["ts"] if use_live else last_date, "live": bool(use_live),
                    "sma50": sma50, "sma200": sma200,
                    "vs50": (value / sma50 - 1) * 100 if value and sma50 else None,
                    "vs200": (value / sma200 - 1) * 100 if value and sma200 else None,
                    "golden": (sma50 > sma200) if sma50 and sma200 else None,
                    "max52": max(base[-250:]) if len(base) >= 200 else None,
                    "min52": min(base[-250:]) if len(base) >= 200 else None,
                    "sessions": len(base)})
    return out


def macro(con):
    out = []
    items = [(f"FX_{c}", n, "NBP (kurs średni)") for c, n in FX.items()] + [("GOLD", "Złoto (zł/g)", "NBP")] + \
            [(k, n, "Bankier.pl") for k, n in COMMODITIES.items()]
    for key, name, src in items:
        rows = con.execute("SELECT date, value, change, ts FROM macro_daily WHERE key=? ORDER BY date DESC LIMIT 25",
                           (key,)).fetchall()
        if not rows:
            continue
        v = rows[0]["value"]
        prev = rows[1]["value"] if len(rows) > 1 else None
        m = con.execute("SELECT value FROM macro_daily WHERE key=? AND date<=? ORDER BY date DESC LIMIT 1",
                        (key, (date.fromisoformat(rows[0]["date"]) - timedelta(days=30)).isoformat())).fetchone()
        out.append({"key": key, "name": name, "value": v, "date": rows[0]["date"], "ts": rows[0]["ts"], "source": src,
                    "change_pct": rows[0]["change"] if rows[0]["change"] is not None else
                    ((v / prev - 1) * 100 if prev else None),
                    "change_1m": (v / m["value"] - 1) * 100 if m else None})
    return out


def context(con):
    return {"indices": indices(con), "breadth": breadth(con), "macro": macro(con),
            "updated": (con.execute("SELECT MAX(updated) FROM market_live").fetchone() or [None])[0]}
