"""Everything the Settings & data page needs, so no terminal is required:
key status / save (writes .env), catalogue fetch (polite, one try per store), seed catalogue,
marketplace JSON import, review refresh, connection tests."""
from __future__ import annotations

import json
import os
import re
import tempfile

from .config import ROOT, brand_list, brand_name

KEYS = [
    ("GEMINI_API_KEY", "Gemini", "AI analysis + copy (or set ANTHROPIC_API_KEY)"),
    ("ANTHROPIC_API_KEY", "Anthropic Claude", "AI analysis + copy (preferred if set)"),
    ("SARVAM_API_KEY", "Sarvam", "Hindi / Bengali translation + voiceover"),
    ("CF_ACCOUNT_ID", "Cloudflare account ID", "FLUX backgrounds (with token)"),
    ("CF_API_TOKEN", "Cloudflare API token", "FLUX backgrounds"),
    ("HIGGSFIELD_API_KEY", "Higgsfield key ID", "paid hero video clip"),
    ("HIGGSFIELD_API_SECRET", "Higgsfield secret", "paid hero video clip"),
    ("TELEGRAM_BOT_TOKEN", "Telegram bot token", "alerts + approvals"),
    ("TELEGRAM_CHAT_ID", "Telegram chat ID", "where alerts go"),
    ("N8N_APPROVAL_WEBHOOK_URL", "n8n approval webhook", "optional; Telegram direct otherwise"),
]
ENV = ROOT / ".env"


def key_status() -> list[dict]:
    return [{"key": k, "label": l, "purpose": p, "set": bool(os.environ.get(k))} for k, l, p in KEYS]


def save_keys(values: dict[str, str]) -> list[str]:
    """Write non-empty values to .env and the live environment. Never returns or logs the values."""
    s = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    changed = []
    for k, v in values.items():
        v = (v or "").strip()
        if not v:
            continue
        line = f"{k}={v}"
        s = re.sub(rf"^{k}=.*$", line, s, flags=re.M) if re.search(rf"^{k}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
        os.environ[k] = v
        changed.append(k)
    if changed and not os.environ.get("LLM_PROVIDER"):
        pass
    if "GEMINI_API_KEY" in changed and not os.environ.get("ANTHROPIC_API_KEY"):
        s = re.sub(r"^LLM_PROVIDER=.*$", "LLM_PROVIDER=gemini", s, flags=re.M)
        os.environ["LLM_PROVIDER"] = "gemini"
    ENV.write_text(s, encoding="utf-8")
    return changed


def fetch_catalogues(log=print) -> dict:
    """One polite attempt per store (no retries on 429 — we respect the limit)."""
    from .collect.catalog import fetch_catalog, save_snapshot
    out = {}
    for b in brand_list():
        try:
            prods = fetch_catalog(b)
            save_snapshot(b, prods)
            out[b] = len(prods)
        except Exception as e:
            out[b] = str(e)[:80]
        log(f"{brand_name(b)}: {out[b]}")
    return out


def seed_catalogue(log=print) -> list[str]:
    from .collect.seed import build_seed
    return build_seed(log=log)


def import_marketplace_json(text: str) -> int:
    """Accepts the JSON array produced by the Gemini marketplace prompt (README)."""
    from . import marketplace
    rows = json.loads(text)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    marketplace.import_file(f.name)
    return len(marketplace.load())


def test_connections() -> dict:
    from . import llm
    from .providers import cloudflare, higgsfield, sarvam, telegram
    res = {"llm": llm.provider(), "sarvam": sarvam.available(), "cloudflare": cloudflare.available(),
           "higgsfield": higgsfield.available(), "telegram": telegram.available()}
    if llm.available():
        try:
            from pydantic import BaseModel

            class Ping(BaseModel):
                ok: bool
            llm.structured("Return ok=true.", Ping, purpose="ping", max_tokens=200, effort="low", use_cache=False)
            res["llm_test"] = "ok"
        except Exception as e:
            res["llm_test"] = str(e)[:160]
    return res
