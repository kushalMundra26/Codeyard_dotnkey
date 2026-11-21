"""Listing audit (before/after): what D&K's current copy stresses vs what customers actually talk about."""
from __future__ import annotations

from . import llm
from .creative.brief import research_digest
from .creative.claims import TOPIC_PATTERNS, topic_hits
from .evidence import EvidenceIndex
from .schemas import ListingAudit


def coverage_score(ctx: dict) -> dict:
    """Deterministic score: share of customer attention (mentions) whose topic the listing copy addresses."""
    copy = ctx["product"].get("body_text", "") + " " + ctx["product"]["title"]
    covered = set(topic_hits(copy))
    topics = sorted(ctx["own_topics"], key=lambda t: -t["n"])
    total = sum(t["n"] for t in topics) or 1
    attention_covered = sum(t["n"] for t in topics if t["topic"] in covered)
    rows = [{"topic": t["topic"], "label": t["label"], "mentions": t["n"], "net": t["net"],
             "in_listing": t["topic"] in covered,
             "action": ("Lead with it" if t["net"] > 0.3 and t["topic"] not in covered else
                        "Remove / soften" if t["net"] < 0 and t["topic"] in covered else
                        "Keep" if t["topic"] in covered else "Address honestly" if t["net"] < 0 else "Consider")}
            for t in topics]
    return {"score": round(attention_covered / total * 100), "rows": rows, "covered": sorted(covered),
            "listing_words": len(copy.split())}


SYSTEM = ("You audit Dot & Key's product listing against what customers say in reviews. Identify which customer topics the "
          "copy covers, which it misses, and any lines that over-promise where reviews disagree. Then rewrite the description "
          "(120-170 words) to lead with what customers love, address top concerns honestly, keep every factual spec, and cite "
          "evidence ids. No medical claims, no competitor names.")


def run_audit(ctx: dict, index: EvidenceIndex) -> tuple[dict, str]:
    base = coverage_score(ctx)
    prompt = (f"{research_digest(ctx)}\n\nDETERMINISTIC COVERAGE: listing covers {base['covered']}; "
              f"attention-weighted coverage {base['score']}%.\nCURRENT LISTING:\n{ctx['product'].get('body_text', '')[:2500]}")
    try:
        a = llm.structured(prompt, ListingAudit, system=SYSTEM, purpose="audit", max_tokens=4000, effort="medium")
        d = a.model_dump()
        d["evidence"] = index.clean(d["evidence"])
        return base | {"llm": d}, "llm"
    except Exception:
        lead = [r["label"].lower() for r in base["rows"] if r["action"] == "Lead with it"][:3]
        p = ctx["product"]
        rew = (f"{p['title']}. " + (f"Customers keep coming back for its {', '.join(lead)}. " if lead else "") +
               p.get("body_text", "")[:500])
        return base | {"llm": {"covered_topics": base["covered"], "missing_topics": lead, "risky_lines": [],
                               "score_rationale": "Rule-based coverage (no LLM configured).",
                               "rewritten_description": rew, "evidence": []}}, "template"
