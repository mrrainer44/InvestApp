"""Kalendarz na najbliższe dni: wydarzenia spółek i makro.

  dywidendy  - ostatni dzień z prawem i dzień odcięcia (tabela dividends),
  raporty    - daty z harmonogramów publikacji raportów okresowych (komunikaty "Terminy przekazywania raportów
               okresowych", najnowszy harmonogram i jego zmiany) oraz ustawowe terminy raportów,
  WZ         - walne zgromadzenia ze zwołań (data z treści komunikatu),
  wezwania   - przyjmowanie zapisów (daty z treści wezwania),
  makro      - posiedzenia decyzyjne RPP (harmonogram NBP) i publikacje inflacji GUS (orientacyjnie, wg reguły GUS).
"""
import json
from datetime import date, timedelta

from . import espi

# Harmonogram NBP (nbp.pl, Rada Polityki Pieniężnej -> Harmonogram posiedzeń RPP). Serwis NBP blokuje pobieranie
# automatyczne, więc daty są przepisane ręcznie - do aktualizacji raz w roku (zwykle w grudniu).
RPP = {
    2026: [("2026-01-14", True), ("2026-02-04", True), ("2026-03-04", True), ("2026-04-09", True), ("2026-05-06", True),
           ("2026-06-02", True), ("2026-07-08", True), ("2026-08-25", False), ("2026-09-09", True), ("2026-10-07", True),
           ("2026-11-04", True), ("2026-12-02", True)],
}
# ustawowe terminy raportów za III kwartał / półrocze / I kwartał: GPW 60 dni (półrocze 3 miesiące), NewConnect 45 dni
LEGAL = [("05-15", "NC", "q1"), ("05-29", "GPW", "q1"), ("08-14", "NC", "q2"), ("09-30", "GPW", "h1"),
         ("11-14", "NC", "q3"), ("11-29", "GPW", "q3"), ("03-31", "GPW+NC", "y"), ("04-30", "GPW+NC", "y")]


def _cap(s):
    return s[:1].upper() + s[1:]


def _workday_back(d):
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _cpi_dates(year):
    """GUS: szybki szacunek inflacji w ostatni dzień roboczy miesiąca, pełne dane ok. 15. dnia następnego miesiąca."""
    out = []
    for m in range(1, 13):
        nxt = date(year + (m == 12), m % 12 + 1, 1)
        out.append((_workday_back(nxt - timedelta(days=1)).isoformat(), "Szybki szacunek inflacji CPI (GUS)"))
        out.append((_workday_back(date(year, m, 15)).isoformat(), "Inflacja CPI za poprzedni miesiąc – pełne dane (GUS)"))
    return out


