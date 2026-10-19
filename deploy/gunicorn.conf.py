# gunicorn -c deploy/gunicorn.conf.py wsgi:app
import os

# Domyślnie tylko lokalnie - na świat wystawia reverse proxy z HTTPS (nginx/Caddy), patrz README.
bind = os.environ.get("GPWT_BIND", "127.0.0.1:8050")
# Jeden proces: stan "pobieranie trwa" jest w pamięci, a SQLite i tak zapisuje jednym wątkiem naraz.
workers = 1
threads = 4
timeout = 120
accesslog = "-"
errorlog = "-"
