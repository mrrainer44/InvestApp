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
    # do kalendarza: harmonogramy raportów okresowych i zwołania walnych zgromadzeń
    ("terminy", r"termin\w*\s+(przekazywania|publikacji|przekazania)\s+raport|harmonogram\w*\s+(publikacji|przekazywania)"
                r"\s+raport|zmian\w*\s+(harmonogramu|termin\w*).{0,40}raport\w*\s+(okresow|kwartaln|p[oó][lł]roczn|roczn)|"
                r"financial\s+calendar|dates?\s+of\s+(publication|periodic)"),
    ("wz_zwolanie", r"zwo[lł]ani\w*.{0,60}walne\w*\s+zgromadz|og[lł]oszeni\w*\s+o\s+zwo[lł]aniu|"
                    r"zwo[lł]uj\w*.{0,40}walne|notice\s+of\s+(the\s+)?(annual\s+|extraordinary\s+)?general\s+meeting|"
                    r"convening\s+(notice|of)"),
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
    # zagraniczni emitenci (MOL, KRKA, Kernel, Sopharma, Pepco...) publikują po angielsku
    ("wz_lista", r"shareholders?\s+(holding|with|having)\s+(at least|more than|over)\s+5\s*%"),
    ("mar", r"\bPDMRs?\b|discharging\s+manag\w+\s+responsibilit|closely\s+associated|"
            r"manager'?s'?\s+transactions?|notification\s+(of|on)\s+manager\w*\s+transaction|"
            r"directors?'?\s+(dealings?|transactions?)|596/2014\s+for\s+(transactions?|a\s+pledge|pledge)|"
            r"^notification\s+of\s+transactions?$"),
    ("wezwanie", r"(mandatory|voluntary|non-competitive)\s+(\w+\s+)?tender\s+offer|takeover\s+bid|"
                 r"tender\s+offer\s+(to|for)\s+(buy|acquire|purchase)\w*(-up)?\s+(the\s+)?(remaining\s+)?(\w+\s+)?shares"),
    ("art69", r"major\s+holdings?|large\s+shareholding|significant\s+(holding|shareholding)|"
              r"acquisition\s+of\s+voting\s+rights|(threshold|thresholds)\s+(of|was|were|has|crossed|exceeded)|"
              r"crossing\s+(of\s+)?(the\s+)?threshold|article\s+145\b.*(POSA|public\s+offering)"),
    ("skup", r"treasury\s+shares?|own\s+shares|buy-?\s?back|share\s+repurchase|repurchase\s+(of\s+)?(own\s+)?shares"),
]


# słowa kluczowe w tytułach komunikatów (tagi w Sesji i kalendarzu); raporty okresowe pomijamy
KEYWORDS = [
    ("umowa", r"umow|kontrakt|zam[oó]wieni|zleceni|porozumieni|list\w* intencyjn|aneks|kontrahent|"
              r"\bcontract|\bagreement|\border\b|purchase order"),
    ("wyniki", r"szacunkow|wst[eę]pn\w* (wynik|dan)|wybran\w* (dan|wynik)|prognoz|estimated (results|financial)|"
               r"preliminary (results|financial)|guidance"),
    ("skup", r"skup\w* akcji|nabyci\w* akcji w[lł]asnych|buy-?\s?back|treasury shares|own shares"),
    ("wezwanie", r"wezwani\w* do zapis|og[lł]osz\w* wezwani|wezwani\w* na (sprzeda|akcje)|stanowisk\w*.{0,40}wezwani|"
                 r"zamiar\w*.{0,30}wezwani|mandatory.{0,20}tender offer|tender offer to|takeover"),
    ("emisja", r"emisj|ofert\w* publiczn|prospekt|zapis\w* na akcje|subskrypc|book-?building|podwy[zż]szeni\w* kapita|"
               r"warrant\w* subskrypcyjn|share issue|new shares|capital increase|private placement"),
    ("dywidenda", r"dywidend|dividend"),
    ("wz", r"walne\w* zgromadzeni|\b[NZ]?WZ\b|general meeting|\bAGM\b|\bEGM\b"),
]
# fałszywe trafienia tagu: umowa z audytorem to nie kontrakt handlowy, obligacje nie rozwadniają akcjonariuszy
_NOT_TAG = {"umowa": re.compile(r"audytor|bieg[lł]\w* rewident|badani\w* sprawozda", re.I),
            "emisja": re.compile(r"obligacj|bond|\bFIZ\b|certyfikat|podporz[aą]dkowan|\btier\b|instrument\w* dodatkow|"
                                 r"list\w* zastawn|koszt\w* emisji|uzupe[lł]nieni\w* raportu|suplement", re.I)}
