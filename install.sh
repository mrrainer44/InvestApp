#!/usr/bin/env bash
# GPW Tracker - instalacja na Linuksie (odpowiednik install.bat). Nie wymaga uprawnień roota.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

echo "=== GPW Tracker - instalacja ==="
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Nie znaleziono $PY. Zainstaluj Python 3.10 lub nowszy (Debian/Ubuntu: sudo apt install python3 python3-venv)."
  exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Wymagany Python 3.10 lub nowszy, a jest: $("$PY" --version)"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Tworzę środowisko Pythona w folderze .venv ..."
  if ! "$PY" -m venv .venv; then
    echo "Nie udało się utworzyć .venv. Debian/Ubuntu: sudo apt install python3-venv"
    exit 1
  fi
fi
echo "Instaluję biblioteki ..."
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data logs

cat <<EOF

Gotowe. Teraz:
  1. ./pierwsze_pobranie.sh   - pierwsze pełne pobranie (ok. 40 minut)
  2. ./start.sh               - aplikacja na http://127.0.0.1:8050 (tylko z tego komputera)

Codzienne pobieranie: cron (crontab -e):
  30 18 * * *  cd "$PWD" && ./run_daily.sh >/dev/null 2>&1
albo usługi systemd z katalogu deploy/ (opis w README, sekcja "Linux / serwer").
EOF
