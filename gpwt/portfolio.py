"""Moje spółki: portfel (zakupy w partiach), plan dla każdej spółki i alerty tylko dla posiadanych papierów.

  positions - partie zakupu: ticker, data, liczba akcji, cena, prowizja; sprzedaż zamyka partie od najstarszej
              (FIFO), a częściowa sprzedaż dzieli partię na sprzedaną i pozostałą,
  plans     - plan na spółkę: dlaczego kupiłem, poziom wyjścia na stracie, cel, horyzont, termin przeglądu.

Wynik liczony od kursu z ostatniego pobrania (w trakcie sesji - bieżącego), porównanie z WIG od dnia zakupu
(zamknięcie indeksu z archiwum gpw.pl). Alerty to podpowiedzi, co sprawdzić, a nie rekomendacje.
"""
from datetime import date, datetime, timedelta

from .pressure import index_close
from .session import _avg_turnover, _subject

PLAN_FIELDS = ("thesis", "stop", "target", "horizon", "review", "notes")
EXIT_SHARE = 0.2  # przy wyjściu realnie da się sprzedać ok. 20% dziennego obrotu bez mocnego ruchu kursu


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def save_plan(con, ticker, d):
    cur = con.execute("SELECT * FROM plans WHERE ticker=?", (ticker,)).fetchone()
    row = {k: (cur[k] if cur else None) for k in PLAN_FIELDS}
    for k in PLAN_FIELDS:
        if k in d:
            row[k] = _f(d[k]) if k in ("stop", "target") else ((d[k] or "").strip() or None)
    con.execute("INSERT OR REPLACE INTO plans VALUES(?,?,?,?,?,?,?,?)",
                (ticker, *[row[k] for k in PLAN_FIELDS], datetime.now().isoformat(timespec="seconds")))


def add_lot(con, d):
    t = (d.get("ticker") or "").strip().upper()
    qty, price = _f(d.get("qty")), _f(d.get("price"))
    if not t or not qty or qty <= 0 or price is None or price < 0:
        raise ValueError("Podaj ticker, liczbę akcji i cenę zakupu")
    if not con.execute("SELECT 1 FROM companies WHERE ticker=?", (t,)).fetchone():
        raise ValueError(f"Nie znam spółki {t}")
    opened = d.get("opened") or date.today().isoformat()
    cur = con.execute("INSERT INTO positions(ticker, opened, qty, price, fees, created) VALUES(?,?,?,?,?,?)",
                      (t, opened, qty, price, _f(d.get("fees")) or 0, datetime.now().isoformat(timespec="seconds")))
    plan = {k: d[k] for k in PLAN_FIELDS if k in d and d[k] not in (None, "")}
    if plan or not con.execute("SELECT 1 FROM plans WHERE ticker=?", (t,)).fetchone():
        save_plan(con, t, plan)
    return cur.lastrowid


def sell(con, ticker, qty, price, day=None, fees=0):
    """Sprzedaż qty akcji: zamyka partie od najstarszej, ostatnią dzieli. Prowizja rozkładana proporcjonalnie."""
    qty, price, fees = _f(qty), _f(price), _f(fees) or 0
    lots = con.execute("SELECT * FROM positions WHERE ticker=? AND closed IS NULL ORDER BY opened, id", (ticker,)).fetchall()
    held = sum(r["qty"] for r in lots)
    if not qty or qty <= 0 or price is None or qty > held + 1e-9:
        raise ValueError(f"Masz {held:g} akcji {ticker} - podaj liczbę akcji do sprzedaży i cenę")
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
            con.execute("INSERT INTO positions(ticker, opened, qty, price, fees, closed, close_price, close_fees, created) "
                        "VALUES(?,?,?,?,?,?,?,?,?)", (ticker, r["opened"], take, r["price"], part_fee, day, price, fee,
                                                      datetime.now().isoformat(timespec="seconds")))
        else:
            con.execute("UPDATE positions SET closed=?, close_price=?, close_fees=? WHERE id=?", (day, price, fee, r["id"]))
        left -= take


def _sessions_back(con, n):
    ds = [r[0] for r in con.execute("SELECT DISTINCT date FROM quotes ORDER BY date DESC LIMIT ?", (n + 1,))]
    return ds[-1] if ds else None


