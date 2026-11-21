"""Polite HTTP: per-host pacing, exponential backoff on 429/5xx, real User-Agent."""
from __future__ import annotations

import random
import threading
import time
from urllib.parse import urlparse

import requests

from .config import USER_AGENT

_last: dict[str, float] = {}
_lock = threading.Lock()
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
})


def _pace(host: str, min_gap: float) -> None:
    with _lock:
        now = time.time()
        wait = _last.get(host, 0) + min_gap - now
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()


def get(url: str, *, params=None, headers=None, min_gap: float = 1.5, max_tries: int = 5,
        timeout: float = 30, polite: bool = True) -> requests.Response:
    host = urlparse(url).netloc
    delay = 5.0
    last_exc: Exception | None = None
    for attempt in range(max_tries):
        if polite:
            _pace(host, min_gap + random.uniform(0, 0.5))
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == max_tries - 1:
                break  # respect the limit; caller records the failure and moves on
            ra = r.headers.get("retry-after")
            wait = float(ra) if ra and ra.replace(".", "").isdigit() else delay
            time.sleep(min(wait, 90))
            delay *= 2
            continue
        return r
    if last_exc:
        raise last_exc
    return r  # last 429/5xx response (honoured, not retried further)
