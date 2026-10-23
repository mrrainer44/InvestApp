"""Flagi spółek: green flag / neutral / red flag - sito, które spółki w ogóle brać do dalszej analizy.

Dwie warstwy:
  knock-outy  - jeden wystarczy na red flag: spółka w upadłości, restrukturyzacji lub likwidacji, brak raportu
                okresowego po ustawowym terminie, ujemne przepływy operacyjne przez 3 lata przy wykazywanym zysku,
  punktacja   - każde kryterium: zielone +1, neutralne 0, czerwone -1; kryteria oznaczone gwiazdką liczą się podwójnie.
Wynik: co najmniej +6 bez knock-outów -> green flag; od 0 do +5 -> neutral; poniżej 0, knock-out albo 3 czerwone
kryteria w jednej kategorii -> red flag. Flaga ustawiona ręcznie ma pierwszeństwo przed automatyczną.

Pojedynczy słaby kwartał to szum: kryteria patrzą na lata (4 kwartały na koniec roku) albo ostatnie 12 miesięcy.
Kryterium bez danych liczy się jako 0. Gdy da się policzyć mniej niż 4 kryteria, spółka nie dostaje oceny automatycznej.
Nie liczymy (brak danych w darmowych sprawozdaniach): należności, zapasów, pokrycia odsetek, zapadalności długu,
opinii biegłego, zmian audytora, transakcji z podmiotami powiązanymi i realizacji prognoz - to zostaje do oceny ręcznej.
"""
import re
import statistics
import threading
from datetime import date, datetime, timedelta

_cache = {"key": None, "data": None}
_lock = threading.Lock()

FLAGS = {"green": "Green flag", "neutral": "Neutral", "red": "Red flag"}
CATS = {"wyniki": "Jakość wyników", "bilans": "Bilans i ryzyko finansowe", "akcjonariat": "Akcjonariusze i zarząd",
        "wycena": "Wycena"}
GREEN_MIN, MIN_CRITERIA, RED_IN_CAT = 6, 4, 3
_KO_NAME = re.compile(r"\bw (upad[lł]o[sś]ci|restrukturyzacji|likwidacji)\b", re.I)


def _prev(period, n=4):
    y, q = int(period[:4]), int(period[-1])
    idx = y * 4 + (q - 1) - n
    return f"{idx // 4}/Q{idx % 4 + 1}"


def compute(con):
    """Ocena automatyczna wszystkich spółek {ticker: {...}}; zapamiętana do następnego pobrania."""
    key = (con.execute("SELECT MAX(fetched), COUNT(*) FROM fin_meta").fetchone()[:],
           con.execute("SELECT MAX(updated) FROM ratios").fetchone()[0],
           con.execute("SELECT MAX(id) FROM espi").fetchone()[0],
           con.execute("SELECT MAX(id) FROM changes").fetchone()[0],
           con.execute("SELECT MAX(date) FROM quotes").fetchone()[0], date.today().isoformat())
    with _lock:
        if _cache["key"] == key:
            return _cache["data"]
    data = _compute(con)
    with _lock:
        _cache.update(key=key, data=data)
    return data


def _yearly(f, bank):
    """Wartości roczne (suma 4 kwartałów do Q4) i stan na koniec roku."""
    g = lambda field, p: (f.get(field) or {}).get(p)  # noqa: E731

    def ttm(field, p):
        v = [g(field, _prev(p, i)) for i in range(4)]
        return sum(v) if all(x is not None for x in v) else None

    def rev(p):
        if bank:
            a = [ttm("IncomeNetIntrestIncome", p), ttm("IncomeNetFeeExpense", p)]
            return (a[0] or 0) + (a[1] or 0) if a[0] is not None else None
        return ttm("IncomeRevenues", p)
    npf = "IncomeShareholderNetProfit" if f.get("IncomeShareholderNetProfit") else "IncomeNetProfit"
    q4 = sorted(int(p[:4]) for p in (f.get(npf) or {}) if p.endswith("Q4"))
    out = {}
    for y in q4[-6:]:
        p = f"{y}/Q4"
        eq = g("BalanceCapital", p) if g("BalanceCapital", p) is not None else g("BalanceOwnCapital", p)
        out[y] = {"rev": rev(p), "np": ttm(npf, p), "ebit": None if bank else ttm("IncomeEBIT", p),
                  "cfo": None if bank else ttm("CashflowOperatingCashflow", p), "eq": eq}
    return out


