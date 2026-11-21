"""SignalStudio MCP server (agent mode). Exposes the pipeline as tools for Claude Desktop / Claude Code.

Run:  .venv/bin/python mcp_server.py          (stdio transport)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x; FastMCP was renamed)

from core import pipeline  # noqa: E402
from core.config import brand_name, home_brand  # noqa: E402

mcp = MCPServer("signalstudio", instructions="Dot & Key market intelligence → marketing content pipeline.")


def _ins(category: str):
    ins = pipeline.load_insights(category)
    if ins is None:
        raise ValueError(f"No analysis for {category}. Call run_analysis first.")
    return ins


@mcp.tool()
def list_products(category: str = "sunscreen", brand: str = "dotandkey") -> list[dict]:
    """List products in a category for a brand key (dotandkey, minimalist, foxtale, ...), with price, ₹/ml and spec."""
    return [{"handle": p["handle"], "title": p["title"], "price": p["price"], "price_per_ml": p.get("price_per_ml"),
             "spf": (p.get("spec") or {}).get("spf"), "url": p["url"]}
            for p in _ins(category)["products"] if p["brand"] == brand]


@mcp.tool()
def get_rivals(product: str, category: str = "sunscreen") -> list[dict]:
    """Top-5 rival products for a Dot & Key product handle, with explainable match score and reason."""
    ctx = pipeline.product_context(_ins(category), product)
    return [{"brand": r["brand_name"], "title": r["title"], "price": r["price"], "score": r["match"]["score"],
             "parts": r["match"]["parts"], "reason": r["match"]["reason"]} for r in ctx["rivals"]]


@mcp.tool()
def review_insights(product: str, category: str = "sunscreen") -> dict:
    """Topic × sentiment for a Dot & Key product (pandas-computed), with real customer quotes and review ids."""
    ctx = pipeline.product_context(_ins(category), product)
    return {"topics": [{k: t[k] for k in ("label", "n", "net")} for t in ctx["own_topics"]],
            "quotes": [{k: q[k] for k in ("review_id", "topic", "sentiment", "quote")} for q in ctx["quotes"]],
            "unmet_needs": [u["quote"] for u in ctx["unmet"][:8]], "rating": ctx.get("rating")}


@mcp.tool()
def market_gaps(category: str = "sunscreen") -> dict:
    """Category-level gaps: complaint share, opportunity estimates, whitespace and the evidenced SWOT."""
    ins = _ins(category)
    return {"complaints": ins["metrics"]["complaint_share"][:8], "opportunity_estimate": ins["opportunity"][:8],
            "whitespace": ins["whitespace"][:10], "swot": ins["strategy"]["swot"], "summary": ins["strategy"].get("summary")}


@mcp.tool()
def generate_campaign(product: str, persona: str = "college_commuter", languages: list[str] | None = None,
                      category: str = "sunscreen", make_video: bool = False) -> dict:
    """Generate a full campaign (brief, 3 ad variants × 3 sizes, e-com copy, A+, scripts, claims check) for a D&K product.
    persona: college_commuter | young_professional | outdoor_mom. languages (e.g. ['hi','bn']) adds Sarvam regional versions."""
    c = pipeline.generate_campaign(category, product, persona, make_video=make_video)
    if languages:
        c = pipeline.regional(c["id"], languages, make_video=make_video)
    return {"id": c["id"], "brief": c["brief"], "ads": [{k: v[k] for k in ("headline", "subline", "cta", "why")} | {"claims": v["claims"]["verdict"]}
                                                       for v in c["ads"]["variants"]],
            "assets": [a["path"] for a in c["ads"]["assets"]], "amazon_title": c["ecom"]["amazon_title"],
            "bullets": c["ecom"]["bullets"], "script_15s": c["script15"]["frames"], "regional": list(c.get("regional", {}).keys())}


@mcp.tool()
def radar(category: str = "sunscreen") -> dict:
    """Launch radar: snapshot diffs, rival launches in the last 45 days and a draft counter-ad."""
    r = pipeline.radar(category)
    return {"n_changes": r["n_changes"], "rival_launches": r["rival_category_launches"][:10], "counter_ad": r.get("counter_ad")}


@mcp.tool()
def run_analysis(category: str = "sunscreen", live: bool = False) -> dict:
    """(Re)run the analysis pipeline. live=True re-scrapes catalogues and review feeds (slow, polite)."""
    ins = pipeline.run_analysis(category, live=live)
    return {"products": len(ins["products"]), "reviews": sum(ins["metrics"]["n_reviews"].values()), "elapsed_s": ins["elapsed_s"]}


if __name__ == "__main__":
    mcp.run()
