"""Serwer aplikacji: http://127.0.0.1:8050  (uruchom: python app.py; na serwerze: gunicorn wsgi:app)"""
import hmac
import ipaddress
import json
import re
import statistics
import threading
import webbrowser
from datetime import date, datetime, timedelta

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from gpwt import (alerts, analyses, collect, config, db, flags, flows, kalendarz, market, portfolio, pressure, quality, session,
                  technicals, trends)
from gpwt import ostrzezenia as gwarn
from gpwt.config import ROOT, SERVER_HOST, SERVER_PORT
from gpwt.util import ascii_fold, norm_investor

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="/static")
db.init()


def _ensure_af_rating_column():
    """Kolumna "Ocena AF" tworzona raz - jeśli użytkownik ją usunie, nie wraca."""
    with db.session() as c:
        if c.execute("SELECT 1 FROM settings WHERE key='af_rating_column'").fetchone():
            return
        if not c.execute("SELECT 1 FROM custom_columns WHERE key='ocena_af'").fetchone():
            c.execute("INSERT INTO custom_columns VALUES(?,?,?,?,?)",
                      ("ocena_af", "Ocena AF", "list", json.dumps(["Warto", "Obserwuj", "Nie warto"], ensure_ascii=False),
                       datetime.now().isoformat(timespec="seconds")))
        c.execute("INSERT INTO settings VALUES('af_rating_column', '1')")


_ensure_af_rating_column()
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

def _held(c):
    """Otwarte pozycje z zakładki Moje spółki: {ticker: {names: "IKE, Konto", qty}} - do kolumny "W portfelu"."""
    out = {}
    for r in c.execute("SELECT p.ticker, f.name, SUM(p.qty) q FROM positions p LEFT JOIN portfolios f "
                       "ON f.id=p.portfolio_id WHERE p.closed IS NULL GROUP BY p.ticker, f.name ORDER BY f.id"):
        h = out.setdefault(r["ticker"], {"names": [], "qty": 0.0})
        h["names"].append(r["name"] or "portfel")
        h["qty"] += r["q"]
    return {t: {"names": ", ".join(h["names"]), "qty": h["qty"]} for t, h in out.items()}