def _compute(con, today=None):
    from . import ostrzezenia, quality
    today = today or date.today()
    raw = {}
    for r in con.execute("SELECT ticker, period, field, value FROM fin_q"):
        raw.setdefault(r[0], {}).setdefault(r[2], {})[r[1]] = r[3]
    q = quality.compute(con)
    warn = ostrzezenia.compute(con)
    co = {r["ticker"]: dict(r) for r in con.execute(
        "SELECT c.ticker, c.full_name, c.short_name, c.sector, c.shares, r.evebitda FROM companies c "
        "LEFT JOIN ratios r ON r.ticker=c.ticker")}
    close = {r[0]: r[1] for r in con.execute(
        "SELECT ticker, close FROM quotes WHERE date=(SELECT MAX(date) FROM quotes)")}
    # nazwa z ostatniego komunikatu - "... S.A. w restrukturyzacji" pojawia się tam szybciej niż w bazie spółek
    espi_name = {r[0]: r[1] for r in con.execute(
        "SELECT ticker, company FROM espi WHERE ticker IS NOT NULL AND ts>=? ORDER BY ts",
        ((today - timedelta(days=120)).isoformat(),))}
    sec_ev = {}
    for x in co.values():
        if x["sector"] and x["evebitda"] and x["evebitda"] > 0:
            sec_ev.setdefault(x["sector"], []).append(x["evebitda"])
    sec_med = {s: statistics.median(v) for s, v in sec_ev.items() if len(v) >= 5}
    ins = {}
    for r in con.execute("SELECT ticker, investor_norm, delta, date FROM changes WHERE source='mar' AND excluded=0 "
                         "AND date>=?", ((today - timedelta(days=180)).isoformat(),)):
        g = ins.setdefault(r["ticker"], {"buy": 0, "sell": 0, "sellers90": set()})
        g["buy" if r["delta"] > 0 else "sell"] += 1
        if r["delta"] < 0 and r["date"] >= (today - timedelta(days=90)).isoformat():
            g["sellers90"].add(r["investor_norm"])

    out = {}
    for t, c in co.items():
        f, qx = raw.get(t), q.get(t) or {}
        bank = bool(qx.get("bank"))
        ko, crit = [], []

        def add(key, cat, name, state, text, weight=1):
            crit.append({"key": key, "cat": cat, "name": name, "weight": weight, "state": state, "text": text})

        name = espi_name.get(t) or c["full_name"] or ""
        if _KO_NAME.search(name) or _KO_NAME.search(c["full_name"] or ""):
            ko.append(f"Spółka {_KO_NAME.search(name) and _KO_NAME.search(name).group(0) or 'w postępowaniu'} "
                      f"(nazwa w komunikatach: {name})")
        for w in warn.get(t, []):
            if w["kind"] == "raport":
                ko.append(w["text"])
        if f:
            ys = _yearly(f, bank)
            yl = sorted(ys)[-3:]
            last3 = [ys[y] for y in yl]
            if len(last3) == 3 and not bank and all(v["cfo"] is not None and v["np"] is not None for v in last3) \
                    and all(v["cfo"] < 0 < v["np"] for v in last3):
                ko.append(f"Ujemne przepływy operacyjne przez 3 lata ({yl[0]}-{yl[-1]}) przy wykazywanym zysku netto")
            _criteria(add, ys, qx, bank, c, close.get(t), sec_med, ins.get(t))
        n = sum(1 for x in crit if x["state"] is not None)
        score = sum((x["state"] or 0) * x["weight"] for x in crit)
        red_cats = [k for k in CATS if sum(1 for x in crit if x["cat"] == k and x["state"] == -1) >= RED_IN_CAT]
        if ko or red_cats or (n >= MIN_CRITERIA and score < 0):
            auto = "red"
        elif n < MIN_CRITERIA:
            auto = None
        else:
            auto = "green" if score >= GREEN_MIN else "neutral"
        out[t] = {"auto": auto, "score": score if n else None, "n": n, "ko": ko, "red_cats": red_cats, "criteria": crit}
    return out


def _pp(v):
    return f"{v:.1f}".replace(".", ",")