def summary(con):
    today = date.today().isoformat()
    lots = [dict(r) for r in con.execute("SELECT * FROM positions ORDER BY opened, id")]
    open_lots = [x for x in lots if not x["closed"]]
    tickers = sorted({x["ticker"] for x in open_lots})
    day = (con.execute("SELECT MAX(date) FROM quotes").fetchone() or [None])[0]
    q = {r["ticker"]: r for r in con.execute(
        "SELECT q.*, c.full_name, c.short_name, c.market FROM quotes q JOIN companies c ON c.ticker=q.ticker "
        "WHERE q.date=?", (day,))} if day else {}
    names = {r["ticker"]: (r["full_name"] or r["short_name"], r["market"]) for r in con.execute(
        "SELECT ticker, full_name, short_name, market FROM companies")}
    plans = {r["ticker"]: dict(r) for r in con.execute("SELECT * FROM plans")}
    avg = _avg_turnover(con, day) if day else {}
    wig_last = (con.execute("SELECT MAX(date) FROM index_ohlc WHERE name='WIG'").fetchone() or [None])[0]
    # WIG z archiwum gpw.pl jest dostępny po sesji; starszy niż tydzień = brak danych (nie porównujemy z zerem)
    fresh = wig_last and day and (date.fromisoformat(day) - date.fromisoformat(wig_last)).days <= 7
    wig_now = index_close(con, "WIG", today) if fresh else None
    prev = _sessions_back(con, 1)
    since1 = f"{prev} 17:00" if prev else today
    since5 = f"{_sessions_back(con, 5) or today} 17:00"

    hold = {}
    for x in open_lots:
        h = hold.setdefault(x["ticker"], {"ticker": x["ticker"], "qty": 0.0, "cost": 0.0, "lots": [], "wig_w": 0.0})
        h["qty"] += x["qty"]
        h["cost"] += x["qty"] * x["price"] + (x["fees"] or 0)
        h["lots"].append({k: x[k] for k in ("id", "opened", "qty", "price", "fees")})
        w0 = index_close(con, "WIG", x["opened"])
        if w0 and wig_now:  # WIG od daty zakupu, ważony kosztem partii
            h["wig_w"] += (wig_now / w0 - 1) * (x["qty"] * x["price"])
    rows, total_value, total_cost, total_today = [], 0.0, 0.0, 0.0
    for t, h in hold.items():
        qq = q.get(t)
        close = qq["close"] if qq else None
        chg = qq["change_pct"] if qq else None
        value = close * h["qty"] if close is not None else None
        base = sum(lt["qty"] * lt["price"] for lt in h["lots"]) or 1
        r = {"ticker": t, "name": names.get(t, (t, None))[0], "market": names.get(t, (None, None))[1],
             "qty": h["qty"], "avg_price": h["cost"] / h["qty"], "cost": h["cost"], "close": close, "chg": chg,
             "value": value, "pnl": (value - h["cost"]) if value is not None else None,
             "pnl_pct": ((value / h["cost"] - 1) * 100) if value is not None and h["cost"] else None,
             "wig_pct": h["wig_w"] / base * 100 if wig_now else None,
             "today_pnl": (value - value / (1 + chg / 100)) if value is not None and chg is not None else None,
             "first_opened": min(lt["opened"] for lt in h["lots"]), "lots": h["lots"],
             "plan": {k: (plans.get(t) or {}).get(k) for k in PLAN_FIELDS},
             "avg20": avg.get(t)}
        r["vs_wig"] = (r["pnl_pct"] - r["wig_pct"]) if r["pnl_pct"] is not None and r["wig_pct"] is not None else None
        r["exit_days"] = (value / (avg[t] * EXIT_SHARE)) if value and avg.get(t) else None
        rows.append(r)
        total_value += value or 0
        total_cost += h["cost"]
        total_today += r["today_pnl"] or 0
    for r in rows:
        r["weight"] = (r["value"] / total_value * 100) if r["value"] and total_value else None

    alerts = _alerts(con, rows, tickers, since1, since5, prev, today)
    for r in rows:
        r["alerts"] = [a for a in alerts if a["ticker"] == r["ticker"]]
    rows.sort(key=lambda r: -(r["value"] or 0))

    closed = []
    for x in lots:
        if x["closed"]:
            cost = x["qty"] * x["price"] + (x["fees"] or 0)
            proceeds = x["qty"] * x["close_price"] - (x["close_fees"] or 0)
            closed.append({**x, "name": names.get(x["ticker"], (x["ticker"],))[0], "pnl": proceeds - cost,
                           "pnl_pct": (proceeds / cost - 1) * 100 if cost else None})
    closed.sort(key=lambda x: x["closed"], reverse=True)

    wig_total = sum((r["wig_pct"] or 0) * r["cost"] for r in rows) / total_cost if total_cost else None
    pnl_pct = (total_value / total_cost - 1) * 100 if total_cost else None
    return {
        "date": day, "as_of": con.execute("SELECT MAX(finished) FROM runs WHERE status='ok'").fetchone()[0],
        "wig_date": (con.execute("SELECT MAX(date) FROM index_ohlc WHERE name='WIG'").fetchone() or [None])[0],
        "totals": {"value": total_value, "cost": total_cost, "pnl": total_value - total_cost, "pnl_pct": pnl_pct,
                   "today_pnl": total_today,
                   "today_pct": total_today / (total_value - total_today) * 100 if total_value - total_today else None,
                   "wig_pct": wig_total, "vs_wig": (pnl_pct - wig_total) if pnl_pct is not None and wig_total is not None
                   else None, "realized": sum(c["pnl"] for c in closed), "n": len(rows)},
        "positions": rows, "alerts": alerts, "closed": closed,
        "dividends": _dividend_calendar(con, rows, today),
        "plans_only": [dict(p) for t, p in plans.items() if t not in hold],
    }


