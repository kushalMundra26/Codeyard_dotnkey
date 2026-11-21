"""Claims checker — rules first (deterministic gate), optional LLM second opinion that can only ADD warnings.

Blocks:  medical / absolute claims, banned brand words, SPF/PA not matching the enriched spec, naming or
         disparaging competitors (ASCI), and any claim on a topic where D&K's OWN reviews are net negative.
"""
from __future__ import annotations

import re

from ..config import brand_inputs, brands, home_brand

MEDICAL = [r"\bcures?\b", r"\btreats?\b", r"\bheals?\b", r"\bprevents? (?:skin )?cancer\b", r"100\s*% safe",
           r"\bclinically proven\b", r"\bdermatologist recommended\b", r"\bpermanent(?:ly)?\b", r"\bguarantee",
           r"\bmiracle\b", r"\bside[- ]effect[- ]free\b", r"\bchemical[- ]free\b", r"\bfairness\b", r"\bwhiten"]
SUPERLATIVE = [r"\bbest\b", r"#\s*1\b", r"\bno\.?\s*1\b", r"\bnumber one\b", r"\bonly sunscreen\b", r"\bunbeatable\b"]
TOPIC_PATTERNS = {
    "white_cast": [r"white\s*cast", r"\bcast\b", r"\bashy\b", r"invisible", r"no residue"],
    "greasy_sticky": [r"greas", r"stick(?:y|iness)", r"\boily\b", r"non[- ]?greasy", r"weightless"],
    "breakouts": [r"break\s*out", r"acne", r"pimple", r"non[- ]comedogenic", r"irritat", r"gentle"],
    "eye_sting": [r"\bsting", r"\beyes?\b", r"tear[- ]free"],
    "makeup_pilling": [r"pill(?:ing)?", r"under make\s*up", r"makeup[- ]friendly", r"primer"],
    "fragrance": [r"fragrance", r"\bscent", r"\bsmell"],
    "tan_protection": [r"\btan\b", r"de-?tan", r"sunburn", r"protect"],
    "texture": [r"lightweight", r"light[- ]weight", r"absorbs?", r"texture", r"blends?"],
    "finish": [r"\bmatte\b", r"\bdewy\b", r"\bglow"],
    "value": [r"\bvalue\b", r"affordable", r"worth"],
}


def topic_hits(text: str) -> list[str]:
    t = text.lower()
    return [k for k, pats in TOPIC_PATTERNS.items() if any(re.search(p, t) for p in pats)]


def check(text: str, spec: dict, own_topic_net: dict[str, dict], rival_names: list[str] | None = None) -> dict:
    """Return {'verdict': ok|warn|block, 'reasons': [...], 'topics': [...]} for one line of copy.
    own_topic_net: {topic: {'net': float, 'n': int, 'review_ids': [...]}} for the D&K product (or D&K overall)."""
    reasons, verdict = [], "ok"
    low = text.lower()

    def bump(v, r):
        nonlocal verdict
        order = {"ok": 0, "warn": 1, "block": 2}
        if order[v] > order[verdict]:
            verdict = v
        reasons.append({"level": v, "reason": r})

    for p in MEDICAL:
        if re.search(p, low):
            bump("block", f"Medical/absolute claim ('{re.search(p, low).group(0)}') — not allowed under ASCI/CDSCO norms.")
    for w in brand_inputs().get("banned_words", []):
        if re.search(rf"\b{re.escape(w.lower())}\b", low):
            bump("block", f"Banned brand word: '{w}'.")
    for p in SUPERLATIVE:
        if re.search(p, low):
            bump("warn", "Superlative needs substantiation (ASCI Chapter I).")
    m = re.search(r"spf\s*(\d{2,3})", low)
    if m:
        if spec.get("spf") is None:
            bump("block", f"Claims SPF {m.group(1)} but the product's SPF could not be verified from its listing.")
        elif int(m.group(1)) != int(spec["spf"]):
            bump("block", f"SPF {m.group(1)} does not match the product (SPF {spec['spf']}).")
    m = re.search(r"pa\s*(\+{2,4})", low)
    if m and spec.get("pa") and ("PA" + m.group(1)) != spec["pa"]:
        bump("block", f"PA{m.group(1)} does not match the product ({spec['pa']}).")
    names = rival_names or [b["name"] for k, b in brands()["brands"].items() if k != home_brand()]
    for n in names:
        if re.search(rf"\b{re.escape(n.lower())}\b", low):
            bump("block", f"Names a competitor ('{n}') — comparative ads need ASCI-grade substantiation.")
    topics = topic_hits(text)
    for t in topics:
        d = own_topic_net.get(t)
        if not d or d.get("n", 0) < 3:
            continue
        if d["net"] < 0:
            bump("block", f"⚠️ Our own reviews disagree: {t.replace('_', ' ')} net sentiment {d['net']:+.2f} (n={d['n']}).")
        elif d["net"] < 0.3:
            bump("warn", f"Mixed reviews on {t.replace('_', ' ')} (net {d['net']:+.2f}, n={d['n']}) — soften the claim.")
    return {"verdict": verdict, "reasons": reasons, "topics": topics,
            "evidence": [rid for t in topics for rid in (own_topic_net.get(t) or {}).get("review_ids", [])[:3]]}


def check_many(lines: list[str], spec: dict, own_topic_net: dict) -> list[dict]:
    return [{"text": l} | check(l, spec, own_topic_net) for l in lines if l and l.strip()]
