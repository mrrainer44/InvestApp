"""Ostrzeżenia "nie dotykaj" - sytuacje, w których warto wstrzymać się z zakupem i sprawdzić szczegóły.

  emisja      - komunikat o emisji akcji, ofercie lub podwyższeniu kapitału z ostatnich 60 dni (rozwodnienie),
  sprzedaż    - główny akcjonariusz (art. 69) albo insider (MAR) sprzedawał w ostatnich 30 dniach po dużym wzroście
                kursu (3 miesiące co najmniej +30% albo miesiąc +20%),
  raport      - brak raportu okresowego za okres, którego ustawowy termin już minął (wg Biznesradar), albo raport
                opóźniony względem harmonogramu spółki,
  skrajności  - NewConnect: C/WK powyżej 20, ujemna EBITDA (ujemne EV/EBITDA) albo kapitalizacja poniżej 20 mln zł.
To sygnał do sprawdzenia, nie wyrok - np. emisja może finansować dobry projekt.
"""
import json
import re
from datetime import date, timedelta

from . import espi, technicals

# ustawowe terminy raportów: (kwartał, miesiąc-dzień terminu, przesunięcie roku)
_DEADLINES = {"GPW": [(1, "05-29", 0), (2, "09-30", 0), (3, "11-29", 0), (4, "04-30", 1)],
              "NC": [(1, "05-15", 0), (2, "08-14", 0), (3, "11-14", 0), (4, "02-14", 1)]}
_PERIODIC = re.compile(r"raport\w*\s+(okresow|kwartaln|p[oó][lł]roczn|roczn)|\bQSr\b|\bPSr\b|\bSA-?[QPR]\b|\bRS\b|"
                       r"quarterly report|half-?year(ly)? report|annual report|interim report", re.I)


def expected_period(market, today=None, grace=3):
    """Najnowszy okres (rok, kwartał), którego raport już musiał się ukazać."""
    today = today or date.today()
    best = None
    for year in (today.year - 1, today.year):
        for q, md, shift in _DEADLINES.get(market, _DEADLINES["GPW"]):
            dl = date.fromisoformat(f"{year + shift}-{md}") + timedelta(days=grace)
            if dl < today and (best is None or (year, q) > best):
                best = (year, q)
    return best


