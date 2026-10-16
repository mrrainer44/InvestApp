# GPW Tracker

Lokalna aplikacja, która raz dziennie zbiera dane o spółkach z GPW i NewConnect i pokazuje je w przeglądarce:

- **Spółki** – lista ok. 730 spółek: branża, kurs, obrót, kapitalizacja, stopy zwrotu, C/Z, C/WK, EV/EBITDA, dywidendy (stopa z 12 mies., najbliższy dzień z prawem), główni akcjonariusze, udział OFE/TFI, ostatnie zawiadomienie i przepływ kapitału z 30 dni. Kolumny włączasz/wyłączasz, przeciągasz i sortujesz, a układ zapisuje się sam. Możesz dodawać **własne kolumny** (tekst, liczba, tak/nie, data, lista) i wpisywać w nie wartości wprost w tabeli, np. „Kupiłem”, „Cena docelowa”, „Status”. Zapisane **widoki** pozwalają przełączać się między zestawami kolumn.
- **Inwestorzy** – ile każdy inwestor kupił i sprzedał w danym tygodniu lub miesiącu (w zł), z podziałem na źródła.
- **Zmiany stanu posiadania** – każda pojedyncza zmiana, z której liczone są sumy. Tu poprawiasz liczby, jeśli parser się pomylił, albo wykluczasz wiersz z sum.
- **Komunikaty ESPI** – zawiadomienia o zmianie udziału (art. 69), transakcje insiderów (MAR), wezwania, listy akcjonariuszy z walnych, skup akcji własnych – z odczytanymi liczbami.
- **Dane i ustawienia** – historia pobrań, ręczne uruchomienie, łączenie różnych zapisów tej samej nazwy inwestora.

Kliknięcie tickera otwiera panel spółki: wykres kursu, akcjonariat, zmiany, dywidendy, komunikaty.

## Instalacja (Windows)

1. Zainstaluj **Python 3.10+** z python.org (zaznacz „Add python.exe to PATH”).
2. Rozpakuj folder w dowolnym miejscu, np. `C:\Users\barte\OneDrive\Dokumenty\Bartek\TRADING\GPW Tracker`.
3. Uruchom **`install.bat`** – utworzy środowisko, zainstaluje biblioteki i doda zadanie w Harmonogramie zadań (codziennie 18:30; jeśli komputer był wyłączony, uruchomi się po włączeniu).
4. Uruchom **`pierwsze_pobranie.bat`** – pierwszy pełny przebieg trwa ok. 40 minut.
5. Uruchom **`start.bat`** – aplikacja otworzy się w przeglądarce pod `http://127.0.0.1:8050`. To okno musi zostać otwarte, dopóki korzystasz z aplikacji – zamknięcie go wyłącza serwer.

Żeby korzystać z aplikacji bez trzymania otwartego okna konsoli, uruchom zamiast tego **`start_tlo.bat`** – uruchomi serwer w tle (bez widocznego okna) i od razu otworzy przeglądarkę. Adres `http://127.0.0.1:8050` zostaje ten sam, działa dopóki nie uruchomisz **`stop_tlo.bat`** albo nie zrestartujesz komputera. Logi serwera trafiają do `logs\server.out.log` i `logs\server.err.log`.

Godzinę pobierania zmienisz poleceniem (PowerShell w folderze aplikacji):
`powershell -ExecutionPolicy Bypass -File schedule.ps1 -Time "07:30"`

## Skąd są dane

Wszystko pochodzi z publicznych stron serwisu Biznesradar.pl (notowania opóźnione o 15 min, wskaźniki, dywidendy, akcjonariat, komunikaty ESPI/EBI razem z załącznikami PDF). Aplikacja pobiera strony powoli (ok. 1,5–2 s przerwy między zapytaniami) i tylko to, czego potrzebuje:

| Co | Jak często | Ile zapytań |
|---|---|---|
| Notowania, stopy zwrotu, wskaźniki, dywidendy | codziennie | ok. 20 |
| Nowe komunikaty ESPI + treść i PDF istotnych | codziennie | 20–150 |
| Akcjonariat, liczba akcji, branża każdej spółki | raz w tygodniu | ok. 730 |
| Archiwalne kursy do wyceny starszych zmian | gdy potrzeba | kilka–kilkadziesiąt |

Lista komunikatów ESPI/EBI na Biznesradar sięga tylko ok. 6 tygodni wstecz. Starsze komunikaty uzupełnia jednorazowo **`pobierz_historie_2026.bat`** (`python -m gpwt.collect --since 2026-01-01`) z archiwów **gpw.pl** (Główny Rynek) i **newconnect.pl** (NewConnect). Te archiwa sięgają lat wstecz, a spółkę rozpoznajemy po kodzie ISIN. Bieżące pobieranie zostaje na Biznesradar, bo porównanie pokazało, że ma 100% komunikatów z obu serwisów GPW.

