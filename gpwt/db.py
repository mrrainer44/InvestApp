"""Baza SQLite: schemat i proste helpery."""
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(
  ticker TEXT PRIMARY KEY, short_name TEXT, full_name TEXT, market TEXT,
  slug TEXT, sector TEXT, shares REAL, isin TEXT, profile_updated TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS quotes(
  ticker TEXT, date TEXT, close REAL, change_pct REAL, volume REAL, turnover REAL,
  PRIMARY KEY(ticker, date)
);
CREATE TABLE IF NOT EXISTS returns(
  ticker TEXT PRIMARY KEY, r1w REAL, r1m REAL, r3m REAL, r6m REAL, ytd REAL, r12m REAL,
  r24m REAL, r36m REAL, updated TEXT
);
CREATE TABLE IF NOT EXISTS ratios(
  ticker TEXT PRIMARY KEY, cz REAL, cwk REAL, evebitda REAL, cp REAL, report TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS dividends(
  ticker TEXT, year_for TEXT, wza TEXT, last_day TEXT, pay_day TEXT, dps REAL, status TEXT,
  PRIMARY KEY(ticker, last_day, pay_day, dps)
);
CREATE TABLE IF NOT EXISTS espi(
  id INTEGER PRIMARY KEY, ticker TEXT, company TEXT, title TEXT, url TEXT, ts TEXT,
  category TEXT, body TEXT, parsed TEXT, fetched INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS holdings_snap(
  ticker TEXT, holder TEXT, holder_norm TEXT, shares REAL, pct REAL, date_upd TEXT,
  source TEXT, first_seen TEXT,
  PRIMARY KEY(ticker, holder_norm, date_upd, source)
);
CREATE TABLE IF NOT EXISTS changes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT, investor TEXT, investor_norm TEXT,
  shares_before REAL, shares_after REAL, delta REAL, price REAL, price_src TEXT, value REAL,
  source TEXT, espi_id INTEGER, verified INTEGER DEFAULT 0, excluded INTEGER DEFAULT 0, note TEXT,
  UNIQUE(source, ticker, investor_norm, date, espi_id)
);
CREATE TABLE IF NOT EXISTS ohlc(
  ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, turnover REAL,
  PRIMARY KEY(ticker, date)
);
CREATE TABLE IF NOT EXISTS index_ohlc(
  name TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, turnover REAL, PRIMARY KEY(name, date)
);
CREATE TABLE IF NOT EXISTS market_live(
  key TEXT PRIMARY KEY, value REAL, change_pct REAL, ts TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS macro_daily(
  key TEXT, date TEXT, value REAL, change REAL, ts TEXT, source TEXT, PRIMARY KEY(key, date)
);
CREATE TABLE IF NOT EXISTS positions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, opened TEXT NOT NULL, qty REAL NOT NULL,
  price REAL NOT NULL, fees REAL DEFAULT 0, closed TEXT, close_price REAL, close_fees REAL DEFAULT 0, created TEXT
);
CREATE TABLE IF NOT EXISTS plans(
  ticker TEXT PRIMARY KEY, thesis TEXT, stop REAL, target REAL, horizon TEXT, review TEXT, notes TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS price_history(
  ticker TEXT, date TEXT, close REAL, PRIMARY KEY(ticker, date)
);
CREATE TABLE IF NOT EXISTS custom_columns(
  key TEXT PRIMARY KEY, label TEXT, type TEXT, options TEXT, created TEXT
);
CREATE TABLE IF NOT EXISTS custom_values(
  ticker TEXT, key TEXT, value TEXT, updated TEXT, PRIMARY KEY(ticker, key)
);
CREATE TABLE IF NOT EXISTS investor_aliases(
  alias_norm TEXT PRIMARY KEY, canonical TEXT
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, kind TEXT,
  status TEXT, summary TEXT
);
CREATE INDEX IF NOT EXISTS ix_changes_date ON changes(date);
CREATE INDEX IF NOT EXISTS ix_espi_ts ON espi(ts);
CREATE INDEX IF NOT EXISTS ix_quotes_t ON quotes(ticker, date);
"""


def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with session() as con:
        con.executescript(SCHEMA)


def rows(con, sql, params=()):
    return [dict(r) for r in con.execute(sql, params).fetchall()]
