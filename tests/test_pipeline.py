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
            ("CPD", "CELTIC", "CPD", "CPD", "0,700", "-5,41%", "23 770", "16 921")]
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


def akc_page(rows, shares="1 250 000 000"):
    tr = "".join(f"<tr><td>{h}</td><td>{p} %</td><td>{s}</td><td>1</td><td>{p} %</td><td>{s}</td><td>{d}</td></tr>"
                 for h, p, s, d in rows)
    return ('<table class="profileSummary"><tr><th>ISIN:</th><td>PLPKO0000016</td></tr>'
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


def fake_get(path, binary=False, tries=3):
    p = path.replace(config.BASE, "")
    if "/ajaxindex.php?" in p:
        if "offset=0&" not in p:
            return ""
        return GPW_LIST if p.startswith("https://www.gpw.pl/") else NC_LIST
    if p == "https://www.gpw.pl/komunikat?geru_id=480001":
        return GPW_DETAIL
    if binary and p == "https://www.gpw.pl/attachment/zal01_Zakup.pdf,20260820_101530_1,20260820":
        return (FIX / "mar.pdf").read_bytes()
    if binary:
        name = {"/pdf/hegen.pdf": "art69_hegen.txt", "/pdf/bt.pdf": "art69_bt.txt"}.get(p)
        if name:
            return ("TXT:" + (FIX / name).read_text(encoding="utf-8")).encode()
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
        return akc_page([], "26 150 000")
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
        return article("<p>zawiadomienia</p>", ["/pdf/bt.pdf"])
    if p.startswith("/notowania-historyczne/"):
        return HIST
    return "<html></html>"


def fake_pdf_text(data):
    if data.startswith(b"TXT:"):
        return data[4:].decode()
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

    st, stats = collect.run(weekly=True)
    assert st == "ok", stats
    assert stats["quotes_GPW"] == 4 and stats["quotes_NC"] == 1

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
    assert '"forms": [{' in g["parsed"], g["parsed"]
    nc = con.execute("SELECT * FROM espi WHERE id=?", (60_000_000 + 230001,)).fetchone()
    assert nc["ticker"] == "TBT" and nc["category"] == "other"
    assert con.execute("SELECT 1 FROM changes WHERE source='mar' AND espi_id=?",
                       ((50_000_000 + 480001) * 10,)).fetchone()

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
    assert cl.get("/api/status").get_json()["counts"]["companies"] == 5
    assert cl.post("/api/aliases", json={"alias_norm": out["investor_norm"], "canonical": "Hegen Invest"}).status_code == 200
    print("OK – potok i API działają")


if __name__ == "__main__":
    test_pipeline()
