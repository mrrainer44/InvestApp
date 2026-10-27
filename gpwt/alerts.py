"""Alerty cenowe: "kup, gdy kurs spadnie do X" i "sprzedaj, gdy kurs wzrośnie do Y".

Sprawdzane przy każdym pobraniu notowań (w dni sesyjne 10:00, 13:00, 17:10 i 18:30). Pod uwagę bierzemy także
minimum i maksimum dnia, więc alert zadziała, gdy kurs dotknie progu w trakcie sesji, nawet jeśli potem odbił.
Alert jest jednorazowy: po zadziałaniu przestaje być aktywny i jest "zrealizowany" - wyróżniony, dopóki go nie
odhaczysz (done). Zrealizowany albo odhaczony alert można włączyć ponownie, także z nową ceną. Opcjonalnie wysyłamy
powiadomienie przez Home Assistant (config: GPWT_HA_URL, GPWT_HA_TOKEN, GPWT_HA_NOTIFY).
"""
import json
import logging
from datetime import datetime

import requests

from . import config

log = logging.getLogger("gpwt.alerts")
KINDS = {"buy": "kupno", "sell": "sprzedaż"}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _f(v):
    try:
        return float(str(v).replace(",", ".").replace(" ", "")) if v not in (None, "") else None
    except ValueError:
        return None


def add(con, d):
    t = (d.get("ticker") or "").strip().upper()
    kind, price = d.get("kind"), _f(d.get("price"))
    if kind not in KINDS or not price or price <= 0:
        raise ValueError("Podaj rodzaj alertu (kupno lub sprzedaż) i cenę większą od zera")
    if not con.execute("SELECT 1 FROM companies WHERE ticker=?", (t,)).fetchone():
        raise ValueError(f"Nie znam spółki {t}")
    return con.execute("INSERT INTO price_alerts(ticker, kind, price, note, created) VALUES(?,?,?,?,?)",
                       (t, kind, price, (d.get("note") or "").strip() or None, _now())).lastrowid


def update(con, aid, d):
    row = con.execute("SELECT * FROM price_alerts WHERE id=?", (aid,)).fetchone()
    if not row:
        raise ValueError("Nie ma takiego alertu")
    price = _f(d["price"]) if "price" in d else row["price"]
    if not price or price <= 0:
        raise ValueError("Cena musi być większa od zera")
    kind = d.get("kind", row["kind"])
    if kind not in KINDS:
        raise ValueError("Nieznany rodzaj alertu")
    note = (d.get("note") or "").strip() or None if "note" in d else row["note"]
    rearm = bool(d.get("rearm"))
    done = row["done"]
    if "done" in d and not rearm:
        if d["done"] and row["active"]:
            raise ValueError("Odhaczyć można tylko alert, który zadziałał")
        done = _now() if d["done"] else None
    con.execute("UPDATE price_alerts SET kind=?, price=?, note=?, active=?, triggered_at=?, triggered_price=?, notified=?, "
                "done=? WHERE id=?", (kind, price, note, 1 if rearm else row["active"],
                                      None if rearm else row["triggered_at"], None if rearm else row["triggered_price"],
                                      0 if rearm else row["notified"], None if rearm else done, aid))


def delete(con, aid):
    con.execute("DELETE FROM price_alerts WHERE id=?", (aid,))


def _quotes(con):
    """Kurs z ostatniego pobrania oraz minimum/maksimum dnia (jeśli spółka miała dziś transakcje)."""
    day = (con.execute("SELECT MAX(date) FROM quotes").fetchone() or [None])[0]
    if not day:
        return None, {}
    q = {r["ticker"]: {"close": r["close"], "chg": r["change_pct"], "low": r["close"], "high": r["close"]}
         for r in con.execute("SELECT ticker, close, change_pct FROM quotes WHERE date=?", (day,))}
    for r in con.execute("SELECT ticker, high, low FROM ohlc WHERE date=?", (day,)):
        if r["ticker"] in q:
            q[r["ticker"]]["high"] = max(x for x in (r["high"], q[r["ticker"]]["close"]) if x is not None)
            q[r["ticker"]]["low"] = min(x for x in (r["low"], q[r["ticker"]]["close"]) if x is not None)
    return day, q