def events(con, days=14, start=None):
    today = date.fromisoformat(start) if start else date.today()
    end = today + timedelta(days=days)
    t0, t1 = today.isoformat(), end.isoformat()
    names = {r["ticker"]: (r["full_name"] or r["short_name"], r["market"]) for r in con.execute(
        "SELECT ticker, full_name, short_name, market FROM companies")}
    held = {r[0] for r in con.execute("SELECT DISTINCT ticker FROM positions WHERE closed IS NULL")}
    out = []

    def add(d, kind, title, ticker=None, detail="", source=""):
        out.append({"date": d, "kind": kind, "title": title, "ticker": ticker,
                    "name": names.get(ticker, (None,))[0] if ticker else None,
                    "market": names.get(ticker, (None, None))[1] if ticker else None,
                    "held": ticker in held, "detail": detail, "source": source})

    # dywidendy: dzień odcięcia = sesja po ostatnim dniu z prawem
    seen = set()
    for r in con.execute("SELECT ticker, last_day, pay_day, dps, status FROM dividends WHERE dps>0 AND "
                         "((last_day BETWEEN ? AND ?) OR (pay_day BETWEEN ? AND ?))", (t0, t1, t0, t1)):
        k = (r["ticker"], r["last_day"], r["dps"])
        if k in seen:
            continue
        seen.add(k)
        if t0 <= (r["last_day"] or "") <= t1:
            add(r["last_day"], "dywidenda", f"Ostatni dzień z prawem do dywidendy {r['dps']:.2f} zł".replace(".", ","), r["ticker"],
                "Następnego dnia kurs spadnie technicznie o wartość dywidendy.", "Biznesradar")
        if t0 <= (r["pay_day"] or "") <= t1:
            add(r["pay_day"], "wyplata", f"Wypłata dywidendy {r['dps']:.2f} zł".replace(".", ","), r["ticker"], "", "Biznesradar")

    # raporty okresowe z harmonogramów (najnowszy harmonogram i zmiany - kolejno nadpisują daty)
    sched = {}
    for r in con.execute("SELECT ticker, ts, parsed FROM espi WHERE category='terminy' AND fetched=1 AND ticker IS NOT NULL "
                         "AND ts>=? ORDER BY ts", (f"{today.year - 1}-12-01",)):
        for kind, d in (json.loads(r["parsed"] or "{}").get("dates") or {}).items():
            sched.setdefault(r["ticker"], {})[kind] = d
    for t, kinds in sched.items():
        for kind, d in kinds.items():
            if t0 <= d <= t1:
                add(d, "raport", _cap(espi.REPORT_LABEL.get(kind, "raport okresowy")), t,
                    "Termin z harmonogramu publikacji raportów okresowych spółki.", "ESPI/EBI")
    for md, mkt, kind in LEGAL:
        d = f"{today.year}-{md}"
        if t0 <= d <= t1:
            add(d, "raport_termin", f"Ustawowy termin: {espi.REPORT_LABEL[kind]} ({mkt})", None,
                "Ostatni dzień na publikację - spółki bez harmonogramu zwykle publikują tuż przed nim.", "przepisy")

    # walne zgromadzenia
    for r in con.execute("SELECT ticker, ts, title, parsed FROM espi WHERE category='wz_zwolanie' AND fetched=1 "
                         "AND ts>=?", ((today - timedelta(days=75)).isoformat(),)):
        d = (json.loads(r["parsed"] or "{}").get("meeting") or "")
        if t0 <= d <= t1:
            tl = r["title"].lower()
            kind = "Nadzwyczajne " if "nadzwyczajn" in tl or "extraordinary" in tl else                 "Zwyczajne " if "zwyczajn" in tl or "annual" in tl else ""
            add(d, "wz", f"{kind}Walne Zgromadzenie", r["ticker"], espi.split_title(r["title"])[1], "ESPI/EBI")

    # wezwania: zapisy
    for r in con.execute("SELECT ticker, ts, title, parsed FROM espi WHERE category='wezwanie' AND fetched=1 AND ts>=?",
                         ((today - timedelta(days=90)).isoformat(),)):
        tnd = json.loads(r["parsed"] or "{}").get("tender") or {}
        price = f" po {tnd['price']:.2f} zł".replace(".", ",") if tnd.get("price") else ""
        for key, label in (("start", "Początek zapisów w wezwaniu"), ("end", "Koniec zapisów w wezwaniu")):
            if t0 <= (tnd.get(key) or "") <= t1:
                add(tnd[key], "wezwanie", label + price, r["ticker"], espi.split_title(r["title"])[1], "ESPI/EBI")

    # makro
    for d, decision in RPP.get(today.year, []) + RPP.get(today.year + 1, []):
        if t0 <= d <= t1:
            add(d, "rpp", "Posiedzenie RPP – decyzja o stopach procentowych" if decision else "Posiedzenie RPP (bez decyzji)",
                None, "Harmonogram NBP.", "NBP")
    for d, label in _cpi_dates(today.year) + _cpi_dates(today.year + 1):
        if t0 <= d <= t1:
            add(d, "cpi", label, None, "Orientacyjnie, według stałego harmonogramu GUS.", "GUS")

    order = {"rpp": 0, "cpi": 1, "raport_termin": 2, "dywidenda": 3, "wyplata": 4, "wezwanie": 5, "wz": 6, "raport": 7,
             "emisja": 8}
    out.sort(key=lambda e: (e["date"], not e["held"], order.get(e["kind"], 9), e["ticker"] or ""))
    return {"from": t0, "to": t1, "events": out,
            "schedules": len(sched), "rpp_year_known": today.year in RPP}
