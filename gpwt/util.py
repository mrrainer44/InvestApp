"""Parsowanie liczb, dat i nazw w polskim formacie."""
import re
import unicodedata
from datetime import date, datetime

MONTHS = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8,
    "wrz": 9, "paź": 10, "paz": 10, "lis": 11, "gru": 12,
}
MONTHS_GEN = {  # dopełniacz: "1 września 2026"
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10,
    "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}


def num(s):
    """'1 234,56' -> 1234.56 ; '(+0,67%)' -> 0.67 ; 'bd.' -> None"""
    if s is None:
        return None
    s = str(s).replace("\xa0", " ").strip()
    s = re.sub(r"[()%+]|PLN|zł|EUR|USD", "", s).strip()
    if not s or s.lower().startswith("bd") or s in {"-", "—"}:
        return None
    s = s.replace(" ", "")
    if "," in s and "." in s:
        # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def int_pl(s):
    """'367.918.980' / '1 250 000 000' -> 367918980 (separator tysięcy: spacja, kropka)"""
    if s is None:
        return None
    s = str(s).replace("\xa0", " ").strip()
    if re.fullmatch(r"\d{1,3}([ .]\d{3})+", s):
        return int(re.sub(r"[ .]", "", s))
    s2 = s.replace(" ", "")
    return int(s2) if s2.isdigit() else None


def short_date(s, today=None):
    """'24 cze 26' -> '2026-06-24'"""
    if not s:
        return None
    m = re.match(r"\s*(\d{1,2})\s+(\w+)\s+(\d{2,4})", s)
    if not m:
        return None
    mon = MONTHS.get(m.group(2).lower()[:3])
    if not mon:
        return None
    y = int(m.group(3))
    y = y + 2000 if y < 100 else y
    try:
        return date(y, mon, int(m.group(1))).isoformat()
    except ValueError:
        return None


def any_date(s):
    """Rozpoznaje '29.06.2026', '2026-10-16', '1 września 2026'. Zwraca ISO albo None."""
    if not s:
        return None
    s = s.strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", s.lower())
    if m and m.group(2) in MONTHS_GEN:
        try:
            return date(int(m.group(3)), MONTHS_GEN[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def ascii_fold(s):
    s = s.replace("ł", "l").replace("Ł", "L")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


_COMPANY_SUFFIX = re.compile(
    r"\b(s\s*a|spolka akcyjna|se|n\s*v|plc|inc|ltd|ab|ad|asi|nyrt|a\s*s|spa|ag|"
    r"sp\s*z\s*o\s*o|spolka z ograniczona odpowiedzialnoscia|holding|group|grupa)\b"
)


def norm_company(name):
    s = ascii_fold(name or "").lower().replace("&amp;", "&")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _COMPANY_SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


_INV_REPL = [
    (r"otwart\w* fundusz\w* emerytaln\w*", "ofe"),
    (r"dobrowoln\w* fundusz\w* emerytaln\w*", "dfe"),
    (r"towarzystw\w* fundusz\w* inwestycyjn\w*", "tfi"),
    (r"powszechn\w* towarzystw\w* emerytaln\w*", "pte"),
    (r"fundusz\w* inwestycyjn\w* zamkni\w*", "fiz"),
    (r"fundusz\w* inwestycyjn\w* otwart\w*", "fio"),
    (r"\bspolka akcyjna\b|\bs a\b|\bsa\b", ""),
    (r"\bsp z o o\b|\bspolka z ograniczona odpowiedzialnoscia\b", ""),
    (r"\breprezentowan\w* przez .*", ""),
    (r"\bpan\b|\bpani\b|\bpanstwo\b", ""),
    (r"\bzlota jesien\b", ""),
    (r"\bpolska\b", ""),
]


def norm_investor(name):
    """Klucz do łączenia tego samego inwestora zapisanego różnie.
    'Nationale - Nederlanden Otwarty Fundusz Emerytalny' == 'OFE Nationale Nederlanden'."""
    s = ascii_fold(name or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s)
    for pat, rep in _INV_REPL:
        s = re.sub(pat, rep, s)
    toks = sorted(set(t for t in s.split() if len(t) > 1 or t.isdigit()))
    return " ".join(toks)


def iso_week(d):
    dt = datetime.fromisoformat(d[:10]).date()
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"
