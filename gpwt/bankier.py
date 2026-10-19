"""Bankier.pl jako drugie źródło raportów ESPI/EBI - z załącznikami.

Raporty z archiwów gpw.pl i newconnect.pl mają liczby (formularze art. 69 i MAR) w załącznikach PDF, których
te serwisy nie wydają przy pobieraniu automatycznym. Bankier publikuje te same raporty razem z plikami
(bonnier.pl/static/att/emitent/...), a robots.txt na to pozwala - stąd uzupełnienie załączników.

Lista komunikatów spółki: /gielda/notowania/akcje/<SYMBOL>/komunikaty[/<strona>], ok. 30 pozycji na stronę,
każda z datą i godziną publikacji ("14.10.2026 18:00 | Director/PDMR transaction | espi").
"""
import re
from datetime import datetime

from bs4 import BeautifulSoup

from . import http

HOST = "https://www.bankier.pl"
LIST_URL = HOST + "/gielda/notowania/akcje/{symbol}/komunikaty"
_TS = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})")
_ATT = re.compile(r"https?://(?:[\w-]+\.)?(?:bonnier|bankier)\.pl/static/att/[^\"'\s<>]+", re.I)


def parse_list(html):
    """[{ts: 'YYYY-MM-DD HH:MM', title, url}] - tylko komunikaty ESPI/EBI spółki (bez artykułów redakcji).
    Adres komunikatu zaczyna się od nazwy spółki, nie zawsze równej symbolowi (DEFENCEH -> /wiadomosc/DEFENCE-...),
    więc bierzemy przedrostek wspólny dla większości komunikatów na stronie (odrzuca boczne listy innych spółek)."""
    import collections
    items, seen = [], set()
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=re.compile(r"/wiadomosc/[^/]+-\d+\.html")):
        url = a["href"] if a["href"].startswith("http") else HOST + a["href"]
        if url in seen:
            continue
        box = a.find_parent(["li", "article", "tr", "div"])
        text = box.get_text(" | ", strip=True) if box else ""
        m = _TS.search(text)
        if not m or not re.search(r"\|\s*(espi|ebi)\b", text, re.I):
            continue
        seen.add(url)
        items.append({"ts": f"{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)}",
                      "title": a.get_text(" ", strip=True), "url": url,
                      "prefix": re.search(r"/wiadomosc/([^-/]+)-", url).group(1).upper()})
    if not items:
        return []
    main = collections.Counter(i["prefix"] for i in items).most_common(1)[0][0]
    return [{k: i[k] for k in ("ts", "title", "url")} for i in items if i["prefix"] == main]


def fetch_list(symbol, market="GPW", page=1):
    path = "new-connect" if market == "NC" else "akcje"
    url = LIST_URL.format(symbol=symbol).replace("/akcje/", f"/{path}/") + (f"/{page}" if page > 1 else "")
    html = http.get(url)
    return parse_list(html) if html else []


def attachments(html):
    """Adresy załączników raportu (PDF) ze strony komunikatu."""
    out = []
    for u in _ATT.findall(html or ""):
        if u not in out:
            out.append(u)
    return out


def fetch_attachments(url):
    html = http.get(url)
    return attachments(html) if html else []


def match(item_ts, title, candidates, minutes=5):
    """Komunikat Bankiera odpowiadający raportowi z gpw.pl: ta sama chwila publikacji (+-kilka minut),
    przy kilku kandydatach - najbardziej podobny tytuł."""
    import difflib
    t0 = datetime.fromisoformat(item_ts[:16])
    near = [c for c in candidates if abs((datetime.fromisoformat(c["ts"]) - t0).total_seconds()) <= minutes * 60]
    if not near:
        return None

    def sim(c):
        return difflib.SequenceMatcher(None, _norm(c["title"]), _norm(title)).ratio()
    best = max(near, key=sim)
    return best if len(near) == 1 or sim(best) >= 0.5 else None


def _norm(s):
    s = re.sub(r"^[^:]{1,40}:\s*", "", s or "")  # "MOL: Director/PDMR transaction"
    s = re.sub(r"^.*?\(\d+/\d{4}\)\s*", "", s)  # "MOL RT. (95/2026) Director/PDMR transaction"
    return re.sub(r"\W+", " ", s.lower()).strip()