_PERIODIC = re.compile(r"raport (kwartalny|p[oó][lł]roczny|roczny|okresowy)|\bQSr|\bSA-?[PRQ]|\bPSr|\bRS\b", re.I)


_SHARE_ISSUE = re.compile(
    r"emisj\w* (nowych )?akcji|akcj\w* (nowej )?emisji|akcj\w*(\s+[\wąćęłńóśźż]+){0,4}\s+serii\s+[A-Z0-9]{1,3}\b.{0,60}(emisj|subskrypc|zapis|przydzia|ofert)|"
    r"(emisj|subskrypc|zapis|przydzia|ofert)\w*.{0,60}akcj\w*(\s+[\wąćęłńóśźż]+){0,4}\s+serii|ofert\w* publiczn\w* akcji|kapita[lł]\w* docelow|"
    r"warrant\w* subskrypcyjn|private placement|new shares|share issue|capital increase|accelerated book|book-?building", re.I)


def share_issue(title):
    """Emisja AKCJI (rozwodnienie) - ostrzej niż tag "emisja": bez obligacji, sprostowań i warunkowych podwyższeń
    kapitału pod programy motywacyjne."""
    _, subject = split_title(title)
    s = subject or title or ""
    return bool(_SHARE_ISSUE.search(s)) and not _NOT_TAG["emisja"].search(s) and not re.search(
        r"warunkow\w* podwy|uchyl|odst[aą]pi|rezygnacj|odwo[lł]ani|zaniechani|powiadomieni\w* o transakcj|"
        r"transakcj\w* (na|dotycz)|withdraw|cancel", s, re.I)


def keywords(title):
    _, subject = split_title(title)
    s = subject or title or ""
    if _PERIODIC.search(s):
        return []
    return [tag for tag, pat in KEYWORDS if re.search(pat, s, re.I) and not (tag in _NOT_TAG and _NOT_TAG[tag].search(s))]


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
                         r"futures|walut|uprawnie\w* do emisji|emisji gaz|\bCO2\b|jednost\w* uczestnictwa|instrument\w* pochodn|"
                         r"\b(euro)?bonds?\b|\bnotes?\b|derivativ|\bCFDs?\b|\boptions?\b|rights? to (acquire|subscribe)",
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
    # data transakcji, nie jej rozliczenia (T+2, bywa późniejsza niż publikacja raportu)
    for lab in ("Data zdarzenia", "Data powzięcia informacji o zdarzeniu", "Data rozliczenia transakcji"):
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
    if "delta" not in res and re.search(r"Nature of the transaction|Aggregated (information|volume)|"
                                        r"Regulation\W+(\(EU\)\s*)?(No\.?\s*)?596/2014|\bPDMR|managerial responsib",
                                        t, re.I):
        en = parse_mar_en(t)
        if en.get("delta"):
            return {**res, **en}
    return res


CCY = r"PLN|zł|EUR|HUF|CZK|USD|GBP|BGN|RON|UAH|CHF|SEK|NOK|DKK"
EN_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"


