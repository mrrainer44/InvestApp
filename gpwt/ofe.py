"""Historia portfeli OFE z oficjalnych struktur aktywów: rocznej (31.12, pełna lista spółek)
i półrocznej (30.06, tylko większe pozycje). Pliki (PDF, XLSX, XLS - każde PTE ma inny układ)
pobieramy z archiwum dokumenty.analizy.pl.

Struktury podają wartość pozycji w zł, a nie liczbę akcji. Liczbę akcji szacujemy jako
wartość / kurs zamknięcia z ostatniej sesji przed datą wyceny (archiwum notowań gpw.pl).
Zrzuty trafiają do holdings_snap (source='OFE'); flows.rebuild_changes liczy z nich zmiany.

Lista notowań Biznesradar ma tylko spółki notowane dziś - pod dzisiejszymi nazwami. Archiwum gpw.pl
(eksport XLS z ISIN) pokazuje skład rynku z dnia wyceny: spółki po zmianie nazwy (CCC -> MODIVO,
SANPL -> ERSTEPL) łączymy po ISIN z istniejącym tickerem, a wycofane z obrotu (Shoper, Grenevia,
Comarch...) dopisujemy do companies, żeby było do czego przypisać pozycje i ich sprzedaż.
"""
import difflib
import io
import json
import logging
import re
from datetime import date, timedelta

from . import http
from .util import ascii_fold, norm_company, norm_investor

log = logging.getLogger("gpwt.ofe")

# kod funduszu w archiwum analizy.pl -> nazwa jak w akcjonariacie Biznesradar (żeby łączyć inwestora)
FUNDS = {
    "EALL1": "OFE Allianz Polska",
    "EZUR1": "OFE Generali",
    "ENNE1": "OFE Nationale Nederlanden",
    "EBAN1": "OFE PKO BP Bankowy",
    "EPZU1": "OFE PZU Złota Jesień",
    "EWIN1": "OFE UNIQA",
    "EORZ1": "OFE Vienna",
    "EPCZ1": "OFE Pocztylion Arka",
}
DOC_URL = "https://dokumenty.analizy.pl/pobierz/fe/{code}/{kind}/{date}"
ARCHIVE_URL = "https://www.gpw.pl/archiwum-notowan?fetch=1&type=10&instrument=&date={d}"

# dawne nazwy prawne spółek po zmianie nazwy (ISIN -> nazwy z dokumentów PTE); skrót giełdowy
# z dnia wyceny dochodzi automatycznie z archiwum gpw.pl
OLD_NAMES = {
    "PLBZ00000044": ["Santander Bank Polska"],          # dziś Erste Bank Polska (EBP)
    "PLFAMUR00012": ["Fabryka Maszyn Famur", "Famur"],  # Grenevia
    "PLKRINK00014": ["Kredyt Inkaso"],
    "PLMRCOR00016": ["Mercor"],                         # dziś MCR
}
# tickery spółek wycofanych z obrotu (Biznesradar i gpw.pl już ich nie pokazują); pozostałe
# wycofane dostają ticker = skrót z archiwum gpw.pl
DELISTED_TICKERS = {
    "PLSHPR000021": "SHO",   # Shoper
    "PLFAMUR00012": "GEA",   # Grenevia
    "PLCOMAR00012": "CMR",   # Comarch
    "PLKRINK00014": "KRI",   # Kredyt Inkaso
}

# nazwy prawne / skróty z dokumentów PTE, których nie da się dopasować automatycznie
ALIASES = {
    "powszechna kasa oszczednosci bank polski": "PKO",
    "bank polska kasa opieki": "PEO",
    "powszechny zaklad ubezpieczen": "PZU",
    "pge polska energetyczna": "PGE",
    "kghm polska miedz": "KGH",
    "gielda papierow wartosciowych w warszawie": "GPW",
    "gpw": "GPW",
    "pko bank polski": "PKO",
    "globe trade centre": "GTC",
    "zespol elektrowni patnow adamow konin": "ZEP",
    "mercor": "MCR",
    "bank ochrony srodowiska": "BOS",
    "wp": "WPL",
    "vigo system": "VGO",
    "synektit": "SNT",
    "sanok rc": "SNK",
    "quercus towarzystwo funduszy inwestycyjnych": "QRS",
    "mol rt": "MOL",
    "mol hungarian oil gas": "MOL",
    "mol hungarian oil and gas": "MOL",
    "mol hungarian oil and gas public limited company": "MOL",
    "mol magyar olaj es gazipari rt": "MOL",
    "mol magyar olaj es gazipari reszvenytarsasag": "MOL",
}

