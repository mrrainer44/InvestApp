@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo GPW Tracker dziala pod adresem http://127.0.0.1:8050  (zamknij to okno, zeby wylaczyc)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" app.py
