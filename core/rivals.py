"""L3 Rivals — explainable weighted match score.

match = 0.35·category/format + 0.25·ingredient+claim Jaccard + 0.20·price-band closeness + 0.20·skin-type overlap
"""
from __future__ import annotations

from .config import brand_name, home_brand

W = {"format": 0.35, "ingredients": 0.25, "price": 0.20, "skin": 0.20}
FORMAT_FAMILY = {"gel": "light", "fluid": "light", "aqua": "light", "serum": "light", "essence": "light",
                 "drops": "light", "emulsion": "light", "lotion": "cream", "cream": "cream", "butter": "cream",
                 "stick": "stick", "spray": "spray", "mist": "spray", "balm": "balm", "mousse": "light"}


def jaccard(a, b) -> float:
    a, b = set(a or []), set(b or [])
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def format_score(s1: dict, s2: dict) -> float:
    f1, f2 = s1.get("format"), s2.get("format")
    if f1 and f2 and f1 == f2:
        sc = 1.0
    elif f1 and f2 and FORMAT_FAMILY.get(f1) == FORMAT_FAMILY.get(f2):
        sc = 0.7
    elif not f1 or not f2:
        sc = 0.5
    else:
        sc = 0.2
    # SPF / tint parity nudges within the format dimension
    if s1.get("spf") and s2.get("spf"):
        sc = sc * (1.0 if abs(s1["spf"] - s2["spf"]) <= 10 else 0.8)
    if bool(s1.get("tinted")) != bool(s2.get("tinted")):
        sc *= 0.8
    return sc


def price_score(p1: dict, p2: dict) -> float:
    a = p1.get("price_per_ml") or None
    b = p2.get("price_per_ml") or None
    if a and b:
        return max(0.0, 1 - abs(a - b) / max(a, b))
    if p1.get("price") and p2.get("price"):
        return max(0.0, 1 - abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"]))
    return 0.0


def score(p1: dict, p2: dict) -> dict:
    s1, s2 = p1.get("spec", {}), p2.get("spec", {})
    parts = {
        "format": format_score(s1, s2),
        "ingredients": jaccard((s1.get("key_ingredients") or []) + (s1.get("claims") or []),
                               (s2.get("key_ingredients") or []) + (s2.get("claims") or [])),
        "price": price_score(p1, p2),
        "skin": jaccard(s1.get("skin_types"), s2.get("skin_types")),
    }
    total = sum(W[k] * v for k, v in parts.items())
    return {"score": round(total, 3), "parts": {k: round(v, 2) for k, v in parts.items()}, "reason": reason(p1, p2)}


def reason(p1: dict, p2: dict) -> str:
    s1, s2 = p1.get("spec", {}), p2.get("spec", {})
    bits = []
    if s1.get("spf") and s2.get("spf"):
        same_pa = s1.get("pa") and s1.get("pa") == s2.get("pa")
        if s1["spf"] == s2["spf"]:
            bits.append(f"Same SPF {s1['spf']}" + (f" {s1['pa']}" if same_pa else ""))
        else:
            bits.append(f"SPF {s1['spf']} vs {s2['spf']}")
    if s1.get("format") and s1.get("format") == s2.get("format"):
        bits.append(f"both {s1['format']}s")
    shared = sorted(set(s1.get("key_ingredients") or []) & set(s2.get("key_ingredients") or []))
    if shared:
        bits.append("both " + ", ".join(shared[:2]))
    sc = sorted(set(s1.get("claims") or []) & set(s2.get("claims") or []))
    if sc:
        bits.append("shared claim: " + sc[0])
    if p1.get("price") and p2.get("price"):
        d = p2["price"] - p1["price"]
        bits.append(f"{'+' if d >= 0 else '−'}₹{abs(d):.0f}")
    if p1.get("price_per_ml") and p2.get("price_per_ml"):
        bits.append(f"₹{p2['price_per_ml']:.1f}/ml vs ₹{p1['price_per_ml']:.1f}/ml")
    return ", ".join(bits) or "Same category"


def top_rivals(product: dict, pool: list[dict], k: int = 5, one_per_brand: bool = True) -> list[dict]:
    cands = []
    for q in pool:
        if q["brand"] == product["brand"]:
            continue
        cands.append(q | {"match": score(product, q)})
    cands.sort(key=lambda x: x["match"]["score"], reverse=True)
    if not one_per_brand:
        return cands[:k]
    seen, out = set(), []
    for c in cands:
        if c["brand"] in seen:
            continue
        seen.add(c["brand"])
        out.append(c)
        if len(out) == k:
            break
    return out


def category_rivals(pool: list[dict], k: int = 5) -> list[dict]:
    """Top rival brands for a whole category: mean of each brand's best match against home products."""
    home = [p for p in pool if p["brand"] == home_brand()]
    agg: dict[str, list[float]] = {}
    for h in home:
        for r in top_rivals(h, pool, k=20, one_per_brand=True):
            agg.setdefault(r["brand"], []).append(r["match"]["score"])
    ranked = sorted(((b, sum(v) / len(v), len(v)) for b, v in agg.items()), key=lambda x: x[1], reverse=True)
    return [{"brand": b, "name": brand_name(b), "avg_match": round(s, 3), "n": n} for b, s, n in ranked[:k]]
