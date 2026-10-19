"""Serwer aplikacji: http://127.0.0.1:8050  (uruchom: python app.py; na serwerze: gunicorn wsgi:app)"""
import hmac
import ipaddress
import json
import re
import threading
import webbrowser
from datetime import date, datetime, timedelta

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from gpwt import collect, config, db, flows
from gpwt.config import ROOT, SERVER_HOST, SERVER_PORT
from gpwt.util import ascii_fold, norm_investor

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
db.init()
_job = {"running": False, "last": None}
_job_lock = threading.Lock()


@app.before_request
def require_login():
    if not config.AUTH_PASSWORD:
        if config.LAN_NO_PASSWORD:
            ip = ipaddress.ip_address(request.remote_addr or "0.0.0.0")
            if not (ip.is_private or ip.is_loopback):
                abort(403)
        return None
    a = request.authorization
    if a and hmac.compare_digest((a.username or "").encode(), config.AUTH_USER.encode()) \
            and hmac.compare_digest((a.password or "").encode(), config.AUTH_PASSWORD.encode()):
        return None
    return Response("Wymagane logowanie", 401, {"WWW-Authenticate": 'Basic realm="GPW Tracker", charset="UTF-8"'})


def con():
    return db.connect()


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------- lista spółek ----------------

@app.get("/api/companies")
def companies():
    c = con()
    today = date.today()
    y_ago = (today - timedelta(days=365)).isoformat()
    d30 = (today - timedelta(days=30)).isoformat()

    last_q = {r["ticker"]: r for r in c.execute(
        "SELECT q.* FROM quotes q JOIN (SELECT ticker, MAX(date) d FROM quotes GROUP BY ticker) m "
        "ON q.ticker=m.ticker AND q.date=m.d")}
    avg_turn = {r["ticker"]: r["a"] for r in c.execute(
        "SELECT ticker, AVG(turnover) a, COUNT(*) n FROM (SELECT * FROM quotes WHERE date>=? ) GROUP BY ticker",
        ((today - timedelta(days=30)).isoformat(),))}
    rets = {r["ticker"]: r for r in c.execute("SELECT * FROM returns")}
    rat = {r["ticker"]: r for r in c.execute("SELECT * FROM ratios")}
    divs = {}
    for r in c.execute("SELECT * FROM dividends ORDER BY last_day"):
        divs.setdefault(r["ticker"], []).append(r)
    holders = {}
    for r in c.execute(
            "SELECT h.* FROM holdings_snap h JOIN (SELECT ticker, holder_norm, MAX(date_upd) d FROM holdings_snap "
            "WHERE source='BR' GROUP BY ticker, holder_norm) m ON h.ticker=m.ticker AND h.holder_norm=m.holder_norm "
            "AND h.date_upd=m.d AND h.source='BR' ORDER BY h.pct DESC"):
        holders.setdefault(r["ticker"], []).append(r)
    flows30 = {r["ticker"]: r for r in c.execute(
        "SELECT ticker, SUM(value) v, COUNT(*) n FROM changes WHERE excluded=0 AND date>=? GROUP BY ticker", (d30,))}
    last_art = {r["ticker"]: r for r in c.execute(
        "SELECT c.ticker, c.date, c.investor, c.delta FROM changes c JOIN (SELECT ticker, MAX(date) d FROM changes "
        "WHERE source='art69' AND excluded=0 GROUP BY ticker) m ON c.ticker=m.ticker AND c.date=m.d "
        "WHERE c.source='art69'")}
    custom = {}
    for r in c.execute("SELECT * FROM custom_values"):
        custom.setdefault(r["ticker"], {})[f"c_{r['key']}"] = r["value"]

    out = []
    for co in c.execute("SELECT * FROM companies ORDER BY ticker"):
        t = co["ticker"]
        q = last_q.get(t)
        price = q["close"] if q else None
        rr, ra = rets.get(t), rat.get(t)
        dl = divs.get(t, [])
        paid12 = [d for d in dl if (d["pay_day"] or d["last_day"] or "") >= y_ago
                  and (d["last_day"] or "9") <= today.isoformat()]
        upcoming = [d for d in dl if (d["last_day"] or "") >= today.isoformat()]
        dps12 = sum(d["dps"] for d in paid12) if paid12 else None
        hs = holders.get(t, [])
        big = [h for h in hs if (h["pct"] or 0) >= 5]
        f30 = flows30.get(t)
        la = last_art.get(t)
        row = {
            "ticker": t, "name": co["full_name"] or co["short_name"], "short": co["short_name"],
            "market": co["market"], "sector": co["sector"], "slug": co["slug"],
            "price": price, "change_pct": q["change_pct"] if q else None,
            "volume": q["volume"] if q else None, "turnover": q["turnover"] if q else None,
            "avg_turnover_30d": avg_turn.get(t),
            "mcap": (price * co["shares"]) if price and co["shares"] else None,
            "shares": co["shares"],
            "r1w": rr["r1w"] if rr else None, "r1m": rr["r1m"] if rr else None, "r3m": rr["r3m"] if rr else None,
            "r6m": rr["r6m"] if rr else None, "ytd": rr["ytd"] if rr else None, "r12m": rr["r12m"] if rr else None,
            "cz": ra["cz"] if ra else None, "cwk": ra["cwk"] if ra else None,
            "evebitda": ra["evebitda"] if ra else None, "cp": ra["cp"] if ra else None,
            "report": ra["report"] if ra else None,
            "div_has": bool(paid12 or upcoming),
            "div_dps12": dps12,
            "div_yield": (dps12 / price * 100) if dps12 and price else None,
            "div_next_day": upcoming[0]["last_day"] if upcoming else None,
            "div_next_dps": upcoming[0]["dps"] if upcoming else None,
            "top_holders": "; ".join(f"{h['holder']} {h['pct']:.1f}%" for h in big[:3] if h["pct"] is not None),
            "free_float": (100 - sum(h["pct"] for h in big if h["pct"])) if big else None,
            "funds_pct": sum(h["pct"] or 0 for h in hs if any(x in (h["holder_norm"] or "").split()
                                                               for x in flows.FUND_RE)) or None,
            "last_art69": f"{la['date']} {la['investor']} ({'+' if la['delta'] > 0 else ''}{la['delta']:,.0f})"
            .replace(",", " ") if la else None,
            "flow_30d": f30["v"] if f30 else None,
            "flow_30d_n": f30["n"] if f30 else None,
        }
        row.update(custom.get(t, {}))
        out.append(row)
    c.close()
    return jsonify(out)