NUM = r"(?<![\d.,])-?(?:\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,]\d+)?%?"
_TAIL_NUM = re.compile(rf"\s*({NUM})\s*$")
_INDEX = re.compile(r"^\s*(?:\d+\.\d*|\d+(?:\.\d+)?\s*\|)\s*")
_SECTION = "akcjespoleknotowanychnarynkuregulowanymnaterytorium"
_SECTION_ALT = "akcjespoleknotowanenarynkuregulowanymnaterytorium"
# początek kolejnej kategorii lokat - pełne frazy, bo nazwy spółek bywają podobne ("Creotech Instruments")
_STOP = ("prawapoboru", "ofertypublicznej", "wpanstwachinnych", "certyfikatyinwestycyjne", "tytulyuczestnictwa",
         "jednostkiuczestnictwa", "obligacje", "depozyty", "listyzastawne", "dluznepapiery", "papierywartosciowe",
         "instrumentypochodne", "razem", "sumaaktywow", "naleznosci", "srodkipieniezne", "art141")
_SKIP = ("doakcji", "kategoria", "emitent", "wartosc", "udzial")


def _fold(s):
    return re.sub(r"[^a-z0-9]", "", ascii_fold(s).lower())


def to_float(s):
    s = s.replace("%", "").replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s.replace(",", "."))


def sheet_rows(data):
    """Arkusz XLSX / XLS -> lista wierszy (wszystkie zakładki); [] gdy to nie arkusz (np. strona HTML)."""
    rows = []
    if data[:4] == b"PK\x03\x04":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows += [list(r) for r in ws.iter_rows(values_only=True)]
    elif data[:4] == b"\xd0\xcf\x11\xe0":
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        for sh in wb.sheets():
            rows += [sh.row_values(i) for i in range(sh.nrows)]
    return rows


def doc_lines(data):
    """Plik struktury (PDF / XLSX / XLS) -> lista linii tekstu; komórki arkusza rozdzielone ' | '."""
    if data[:4] == b"%PDF":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages).splitlines()
    out = []
    for r in sheet_rows(data):
        cells = [str(c).strip() for c in r if c is not None and str(c).strip()]
        if cells:
            out.append(" | ".join(cells))
    return out


def split_position(line):
    """'2.10 AB SA 155 627 429,79 0,40' -> ('AB SA', 155627429.79); None, jeśli to nie pozycja."""
    rest, nums = line.replace("|", " "), []
    while len(nums) < 3:
        m = _TAIL_NUM.search(rest)
        if not m:
            break
        nums.append(m.group(1))
        rest = rest[:m.start()]
    if len(nums) < 2:
        return None
    vals = [to_float(n) for n in nums]
    value = max(vals)
    name = _INDEX.sub("", rest).strip(" ;:-–")
    if value < 1000 or min(abs(v) for v in vals) > 100 or not re.search(r"[A-Za-zĄ-ż]{2}", name):
        return None
    return name, value


def parse_positions(lines):
    """Pozycje z sekcji 'Akcje spółek notowanych na rynku regulowanym na terytorium RP'."""
    start = None
    for i in range(len(lines)):
        window = _fold(" ".join(lines[i:i + 2]))
        if (_SECTION in window or _SECTION_ALT in window) and "akcjespolek" in _fold(lines[i]):
            start = i
            break
    if start is None:
        return []
    out, pending, started = [], "", False
    for line in lines[start:]:
        pos = split_position(line)
        if pos:
            name, value = pos
            if any(k in _fold(name) for k in _STOP):
                if started:
                    break
                continue  # wiersz nagłówka sekcji z sumą
            if any(k in _fold(name) for k in _SKIP):
                continue
            started = True
            out.append((name, value, pending))
            pending = ""
            continue
        f = _fold(line)
        if started and any(k in f for k in _STOP):
            break
        pending = line.strip() if started and f and not f.isdigit() else ""
    return out


_COMMON = {"polska", "polski", "bank", "spolka", "akcyjna", "group", "grupa", "holding"}


def _key(name):
    k = norm_company(name or "")
    if k:
        return k
    # norm_company zjada m.in. całą nazwę "AB S.A." - zostaje sam rdzeń bez formy prawnej
    base = re.sub(r"(?i)[\s,]+(s\.?\s?a\.?|spółka akcyjna)\s*$", "", (name or "").strip())
    return re.sub(r"[^a-z0-9]", "", ascii_fold(base).lower())