def _dividend_split(dl, today, y_ago, prev_session):
    """Dywidendy spółki: wypłacone w 12 mies. (po dniu odcięcia = dzień po ostatnim dniu z prawem), zapowiedziane,
    podział na regularne i jednorazowe. Wypłata jest jednorazowa, gdy jednocześnie:
      - jest ponad 2x wyższa od mediany wypłat z 3 poprzednich lat (co najmniej 2 wypłaty),
      - suma dywidend za jej rok obrotowy jest ponad 1,6x wyższa niż za rok poprzedni
    (drugi warunek odróżnia jednorazowy skok od spółek, które z roku na rok płacą więcej, np. banki)."""
    t = today.isoformat()
    seen, dated = set(), []
    for d in sorted(dl, key=lambda d: d["last_day"] or d["pay_day"] or ""):
        day = d["last_day"] or d["pay_day"]
        if (d["dps"] or 0) > 0 and day and (day, d["dps"]) not in seen:  # ta sama wypłata bywa w dwóch rocznikach
            seen.add((day, d["dps"]))
            dated.append(d)
    paid12 = [d for d in dated if y_ago < (d["last_day"] or d["pay_day"]) < t]
    upcoming = [d for d in dl if (d["last_day"] or "") >= t]
    year_total = {}
    for d in dated:
        year_total[d["year_for"]] = year_total.get(d["year_for"], 0) + d["dps"]
    oneoff = 0.0
    for d in paid12:
        day = d["last_day"] or d["pay_day"]
        start = f"{int(day[:4]) - 3}{day[4:]}"
        prev = [o["dps"] for o in dated if start <= (o["last_day"] or o["pay_day"]) < day]
        try:
            prev_year = year_total.get(str(int(d["year_for"]) - 1), 0)
        except (TypeError, ValueError):
            continue
        if len(prev) >= 2 and d["dps"] > 2 * statistics.median(prev) \
                and year_total.get(d["year_for"], 0) > 1.6 * prev_year:
            oneoff += d["dps"]
    dps12 = sum(d["dps"] for d in paid12) if paid12 else None
    ex = next((d for d in dl if prev_session and d["last_day"] == prev_session and (d["dps"] or 0) > 0), None)
    return {"paid12": paid12, "upcoming": upcoming, "dps12": dps12, "oneoff12": oneoff,
            "regular12": (dps12 or 0) - oneoff, "exdiv_today": ex["dps"] if ex else None}


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
    held = _held(c)
    tech = technicals.compute(c)["rows"]
    warn = gwarn.compute(c)
    qual = quality.compute(c)
    fl_auto, fl_man = flags.compute(c), flags.manual(c)
    palerts = {}
    for a in alerts.listing(c):
        if a["active"] or (a["triggered_at"] or "") >= (today - timedelta(days=3)).isoformat():
            palerts.setdefault(a["ticker"], []).append({k: a[k] for k in ("id", "kind", "price", "active", "triggered_at",
                                                                           "triggered_price", "distance", "note")})
    custom = {}
    for r in c.execute("SELECT * FROM custom_values"):
        custom.setdefault(r["ticker"], {})[f"c_{r['key']}"] = r["value"]
    af = analyses.scan(c)
    press = pressure.all_cmf(c)
    ds = [r[0] for r in c.execute("SELECT DISTINCT date FROM quotes ORDER BY date DESC LIMIT 2")]
    prev_session = ds[1] if len(ds) > 1 else None

    out = []
    for co in c.execute("SELECT * FROM companies ORDER BY ticker"):
        t = co["ticker"]
        q = last_q.get(t)
        price = q["close"] if q else None
        rr, ra = rets.get(t), rat.get(t)
        dl = divs.get(t, [])
        dv = _dividend_split(dl, today, y_ago, prev_session)
        paid12, upcoming, dps12 = dv["paid12"], dv["upcoming"], dv["dps12"]
        eps = price / ra["cz"] if price and ra and ra["cz"] and ra["cz"] > 0 else None
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
            "div_yield_regular": (dv["regular12"] / price * 100) if dps12 and price else None,
            "div_oneoff12": dv["oneoff12"] or None,
            "div_payout": (dps12 / eps * 100) if dps12 and eps else None,
            "exdiv_today": dv["exdiv_today"],
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
            "af_date": af[t][0]["date"] if af.get(t) else None,
            "pf": held.get(t, {}).get("names"), "pf_qty": held.get(t, {}).get("qty"),
            **{k: (tech.get(t) or {}).get(src) for k, src in (
                ("trend", "trend"), ("vs200", "vs200"), ("rs_1m", "rs_1m"), ("rs_3m", "rs_3m"), ("mom", "mom"),
                ("new_high52", "new_high52"), ("new_low52", "new_low52"))},
            "warnings": warn.get(t) or None,
            "price_alerts": palerts.get(t),
            "flag": (fl_man.get(t) or {}).get("flag") or (fl_auto.get(t) or {}).get("auto") or "neutral",
            "flag_manual": bool(fl_man.get(t)), "flag_score": (fl_auto.get(t) or {}).get("score"),
            **{k: (qual.get(t) or {}).get(src) for k, src in (
                ("quality", "quality"), ("rev_ttm_yoy", "rev_ttm_yoy"), ("np_ttm_yoy", "np_ttm_yoy"), ("rev_yoy", "rev_yoy"),
                ("np_yoy", "np_yoy"), ("roe", "roe"), ("roic", "roic"), ("net_margin", "net_margin"),
                ("nd_ebitda", "nd_ebitda"), ("net_cash", "net_cash"), ("fcf_ttm", "fcf_ttm"), ("fscore", "fscore"),
                ("altman", "altman"), ("altman_rating", "altman_rating"), ("div_streak", "div_streak"),
                ("payout", "payout"), ("cz_vs_med", "cz_vs_med"), ("cz_med5", "cz_med5"), ("shares_3y", "shares_3y"),
                ("fin_period", "period"))},
            "af_count": len(af.get(t, [])),
            "cmf21": press.get(t, {}).get(21),
            "cmf63": press.get(t, {}).get(63),
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
        "holder_groups": flows.holder_groups(c, ticker),
        "analyses": analyses.scan(c).get(ticker, []),
        "ohlc": pressure.series(c, ticker, (date.today() - timedelta(days=400)).isoformat()),
        "custom": {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM custom_values WHERE ticker=?",
                                                           (ticker,))},
    }
    res["quality"] = quality.compute(c).get(ticker)
    res["price_alerts"] = alerts.listing(c, ticker)
    res["flag"] = flags.detail(c, ticker)
    res["quarters"] = quality.quarters(c, ticker)
    af_col = c.execute("SELECT key, label, options FROM custom_columns WHERE key='ocena_af'").fetchone()
    res["af_column"] = ({"key": af_col["key"], "label": af_col["label"], "options": json.loads(af_col["options"] or "[]")}
                        if af_col else None)
    # notatka w panelu spółki = własna kolumna tekstowa "Komentarz" z tabeli Spółki (ta sama wartość)
    cm = c.execute("SELECT c.key, c.label, v.value, v.updated FROM custom_columns c LEFT JOIN custom_values v "
                   "ON v.key=c.key AND v.ticker=? WHERE c.type='text' AND (c.key='komentarz' OR lower(c.label)='komentarz') "
                   "ORDER BY c.key='komentarz' DESC LIMIT 1", (ticker,)).fetchone()
    res["comment"] = dict(cm) if cm else None
    c.close()
    return jsonify(res)


