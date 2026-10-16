@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs

if exist logs\server.pid (
  set /p OLDPID=<logs\server.pid
  tasklist /FI "PID eq %OLDPID%" | find "%OLDPID%" >nul
  if not errorlevel 1 (
    echo GPW Tracker juz dziala w tle ^(PID %OLDPID%^), http://127.0.0.1:8050
    pause
    exit /b 0
  )
)

echo Uruchamiam GPW Tracker w tle...
set PYTHONIOENCODING=utf-8
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Start-Process -FilePath '.venv\Scripts\pythonw.exe' -ArgumentList 'app.py' -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput 'logs\server.out.log' -RedirectStandardError 'logs\server.err.log' -PassThru; $p.Id | Out-File -Encoding ascii 'logs\server.pid'"

timeout /t 2 >nul
echo.
echo Gotowe. GPW Tracker dziala w tle pod adresem http://127.0.0.1:8050
echo To okno mozna zamknac - serwer dalej dziala. Aby go zatrzymac, uruchom stop_tlo.bat
pause