def _criteria(add, ys, qx, bank, c, close, sec_med, ins):
    yl = sorted(ys)
    v = lambda y, k: (ys.get(y) or {}).get(k)  # noqa: E731
    # --- jakość wyników
    revs = [(y, v(y, "rev")) for y in yl if v(y, "rev") is not None and v(y, "rev") > 0]
    if len(revs) >= 4:
        (y0, r0), (y1, r1), (y2, r2), (y3, r3) = revs[-4:]
        cagr = ((r3 / r0) ** (1 / 3) - 1) * 100
        state = -1 if r3 < r2 < r1 else 1 if cagr > 5 and r3 >= r2 and r2 >= r1 * 0.97 else 0
        add("rev", "wyniki", "Wzrost przychodów (3 lata)", state, f"średnio {_pp(cagr)}% rocznie {y0}-{y3}"
            + (", spadek 2 lata z rzędu" if state == -1 else ""))
    if not bank:
        pairs = [(y, v(y, "cfo"), v(y, "np")) for y in yl[-3:] if v(y, "cfo") is not None and v(y, "np") is not None]
        if len(pairs) >= 2:
            ratios = [(y, cf / np_) for y, cf, np_ in pairs if np_ > 0]
            last2 = pairs[-2:]
            if len(ratios) == len(pairs) == 3 and all(r >= 0.9 for _, r in ratios):
                state = 1
            elif all(np_ > 0 and cf / np_ < 0.7 for _, cf, np_ in last2):
                state = -1
            else:
                state = 0
            txt = ", ".join(f"{y}: {_pp(cf / np_)}" if np_ > 0 else f"{y}: strata" for y, cf, np_ in pairs)
            add("cfo", "wyniki", "Przepływy operacyjne / zysk netto", state, txt, 2)
        m = [(y, v(y, "ebit") / v(y, "rev") * 100) for y in yl[-3:]
             if v(y, "ebit") is not None and v(y, "rev") and v(y, "rev") > 0]
        if len(m) == 3:
            d1, d2 = m[1][1] - m[0][1], m[2][1] - m[1][1]
            state = -1 if d1 < -3 and d2 < -3 else 1 if m[2][1] > 0 and m[2][1] >= m[0][1] - 1 else 0
            add("margin", "wyniki", "Marża operacyjna", state, " → ".join(f"{_pp(x)}%" for _, x in m) + f" ({m[0][0]}-{m[2][0]})")
    roe = [(y, v(y, "np") / v(y, "eq") * 100) for y in yl[-3:]
           if v(y, "np") is not None and v(y, "eq") and v(y, "eq") > 0]
    if len(roe) == 3:
        lo = min(x for _, x in roe)
        state = 1 if lo >= 12 else -1 if all(x < 8 for _, x in roe) else 0
        add("roe", "wyniki", "ROE (3 lata)", state, ", ".join(f"{y}: {_pp(x)}%" for y, x in roe))
    if not bank and qx.get("np_ttm") is not None and qx.get("ebitda_ttm") is not None:
        y_last = yl[-1] if yl else None
        np_, ebit = qx["np_ttm"], None
        # EBIT za 12 miesięcy: EBITDA - amortyzacja nie jest dostępna wprost, więc bierzemy marżę EBIT z quality
        if qx.get("ebit_margin") is not None and qx.get("rev_ttm"):
            ebit = qx["ebit_margin"] / 100 * qx["rev_ttm"]
        elif y_last and v(y_last, "ebit") is not None:
            ebit = v(y_last, "ebit")
        if ebit is not None and np_ > 0:
            state = -1 if ebit <= 0 or np_ > 1.5 * ebit else 1 if np_ <= 1.1 * ebit else 0
            add("core", "wyniki", "Zysk z działalności podstawowej", state,
                "zysk netto mimo straty operacyjnej" if ebit <= 0 else f"zysk netto = {_pp(np_ / ebit)}× zysku operacyjnego (12 mies.)")
        elif ebit is not None:
            add("core", "wyniki", "Zysk z działalności podstawowej", 0, "strata netto w ostatnich 12 miesiącach")
    # --- bilans
    if not bank:
        nde, cash = qx.get("nd_ebitda"), qx.get("net_cash")
        if cash:
            add("debt", "bilans", "Dług netto / EBITDA", 1, "gotówka netto", 2)
        elif nde is not None:
            add("debt", "bilans", "Dług netto / EBITDA", 1 if nde < 1.5 else -1 if nde > 3 else 0, f"{_pp(nde)}×", 2)
        elif qx.get("net_debt") is not None and qx["net_debt"] > 0 and (qx.get("ebitda_ttm") or 0) <= 0:
            add("debt", "bilans", "Dług netto / EBITDA", -1, "dług netto przy ujemnej EBITDA", 2)
        if qx.get("current_ratio") is not None:
            cr = qx["current_ratio"]
            add("liq", "bilans", "Płynność bieżąca", 1 if cr > 1.2 else -1 if cr < 1 else 0, f"{_pp(cr)}")
    # --- akcjonariusze i zarząd
    s3 = qx.get("shares_3y")
    if s3 is not None:
        rev_g = (revs[-1][1] / revs[-4][1] - 1) * 100 if len(revs) >= 4 else None
        state = 1 if s3 <= 2 else -1 if s3 > 10 and (rev_g is None or rev_g < s3) else 0
        add("issue", "akcjonariat", "Emisje akcji (3 lata)", state, f"liczba akcji {'+' if s3 >= 0 else ''}{_pp(s3)}%"
            + (f", przychody {'+' if rev_g >= 0 else ''}{_pp(rev_g)}%" if rev_g is not None else ""), 2)
    if ins:
        if len(ins["sellers90"]) >= 2:
            add("insider", "akcjonariat", "Transakcje insiderów", -1, f"sprzedaż przez {len(ins['sellers90'])} osoby w 90 dni")
        elif ins["buy"] and not ins["sell"]:
            add("insider", "akcjonariat", "Transakcje insiderów", 1, f"zarząd kupuje ({ins['buy']} transakcji w 6 mies.)")
        else:
            add("insider", "akcjonariat", "Transakcje insiderów", 0, f"kupno {ins['buy']}, sprzedaż {ins['sell']} w 6 mies.")
    if not bank and qx.get("payout") is not None and qx.get("fcf_ttm") is not None and qx.get("np_ttm"):
        div = qx["payout"] / 100 * qx["np_ttm"]
        fcf = qx["fcf_ttm"]
        state = -1 if div > max(fcf, 0) * 1.1 else 1 if qx.get("div_streak", 0) >= 3 else 0
        add("div", "akcjonariat", "Dywidenda a wolna gotówka", state,
            f"dywidenda {'większa' if div > fcf else 'mniejsza'} niż FCF"
            + (f", wypłaty {qx['div_streak']} lata z rzędu" if qx.get("div_streak") else ""))
    # --- wycena
    if qx.get("cz_vs_med") is not None:
        d = qx["cz_vs_med"]
        add("cz", "wycena", "C/Z na tle własnej średniej 5 lat", 1 if d <= 10 else -1 if d > 50 else 0,
            f"{'+' if d >= 0 else ''}{_pp(d)}% od mediany")
    ev, med = c.get("evebitda"), sec_med.get(c.get("sector"))
    if ev and ev > 0 and med and not bank:
        add("ev", "wycena", "EV/EBITDA na tle sektora", 1 if ev <= med * 1.1 else -1 if ev > med * 1.5 else 0,
            f"{_pp(ev)} przy medianie sektora {_pp(med)}")
    if not bank and qx.get("fcf_ttm") is not None and close and c.get("shares"):
        y = qx["fcf_ttm"] * 1000 / (close * c["shares"]) * 100
        add("fcfy", "wycena", "Stopa wolnych przepływów (FCF yield)", 1 if y > 5 else -1 if y < 0 else 0, f"{_pp(y)}%")