# ---------------- analizy fundamentalne (pliki z OneDrive) ----------------

@app.get("/api/analyses")
def list_analyses():
    c = con()
    af = analyses.scan(c)
    c.close()
    return jsonify({"assigned": sum(len(v) for k, v in af.items() if k), "unassigned": af.get(None, []),
                    "companies": len([k for k in af if k]), "last_sync": analyses.last_sync()})


@app.get("/af/<path:rel>")
def analysis_file(rel):
    return send_from_directory(analyses.AF_DIR, rel)


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

def _hide_red(c):
    """Spółki z red flag do pominięcia w listach - chyba że ?show_red=1."""
    return set() if request.args.get("show_red") == "1" else flags.hidden(c)


@app.get("/api/flows")
def get_flows():
    c = con()
    src = [s for s in (request.args.get("sources") or "").split(",") if s] or None
    r = flows.investor_flows(c, request.args.get("period", "week"), src,
                             request.args.get("from"), request.args.get("to"), _hide_red(c))
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
    hide = _hide_red(c)
    r = [x for x in db.rows(c, q, p) if x["ticker"] not in hide]
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
    # ręczna poprawka liczb, daty albo inwestora = wiersz sprawdzony; przeliczenie zmian go nie nadpisze
    if "verified" not in sets and sets.keys() & {"investor", "shares_before", "shares_after", "delta", "price", "date"}:
        row["verified"] = 1
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
    hide = _hide_red(c)
    r = [x for x in db.rows(c, q, p) if x["ticker"] not in hide]  # komunikaty bez spółki zostają
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


# ---------------- kontekst rynku ----------------

@app.get("/api/market")
def get_market():
    c = con()
    r = market.context(c)
    c.close()
    return jsonify(r)


# ---------------- alerty cenowe ----------------

@app.get("/api/alerts")
def get_alerts():
    c = con()
    r = alerts.listing(c, (request.args.get("ticker") or "").upper() or None)
    c.close()
    return jsonify({"alerts": r, "push": bool(config.HA_URL and config.HA_TOKEN and config.HA_NOTIFY)})


@app.post("/api/alerts")
def add_alert():
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: {"id": alerts.add(c, d)})


@app.patch("/api/alerts/<int:aid>")
def edit_alert(aid):
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: alerts.update(c, aid, d))


@app.delete("/api/alerts/<int:aid>")
def delete_alert(aid):
    return _portfolio_write(lambda c: alerts.delete(c, aid))


# ---------------- kalendarz ----------------

@app.get("/api/calendar")
def get_calendar():
    try:
        days = max(1, min(60, int(request.args.get("days", 14))))
    except ValueError:
        days = 14
    c = con()
    r = kalendarz.events(c, days)
    if request.args.get("hide_red") == "1":
        hide = flags.hidden(c)
        r["events"] = [e for e in r["events"] if e.get("ticker") not in hide]
    c.close()
    return jsonify(r)


# ---------------- trendy (średni termin) ----------------

@app.get("/api/trends")
def get_trends():
    a = request.args

    def num(k, d):
        try:
            return float(a.get(k, d))
        except ValueError:
            return d
    c = con()
    r = trends.summary(c, min_turn=num("min", 100_000), min_nc=num("min_nc", 30_000),
                       trend_only=a.get("trend", "1") != "0", fund_days=int(num("days", 365)),
                       hide=None if a.get("show_red") == "1" else flags.hidden(c))
    c.close()
    return jsonify(r)


# ---------------- moje spółki (portfel) ----------------

