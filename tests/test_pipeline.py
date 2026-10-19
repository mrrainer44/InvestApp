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
        '<tr><td>06.10.2026</td><td>1</td><td>1</td><td>1</td><td>1.15</td><td>1</td><td>1</td></tr></tbody></table>')

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
    assert out["delta"] == -140000 and out["date"] == "2026-10-12"
    assert abs(out["price"] - 3.05) < 1e-9 and abs(out["value"] - (-140000 * 3.05)) < 1e-6
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
    assert cl.get("/api/status").get_json()["counts"]["companies"] == 7
    assert any(r["ticker"] == "SHO" for r in rows)  # wycofana spółka widoczna w widoku Spółki
    assert cl.post("/api/aliases", json={"alias_norm": out["investor_norm"], "canonical": "Hegen Invest"}).status_code == 200
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
