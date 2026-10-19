#!/usr/bin/env bash
# Pierwsze pełne pobranie (odpowiednik pierwsze_pobranie.bat): notowania, wskaźniki, dywidendy,
# ok. 600 ostatnich komunikatów ESPI, struktury portfeli OFE i akcjonariat wszystkich spółek (~40 min).
cd "$(dirname "$0")"
.venv/bin/python -m gpwt.collect --weekly
echo
echo "Zakończone. Uruchom ./start.sh, żeby zobaczyć dane."
