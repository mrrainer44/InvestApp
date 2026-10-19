"""Parsery stron Biznesradar. Funkcje parse_* przyjmują HTML (testowalne offline),
funkcje fetch_* pobierają i parsują."""
import re

from bs4 import BeautifulSoup

from . import http
from .util import any_date, int_pl, num, short_date

PROFILE_RE = re.compile(r"^\s*([0-9A-Z]{2,6})\s*(?:\(([^)]+)\))?\s*$")


def _soup(html):
    return BeautifulSoup(html, "lxml")


def _main_table(soup):
    for t in soup.find_all("table"):
        th = t.find("th")
        if th and th.get_text(strip=True).startswith("Profil"):
            return t
    return None


def _profile_cell(td):
    a = td.find("a")
    if not a:
        return None
    m = PROFILE_RE.match(a.get_text(" ", strip=True))
    if not m:
        return None
    href = a.get("href", "")
    slug = href.rstrip("/").split("/")[-1] if href else None
    return {
        "ticker": m.group(1),
        "short_name": m.group(2) or m.group(1),
        "full_name": (a.get("title") or "").replace("&amp;", "&"),
        "slug": slug,
    }


def parse_profile_table(html):
    """Wspólny parser tabel z kolumną 'Profil'. Zwraca (nagłówki, lista wierszy)."""
    soup = _soup(html)
    t = _main_table(soup)
    if t is None:
        return [], []
    # nagłówki bywają w <tr> albo bezpośrednio w <thead> (bez <tr>) - bierzemy pierwszy wiersz z <th>
    head = next((tr for tr in t.find_all("tr") if tr.find("th")), None) or t.find("thead") or t
    headers = [th.get_text(" ", strip=True) for th in head.find_all("th")]
    out = []
    for tr in t.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        prof = _profile_cell(tds[0])
        if not prof:
            continue
        prof["cells"] = [td.get_text(" ", strip=True) for td in tds]
        out.append(prof)
    return headers, out


def _col(headers, *names):
    for i, h in enumerate(headers):
        hl = h.lower().replace("\xa0", " ")
        if any(hl == n or hl.startswith(n) for n in names):
            return i
    return None


def parse_quotes(html):
    h, rows = parse_profile_table(html)
    ik, ich, iv, io = _col(h, "kurs"), _col(h, "zmiana %"), _col(h, "wolumen"), _col(h, "obrót")
    iop, imin, imax = _col(h, "otw."), _col(h, "min."), _col(h, "max.")
    res = []
    for r in rows:
        c = r["cells"]
        res.append({**{k: r[k] for k in ("ticker", "short_name", "full_name", "slug")},
                    "close": num(c[ik]) if ik is not None else None,
                    "change_pct": num(c[ich]) if ich is not None else None,
                    "volume": num(c[iv]) if iv is not None else None,
                    "turnover": num(c[io]) if io is not None else None,
                    "open": num(c[iop]) if iop is not None else None,
                    "low": num(c[imin]) if imin is not None else None,
                    "high": num(c[imax]) if imax is not None else None,
                    "time": c[1] if len(c) > 1 else None})
    return res


def parse_returns(html):
    h, rows = parse_profile_table(html)
    keys = {"1t": "r1w", "1m": "r1m", "3m": "r3m", "6m": "r6m", "ytd": "ytd",
            "12m": "r12m", "24m": "r24m", "36m": "r36m"}
    idx = {v: _col(h, k) for k, v in keys.items()}
    return [{"ticker": r["ticker"], **{k: (num(r["cells"][i]) if i is not None else None)
                                       for k, i in idx.items()}} for r in rows]


def parse_ratio(html):
    """Lista wskaźnika: Profil | Raport | <wartość> | r/r | k/k"""
    h, rows = parse_profile_table(html)
    return [{"ticker": r["ticker"], "report": r["cells"][1] if len(r["cells"]) > 1 else None,
             "value": num(r["cells"][2]) if len(r["cells"]) > 2 else None} for r in rows]


def parse_dividends(html):
    h, rows = parse_profile_table(html)
    i = {k: _col(h, n) for k, n in [("year_for", "dywidenda za rok"), ("wza", "data wza"),
                                    ("last_day", "ostatnie notowanie"), ("pay_day", "dzień wypłaty"),
                                    ("dps", "dywidenda na akcję"), ("status", "status")]}
    out = []
    for r in rows:
        c = r["cells"]
        g = lambda k: c[i[k]] if i[k] is not None and i[k] < len(c) else None  # noqa: E731
        out.append({"ticker": r["ticker"], "year_for": g("year_for"),
                    "wza": short_date(g("wza")), "last_day": short_date(g("last_day")),
                    "pay_day": short_date(g("pay_day")), "dps": num(g("dps")),
                    "status": (g("status") or "").strip() or None})
    return out


