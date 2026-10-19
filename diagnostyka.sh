#!/usr/bin/env bash
# Sprawdzenie źródeł danych (odpowiednik diagnostyka.bat).
cd "$(dirname "$0")"
exec .venv/bin/python -m gpwt.diag
