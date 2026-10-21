"""Zbieranie danych. Uruchamiane codziennie (Harmonogram zadań Windows) albo ręcznie:

    python -m gpwt.collect              # dzienny zestaw + tygodniowy, jeśli minęło >= 6 dni
    python -m gpwt.collect --weekly     # wymuś pełne odświeżenie akcjonariatu (ok. 30 min)
    python -m gpwt.collect --limit 20   # tylko 20 spółek w części tygodniowej (test)
"""
import argparse
import difflib
import json
import logging
import re
import sys
import traceback
from datetime import date, datetime, timedelta

from . import biznesradar as br
from . import bankier, db, espi, flows, gpwpl, http, ofe, pressure
from .config import (ESPI_FIRST_RUN_PAGES, ESPI_MAX_PAGES, LOG_DIR, MARKETS, MAX_PDF_BYTES,
                     PDF_CACHE, RATIOS)
from .util import norm_company, norm_investor

log = logging.getLogger("gpwt.collect")


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        fh = logging.FileHandler(LOG_DIR / "collect.log", encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(fh)
        root.addHandler(sh)
    # pypdf zgłasza drobne usterki w budowie plików PDF spółek, a i tak je czyta - nie zaśmiecamy okna
    logging.getLogger("pypdf").setLevel(logging.ERROR)


def trading_date(today=None):
    d = today or date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def stale_quote(time_cell):
    """Kolumna czasu w notowaniach: "16:59" = transakcja z dzisiejszej sesji, "16 paź 09:56" = z wcześniejszej."""
    return bool(re.match(r"\s*\d{1,2}\s+[^\d\s:]", time_cell or ""))


def now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------- notowania, stopy zwrotu, wskaźniki, dywidendy ----------------

def collect_market_tables(con, stats, quick=False):
    """quick: tylko notowania i stopy zwrotu (pobieranie w trakcie sesji), bez wskaźników i dywidend."""
    td = trading_date()
    for mkt, label in MARKETS.items():
        log.info("[1/4] %s: notowania, stopy zwrotu, wskaźniki, dywidendy...", label)
        q = br.fetch_quotes(mkt)
        stats[f"quotes_{label}"] = len(q)
        for r in q:
            con.execute(
                """INSERT INTO companies(ticker, short_name, full_name, market, slug, last_seen)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(ticker) DO UPDATE SET short_name=excluded.short_name,
                     full_name=excluded.full_name, market=excluded.market, slug=excluded.slug,
                     last_seen=excluded.last_seen""",
                (r["ticker"], r["short_name"], r["full_name"], label, r["slug"], td))
            if r["close"] and stale_quote(r.get("time")):
                # brak handlu dziś: Biznesradar pokazuje ostatnią transakcję z wcześniejszej sesji ("16 paź 09:56")
                # - zostaje tylko kurs, bez jej wolumenu i obrotu
                r = {**r, "change_pct": 0.0, "volume": 0.0, "turnover": 0.0}
            if r["close"]:
                con.execute("INSERT OR REPLACE INTO quotes VALUES(?,?,?,?,?,?)",
                            (r["ticker"], td, r["close"], r["change_pct"], r["volume"], r["turnover"]))
                con.execute("INSERT OR REPLACE INTO price_history VALUES(?,?,?)", (r["ticker"], td, r["close"]))
                if r.get("turnover"):  # tylko spółki z handlem tego dnia - do wskaźników presji kupujących
                    con.execute("INSERT OR REPLACE INTO ohlc VALUES(?,?,?,?,?,?,?,?)",
                                (r["ticker"], td, r.get("open"), r.get("high"), r.get("low"), r["close"],
                                 r["volume"], r["turnover"]))
        con.commit()

        stats[f"returns_{label}"] = _store_returns(con, br.fetch_returns(mkt), td)
        if quick:
            con.commit()
            continue

        for code, col in RATIOS.items():
            rr = br.fetch_ratio(mkt, code)
            stats[f"ratio_{col}_{label}"] = len(rr)
            for r in rr:
                con.execute("INSERT INTO ratios(ticker, updated) VALUES(?,?) ON CONFLICT(ticker) DO NOTHING",
                            (r["ticker"], td))
                con.execute(f"UPDATE ratios SET {col}=?, report=COALESCE(?, report), updated=? WHERE ticker=?",
                            (r["value"], r["report"], td, r["ticker"]))

        y = date.today().year
        # starsze lata raz (historia wypłat do odróżnienia dywidendy regularnej od jednorazowej)
        hist = () if con.execute("SELECT 1 FROM settings WHERE key='div_history'").fetchone() else range(y - 7, y - 1)
        for year in (*hist, y - 1, y, y + 1):
            dv = br.fetch_dividends(mkt, year)
            stats[f"div_{year}_{label}"] = len(dv)
            for r in dv:
                if r["dps"] is None:
                    continue
                con.execute("INSERT OR REPLACE INTO dividends VALUES(?,?,?,?,?,?,?)",
                            (r["ticker"], r["year_for"], r["wza"], r["last_day"] or "", r["pay_day"] or "",
                             r["dps"], r["status"]))
        con.commit()
    con.execute("INSERT OR REPLACE INTO settings VALUES('div_history', ?)", (td,))
    con.commit()


def _store_returns(con, ret, td):
    for r in ret:
        con.execute("INSERT OR REPLACE INTO returns VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (r["ticker"], r["r1w"], r["r1m"], r["r3m"], r["r6m"], r["ytd"], r["r12m"],
                     r["r24m"], r["r36m"], td))
    return len(ret)


