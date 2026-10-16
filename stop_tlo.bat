@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist logs\server.pid (
  echo GPW Tracker nie dziala w tle ^(brak logs\server.pid^).
  pause
  exit /b 0
)

set /p PID=<logs\server.pid
taskkill /PID %PID% /F >nul 2>nul
del logs\server.pid >nul 2>nul
echo Zatrzymano GPW Tracker.
pause
