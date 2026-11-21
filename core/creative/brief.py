"""Creative brief: insight → one key message → evidenced proof points → persona → tone."""
from __future__ import annotations

from .. import llm
from ..config import brand_inputs
from ..evidence import EvidenceIndex, validate
from ..schemas import Brief

SYSTEM = ("You are Dot & Key's creative strategist. Write a tight creative brief for one product and one persona, "
          "grounded ONLY in the research provided. Every proof point must cite evidence ids copied exactly from the "
          "research (review ids 'r:...' or metric ids 'm:...'). Lead with what customers already love and what the "
          "category complains about that this product genuinely solves. Never claim a benefit where the product's own "
          "reviews are negative.")


def research_digest(ctx: dict, max_quotes: int = 24) -> str:
    p, s = ctx["product"], ctx["product"].get("spec", {})
    price = f"₹{p['price']:.0f}" if p.get("price") else "price n/a"
    lines = [f"PRODUCT: {p['title']} — {price}" + (f" ({p['size']:.0f}{p['unit']})" if p.get("size") else ""),
             f"SPEC: SPF {s.get('spf')} {s.get('pa') or ''} · format {s.get('format')} · finish {s.get('finish')} · "
             f"ingredients {', '.join(s.get('key_ingredients') or [])} · claims {', '.join(s.get('claims') or [])}",
             f"LISTING COPY (excerpt): {p.get('body_text', '')[:600]}", "", "THIS PRODUCT — topic sentiment (pandas):"]
    for t in ctx["own_topics"]:
        lines.append(f"m:net:{t['brand']}:{t['topic']}|{t['handle']} :: {t['label']} net {t['net']:+.2f} n={t['n']}")
    lines.append("\nCATEGORY COMPLAINTS (share of all complaints):")
    for c in ctx["complaints"][:8]:
        lines.append(f"m:complaint:{c['topic']} :: {c['label']} {c['share_of_complaints']:.0%} of complaints ({c['neg_reviews']} reviews)")
    lines.append("\nTOP RIVALS:")
    for r in ctx["rivals"]:
        rp = f"₹{r['price']:.0f}" if r.get("price") else "price n/a"
        lines.append(f"- {r['brand_name']}: {r['title']} {rp} — {r['match']['reason']} (score {r['match']['score']})")
    lines.append("\nCUSTOMER QUOTES (this product):")
    for q in ctx["quotes"][:max_quotes]:
        lines.append(f"{q['review_id']} :: [{q['topic']} {q['sentiment']:+d}] \"{q['quote'][:180]}\"")
    if ctx.get("unmet"):
        lines.append("\nUNMET NEEDS (customers' own words):")
        for u in ctx["unmet"][:8]:
            lines.append(f"{u['review_id']} :: \"{u['quote'][:160]}\"")
    if ctx.get("opportunities"):
        lines.append("\nOPPORTUNITY (estimate): " + "; ".join(f"{o['label']} {o['opportunity']}" for o in ctx["opportunities"][:5]))
    return "\n".join(lines)


def make_brief(ctx: dict, persona: dict, index: EvidenceIndex) -> tuple[dict, str]:
    bi = brand_inputs()
    prompt = (f"{research_digest(ctx)}\n\nPERSONA: {persona['name']} — {persona['detail']}\nBRAND TONE: {bi['tone']}\n"
              f"BANNED WORDS: {', '.join(bi['banned_words'])}\n\nWrite the brief (3-4 proof points).")
    try:
        b = llm.structured(prompt, Brief, system=SYSTEM, purpose="brief", max_tokens=3000, effort="medium")
        d = b.model_dump()
        kept, _ = validate(d["proof_points"], index)
        d["proof_points"] = kept
        return d, "llm"
    except Exception:
        return template_brief(ctx, persona), "template"


def template_brief(ctx: dict, persona: dict) -> dict:
    s = ctx["product"].get("spec", {})
    good = [t for t in ctx["own_topics"] if t["net"] > 0.3 and t["n"] >= 3]
    good.sort(key=lambda t: (-t["n"], -t["net"]))
    pp = []
    for t in good[:3]:
        q = next((q for q in ctx["quotes"] if q["topic"] == t["topic"] and q["sentiment"] > 0), None)
        pp.append({"text": f"Customers love the {t['label'].lower()} (net {t['net']:+.2f}, n={t['n']})"
                           + (f": “{q['quote'][:80]}”" if q else ""),
                   "evidence": [q["review_id"]] if q else [f"m:net:{t['brand']}:{t['topic']}|{t['handle']}"]})
    top_c = ctx["complaints"][0]["label"].lower() if ctx["complaints"] else "heavy sunscreens"
    spf = f"SPF {s['spf']}" + (f" {s['pa']}" if s.get("pa") else "") if s.get("spf") else "daily sun care"
    return {"insight": f"The category's #1 complaint is {top_c}; this product's reviewers praise "
                       f"{', '.join(t['label'].lower() for t in good[:2]) or 'its feel'}.",
            "key_message": f"{spf} that actually feels good to wear every day.",
            "proof_points": pp, "persona": persona["name"], "tone": brand_inputs()["tone"],
            "avoid": brand_inputs()["banned_words"][:6]}
