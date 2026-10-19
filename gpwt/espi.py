"""Klasyfikacja komunikatów ESPI/EBI i wyciąganie z nich liczb.

Kategorie:
  art69     - zawiadomienia o zmianie udziału (przekroczenie progów 5/10/15...%)
  mar       - transakcje osób zarządzających (art. 19 MAR)
  wezwanie  - wezwania do zapisywania się na akcje
  wz_lista  - wykaz akcjonariuszy z >=5% głosów na walnym zgromadzeniu
  skup      - skup akcji własnych
  other     - reszta (zapisujemy tylko tytuł)
"""
import io
import logging
import re

from .util import any_date, int_pl, num

log = logging.getLogger("gpwt.espi")

TITLE_RE = re.compile(r"^(.*?)\s*\((\d+/\d{4})\)\s*(.*)$")

_RULES = [
    ("wz_lista", r"(wykaz|lista)\s+akcjonariusz\w*.*(5|pi[eę][cć])\s*%"),
    ("wz_lista", r"(wykaz|lista)\s+akcjonariusz\w*.*walnym"),
    ("mar", r"art\.?\s*19\b|\bMAR\b|obowi[aą]zki zarz[aą]dcze|blisko zwi[aą]zan|"
            r"os[oó]b\w* zarz[aą]dzaj|transakcj\w* (na )?akcjach.*(prezes|cz[lł]onk|insider)"),
    ("wezwanie", r"wezwani\w* do (zapisywania|sprzeda|zapis)|og[lł]oszeni\w* wezwania|\bwezwani\w*\b(?!.* do zap[lł]aty)"),
    ("art69", r"art\.?\s*69|zmian\w* (udzia[lł]u|stanu posiadania)|przekroczeni\w* progu|"
              r"znacz\w* pakiet|zawiadomie\w*.*(udzia[lł]|g[lł]os[oó]w|posiadan)|"
              r"(zwi[eę]kszeni|zmniejszeni)\w* (stanu|udzia)|"
              r"zawiadomie\w* (od|otrzyman\w* od)\s+(?!.*\b(ZUS|KNF|UOKiK|s[aą]d\w*|urz[eę]d\w*|komisj\w*|prokurat\w*|KDPW|GPW)\b)"),
    ("skup", r"skup\w* akcji w[lł]asnych|nabyci\w* akcji w[lł]asnych"),
]


def split_title(title):
    m = TITLE_RE.match(title or "")
    if m:
        return m.group(1).strip(), m.group(3).strip()
    return None, title


def classify(title):
    _, subject = split_title(title)
    s = (subject or title or "")
    for cat, pat in _RULES:
        if re.search(pat, s, re.I):
            if cat == "wezwanie" and re.search(r"do zap[lł]aty|wezwanie do usuni", s, re.I):
                continue
            return cat
    return "other"


_NOT_SHARES = re.compile(r"obligacj|warrant|opcj|prawa do akcji|\bPDA\b|certyfikat|kontrakt|terminow|swap|forward|"
                         r"futures|walut|uprawnie\w* do emisji|emisji gaz|\bCO2\b|jednost\w* uczestnictwa|instrument\w* pochodn",
                         re.I)


def instrument_is_shares(instrument):
    """Czy rodzaj instrumentu z formularza MAR to akcje. "\\bakcj", bo "transakcja" też zawiera "akcj"."""
    return bool(re.search(r"\bakcj|\bshares?\b", instrument, re.I)) and not _NOT_SHARES.search(instrument)


def pdf_text(data):
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception as e:  # noqa: BLE001
        log.warning("Nie udało się odczytać PDF: %s", e)
        return ""


NUM = r"(\d{1,3}(?:[ . ]\d{3})+|\d+)"


def _ints_after(label, text, limit=4):
    pat = re.compile(re.escape(label) + r"\s*[:\-]?\s*\n?\s*" + NUM, re.I)
    return [int_pl(m.group(1)) for m in pat.finditer(text)][:limit]


