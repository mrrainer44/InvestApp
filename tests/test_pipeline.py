"""Test całego potoku offline: strony Biznesradar są podmienione na fixtury
odtwarzające prawdziwą strukturę HTML (pobraną 16.10.2026).

Uruchom:  python -m pytest -q tests   (albo: python tests/test_pipeline.py)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"

TMP = Path(tempfile.mkdtemp())
os.environ["GPWT_TEST"] = "1"
from gpwt import config  # noqa: E402

config.DB_PATH = TMP / "test.sqlite"
config.PDF_CACHE = TMP / "pdf"
config.PDF_CACHE.mkdir()
import gpwt.collect as _c  # noqa: E402
_c.PDF_CACHE = config.PDF_CACHE
from gpwt import db  # noqa: E402

db.DB_PATH = config.DB_PATH


def qrow(tk, short, slug, title, close, chg, vol, turn):
    return (f'<tr class="hot-row"><td><a href="/notowania/{slug}" title="{title}">{tk} ({short})</a></td>'
            f'<td class="hot-value"><span>15:04</span></td><td><span>{close}</span></td><td><span>+0,10</span></td>'
            f'<td><span class="value--up">({chg})</span></td><td>1</td><td>1</td><td>1</td><td>1</td>'
            f'<td><span class="value--int">{vol}</span></td><td><span class="value--int">{turn}</span></td><td class="sparks"></td></tr>')


QHEAD = ('<table class="table"><thead><tr><th><a>Profil</a></th><th>Czas</th><th>Kurs</th><th>Zmiana</th>'
         '<th>Zmiana&nbsp;%</th><th>Odn.</th><th>Otw.</th><th>Min.</th><th>Max.</th><th>Wolumen</th><th>Obrót</th>'
         '<th class="sparks">1r</th></tr></thead><tbody>')
GPW_ROWS = [("PKO", "PKOBP", "PKO", "PKO BP", "115,84", "+0,57%", "2 801 040", "323 180 854"),
            ("11B", "11BIT", "11-BIT-STUDIOS", "11 BIT STUDIOS", "121,00", "+0,67%", "6 869", "824 830"),
            ("OUT", "OUTDOORZY", "OUT", "OUTDOORZY", "3,10", "-1,00%", "1 000", "3 100"),
            ("CPD", "CELTIC", "CPD", "CPD", "0,700", "-5,41%", "23 770", "16 921"),
            ("EBP", "ERSTEPL", "EBP", "ERSTE BANK POLSKA", "500,00", "+0,10%", "1 000", "500 000")]
NC_ROWS = [("TBT", "TRUSTBTC", "TBT", "TRUSTBTC", "1,20", "0,00%", "500", "600")]

RET = ('<table class="table"><thead><tr><th>Profil</th><th>1t</th><th>1m</th><th>3m</th><th>6m</th><th>YTD</th>'
       '<th>12m</th><th>24m</th><th>36m</th><th>60m</th><th>120m</th></tr></thead><tbody>'
       '<tr><td><a href="/stopa-zwrotu/PKO" title="PKO BP">PKO (PKOBP)</a></td><td>+0,80%</td><td>-3,71%</td>'
       '<td>+12,31%</td><td>+21,82%</td><td>+43,88%</td><td>+61,22%</td><td>bd.</td><td>bd.</td><td>bd.</td><td>bd.</td></tr>'
       '</tbody></table>')
RATIO = ('<table class="table"><thead><tr><th>Profil</th><th>Raport</th><th>Cena / Zysk</th><th>r/r</th><th>k/k</th>'
         '</tr></thead><tbody><tr><td><a href="/wskazniki-wartosci-rynkowej/PKO" title="PKO BP">PKO (PKOBP)</a></td>'
         '<td>2026/Q2</td><td class="value--bold"><span class="pv"><span>13,36</span></span></td><td></td><td></td></tr>'
         '</tbody></table>')
DIV = ('<table class="table"><thead><tr><th>Profil</th><th>Dywidenda za rok</th><th>Data WZA</th>'
       '<th>Ostatnie notowanie z prawem do dywidendy</th><th>Dzień wypłaty</th><th>Dywidenda na akcję</th>'
       '<th>Stopa dywidendy*</th><th>Status</th></tr></thead><tbody>'
       '<tr><td><a href="/dywidenda/PKO" title="PKO BP">PKO (PKOBP)</a></td><td>2025</td><td>29 cze 26</td>'
       '<td>03 sie 26</td><td>13 sie 26</td><td> 6,14 PLN </td><td><a></a></td><td> wypłacona </td></tr>'
       '</tbody></table>')


ISINS = {"PKO": "PLPKO0000016", "11-BIT-STUDIOS": "PL11BTS00015", "OUT": "PLOUTDR00012",
         "CPD": "PLCELPD00013", "EBP": "PLBZ00000044", "TBT": "PLTRSTB00011"}


def akc_page(rows, shares="1 250 000 000", isin="PLPKO0000016"):
    tr = "".join(f"<tr><td>{h}</td><td>{p} %</td><td>{s}</td><td>1</td><td>{p} %</td><td>{s}</td><td>{d}</td></tr>"
                 for h, p, s, d in rows)
    return (f'<table class="profileSummary"><tr><th>ISIN:</th><td>{isin}</td></tr>'
            f'<tr><th>Liczba akcji:</th><td><a>{shares}</a></td></tr><tr><th>Kapitalizacja:</th><td>1</td></tr>'
            '<tr><th>Branża:</th><td><a>Banki</a></td></tr></table>'
            '<table class="qTableFull"><tbody><tr><th>Akcjonariusz</th><th>Udział</th><th>Liczba akcji</th>'
            '<th>Wartość rynkowa</th><th>Udział na WZA</th><th>Liczba głosów</th><th>Data aktualizacji</th></tr>'
            f'{tr}<tr class="summary"><th>razem</th><td>1</td><td>1</td><td>1</td><td>1</td><td>1</td><td></td></tr></tbody></table>')


ESPI_LIST = """
<div><h3><a href="/a/162118,prime">OUTDOORZY SA (16/2026) Zawiadomienie w trybie art. 69 Ustawy o ofercie publicznej</a></h3>
<p>x</p><div><div class="time">2026-10-14, 18:00</div></div></div>
<div><h3><a href="/a/162088,cpd">CPD SA (41/2026) Powiadomienie osoby pełniącej obowiązki zarządcze o transakcji na akcjach Emitenta</a></h3>
<p>x</p><div><div class="time">2026-10-16, 08:26</div></div></div>
<div><h3><a href="/a/161596,pko">PKO BP SA (39/2026) Wykaz akcjonariuszy posiadających co najmniej 5% liczby głosów na Nadzwyczajnym Walnym Zgromadzeniu PKO Bank</a></h3>
<p>x</p><div><div class="time">2026-10-14, 13:56</div></div></div>
<div><h3><a href="/a/162097,tbt">TRUSTBTC SA (17/2026) Otrzymanie zawiadomień w trybie art. 69 ustawy o ofercie publicznej - zwiększenie stanu posiadania</a></h3>
<p>x</p><div><div class="time">2026-10-15, 20:00</div></div></div>
<div><h3><a href="/a/162076,bog">LW BOGDANKA SA (19/2026) Informacja w sprawie wstępnych wyników</a></h3>
<p>x</p><div><div class="time">2026-10-16, 08:00</div></div></div>
<h2>Najczęściej czytane</h2><div><h3><a href="/a/161995,premium">[BR Premium] Co robią grube ryby</a></h3><span class="time js-ago">16 minut temu</span></div>
"""


def article(body, pdfs=()):
    files = "".join(f'<li><a class="file file--pdf" href="{p}">x.pdf</a></li>' for p in pdfs)
    return (f'<article class="article"><header><h1>t</h1><div class="article__meta"><time>2026-10-14, 18:00</time></div>'
            f'<ul class="article__files">{files}</ul></header><div class="article__content">'
            f'<div class="article__body">{body}</div></div></article>')


HIST = ('<table class="qTableFull"><tbody><tr><th>Data</th><th>Otwarcie</th><th>Max</th><th>Min</th><th>Zamknięcie</th>'
        '<th>Wolumen</th><th>Obrót</th></tr>'
        '<tr><td>15.10.2026</td><td>3</td><td>3</td><td>3</td><td>3.10</td><td>1</td><td>1</td></tr>'
        '<tr><td>12.10.2026</td><td>3</td><td>3</td><td>3</td><td>3.05</td><td>1</td><td>1</td></tr>'
        '<tr><td>06.10.2026</td><td>1</td><td>1</td><td>1</td><td>1.15</td><td>1</td><td>1</td></tr>'
        '<tr><td>05.10.2026</td><td>3</td><td>3</td><td>3</td><td>2.95</td><td>1</td><td>1</td></tr></tbody></table>')

STATE = {"akc_round": 1}


def gpw_li(ts, kind, no, company, gid, subject):
    return (f'<li><span class="date">{ts} | {kind} | ESPI | {no}</span><strong class="name">'
            f'<a href="komunikat?geru_id={gid}&amp;title=x">{company}</a></strong>'
            f'<span class="profit"><small>Zmiana</small> 0,10%</span><p>{subject}</p>'
            f'<a href="komunikat?geru_id={gid}&amp;title=x">więcej &gt;</a></li>')


GPW_LIST = (gpw_li("16-10-2026 09:00:00", "Bieżący", "42/2026", "CPD SPÓŁKA AKCYJNA (PLCELPD00013)", 499100,
                   "Powiadomienie o transakcjach otrzymane w trybie art. 19 Rozporządzenia MAR")
            + gpw_li("20-08-2026 10:15:30", "Bieżący", "30/2026", "CPD SPÓŁKA AKCYJNA (PLCELPD00013)", 480001,
                     "Powiadomienie o transakcjach otrzymane w trybie art. 19 Rozporządzenia MAR")
            + gpw_li("30-12-2025 16:00:00", "Bieżący", "50/2025", "CPD SPÓŁKA AKCYJNA (PLCELPD00013)", 460000,
                     "Powiadomienie o transakcjach otrzymane w trybie art. 19 Rozporządzenia MAR"))
NC_LIST = gpw_li("05-03-2026 12:00:00", "Bieżący", "3/2026", "TRUSTBTC S.A. (PLTRSTB00011)", 230001,
                 "Rejestracja zmian statutu")
GPW_DETAIL = ('<section><div class="report-data"><div class="dane"><p>Podstawa prawna: Art. 19 ust. 3 MAR</p>'
              '<a href="attachment/zal01_Zakup.pdf,20260820_101530_1,20260820">Zakup.pdf</a></div></div></section>')


def ofe_xlsx(rows):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    for r in [["7", "Akcje spółek notowanych na rynku regulowanym na terytorium Rzeczypospolitej Polskiej oraz "
                    "obligacje zamienne na akcje tych spółek"]] + rows + [
            ["9", "Akcje spółek notowanych na rynku regulowanym w państwach innych niż Rzeczpospolita Polska"],
            ["APPLE INC", 1.0, 5_000_000]]:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# struktury PKO OFE: CPD 1,0 mln akcji -> 1,3 mln (+300 tys.), 11 BIT sprzedane w całości do końca 2025;
# Santander Bank Polska (dziś Erste, EBP) 2 tys. -> 3 tys. akcji; Shoper wycofany z obrotu w 2025 (sprzedany)
OFE_DOCS = {
    "EBAN1/RR/2024-12-31": [["CPD S.A.", 0.1, 700_000.0], ["11 BIT STUDIOS S.A.", 0.5, 12_000_000.0],
                            ["Santander Bank Polska S.A.", 0.1, 1_000_000.0], ["Shoper S.A.", 0.1, 5_000_000.0]],
    "EBAN1/RP/2025-06-30": [["CPD S.A.", 0.1, 910_000.0]],
    "EBAN1/RR/2025-12-31": [["CPD S.A.", 0.1, 910_000.0], ["SANTANDER BANK POLSKA S.A.", 0.1, 1_500_000.0]],
}
# eksport XLS archiwum notowań gpw.pl (w teście XLSX - parser czyta oba)
ARCH_HEAD = ["Data", "Nazwa", "ISIN", "Waluta", "Kurs otwarcia", "Kurs max", "Kurs min", "Kurs zamknięcia", "Zmiana"]
ARCHIVE = {
    "30-12-2024": [("CELTIC", "PLCELPD00013", 0.7), ("11BIT", "PL11BTS00015", 120.0),
                   ("SANPL", "PLBZ00000044", 500.0), ("SHOPER", "PLSHPR000021", 40.0)],
    "30-06-2025": [("CELTIC", "PLCELPD00013", 0.7), ("11BIT", "PL11BTS00015", 120.0),
                   ("SANPL", "PLBZ00000044", 500.0)],
    "30-12-2025": [("CELTIC", "PLCELPD00013", 0.7), ("11BIT", "PL11BTS00015", 120.0),
                   ("ERSTEPL", "PLBZ00000044", 500.0)],
}


def archive_xlsx(d):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(ARCH_HEAD)
    for name, isin, close in ARCHIVE.get(d, ARCHIVE["30-12-2025"]):
        wb.active.append([d, name, isin, "PLN", close, close, close, close, 0.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


REQUESTED = []
REJECTED = b"<html><head><title>Request Rejected</title></head><body>The requested URL was rejected.</body></html>"


def fake_get(path, binary=False, tries=3):
    REQUESTED.append(path)
    p = path.replace(config.BASE, "")
    if p.startswith("https://dokumenty.analizy.pl/pobierz/fe/"):
        rows = OFE_DOCS.get(p.split("/pobierz/fe/")[1])
        return ofe_xlsx(rows) if rows else None
    if p.startswith("https://www.gpw.pl/archiwum-notowan"):
        d = p.split("date=")[1]
        return b"<html>brak sesji</html>" if d.startswith("31-12-") else archive_xlsx(d)
    if "/ajaxindex.php?" in p:
        if "offset=0&" not in p:
            return ""
        return GPW_LIST if p.startswith("https://www.gpw.pl/") else NC_LIST
    if p == "https://www.gpw.pl/komunikat?geru_id=480001":
        return GPW_DETAIL
    if binary and (p.startswith("https://www.gpw.pl/attachment/") or p == "/pdf/blocked.pdf"):
        return REJECTED  # tak serwer odpowiada na automatyczne pobieranie załącznika
    if binary:
        name = {"/pdf/hegen.pdf": "art69_hegen.txt", "/pdf/bt.pdf": "art69_bt.txt"}.get(p)
        if name:
            return ("%PDF-TXT:" + (FIX / name).read_text(encoding="utf-8")).encode()
        if p == "/pdf/mar.pdf":
            return (FIX / "mar.pdf").read_bytes()
        return None
    if p == "/gielda/akcje_gpw":
        return QHEAD + "".join(qrow(*r) for r in GPW_ROWS) + "</tbody></table>"
    if p == "/gielda/newconnect":
        return QHEAD + "".join(qrow(*r) for r in NC_ROWS) + "</tbody></table>"
    if p.startswith("/stopy-zwrotu/akcje_gpw"):
        return RET
    if p.startswith("/spolki-wskazniki-wartosci-rynkowej/akcje_gpw,1,CZ"):
        return RATIO
    if p.startswith("/dywidendy/akcje_gpw,2026"):
        return DIV
    if p.startswith("/akcjonariat/PKO"):
        if STATE["akc_round"] == 1:
            return akc_page([("Skarb Państwa", "29.43", "367 918 980", "29.06.2026"),
                             ("OFE Nationale Nederlanden", "7.03", "87 916 000", "29.06.2026"),
                             ("TFI PZU S.A.", "0.79", "9 867 062", "31.03.2026")])
        return akc_page([("Skarb Państwa", "29.43", "367 918 980", "29.06.2026"),
                         ("OFE Nationale Nederlanden", "7.03", "87 916 000", "29.06.2026"),
                         ("TFI PZU S.A.", "0.81", "10 167 062", "30.06.2026")])
    if p.startswith("/akcjonariat/"):
        return akc_page([], "26 150 000", ISINS[p.split("/")[-1]])
    if p == "/temat/76,espi-ebi":
        return ESPI_LIST
    if p.startswith("/temat/76,espi-ebi,"):
        return "<html></html>"
    if p == "/a/162118,prime":
        return article("<p>Zawiadomienie</p>", ["/pdf/hegen.pdf"])
    if p == "/a/162088,cpd":
        return article("<p>Podstawa prawna: Art. 19 ust. 3 MAR</p>", ["/pdf/mar.pdf"])
    if p == "/a/161596,pko":
        return article("".join(f"<p>{x}</p>" for x in (FIX / "wz_pko.txt").read_text(encoding="utf-8").splitlines()))
    if p == "/a/162097,tbt":
        return article("<p>zawiadomienia</p>", ["/pdf/bt.pdf", "/pdf/blocked.pdf"])
    if p.startswith("/notowania-historyczne/"):
        return HIST
    return "<html></html>"


def fake_pdf_text(data):
    if data.startswith(b"%PDF-TXT:"):
        return data[9:].decode()
    from pypdf import PdfReader
    import io
    return "\n".join(pg.extract_text() for pg in PdfReader(io.BytesIO(data)).pages)


def test_pipeline():
    from gpwt import collect, espi, http, flows
    http.get = fake_get
    collect.http.get = fake_get
    collect.br.http.get = fake_get
    espi.pdf_text = fake_pdf_text
    db.init()

    # presja kupujących: zamknięcie na maksimum = +1, na minimum = -1, za mało sesji = brak oceny
    from gpwt import pressure
    up = {"high": 10.0, "low": 8.0, "close": 10.0, "turnover": 100.0}
    down = {"high": 10.0, "low": 8.0, "close": 8.0, "turnover": 100.0}
    assert pressure.cmf([up] * 20) == 1 and pressure.cmf([down] * 20) == -1
    assert pressure.cmf([up] * 10 + [down] * 10) == 0 and pressure.cmf([up] * 5) is None
    assert pressure.clv({"high": 9.0, "low": 9.0, "close": 9.0}) == 0  # brak zakresu dnia

    # rodzaj instrumentu z formularzy MAR ("transakcja" zawiera "akcj", ale to nie akcje)
    from gpwt.espi import instrument_is_shares as is_sh
    assert is_sh("Akcje zwykłe na okaziciela") and is_sh("akcji serii B")
    assert not is_sh("Negocjowana terminowa transakcja wymiany walut")
    assert not is_sh("uprawnienia do emisji gazów cieplarnianych") and not is_sh("Kontrakt terminowy na akcje PGE")
    assert not is_sh("Obligacje") and not is_sh("Instrument dłużny")
    assert is_sh("MOL ordinary shares (ISIN: HU0000153937)") and is_sh("Shares in Kernel Holding S.A.")
    assert not is_sh("MOL Eurobond (ISIN: XS3515070046)") and not is_sh("Warrants on shares of Sopharma AD")

    # angielskie komunikaty zagranicznych emitentów
    cl = espi.classify
    assert cl("MOL RT. (95/2026) Director/PDMR transaction") == "mar"
    assert cl("KERNEL HOLDING S.A. (27/2026) NOTIFICATION OF MANAGER'S TRANSACTION") == "mar"
    assert cl("KRKA D.D. (10/2026) Notification of transactions by person closely associated with person "
              "discharging managerial responsibilities") == "mar"
    assert cl("KRKA D.D. (27/2026) Notification on change of major holdings") == "art69"
    assert cl("NOVATURAS AB (278/2026) Notification on the acquisition of voting rights") == "art69"
    assert cl("KRKA D.D. (43/2026) Acquisition of treasury shares") == "skup"
    assert cl("PEPCO GROUP N.V. (1/2026) Share buyback programme: acquisition of shares from 1 - 5 April 2026") == "skup"
    assert cl("NOVATURAS AB (1/2026) Regarding approval of circular of the non-competitive mandatory tender offer") \
        == "wezwanie"
    assert cl("ASTARTA HOLDING PLC (1/2026) Shareholders holding at least 5% of shares at the AGM") == "wz_lista"
    assert cl("ENEFI PLC (57/2026) Number of voting rights") == "other"
    assert cl("MOL RT. (78/2026) Notifications on change in voting rights") == "other"  # łączna liczba głosów
    assert cl("SANTANDER (1/2026) Banco Santander announces a tender offer for one series of its notes") == "other"
    en = espi.parse_mar(
        "1. Details of the Person Discharging Managerial Responsibilities\na) Name Dr. Jan Kowalski\n"
        "2. Reason for the notification\na) Position/status Member of the Board\nb) Initial notification/ Amendment "
        "Initial notification\n3. Details of the issuer\na) Name MOL Plc.\n4. Details of the transaction(s): section "
        "to be repeated for (i) each type of instrument; (ii) each type of transaction\na) Description of the financial\n"
        "instrument, type of instrument\nIdentification code\nMOL ordinary shares (ISIN: HU0000153937)\n"
        "b) Nature of the transaction  sale\nc) Price(s) and volume(s)  Price(s) Volume(s)\n4810 HUF/piece\n9762 pieces\n"
        "d) Aggregated information\n- Aggregated volume\n- Price\n\n185030 pieces\n4888 HUF/piece\n"
        "e) Date of the transaction 12.10.2026\n")
    assert en["investor"] == "Dr. Jan Kowalski" and en["delta"] == -185030 and en["is_shares"]
    assert en["event_date"] == "2026-10-12" and "price" not in en  # cena w HUF - wartość z kursu na GPW
    en = espi.parse_mar("a) Name Namsen Limited\nb) Nature of the transaction Acquisition\n"
                        "d) Aggregated information\n- Aggregated volume\n- Price\n 1,027,948 \n19.93 PLN\n"
                        "e) Date of the transaction 2026-10-02")
    assert en["delta"] == 1027948 and en["price"] == 19.93
    en = espi.parse_mar("Based on Article 19 of Regulation (EU) No 596/2014, Krka announces:\nGašper Kastelic, the person "
                        "closely associated with the Member of the Management Board, informed the company that on "
                        "2 March 2026, he acquired 122 shares of the company at a weighted average price of EUR 236.00.")
    assert en["investor"] == "Gašper Kastelic" and en["delta"] == 122 and en["event_date"] == "2026-03-02"
    assert collect.stale_quote("16 paź 09:56") and not collect.stale_quote("16:59")

    # korekta zawiadomienia MAR zastępuje pierwotne (nie liczymy tej samej transakcji dwa razy)
    import json
    import sqlite3
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.executescript(db.SCHEMA)
    form = {"investor": "Krzysztof Kucharski", "delta": -25000, "price": 28.0, "instrument": "akcje"}
    for i, (ts, title, price) in enumerate([("2026-02-26 18:00", "AB SA (3/2026) Zawiadomienie o transakcjach", 28.0),
                                            ("2026-02-27 17:00", "AB SA (4/2026) Otrzymanie korekty zawiadomienia", 28.4)]):
        mem.execute("INSERT INTO espi(id, ticker, title, ts, category, parsed, fetched) VALUES(?,?,?,?,?,?,1)",
                    (i + 1, "ABE", title, ts, "mar", json.dumps({"forms": [{**form, "price": price}]})))
    flows.rebuild_changes(mem)
    ch = {r["price"]: r["excluded"] for r in mem.execute("SELECT price, excluded FROM changes")}
    assert ch == {28.0: 1, 28.4: 0}, ch

    # art. 69: data zdarzenia (transakcji), nie rozliczenia T+2 (CRJ: zdarzenie 16.10, rozliczenie 20.10)
    a69 = espi.parse_art69("Podmiot, którego dotyczy zdarzenie\nQUERCUS Parasolowy SFIO\nData przekazania zawiadomienia\n"
                           "2026-10-19\nData zdarzenia\n2026-10-16\nData rozliczenia transakcji\n2026-10-20\n"
                           "Data powzięcia informacji o zdarzeniu\n2026-10-16\n")
    assert a69["event_date"] == "2026-10-16", a69
    # po poprawce parsera stary odczyt znika (bez duplikatu), a wiersz poprawiony ręcznie zostaje
    mem.execute("INSERT INTO espi(id, ticker, title, ts, category, parsed, fetched) VALUES(9,'CRJ','CRJ (1/2026) Zawiadomienie',"
                "'2026-10-19 11:58','art69',?,1)", (json.dumps({"forms": [{"investor": "QUERCUS", "delta": 1945,
                                                                           "event_date": "2026-10-20"}]}),))
    flows.rebuild_changes(mem)
    mem.execute("UPDATE espi SET parsed=? WHERE id=9", (json.dumps({"forms": [{"investor": "QUERCUS", "delta": 1945,
                                                                           "event_date": "2026-10-16"}]}),))
    flows.rebuild_changes(mem)
    assert [r[0] for r in mem.execute("SELECT date FROM changes WHERE espi_id=90")] == ["2026-10-16"]
    mem.execute("UPDATE changes SET date='2026-10-15', verified=1 WHERE espi_id=90")
    flows.rebuild_changes(mem)
    assert [r[0] for r in mem.execute("SELECT date FROM changes WHERE espi_id=90")] == ["2026-10-15"]
    # ten sam raport opublikowany dwa razy (MTN 2/2026 o 13:35 i 13:56) liczy się raz
    for i, ts in ((20, "2026-01-09 13:35"), (21, "2026-01-09 13:56")):
        mem.execute("INSERT INTO espi(id, ticker, title, ts, category, parsed, fetched) VALUES(?,'MTN','MTN (2/2026) "
                    "zawiadomienie',?,'art69',?,1)", (i, ts, json.dumps({"forms": [{"investor": "SANFORD JOANNA",
                                                                                    "delta": 33397682}]})))
    flows.rebuild_changes(mem)
    assert [r[0] for r in mem.execute("SELECT excluded FROM changes WHERE ticker='MTN' ORDER BY espi_id")] == [0, 1]

    # Bankier.pl: lista komunikatów spółki (bez artykułów redakcji i bocznych list innych spółek) i dopasowanie
    from gpwt import bankier
    li = ('<li><span>{d}</span><a href="/wiadomosc/{p}-{s}-{i}.html">{t}</a><span>{k}</span></li>')
    html = "<ul>" + "".join(li.format(**x) for x in [
        dict(d="14.10.2026 18:00", p="MOL", s="Director-PDMR-transaction", i=1, t="Director/PDMR transaction", k="espi"),
        dict(d="14.10.2026 18:00", p="MOL", s="Number-of-voting-rights", i=2, t="Number of voting rights", k="espi"),
        dict(d="19.08.2026 16:01", p="MOL", s="Director-PDMR-transaction", i=3, t="Director/PDMR transaction", k="espi"),
        dict(d="19.08.2026 16:05", p="MOL", s="Bond-interest-payment", i=4, t="Bond interest payment", k="ebi"),
        dict(d="15.10.2026 10:00", p="MOL", s="Grupa-MOL-uruchomila", i=5, t="Grupa MOL uruchomiła", k="Firmy"),
        dict(d="15.10.2026 11:00", p="PKOBP", s="Raport", i=6, t="Raport", k="espi"),
    ]) + "</ul>"
    lst = bankier.parse_list(html)
    assert [x["url"][-6:] for x in lst] == ["1.html", "2.html", "3.html", "4.html"] and lst[0]["ts"] == "2026-10-14 18:00"
    assert bankier.match("2026-08-19 16:02", "MOL RT. (72/2026) Director/PDMR transaction", lst)["url"].endswith("-3.html")
    assert bankier.match("2026-10-14 17:59", "MOL RT. (95/2026) Director/PDMR transaction", lst)["url"].endswith("-1.html")
    assert bankier.match("2026-09-01 12:00", "Director/PDMR transaction", lst) is None
    assert bankier.attachments('<a href="https://bonnier.pl/static/att/emitent/2026-08/x_eng.pdf">plik</a>') == \
        ["https://bonnier.pl/static/att/emitent/2026-08/x_eng.pdf"]

    # nowszy układ Biznesradar: <th> bezpośrednio w <thead>, bez <tr>; pierwszy wiersz to już dane
    ret2 = collect.br.parse_returns(
        '<table><thead><th>Profil</th><th>1t</th><th>1m</th><th>3m</th></thead><tbody>'
        '<tr><td><a href="/stopa-zwrotu/06N" title="MAGNA">06N (06MAGNA)</a></td><td>+0,84%</td><td>-3,23%</td>'
        '<td>-2,83%</td></tr></tbody></table>')
    assert ret2 == [{"ticker": "06N", "r1w": 0.84, "r1m": -3.23, "r3m": -2.83, "r6m": None, "ytd": None,
                     "r12m": None, "r24m": None, "r36m": None}], ret2

    st, stats = collect.run(weekly=True)
    assert st == "ok", stats
    assert stats["quotes_GPW"] == 5 and stats["quotes_NC"] == 1

    con = db.connect()
    cats = dict(con.execute("SELECT id, category FROM espi").fetchall())
    assert cats[162118] == "art69" and cats[162088] == "mar" and cats[161596] == "wz_lista" and cats[162076] == "other"
    assert 161995 not in cats  # sekcja "Najczęściej czytane" pominięta
    tick = dict(con.execute("SELECT id, ticker FROM espi").fetchall())
    assert tick[162118] == "OUT" and tick[162088] == "CPD" and tick[161596] == "PKO" and tick[162097] == "TBT"

    ch = {r["source"] + ":" + r["ticker"]: dict(r) for r in con.execute("SELECT * FROM changes")}
    out = ch["art69:OUT"]
    assert out["delta"] == -140000 and out["date"] == "2026-10-05"  # data zdarzenia, nie rozliczenia
    assert abs(out["price"] - 2.95) < 1e-9 and abs(out["value"] - (-140000 * 2.95)) < 1e-6
    mar = ch["mar:CPD"]
    assert mar["delta"] == 30000 and mar["price"] == 0.1 and abs(mar["value"] - 3000) < 1e-9
    assert ch["art69:TBT"]["delta"] == 500000
    # odrzucony załącznik (strona HTML zamiast PDF) jest pomijany i nie trafia do pamięci podręcznej
    assert stats["espi_not_pdf"] == 1, stats
    assert not (config.PDF_CACHE / "162097_1.txt").exists()

    # druga runda: fundusz PZU dokupił akcje PKO -> zmiana "fundusze"
    STATE["akc_round"] = 2
    st, stats = collect.run(weekly=True)
    assert st == "ok", stats
    f = con.execute("SELECT * FROM changes WHERE source='fundusze' AND ticker='PKO'").fetchone()
    assert f and f["delta"] == 300000 and f["date"] == "2026-06-30", dict(f) if f else None

    # trzecia runda: historia z archiwów gpw.pl / newconnect.pl sprzed zasięgu listy Biznesradar
    st, stats = collect.run(since="2026-01-01")
    assert st == "ok", stats
    assert stats["gpw_history_new"] == 2, stats  # 16.10 jest w zasięgu Biznesradar, 2025 przed --since
    g = con.execute("SELECT * FROM espi WHERE id=?", (50_000_000 + 480001,)).fetchone()
    assert g["ticker"] == "CPD" and g["category"] == "mar" and g["ts"] == "2026-08-20 10:15", dict(g)
    assert g["url"] == "https://www.gpw.pl/komunikat?geru_id=480001" and g["fetched"] == 1
    assert "Art. 19 ust. 3 MAR" in g["body"]  # treść raportu jest czytana...
    assert not any("/attachment/" in u for u in REQUESTED)  # ...a zablokowanych załączników nie pobieramy
    nc = con.execute("SELECT * FROM espi WHERE id=?", (60_000_000 + 230001,)).fetchone()
    assert nc["ticker"] == "TBT" and nc["category"] == "other"

    # struktury portfeli OFE (zaimportowane już w pierwszej rundzie tygodniowej)
    ofe_rows = {(r["ticker"], r["date"]): dict(r) for r in con.execute(
        "SELECT * FROM changes WHERE note LIKE 'struktura portfela OFE%'")}
    cpd = ofe_rows[("CPD", "2025-06-30")]
    assert cpd["investor"] == "OFE PKO BP Bankowy" and cpd["source"] == "fundusze", cpd
    assert cpd["delta"] == 300000 and abs(cpd["value"] - 300000 * 0.7) < 1e-6, cpd
    sold = ofe_rows[("11B", "2025-12-31")]  # roczna struktura = pełna lista -> brak spółki to sprzedaż
    assert sold["delta"] == -100000 and abs(sold["value"] + 100000 * 120) < 1e-6, sold
    assert ("CPD", "2025-12-31") not in ofe_rows  # bez zmiany
    assert ("11B", "2025-06-30") not in ofe_rows  # półroczna lista jest niepełna - brak to nie sprzedaż
    assert con.execute("SELECT close FROM price_history WHERE ticker='CPD' AND date='2024-12-30'").fetchone()
    # spółka po zmianie nazwy (SANPL -> ERSTEPL): dawna nazwa prawna i skrót z archiwum łączone po ISIN
    ebp = ofe_rows[("EBP", "2025-12-31")]
    assert ebp["delta"] == 1000 and abs(ebp["value"] - 1000 * 500) < 1e-6, ebp
    assert con.execute("SELECT shares FROM holdings_snap WHERE source='OFE' AND ticker='EBP' AND date_upd='2024-12-31'"
                       ).fetchone()[0] == 2000
    # spółka wycofana z obrotu (brak na liście Biznesradar) dopisana z archiwum gpw.pl, jej sprzedaż policzona
    sho = dict(con.execute("SELECT * FROM companies WHERE isin='PLSHPR000021'").fetchone())
    assert sho["ticker"] == "SHO" and sho["short_name"] == "SHOPER" and sho["market"] == "GPW", sho
    assert sho["last_seen"] == "2024-12-30" and sho["slug"] is None, sho
    assert ofe_rows[("SHO", "2025-12-31")]["delta"] == -125000
    assert con.execute("SELECT COUNT(*) FROM companies WHERE short_name IN ('SANPL', 'ERSTEPL')").fetchone()[0] == 1
    # podział akcji 1:10: jednodniowy skok 502 -> 49,61 zł; sama luka 526 -> 41,35 (bez sesji pomiędzy) to nie split
    con.executemany("INSERT INTO price_history VALUES(?,?,?)", [("DNP", "2025-06-30", 526.0), ("DNP", "2025-12-30", 41.35)])
    assert flows.split_factor(con, "DNP", "2025-06-30", "2025-12-31") == 1
    con.executemany("INSERT INTO price_history VALUES(?,?,?)", [("DNP", "2025-07-30", 502.0), ("DNP", "2025-07-31", 49.61)])
    assert flows.split_factor(con, "DNP", "2025-06-30", "2025-12-31") == 10
    con.executemany("INSERT INTO price_history VALUES(?,?,?)", [("XYZ", "2025-03-03", 2.0), ("XYZ", "2025-03-04", 20.4)])
    assert flows.split_factor(con, "XYZ", "2025-01-01", "2025-06-30") == 0.1  # scalenie akcji 10:1

    # agregacja tygodniowa
    agg = flows.investor_flows(con, "week", start="2026-01-01")
    names = {g["investor"] for g in agg}
    assert "Tomasz Kaniowski" in names
    con.close()

    # API
    import importlib
    app_mod = importlib.import_module("app")
    cl = app_mod.app.test_client()
    rows = cl.get("/api/companies").get_json()
    pko = next(r for r in rows if r["ticker"] == "PKO")
    assert pko["sector"] == "Banki" and pko["cz"] == 13.36 and pko["div_has"]
    assert abs(pko["mcap"] - 115.84 * 1_250_000_000) < 1
    r = cl.post("/api/columns", json={"label": "Kupiłem", "type": "bool"}).get_json()
    cl.put("/api/values", json={"ticker": "PKO", "key": r["key"], "value": "true"})
    pko = next(x for x in cl.get("/api/companies").get_json() if x["ticker"] == "PKO")
    assert pko["c_kupilem"] == "true"
    cl.put("/api/settings/companies_layout", json={"layout": [{"field": "ticker", "visible": True}]})
    assert cl.get("/api/settings/companies_layout").get_json()["layout"][0]["field"] == "ticker"
    fl = cl.get("/api/flows?period=month&from=2026-01-01").get_json()
    assert any(g["period"] == "2026-10" for g in fl)
    chs = cl.get("/api/changes").get_json()
    cid = next(c["id"] for c in chs if c["source"] == "art69" and c["ticker"] == "OUT")
    upd = cl.patch(f"/api/changes/{cid}", json={"price": 3.0}).get_json()
    assert upd["value"] == -420000 and upd["price_src"] == "ręcznie"
    assert cl.get("/api/espi?days=3650&categories=art69,mar").status_code == 200
    assert cl.get("/api/company/PKO").get_json()["dividends"]
    # ocena AF ustawiona w panelu spółki = ta sama wartość co w kolumnie tabeli
    cl.put("/api/values", json={"ticker": "PKO", "key": "ocena_af", "value": "Obserwuj"})
    pc = cl.get("/api/company/PKO").get_json()
    assert pc["custom"]["ocena_af"] == "Obserwuj" and pc["af_column"]["options"] == ["Warto", "Obserwuj", "Nie warto"]
    assert next(x for x in cl.get("/api/companies").get_json() if x["ticker"] == "PKO")["c_ocena_af"] == "Obserwuj"
    assert cl.get("/api/status").get_json()["counts"]["companies"] == 7
    assert any(r["ticker"] == "SHO" for r in rows)  # wycofana spółka widoczna w widoku Spółki
    assert cl.post("/api/aliases", json={"alias_norm": out["investor_norm"], "canonical": "Hegen Invest"}).status_code == 200

    # podsumowanie sesji: struktura, "Moje spółki" z własnej kolumny Tak/Nie
    ses = cl.get(f"/api/session?min=0&watch={r['key']}").get_json()
    assert ses["date"] and set(ses["breadth"]["all"]) >= {"up", "down", "flat", "none", "median_change"}
    assert ses["watch"]["label"] == "Kupiłem" and [x["ticker"] for x in ses["watch"]["rows"]] == ["PKO"]
    assert "gainers" in ses and "holders" in ses and ses["espi"]["total"] >= 0
    # dywidendy: dzień odcięcia, wypłata jednorazowa (ponad 2x mediany innych), okno 12 mies. po dniu odcięcia
    from datetime import date as _d
    mk = lambda y, last, dps: {"year_for": y, "last_day": last, "pay_day": "", "dps": dps}  # noqa: E731
    vot = [mk("2023", "2024-09-16", 1.21), mk("2024", "2024-11-06", 0.41), mk("2024", "2025-05-28", 3.33),
           mk("2025", "2025-10-17", 1.67), mk("2025", "2025-12-12", 1.67), mk("2025", "2026-05-14", 5.0),
           mk("2025", "2026-05-14", 5.0), mk("2026", "2026-10-19", 2.5)]  # ta sama wypłata dwa razy = jedna
    dv = app_mod._dividend_split(vot, _d(2026, 10, 20), "2025-10-20", "2026-10-19")
    assert abs(dv["dps12"] - 9.17) < 1e-9 and dv["oneoff12"] == 5.0 and dv["exdiv_today"] == 2.5
    pko = [mk("2021", "2022-08-02", 1.83), mk("2023", "2024-01-23", 1.28), mk("2023", "2024-08-06", 2.59),
           mk("2024", "2025-08-01", 5.48), mk("2025", "2026-08-03", 6.14)]  # rosnąca dywidenda to nie jednorazowa
    assert app_mod._dividend_split(pko, _d(2026, 10, 20), "2025-10-20", "2026-10-19")["oneoff12"] == 0
    # Moje spółki: zakup z planem, dokupienie, częściowa sprzedaż (FIFO), wynik na tle WIG, alert poziomu wyjścia
    pko_close = next(x for x in cl.get("/api/companies").get_json() if x["ticker"] == "PKO")["price"]
    dcon = db.connect()
    dcon.executemany("INSERT OR REPLACE INTO index_ohlc VALUES('WIG',?,?,?,?,?,?)",
                     [("2026-01-02", 1, 1, 1, 100000.0, 0), (_d.today().isoformat(), 1, 1, 1, 110000.0, 0)])
    dcon.commit()
    dcon.close()
    assert cl.post("/api/positions", json={"ticker": "XXX", "qty": 1, "price": 1}).status_code == 400
    r1 = cl.post("/api/positions", json={"ticker": "pko", "opened": "2026-01-02", "qty": 100, "price": 100, "fees": 10,
                                         "thesis": "dywidenda", "stop": pko_close + 1, "target": 200,
                                         "horizon": "długi (1–5 lat)"}).get_json()
    assert r1["ok"]
    cl.post("/api/positions", json={"ticker": "PKO", "opened": "2026-03-02", "qty": 50, "price": 110})
    pf = cl.get("/api/portfolio").get_json()
    pos = pf["positions"][0]
    assert pos["ticker"] == "PKO" and pos["qty"] == 150 and abs(pos["cost"] - (10000 + 10 + 5500)) < 1e-6
    assert pos["plan"]["thesis"] == "dywidenda" and pos["weight"] == 100
    assert abs(pos["wig_pct"] - 10.0) < 1e-6  # WIG 100 000 -> 110 000 od obu zakupów
    assert any(a["kind"] == "stop" and a["level"] == "critical" for a in pf["alerts"]), pf["alerts"]
    assert cl.post("/api/positions/sell", json={"ticker": "PKO", "qty": 500, "price": 1}).status_code == 400
    assert cl.post("/api/positions/sell", json={"ticker": "PKO", "qty": 120, "price": 120, "date": "2026-10-01"}).get_json()["ok"]
    pf = cl.get("/api/portfolio").get_json()
    assert pf["positions"][0]["qty"] == 30 and pf["positions"][0]["lots"][0]["price"] == 110  # zostało 30 z drugiej partii
    assert sorted(c["qty"] for c in pf["closed"]) == [20, 100]
    assert abs(pf["totals"]["realized"] - (120 * 120 - 100 * 100 - 10 - 20 * 110)) < 1e-6
    pid1 = pf["portfolios"][0]["id"]
    assert pf["portfolios"][0]["name"] == "Mój portfel"  # pierwszy zakup bez portfela tworzy domyślny
    cl.put(f"/api/plans/{pid1}/PKO", json={"stop": "", "target": 150})
    pl = cl.get("/api/portfolio").get_json()["positions"][0]["plan"]
    assert pl["stop"] is None and pl["target"] == 150 and pl["thesis"] == "dywidenda"
    # drugi portfel (np. IKE): osobne wyniki, plan i sprzedaż w obrębie portfela, łączne zestawienie
    assert cl.post("/api/portfolios", json={"name": "Mój portfel"}).status_code == 400  # nazwa zajęta
    pid2 = cl.post("/api/portfolios", json={"name": "IKE"}).get_json()["id"]
    cl.post("/api/positions", json={"portfolio_id": pid2, "ticker": "PKO", "opened": "2026-02-02", "qty": 10, "price": 90,
                                    "thesis": "IKE - długo"})
    both = cl.get("/api/portfolio").get_json()
    assert sorted((p["portfolio"], p["qty"]) for p in both["positions"]) == [("IKE", 10), ("Mój portfel", 30)]
    assert {b["name"]: b["n"] for b in both["portfolios"]} == {"Mój portfel": 1, "IKE": 1}
    rows_c = {x["ticker"]: x for x in cl.get("/api/companies").get_json()}
    assert rows_c["PKO"]["pf"] == "Mój portfel, IKE" and rows_c["PKO"]["pf_qty"] == 40 and rows_c["CPD"]["pf"] is None
    assert abs(sum(b["share"] for b in both["portfolios"]) - 100) < 1e-6
    ike = cl.get(f"/api/portfolio?pid={pid2}").get_json()
    assert [p["qty"] for p in ike["positions"]] == [10] and ike["positions"][0]["plan"]["thesis"] == "IKE - długo"
    assert ike["positions"][0]["weight"] == 100 and ike["totals"]["realized"] == 0 and not ike["closed"]
    assert cl.post("/api/positions/sell", json={"portfolio_id": pid2, "ticker": "PKO", "qty": 20, "price": 1}).status_code == 400
    assert cl.delete(f"/api/portfolios/{pid2}").status_code == 400  # niepusty
    lot2 = ike["positions"][0]["lots"][0]["id"]
    cl.patch(f"/api/positions/{lot2}", json={"portfolio_id": pid1})  # przeniesienie partii
    assert cl.get(f"/api/portfolio?pid={pid1}").get_json()["positions"][0]["qty"] == 40
    assert cl.patch(f"/api/portfolios/{pid2}", json={"name": "IKZE"}).get_json()["ok"]
    assert cl.delete(f"/api/portfolios/{pid2}").get_json()["ok"]
    assert cl.get(f"/api/session?min=0&watch=__portfolio:{pid1}").get_json()["watch"]["label"] == "Mój portfel"
    ses = cl.get("/api/session?min=0").get_json()
    assert ses["watch"]["key"] == "__portfolio" and [x["ticker"] for x in ses["watch"]["rows"]] == ["PKO"]
    assert ses["insider_sessions"] == 1 and "series" in ses
    assert cl.get("/api/session?min=0&sessions=20").get_json()["insider_sessions"] == 20
    # kontekst rynku: WIG z archiwum (2 sesje wyżej), bez historii do SMA i szerokości - bez błędów
    mk_ = cl.get("/api/market").get_json()
    wig = next(i for i in mk_["indices"] if i["key"] == "WIG")
    assert wig["value"] == 110000.0 and abs(wig["change_pct"] - 10.0) < 1e-9 and wig["sma200"] is None
    from gpwt import market as _mkt
    assert _mkt._sma([1, 2, 3, 4], 2) == 3.5 and _mkt._sma([1], 2) is None
    # C/D: słowa kluczowe ESPI, wskaźniki techniczne, sygnały krótkoterminowe w Sesji, zakładka Trendy
    kw = espi.keywords
    assert kw("XTPL SA (40/2026) Decyzja o emisji akcji serii X") == ["emisja"]
    assert kw("ARCHICOM SA (23/2026) Emisja obligacji") == [] and kw("ALTUS SA (1/2026) Wezwanie do udziału w sprawie") == []
    assert kw("ENERGY SA (43/2026) Zawarcie umowy na realizację prac") == ["umowa"]
    assert kw("V-MAX SA (9/2026) Podpisanie z firmą audytorską umowy o badanie sprawozdań") == []
    assert kw("KRUK SA (40/2026) Wstępny szacunkowy wynik finansowy za III kwartał") == ["wyniki"]
    assert kw("PKO BP (1/2026) Raport kwartalny QSr 3/2026") == []
    from gpwt import technicals
    assert technicals._sma([1, 2, 3], 2) == 2.5 and abs(technicals._ret([100, 110], 2, 121) - 21.0) < 1e-9
    ses = cl.get("/api/session?min=0").get_json()
    assert {"breakouts", "gaps", "rs_top", "rs_bottom"} <= set(ses) and "tagged" in ses["espi"]
    tr = cl.get("/api/trends?min=0&min_nc=0&trend=0").get_json()
    assert {"momentum", "sectors", "funds_buy", "funds_sell", "wig"} <= set(tr)
    co = cl.get("/api/companies").get_json()[0]
    assert {"trend", "vs200", "rs_3m", "mom", "new_high52"} <= set(co)
    # A/B: harmonogram raportów, zwołanie WZ, wezwanie, kalendarz, ostrzeżenia
    assert espi.classify("BORYSZEW SA (3/2026) Terminy publikacji raportów okresowych w 2026 roku") == "terminy"
    assert espi.classify("X SA (1/2026) Zmiana harmonogramu publikacji raportów okresowych") == "terminy"
    assert espi.classify("SYNTHAVERSE SA (39/2026) Ogłoszenie o zwołaniu Nadzwyczajnego Walnego Zgromadzenia") == "wz_zwolanie"
    rd = espi.parse_report_dates("Treść raportu: - za I kwartał 2026 roku - 14 maja 2026 roku; - za III kwartał 2026 roku - "
                                 "17 listopada 2026 roku; Raport roczny za 2025 rok - 16 kwietnia 2026 roku; raport półroczny "
                                 "za I półrocze 2026 r. w dniu 13.08.2026 r. Nie będzie raportu za IV kwartał 2025 roku.")
    assert rd == {"q1": "2026-05-14", "q3": "2026-11-17", "y": "2026-04-16", "h1": "2026-08-13"}, rd
    assert espi.parse_report_dates("Treść raportu: zmiana terminu raportu za I półrocze 2026 r. z dnia 30 września 2026 r. "
                                   "na dzień 22 września 2026 r.", "Zmiana terminu") == {"h1": "2026-09-22"}
    assert espi.parse_meeting_date("Zarząd zwołuje NWZ na dzień 24 listopada 2026 r.", "2026-10-20 10:00") == "2026-11-24"
    assert espi.parse_tender("Rozpoczęcie przyjmowania zapisów: 5.11.2026. Zakończenie przyjmowania zapisów: 4.12.2026. "
                             "Cena akcji w wezwaniu 12,50 zł") == {"start": "2026-11-05", "end": "2026-12-04", "price": 12.5}
    from gpwt import kalendarz, ostrzezenia
    ev = kalendarz.events(db.connect(), 10, start="2026-10-30")
    kinds = {e["kind"] for e in ev["events"]}
    assert {"rpp", "cpi"} <= kinds, kinds  # RPP 4.11, szybki szacunek CPI 30.10
    assert any(e["kind"] == "raport_termin" and "14" in e["date"][8:] for e in kalendarz.events(db.connect(), 5, start="2026-11-10")["events"])
    # harmonogram NewConnect z minioną datą raportu i bez raportu w komunikatach -> ostrzeżenie o opóźnieniu
    nc_t = next(r["ticker"] for r in cl.get("/api/companies").get_json() if r["market"] == "NC")
    wc = db.connect()
    wc.execute("INSERT INTO espi(id, ticker, title, ts, category, parsed, fetched) VALUES(7777, ?, 'X (1/2026) Harmonogram "
               "publikacji raportów okresowych', ?, 'terminy', ?, 1)",
               (nc_t, f"{_d.today().year}-01-10 10:00", json.dumps({"dates": {"q1": f"{_d.today().year}-01-15"}})))
    wc.commit()
    ws = ostrzezenia._compute(wc)
    assert any(w["kind"] == "raport_opozniony" for w in ws.get(nc_t, [])), ws.get(nc_t)
    assert any(e["kind"] == "raport" for e in kalendarz.events(wc, 3, start=f"{_d.today().year}-01-14")["events"])
    wc.execute("DELETE FROM espi WHERE id=7777")
    wc.commit()
    wc.close()
    assert ostrzezenia.expected_period("GPW", _d(2026, 10, 21)) == (2026, 2)
    assert ostrzezenia.expected_period("NC", _d(2026, 11, 20)) == (2026, 3)
    assert cl.get("/api/calendar?days=14").status_code == 200
    assert "warned" in cl.get("/api/session?min=0").get_json()
    assert "warnings" in cl.get("/api/companies").get_json()[0] and "events" in cl.get("/api/portfolio").get_json()
    # szybkie pobieranie w trakcie sesji
    st_q, stats_q = collect.run(quick=True)
    assert st_q == "ok" and stats_q["quotes_GPW"] == 5 and "ratio_cz_GPW" not in stats_q, stats_q
    # analizy fundamentalne: przypisanie po tickerze, po nazwie spółki, plik nieprzypisany
    from gpwt import analyses
    analyses.AF_DIR = TMP / "analyses"
    analyses.AF_DIR.mkdir()
    (analyses.AF_DIR / "PKO_Analiza_Fundamentalna.docx").write_bytes(b"x")
    (analyses.AF_DIR / "Outdoorzy_analiza_2026-09-25.pdf").write_bytes(b"%PDF-1.4 x")
    (analyses.AF_DIR / "notatki_rozne.txt").write_text("y")
    rows = {r["ticker"]: r for r in cl.get("/api/companies").get_json()}
    assert rows["PKO"]["af_count"] == 1 and rows["OUT"]["af_date"] == "2026-09-25" and rows["CPD"]["af_date"] is None
    afs = cl.get("/api/analyses").get_json()
    assert afs["assigned"] == 2 and [a["name"] for a in afs["unassigned"]] == ["notatki_rozne.txt"], afs
    assert cl.get("/api/company/OUT").get_json()["analyses"][0]["file"] == "Outdoorzy_analiza_2026-09-25.pdf"
    assert cl.get("/af/Outdoorzy_analiza_2026-09-25.pdf").data.startswith(b"%PDF")
    assert cl.get("/af/../test.sqlite").status_code == 404
    assert any(c["key"] == "ocena_af" for c in cl.get("/api/columns").get_json())
    assert "cmf63" in rows["PKO"] and isinstance(cl.get("/api/company/PKO").get_json()["ohlc"], list)
    c2 = db.connect()
    assert c2.execute("SELECT COUNT(*) FROM ohlc WHERE ticker='PKO'").fetchone()[0] >= 1  # z dziennych notowań
    c2.close()

    # logowanie: bez hasła w konfiguracji dostęp lokalny jak dotąd, z hasłem każde zapytanie wymaga logowania
    import base64
    config.AUTH_PASSWORD = "tajne"
    try:
        assert cl.get("/").status_code == 401
        assert cl.post("/api/collect", json={}).status_code == 401
        bad = base64.b64encode(b"gpw:zle").decode()
        assert cl.get("/api/status", headers={"Authorization": f"Basic {bad}"}).status_code == 401
        good = base64.b64encode(b"gpw:tajne").decode()
        assert cl.get("/api/status", headers={"Authorization": f"Basic {good}"}).status_code == 200
    finally:
        config.AUTH_PASSWORD = ""
    assert cl.get("/api/status").status_code == 200
    # tryb sieci domowej bez hasła: tylko adresy prywatne/lokalne
    config.LAN_NO_PASSWORD = True
    try:
        assert cl.get("/api/status", environ_base={"REMOTE_ADDR": "192.168.1.15"}).status_code == 200
        assert cl.get("/api/status", environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code == 200
        assert cl.get("/api/status", environ_base={"REMOTE_ADDR": "8.8.8.8"}).status_code == 403
        assert cl.post("/api/collect", json={}, environ_base={"REMOTE_ADDR": "83.10.20.30"}).status_code == 403
    finally:
        config.LAN_NO_PASSWORD = False
    print("OK – potok i API działają")


if __name__ == "__main__":
    test_pipeline()
