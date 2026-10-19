"""Archiwum raportów ESPI/EBI z gpw.pl (Główny Rynek) i newconnect.pl (NewConnect).

Biznesradar udostępnia listę komunikatów tylko z ostatnich ok. 6-7 tygodni, a te dwa serwisy
sięgają lat wstecz - używamy ich do historycznego uzupełnienia (collect --since).

Załączniki (attachment/...) oba serwisy odrzucają przy pobieraniu automatycznym (strona "Request
Rejected" zamiast PDF), dlatego collect czyta z tych źródeł tylko treść raportu, a załączniki pobiera
z Bankier.pl (gpwt.bankier).
"""
import re

from bs4 import BeautifulSoup

from . import http

SOURCES = {
    # host: (strona listy, przesunięcie id w tabeli espi - żeby nie kolidowało z id Biznesradar)
    "www.gpw.pl": ("komunikaty", 50_000_000),
    "newconnect.pl": ("spolki-komunikaty-spolek", 60_000_000),
}
PAGE_SIZE = 100
_ISIN = re.compile(r"\(([A-Z]{2}[A-Z0-9]{9}\d)\)\s*$")


def _soup(html):
    return BeautifulSoup(html, "lxml")


def parse_list(html, host):
    out = []
    for li in _soup(html).find_all("li"):
        d = li.find("span", class_="date")
        a = li.select_one("strong.name a[href*=geru_id]")
        if not d or not a:
            continue
        parts = [x.strip() for x in d.get_text().split("|")]
        m = re.match(r"(\d{2})-(\d{2})-(\d{4}) (\d{2}:\d{2})", parts[0])
        if not m:
            continue
        gid = int(re.search(r"geru_id=(\d+)", a["href"]).group(1))
        name = a.get_text(" ", strip=True)
        im = _ISIN.search(name)
        p = li.find("p")
        out.append({
            "id": SOURCES[host][1] + gid,
            "ts": f"{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)}",
            "company": _ISIN.sub("", name).strip(),
            "isin": im.group(1) if im else None,
            "report_no": parts[3] if len(parts) > 3 else "",
            "subject": p.get_text(" ", strip=True) if p else "",
            "url": f"https://{host}/komunikat?geru_id={gid}",
        })
    return out


def fetch_list(host, offset):
    page = SOURCES[host][0]
    params = ("action=GPWEspiReportUnion&start=ajaxSearch&page={}&format=html&lang=PL&letter="
              "&offset={}&limit={}&categoryRaports%5B%5D=ESPI&categoryRaports%5B%5D=EBI"
              "&typeRaports%5B%5D=RB&typeRaports%5B%5D=P&typeRaports%5B%5D=Q&typeRaports%5B%5D=O"
              "&typeRaports%5B%5D=R&searchText=&date=").format(page, offset, PAGE_SIZE)
    html = http.get(f"https://{host}/ajaxindex.php?{params}")
    return parse_list(html, host) if html else []


def parse_article(html, host):
    soup = _soup(html)
    box = soup.find("div", class_="report-data")
    text = box.get_text("\n", strip=True) if box else ""
    pdfs = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith("attachment/") and ".pdf" in h.lower():
            u = f"https://{host}/{h}"
            if u not in pdfs:
                pdfs.append(u)
    return {"text": text, "pdfs": pdfs}


def fetch_article(url):
    host = re.match(r"https://([^/]+)/", url).group(1)
    html = http.get(url)
    return parse_article(html, host) if html else None


def is_own_url(url):
    return any((url or "").startswith(f"https://{h}/") for h in SOURCES)