class Matcher:
    def __init__(self, con):
        self.by_norm, self.names_of, self.long_keys = {}, {}, {}
        for r in con.execute("SELECT ticker, full_name, short_name FROM companies"):
            self._add(r["full_name"], r["ticker"], long=True)
            for n in (r["short_name"], r["ticker"]):
                self._add(n, r["ticker"])
        # pełne nazwy prawne z archiwum gpw.pl / newconnect.pl (ticker dopasowany po ISIN)
        for r in con.execute("SELECT DISTINCT company, ticker FROM espi WHERE id >= 50000000 AND ticker IS NOT NULL"):
            self._add(r["company"], r["ticker"], long=True)
        tickers = {r["ticker"] for r in con.execute("SELECT ticker FROM companies")}
        for k, t in ALIASES.items():
            if t in tickers:
                self.by_norm[k] = t
                self.long_keys[k] = t
                self.names_of.setdefault(t, set()).add(k)
        self.keys = list(self.by_norm)
        self.flat = {}
        for k, t in self.by_norm.items():
            self.flat.setdefault(k.replace(" ", ""), t)

    def _add(self, name, ticker, long=False):
        k = _key(name)
        if k:
            self.by_norm.setdefault(k, ticker)
            self.names_of.setdefault(ticker, set()).add(k)
            if long:
                self.long_keys.setdefault(k, ticker)

    def add_session_names(self, names):
        """Nazwy z archiwum gpw.pl z dnia wyceny ({skrót: ticker}) i dawne nazwy prawne spod OLD_NAMES."""
        for name, (ticker, long) in names.items():
            self._add(name, ticker, long)
        self.keys = list(self.by_norm)
        for k, t in self.by_norm.items():
            self.flat.setdefault(k.replace(" ", ""), t)

    def match(self, name):
        k = _key(name)
        if not k:
            return None
        if k in self.by_norm:
            return self.by_norm[k]
        if k.replace(" ", "") in self.flat:
            return self.flat[k.replace(" ", "")]
        # pełna nazwa (min. 4 litery) w całości zawarta w nazwie z dokumentu, np. "unicredit" w "unicredit s p a";
        # bez skrótów giełdowych ("SANTANDER" = Banco Santander, a nie Santander Bank Polska);
        # przy kilku spółkach wygrywa najdłuższy klucz, remis = brak dopasowania
        words = set(k.split())
        hits = {}
        for key, t in self.long_keys.items():
            kw = set(key.split())
            if len(key.replace(" ", "")) >= 4 and kw <= words:
                hits[t] = max(hits.get(t, 0), len(key))
        if hits:
            best = max(hits.values())
            winners = [t for t, n in hits.items() if n == best]
            if len(winners) == 1:
                return winners[0]
        close = difflib.get_close_matches(k, self.keys, n=1, cutoff=0.88)
        return self.by_norm[close[0]] if close else None

    def may_be(self, ticker, names):
        """Czy któraś z niedopasowanych nazw może być tą spółką (wspólne słowo min. 4 litery)?"""
        own = {w for n in self.names_of.get(ticker, ()) for w in n.split() if len(w) >= 4} - _COMMON
        return any(own & {w for w in _key(n).split() if len(w) >= 4} for n in names)


def parse_session(data):
    """Eksport XLS archiwum notowań gpw.pl -> [{name, isin, close}]; [] w dzień bez sesji (strona HTML)."""
    rows = sheet_rows(data or b"")
    if not rows:
        return []
    hdr = [ascii_fold(str(h or "")).lower() for h in rows[0]]
    try:
        iname, iisin = hdr.index("nazwa"), hdr.index("isin")
        iclose = next(i for i, h in enumerate(hdr) if h.startswith("kurs zamkni"))
    except (ValueError, StopIteration):
        return []
    out = []
    for r in rows[1:]:
        if len(r) <= max(iname, iisin, iclose) or not r[iname] or r[iclose] in (None, ""):
            continue
        close = r[iclose] if isinstance(r[iclose], (int, float)) else to_float(str(r[iclose]))
        out.append({"name": str(r[iname]).strip(), "isin": str(r[iisin] or "").strip() or None, "close": close})
    return out