def backfill_nc_history(con, stats):
    """NewConnect nie ma archiwum sesji jak gpw.pl - bierzemy ok. 50 ostatnich sesji spółki z pierwszej strony
    historii notowań Biznesradar (dalszych stron robots.txt zabrania). Raz na spółkę, potem historia rośnie
    z codziennych notowań - wystarcza do presji kupujących z 30 dni."""
    done = set(json.loads((con.execute("SELECT value FROM settings WHERE key='nc_history'").fetchone() or ["[]"])[0]))
    todo = [r for r in con.execute("SELECT ticker, slug FROM companies WHERE market='NC' AND slug IS NOT NULL "
                                   "ORDER BY ticker").fetchall() if r["ticker"] not in done]
    if not todo:
        return
    log.info("[1/4] Historia notowań NewConnect (do presji kupujących): %s spółek", len(todo))
    added = 0
    for i, r in enumerate(todo, 1):
        rows = br.fetch_price_history_full(r["slug"])
        batch = [(r["ticker"], x["date"], x["open"], x["high"], x["low"], x["close"], x["volume"], x["turnover"])
                 for x in rows if x["turnover"]]
        if batch:
            added += con.executemany("INSERT OR IGNORE INTO ohlc VALUES(?,?,?,?,?,?,?,?)", batch).rowcount
        done.add(r["ticker"])
        if i % 25 == 0 or i == len(todo):
            con.execute("INSERT OR REPLACE INTO settings VALUES('nc_history', ?)", (json.dumps(sorted(done)),))
            con.commit()
            log.info("      NewConnect: %s/%s spółek", i, len(todo))
    stats["nc_history_rows"] = added