@app.get("/api/company/<ticker>")
def company(ticker):
    c = con()
    co = c.execute("SELECT * FROM companies WHERE ticker=?", (ticker,)).fetchone()
    if not co:
        abort(404)
    res = {
        "company": dict(co),
        "holders": db.rows(c, "SELECT h.* FROM holdings_snap h WHERE ticker=? ORDER BY date_upd DESC, pct DESC",
                           (ticker,)),
        "changes": db.rows(c, "SELECT * FROM changes WHERE ticker=? ORDER BY date DESC", (ticker,)),
        "espi": db.rows(c, "SELECT id, ts, category, title, url FROM espi WHERE ticker=? ORDER BY id DESC LIMIT 60",
                        (ticker,)),
        "dividends": db.rows(c, "SELECT * FROM dividends WHERE ticker=? ORDER BY last_day DESC", (ticker,)),
        "prices": db.rows(c, "SELECT date, close FROM price_history WHERE ticker=? ORDER BY date", (ticker,)),
    }
    c.close()
    return jsonify(res)


# ---------------- własne kolumny ----------------

@app.get("/api/columns")
def get_columns():
    c = con()
    r = db.rows(c, "SELECT * FROM custom_columns ORDER BY created")
    c.close()
    return jsonify(r)


@app.post("/api/columns")
def add_column():
    d = request.get_json(force=True)
    label = (d.get("label") or "").strip()
    if not label:
        abort(400, "Brak nazwy kolumny")
    typ = d.get("type", "text")
    if typ not in ("text", "number", "bool", "date", "list"):
        abort(400, "Nieznany typ")
    key = re.sub(r"[^a-z0-9]+", "_", ascii_fold(label).lower()).strip("_")[:40] or "kol"
    c = con()
    base, i = key, 2
    while c.execute("SELECT 1 FROM custom_columns WHERE key=?", (key,)).fetchone():
        key, i = f"{base}_{i}", i + 1
    c.execute("INSERT INTO custom_columns VALUES(?,?,?,?,?)",
              (key, label, typ, json.dumps(d.get("options") or [], ensure_ascii=False),
               datetime.now().isoformat(timespec="seconds")))
    c.commit()
    c.close()
    return jsonify({"key": key})


