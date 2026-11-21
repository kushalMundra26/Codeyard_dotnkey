"""E-commerce copy (description, Amazon title + 5 bullets, 5 A+ modules, SEO keywords from customers' words),
ad variants and the video script — all generated from the brief + research, with evidence ids."""
from __future__ import annotations

import re
from collections import Counter

from .. import llm
from ..config import brand_inputs
from ..evidence import EvidenceIndex, validate
from ..schemas import AdSet, EcomCopy, Script
from .brief import research_digest

SYS = ("You are Dot & Key's senior copywriter (India). Voice: {tone} Write ONLY claims supported by the research; cite "
       "evidence ids copied exactly from the research. Never use: {banned}. Never name competitors. Never state an "
       "SPF/PA different from the spec. No medical claims (cure/treat/heal). Indian English, ₹ prices.")


def _sys():
    bi = brand_inputs()
    return SYS.format(tone=bi["tone"], banned=", ".join(bi["banned_words"]))


def customer_keywords(quotes: list[dict], reviews: list[dict], n: int = 15) -> list[str]:
    """SEO keywords mined from customers' own words (bigrams in positive reviews)."""
    text = " ".join((r.get("body") or "") for r in reviews if (r.get("rating") or 0) >= 4).lower()
    toks = re.findall(r"[a-z]+", text)
    stop = set("i it is the a an and or to of for this that my me was very so but in on with have has not are be "
               "its am really also just too can will product skin use using used".split())
    bigrams = Counter(f"{a} {b}" for a, b in zip(toks, toks[1:]) if a not in stop and b not in stop and len(a) > 2 and len(b) > 2)
    return [b for b, _ in bigrams.most_common(n)]


def ad_variants(ctx: dict, brief: dict, persona: dict, index: EvidenceIndex, n: int = 3) -> tuple[list[dict], str]:
    prompt = (f"{research_digest(ctx)}\n\nBRIEF: {brief}\nPERSONA: {persona['name']} — {persona['detail']}\n"
              f"CTA options: {brand_inputs()['cta_options']}\n\nWrite {n} distinct static-ad variants "
              f"(different angles: one benefit-led, one problem/solution, one social-proof using a real customer phrase). "
              f"scene_prompt describes a photographic background only, matching the persona's world and the product's "
              f"fruit active (e.g. sliced watermelon on wet stone, sunlit Kolkata balcony) — no product, no text.")
    try:
        res = llm.structured(prompt, AdSet, system=_sys(), purpose="ads", max_tokens=4000, effort="medium")
        vs = [v.model_dump() for v in res.variants]
        kept, _ = validate(vs, index)
        if kept:
            return kept[:n], "llm"
    except Exception:
        pass
    return template_variants(ctx, brief, persona), "template"


def template_variants(ctx: dict, brief: dict, persona: dict) -> list[dict]:
    p, s = ctx["product"], ctx["product"].get("spec", {})
    fruit = next((i for i in (s.get("key_ingredients") or []) if i in ("watermelon", "strawberry", "mango", "lime",
                                                                       "dragon fruit", "vitamin c", "cica")), "fresh fruit")
    good = [t for t in ctx["own_topics"] if t["net"] > 0.3 and t["n"] >= 3]
    good.sort(key=lambda t: -t["n"])
    pos_q = [q for q in ctx["quotes"] if q["sentiment"] > 0 and 15 < len(q["quote"]) < 70]
    spf = f"SPF {s['spf']}" if s.get("spf") else "Sun care"
    ev = [pp["evidence"][0] for pp in brief.get("proof_points", []) if pp.get("evidence")] or \
         [f"m:net:{t['brand']}:{t['topic']}|{t['handle']}" for t in good[:1]]
    v = [{"headline": f"{spf}, minus the heavy feel", "subline": brief["key_message"][:90],
          "cta": "Shop now", "scene_prompt": f"sliced {fruit} on wet pale stone, morning sunlight, water droplets",
          "why": brief["insight"], "evidence": ev[:2]}]
    if good:
        t = good[0]
        v.append({"headline": f"Loved for its {t['label'].lower().split(' (')[0]}", "subline": f"Net {t['net']:+.2f} across {t['n']} real reviews.",
                  "cta": "Grab yours", "scene_prompt": f"sunlit Indian balcony with plants and {fruit}, warm afternoon light",
                  "why": f"Top positive topic for this product ({t['label']}).", "evidence": [f"m:net:{t['brand']}:{t['topic']}|{t['handle']}"]})
    if pos_q:
        q = pos_q[0]
        v.append({"headline": f"“{q['quote'][:46]}”", "subline": "— a verified Dot & Key customer", "cta": "Try it today",
                  "scene_prompt": f"pastel bathroom shelf with soft shadows and {fruit} slices", "why": "Social proof in the customer's own words.",
                  "evidence": [q["review_id"]]})
    return v