def _lock():
    """Jedno pobieranie naraz (timer systemd i przycisk w aplikacji mogą trafić w ten sam moment).
    None = brak blokad w tym systemie (Windows), False = inne pobieranie trwa."""
    try:
        import fcntl
    except ImportError:
        return None
    f = open(LOG_DIR / "collect.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    return f


# ---------------- dopasowanie nazwy spółki z ESPI do tickera ----------------

class CompanyMatcher:
    def __init__(self, con):
        self.by_norm = {}
        for r in con.execute("SELECT ticker, full_name, short_name FROM companies"):
            for n in (r["full_name"], r["short_name"], r["ticker"]):
                k = norm_company(n or "")
                if k:
                    self.by_norm.setdefault(k, r["ticker"])
        self.keys = list(self.by_norm)

    def match(self, name):
        k = norm_company(name or "")
        if not k:
            return None
        if k in self.by_norm:
            return self.by_norm[k]
        kt = set(k.split())
        best = [c for c in self.keys if set(c.split()) and (set(c.split()) <= kt or kt <= set(c.split()))
                and len(c) >= 3]
        if len(best) == 1:
            return self.by_norm[best[0]]
        if best:  # najdłuższe dopasowanie
            return self.by_norm[max(best, key=len)]
        close = difflib.get_close_matches(k, self.keys, n=1, cutoff=0.86)
        return self.by_norm[close[0]] if close else None


# ---------------- ESPI ----------------

FETCH_BODY = {"art69", "mar", "wz_lista", "wezwanie"}
FETCH_PDF = {"art69", "mar"}


def collect_espi(con, stats, max_pages=None, since=None):
    """since: pobieraj strony listy, dopóki nie miniemy tej daty (YYYY-MM-DD) - do jednorazowego
    historycznego uzupełnienia (python -m gpwt.collect --since 2026-01-01)."""
    known_max = con.execute("SELECT MAX(id) FROM espi").fetchone()[0]
    pages = max_pages or (ESPI_MAX_PAGES if known_max else ESPI_FIRST_RUN_PAGES)
    matcher = CompanyMatcher(con)
    new = 0
    log.info("[2/4] Komunikaty ESPI: przeglądam do %s stron listy%s...",
             pages, f" (do {since})" if since else "")
    for p in range(1, pages + 1):
        items = br.fetch_espi_page(p)
        if not items:
            break
        fresh = [i for i in items if not con.execute("SELECT 1 FROM espi WHERE id=?", (i["id"],)).fetchone()]
        for it in fresh:
            company, _ = espi.split_title(it["title"])
            cat = espi.classify(it["title"])
            con.execute("INSERT OR IGNORE INTO espi(id, ticker, company, title, url, ts, category) VALUES(?,?,?,?,?,?,?)",
                        (it["id"], matcher.match(company), company, it["title"], it["url"], it["ts"], cat))
            new += 1
        con.commit()
        if p % 10 == 0:
            log.info("      lista komunikatów: strona %s/%s (najstarsza na stronie: %s)", p, pages, items[-1]["ts"][:10])
        if since:
            if items[-1]["ts"][:10] < since:
                break
        elif known_max and not fresh:
            break
    stats["espi_new"] = new


def collect_gpw_history(con, stats, since):
    """Komunikaty sprzed zasięgu listy Biznesradar - z archiwów gpw.pl i newconnect.pl."""
    until = con.execute("SELECT MIN(ts) FROM espi WHERE id < ?", (min(o for _, o in gpwpl.SOURCES.values()),)
                        ).fetchone()[0] or "9999"
    by_isin = {r["isin"]: r["ticker"] for r in con.execute("SELECT ticker, isin FROM companies WHERE isin IS NOT NULL")}
    matcher = CompanyMatcher(con)
    new = 0
    for host in gpwpl.SOURCES:
        log.info("[2/4] Archiwum %s: komunikaty od %s do %s...", host, since, until)
        offset = 0
        while True:
            items = gpwpl.fetch_list(host, offset)
            if not items:
                break
            for it in items:
                if not (since <= it["ts"] < until):
                    continue
                if con.execute("SELECT 1 FROM espi WHERE id=?", (it["id"],)).fetchone():
                    continue
                no = it["report_no"]
                title = (f"{it['company']} ({no}) {it['subject']}" if re.fullmatch(r"\d+/\d{4}", no)
                         else f"{it['company']} {it['subject']}")
                ticker = by_isin.get(it["isin"]) or matcher.match(it["company"])
                con.execute("INSERT OR IGNORE INTO espi(id, ticker, company, title, url, ts, category) "
                            "VALUES(?,?,?,?,?,?,?)",
                            (it["id"], ticker, it["company"], title, it["url"], it["ts"], espi.classify(title)))
                new += 1
            con.commit()
            offset += gpwpl.PAGE_SIZE
            if offset % (gpwpl.PAGE_SIZE * 10) == 0:
                log.info("      %s: %s komunikatów przejrzanych (najstarszy: %s)", host, offset, items[-1]["ts"][:10])
            if items[-1]["ts"][:10] < since:
                break
    stats["gpw_history_new"] = new


def reparse_espi(con, stats):
    """Ponowny odczyt zapisanej treści raportów art. 69 / MAR po poprawce parsera - bez pobierania z sieci."""
    n = 0
    for r in con.execute("SELECT id, category, title, body, parsed FROM espi WHERE fetched=1 "
                         "AND category IN ('art69','mar') AND body IS NOT NULL").fetchall():
        old = json.loads(r["parsed"] or "{}")
        new = parse_espi_text(r["category"], r["body"], r["title"], [])
        if "bankier" in old:
            new["bankier"] = old["bankier"]
        if new != old:
            con.execute("UPDATE espi SET parsed=? WHERE id=?", (json.dumps(new, ensure_ascii=False), r["id"]))
            n += 1
    con.commit()
    stats["espi_reparsed"] = n


def reclassify_other(con, stats):
    """Komunikaty z kategorii "other" sprawdzane ponownie po rozszerzeniu reguł (np. angielskie tytuły)
    - nowe art69/mar trafią do odczytu treści w fetch_espi_details."""
    moved = 0
    for r in con.execute("SELECT id, title FROM espi WHERE category='other'").fetchall():
        cat = espi.classify(r["title"])
        if cat != "other":
            con.execute("UPDATE espi SET category=?, fetched=0 WHERE id=? AND category='other'", (cat, r["id"]))
            moved += 1
    con.commit()
    if moved:
        stats["espi_reclassified"] = moved


def _pdf_texts(espi_id, hrefs, tag=""):
    """Tekst załączników PDF (z pamięci podręcznej albo pobrany). Zwraca (tekst, liczba plików nie-PDF)."""
    text, not_pdf = "", 0
    for i, href in enumerate(hrefs[:6]):
        cache = PDF_CACHE / f"{espi_id}_{tag}{i}.txt"
        if cache.exists() and cache.stat().st_size:
            text += "\n\n=== PDF ===\n" + cache.read_text(encoding="utf-8")
            continue
        data = http.get(href, binary=True)
        if not data or len(data) > MAX_PDF_BYTES:
            continue
        if data[:4] != b"%PDF":
            not_pdf += 1
            log.warning("Załącznik nie jest plikiem PDF (%s B, zaczyna się od %r) - pomijam: %s",
                        len(data), data[:15], href)
            continue
        t = espi.pdf_text(data)
        if t.strip():
            cache.write_text(t, encoding="utf-8")
            text += "\n\n=== PDF ===\n" + t
    return text, not_pdf


def _has_forms(parsed):
    return any(f.get("delta") for f in json.loads(parsed or "{}").get("forms", []))


def fetch_bankier_attachments(con, stats, max_pages=20):
    """Raporty art. 69 / MAR z archiwów gpw.pl i newconnect.pl, z których nie odczytaliśmy liczb, a mają
    załączniki - te same pliki pobieramy z Bankier.pl (komunikat dopasowany po chwili publikacji i tytule).
    Każdy raport sprawdzamy raz (parsed.bankier = adres komunikatu albo "brak")."""
    rows = con.execute(
        "SELECT e.id, e.ticker, e.ts, e.title, e.category, e.body, e.parsed, c.short_name, c.market FROM espi e "
        "JOIN companies c ON c.ticker=e.ticker WHERE e.category IN ('art69','mar') AND e.fetched=1 "
        "AND (e.url LIKE 'https://www.gpw.pl/%' OR e.url LIKE 'https://newconnect.pl/%') ORDER BY e.ticker, e.ts DESC"
    ).fetchall()
    todo = {}
    for r in rows:
        p = json.loads(r["parsed"] or "{}")
        if "bankier" in p or _has_forms(r["parsed"]) or not r["short_name"]:
            continue
        if re.search(r"Spis zalacznikow|Znaleziono \d+ za", r["body"] or ""):
            todo.setdefault(r["ticker"], []).append(r)
    n_rep = sum(len(v) for v in todo.values())
    if not n_rep:
        return
    log.info("[2/4] Załączniki z Bankier.pl: %s raportów z gpw.pl/newconnect.pl (%s spółek)", n_rep, len(todo))
    found = parsed_ok = done = 0
    for ticker, items in todo.items():
        oldest = min(r["ts"] for r in items)[:10]
        cands = []
        for page in range(1, max_pages + 1):
            lst = bankier.fetch_list(items[0]["short_name"], items[0]["market"], page)
            if not lst:
                break
            cands += lst
            if lst[-1]["ts"][:10] < oldest:
                break
        for r in items:
            done += 1
            if done % 25 == 0:
                log.info("      załączniki: %s/%s (dopasowane %s, z liczbami %s)", done, n_rep, found, parsed_ok)
            p = json.loads(r["parsed"] or "{}")
            m = bankier.match(r["ts"], r["title"], cands)
            pdf = ""
            if m:
                found += 1
                pdf, _ = _pdf_texts(r["id"], bankier.fetch_attachments(m["url"]), tag="bk")
            if pdf:
                text = (r["body"] or "") + pdf
                p = parse_espi_text(r["category"], text, r["title"], [])
                parsed_ok += _has_forms(json.dumps(p))
                p["bankier"] = m["url"]
                con.execute("UPDATE espi SET body=?, parsed=? WHERE id=?",
                            (text[:60000], json.dumps(p, ensure_ascii=False), r["id"]))
            else:
                p["bankier"] = m["url"] if m else "brak"
                con.execute("UPDATE espi SET parsed=? WHERE id=?", (json.dumps(p, ensure_ascii=False), r["id"]))
            con.commit()
    stats["bankier_reports"] = n_rep
    stats["bankier_matched"] = found
    stats["bankier_parsed"] = parsed_ok


def fetch_espi_details(con, stats):
    todo = con.execute(
        f"SELECT * FROM espi WHERE fetched=0 AND category IN ({','.join('?' * len(FETCH_BODY))}) ORDER BY id",
        tuple(FETCH_BODY)).fetchall()
    parsed_ok, not_pdf = 0, 0
    log.info("[2/4] Odczytuję treść i załączniki PDF istotnych komunikatów: %s", len(todo))
    for n_done, row in enumerate(todo, 1):
        if n_done % 10 == 0:
            log.info("      komunikaty: %s/%s", n_done, len(todo))
        own = gpwpl.is_own_url(row["url"])
        art = (gpwpl.fetch_article if own else br.fetch_article)(row["url"])
        if art is None:
            con.execute("UPDATE espi SET fetched=-1 WHERE id=?", (row["id"],))
            continue
        text = art["text"]
        # gpw.pl i newconnect.pl odrzucają automatyczne pobieranie załączników (zabezpieczenie serwera),
        # więc z tych źródeł czytamy tylko treść raportu - załączniki uzupełnia potem fetch_bankier_attachments
        if row["category"] in FETCH_PDF and not own:
            pdf, bad = _pdf_texts(row["id"], art["pdfs"])
            text += pdf
            not_pdf += bad
        parsed = parse_espi_text(row["category"], text, row["title"], art.get("pdfs", []))
        if parsed:
            parsed_ok += 1
        con.execute("UPDATE espi SET body=?, parsed=?, fetched=1 WHERE id=?",
                    (text[:60000], json.dumps(parsed, ensure_ascii=False), row["id"]))
        con.commit()
    stats["espi_details"] = len(todo)
    stats["espi_parsed"] = parsed_ok
    if not_pdf:
        stats["espi_not_pdf"] = not_pdf


def parse_espi_text(cat, text, title, pdfs):
    if cat == "art69":
        # Jeden raport może zawierać kilka zawiadomień (kilka PDF) - parsujemy każdy osobno.
        parts = text.split("=== PDF ===")
        forms = [espi.parse_art69(p, title) for p in parts[1:]] if len(parts) > 1 else []
        forms = [f for f in forms if f.get("shares_after") is not None]
        if not forms:
            f = espi.parse_art69(parts[0], title)
            forms = [f] if f else []
        return {"forms": forms}
    if cat == "mar":
        parts = text.split("=== PDF ===")
        forms = [espi.parse_mar(p) for p in parts[1:]] if len(parts) > 1 else [espi.parse_mar(text)]
        return {"forms": [f for f in forms if f]}
    if cat == "wz_lista":
        return {"holders": espi.parse_wz_list(text)}
    return {}


# ---------------- akcjonariat (tygodniowo) ----------------

def collect_companies(con, stats, limit=None):
    q = "SELECT ticker, slug FROM companies WHERE slug IS NOT NULL ORDER BY (profile_updated IS NOT NULL), profile_updated"
    rows = con.execute(q).fetchall()
    if limit:
        rows = rows[:limit]
    ok = 0
    today = date.today().isoformat()
    log.info("[3/4] Akcjonariat, liczba akcji i branża: %s spółek (ok. %s min)...", len(rows), round(len(rows) * 1.9 / 60))
    for i, r in enumerate(rows, 1):
        try:
            d = br.fetch_company(r["slug"])
        except Exception as e:  # noqa: BLE001
            log.warning("Błąd profilu %s: %s", r["ticker"], e)
            continue
        if not d:
            continue
        con.execute("UPDATE companies SET shares=COALESCE(?, shares), sector=COALESCE(?, sector), "
                    "isin=COALESCE(?, isin), profile_updated=? WHERE ticker=?",
                    (d["shares"], d["sector"], d["isin"], today, r["ticker"]))
        for h in d["holders"]:
            if not h["holder"] or not h["shares"]:
                continue
            con.execute("""INSERT OR IGNORE INTO holdings_snap VALUES(?,?,?,?,?,?,?,?)""",
                        (r["ticker"], h["holder"], norm_investor(h["holder"]), h["shares"], h["pct"],
                         h["date_upd"] or today, "BR", today))
        ok += 1
        if i % 25 == 0:
            con.commit()
            log.info("Akcjonariat: %s/%s", i, len(rows))
    con.commit()
    stats["companies_profiles"] = ok
    con.execute("INSERT OR REPLACE INTO settings VALUES('last_weekly', ?)", (today,))


def store_wz_snapshots(con):
    for row in con.execute("SELECT id, ticker, ts, parsed FROM espi WHERE category='wz_lista' AND fetched=1 "
                           "AND ticker IS NOT NULL").fetchall():
        p = json.loads(row["parsed"] or "{}")
        for h in p.get("holders", []):
            con.execute("INSERT OR IGNORE INTO holdings_snap VALUES(?,?,?,?,?,?,?,?)",
                        (row["ticker"], h["holder"], norm_investor(h["holder"]), h["votes"], h.get("pct_total"),
                         row["ts"][:10], "WZ", row["ts"][:10]))
    con.commit()


def run(weekly=False, limit=None, skip_espi=False, since=None, max_pages=None, ofe_only=False, ohlc_days=None,
        bankier_only=False, reparse=False, quick=False):
    setup_logging()
    lock = _lock()
    if lock is False:
        log.warning("Inne pobieranie właśnie trwa - pomijam to uruchomienie")
        return "busy", {}
    db.init()
    stats = {}
    con = db.connect()
    kind = ("quick" if quick else "sesje" if ohlc_days else "reparse" if reparse else "bankier" if bankier_only else "ofe" if ofe_only else "backfill" if since
            else ("weekly" if weekly else "daily"))
    run_id = con.execute("INSERT INTO runs(started, kind, status) VALUES(?,?,?)", (now(), kind, "running")).lastrowid
    con.commit()
    status = "ok"
    try:
        if ohlc_days:  # tylko historia notowań sesyjnych GPW (do wskaźników presji kupujących)
            pressure.backfill(con, ohlc_days, stats)
            pressure.backfill_indices(con, ohlc_days, stats)
            return status, stats
        if reparse:  # tylko ponowny odczyt zapisanych raportów (po poprawce parsera) i przeliczenie zmian
            reparse_espi(con, stats)
            stats.update(flows.rebuild_changes(con))
            stats.update(flows.fill_prices(con))
            return status, stats
        if quick:  # w trakcie sesji: notowania i nowe komunikaty (ok. minuty)
            collect_market_tables(con, stats, quick=True)
            collect_espi(con, stats)
            reclassify_other(con, stats)
            fetch_espi_details(con, stats)
            store_wz_snapshots(con)
            stats.update(flows.rebuild_changes(con))
            stats.update(flows.fill_prices(con))
            return status, stats
        if bankier_only:  # tylko załączniki raportów z archiwum gpw.pl (jednorazowe uzupełnienie historii)
            fetch_bankier_attachments(con, stats)
            stats.update(flows.rebuild_changes(con))
            stats.update(flows.fill_prices(con))
            return status, stats
        if not since and not ofe_only:
            collect_market_tables(con, stats)
            pressure.backfill(con, 10, stats)  # uzupełnia sesje GPW z ostatnich dni, gdyby pobieranie wypadło
            pressure.backfill_indices(con, 10, stats)
            backfill_nc_history(con, stats)
        if not skip_espi and not ofe_only:
            collect_espi(con, stats, max_pages=max_pages or (500 if since else None), since=since)
            if since:
                collect_gpw_history(con, stats, since)
            reclassify_other(con, stats)
            fetch_espi_details(con, stats)
            fetch_bankier_attachments(con, stats)
            store_wz_snapshots(con)
        last_weekly = con.execute("SELECT value FROM settings WHERE key='last_weekly'").fetchone()
        due = not last_weekly or (date.today() - date.fromisoformat(last_weekly[0])).days >= 6
        if (weekly or due or limit) and not ofe_only:
            collect_companies(con, stats, limit)
        if weekly or due or since or ofe_only:
            ofe.collect(con, stats)
        log.info("[4/4] Liczę zmiany stanu posiadania i ich wartość...")
        stats.update(flows.rebuild_changes(con))
        stats.update(flows.fill_prices(con))
    except Exception as e:  # noqa: BLE001
        status = "error"
        stats["error"] = f"{e.__class__.__name__}: {e}"
        log.error(traceback.format_exc())
    finally:
        con.execute("UPDATE runs SET finished=?, status=?, summary=? WHERE id=?",
                    (now(), status, json.dumps(stats, ensure_ascii=False), run_id))
        con.commit()
        con.close()
        if lock:
            lock.close()
    log.info("Koniec: %s %s", status, stats)
    return status, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true", help="wymuś odświeżenie akcjonariatu wszystkich spółek")
    ap.add_argument("--limit", type=int, help="ogranicz liczbę spółek w części tygodniowej")
    ap.add_argument("--skip-espi", action="store_true")
    ap.add_argument("--since", metavar="YYYY-MM-DD",
                     help="jednorazowe historyczne uzupełnienie komunikatów ESPI (art.69/MAR/wezwania/WZ) "
                          "wstecz do tej daty, np. --since 2026-01-01")
    ap.add_argument("--max-pages", type=int, help="limit stron listy komunikatów (domyślnie 500 przy --since)")
    ap.add_argument("--ofe", action="store_true",
                    help="tylko struktury portfeli OFE (od 31.12.2024) i przeliczenie zmian")
    ap.add_argument("--ohlc-history", type=int, metavar="DNI",
                    help="tylko historia notowań sesyjnych GPW z archiwum gpw.pl za ostatnie DNI dni (np. 400)")
    ap.add_argument("--bankier", action="store_true",
                    help="tylko załączniki PDF raportów z archiwum gpw.pl/newconnect.pl - pobrane z Bankier.pl")
    ap.add_argument("--reparse", action="store_true",
                    help="ponownie odczytaj zapisane raporty art. 69 / MAR (po poprawce parsera) i przelicz zmiany")
    ap.add_argument("--quick", action="store_true",
                    help="szybkie pobranie w trakcie sesji: notowania, stopy zwrotu i nowe komunikaty")
    a = ap.parse_args()
    st, _ = run(weekly=a.weekly, limit=a.limit, skip_espi=a.skip_espi, since=a.since, max_pages=a.max_pages,
                ofe_only=a.ofe, ohlc_days=a.ohlc_history, bankier_only=a.bankier,
                reparse=a.reparse, quick=a.quick)
    sys.exit(0 if st in ("ok", "busy") else 1)
