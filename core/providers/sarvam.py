"""Sarvam AI — translation (Mayura) + TTS (Bulbul v3).

Docs (verified 2026-11-21, see docs/api_reference.md):
  POST https://api.sarvam.ai/translate      header api-subscription-key
       {input (≤1000 chars mayura:v1), source_language_code, target_language_code, model, mode, speaker_gender}
       → {translated_text}
  POST https://api.sarvam.ai/text-to-speech header api-subscription-key
       {text (≤2500), language_code, model: bulbul:v3, speaker, pace, speech_sample_rate, output_audio_codec}
       → {audios: [<base64 wav>]}
"""
from __future__ import annotations

import base64
import io
import wave

import requests

from .. import cache, costs
from ..config import env

BASE = "https://api.sarvam.ai"
LANGS = {"en": "en-IN", "hi": "hi-IN", "bn": "bn-IN", "ta": "ta-IN", "mr": "mr-IN", "te": "te-IN", "gu": "gu-IN",
         "kn": "kn-IN", "ml": "ml-IN", "pa": "pa-IN", "od": "od-IN"}
LANG_NAMES = {"en": "English", "hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "mr": "Marathi"}
# bulbul:v3 speakers confirmed in Sarvam docs (change-the-speaker-voice page)
SPEAKERS_V3 = {"female": ["priya", "ritu", "neha", "pooja", "simran", "kavya", "ishita", "shreya"],
               "male": ["shubh", "aditya", "rahul", "rohan", "amit"]}
DEFAULT_SPEAKER = "priya"


class SarvamError(RuntimeError):
    pass


def available() -> bool:
    return bool(env("SARVAM_API_KEY"))


def _headers():
    return {"api-subscription-key": env("SARVAM_API_KEY"), "Content-Type": "application/json"}


def _chunks(text: str, n: int) -> list[str]:
    parts, cur = [], ""
    for s in text.replace("\n", " \n ").split(". "):
        s = s.strip()
        if not s:
            continue
        cand = (cur + ". " + s) if cur else s
        if len(cand) > n and cur:
            parts.append(cur)
            cur = s
        else:
            cur = cand
    if cur:
        parts.append(cur)
    return [p[:n] for p in parts]


def translate(text: str, target: str, source: str = "en", mode: str = "formal") -> str:
    if not text.strip() or target == source:
        return text
    if not available():
        raise SarvamError("SARVAM_API_KEY not set")
    ck = {"t": text, "tgt": target, "src": source, "mode": mode}
    hit = cache.get("sarvam_tr", ck)
    if hit:
        return hit
    out = []
    for ch in _chunks(text, 950):
        r = requests.post(f"{BASE}/translate", headers=_headers(), timeout=60, json={
            "input": ch, "source_language_code": LANGS[source], "target_language_code": LANGS[target],
            "model": "mayura:v1", "mode": mode, "speaker_gender": "Female"})
        if r.status_code != 200:
            raise SarvamError(f"translate HTTP {r.status_code}: {r.text[:300]}")
        out.append(r.json()["translated_text"])
    res = " ".join(out)
    costs.log(costs.CostEntry("sarvam", "mayura:v1", "translate", est_usd=len(text) / 10000 * 20 / costs.INR_PER_USD,
                              units=f"{len(text)} chars"))
    cache.put("sarvam_tr", ck, res)
    return res


def tts(text: str, lang: str = "en", speaker: str = DEFAULT_SPEAKER, pace: float = 1.05,
        sample_rate: int = 24000) -> bytes:
    """Returns WAV bytes (concatenated if text needed chunking)."""
    if not available():
        raise SarvamError("SARVAM_API_KEY not set")
    ck = {"t": text, "l": lang, "s": speaker, "p": pace, "sr": sample_rate}
    hit = cache.get("sarvam_tts", ck)
    if hit:
        return base64.b64decode(hit)
    frames, params = [], None
    for ch in _chunks(text, 2400):
        r = requests.post(f"{BASE}/text-to-speech", headers=_headers(), timeout=120, json={
            "text": ch, "language_code": LANGS[lang], "model": "bulbul:v3", "speaker": speaker,
            "pace": pace, "speech_sample_rate": sample_rate, "output_audio_codec": "wav"})
        if r.status_code != 200:
            raise SarvamError(f"tts HTTP {r.status_code}: {r.text[:300]}")
        wav = base64.b64decode(r.json()["audios"][0])
        with wave.open(io.BytesIO(wav)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        for f in frames:
            w.writeframes(f)
    data = buf.getvalue()
    costs.log(costs.CostEntry("sarvam", "bulbul:v3", f"tts:{lang}", est_usd=len(text) / 10000 * 25 / costs.INR_PER_USD,
                              units=f"{len(text)} chars"))
    cache.put("sarvam_tts", ck, base64.b64encode(data).decode())
    return data
