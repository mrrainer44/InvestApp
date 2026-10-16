"""Ustawienia aplikacji. Wszystko, co warto zmienić, jest w jednym miejscu."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
import os
DB_PATH = Path(os.environ["GPWT_DB"]) if os.environ.get("GPWT_DB") else DATA_DIR / "gpw.sqlite"
PDF_CACHE = DATA_DIR / "pdf_cache"

BASE = "https://www.biznesradar.pl"
MARKETS = {"akcje_gpw": "GPW", "newconnect": "NC"}

# Uprzejme pobieranie: przerwa między zapytaniami (sekundy) + losowy dodatek.
REQUEST_DELAY = 1.5
REQUEST_JITTER = 0.7
TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GPW-Tracker/1.0 "
    "(narzedzie do uzytku prywatnego)"
)

# ESPI: przy pierwszym uruchomieniu ile stron listy przejrzeć (ok. 20 komunikatów na stronę)
ESPI_FIRST_RUN_PAGES = 30
ESPI_MAX_PAGES = 30
MAX_PDF_BYTES = 3_000_000

# Wskaźniki wyceny pobierane z list Biznesradar (kod w URL -> nazwa kolumny)
RATIOS = {"CZCurrent": "cz", "CWKCurrent": "cwk", "EVEBITDACurrent": "evebitda", "CPCurrent": "cp"}

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8050

for d in (DATA_DIR, LOG_DIR, PDF_CACHE):
    d.mkdir(parents=True, exist_ok=True)
