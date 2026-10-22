"""Moje spółki: portfele (zakupy w partiach), plan dla każdej pozycji i alerty tylko dla posiadanych papierów.

  portfolios - nazwane portfele (np. IKE i zwykłe konto); wyniki liczone osobno i łącznie,
  positions  - partie zakupu w portfelu: ticker, data, liczba akcji, cena, prowizja; sprzedaż zamyka partie od
               najstarszej (FIFO), a częściowa sprzedaż dzieli partię na sprzedaną i pozostałą,
  plans      - plan pozycji (portfel + spółka): dlaczego kupiłem, poziom wyjścia na stracie, cel, horyzont, przegląd.

Wynik liczony od kursu z ostatniego pobrania (w trakcie sesji - bieżącego), porównanie z WIG od dnia zakupu
(zamknięcie indeksu z archiwum gpw.pl). Alerty to podpowiedzi, co sprawdzić, a nie rekomendacje.
"""
from datetime import date, datetime, timedelta

from .pressure import index_close
from .session import _avg_turnover, _subject, session_days

PLAN_FIELDS = ("thesis", "stop", "target", "horizon", "review", "notes")
EXIT_SHARE = 0.2  # przy wyjściu realnie da się sprzedać ok. 20% dziennego obrotu bez mocnego ruchu kursu


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------- portfele ----------------

def portfolios(con):
    return [dict(r) for r in con.execute("SELECT id, name FROM portfolios ORDER BY id")]


