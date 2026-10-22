"""Wyniki finansowe i jakość biznesu (długi termin) - z kwartalnych sprawozdań Biznesradar (tabela fin_q, tys. zł).

  dynamika      - przychody, EBITDA i zysk netto: ostatni kwartał r/r oraz 4 kwartały (TTM) r/r,
  rentowność    - ROE (TTM, średni kapitał), ROIC (EBIT x 0,81 / kapitał + dług netto), marże EBIT i netto,
                  ROE i marża netto na koniec 5 ostatnich lat - stabilność,
  zadłużenie    - dług netto (kredyty, obligacje, leasing - gotówka i inwestycje krótkoterminowe) / EBITDA TTM;
                  EBITDA = EBIT + amortyzacja (gotowa EBITDA kwartalna w Biznesradar jest płatna),
  gotówka       - wolny przepływ FCF = przepływy operacyjne - CAPEX, TTM i w ilu z 5 lat był dodatni,
  dywidenda     - lata wypłat z rzędu (przepływy z dywidendy), wypłata jako % zysku (powyżej 80% ryzyko cięcia),
  wycena        - C/Z na tle mediany własnych C/Z z 5 lat (20 kwartałów),
  liczba akcji  - zmiana w rok i 3 lata (rozwodnienie albo skup),
  F-Score / Altman - z Biznesradar (strona Rating).
Ocena jakości 0-100 to suma punktów za kryteria, które da się policzyć (szczegóły w JAKOSC_OPIS). Banki i
ubezpieczyciele mają inną strukturę sprawozdań - liczymy dla nich tylko to, co ma sens.
"""
import json
import statistics
import threading

_cache = {"key": None, "data": None}
_lock = threading.Lock()

JAKOSC_OPIS = ("F-Score Piotroskiego (do 25 pkt), ROE co najmniej 10% w każdym z ostatnich lat (20), stabilna marża netto "
               "(10), dług netto / EBITDA poniżej 2 (15), dodatni wolny przepływ gotówki w 4 z 5 lat (15), Altman EM-Score "
               "co najmniej 5,5 - niskie ryzyko upadłości (15). Wynik w % punktów możliwych do policzenia dla spółki.")


def _prev(period, n=4):
    y, q = int(period[:4]), int(period[-1])
    idx = y * 4 + (q - 1) - n
    return f"{idx // 4}/Q{idx % 4 + 1}"


def _pct(a, b):
    return (a / b - 1) * 100 if a is not None and b not in (None, 0) and b > 0 else None


def compute(con):
    key = (con.execute("SELECT MAX(fetched), COUNT(*) FROM fin_meta").fetchone()[:],
           con.execute("SELECT MAX(updated) FROM ratios").fetchone()[0])
    with _lock:
        if _cache["key"] == key:
            return _cache["data"]
    data = _compute(con)
    with _lock:
        _cache.update(key=key, data=data)
    return data


def _compute(con):
    raw = {}
    for r in con.execute("SELECT ticker, period, field, value FROM fin_q"):
        raw.setdefault(r[0], {}).setdefault(r[2], {})[r[1]] = r[3]
    meta = {r["ticker"]: r for r in con.execute("SELECT * FROM fin_meta")}
    cz_now = {r[0]: r[1] for r in con.execute("SELECT ticker, cz FROM ratios")}
    return {t: metrics(f, meta.get(t), cz_now.get(t)) for t, f in raw.items()}