@app.get("/api/portfolio")
def get_portfolio():
    c = con()
    try:
        pid = int(request.args.get("pid") or 0) or None
    except ValueError:
        pid = None
    r = portfolio.summary(c, pid)
    c.close()
    return jsonify(r)


def _portfolio_write(fn):
    c = con()
    try:
        out = fn(c)
        c.commit()
        return jsonify({"ok": True, **(out or {})})
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    finally:
        c.close()


@app.put("/api/flags/<ticker>")
def put_flag(ticker):
    d = request.get_json(silent=True) or {}
    return _portfolio_write(lambda c: (flags.set_flag(c, ticker, d.get("flag"), d.get("note")),
                                       {"flag": flags.detail(c, ticker.upper())})[1])


@app.post("/api/portfolios")
def add_portfolio():
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: {"id": portfolio.create_portfolio(c, d.get("name"))})


@app.patch("/api/portfolios/<int:pid>")
def rename_portfolio(pid):
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: portfolio.rename_portfolio(c, pid, d.get("name")))


@app.delete("/api/portfolios/<int:pid>")
def delete_portfolio(pid):
    return _portfolio_write(lambda c: portfolio.delete_portfolio(c, pid))


@app.post("/api/positions")
def add_position():
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: {"id": portfolio.add_lot(c, d)})


@app.patch("/api/positions/<int:pid>")
def edit_position(pid):
    d = request.get_json(force=True)

    def fn(c):
        row = c.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()
        if not row:
            raise ValueError("Nie ma takiej partii")
        vals = {k: d.get(k, row[k]) for k in ("opened", "qty", "price", "fees")}
        if not portfolio._f(vals["qty"]) or portfolio._f(vals["price"]) is None:
            raise ValueError("Podaj liczbę akcji i cenę")
        if d.get("portfolio_id") and int(d["portfolio_id"]) != row["portfolio_id"]:
            portfolio.move_lot(c, pid, d["portfolio_id"])
        c.execute("UPDATE positions SET opened=?, qty=?, price=?, fees=? WHERE id=?",
                  (vals["opened"], portfolio._f(vals["qty"]), portfolio._f(vals["price"]),
                   portfolio._f(vals["fees"]) or 0, pid))
    return _portfolio_write(fn)


@app.delete("/api/positions/<int:pid>")
def delete_position(pid):
    return _portfolio_write(lambda c: c.execute("DELETE FROM positions WHERE id=?", (pid,)) and None)


@app.post("/api/positions/sell")
def sell_position():
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: portfolio.sell(c, d.get("portfolio_id"), d.get("ticker"), d.get("qty"),
                                                     d.get("price"), d.get("date"), d.get("fees")))


@app.put("/api/plans/<int:pid>/<ticker>")
def put_plan(pid, ticker):
    d = request.get_json(force=True)
    return _portfolio_write(lambda c: portfolio.save_plan(c, pid, ticker.upper(), d))


# ---------------- podsumowanie sesji ----------------

@app.get("/api/session")
def session_summary():
    c = con()
    pref = c.execute("SELECT value FROM settings WHERE key='ui_session'").fetchone()
    pref = json.loads(pref["value"]) if pref and pref["value"] else {}
    a = request.args
    try:
        min_t = float(a.get("min", pref.get("min", 100_000)))
    except ValueError:
        min_t = 100_000
    def num_arg(k, default):
        try:
            return float(a.get(k, pref.get(k, default)))
        except (TypeError, ValueError):
            return default
    r = session.summary(c, min_turnover=min_t, market=a.get("market", pref.get("market", "")),
                        watch_key=a.get("watch", pref.get("watch")) or None, min_nc=num_arg("min_nc", 30_000),
                        insider_sessions=int(num_arg("sessions", 1)) if num_arg("sessions", 1) in (1, 5, 20) else 1,
                        hide=None if str(a.get("show_red", pref.get("show_red", ""))) in ("1", "True", "true") else flags.hidden(c))
    c.close()
    return jsonify(r)


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
    body = request.get_json(silent=True) or {}
    weekly, quick = bool(body.get("weekly")), bool(body.get("quick"))
    with _job_lock:  # serwer wielowątkowy: dwa kliknięcia naraz nie mogą uruchomić dwóch pobierań
        if _job["running"]:
            return jsonify({"started": False, "msg": "Zbieranie już trwa"})
        _job["running"] = True

    def work():
        try:
            collect.run(weekly=weekly, quick=quick)
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