def create_portfolio(con, name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Podaj nazwę portfela")
    if con.execute("SELECT 1 FROM portfolios WHERE name=?", (name,)).fetchone():
        raise ValueError(f"Portfel „{name}” już istnieje")
    return con.execute("INSERT INTO portfolios(name, created) VALUES(?,?)", (name, _now())).lastrowid


def rename_portfolio(con, pid, name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Podaj nazwę portfela")
    if con.execute("SELECT 1 FROM portfolios WHERE name=? AND id<>?", (name, pid)).fetchone():
        raise ValueError(f"Portfel „{name}” już istnieje")
    con.execute("UPDATE portfolios SET name=? WHERE id=?", (name, pid))


def delete_portfolio(con, pid):
    if con.execute("SELECT 1 FROM positions WHERE portfolio_id=?", (pid,)).fetchone():
        raise ValueError("W portfelu są pozycje lub historia sprzedaży - usuń je najpierw")
    con.execute("DELETE FROM plans WHERE portfolio_id=?", (pid,))
    con.execute("DELETE FROM portfolios WHERE id=?", (pid,))


def _pid(con, v):
    """Portfel z formularza; gdy nie ma żadnego - tworzymy pierwszy."""
    pid = int(_f(v) or 0)
    if pid:
        if not con.execute("SELECT 1 FROM portfolios WHERE id=?", (pid,)).fetchone():
            raise ValueError("Nie ma takiego portfela")
        return pid
    first = con.execute("SELECT id FROM portfolios ORDER BY id LIMIT 1").fetchone()
    return first[0] if first else create_portfolio(con, "Mój portfel")


# ---------------- zakupy, sprzedaż, plan ----------------

def save_plan(con, pid, ticker, d):
    cur = con.execute("SELECT * FROM plans WHERE portfolio_id=? AND ticker=?", (pid, ticker)).fetchone()
    row = {k: (cur[k] if cur else None) for k in PLAN_FIELDS}
    for k in PLAN_FIELDS:
        if k in d:
            row[k] = _f(d[k]) if k in ("stop", "target") else ((d[k] or "").strip() or None)
    con.execute("INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?,?,?,?,?)",
                (pid, ticker, *[row[k] for k in PLAN_FIELDS], _now()))


def add_lot(con, d):
    t = (d.get("ticker") or "").strip().upper()
    qty, price = _f(d.get("qty")), _f(d.get("price"))
    if not t or not qty or qty <= 0 or price is None or price < 0:
        raise ValueError("Podaj ticker, liczbę akcji i cenę zakupu")
    if not con.execute("SELECT 1 FROM companies WHERE ticker=?", (t,)).fetchone():
        raise ValueError(f"Nie znam spółki {t}")
    pid = _pid(con, d.get("portfolio_id"))
    cur = con.execute("INSERT INTO positions(ticker, opened, qty, price, fees, created, portfolio_id) "
                      "VALUES(?,?,?,?,?,?,?)", (t, d.get("opened") or date.today().isoformat(), qty, price,
                                                 _f(d.get("fees")) or 0, _now(), pid))
    plan = {k: d[k] for k in PLAN_FIELDS if k in d and d[k] not in (None, "")}
    if plan or not con.execute("SELECT 1 FROM plans WHERE portfolio_id=? AND ticker=?", (pid, t)).fetchone():
        save_plan(con, pid, t, plan)
    return cur.lastrowid


def sell(con, pid, ticker, qty, price, day=None, fees=0):
    """Sprzedaż qty akcji z portfela: zamyka partie od najstarszej, ostatnią dzieli. Prowizja proporcjonalnie."""
    pid = _pid(con, pid)
    qty, price, fees = _f(qty), _f(price), _f(fees) or 0
    lots = con.execute("SELECT * FROM positions WHERE portfolio_id=? AND ticker=? AND closed IS NULL "
                       "ORDER BY opened, id", (pid, ticker)).fetchall()
    held = sum(r["qty"] for r in lots)
    if not qty or qty <= 0 or price is None or qty > held + 1e-9:
        raise ValueError(f"Masz w tym portfelu {held:g} akcji {ticker} - podaj liczbę akcji do sprzedaży i cenę")
    day = day or date.today().isoformat()
    left = qty
    for r in lots:
        if left <= 1e-9:
            break
        take = min(r["qty"], left)
        fee = fees * take / qty
        if take < r["qty"] - 1e-9:  # część partii: sprzedana część jako osobny, zamknięty wiersz
            part_fee = (r["fees"] or 0) * take / r["qty"]
            con.execute("UPDATE positions SET qty=?, fees=? WHERE id=?", (r["qty"] - take, (r["fees"] or 0) - part_fee, r["id"]))
            con.execute("INSERT INTO positions(ticker, opened, qty, price, fees, closed, close_price, close_fees, created, "
                        "portfolio_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (ticker, r["opened"], take, r["price"], part_fee, day, price, fee, _now(), pid))
        else:
            con.execute("UPDATE positions SET closed=?, close_price=?, close_fees=? WHERE id=?", (day, price, fee, r["id"]))
        left -= take


def move_lot(con, lot_id, pid):
    pid = _pid(con, pid)
    con.execute("UPDATE positions SET portfolio_id=? WHERE id=?", (pid, lot_id))


def _sessions_back(con, n):
    ds = session_days(con, n + 1)
    return ds[-1] if ds else None


# ---------------- wyniki ----------------

def _totals(rows, closed):
    value = sum(r["value"] or 0 for r in rows)
    cost = sum(r["cost"] for r in rows)
    today = sum(r["today_pnl"] or 0 for r in rows)
    wig = sum((r["wig_pct"] or 0) * r["cost"] for r in rows) / cost if cost and any(
        r["wig_pct"] is not None for r in rows) else None
    pct = (value / cost - 1) * 100 if cost else None
    return {"value": value, "cost": cost, "pnl": value - cost, "pnl_pct": pct, "today_pnl": today,
            "today_pct": today / (value - today) * 100 if value - today else None, "wig_pct": wig,
            "vs_wig": (pct - wig) if pct is not None and wig is not None else None,
            "realized": sum(c["pnl"] for c in closed), "n": len(rows)}


def summary(con, portfolio_id=None):
    """portfolio_id=None - wszystkie portfele razem (pozycje osobno dla każdego portfela) i wyniki każdego z nich."""
    today = date.today().isoformat()
    pfs = portfolios(con)
    pname = {p["id"]: p["name"] for p in pfs}
    lots = [dict(r) for r in con.execute("SELECT * FROM positions ORDER BY opened, id")]
    day = (con.execute("SELECT MAX(date) FROM quotes").fetchone() or [None])[0]
    q = {r["ticker"]: r for r in con.execute("SELECT * FROM quotes WHERE date=?", (day,))} if day else {}
    names = {r["ticker"]: (r["full_name"] or r["short_name"], r["market"]) for r in con.execute(
        "SELECT ticker, full_name, short_name, market FROM companies")}
    plans = {(r["portfolio_id"], r["ticker"]): dict(r) for r in con.execute("SELECT * FROM plans")}
    avg = _avg_turnover(con, day) if day else {}
    wig_last = (con.execute("SELECT MAX(date) FROM index_ohlc WHERE name='WIG'").fetchone() or [None])[0]
    # zamknięcie z archiwum gpw.pl pojawia się dopiero wieczorem albo następnego dnia - w trakcie sesji i zaraz po niej
    # bierzemy bieżącą wartość WIG z Biznesradar (market_live), jeśli jest nowsza
    live = con.execute("SELECT value, ts FROM market_live WHERE key='WIG'").fetchone()
    use_live = bool(live and live["value"] and (not wig_last or live["ts"][:10] > wig_last))
    wig_ref = live["ts"][:10] if use_live else wig_last
    # starsze niż tydzień = brak danych (nie porównujemy z zerem)
    fresh = wig_ref and day and (date.fromisoformat(day) - date.fromisoformat(wig_ref)).days <= 7
    wig_now = (live["value"] if use_live else index_close(con, "WIG", today)) if fresh else None
    wig_asof = (live["ts"] if use_live else wig_last) if fresh else None
    prev = _sessions_back(con, 1)

    hold = {}
    for x in lots:
        if x["closed"]:
            continue
        k = (x["portfolio_id"], x["ticker"])
        h = hold.setdefault(k, {"qty": 0.0, "cost": 0.0, "lots": [], "wig_w": 0.0})
        h["qty"] += x["qty"]
        h["cost"] += x["qty"] * x["price"] + (x["fees"] or 0)
        h["lots"].append({c: x[c] for c in ("id", "opened", "qty", "price", "fees")})
        w0 = index_close(con, "WIG", x["opened"])
        if w0 and wig_now:  # WIG od daty zakupu, ważony kosztem partii
            h["wig_w"] += (wig_now / w0 - 1) * (x["qty"] * x["price"])
    rows = []
    for (pid, t), h in hold.items():
        qq = q.get(t)
        close = qq["close"] if qq else None
        chg = qq["change_pct"] if qq else None
        value = close * h["qty"] if close is not None else None
        base = sum(lt["qty"] * lt["price"] for lt in h["lots"]) or 1
        r = {"portfolio_id": pid, "portfolio": pname.get(pid, "?"), "ticker": t,
             "name": names.get(t, (t, None))[0], "market": names.get(t, (None, None))[1],
             "qty": h["qty"], "avg_price": h["cost"] / h["qty"], "cost": h["cost"], "close": close, "chg": chg,
             "value": value, "pnl": (value - h["cost"]) if value is not None else None,
             "pnl_pct": ((value / h["cost"] - 1) * 100) if value is not None and h["cost"] else None,
             "wig_pct": h["wig_w"] / base * 100 if wig_now else None,
             "today_pnl": (value - value / (1 + chg / 100)) if value is not None and chg is not None else None,
             "first_opened": min(lt["opened"] for lt in h["lots"]), "lots": h["lots"],
             "plan": {k: (plans.get((pid, t)) or {}).get(k) for k in PLAN_FIELDS}, "avg20": avg.get(t)}
        r["vs_wig"] = (r["pnl_pct"] - r["wig_pct"]) if r["pnl_pct"] is not None and r["wig_pct"] is not None else None
        r["exit_days"] = (value / (avg[t] * EXIT_SHARE)) if value and avg.get(t) else None
        rows.append(r)

    closed = []
    for x in lots:
        if x["closed"]:
            cost = x["qty"] * x["price"] + (x["fees"] or 0)
            proceeds = x["qty"] * x["close_price"] - (x["close_fees"] or 0)
            closed.append({**x, "portfolio": pname.get(x["portfolio_id"], "?"),
                           "name": names.get(x["ticker"], (x["ticker"],))[0], "pnl": proceeds - cost,
                           "pnl_pct": (proceeds / cost - 1) * 100 if cost else None})
    closed.sort(key=lambda x: x["closed"], reverse=True)

    # wyniki każdego portfela (zawsze - do zestawienia w widoku "Wszystkie")
    breakdown = []
    for p in pfs:
        pr = [r for r in rows if r["portfolio_id"] == p["id"]]
        breakdown.append({**p, **_totals(pr, [c for c in closed if c["portfolio_id"] == p["id"]])})
    all_value = sum(b["value"] for b in breakdown)
    for b in breakdown:
        b["share"] = b["value"] / all_value * 100 if all_value else None

    if portfolio_id:
        rows = [r for r in rows if r["portfolio_id"] == portfolio_id]
        closed = [c for c in closed if c["portfolio_id"] == portfolio_id]
    scope_value = sum(r["value"] or 0 for r in rows)
    for r in rows:
        r["weight"] = (r["value"] / scope_value * 100) if r["value"] and scope_value else None
    alerts = _alerts(con, rows, prev, today)
    for r in rows:
        r["alerts"] = [a for a in alerts if a["ticker"] == r["ticker"] and a["portfolio_id"] in (None, r["portfolio_id"])]
    rows.sort(key=lambda r: -(r["value"] or 0))
    return {
        "date": day, "as_of": con.execute("SELECT MAX(finished) FROM runs WHERE status='ok'").fetchone()[0],
        "wig_date": wig_asof, "wig_live": use_live, "portfolio_id": portfolio_id, "portfolios": breakdown,
        "totals": _totals(rows, closed), "positions": rows, "alerts": alerts, "closed": closed,
        "dividends": _dividend_calendar(con, rows, today),
        "events": _events(con, rows),
    }


def _events(con, rows):
    """Wydarzenia z kalendarza (30 dni) dla posiadanych spółek: raporty, WZ, wezwania, dywidendy."""
    from . import kalendarz
    held = {r["ticker"] for r in rows}
    return [e for e in kalendarz.events(con, 30)["events"] if e["ticker"] in held]


def _alerts(con, rows, prev, today):
    """Alerty dla posiadanych spółek, od najważniejszych. level: critical / warn / info.
    Alerty z planu dotyczą pozycji w konkretnym portfelu, komunikaty i dywidendy - spółki (portfolio_id=None)."""
    out = []
    qty = {}
    for r in rows:
        qty[r["ticker"]] = qty.get(r["ticker"], 0) + r["qty"]

    def add(t, level, kind, text, ts=None, r=None):
        out.append({"ticker": t, "level": level, "kind": kind, "text": text, "ts": ts,
                    "portfolio_id": r["portfolio_id"] if r else None, "portfolio": r["portfolio"] if r else None})

    for r in rows:
        t, close, p = r["ticker"], r["close"], r["plan"]
        if close is not None and p["stop"]:
            if close <= p["stop"]:
                add(t, "critical", "stop", f"Kurs {close:.2f} zł przebił poziom wyjścia {p['stop']:.2f} zł "
                                           f"({(close / p['stop'] - 1) * 100:+.1f}%)", r=r)
            elif close <= p["stop"] * 1.03:
                add(t, "warn", "stop_near", f"Kurs {close:.2f} zł jest mniej niż 3% nad poziomem wyjścia "
                                            f"{p['stop']:.2f} zł", r=r)
        if close is not None and p["target"] and close >= p["target"]:
            add(t, "info", "target", f"Kurs {close:.2f} zł osiągnął cel {p['target']:.2f} zł - czas sprawdzić plan", r=r)
        if r["exit_days"] and r["exit_days"] > 1:
            add(t, "warn" if r["exit_days"] > 5 else "info", "liquidity",
                f"Pozycja to {r['exit_days']:.1f} dnia sprzedaży przy 20% średniego dziennego obrotu - wyjście może "
                f"potrwać i ruszyć kursem", r=r)
        if p["review"] and p["review"] <= today:
            add(t, "info", "review", f"Minął termin przeglądu planu ({p['review']})", r=r)
    tickers = sorted(qty)
    if not tickers:
        return out
    chg = {r["ticker"]: r["chg"] for r in rows}
    for t in tickers:
        if chg.get(t) is not None and abs(chg[t]) >= 5:
            add(t, "warn", "move", f"Dzisiejsza zmiana kursu {chg[t]:+.2f}%")
    qm = ",".join("?" * len(tickers))
    since1 = f"{prev} 17:00" if prev else today
    since5 = f"{_sessions_back(con, 5) or today} 17:00"
    for e in con.execute(f"SELECT ticker, ts, title, category FROM espi WHERE ticker IN ({qm}) AND ts>? ORDER BY ts DESC",
                         (*tickers, since1)):
        lvl = "warn" if e["category"] in ("wezwanie", "art69", "mar") else "info"
        add(e["ticker"], lvl, "espi", f"Komunikat: {_subject(e['title'])}", e["ts"])
    for h in con.execute(
            f"SELECT c.ticker, c.investor, c.delta, c.value, c.source, e.ts FROM changes c JOIN espi e ON e.id=c.espi_id/10 "
            f"WHERE c.ticker IN ({qm}) AND c.source IN ('mar','art69') AND c.excluded=0 AND e.ts>? ORDER BY e.ts DESC",
            (*tickers, since5)):
        who = "Insider" if h["source"] == "mar" else "Akcjonariusz"
        val = f" (ok. {abs(h['value']) / 1e3:,.0f} tys. zł)".replace(",", " ") if h["value"] else ""
        add(h["ticker"], "warn" if h["delta"] < 0 else "info", "insider",
            f"{who} {h['investor']} {'kupił' if h['delta'] > 0 else 'sprzedał'} {abs(h['delta']):,.0f} akcji{val}"
            .replace(",", " "), h["ts"])
    for d in con.execute(f"SELECT ticker, last_day, dps FROM dividends WHERE ticker IN ({qm}) AND dps>0 AND last_day>=?",
                         (*tickers, prev or today)):
        if d["last_day"] == prev:
            add(d["ticker"], "info", "exdiv", f"Dziś dzień odcięcia dywidendy {d['dps']:.2f} zł - spadek kursu o jej "
                                              f"wartość jest techniczny")
        elif d["last_day"] <= (date.fromisoformat(today) + timedelta(days=14)).isoformat():
            amount = f"{d['dps'] * qty[d['ticker']]:,.0f}".replace(",", " ")
            add(d["ticker"], "info", "dividend", f"Ostatni dzień z prawem do dywidendy {d['dps']:.2f} zł: "
                                                 f"{d['last_day']}, dla Ciebie ok. {amount} zł brutto")
    from . import ostrzezenia as gwarn
    warn = gwarn.compute(con)
    for t in tickers:
        for w in warn.get(t, []):
            add(t, "warn" if w["level"] == "warn" else "info", f"warn_{w['kind']}", "Ostrzeżenie: " + w["text"])
    rank = {"critical": 0, "warn": 1, "info": 2}
    out.sort(key=lambda a: (rank[a["level"]], a["ticker"]))
    return out


def _dividend_calendar(con, rows, today):
    held = {}
    for r in rows:
        h = held.setdefault(r["ticker"], {"name": r["name"], "qty": 0.0, "close": r["close"], "portfolios": set()})
        h["qty"] += r["qty"]
        h["portfolios"].add(r["portfolio"])
    if not held:
        return []
    qm = ",".join("?" * len(held))
    start = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
    out, seen = [], set()
    for d in con.execute(f"SELECT * FROM dividends WHERE ticker IN ({qm}) AND dps>0 AND "
                         f"(last_day>=? OR pay_day>=?) ORDER BY COALESCE(NULLIF(last_day,''), pay_day)",
                         (*held, start, today)):
        k = (d["ticker"], d["last_day"], d["dps"])
        if k in seen:
            continue
        seen.add(k)
        h = held[d["ticker"]]
        out.append({"ticker": d["ticker"], "name": h["name"], "year_for": d["year_for"], "last_day": d["last_day"],
                    "pay_day": d["pay_day"], "dps": d["dps"], "status": d["status"], "qty": h["qty"],
                    "portfolios": sorted(h["portfolios"]), "amount": d["dps"] * h["qty"],
                    "yield": d["dps"] / h["close"] * 100 if h["close"] else None})
    return out