def _period(s):
    m = re.match(r"(\d{4})/Q([1-4])", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _pl(v, d):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


_cache = {"key": None, "data": None}


def compute(con, today=None):
    """Ostrzeżenia wszystkich spółek {ticker: [{kind, level, text}]}; zapamiętane do następnego pobrania."""
    key = (today, con.execute("SELECT MAX(finished) FROM runs").fetchone()[0],
           con.execute("SELECT MAX(id) FROM espi").fetchone()[0], con.execute("SELECT COUNT(*) FROM changes").fetchone()[0])
    if _cache["key"] == key and today is None:
        return _cache["data"]
    data = _compute(con, today)
    if today is None:
        _cache.update(key=key, data=data)
    return data


def _compute(con, today=None):
    today = today or date.today()
    t = today.isoformat()
    tech = technicals.compute(con)["rows"]
    co = {r["ticker"]: r for r in con.execute(
        "SELECT c.ticker, c.market, c.isin, r.cwk, r.evebitda, r.report FROM companies c "
        "LEFT JOIN ratios r ON r.ticker=c.ticker")}
    out = {}

    def add(tk, kind, level, text):
        out.setdefault(tk, []).append({"kind": kind, "level": level, "text": text})

    # emisje akcji
    for r in con.execute("SELECT ticker, ts, title FROM espi WHERE ts>=? AND ticker IS NOT NULL ORDER BY ts DESC",
                         ((today - timedelta(days=60)).isoformat(),)):
        if "emisja" in espi.keywords(r["title"]) and not any(w["kind"] == "emisja" for w in out.get(r["ticker"], [])):
            add(r["ticker"], "emisja", "warn", f"Emisja akcji / podwyższenie kapitału: {espi.split_title(r['title'])[1]} "
                                              f"({r['ts'][8:10]}.{r['ts'][5:7]})")

    # sprzedaż głównego akcjonariusza lub insidera po dużym wzroście (jedno ostrzeżenie na spółkę)
    sellers = {}
    for r in con.execute("SELECT ticker, investor, SUM(delta) d, SUM(value) v, source FROM changes "
                         "WHERE source IN ('art69','mar') AND excluded=0 AND date>=? GROUP BY ticker, investor_norm, source "
                         "HAVING SUM(delta) < 0", ((today - timedelta(days=30)).isoformat(),)):
        g = sellers.setdefault(r["ticker"], {"who": [], "shares": 0.0, "value": 0.0})
        if r["investor"] not in g["who"]:
            g["who"].append(r["investor"])
        g["shares"] += -r["d"]
        g["value"] += -(r["v"] or 0)
    for tk, g in sellers.items():
        x = tech.get(tk) or {}
        r3, r1 = x.get("ret_3m"), x.get("ret_1m")
        if (r3 is not None and r3 >= 30) or (r1 is not None and r1 >= 20):
            rise = f"{r3:+.0f}% w 3 mies." if r3 is not None and r3 >= 30 else f"{r1:+.0f}% w miesiąc"
            who = g["who"][0] if len(g["who"]) == 1 else f"{len(g['who'])} sprzedających ({', '.join(g['who'][:2])}...)"
            val = f", ok. {_pl(g['value'] / 1e6, 1)} mln zł" if g["value"] else ""
            add(tk, "sprzedaz", "warn", f"Duzi akcjonariusze lub insiderzy sprzedają po wzroście kursu ({rise}): {who} - "
                                       f"{_pl(g['shares'], 0)} akcji{val} w 30 dni")

    # raporty okresowe: dane finansowe w Biznesradar starsze niż okres po terminie ustawowym I brak raportu okresowego
    # w komunikatach od końca tego kwartału (samo opóźnienie Biznesradar to za mało - często to tylko jego dane)
    last_periodic = {}
    for r in con.execute("SELECT ticker, ts, title FROM espi WHERE ts>=? AND ticker IS NOT NULL",
                         (f"{today.year - 1}-07-01",)):
        subj = espi.split_title(r["title"])[1] or ""
        if _PERIODIC.search(subj) and espi.classify(r["title"]) != "terminy":
            last_periodic[r["ticker"]] = max(last_periodic.get(r["ticker"], ""), r["ts"][:10])
    for tk, c in co.items():
        exp = expected_period(c["market"], today)
        have = _period(c["report"])
        # tylko spółki polskie (dane finansowe zagranicznych emitentów w Biznesradar bywają nieaktualne) i opóźnienie
        # o co najmniej 2 kwartały - pojedynczy kwartał to częściej opóźnienie aktualizacji danych niż spółki
        lag = (exp[0] * 4 + exp[1]) - (have[0] * 4 + have[1]) if exp and have else 0
        if lag >= 2 and (c["isin"] or "PL").startswith("PL"):
            q_end = date(exp[0], exp[1] * 3, 1) + timedelta(days=31)
            q_end = q_end.replace(day=1) - timedelta(days=1)
            if last_periodic.get(tk, "") <= q_end.isoformat():
                add(tk, "raport", "warn", f"Brak raportu za {exp[1]} kw. {exp[0]} po ustawowym terminie - ostatnie dane "
                                         f"finansowe za {have[1]} kw. {have[0]}, w komunikatach nie widać nowszego raportu")
    sched = {}
    for r in con.execute("SELECT ticker, parsed FROM espi WHERE category='terminy' AND fetched=1 AND ticker IS NOT NULL "
                         "AND ts>=? ORDER BY ts", (f"{today.year - 1}-12-01",)):
        for kind, d in (json.loads(r["parsed"] or "{}").get("dates") or {}).items():
            sched.setdefault(r["ticker"], {})[kind] = d
    for tk, kinds in sched.items():
        # raporty okresowe widać w komunikatach tylko na NewConnect (EBI); na rynku głównym idą osobnym kanałem
        if (co.get(tk) or {}).get("market") != "NC":
            continue
        due = [d for d in kinds.values() if d <= (today - timedelta(days=2)).isoformat()]
        if not due:
            continue
        last_due = max(due)
        if last_periodic.get(tk, "") < (date.fromisoformat(last_due) - timedelta(days=1)).isoformat():
            kind = next(k for k, d in kinds.items() if d == last_due)
            add(tk, "raport_opozniony", "warn", f"Według harmonogramu {espi.REPORT_LABEL[kind]} miał się ukazać "
                                                f"{last_due[8:10]}.{last_due[5:7]} - nie widać go w komunikatach")

    # NewConnect: skrajne wskaźniki
    for tk, c in co.items():
        if c["market"] != "NC":
            continue
        x = tech.get(tk) or {}
        why = []
        if c["cwk"] is not None and c["cwk"] > 20:
            why.append(f"C/WK {_pl(c['cwk'], 1)}")
        if c["evebitda"] is not None and c["evebitda"] < 0:
            why.append("ujemna EBITDA")
        if x.get("mcap") and x["mcap"] < 20e6:
            why.append(f"kapitalizacja {_pl(x['mcap'] / 1e6, 1)} mln zł")
        if why:
            add(tk, "skrajne", "info", "NewConnect, skrajne wskaźniki: " + ", ".join(why))
    return out
