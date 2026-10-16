@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Pierwsze pelne pobranie: notowania, wskazniki, dywidendy, ok. 600 ostatnich komunikatow ESPI
echo oraz akcjonariat wszystkich spolek. Potrwa ok. 40 minut - mozesz zostawic okno otwarte.
echo.
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m gpwt.collect --weekly
echo.
echo Zakonczone. Uruchom start.bat, zeby zobaczyc dane.
pause
