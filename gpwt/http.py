"""Pobieranie stron z przerwami między zapytaniami i ponawianiem przy błędach."""
import logging
import random
import time

import requests

from .config import BASE, REQUEST_DELAY, REQUEST_JITTER, TIMEOUT, USER_AGENT

log = logging.getLogger("gpwt.http")
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pl-PL,pl;q=0.9"})
_last = 0.0


def _wait():
    global _last
    gap = REQUEST_DELAY + random.random() * REQUEST_JITTER
    sleep = _last + gap - time.monotonic()
    if sleep > 0:
        time.sleep(sleep)
    _last = time.monotonic()


def get(path_or_url, binary=False, tries=3):
    url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
    for attempt in range(1, tries + 1):
        _wait()
        try:
            r = _session.get(url, timeout=TIMEOUT)
            if r.status_code == 404:
                log.warning("404 %s", url)
                return None
            if r.status_code in (429, 503):
                time.sleep(20 * attempt)
                continue
            r.raise_for_status()
            if binary:
                return r.content
            r.encoding = r.encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            log.warning("Błąd pobierania %s (próba %s): %s", url, attempt, e)
            time.sleep(5 * attempt)
    log.error("Nie udało się pobrać %s", url)
    return None