def _pcts_after(label, text, limit=4):
    pat = re.compile(re.escape(label) + r"\s*[:\-]?\s*\n?\s*(\d+(?:[.,]\d+)?)", re.I)
    return [num(m.group(1)) for m in pat.finditer(text)][:limit]


def _line_after(label, text):
    m = re.search(re.escape(label) + r"\s*[:\-]?\s*\n\s*([^\n]+)", text, re.I)
    if not m:
        m = re.search(re.escape(label) + r"[ \t]*[:\-]?[ \t]+([^\n]+)", text, re.I)
    return m.group(1).strip() if m else None


def parse_art69(text, title=""):
    """Zwraca dict: investor, shares_before, shares_after, pct_before, pct_after, event_date, kind.
    Obsługuje standardowy formularz KNF (Formularz A/B) oraz opis w treści raportu."""
    res = {}
    t = text or ""

    # --- inwestor ---
    inv = _line_after("Podmiot, którego dotyczy zdarzenie", t) or _line_after("Nazwa podmiotu", t)
    if not inv:
        mi = re.search(r"Imi[eę]\s*\n\s*([^\n]+)\s*\n\s*Nazwisko\s*\n\s*([^\n]+)", t)
        if mi:
            inv = f"{mi.group(1).strip()} {mi.group(2).strip()}"
    if not inv:
        for pat in [
            r"zawiadomieni\w*\s+(?:od|z)\s+(.{3,120}?)(?:\s+z siedzib|\s+o\s+zmian|\s+dotycz|,|\.|\(|\n)",
            r"przez\s+((?:Pan|Pani|Panią|Pana)?\s*[A-ZŁŚŻŹĆ][^\n,.(]{2,100}?)(?:\s+z siedzib|\.|,|\n|$)",
            r"otrzyma[lł]\w*\s+od\s+(.{3,120}?)\s+zawiadomieni",
        ]:
            m = re.search(pat, t)
            if m:
                inv = m.group(1).strip()
                break
    if not inv and title:
        m = re.search(r"(?:od|przez)\s+(.{3,80})$", title)
        if m:
            inv = m.group(1).strip()
    if inv:
        inv = re.sub(r"^(Pan[a-zią]*|Pani[a-zą]*)\s+", "", inv, flags=re.I).strip(" .,;")
        res["investor"] = inv[:150]

    # --- liczby: formularz KNF ---
    seg = t
    k = re.search(r"stan przed zmian\w*\s+stan po zmian\w*", t, re.I)
    if k:
        seg = t[k.end():]
        a = _ints_after("Liczba akcji razem", seg, 2)
        if len(a) < 2:
            a = _ints_after("Liczba głosów", seg, 2)
        p = _pcts_after("% udział w liczbie głosów", seg, 2)
        if len(a) == 2:
            res["shares_before"], res["shares_after"] = a
        if len(p) == 2:
            res["pct_before"], res["pct_after"] = p
    # --- liczby: tekst swobodny ---
    if "shares_after" not in res:
        before = re.search(r"przed\s+(?:zmian|transakc|nabyci|zbyci|rozlicz)\w*.{0,300}?" + NUM + r"\s+(?:szt\.?\s+)?akcj",
                           t, re.I | re.S)
        after = re.search(r"(?:po\s+(?:zmian|transakc|nabyci|zbyci|rozlicz|rejestr)\w*|obecnie|aktualnie)"
                          r".{0,300}?" + NUM + r"\s+(?:szt\.?\s+)?akcj", t, re.I | re.S)
        if before:
            res["shares_before"] = int_pl(before.group(1))
        if after:
            res["shares_after"] = int_pl(after.group(1))
        pb = re.search(r"przed\s+\w+.{0,300}?(\d+[.,]\d+)\s*%", t, re.I | re.S)
        pa = re.search(r"(?:po\s+\w+|obecnie|do poziomu|aktualnie).{0,200}?(\d+[.,]\d+)\s*%", t, re.I | re.S)
        if pb:
            res["pct_before"] = num(pb.group(1))
        if pa:
            res["pct_after"] = num(pa.group(1))

    # --- data i rodzaj zdarzenia ---
    for lab in ("Data rozliczenia transakcji", "Data zdarzenia"):
        v = _line_after(lab, t)
        d = _loose_iso(v)
        if d:
            res["event_date"] = d
            break
    if "event_date" not in res:
        m = re.search(r"(?:w dniu|dnia)\s+(\d{1,2}[ .]\S+[ .]\d{4})", t)
        if m:
            res["event_date"] = any_date(m.group(1))
    kind = _line_after("Rodzaj zdarzenia", t)
    if kind and len(kind) < 120:
        res["kind"] = kind
    if res.get("shares_before") is not None and res.get("shares_after") is not None:
        res["delta"] = res["shares_after"] - res["shares_before"]
    return res