def manual(con):
    return {r["ticker"]: dict(r) for r in con.execute("SELECT * FROM company_flags")}


def effective(con):
    """Flaga każdej spółki: ręczna, a bez niej automatyczna (bez oceny = neutral)."""
    auto, man = compute(con), manual(con)
    tick = set(auto) | set(man)
    return {t: (man.get(t) or {}).get("flag") or (auto.get(t) or {}).get("auto") or "neutral" for t in tick}


def hidden(con):
    """Spółki z red flag, które pomijamy w Sesji i Trendach - poza tymi, które masz w portfelu."""
    held = {r[0] for r in con.execute("SELECT DISTINCT ticker FROM positions WHERE closed IS NULL")}
    return {t for t, f in effective(con).items() if f == "red"} - held


def detail(con, ticker):
    a = compute(con).get(ticker) or {"auto": None, "score": None, "n": 0, "ko": [], "red_cats": [], "criteria": []}
    m = manual(con).get(ticker) or {}
    return {**a, "manual": m.get("flag"), "note": m.get("note"), "updated": m.get("updated"),
            "flag": m.get("flag") or a["auto"] or "neutral", "cats": CATS, "green_min": GREEN_MIN}


def set_flag(con, ticker, flag, note=None):
    t = (ticker or "").strip().upper()
    if not con.execute("SELECT 1 FROM companies WHERE ticker=?", (t,)).fetchone():
        raise ValueError(f"Nie znam spółki {t}")
    if flag in (None, "", "auto"):
        con.execute("DELETE FROM company_flags WHERE ticker=?", (t,))
        return
    if flag not in FLAGS:
        raise ValueError("Flaga musi być: green, neutral, red albo auto")
    con.execute("INSERT INTO company_flags(ticker, flag, note, updated) VALUES(?,?,?,?) ON CONFLICT(ticker) DO UPDATE "
                "SET flag=excluded.flag, note=excluded.note, updated=excluded.updated",
                (t, flag, (note or "").strip() or None, datetime.now().isoformat(timespec="seconds")))
