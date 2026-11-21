"""Higgsfield API (pay-as-you-go). Docs: https://docs.higgsfield.ai (verified 2026-11-21, docs/api_reference.md)

Auth:     Authorization: Key {HIGGSFIELD_API_KEY}:{HIGGSFIELD_API_SECRET}
Upload:   POST /files/generate-upload-url {content_type} → {public_url, upload_url, upload_headers}; PUT bytes
I2V:      POST /kling-video/v2.5-turbo/standard/image-to-video {prompt, image_url, duration: 5|10, cfg_scale, negative_prompt}
T2I:      POST /higgsfield-ai/soul/standard {prompt, aspect_ratio, resolution, seed}
Status:   GET /requests/{id}/status → status in queued|in_progress|completed|failed|nsfw|canceled;
          result at video.url or images[].url
Pricing:  Kling 2.5 Turbo ≈ $0.042/s; Soul ≈ $0.0032/image (720p).
"""
from __future__ import annotations

import random
import time

import requests

from .. import costs
from ..config import env

BASE = "https://api.higgsfield.ai"
I2V_PATH = "/kling-video/v2.5-turbo/standard/image-to-video"
I2V_USD_PER_S = 0.042
T2I_PATH = "/higgsfield-ai/soul/standard"
T2I_USD = 0.0032


def available() -> bool:
    return bool(env("HIGGSFIELD_API_KEY") and env("HIGGSFIELD_API_SECRET"))


def _h():
    return {"Authorization": f"Key {env('HIGGSFIELD_API_KEY')}:{env('HIGGSFIELD_API_SECRET')}",
            "Content-Type": "application/json"}


def upload(data: bytes, content_type: str = "image/png") -> str:
    r = requests.post(f"{BASE}/files/generate-upload-url", headers=_h(), json={"content_type": content_type}, timeout=60)
    r.raise_for_status()
    j = r.json()
    put = requests.put(j["upload_url"], data=data, headers=j.get("upload_headers") or {"Content-Type": content_type},
                       timeout=120)
    put.raise_for_status()
    return j["public_url"]


def _poll(request_id: str, timeout_s: int = 600) -> dict:
    t0, delay = time.time(), 2.0
    while time.time() - t0 < timeout_s:
        r = requests.get(f"{BASE}/requests/{request_id}/status", headers=_h(), timeout=60)
        r.raise_for_status()
        j = r.json()
        st = j.get("status")
        if st == "completed":
            return j
        if st in ("failed", "nsfw", "canceled"):
            raise RuntimeError(f"Higgsfield request {request_id} ended with status={st}: {j.get('error')}")
        time.sleep(delay + random.uniform(0, 0.5))
        delay = min(delay * 1.5, 10)
    raise TimeoutError(f"Higgsfield request {request_id} timed out")


def estimate_i2v(duration: int = 5) -> float:
    return round(I2V_USD_PER_S * duration, 3)


def image_to_video(image_url: str, prompt: str, duration: int = 5) -> str:
    """Returns the video URL. Enforces HIGGSFIELD_MAX_USD before submitting."""
    est = estimate_i2v(duration)
    costs.guard_higgsfield(est)
    if costs.is_dry():
        costs.log(costs.CostEntry("higgsfield", "kling-2.5-turbo", "i2v", est_usd=est, dry_run=True))
        raise RuntimeError("DRY_RUN=1 — Higgsfield call skipped")
    r = requests.post(f"{BASE}{I2V_PATH}", headers=_h(), timeout=60, json={
        "prompt": prompt[:1500], "image_url": image_url, "duration": duration, "cfg_scale": 0.5,
        "negative_prompt": "text, watermark, distorted label, extra products, deformed hands, blurry"})
    r.raise_for_status()
    rid = r.json()["request_id"]
    j = _poll(rid)
    costs.log(costs.CostEntry("higgsfield", "kling-2.5-turbo", "i2v", est_usd=est, actual_usd=est, units=f"{duration}s"))
    return j["video"]["url"]


def text_to_image(prompt: str, aspect_ratio: str = "1:1", seed: int = 7) -> bytes:
    costs.guard_higgsfield(T2I_USD)
    if costs.is_dry():
        raise RuntimeError("DRY_RUN=1")
    r = requests.post(f"{BASE}{T2I_PATH}", headers=_h(), timeout=60, json={
        "prompt": prompt[:1500], "aspect_ratio": aspect_ratio, "resolution": "720p", "seed": seed})
    r.raise_for_status()
    j = _poll(r.json()["request_id"], timeout_s=240)
    costs.log(costs.CostEntry("higgsfield", "soul", "t2i", est_usd=T2I_USD, actual_usd=T2I_USD, units="1 image"))
    url = j["images"][0]["url"]
    return requests.get(url, timeout=120).content
