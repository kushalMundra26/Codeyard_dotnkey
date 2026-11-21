"""L5 Strategy — gap map, whitespace, launch trends, demand forecast, opportunity score (pandas),
then SWOT / improvements / concepts / GTM from the LLM, with every point validated against evidence."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd

from . import llm
from .config import INSIGHTS, brand_name, home_brand, topic_labels
from .evidence import EvidenceIndex, validate
from .schemas import StrategyPack

HOME = None


def _home():
    return home_brand()


# ---------------- deterministic analytics ----------------

def metric_index(m: dict, products: list[dict], cat: str) -> dict[str, dict]:
    """Every number the LLM may cite, with a stable id."""
    idx: dict[str, dict] = {}
    for c in m.get("complaint_share", []):
        idx[f"m:complaint:{c['topic']}"] = {"label": f"{c['label']}: {c['neg_reviews']} negative reviews "
                                                     f"({c['share_of_complaints']:.0%} of all complaints)", **c}
    for d in m.get("brand_topic", []):
        idx[f"m:net:{d['brand']}:{d['topic']}"] = {
            "label": f"{brand_name(d['brand'])} · {d['label']}: net sentiment {d['net']:+.2f} (n={d['n']})",
            **{k: v for k, v in d.items() if k != "review_ids"}}
    df = pd.DataFrame(products)
    if not df.empty:
        for b, d in df.groupby("brand"):
            ppm = d["price_per_ml"].dropna()
            pr = d["price"].dropna()
            idx[f"m:price:{b}"] = {"label": f"{brand_name(b)} {cat}: {len(d)} SKUs"
                                            + (f", median ₹{pr.median():.0f}" if len(pr) else ", price n/a")
                                            + (f", median ₹{ppm.median():.1f}/ml" if len(ppm) else ""),
                                   "brand": b, "n_skus": int(len(d)), "median_price": float(pr.median()) if len(pr) else None,
                                   "median_ppm": float(ppm.median()) if len(ppm) else None}
    for r in m.get("ratings", []):
        if r.get("avg_rating"):
            idx[f"m:rating:{r['brand']}:{r['handle']}"] = {"label": f"{brand_name(r['brand'])} {r['handle']}: "
                                                                    f"avg {r['avg_rating']}★ over {r['n']} reviews", **r}
    return idx


def gap_map(products: list[dict], m: dict) -> pd.DataFrame:
    """One row per product: price/ml × mean topic satisfaction (net sentiment over its labelled topics)."""
    bt = pd.DataFrame(m.get("labels_flat", []))
    rows = []
    for p in products:
        sat = None
        n = 0
        if not bt.empty:
            d = bt[(bt["brand"] == p["brand"]) & (bt["handle"] == p["handle"])]
            n = d["review_id"].nunique()
            if len(d):
                sat = float(d["sentiment"].mean())
        rows.append({"brand": p["brand"], "brand_name": brand_name(p["brand"]), "title": p["title"],
                     "handle": p["handle"], "price": p["price"], "price_per_ml": p.get("price_per_ml"),
                     "satisfaction": sat, "n_reviews_labelled": n,
                     "spf": (p.get("spec") or {}).get("spf"), "format": (p.get("spec") or {}).get("format")})
    return pd.DataFrame(rows)


def price_band(ppm: float | None) -> str:
    if ppm is None or (isinstance(ppm, float) and np.isnan(ppm)):
        return "unknown"
    return "value (<₹8/ml)" if ppm < 8 else "mid (₹8–14/ml)" if ppm < 14 else "premium (≥₹14/ml)"


def whitespace(products: list[dict], m: dict, cat: str) -> pd.DataFrame:
    """Feature × price-band combinations: how many SKUs serve it and how satisfied customers are."""
    feats = {}
    for p in products:
        s = p.get("spec") or {}
        fs = set()
        if s.get("format"):
            fs.add(f"format: {s['format']}")
        if s.get("tinted"):
            fs.add("tinted")
        if s.get("filter_type"):
            fs.add(f"filter: {s['filter_type']}")
        for c in s.get("claims") or []:
            if c in ("no white cast", "water resistant", "matte finish", "dewy finish", "fragrance free",
                     "makeup friendly", "oil control", "blue light protection", "reef safe", "pregnancy safe",
                     "hydrating", "non-comedogenic"):
                fs.add(c)
        for f in fs:
            feats.setdefault((f, price_band(p.get("price_per_ml"))), []).append(p)
    lab = pd.DataFrame(m.get("labels_flat", []))
    rows = []
    for (f, band), ps in feats.items():
        sat = None
        if not lab.empty:
            keys = {(p["brand"], p["handle"]) for p in ps}
            d = lab[[(b, h) in keys for b, h in zip(lab["brand"], lab["handle"])]]
            sat = float(d["sentiment"].mean()) if len(d) else None
        rows.append({"feature": f, "price_band": band, "n_skus": len(ps),
                     "n_brands": len({p["brand"] for p in ps}),
                     "dk_has": any(p["brand"] == _home() for p in ps),
                     "satisfaction": None if sat is None else round(sat, 2),
                     "brands": ", ".join(sorted({brand_name(p["brand"]) for p in ps}))})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["whitespace_score"] = (1 / (1 + df["n_skus"])) + df["satisfaction"].fillna(0).clip(upper=0).abs() * 0.5
    return df.sort_values(["whitespace_score", "n_skus"], ascending=[False, True])


def launch_trends(all_rows: list[dict], cat_rows_keys: set, months: int = 24) -> pd.DataFrame:
    """Ingredient & claim mentions among category launches by quarter (created_at — approximate signal)."""
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(months=months)
    recs = []
    for r in all_rows:
        if (r["brand"], r["handle"]) not in cat_rows_keys:
            continue
        try:
            c = pd.Timestamp(r["created_at"]).tz_convert("UTC")
        except Exception:
            continue
        if c < cutoff:
            continue
        q = f"{c.year}-Q{(c.month - 1) // 3 + 1}"
        s = r.get("spec") or {}
        for t in (s.get("key_ingredients") or []) + [f"claim: {x}" for x in s.get("claims") or []] + \
                 ([f"format: {s['format']}"] if s.get("format") else []):
            recs.append({"quarter": q, "term": t, "brand": r["brand"], "title": r["title"]})
    return pd.DataFrame(recs)


def demand_forecast(reviews: list[dict], horizon_months: int = 3) -> pd.DataFrame:
    """Review velocity (reviews / month) per brand as a demand proxy; linear trend projection.
    Labelled 'estimate' in the UI — reviews lag sales and only cover sites with public review feeds."""
    df = pd.DataFrame(reviews)
    if df.empty or "date" not in df:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].dt.tz_localize(None).dt.to_period("M")
    out = []
    last = pd.Period(dt.date.today(), "M")
    for b, d in df.groupby("brand"):
        s = d.groupby("month").size()
        idx = pd.period_range(last - 11, last, freq="M")
        s = s.reindex(idx, fill_value=0)
        y = s.values.astype(float)
        x = np.arange(len(y))
        if y.sum() < 6:
            continue
        slope, inter = np.polyfit(x, y, 1)
        for i, (p, v) in enumerate(s.items()):
            out.append({"brand": b, "month": str(p), "reviews": int(v), "kind": "actual"})
        for h in range(1, horizon_months + 1):
            out.append({"brand": b, "month": str(last + h), "reviews": max(0.0, round(inter + slope * (len(y) - 1 + h), 1)),
                        "kind": "forecast"})
    return pd.DataFrame(out)


def opportunity_scores(m: dict, cat: str) -> pd.DataFrame:
    """estimate = demand signal (share of all reviews mentioning topic) × D&K weakness on topic × fit.
    D&K weakness = (1 - D&K net)/2 relative to best rival net."""
    tl = topic_labels(cat)
    bt = pd.DataFrame(m.get("brand_topic", []))
    if bt.empty:
        return pd.DataFrame()
    tot = sum(m.get("n_reviews", {}).values()) or 1
    rows = []
    for t, d in bt.groupby("topic"):
        demand = d["n"].sum() / tot
        dk = d[d["brand"] == _home()]
        dk_net = float(dk["net"].iloc[0]) if len(dk) else None
        dk_n = int(dk["n"].iloc[0]) if len(dk) else 0
        rivals = d[(d["brand"] != _home()) & (d["n"] >= 3)]
        best = rivals.sort_values("net", ascending=False).head(1)
        best_net = float(best["net"].iloc[0]) if len(best) else None
        weakness = (1 - dk_net) / 2 if dk_net is not None else 0.5
        gap_vs_best = (best_net - dk_net) if (best_net is not None and dk_net is not None) else None
        rows.append({"topic": t, "label": tl.get(t, t), "demand_share": round(demand, 3), "dk_net": dk_net,
                     "dk_n": dk_n, "best_rival": brand_name(best["brand"].iloc[0]) if len(best) else None,
                     "best_rival_net": best_net, "gap_vs_best": None if gap_vs_best is None else round(gap_vs_best, 2),
                     "opportunity": round(demand * weakness * 100, 1)})
    return pd.DataFrame(rows).sort_values("opportunity", ascending=False)


# ---------------- LLM strategy with evidence ----------------

SYSTEM = ("You are a senior D2C skincare strategist for Dot & Key (India). You write a SWOT, product "
          "improvements, new product concepts and go-to-market rows. RULES: every point must cite 1-4 evidence ids "
          "copied exactly from the EVIDENCE list (metric ids 'm:...' or review ids 'r:...'). Never invent numbers; "
          "only quote numbers that appear in the evidence labels. No medical claims. Be specific to India "
          "(cities, languages, channels like Nykaa, Amazon, Flipkart, Instagram Reels, quick-commerce).")


def evidence_digest(midx: dict, labels: list[dict], reviews_by_id: dict, max_quotes: int = 60) -> str:
    lines = ["METRICS:"] + [f"{k} :: {v['label']}" for k, v in list(midx.items())[:220]]
    lines.append("\nREVIEW QUOTES:")
    seen = 0
    # balanced: strongest negative and positive quotes per topic, D&K first
    df = pd.DataFrame(labels)
    if not df.empty:
        df["is_home"] = df["brand"] == _home()
        df = df.sort_values(["is_home", "sentiment"], ascending=[False, True])
        for (t, s), d in df.groupby(["topic", "sentiment"]):
            for _, r in d.head(3).iterrows():
                lines.append(f"r:{r['review_id'].split('r:', 1)[-1]} :: [{brand_name(r['brand'])} · {t} · {s:+d}] \"{r['quote'][:160]}\"")
                seen += 1
                if seen >= max_quotes:
                    break
    return "\n".join(lines)


def build_strategy(cat: str, m: dict, products: list[dict], labels: list[dict], reviews: list[dict],
                   opp: pd.DataFrame, ws: pd.DataFrame, trends: pd.DataFrame) -> dict:
    midx = metric_index(m, products, cat)
    rev_idx = {r["review_id"]: r for r in reviews}
    prod_idx = {f"p:{p['brand']}:{p['handle']}": {"label": p["title"], "brand": p["brand"]} for p in products}
    index = EvidenceIndex(reviews={k: {"label": (v.get("body") or "")[:200], **v} for k, v in rev_idx.items()},
                          metrics=midx, products=prod_idx)
    digest = evidence_digest(midx, labels, rev_idx)
    opp_txt = opp.head(8).to_string(index=False) if not opp.empty else "n/a"
    ws_txt = ws.head(12)[["feature", "price_band", "n_skus", "satisfaction", "brands"]].to_string(index=False) if not ws.empty else "n/a"
    tr_txt = (trends.groupby("term").size().sort_values(ascending=False).head(15).to_string()
              if not trends.empty else "n/a")
    prompt = (f"Category: {cat}. Home brand: Dot & Key.\n\nOPPORTUNITY TABLE (estimate):\n{opp_txt}\n\n"
              f"WHITESPACE (feature × price band):\n{ws_txt}\n\nLAUNCH TERMS (last 24 months, approximate):\n{tr_txt}\n\n"
              f"{digest}\n\nWrite: SWOT for Dot & Key in this category (3-5 points each), 3-5 product improvements, "
              f"3 new product concept cards, 5 GTM rows, and a 2-sentence summary.")
    engine = "llm"
    try:
        pack = llm.structured(prompt, StrategyPack, system=SYSTEM, purpose=f"strategy:{cat}", max_tokens=12000,
                              effort="medium")
        data = pack.model_dump()
    except Exception as e:
        engine = f"rules ({type(e).__name__})"
        data = rules_strategy(cat, m, opp, ws, midx)
    dropped = 0
    for q in ("strengths", "weaknesses", "opportunities", "threats"):
        kept, d = validate(data["swot"][q], index)
        data["swot"][q] = kept
        dropped += len(d)
    for key in ("improvements", "concepts", "gtm"):
        kept, d = validate(data[key], index)
        data[key] = kept
        dropped += len(d)
    data["engine"] = engine
    data["dropped_without_evidence"] = dropped
    return data


def rules_strategy(cat: str, m: dict, opp: pd.DataFrame, ws: pd.DataFrame, midx: dict) -> dict:
    """Deterministic fallback when no LLM is configured — templated from the same metrics."""
    home = _home()
    bt = [d for d in m.get("brand_topic", []) if d["brand"] == home and d["n"] >= 3]
    S = [{"text": f"Customers rate Dot & Key well on {d['label'].lower()} (net {d['net']:+.2f}, n={d['n']}).",
          "evidence": [f"m:net:{home}:{d['topic']}"]} for d in sorted(bt, key=lambda x: -x["net"])[:4] if d["net"] > 0.2]
    W = [{"text": f"{d['label']} is a weak spot for Dot & Key (net {d['net']:+.2f}, n={d['n']}).",
          "evidence": [f"m:net:{home}:{d['topic']}"]} for d in sorted(bt, key=lambda x: x["net"])[:4] if d["net"] < 0.2]
    O, T, I, C, G = [], [], [], [], []
    for _, r in opp.head(4).iterrows():
        ev = [f"m:complaint:{r['topic']}"] if f"m:complaint:{r['topic']}" in midx else [f"m:net:{home}:{r['topic']}"]
        O.append({"text": f"Own the '{r['label']}' conversation — opportunity estimate {r['opportunity']}.", "evidence": ev})
        I.append({"change": f"Reformulate / re-message around {r['label'].lower()}",
                  "rationale": f"D&K net {r['dk_net']} vs best rival {r['best_rival']} {r['best_rival_net']}.", "evidence": ev})
    for d in sorted([x for x in m.get("brand_topic", []) if x["brand"] != home and x["n"] >= 5],
                    key=lambda x: -x["net"])[:4]:
        T.append({"text": f"{brand_name(d['brand'])} is loved for {d['label'].lower()} (net {d['net']:+.2f}).",
                  "evidence": [f"m:net:{d['brand']}:{d['topic']}"]})
    for _, r in ws.head(3).iterrows():
        C.append({"name": f"{r['feature'].title()} — {r['price_band']}", "one_liner": f"Few SKUs ({r['n_skus']}) serve {r['feature']} in {r['price_band']}.",
                  "target_gap": r["feature"], "key_ingredients": [], "price_band": r["price_band"], "why_now": "Whitespace in current catalogues.",
                  "evidence": [k for k in midx if k.startswith("m:price:")][:2]})
    for p in ("Ananya, 21", "Riya, 27", "Meera, 34"):
        if O:
            G.append({"persona": p, "message": O[0]["text"], "channel": "Instagram Reels + Nykaa", "city_language": "Kolkata · Bengali",
                      "evidence": O[0]["evidence"]})
    return {"swot": {"strengths": S, "weaknesses": W, "opportunities": O, "threats": T}, "improvements": I,
            "concepts": C, "gtm": G, "summary": "Generated from metrics without an LLM (no API key configured)."}