@app.delete("/api/columns/<key>")
def del_column(key):
    c = con()
    c.execute("DELETE FROM custom_values WHERE key=?", (key,))
    c.execute("DELETE FROM custom_columns WHERE key=?", (key,))
    c.commit()
    c.close()
    return jsonify({"ok": True})


@app.put("/api/values")
def put_value():
    d = request.get_json(force=True)
    c = con()
    if d.get("value") in (None, ""):
        c.execute("DELETE FROM custom_values WHERE ticker=? AND key=?", (d["ticker"], d["key"]))
    else:
        c.execute("INSERT OR REPLACE INTO custom_values VALUES(?,?,?,?)",
                  (d["ticker"], d["key"], str(d["value"]), datetime.now().isoformat(timespec="seconds")))
    c.commit()
    c.close()
    return jsonify({"ok": True})


# ---------------- ustawienia (układ kolumn, filtry) ----------------

@app.get("/api/settings/<name>")
def get_setting(name):
    c = con()
    r = c.execute("SELECT value FROM settings WHERE key=?", (f"ui_{name}",)).fetchone()
    c.close()
    return jsonify(json.loads(r["value"]) if r else None)


@app.put("/api/settings/<name>")
def put_setting(name):
    c = con()
    c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (f"ui_{name}", json.dumps(request.get_json(force=True))))
    c.commit()
    c.close()
    return jsonify({"ok": True})


# ---------------- inwestorzy / zmiany ----------------

@app.get("/api/flows")
def get_flows():
    c = con()
    src = [s for s in (request.args.get("sources") or "").split(",") if s] or None
    r = flows.investor_flows(c, request.args.get("period", "week"), src,
                             request.args.get("from"), request.args.get("to"))
    c.close()
    return jsonify(r)


@app.get("/api/changes")
def get_changes():
    c = con()
    q, p = ("SELECT c.*, co.full_name, e.url AS espi_url, e.ts AS report_ts FROM changes c "
            "LEFT JOIN companies co ON co.ticker=c.ticker LEFT JOIN espi e ON e.id=c.espi_id/10 WHERE 1=1"), []
    for arg, col in (("ticker", "c.ticker"), ("source", "c.source")):
        if request.args.get(arg):
            q += f" AND {col}=?"
            p.append(request.args[arg])
    if request.args.get("investor_norm"):
        q += " AND c.investor_norm=?"
        p.append(request.args["investor_norm"])
    if request.args.get("from"):
        q += " AND c.date>=?"
        p.append(request.args["from"])
    q += " ORDER BY c.date DESC LIMIT 5000"
    al = flows.aliases(c)
    r = db.rows(c, q, p)
    for x in r:
        x["investor_display"] = al.get(x["investor_norm"]) or x["investor"]
    c.close()
    return jsonify(r)


@app.patch("/api/changes/<int:cid>")
def patch_change(cid):
    d = request.get_json(force=True)
    allowed = {"investor", "shares_before", "shares_after", "delta", "price", "verified", "excluded", "note", "date"}
    sets = {k: v for k, v in d.items() if k in allowed}
    if not sets:
        abort(400)
    c = con()
    row = dict(c.execute("SELECT * FROM changes WHERE id=?", (cid,)).fetchone())
    row.update(sets)
    if "investor" in sets:
        row["investor_norm"] = norm_investor(row["investor"])
    if ("shares_before" in sets or "shares_after" in sets) and row["shares_before"] is not None \
            and row["shares_after"] is not None:
        row["delta"] = row["shares_after"] - row["shares_before"]
    row["value"] = row["delta"] * row["price"] if row["delta"] is not None and row["price"] else None
    if "price" in sets:
        row["price_src"] = "ręcznie"
    c.execute("""UPDATE changes SET date=?, investor=?, investor_norm=?, shares_before=?, shares_after=?, delta=?,
                 price=?, price_src=?, value=?, verified=?, excluded=?, note=? WHERE id=?""",
              (row["date"], row["investor"], row["investor_norm"], row["shares_before"], row["shares_after"],
               row["delta"], row["price"], row["price_src"], row["value"], row["verified"], row["excluded"],
               row["note"], cid))
    c.commit()
    c.close()
    return jsonify(row)


