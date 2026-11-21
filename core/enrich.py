"""L2 Enrich — product specs. Deterministic rule extractor first, then one cached LLM call per
product to fill what rules can't (format, finish, claims). Regex-found SPF/PA always win."""
from __future__ import annotations

import json
import re

from . import llm
from .config import ENRICHED
from .schemas import ProductSpec

INGREDIENTS = [
    "niacinamide", "hyaluronic acid", "vitamin c", "vitamin e", "ceramide", "cica", "centella", "zinc oxide",
    "titanium dioxide", "watermelon", "strawberry", "mango", "dragon fruit", "lime", "aloe vera", "green tea",
    "squalane", "peptide", "panthenol", "allantoin", "glycerin", "salicylic acid", "retinol", "bakuchiol",
    "kakadu plum", "licorice", "rice", "turmeric", "saffron", "tinosorb", "uvinul", "avobenzone", "octocrylene",
    "mexoryl", "beta glucan", "probiotic", "blueberry", "raspberry", "cucumber", "sandalwood", "gotu kola",
    "red algae", "tranexamic acid", "alpha arbutin", "kojic acid", "azelaic acid", "mulberry", "ectoin",
]
CHEM_FILTERS = ["tinosorb", "uvinul", "avobenzone", "octocrylene", "mexoryl", "homosalate", "octinoxate",
                "ethylhexyl", "bemotrizinol", "bisoctrizole", "diethylamino"]
MINERAL = ["zinc oxide", "titanium dioxide"]
FORMATS = ["gel", "cream", "lotion", "fluid", "stick", "spray", "mist", "serum", "balm", "essence", "drops",
           "mousse", "sunstick", "aqua", "emulsion", "butter", "oil", "mask"]
SKIN = {"oily": ["oily"], "dry": ["dry skin", "dry"], "combination": ["combination"], "sensitive": ["sensitive"],
        "acne-prone": ["acne", "acne-prone", "acne prone"], "normal": ["normal skin"], "all": ["all skin types", "all skin type"]}
CLAIMS = {"no white cast": ["no white cast", "zero white cast", "without white cast", "no whitecast"],
          "non-greasy": ["non-greasy", "non greasy", "not greasy", "non-sticky", "non sticky"],
          "water resistant": ["water resistant", "water-resistant", "sweat resistant", "waterproof", "sweat-proof"],
          "lightweight": ["lightweight", "light weight", "featherlight"],
          "matte finish": ["matte"], "dewy finish": ["dewy", "glow"],
          "fragrance free": ["fragrance free", "fragrance-free", "no fragrance"],
          "broad spectrum": ["broad spectrum", "uva", "uvb"], "blue light protection": ["blue light"],
          "makeup friendly": ["under makeup", "makeup-friendly", "makeup friendly", "primer"],
          "dermatologically tested": ["dermatologically tested", "dermatologist tested"],
          "in-vivo tested": ["in-vivo", "in vivo"], "reef safe": ["reef safe", "reef-safe"],
          "oil control": ["oil control", "oil-control", "controls oil", "sebum"], "detan": ["de-tan", "detan", "tan removal"],
          "hydrating": ["hydrat", "moistur"], "soothing": ["sooth", "calm"], "brightening": ["brighten", "glow"],
          "non-comedogenic": ["non-comedogenic", "non comedogenic"], "pregnancy safe": ["pregnancy safe"]}


def rule_spec(row: dict) -> dict:
    text = f"{row['title']} {row['product_type']} {' '.join(row.get('tags', []))} {row.get('body_text', '')}".lower()
    spf = None
    m = re.search(r"spf\s*[-:]?\s*(\d{2,3})\+?", text)
    if m:
        spf = int(m.group(1))
    pa = None
    m = re.search(r"pa\s*(\+{2,4})", text)
    if m:
        pa = "PA" + m.group(1)
    ings = sorted({i for i in INGREDIENTS if i in text})
    has_chem = any(c in text for c in CHEM_FILTERS)
    has_min = any(c in text for c in MINERAL)
    filt = "hybrid" if has_chem and has_min else "mineral" if has_min else "chemical" if has_chem else None
    if filt is None and "mineral" in row["title"].lower():
        filt = "mineral"
    title_l = row["title"].lower()
    fmt = next((f for f in FORMATS if re.search(rf"\b{f}\b", title_l)), None) or \
          next((f for f in FORMATS if re.search(rf"\b{f}\b", text[:800])), None)
    if fmt == "sunstick":
        fmt = "stick"
    tinted = True if "tint" in title_l else None
    finish = "tinted" if tinted else ("matte" if "matte" in title_l else "dewy" if "dewy" in title_l or "glow" in title_l else None)
    skin = sorted({k for k, kws in SKIN.items() if any(kw in text for kw in kws)})
    claims = sorted({k for k, kws in CLAIMS.items() if any(kw in text for kw in kws)})
    ff = True if "fragrance free" in text or "fragrance-free" in text else None
    return {"spf": spf, "pa": pa, "filter_type": filt, "finish": finish, "tinted": tinted, "format": fmt,
            "key_ingredients": ings, "skin_types": skin, "claims": claims, "fragrance_free": ff, "reef_safe": None}


SYSTEM = ("You extract product specifications for Indian skincare products from the brand's own listing text. "
          "Only use facts stated in the text. If a field is not stated, return null (or an empty list). Never guess.")


def llm_spec(row: dict) -> dict | None:
    if not llm.available():
        return None
    prompt = (f"Brand: {row['brand']}\nTitle: {row['title']}\nType: {row['product_type']}\n"
              f"Tags: {', '.join(t for t in row.get('tags', []) if not t.startswith('_'))[:600]}\n"
              f"Description: {row.get('body_text', '')[:3000]}")
    try:
        return llm.structured(prompt, ProductSpec, system=SYSTEM, purpose="enrich", bulk=True,
                              max_tokens=2000, effort="low").model_dump()
    except Exception:
        return None


def merge(rule: dict, ai: dict | None) -> dict:
    if not ai:
        return rule | {"source": "rules"}
    out = dict(ai)
    for k in ("spf", "pa"):
        if rule.get(k) is not None:
            out[k] = rule[k]          # deterministic text match wins
    for k in ("key_ingredients", "skin_types", "claims"):
        out[k] = sorted({*(x.lower().strip() for x in ai.get(k) or []), *rule.get(k, [])})
    for k in ("filter_type", "format", "finish", "tinted", "fragrance_free"):
        if out.get(k) is None:
            out[k] = rule.get(k)
    return out | {"source": "rules+llm"}


def enrich_rows(rows: list[dict], use_llm: bool = True, progress=None) -> list[dict]:
    path = ENRICHED / "specs.json"
    store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    out = []
    for i, r in enumerate(rows):
        key = f"{r['brand']}:{r['handle']}"
        rule = rule_spec(r)
        prev = store.get(key)
        if prev and prev.get("source") == "rules+llm":
            spec = prev
        else:
            spec = merge(rule, llm_spec(r) if use_llm else None)
        store[key] = spec
        out.append(r | {"spec": spec})
        if progress:
            progress(i + 1, len(rows), r["title"])
    path.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load_specs() -> dict:
    p = ENRICHED / "specs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