def parse_company_page(html):
    """Strona /akcjonariat/<slug>: tabela akcjonariuszy + ramka 'Informacje'."""
    soup = _soup(html)
    info = {}
    for t in soup.find_all("table"):
        if "ISIN" in t.get_text():
            for tr in t.find_all("tr"):
                th, td = tr.find("th"), tr.find("td")
                if th and td:
                    info[th.get_text(strip=True).rstrip(":").lower()] = td.get_text(" ", strip=True)
            break
    holders = []
    for t in soup.find_all("table"):
        first = t.find("tr")
        if not first or "Akcjonariusz" not in first.get_text():
            continue
        hdr = [x.get_text(strip=True).lower() for x in first.find_all(["th", "td"])]
        for tr in t.find_all("tr")[1:]:
            if "summary" in (tr.get("class") or []):
                continue
            cells = [x.get_text(" ", strip=True) for x in tr.find_all(["td", "th"])]
            if len(cells) < len(hdr) or cells[0].lower() == "razem":
                continue
            row = dict(zip(hdr, cells))
            holders.append({
                "holder": row.get("akcjonariusz"),
                "pct": num(row.get("udział")),
                "shares": int_pl(row.get("liczba akcji")) or num(row.get("liczba akcji")),
                "date_upd": any_date(row.get("data aktualizacji")),
            })
    return {
        "isin": info.get("isin"),
        "shares": int_pl(info.get("liczba akcji")) or num(info.get("liczba akcji")),
        "market_cap": num(info.get("kapitalizacja")),
        "sector": info.get("branża"),
        "holders": holders,
    }


def parse_espi_list(html):
    soup = _soup(html)
    out = []
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=re.compile(r"/a/\d+"))
        if not a:
            continue
        m = re.search(r"/a/(\d+)", a["href"])
        box = h3.parent
        t = box.find(class_="time")
        ts = t.get_text(strip=True) if t else None
        if not ts or not re.match(r"\d{4}-\d{2}-\d{2}", ts):
            continue  # sekcje "Najczęściej czytane" itp.
        out.append({"id": int(m.group(1)), "title": a.get_text(" ", strip=True),
                    "url": a["href"], "ts": ts.replace(",", "")})
    # deduplikacja z zachowaniem kolejności
    seen, res = set(), []
    for x in out:
        if x["id"] not in seen:
            seen.add(x["id"])
            res.append(x)
    return res


def parse_article(html):
    soup = _soup(html)
    art = soup.find("article") or soup
    body = art.find(class_="article__body")
    text = body.get_text("\n", strip=True) if body else ""
    pdfs = [a["href"] for a in art.select("ul.article__files a[href]") if a["href"].lower().endswith(".pdf")]
    tm = art.find("time")
    return {"text": text, "pdfs": pdfs, "ts": tm.get_text(strip=True).replace(",", "") if tm else None}


def parse_price_history(html):
    """Archiwum notowań: tabela z kolumnami Data ... Zamknięcie."""
    soup = _soup(html)
    for t in soup.find_all("table"):
        first = t.find("tr")
        if not first:
            continue
        hdr = [x.get_text(strip=True).lower() for x in first.find_all(["th", "td"])]
        if "data" in hdr and any(h.startswith("zamkn") for h in hdr):
            idate = hdr.index("data")
            iclose = next(i for i, h in enumerate(hdr) if h.startswith("zamkn"))
            out = []
            for tr in t.find_all("tr")[1:]:
                c = [x.get_text(strip=True) for x in tr.find_all("td")]
                if len(c) > max(idate, iclose):
                    d = any_date(c[idate])
                    v = num(c[iclose])
                    if d and v is not None:
                        out.append((d, v))
            return out
    return []


# ---- pobieranie ----

def fetch_quotes(market):
    html = http.get(f"/gielda/{market}")
    return parse_quotes(html) if html else []


def fetch_returns(market):
    html = http.get(f"/stopy-zwrotu/{market}")
    return parse_returns(html) if html else []


def fetch_ratio(market, code):
    html = http.get(f"/spolki-wskazniki-wartosci-rynkowej/{market},1,{code}")
    return parse_ratio(html) if html else []


def fetch_dividends(market, year):
    html = http.get(f"/dywidendy/{market},{year}")
    return parse_dividends(html) if html else []


def fetch_company(slug):
    html = http.get(f"/akcjonariat/{slug}")
    return parse_company_page(html) if html else None


def fetch_espi_page(page):
    path = "/temat/76,espi-ebi" + (f",{page}" if page > 1 else "")
    html = http.get(path)
    return parse_espi_list(html) if html else []


def fetch_article(url):
    html = http.get(url)
    return parse_article(html) if html else None


def fetch_price_history(slug, page=1):
    html = http.get(f"/notowania-historyczne/{slug}" + (f",{page}" if page > 1 else ""))
    return parse_price_history(html) if html else []