def metrics(f, meta=None, cz_now=None):
    g = lambda field, p: (f.get(field) or {}).get(p)  # noqa: E731
    bank = bool(f.get("IncomeNetIntrestIncome"))
    np_field = "IncomeShareholderNetProfit" if f.get("IncomeShareholderNetProfit") else "IncomeNetProfit"

    def rev(p):
        if bank:
            a, b = g("IncomeNetIntrestIncome", p), g("IncomeNetFeeExpense", p)
            return (a or 0) + (b or 0) if a is not None else None
        return g("IncomeRevenues", p)

    def ttm(fn, p):
        vals = [fn(_prev(p, i)) for i in range(4)]
        return sum(vals) if all(v is not None for v in vals) else None

    fld = lambda name: (lambda p: g(name, p))  # noqa: E731
    # EBITDA i FCF w widoku kwartalnym Biznesradar są płatne - liczymy z darmowych pozycji
    def ebitda(p):
        e, a = g("IncomeEBIT", p), g("CashflowAmortization", p)
        return e + a if e is not None and a is not None and not bank else None

    def fcf(p):
        o, c = g("CashflowOperatingCashflow", p), g("CashflowCapex", p)
        return o - abs(c) if o is not None and c is not None and not bank else None

    def equity(p):
        return g("BalanceCapital", p) if g("BalanceCapital", p) is not None else g("BalanceOwnCapital", p)
    periods = sorted(f.get(np_field, {}))
    if not periods:
        return {"bank": bank}
    p0 = periods[-1]
    py = _prev(p0)
    x = {"period": p0, "bank": bank}
    np_ttm, np_ttm_y = ttm(fld(np_field), p0), ttm(fld(np_field), py)
    rev_ttm, rev_ttm_y = ttm(rev, p0), ttm(rev, py)
    ebitda_ttm, ebitda_ttm_y = ttm(ebitda, p0), ttm(ebitda, py)
    ebit_ttm = ttm(fld("IncomeNetoperatingProfit" if bank else "IncomeEBIT"), p0)
    x.update({
        "rev_q": rev(p0), "rev_yoy": _pct(rev(p0), rev(py)), "rev_ttm": rev_ttm, "rev_ttm_yoy": _pct(rev_ttm, rev_ttm_y),
        "np_q": g(np_field, p0), "np_yoy": _pct(g(np_field, p0), g(np_field, py)), "np_ttm": np_ttm,
        "np_ttm_yoy": _pct(np_ttm, np_ttm_y),
        "np_turnaround": bool(np_ttm is not None and np_ttm_y is not None and np_ttm > 0 >= np_ttm_y),
        "ebitda_ttm": ebitda_ttm, "ebitda_ttm_yoy": None if bank else _pct(ebitda_ttm, ebitda_ttm_y),
    })
    eq0, eq1 = equity(p0), equity(py)
    avg_eq = (eq0 + eq1) / 2 if eq0 and eq1 else eq0
    x["roe"] = np_ttm / avg_eq * 100 if np_ttm is not None and avg_eq and avg_eq > 0 else None
    x["net_margin"] = np_ttm / rev_ttm * 100 if np_ttm is not None and rev_ttm and rev_ttm > 0 else None
    x["ebit_margin"] = ebit_ttm / rev_ttm * 100 if ebit_ttm is not None and rev_ttm and rev_ttm > 0 and not bank else None

    def net_debt(p):
        debt = [g(k, p) for k in ("BalanceNoncurrentBorrowings", "BalanceNoncurrentObligations", "BalanceNoncurrentLeasing",
                                  "BalanceCurrentBorrowings", "BalanceCurrentObligations", "BalanceCurrentLeasing")]
        if all(v is None for v in debt):
            return None
        return sum(v or 0 for v in debt) - (g("BalanceCash", p) or 0) - (g("BalanceCurrentInvestments", p) or 0)
    nd = None if bank else net_debt(p0)
    x["net_debt"] = nd
    x["nd_ebitda"] = (nd / ebitda_ttm) if nd is not None and ebitda_ttm and ebitda_ttm > 0 else None
    x["net_cash"] = bool(nd is not None and nd < 0)
    cap = (eq0 or 0) + (nd or 0)
    x["roic"] = ebit_ttm * 0.81 / cap * 100 if ebit_ttm is not None and cap > 0 and not bank and eq0 else None

    # historia na koniec lat (Q4): ROE, marża netto, FCF, dywidendy
    y0 = int(p0[:4])
    years = [y for y in range(y0 - 5, y0 + 1)]
    roe_h, margin_h, fcf_h = {}, {}, {}
    for y in years:
        p = f"{y}/Q4"
        npy, ry, e = ttm(fld(np_field), p), ttm(rev, p), equity(p)
        if npy is not None and e and e > 0:
            roe_h[y] = npy / e * 100
        if npy is not None and ry and ry > 0:
            margin_h[y] = npy / ry * 100
        fy = ttm(fcf, p)
        if fy is not None:
            fcf_h[y] = fy
    last5 = [y for y in years if y < y0 or p0.endswith("Q4")][-5:]
    x["roe_hist"] = {y: roe_h[y] for y in last5 if y in roe_h}
    x["margin_hist"] = {y: margin_h[y] for y in last5 if y in margin_h}
    x["roe_min5"] = min(x["roe_hist"].values()) if len(x["roe_hist"]) >= 3 else None
    x["margin_std5"] = statistics.pstdev(x["margin_hist"].values()) if len(x["margin_hist"]) >= 3 else None
    x["fcf_ttm"] = ttm(fcf, p0)
    fh = [fcf_h[y] for y in last5 if y in fcf_h]
    x["fcf_pos_years"], x["fcf_years"] = sum(v > 0 for v in fh), len(fh)

    div_year = {}
    for p, v in (f.get("CashflowDividend") or {}).items():
        div_year[int(p[:4])] = div_year.get(int(p[:4]), 0) + abs(v or 0)
    streak, y = 0, y0 if div_year.get(y0, 0) > 0 else y0 - 1
    while div_year.get(y, 0) > 0:
        streak += 1
        y -= 1
    x["div_streak"] = streak
    div_ttm = ttm(lambda p: abs(g("CashflowDividend", p) or 0) if g("CashflowDividend", p) is not None else None, p0)
    x["payout"] = div_ttm / np_ttm * 100 if div_ttm and np_ttm and np_ttm > 0 else None

    czs = [v for p, v in sorted((f.get("CZ") or {}).items())[-20:] if v and v > 0]
    x["cz_med5"] = statistics.median(czs) if len(czs) >= 8 else None
    x["cz_vs_med"] = (cz_now / x["cz_med5"] - 1) * 100 if cz_now and cz_now > 0 and x["cz_med5"] else None
    sa = f.get("ShareAmount") or {}
    sa_p = sorted(sa)
    sa0 = sa[sa_p[-1]] if sa_p else None
    x["shares_1y"] = _pct(sa0, sa.get(_prev(sa_p[-1], 4))) if sa_p else None
    x["shares_3y"] = _pct(sa0, sa.get(_prev(sa_p[-1], 12))) if sa_p else None

    if meta:
        x["fscore"], x["altman"], x["altman_rating"] = meta["fscore"], meta["altman"], meta["altman_rating"]
        x["fscore_items"] = json.loads(meta["fscore_items"] or "[]")
    x.update(_score(x))
    return x


