"""Szybka diagnostyka źródeł: pobiera po jednej stronie z każdego źródła i pokazuje,
ile wierszy udało się odczytać. Uruchom, gdy coś przestanie działać:

    python -m gpwt.diag
"""
from datetime import date

from . import biznesradar as br
from . import espi, http


def line(name, n, sample=""):
    mark = "OK " if n else "!! "
    print(f"{mark}{name:<38} {n:>5}  {sample}")


def main():
    print("Sprawdzam źródła danych (ok. 1 minuta)...\n")
    q = br.fetch_quotes("akcje_gpw")
    line("Notowania GPW", len(q), q[0]["ticker"] + " " + str(q[0]["close"]) if q else "")
    nc = br.fetch_quotes("newconnect")
    line("Notowania NewConnect", len(nc))
    r = br.fetch_returns("akcje_gpw")
    line("Stopy zwrotu GPW", len(r))
    for code in ("CZCurrent", "CWKCurrent", "EVEBITDACurrent"):
        x = br.fetch_ratio("akcje_gpw", code)
        line(f"Wskaźnik {code}", len(x))
    dv = br.fetch_dividends("akcje_gpw", date.today().year)
    line("Dywidendy GPW (bieżący rok)", len(dv))
    if q:
        c = br.fetch_company(q[0]["slug"])
        line(f"Akcjonariat {q[0]['ticker']}", len(c["holders"]) if c else 0,
             f"akcji: {c['shares']}, branża: {c['sector']}" if c else "")
    items = br.fetch_espi_page(1)
    line("Lista komunikatów ESPI", len(items))
    cats = {}
    for it in items:
        cats.setdefault(espi.classify(it["title"]), []).append(it)
    print("     kategorie:", {k: len(v) for k, v in cats.items()})
    for it in (cats.get("art69", []) + cats.get("mar", []))[:3]:
        art = br.fetch_article(it["url"])
        text = art["text"] if art else ""
        for href in (art["pdfs"] if art else [])[:1]:
            data = http.get(href, binary=True)
            if data:
                text += "\n=== PDF ===\n" + espi.pdf_text(data)
        cat = espi.classify(it["title"])
        p = espi.parse_art69(text.split("=== PDF ===")[-1], it["title"]) if cat == "art69" else espi.parse_mar(text)
        print(f"\n  [{cat}] {it['title'][:90]}\n     odczytano: {p}")
    print("\nGotowe. Linie z '!!' oznaczają źródło, z którego nic nie odczytano.")


if __name__ == "__main__":
    main()
