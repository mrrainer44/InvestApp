#!/usr/bin/env bash
# Codzienne pobieranie (odpowiednik run_daily.bat) - do crona albo timera systemd.
cd "$(dirname "$0")"
exec .venv/bin/python -m gpwt.collect "$@"