Dane są do Twojego prywatnego użytku. Nie publikuj ich dalej – prawa do treści mają serwisy źródłowe.

## Jak liczona jest kwota „zainwestowana” przez inwestora

Zawiadomienia i sprawozdania funduszy podają liczbę akcji, a nie kwotę. Dlatego:

**wartość = zmiana liczby akcji × kurs zamknięcia z dnia zdarzenia**
(dla transakcji insiderów – cena z formularza MAR).

Źródła zmian i ich ograniczenia:

- **art69** – zawiadomienia o przekroczeniu progów 5/10/15/20/25/33/50/75/90% i zmianach dużych pakietów. Dokładne liczby akcji „przed” i „po” z formularza KNF w PDF. Data = data rozliczenia transakcji.
- **mar** – transakcje zarządu i rady nadzorczej, z ceną i wolumenem.
- **fundusze** – zmiany w portfelach OFE/TFI/DFE (dane z ich sprawozdań, także poniżej 5%). Data to dzień sprawozdania (koniec kwartału/półrocza/roku), więc te kwoty skupiają się w tygodniach kończących okresy sprawozdawcze.
  - **Historia OFE (od 31.12.2024)** pochodzi z oficjalnych struktur aktywów wszystkich 8 OFE. Roczna struktura (31.12) zawiera pełną listę spółek, półroczna (30.06) tylko większe pozycje. Pliki są pobierane z archiwum dokumenty.analizy.pl. Struktury podają wartość w zł, więc liczba akcji to wartość / kurs zamknięcia z ostatniej sesji (archiwum notowań gpw.pl). Podział akcji (split) jest rozpoznawany po jednodniowym skoku kursu. Spółka, która zniknęła z rocznej struktury, liczy się jako sprzedana w całości. Nowe struktury sprawdzane są przy cotygodniowym pobieraniu, a ręcznie uruchomisz je poleceniem `python -m gpwt.collect --ofe`.
  - Portfele TFI z historią są w Biznesradar tylko w płatnym BR Premium, więc aplikacja ich nie pobiera.
- **akcjonariat** – zmiany wśród głównych akcjonariuszy między cotygodniowymi odczytami. Zmiany już opisane w zawiadomieniu art. 69 są automatycznie oznaczane jako duplikat i nie liczą się podwójnie.
- **wz** – listy z walnych zgromadzeń (najmniej dokładne, domyślnie wyłączone w widoku Inwestorzy).

Kwota to szacunek: przy transakcjach pakietowych, ABB czy emisjach rzeczywista cena bywa inna niż kurs z sesji. Emisja akcji (np. „Rejestracja zmian KZ w KRS”) też pokaże się jako przyrost akcji – kolumna „Uwagi” mówi, jakie to było zdarzenie.

## Gdy coś nie działa

- **`diagnostyka.bat`** sprawdza każde źródło i pokazuje, ile wierszy odczytano, plus przykładowe odczytane zawiadomienia. Linia z `!!` = źródło, z którego nic nie przyszło (zwykle zmiana wyglądu strony).
- Log pobierania: `logs\collect.log`. Baza danych: `data\gpw.sqlite` (zwykły plik SQLite – możesz go otworzyć np. w DB Browser for SQLite albo w Excelu przez Power Query).
- Komunikat bez przypisanej spółki: w widoku „Komunikaty ESPI” kliknij „przypisz” i wpisz ticker.
- Ten sam inwestor pod różnymi nazwami: „Dane i ustawienia” → „Łączenie nazw inwestorów”.

## Struktura

```
app.py                 serwer (Flask) i API
gpwt/collect.py        zbieranie danych (python -m gpwt.collect [--weekly] [--limit N])
gpwt/biznesradar.py    parsery stron
gpwt/gpwpl.py          archiwum komunikatów z gpw.pl i newconnect.pl (uzupełnianie historii)
gpwt/ofe.py            struktury portfeli OFE (roczne/półroczne) -> stany posiadania funduszy
gpwt/espi.py           klasyfikacja komunikatów i odczyt formularzy art. 69 / MAR / WZ
gpwt/flows.py          zmiany stanu posiadania, wycena, sumy tygodniowe/miesięczne
gpwt/config.py         ustawienia (przerwy między zapytaniami, godziny, port)
static/                interfejs (Tabulator 6.6, licencja MIT)
tests/                 test całego potoku offline: python tests/test_pipeline.py
```