def _score(x):
    pts, avail, parts = 0.0, 0.0, []

    def add(name, got, of, ok_txt):
        nonlocal pts, avail
        pts += got
        avail += of
        parts.append({"name": name, "points": round(got, 1), "of": of, "text": ok_txt})

    if x.get("fscore") is not None:
        add("F-Score", x["fscore"] / 9 * 25, 25, f"{x['fscore']}/9")
    if x.get("roe_min5") is not None:
        add("ROE stabilnie", 20 if x["roe_min5"] >= 10 else 10 if x["roe_min5"] >= 5 else 0, 20,
            f"najniższe w {len(x['roe_hist'])} latach: {x['roe_min5']:.1f}%")
    if x.get("margin_std5") is not None:
        add("Stabilna marża", 10 if x["margin_std5"] <= 5 else 5 if x["margin_std5"] <= 10 else 0, 10,
            f"odchylenie marży netto {x['margin_std5']:.1f} pp")
    if not x.get("bank") and (x.get("nd_ebitda") is not None or x.get("net_cash")):
        nde = x.get("nd_ebitda")
        add("Zadłużenie", 15 if x.get("net_cash") or nde < 2 else 7 if nde < 3 else 0, 15,
            "gotówka netto" if x.get("net_cash") else f"dług netto / EBITDA {nde:.1f}")
    if x.get("fcf_years", 0) >= 3:
        add("Wolna gotówka", 15 if x["fcf_pos_years"] >= x["fcf_years"] - 1 and x["fcf_pos_years"] >= 3 else
            7 if x["fcf_pos_years"] >= x["fcf_years"] / 2 else 0, 15, f"FCF dodatni w {x['fcf_pos_years']} z {x['fcf_years']} lat")
    if x.get("altman") is not None:
        add("Altman", 15 if x["altman"] >= 5.5 else 7 if x["altman"] >= 4.5 else 0, 15,
            f"EM-Score {x['altman']:.1f} ({x.get('altman_rating') or '–'})")
    enough = avail >= 50 or (x.get("bank") and avail >= 30)  # bank: ROE i marża (bez długu, FCF, Altmana)
    return {"quality": round(pts / avail * 100) if enough else None, "quality_parts": parts, "quality_avail": avail}


def quarters(con, ticker, n=8):
    """Ostatnie kwartały: przychody, EBITDA (EBIT + amortyzacja), zysk netto i ich zmiana r/r (tys. zł)."""
    f = {}
    for r in con.execute("SELECT period, field, value FROM fin_q WHERE ticker=?", (ticker,)):
        f.setdefault(r[1], {})[r[0]] = r[2]
    bank = bool(f.get("IncomeNetIntrestIncome"))
    g = lambda k, p: (f.get(k) or {}).get(p)  # noqa: E731
    npf = "IncomeShareholderNetProfit" if f.get("IncomeShareholderNetProfit") else "IncomeNetProfit"

    def vals(p):
        rev = ((g("IncomeNetIntrestIncome", p) or 0) + (g("IncomeNetFeeExpense", p) or 0)) if bank else g("IncomeRevenues", p)
        e, a = g("IncomeEBIT", p), g("CashflowAmortization", p)
        return {"rev": rev, "ebitda": e + a if e is not None and a is not None and not bank else None, "np": g(npf, p)}
    out = []
    for p in sorted(f.get(npf, {}))[-n:]:
        v, y = vals(p), vals(_prev(p))
        out.append({"period": p, **v, **{f"{k}_yoy": _pct(v[k], y[k]) for k in ("rev", "ebitda", "np")}})
    return {"bank": bank, "rows": out[::-1]}
