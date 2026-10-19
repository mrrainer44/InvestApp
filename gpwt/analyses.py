"""Analizy fundamentalne użytkownika - pliki w data/analyses.

Na serwerze to lustro folderu OneDrive (rclone sync, deploy/gpw-tracker-af-sync.*): użytkownik zapisuje
plik w OneDrive, a aplikacja przypisuje go do spółki po nazwie pliku - najpierw po tickerze
("ARL_Analiza.docx", "Mentzen_XDD_..."), potem po nazwie spółki ("Enter_Air_Analiza...").
"""
import re
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

AF_DIR = DATA_DIR / "analyses"
EXTENSIONS = {".pdf", ".docx", ".doc", ".odt", ".xlsx", ".xls", ".txt", ".md"}
_DATES = [
    (re.compile(r"(20\d\d)-(\d\d)-(\d\d)"), lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    (re.compile(r"(?<!\d)(\d\d)[_.-](20\d\d)(?!\d)"), lambda m: f"{m[2]}-{m[1]}-01"),
]
_SPLIT = re.compile(r"[\s_\-.()]+")
_BEFORE_KEYWORD = re.compile(r"(?i)[\s_\-]*(analiza|analysis|update|aktualizacja|fundamentaln\w*)\b")
_cache = {"key": None, "data": None}


def file_date(name, path):
    for rx, fmt in _DATES:
        m = rx.search(name)
        if m:
            return fmt(m)
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def ticker_for(name, tickers, matcher=None):
    stem = Path(name).stem
    for tok in _SPLIT.split(stem):
        if tok.isupper() and tok in tickers:
            return tok
    company = _BEFORE_KEYWORD.split(stem)[0].replace("_", " ").strip()
    return matcher.match(company) if matcher and company else None


def scan(con):
    """{ticker albo None: [plik, ...]} - najnowsze pierwsze. Wynik w pamięci, dopóki pliki się nie zmienią."""
    if not AF_DIR.exists():
        return {}
    files = [p for p in AF_DIR.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
             and not p.name.startswith(("~$", "."))]
    key = tuple(sorted((p.as_posix(), p.stat().st_mtime, p.stat().st_size) for p in files))
    if _cache["key"] == key:
        return _cache["data"]
    from .ofe import Matcher
    tickers = {r[0] for r in con.execute("SELECT ticker FROM companies")}
    matcher = Matcher(con)
    out = {}
    for p in files:
        t = ticker_for(p.name, tickers, matcher)
        out.setdefault(t, []).append({"file": p.relative_to(AF_DIR).as_posix(), "name": p.name, "ticker": t,
                                      "date": file_date(p.name, p), "size": p.stat().st_size})
    for v in out.values():
        v.sort(key=lambda x: x["date"], reverse=True)
    _cache.update(key=key, data=out)
    return out


def last_sync():
    marker = AF_DIR / ".last_sync"
    return marker.read_text(encoding="utf-8").strip() if marker.exists() else None