def listing(con, ticker=None):
    _, q = _quotes(con)
    names = {r[0]: r[1] for r in con.execute("SELECT ticker, COALESCE(full_name, short_name) FROM companies")}
    held = {r[0] for r in con.execute("SELECT DISTINCT ticker FROM positions WHERE closed IS NULL")}
    # najpierw zrealizowane (do odhaczenia), potem aktywne, na końcu odhaczone
    sql = ("SELECT * FROM price_alerts" + (" WHERE ticker=?" if ticker else "") +
           " ORDER BY CASE WHEN active=0 AND done IS NULL THEN 0 WHEN active=1 THEN 1 ELSE 2 END, triggered_at DESC, id")
    out = []
    for r in con.execute(sql, (ticker,) if ticker else ()):
        x = dict(r)
        close = (q.get(r["ticker"]) or {}).get("close")
        x.update(name=names.get(r["ticker"]), close=close, held=r["ticker"] in held, kind_label=KINDS[r["kind"]],
                 state="active" if r["active"] else "done" if r["done"] else "hit",
                 # odległość do progu: ile kurs musi spaść (kupno) albo wzrosnąć (sprzedaż), w %
                 distance=((r["price"] / close - 1) * 100) if close else None)
        out.append(x)
    return out


def check(con, stats=None):
    """Sprawdza aktywne alerty względem notowań z ostatniego pobrania. Zwraca listę alertów, które zadziałały."""
    day, q = _quotes(con)
    hit = []
    for r in con.execute("SELECT * FROM price_alerts WHERE active=1").fetchall():
        x = q.get(r["ticker"])
        if not x or x["close"] is None:
            continue
        if r["kind"] == "buy" and x["low"] is not None and x["low"] <= r["price"]:
            touched = x["low"]
        elif r["kind"] == "sell" and x["high"] is not None and x["high"] >= r["price"]:
            touched = x["high"]
        else:
            continue
        con.execute("UPDATE price_alerts SET active=0, triggered_at=?, triggered_price=? WHERE id=?",
                    (_now(), touched, r["id"]))
        hit.append({**dict(r), "touched": touched, "close": x["close"], "day": day})
    con.commit()
    if hit:
        log.info("Alerty cenowe: zadziałało %s (%s)", len(hit), ", ".join(f"{h['ticker']} {h['kind']}" for h in hit))
        _notify(con, hit)
    if stats is not None and hit:
        stats["price_alerts"] = len(hit)
    return hit


def message(h):
    verb = "spadł do" if h["kind"] == "buy" else "wzrósł do"
    p = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
    return (f"{h['ticker']}: kurs {verb} {p(h['touched'])} zł (alert {KINDS[h['kind']]} {p(h['price'])} zł), "
            f"ostatni {p(h['close'])} zł" + (f" – {h['note']}" if h.get("note") else ""))


def _notify(con, hit):
    if not (config.HA_URL and config.HA_TOKEN and config.HA_NOTIFY):
        return
    domain, _, service = config.HA_NOTIFY.partition(".")
    for h in hit:
        try:
            r = requests.post(f"{config.HA_URL}/api/services/{domain}/{service}",
                              headers={"Authorization": f"Bearer {config.HA_TOKEN}"}, timeout=15,
                              data=json.dumps({"title": f"GPW Tracker: alert {KINDS[h['kind']]} {h['ticker']}",
                                               "message": message(h)}))
            if r.ok:
                con.execute("UPDATE price_alerts SET notified=1 WHERE id=?", (h["id"],))
            else:
                log.warning("Powiadomienie Home Assistant: HTTP %s", r.status_code)
        except requests.RequestException as e:
            log.warning("Powiadomienie Home Assistant: %s", e)
    con.commit()