def ecom_copy(ctx: dict, brief: dict, reviews: list[dict], index: EvidenceIndex) -> tuple[dict, str]:
    kws = customer_keywords(ctx["quotes"], reviews)
    prompt = (f"{research_digest(ctx)}\n\nBRIEF: {brief}\nCUSTOMER PHRASES for SEO (use the most relevant): {kws}\n\n"
              "Write: product_description (120-160 words), amazon_title (≤180 chars: Brand + product + SPF/PA + key benefit "
              "+ size), exactly 5 bullets (each starts with a 2-4 word CAPS benefit), exactly 5 A+ modules, 10-15 seo_keywords.")
    try:
        c = llm.structured(prompt, EcomCopy, system=_sys(), purpose="ecom", max_tokens=6000, effort="medium")
        d = c.model_dump()
        d["aplus"], _ = validate(d["aplus"], index)
        d["evidence"] = index.clean(d["evidence"])
        return d, "llm"
    except Exception:
        return template_ecom(ctx, brief, kws), "template"


def template_ecom(ctx: dict, brief: dict, kws: list[str]) -> dict:
    p, s = ctx["product"], ctx["product"].get("spec", {})
    spfpa = " ".join(x for x in [f"SPF {s['spf']}" if s.get("spf") else "", s.get("pa") or ""] if x)
    ings = ", ".join((s.get("key_ingredients") or [])[:3])
    size = f"{p['size']:.0f}{p['unit']}" if p.get("size") else ""
    bullets = [f"{pp['text'].split(' (')[0].upper()[:28]} — {pp['text']}" for pp in brief["proof_points"][:3]]
    bullets += [f"KEY ACTIVES — {ings or 'see ingredient list'}.", f"DAILY PROTECTION — {spfpa or 'sun care'}; reapply every 2–3 hours outdoors."]
    ev = [e for pp in brief["proof_points"] for e in pp.get("evidence", [])]
    return {"product_description": f"{p['title']}. {brief['key_message']} {brief['insight']}",
            "amazon_title": f"Dot & Key {p['title']} {size}".strip()[:180], "bullets": bullets[:5],
            "aplus": [{"title": pp["text"][:40], "body": pp["text"], "image_idea": "macro texture shot", "evidence": pp["evidence"]}
                      for pp in brief["proof_points"]], "seo_keywords": kws[:12], "evidence": ev}


def script(ctx: dict, brief: dict, persona: dict, duration: int, index: EvidenceIndex) -> tuple[dict, str]:
    n = 6
    prompt = (f"{research_digest(ctx)}\n\nBRIEF: {brief}\nPERSONA: {persona['name']} — {persona['detail']}\n\n"
              f"Write a {duration}-second vertical video ad script with exactly {n} frames covering 0→{duration}s. "
              f"Hook in the first 2 seconds (a relatable problem from the reviews). Voiceover lines short enough to "
              f"speak in each frame's time (~2.5 words/second). End frame = product + CTA. Also a 2-3 sentence video_concept "
              f"for a premium AI film, and music_mood.")
    try:
        sc = llm.structured(prompt, Script, system=_sys(), purpose=f"script{duration}", max_tokens=4000, effort="medium")
        d = sc.model_dump()
        d["evidence"] = index.clean(d["evidence"])
        return d, "llm"
    except Exception:
        return template_script(ctx, brief, duration), "template"


def template_script(ctx: dict, brief: dict, duration: int) -> dict:
    p, s = ctx["product"], ctx["product"].get("spec", {})
    top_c = ctx["complaints"][0]["label"].lower() if ctx["complaints"] else "heavy, sticky sunscreen"
    step = duration / 6
    beats = [("Close-up: hand wiping sweaty forehead in harsh sun", "Sunscreen feels heavy?", f"Tired of {top_c}?"),
             ("Fruit slices splash in slow motion", "Meet the fix", f"Meet {p['title'].split(' SPF')[0]}."),
             ("Texture swatch spreading on skin", "Light. Fast. Done.", brief["key_message"]),
             ("Commute montage: metro, auto, sunlight", "All-day ready", "From metro to meetings, it stays comfortable."),
             ("Customer quote card", "Real reviews", (brief["proof_points"][0]["text"][:90] if brief["proof_points"] else "Loved by thousands.")),
             ("Product hero shot + CTA", "Shop now", f"Dot and Key. {'SPF ' + str(s['spf']) if s.get('spf') else ''} Shop now.")]
    frames = [{"t_start": round(i * step, 1), "t_end": round((i + 1) * step, 1), "visual": v, "on_screen_text": o,
               "voiceover": vo, "scene_prompt": v + ", no people's faces, no text"} for i, (v, o, vo) in enumerate(beats)]
    return {"title": f"{p['title']} — {duration}s", "duration_s": duration, "hook": frames[0]["voiceover"], "frames": frames,
            "video_concept": "A juicy, sunlit day-in-the-life film: fruit actives burst into the frame and dissolve into a weightless texture.",
            "music_mood": "upbeat indie-pop, light percussion",
            "evidence": [e for pp in brief["proof_points"] for e in pp.get("evidence", [])]}