def _alerts(con, rows, tickers, since1, since5, prev, today):
    """Lista alertów dla posiadanych spółek, od najważniejszych. level: critical / warn / info."""
    out = []
    by = {r["ticker"]: r for r in rows}

    def add(t, level, kind, text, ts=None):
        out.append({"ticker": t, "level": level, "kind": kind, "text": text, "ts": ts})

    for r in rows:
        t, close, p = r["ticker"], r["close"], r["plan"]
        if close is not None and p["stop"]:
            if close <= p["stop"]:
                add(t, "critical", "stop", f"Kurs {close:.2f} zł przebił poziom wyjścia {p['stop']:.2f} zł "
                                           f"({(close / p['stop'] - 1) * 100:+.1f}%)")
            elif close <= p["stop"] * 1.03:
                add(t, "warn", "stop_near", f"Kurs {close:.2f} zł jest mniej niż 3% nad poziomem wyjścia {p['stop']:.2f} zł")
        if close is not None and p["target"] and close >= p["target"]:
            add(t, "info", "target", f"Kurs {close:.2f} zł osiągnął cel {p['target']:.2f} zł - czas sprawdzić plan")
        if r["chg"] is not None and abs(r["chg"]) >= 5:
            add(t, "warn", "move", f"Dzisiejsza zmiana kursu {r['chg']:+.2f}%")
        if r["exit_days"] and r["exit_days"] > 1:
            add(t, "warn" if r["exit_days"] > 5 else "info", "liquidity",
                f"Pozycja to {r['exit_days']:.1f} dnia sprzedaży przy 20% średniego dziennego obrotu - wyjście może "
                f"potrwać i ruszyć kursem")
        if p["review"] and p["review"] <= today:
            add(t, "info", "review", f"Minął termin przeglądu planu ({p['review']})")
    if not tickers:
        return out
    qm = ",".join("?" * len(tickers))
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
        r = by.get(d["ticker"])
        amount = f", dla Ciebie ok. {d['dps'] * r['qty']:,.0f} zł brutto".replace(",", " ") if r else ""
        if d["last_day"] == prev:
            add(d["ticker"], "info", "exdiv", f"Dziś dzień odcięcia dywidendy {d['dps']:.2f} zł - spadek kursu o jej "
                                              f"wartość jest techniczny")
        elif d["last_day"] <= (date.fromisoformat(today) + timedelta(days=14)).isoformat():
            add(d["ticker"], "info", "dividend", f"Ostatni dzień z prawem do dywidendy {d['dps']:.2f} zł: "
                                                 f"{d['last_day']}{amount}")
    rank = {"critical": 0, "warn": 1, "info": 2}
    out.sort(key=lambda a: (rank[a["level"]], a["ticker"]))
    return out


def _dividend_calendar(con, rows, today):
    held = {r["ticker"]: r for r in rows}
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
        r = held[d["ticker"]]
        out.append({"ticker": d["ticker"], "name": r["name"], "year_for": d["year_for"], "last_day": d["last_day"],
                    "pay_day": d["pay_day"], "dps": d["dps"], "status": d["status"], "qty": r["qty"],
                    "amount": d["dps"] * r["qty"], "yield": d["dps"] / r["close"] * 100 if r["close"] else None})
    return out
