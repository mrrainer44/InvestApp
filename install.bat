@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo === GPW Tracker - instalacja ===
echo.

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Nie znaleziono Pythona. Zainstaluj Python 3.10 lub nowszy z https://www.python.org/downloads/
  echo i zaznacz opcje "Add python.exe to PATH". Potem uruchom ten plik ponownie.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Tworze srodowisko Pythona w folderze .venv ...
  %PY% -m venv .venv || goto :err
)
echo Instaluje biblioteki ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err

echo.
echo Dodaje codzienne pobieranie do Harmonogramu zadan (codziennie 18:30) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0schedule.ps1" -Time "18:30"

echo.
echo Gotowe. Teraz:
echo   1. Uruchom "pierwsze_pobranie.bat" (ok. 40 minut - pobiera wszystko, lacznie z akcjonariatem)
echo   2. Uruchom "start.bat", zeby otworzyc aplikacje w przegladarce
pause
exit /b 0

:err
echo.
echo Instalacja nie powiodla sie. Sprawdz komunikat powyzej.
pause
exit /b 1
