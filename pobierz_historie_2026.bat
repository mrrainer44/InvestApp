@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Jednorazowe historyczne uzupelnienie komunikatow ESPI/EBI (zawiadomienia art. 69,
echo insiderzy MAR, wezwania, listy z WZ) az do poczatku 2026 roku.
echo Ostatnie ok. 6 tygodni pochodzi z Biznesradar, starsze - z archiwow gpw.pl i newconnect.pl.
echo.
echo To duzo wiecej zapytan niz zwykle codzienne pobieranie - moze potrwac
echo od kilkudziesieciu minut do kilku godzin. Mozna zostawic okno otwarte w tle
echo i korzystac w tym czasie z aplikacji normalnie (dane beda sie dopisywac na biezaco).
echo.
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m gpwt.collect --since 2026-01-01
echo.
echo Zakonczone. Odswiez przegladarke (F5), zeby zobaczyc pelna historie w widoku Inwestorzy.
pause
