#!/usr/bin/env bash
# Uruchomienie lokalne (odpowiednik start.bat): http://127.0.0.1:8050, Ctrl+C kończy.
# Na serwerze dostępnym z sieci użyj gunicorna i hasła - patrz deploy/ i README.
cd "$(dirname "$0")"
exec .venv/bin/python app.py "$@"