def resolve_session(con, rows, iso):
    """Wiersze archiwum gpw.pl -> {skrót: ticker}. Spółkę łączymy po ISIN, potem po skrócie (tylko gdy ISIN
    się nie kłóci); spółkę spoza companies (wycofaną z obrotu) dopisujemy."""
    by_isin, by_short, tickers = {}, {}, set()
    for r in con.execute("SELECT ticker, short_name, isin FROM companies"):
        tickers.add(r["ticker"])
        if r["isin"]:
            by_isin.setdefault(r["isin"], r["ticker"])
        by_short.setdefault(r["short_name"], (r["ticker"], r["isin"]))
    out = {}
    for row in rows:
        name, isin = row["name"], row["isin"]
        t = by_isin.get(isin)
        if not t and name in by_short and by_short[name][1] in (None, isin):
            t = by_short[name][0]
            if isin and not by_short[name][1]:
                con.execute("UPDATE companies SET isin=? WHERE ticker=?", (isin, t))
        if not t:
            t = DELISTED_TICKERS.get(isin) or name
            if t in tickers:
                t = f"{name}-W"
            if t in tickers:
                continue
            con.execute("INSERT INTO companies(ticker, short_name, market, isin, last_seen) VALUES(?,?,?,?,?)",
                        (t, name, "GPW", isin, iso))
            log.info("      dopisuję spółkę spoza listy Biznesradar: %s (%s, %s)", t, name, isin)
            tickers.add(t)
            by_isin[isin] = t
        else:
            con.execute("UPDATE companies SET last_seen=? WHERE ticker=? AND slug IS NULL "
                        "AND (last_seen IS NULL OR last_seen<?)", (iso, t, iso))
        out[name] = t
    return out


def session_prices(con, d):
    """Kursy zamknięcia wszystkich spółek GPW z ostatniej sesji <= d
    -> (data sesji, {ticker: kurs}, {nazwa: (ticker, pełna nazwa?)} do Matcher.add_session_names)."""
    day = date.fromisoformat(d)
    for back in range(8):
        dd = day - timedelta(days=back)
        if dd.weekday() >= 5:
            continue
        rows = parse_session(http.get(ARCHIVE_URL.format(d=dd.strftime("%d-%m-%Y")), binary=True))
        if not rows:
            continue
        iso = dd.isoformat()
        tick = resolve_session(con, rows, iso)
        prices, names = {}, {}
        for row in rows:
            t = tick.get(row["name"])
            if not t:
                continue
            prices[t] = row["close"]
            names[row["name"]] = (t, False)
            for old in OLD_NAMES.get(row["isin"], ()):
                names[old] = (t, True)
        con.executemany("INSERT OR IGNORE INTO price_history VALUES(?,?,?)",
                        [(t, iso, p) for t, p in prices.items()])
        con.commit()  # nie trzymamy blokady zapisu bazy w trakcie pobierania plików struktur
        return iso, prices, names
    return None, {}, {}


def ensure_daily_prices(con):
    """Dla spółek, których kurs między kolejnymi strukturami zmienił się >= 1,8 raza, dociąga dzienne kursy
    z Biznesradar - flows.split_factor rozpozna po nich podział akcji (struktury podają tylko wartość)."""
    from . import biznesradar as br
    from .flows import price_on
    pairs = {}
    rows = con.execute("SELECT DISTINCT ticker, date_upd FROM holdings_snap WHERE source='OFE' ORDER BY ticker, date_upd")
    by_t = {}
    for r in rows:
        by_t.setdefault(r["ticker"], []).append(r["date_upd"])
    for t, ds in by_t.items():
        for d1, d2 in zip(ds, ds[1:]):
            p1, p2 = price_on(con, t, d1), price_on(con, t, d2)
            if p1 and p2 and not (1 / 1.8 < p1 / p2 < 1.8):
                pairs.setdefault(t, []).append((d1, d2))
    fetched = 0
    for t, ps in pairs.items():
        d1 = min(a for a, _ in ps)
        d2 = max(b for _, b in ps)
        have = con.execute("SELECT COUNT(*) FROM price_history WHERE ticker=? AND date>=? AND date<=?",
                           (t, d1, d2)).fetchone()[0]
        if have >= 0.6 * (date.fromisoformat(d2) - date.fromisoformat(d1)).days * 5 / 7:
            continue
        slug = con.execute("SELECT slug FROM companies WHERE ticker=?", (t,)).fetchone()
        if not slug or not slug["slug"]:
            continue
        for page in range(1, 30):
            hist = br.fetch_price_history(slug["slug"], page)
            if not hist:
                break
            con.executemany("INSERT OR IGNORE INTO price_history VALUES(?,?,?)", [(t, d, v) for d, v in hist])
            con.commit()
            if min(d for d, _ in hist) <= d1:
                break
        fetched += 1
    return fetched