@app.get("/api/investors")
def investors():
    c = con()
    al = flows.aliases(c)
    r = db.rows(c, "SELECT investor_norm, MAX(investor) investor, COUNT(*) n, SUM(COALESCE(value,0)) net "
                   "FROM changes WHERE excluded=0 GROUP BY investor_norm ORDER BY n DESC")
    for x in r:
        x["canonical"] = al.get(x["investor_norm"])
    c.close()
    return jsonify(r)


@app.post("/api/aliases")
def set_alias():
    d = request.get_json(force=True)
    c = con()
    if d.get("canonical"):
        c.execute("INSERT OR REPLACE INTO investor_aliases VALUES(?,?)", (d["alias_norm"], d["canonical"].strip()))
    else:
        c.execute("DELETE FROM investor_aliases WHERE alias_norm=?", (d["alias_norm"],))
    c.commit()
    c.close()
    return jsonify({"ok": True})


@app.get("/api/espi")
def get_espi():
    c = con()
    days = int(request.args.get("days", 30))
    q = ("SELECT e.id, e.ts, e.ticker, e.company, e.title, e.url, e.category, e.parsed, e.fetched, co.market "
         "FROM espi e LEFT JOIN companies co ON co.ticker=e.ticker WHERE e.ts>=?")
    p = [(date.today() - timedelta(days=days)).isoformat()]
    cats = [x for x in (request.args.get("categories") or "").split(",") if x]
    if cats:
        q += f" AND e.category IN ({','.join('?' * len(cats))})"
        p += cats
    q += " ORDER BY e.id DESC LIMIT 3000"
    r = db.rows(c, q, p)
    c.close()
    return jsonify(r)


@app.post("/api/espi/<int:eid>/ticker")
def set_espi_ticker(eid):
    t = (request.get_json(force=True).get("ticker") or "").upper() or None
    c = con()
    c.execute("UPDATE espi SET ticker=? WHERE id=?", (t, eid))
    c.commit()
    flows.rebuild_changes(c)
    flows.fill_prices(c, max_tickers=5)
    c.close()
    return jsonify({"ok": True})


# ---------------- status i ręczne uruchomienie ----------------

@app.get("/api/status")
def status():
    c = con()
    runs = db.rows(c, "SELECT * FROM runs ORDER BY id DESC LIMIT 15")
    counts = {k: c.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0]
              for k in ("companies", "quotes", "espi", "changes", "holdings_snap", "dividends")}
    c.close()
    return jsonify({"runs": runs, "counts": counts, "job_running": _job["running"]})


@app.post("/api/collect")
def run_collect():
    weekly = bool((request.get_json(silent=True) or {}).get("weekly"))
    with _job_lock:  # serwer wielowątkowy: dwa kliknięcia naraz nie mogą uruchomić dwóch pobierań
        if _job["running"]:
            return jsonify({"started": False, "msg": "Zbieranie już trwa"})
        _job["running"] = True

    def work():
        try:
            collect.run(weekly=weekly)
        finally:
            _job["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return jsonify({"started": True})


if __name__ == "__main__":
    import sys
    if SERVER_HOST not in ("127.0.0.1", "localhost", "::1") and not (config.AUTH_PASSWORD or config.LAN_NO_PASSWORD):
        sys.exit("Serwer ma nasłuchiwać poza tym komputerem (GPWT_HOST=%s) - ustaw najpierw GPWT_PASSWORD, "
                 "bo bez hasła każdy mógłby edytować dane i uruchamiać pobieranie." % SERVER_HOST)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{SERVER_HOST}:{SERVER_PORT}")).start()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
