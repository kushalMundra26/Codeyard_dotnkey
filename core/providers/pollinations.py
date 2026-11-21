"""Pollinations image API.
With POLLINATIONS_KEY (sk_…): GET https://gen.pollinations.ai/image/{prompt}?width&height&seed  (Bearer key)
Without a key: classic GET https://image.pollinations.ai/prompt/{prompt}?width&height&seed
  — anonymous, one image at a time, ≥45 s apart per IP (we enforce 46 s).
"""
from __future__ import annotations

import time
import urllib.parse

import requests

from ..config import env

_last = [0.0]


def generate(prompt: str, width: int = 1024, height: int = 1024, seed: int = 7) -> bytes:
    q = urllib.parse.quote(prompt[:900])
    key = env("POLLINATIONS_KEY")
    if key:
        r = requests.get(f"https://gen.pollinations.ai/image/{q}", params={"width": width, "height": height, "seed": seed},
                         headers={"Authorization": f"Bearer {key}"}, timeout=180)
    else:
        wait = _last[0] + 46 - time.time()
        if wait > 0:
            time.sleep(wait)
        r = requests.get(f"https://image.pollinations.ai/prompt/{q}", params={"width": width, "height": height, "seed": seed},
                         timeout=180)
        _last[0] = time.time()
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(f"Pollinations HTTP {r.status_code}")
    return r.content