def report_dates(since, today=None):
    today = today or date.today()
    out = []
    for y in range(int(since[:4]), today.year + 1):
        for kind, d in (("RP", f"{y}-06-30"), ("RR", f"{y}-12-31")):
            if since <= d <= today.isoformat():
                out.append((kind, d))
    return out


def import_doc(con, code, kind, d, data, prices, matcher, today):
    holder = FUNDS[code]
    hnorm = norm_investor(holder)
    positions = parse_positions(doc_lines(data))
    shares_out = {r["ticker"]: r["shares"] for r in con.execute("SELECT ticker, shares FROM companies")}
    held, unmatched, unpriced = {}, [], []
    for name, value, pending in positions:
        ticker = matcher.match(name) or (matcher.match(f"{pending} {name}") if pending else None)
        if not ticker:
            unmatched.append(name)
            continue
        if ticker not in prices:
            unpriced.append(name)
            continue
        held[ticker] = held.get(ticker, 0) + value / prices[ticker]
    for ticker, sh in held.items():
        sh = round(sh)
        pct = sh / shares_out[ticker] * 100 if shares_out.get(ticker) else None
        con.execute("INSERT OR REPLACE INTO holdings_snap VALUES(?,?,?,?,?,?,?,?)",
                    (ticker, holder, hnorm, sh, pct, d, "OFE", today))
    zeroed = 0
    if kind == "RR":  # roczna = pełna lista: brak spółki oznacza sprzedaż całości
        for r in con.execute(
                "SELECT h.ticker FROM holdings_snap h JOIN (SELECT ticker, MAX(date_upd) m FROM holdings_snap "
                "WHERE source='OFE' AND holder_norm=? AND date_upd<? GROUP BY ticker) x "
                "ON h.ticker=x.ticker AND h.date_upd=x.m WHERE h.source='OFE' AND h.holder_norm=? AND h.shares>0",
                (hnorm, d, hnorm)).fetchall():
            # nie zerujemy, jeśli spółka mogła się ukryć pod nazwą, której nie umieliśmy dopasować
            if r["ticker"] not in held and not matcher.may_be(r["ticker"], unmatched + unpriced):
                con.execute("INSERT OR REPLACE INTO holdings_snap VALUES(?,?,?,?,?,?,?,?)",
                            (r["ticker"], holder, hnorm, 0, 0.0, d, "OFE", today))
                zeroed += 1
    con.commit()
    return {"positions": len(positions), "stored": len(held), "zeroed": zeroed,
            "unmatched": unmatched, "unpriced": unpriced}


def collect(con, stats, since="2024-12-31"):
    done = set(json.loads((con.execute("SELECT value FROM settings WHERE key='ofe_docs'").fetchone() or ["[]"])[0]))
    matcher = Matcher(con)
    today = date.today().isoformat()
    imported, problems = 0, {}
    n_companies = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    for kind, d in report_dates(since):
        todo = [c for c in FUNDS if f"{c}/{kind}/{d}" not in done]
        if not todo:
            continue
        session, prices, names = session_prices(con, d)
        if not prices:
            log.warning("Brak kursów z sesji przed %s - pomijam struktury OFE z tej daty", d)
            continue
        matcher.add_session_names(names)
        log.info("[OFE] Struktury %s na %s (kursy z sesji %s): %s funduszy", kind, d, session, len(todo))
        for code in todo:
            data = http.get(DOC_URL.format(code=code, kind=kind, date=d), binary=True)
            if not data:
                continue  # jeszcze nieopublikowana
            res = import_doc(con, code, kind, d, data, prices, matcher, today)
            log.info("      %s: %s pozycji, zapisane %s, sprzedane w całości %s, niedopasowane %s",
                     FUNDS[code], res["positions"], res["stored"], res["zeroed"], len(res["unmatched"]))
            if res["unmatched"] or res["unpriced"]:
                problems[f"{code}/{kind}/{d}"] = {"niedopasowane": res["unmatched"], "bez kursu": res["unpriced"]}
            if res["stored"]:
                done.add(f"{code}/{kind}/{d}")
                imported += 1
    con.execute("INSERT OR REPLACE INTO settings VALUES('ofe_docs', ?)", (json.dumps(sorted(done)),))
    con.commit()
    stats["ofe_docs"] = imported
    stats["ofe_new_companies"] = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0] - n_companies
    stats["ofe_split_checks"] = ensure_daily_prices(con)
    if problems:
        stats["ofe_problems"] = problems