def _loose_iso(v):
    if not v:
        return None
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return any_date(v)


def parse_mar(text):
    """Standardowy formularz powiadomienia z art. 19 MAR."""
    t = text or ""
    res = {}
    name = _line_after("Nazwa/Nazwisko", t) or _line_after("Imię i nazwisko", t)
    if name:
        res["investor"] = re.sub(r"^\s*a\)\s*", "", name)[:150]
    pos = _line_after("Stanowisko/status", t)
    if pos:
        res["position"] = pos[:120]
    m = re.search(r"rodzaj instrumentu\s*\n(?:\s*Kod identyfikacyjny\s*\n)?\s*([^\n]+)", t, re.I)
    if m:
        res["instrument"] = m.group(1).strip()[:120]
        res["is_shares"] = instrument_is_shares(res["instrument"])
    kind = _line_after("Rodzaj transakcji", t)
    if kind:
        res["kind"] = kind[:120]
        kl = kind.lower()
        if re.search(r"nabyci|kupn|zakup|obj[eę]ci|subskryp", kl):
            res["side"] = 1
        elif re.search(r"zbyci|sprzeda", kl):
            res["side"] = -1
    zb = re.search(r"Informacje zbiorcze(.{0,400})", t, re.I | re.S)
    if zb:
        z = zb.group(1)
        nums = re.findall(r"(\d[\d  .]*(?:,\d+)?)\s*(PLN|zł|EUR)?", z)
        vol = price = None
        for raw, cur in nums:
            if cur and price is None:
                price = num(raw)
            elif not cur and vol is None and "," not in raw:
                vol = int_pl(raw.strip()) or num(raw)
        if vol:
            res["volume"] = vol
        if price is not None:
            res["price"] = price
    if "volume" not in res:
        m = re.search(r"wolumen\w*\s*[:\-]?\s*" + NUM, t, re.I)
        if m:
            res["volume"] = int_pl(m.group(1))
    if "price" not in res:
        m = re.search(r"cen\w*\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(?:PLN|zł)", t, re.I)
        if m:
            res["price"] = num(m.group(1))
    d = _loose_iso(_line_after("Data transakcji", t))
    if d:
        res["event_date"] = d
    if res.get("volume") and res.get("side"):
        res["delta"] = res["side"] * res["volume"]
    return res


WZ_LINE = re.compile(
    r"(?:^|\n)\s*(?:\d+[.)]|[-•–])?\s*(.{3,200}?)\s*[-–:]\s*" + NUM +
    r"\s*(?:głos|akcj)[^\n]*?(?:(\d+[.,]\d+)\s*%\s*ogólnej)?", re.I)


def parse_wz_list(text):
    out = []
    for m in WZ_LINE.finditer(text or ""):
        name = m.group(1).strip(" ;,")
        if re.search(r"dysponowali|kapitał|reprezentowan\w* na|łącznie", name, re.I):
            continue
        votes = int_pl(m.group(2))
        if not votes:
            continue
        eol = (text or "").find("\n", m.end())
        line = (text or "")[m.start(): eol if eol > 0 else None]
        pm = re.search(r"(\d+[.,]\d+)\s*%\s*ogólnej", line)
        out.append({"holder": name, "votes": votes, "pct_total": num(pm.group(1)) if pm else None})
    return out
