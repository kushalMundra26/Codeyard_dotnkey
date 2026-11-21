"""Marketplace snapshot (Amazon.in / Nykaa / Flipkart): price, rating, rating count, bestseller rank.

Source: collected with Gemini + Google Search grounding from the listing pages themselves (prompt in README),
saved as JSON, imported here. Shown with a 'verify the link' label and every URL; NEVER mixed into the
review statistics (those come only from the brands' own review-widget feeds)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import MARKET_DIR, brands

_MD_LINK = re.compile(r"^\[(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)$")
FIELDS = ["brand", "product_name_on_listing", "marketplace", "url", "price_inr", "mrp_inr", "rating", "rating_count",
          "bestseller_rank", "badges", "top_complaints", "checked_at", "pack"]


def _clean_url(u):
    if not isinstance(u, str):
        return None
    u = u.strip()
    m = _MD_LINK.match(u)
    if m:
        u = m.group("url")
    return u if u.startswith("http") else None


def brand_key(name: str) -> str | None:
    n = (name or "").lower().replace("’", "'")
    for k, b in brands()["brands"].items():
        if b["name"].lower() == n or k == n.replace(" ", "").replace("'", "").replace("&", "and"):
            return k
    return None


def normalise(rows: list[dict], source: str = "gemini+google-search") -> list[dict]:
    out = []
    for r in rows:
        url = _clean_url(r.get("url"))
        if not url:
            continue  # unverifiable → dropped
        rec = {k: r.get(k) for k in FIELDS}
        rec["url"] = url
        rec["brand_key"] = brand_key(r.get("brand", ""))
        rec["source"] = source
        # verbatim snippets only; drop empty
        rec["top_complaints"] = [c for c in (r.get("top_complaints") or []) if c.get("snippet")]
        if rec["price_inr"] and rec["mrp_inr"] and rec["mrp_inr"] > rec["price_inr"]:
            rec["discount_pct"] = round((1 - rec["price_inr"] / rec["mrp_inr"]) * 100, 1)
        out.append(rec)
    return out


def import_file(path: str | Path, date: str | None = None) -> Path:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    recs = normalise(rows)
    d = date or (recs[0]["checked_at"] if recs and recs[0].get("checked_at") else "undated")
    out = MARKET_DIR / f"marketplace_{d}.json"
    out.write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load(date: str | None = None) -> list[dict]:
    files = sorted(MARKET_DIR.glob("marketplace_*.json"))
    if not files:
        return []
    f = MARKET_DIR / f"marketplace_{date}.json" if date else files[-1]
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
