"""Wejście dla serwera produkcyjnego: gunicorn -c deploy/gunicorn.conf.py wsgi:app

Wymaga hasła (GPWT_PASSWORD): aplikacja pozwala edytować dane i uruchamiać pobieranie,
więc bez logowania nie wolno jej wystawiać poza własny komputer.
"""
from gpwt import config

if not config.AUTH_PASSWORD:
    raise SystemExit("Ustaw GPWT_PASSWORD (np. w /etc/gpw-tracker.env) - bez hasła każdy mógłby edytować dane.")

from app import app  # noqa: E402,F401
