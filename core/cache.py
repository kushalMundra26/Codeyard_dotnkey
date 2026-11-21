"""Content-addressed JSON cache: key = sha256 of (namespace, payload)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .config import CACHE


def key_for(namespace: str, payload: Any) -> str:
    raw = json.dumps({"ns": namespace, "p": payload}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def get(namespace: str, payload: Any) -> Any | None:
    p = CACHE / namespace / f"{key_for(namespace, payload)}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def put(namespace: str, payload: Any, value: Any) -> None:
    d = CACHE / namespace
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key_for(namespace, payload)}.json").write_text(
        json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8"
    )
