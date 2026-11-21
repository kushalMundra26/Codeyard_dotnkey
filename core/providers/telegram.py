"""Telegram Bot API (direct fallback for n8n). https://core.telegram.org/bots/api
sendMessage {chat_id, text ≤4096, parse_mode, reply_markup}; sendPhoto / sendVideo / sendDocument multipart
(caption ≤1024; reply_markup must be a JSON string in multipart)."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from ..config import env


def available() -> bool:
    return bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"))


def _url(m: str) -> str:
    return f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/{m}"


def _public(u: str) -> bool:
    return u.startswith("https://") and "localhost" not in u and "127.0.0.1" not in u


def _kb(buttons: list[tuple[str, str]] | None):
    """Telegram rejects inline-button URLs that aren't public (e.g. localhost)."""
    if not buttons or not all(_public(u) for _, u in buttons):
        return None
    return {"inline_keyboard": [[{"text": t, "url": u} for t, u in buttons]]}


def _links_text(buttons) -> str:
    if not buttons or _kb(buttons):
        return ""
    return "\n\n" + "\n".join(f"{t}: {u}" for t, u in buttons)


def send_message(text: str, buttons: list[tuple[str, str]] | None = None) -> dict:
    body = {"chat_id": env("TELEGRAM_CHAT_ID"), "text": (text + _links_text(buttons))[:4096], "parse_mode": "HTML",
            "disable_web_page_preview": True}
    if _kb(buttons):
        body["reply_markup"] = _kb(buttons)
    r = requests.post(_url("sendMessage"), json=body, timeout=30)
    return r.json()


def send_file(kind: str, path: str | Path, caption: str = "", buttons=None) -> dict:
    field = {"sendPhoto": "photo", "sendVideo": "video", "sendDocument": "document"}[kind]
    data = {"chat_id": env("TELEGRAM_CHAT_ID"), "caption": (caption + _links_text(buttons))[:1024], "parse_mode": "HTML"}
    if _kb(buttons):
        data["reply_markup"] = json.dumps(_kb(buttons))
    with open(path, "rb") as f:
        r = requests.post(_url(kind), data=data, files={field: f}, timeout=120)
    return r.json()