def num_en(s):
    """Liczba z angielskiego formularza: '1,027,948' -> 1027948 ; '19.93' -> 19.93 ; '185 030' -> 185030."""
    if s is None:
        return None
    s = str(s).replace("\xa0", " ").replace(" ", " ").strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"\d{1,3}( \d{3})+([.,]\d+)?", s):
        s = s.replace(" ", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v.is_integer() else v


def _section(t, start, end):
    m = re.search(start + r"(?P<body>.*?)(?:" + end + r"|$)", t, re.I | re.S)
    return m.group("body") if m else ""


def _vol_price(seg):
    """Wolumen i cena z bloku 'Aggregated information' / 'Price(s) and volume(s)'."""
    seg = re.sub(r"-?\s*Aggregated\s+volume|-?\s*Price\(?s?\)?(\s+and\s+volume\(?s?\)?)?|Volume\(?s?\)?", " ", seg,
                 flags=re.I)
    seg = re.sub(r"\b(19|20)\d{2}-\d{2}-\d{2}\b|\d{1,2}\.\d{1,2}\.\d{4}", " ", seg)  # daty to nie liczby
    vol = price = ccy = None
    for m in re.finditer(r"(?:(" + CCY + r")\s*)?" + EN_NUM + r"\s*(" + CCY + r")?(?:\s*/\s*(?:piece|share))?"
                         r"(\s*(?:pieces|pcs|shares|szt))?", seg, re.I):
        cur = m.group(1) or m.group(3)
        v = num_en(m.group(2))
        if v is None:
            continue
        if cur and price is None:
            price, ccy = v, cur.upper().replace("ZŁ", "PLN")
        elif not cur and vol is None and (m.group(4) or float(v).is_integer()):
            vol = int(v)
    return vol, price, ccy


def parse_mar_en(text):
    """Angielski formularz z art. 19 MAR (szablon ESMA: Name / Position/status / Nature of the transaction /
    Aggregated information / Date of the transaction), a gdy go brak - opis w treści raportu
    ("X, member of the Management Board, ... acquired 122 shares ... at a price of EUR 236.00")."""
    t = text or ""
    res = {}
    m = re.search(r"a\)\s*Name\b[ \t]*:?[ \t]*([^\n]*)(?:\n\s*([^\n]+))?", t, re.I)
    if m:
        name = (m.group(1).strip() or (m.group(2) or "").strip())
        if name and not re.match(r"\d\)|2\s+Reason", name):
            res["investor"] = name.strip(" .,;")[:150]
    pos = _section(t, r"Position\s*/\s*status", r"b\)\s*Initial|Initial notification")
    if pos.strip():
        res["position"] = re.sub(r"\s+", " ", pos).strip(" :")[:120]
    instr = _section(t, r"financial\s+instrument,?\s+type\s+of\s+instrument", r"b\)\s*Nature|Nature of the transaction")
    lines = [ln.strip() for ln in instr.splitlines()
             if ln.strip() and not re.match(r"Identification\s+code|ISIN\b", ln.strip(), re.I)]
    if lines:
        res["instrument"] = lines[0][:120]
        res["is_shares"] = instrument_is_shares(res["instrument"])
    kind = _section(t, r"Nature\s+of\s+(?:the\s+)?transactions?",r"c\)\s*Price|Price\(s\)")
    if kind.strip():
        res["kind"] = re.sub(r"\s+", " ", kind).strip(" :")[:120]
    agg = _section(t, r"Aggregated\s+information", r"e\)\s*Date|Date of the transaction")
    vol, price, ccy = _vol_price(agg)
    if vol is None:
        vol, price, ccy = _vol_price(_section(t, r"Price\(s\)\s+and\s+volume\(s\)", r"d\)\s*Aggregated|Aggregated"))
    d = _loose_iso(_line_after("Date of the transaction", t))

    if not vol:  # bez formularza: opis w treści
        m = re.search(r"\b(acquired|purchased|bought|subscribed\s+for|sold|disposed\s+of|transferred)\s+"
                      r"(?:a\s+total\s+of\s+)?" + EN_NUM + r"\s+(?:\w+\s+){0,2}shares", t, re.I)
        if m:
            vol = num_en(m.group(2))
            res.setdefault("kind", m.group(1).lower())
            pm = re.search(r"price\s+(?:per\s+share\s+)?(?:of\s+)?(" + CCY + r")\s*" + EN_NUM, t[m.end():], re.I)
            if pm:
                price, ccy = num_en(pm.group(2)), pm.group(1).upper()
            dm = re.findall(r"\bon\s+(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})", t[:m.start()])
            d = d or (any_date(dm[-1]) if dm else None)  # najbliższa data przed opisem transakcji
            if "investor" not in res:
                nm = re.search(r"(?:^|\n|\.\s)([A-ZŠČŽĆ][^\s,]+(?:\s+[A-ZŠČŽĆ][^\s,]+){1,3}),\s+(?:the\s+|a\s+)?"
                               r"(?:person|member|president|chairman|chairwoman|vice|chief|CEO|CFO|COO|director|"
                               r"head|supervisory|management)", t)
                if nm:
                    res["investor"] = nm.group(1).strip()[:150]
    if vol:
        res["volume"] = int(vol)
    if price is not None:
        # formularz bywa w walucie rynku macierzystego (HUF, EUR) - wtedy wartość liczymy z kursu na GPW
        if ccy in (None, "PLN"):
            res["price"] = price
        else:
            res["price_foreign"] = f"{price} {ccy}"
    if d:
        res["event_date"] = d
    kl = res.get("kind", "").lower()
    if re.search(r"acqui|purchas|\bbuy|bought|subscri|exercis", kl):
        res["side"] = 1
    elif re.search(r"\bsale|\bsell|sold|dispos", kl):
        res["side"] = -1
    if res.get("volume") and res.get("side"):
        res["delta"] = res["side"] * res["volume"]
    return res


# ---------------- daty do kalendarza ----------------

_DATE = re.compile(r"(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(20\d\d)|(20\d\d)-(\d{2})-(\d{2})|"
                   r"(\d{1,2})\s+([a-ząćęłńóśźż]{3,12})\s+(20\d\d)", re.I)
_REPORT_KIND = re.compile(
    r"(?P<q3>\bIII\s*kw|\b3\s*\.?\s*kw|trzeci\w*\s+kw|\bQ3\b|third\s+quarter)|"
    r"(?P<q1>\bI\s+kw|\b1\s*\.?\s*kw|pierwsz\w*\s+kw|\bQ1\b|first\s+quarter)|"
    r"(?P<q2>\bII\s+kw|\b2\s*\.?\s*kw|drugi\w*\s+kw|\bQ2\b|second\s+quarter)|"
    r"(?P<q4>\bIV\s+kw|\b4\s*\.?\s*kw|czwart\w*\s+kw|\bQ4\b|fourth\s+quarter)|"
    r"(?P<h1>p[oó][lł]roczn|p[oó][lł]rocz|half-?\s?year|semi-?annual|\bH1\b)|"
    r"(?P<y>(?<![oó][lł])roczn\w*|za\s+(rok\s+)?(obrotowy\s+)?20\d\d(?!\s*r\w*\s*\.?\s*[-–]?\s*\d)|annual)", re.I)
REPORT_LABEL = {"q1": "raport za I kwartał", "q2": "raport za II kwartał", "q3": "raport za III kwartał",
                "q4": "raport za IV kwartał", "h1": "raport półroczny", "y": "raport roczny"}


def _dates_in(s):
    from .util import any_date
    out = []
    for m in _DATE.finditer(s):
        d = any_date(m.group(0))
        if d:
            out.append((m.start(), d))
    return out


def parse_report_dates(text, title=""):
    """Harmonogram raportów okresowych: {rodzaj: data}. Dla każdego rodzaju raportu (I/III kwartał, półrocze, rok)
    bierzemy datę stojącą po nim, zanim zacznie się opis kolejnego raportu. W "zmianie harmonogramu" (stary i nowy
    termin w jednym zdaniu) - ostatnią datę."""
    t = re.sub(r"\s+", " ", text or "")
    k = re.search(r"Tre[sś][cć] raportu:?|Contents of the report:?", t)
    if k:
        t = t[k.end():]
    t = re.split(r"Nazwa arkusza|Podstawa prawna:|Szczeg[oó][lł]owa podstawa prawna|Legal basis", t)[0]
    change = bool(re.search(r"zmian|change", title or "", re.I))
    marks = list(_REPORT_KIND.finditer(t))
    out = {}
    for i, m in enumerate(marks):
        kind = m.lastgroup
        end = min(marks[i + 1].start() if i + 1 < len(marks) else len(t), m.end() + 220)
        window = t[m.end():end]
        ds = [d for _, d in _dates_in(window) if d[:4] >= "2025"]
        if not ds:
            continue
        d = ds[-1] if change else ds[0]
        out[kind] = min(out[kind], d) if kind in out and not change else d
    return out


def parse_meeting_date(text, published=""):
    """Data walnego zgromadzenia ze zwołania: pierwsza data po "na dzień"/"zwołuje"/"odbędzie się", nie wcześniejsza
    niż publikacja."""
    t = re.sub(r"\s+", " ", text or "")
    for m in re.finditer(r"(na\s+dzie[nń]|zwo[lł]uj\w*|odb[eę]dzie\s+si[eę]|w\s+dniu|to\s+be\s+held\s+on|on)\D{0,80}", t, re.I):
        ds = _dates_in(t[m.start(): m.end() + 40])
        for _, d in ds:
            if not published or d >= published[:10]:
                return d
    return None


def parse_tender(text):
    """Wezwanie: daty przyjmowania zapisów i cena."""
    t = re.sub(r"\s+", " ", text or "")
    res = {}
    for key, pat in (("start", r"rozpocz[eę]ci\w*\s+przyjmowania\s+zapis"), ("end", r"zako[nń]czeni\w*\s+przyjmowania\s+zapis")):
        m = re.search(pat, t, re.I)
        if m:
            ds = _dates_in(t[m.end(): m.end() + 120])
            if ds:
                res[key] = ds[0][1]
    m = re.search(r"cen\w*[^.]{0,80}?(\d+[.,]\d{2})\s*(z[lł]|PLN)", t, re.I)
    if m:
        res["price"] = num(m.group(1))
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
