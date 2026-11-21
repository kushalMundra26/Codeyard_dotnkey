"""Cloudflare Workers AI — FLUX.1 [schnell].
POST https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell
Authorization: Bearer {CF_API_TOKEN}; body {prompt, steps (≤8), seed} → {result: {image: <base64 jpeg>}}
"""
from __future__ import annotations

import base64

import requests

from ..config import env


def available() -> bool:
    return bool(env("CF_ACCOUNT_ID") and env("CF_API_TOKEN"))


def generate(prompt: str, seed: int = 7, steps: int = 6) -> bytes:
    url = (f"https://api.cloudflare.com/client/v4/accounts/{env('CF_ACCOUNT_ID')}"
           "/ai/run/@cf/black-forest-labs/flux-1-schnell")
    r = requests.post(url, headers={"Authorization": f"Bearer {env('CF_API_TOKEN')}"},
                      json={"prompt": prompt[:2000], "steps": min(steps, 8)}, timeout=120)  # API rejects 'seed'; determinism via our cache
    if r.status_code != 200:
        raise RuntimeError(f"Cloudflare HTTP {r.status_code}: {r.text[:300]}")
    return base64.b64decode(r.json()["result"]["image"])
