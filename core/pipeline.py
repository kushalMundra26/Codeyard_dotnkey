"""Orchestrator: L1 collect → L2 enrich → L3 rivals → L4 review intel → L5 strategy → L6 creative.
Used by Streamlit (direct import), FastAPI and the MCP server — one code path for all three."""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

import pandas as pd

from . import audit as audit_mod
from . import enrich, llm, reviews_intel, rivals, strategy
from .collect import catalog, reviews as rev_collect
from .config import INSIGHTS, OUTPUTS, brand_inputs, brand_list, brand_name, home_brand, topic_labels
from .creative import brandkit, brief as brief_mod, claims, compose, copy as copy_mod, pack, video
from .evidence import EvidenceIndex
from .providers import sarvam

Progress = callable


def _p(progress, step: str, detail: str = "", frac: float | None = None):
    if progress:
        progress(step, detail, frac)


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False))


# ======================= ANALYSIS =======================

def run_analysis(cat: str = "sunscreen", live: bool = False, use_llm: bool = True, refresh_reviews: bool = False,
                 per_product: int = 150, home_per_product: int = 400, progress=None) -> dict:
    t0 = time.time()
    timings = {}
    if live:
        _p(progress, "Catalogue", "fetching /products.json for 11 brands")
        catalog.collect_all(progress=lambda b, s: _p(progress, "Catalogue", f"{brand_name(b)}: {s}"))
    timings["catalogue"] = round(time.time() - t0, 1)

    rows = catalog.category_rows(cat)
    if not rows:
        raise RuntimeError("No catalogue snapshots found — run with live=True first.")
    _p(progress, "Enrich", f"{len(rows)} {cat} SKUs")
    rows = enrich.enrich_rows(rows, use_llm=use_llm,
                              progress=lambda i, n, t: _p(progress, "Enrich", f"{i}/{n} {t[:40]}", i / n))
    timings["enrich"] = round(time.time() - t0, 1)

    if live or refresh_reviews or not rev_collect.coverage():
        rev_collect.collect_for(rows, per_product=per_product, home_per_product=home_per_product, refresh=refresh_reviews,
                                progress=lambda i, n, t, k: _p(progress, "Reviews", f"{i}/{n} {t[:36]} → {k}", i / n))
    reviews = rev_collect.load_reviews(rows)
    timings["reviews"] = round(time.time() - t0, 1)

    _p(progress, "Review intelligence", f"labelling {len(reviews)} reviews")
    labels, lstats = reviews_intel.label_reviews(reviews, cat, use_llm=use_llm,
                                                 progress=lambda i, n: _p(progress, "Review intelligence", f"{i}/{n} labelled", i / max(n, 1)))
    m = reviews_intel.metrics(reviews, labels, cat)
    m["labels_flat"] = labels
    timings["labels"] = round(time.time() - t0, 1)

    _p(progress, "Rivals", "scoring matches")
    home_rows = [r for r in rows if r["brand"] == home_brand()]
    rival_map = {r["handle"]: [{"brand": x["brand"], "handle": x["handle"], "match": x["match"]}
                               for x in rivals.top_rivals(r, rows, k=5)] for r in home_rows}
    cat_rivals = rivals.category_rivals(rows)

    _p(progress, "Market gaps", "gap map, whitespace, trends, forecast")
    gm = strategy.gap_map(rows, m)
    ws = strategy.whitespace(rows, m, cat)
    all_rows = [r for b in brand_list() for r in catalog.rows(b)]
    keys = {(r["brand"], r["handle"]) for r in rows}
    tr = strategy.launch_trends(rows, keys)
    fc = strategy.demand_forecast(reviews)
    opp = strategy.opportunity_scores(m, cat)
    launches = []
    for b in brand_list():
        for r in catalog.recent_launches(b, days=90):
            launches.append({k: r[k] for k in ("brand", "title", "handle", "product_type", "price", "created_at", "image", "url")}
                            | {"in_category": catalog.in_category(r, cat)})
    timings["gaps"] = round(time.time() - t0, 1)

    _p(progress, "Strategy", "SWOT, improvements, concepts, GTM")
    strat = strategy.build_strategy(cat, m, rows, labels, reviews, opp, ws, tr)
    voice = brandkit.tone_of_voice([r for r in all_rows if r["brand"] == home_brand()])
    timings["strategy"] = round(time.time() - t0, 1)

    out = {
        "category": cat, "generated_at": time.strftime("%Y-%m-%d %H:%M"), "elapsed_s": round(time.time() - t0, 1),
        "timings": timings, "llm": {"provider": llm.provider(), "model": llm.model_name() if llm.available() else None},
        "label_stats": lstats, "products": rows, "rivals": rival_map, "category_rivals": cat_rivals,
        "metrics": {k: v for k, v in m.items() if k != "labels_flat"}, "labels": labels,
        "gap_map": _records(gm), "whitespace": _records(ws), "trends": _records(tr), "forecast": _records(fc),
        "opportunity": _records(opp), "launches": sorted(launches, key=lambda x: x["created_at"] or "", reverse=True),
        "strategy": strat, "brand_voice": voice, "coverage": rev_collect.coverage(),
        "catalog_counts": {b: len(catalog.load_snapshot(b)) for b in brand_list()},
        "snapshot_dates": {b: catalog.snapshot_dates(b) for b in brand_list()},
    }
    (INSIGHTS / f"{cat}.json").write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
    _p(progress, "Done", f"{len(rows)} SKUs · {len(reviews)} reviews · {out['elapsed_s']} s", 1.0)
    return out


def load_insights(cat: str = "sunscreen") -> dict | None:
    p = INSIGHTS / f"{cat}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def available_categories() -> list[str]:
    return sorted(p.stem for p in INSIGHTS.glob("*.json")
                  if not p.stem.startswith(("labels_", "brand_voice", "eval_")) and p.stem != "radar")


# ======================= CONTEXT =======================

def all_reviews(ins: dict) -> list[dict]:
    return rev_collect.load_reviews(ins["products"])


def product_topics(ins: dict, brand: str, handle: str) -> list[dict]:
    tl = topic_labels(ins["category"])
    df = pd.DataFrame(ins["labels"])
    if df.empty:
        return []
    d = df[(df["brand"] == brand) & (df["handle"] == handle)]
    out = []
    for t, g in d.groupby("topic"):
        out.append({"brand": brand, "handle": handle, "topic": t, "label": tl.get(t, t), "n": int(len(g)),
                    "net": round(float(g["sentiment"].mean()), 3), "review_ids": g["review_id"].tolist()[:50]})
    return sorted(out, key=lambda x: -x["n"])


def product_context(ins: dict, handle: str, brand: str | None = None) -> dict:
    brand = brand or home_brand()
    prod = next(p for p in ins["products"] if p["handle"] == handle and p["brand"] == brand)
    pmap = {(p["brand"], p["handle"]): p for p in ins["products"]}
    rv = []
    for r in ins["rivals"].get(handle, []):
        q = pmap.get((r["brand"], r["handle"]))
        if q:
            rv.append(q | {"match": r["match"], "brand_name": brand_name(q["brand"])})
    own = product_topics(ins, brand, handle)
    df = pd.DataFrame(ins["labels"])
    quotes = []
    if not df.empty:
        d = df[(df["brand"] == brand) & (df["handle"] == handle)]
        d = d.assign(qlen=d["quote"].str.len()).sort_values(["sentiment", "qlen"], ascending=[False, True])
        pos = d[d["sentiment"] > 0].drop_duplicates("topic").head(12)
        neg = d[d["sentiment"] < 0].drop_duplicates("topic").head(8)
        quotes = _records(pd.concat([pos, neg]).drop(columns=["qlen"]))
    unmet = [u for u in ins["metrics"].get("unmet", []) if u["brand"] == brand and u["handle"] == handle][:12] or \
            [u for u in ins["metrics"].get("unmet", []) if u["brand"] != brand][:8]
    rating = next((r for r in ins["metrics"].get("ratings", []) if r["brand"] == brand and r["handle"] == handle), None)
    cov = ins.get("coverage", {}).get(f"{brand}:{handle}", {})
    return {"category": ins["category"], "product": prod, "rivals": rv, "own_topics": own, "quotes": quotes,
            "complaints": ins["metrics"].get("complaint_share", []), "unmet": unmet,
            "opportunities": ins.get("opportunity", [])[:6], "rating": rating, "coverage": cov}


def evidence_index(ins: dict, ctx: dict | None = None) -> EvidenceIndex:
    reviews = {r["review_id"]: {"label": (r.get("body") or r.get("title") or "")[:240], **r} for r in all_reviews(ins)}
    m = dict(ins["metrics"])
    m["labels_flat"] = ins["labels"]
    metrics = strategy.metric_index(m, ins["products"], ins["category"])
    for p in ins["products"]:
        if p["brand"] != home_brand():
            continue
        for t in product_topics(ins, p["brand"], p["handle"]):
            metrics[f"m:net:{t['brand']}:{t['topic']}|{t['handle']}"] = {
                "label": f"{p['title'][:40]} · {t['label']}: net {t['net']:+.2f} (n={t['n']})", **t}
    prods = {f"p:{p['brand']}:{p['handle']}": {"label": p["title"]} for p in ins["products"]}
    return EvidenceIndex(reviews=reviews, metrics=metrics, products=prods)


def own_topic_net(ctx: dict, ins: dict) -> dict:
    """Topic sentiment used by the claims checker: product-level if n≥3, else D&K category-level."""
    out = {t["topic"]: t for t in ctx["own_topics"] if t["n"] >= 3}
    for d in ins["metrics"].get("brand_topic", []):
        if d["brand"] == home_brand() and d["topic"] not in out:
            out[d["topic"]] = d
    return out


# ======================= CAMPAIGN =======================

def campaign_id(handle: str, persona_id: str, seed: int) -> str:
    return f"{handle[:40]}-{persona_id}-{hashlib.sha1(f'{handle}{persona_id}{seed}'.encode()).hexdigest()[:6]}"


def generate_campaign(cat: str, handle: str, persona_id: str | None = None, sizes=("square", "story", "aplus"),
                      make_video: bool = True, seed: int = 7, progress=None, image_pref: list[str] | None = None,
                      render_ads: bool = True) -> dict:
    ins = load_insights(cat)
    if ins is None:
        raise RuntimeError(f"No insights for {cat}. Run analysis first.")
    bi = brand_inputs()
    persona = next((p for p in bi["personas"] if p["id"] == persona_id), bi["personas"][0])
    ctx = product_context(ins, handle)
    index = evidence_index(ins, ctx)
    reviews = [r for r in all_reviews(ins) if r["handle"] == handle and r["brand"] == home_brand()]
    cid = campaign_id(handle, persona["id"], seed)
    cdir = OUTPUTS / cid
    cdir.mkdir(parents=True, exist_ok=True)
    engines = {}
    t0 = time.time()

    _p(progress, "Brief", persona["name"])
    br, engines["brief"] = brief_mod.make_brief(ctx, persona, index)
    _p(progress, "Ad copy", "3 variants")
    variants, engines["ads"] = copy_mod.ad_variants(ctx, br, persona, index)
    otn = own_topic_net(ctx, ins)
    spec = ctx["product"].get("spec", {})
    for v in variants:
        v["claims"] = claims.check(f"{v['headline']}. {v['subline']}", spec, otn)
    # Demonstrate the guardrail on the claims the category most wants to hear
    probe = [f"Zero white cast, guaranteed", "Non-greasy, never sticky", "No eye sting, ever",
             "Won't break you out", f"SPF {(spec.get('spf') or 50) + 10} protection", "Better than Minimalist",
             "Cures tanning permanently", "Lightweight texture that absorbs fast"]
    probe_results = claims.check_many(probe, spec, otn)

    _p(progress, "E-commerce copy", "description, title, bullets, A+")
    ecom, engines["ecom"] = copy_mod.ecom_copy(ctx, br, reviews, index)
    ecom_claims = claims.check_many([ecom["product_description"], ecom["amazon_title"], *ecom["bullets"]], spec, otn)

    _p(progress, "Listing audit", "before / after")
    aud, engines["audit"] = audit_mod.run_audit(ctx, index)

    _p(progress, "Scripts", "15 s + 30 s")
    s15, engines["script15"] = copy_mod.script(ctx, br, persona, 15, index)
    s30, engines["script30"] = copy_mod.script(ctx, br, persona, 30, index)

    palette = brandkit.product_palette(ctx["product"])
    assets = []
    ok_variants = [v for v in variants if v["claims"]["verdict"] != "block"] or variants
    for vi, v in enumerate(ok_variants if render_ads else []):
        for sz in sizes:
            _p(progress, "Static ads", f"variant {vi + 1} · {sz}")
            a = compose.render_ad(ctx["product"], v, sz, palette, cdir / f"ad_v{vi + 1}_{sz}_en.jpg", seed=seed + vi,
                                  engine_pref=image_pref)
            assets.append(a | {"variant": vi})

    vids = []
    if make_video:
        _p(progress, "Storyboard video", "15 s, English")
        try:
            vids.append(video.render_storyboard_video(ctx["product"], s15, palette, cdir, lang="en", engine_pref=image_pref,
                                                      progress=lambda s: _p(progress, "Storyboard video", s)))
        except Exception as e:
            vids.append({"error": str(e)[:400], "lang": "en"})

    camp = {"id": cid, "category": cat, "created_at": time.strftime("%Y-%m-%d %H:%M"), "elapsed_s": round(time.time() - t0, 1),
            "product": {k: ctx["product"][k] for k in ("brand", "handle", "title", "price", "image", "url", "spec", "size", "unit")},
            "persona": persona, "brief": br, "ads": {"variants": variants, "assets": assets}, "claims_probe": probe_results,
            "ecom": ecom, "ecom_claims": ecom_claims, "audit": aud, "script15": s15, "script30": s30, "palette": palette,
            "videos": vids, "regional": {}, "engines": engines, "status": "draft", "hero": None, "image_pref": image_pref,
            "renders": {}, "selected": None, "fruit": _fruit(ctx["product"])}
    save_campaign(camp)
    pack.build_pack(cdir, camp)
    _p(progress, "Campaign", f"ready in {camp['elapsed_s']} s", 1.0)
    return camp


def _fruit(product: dict) -> str:
    ings = (product.get("spec") or {}).get("key_ingredients") or []
    t = product["title"].lower()
    for f in ("watermelon", "strawberry", "mango", "lime", "dragon fruit", "vitamin c", "cica", "blueberry", "papaya"):
        if f in t or f in ings:
            return f
    return "fresh fruit"


STYLES = compose.STYLES


def ad_concepts(c: dict) -> list[dict]:
    """The ad options shown as tiles: every variant with its claims verdict (blocked ones stay visible but locked)."""
    return [{"index": i, **{k: v[k] for k in ("headline", "subline", "cta", "why", "evidence")},
             "verdict": v["claims"]["verdict"], "reasons": v["claims"]["reasons"]} for i, v in enumerate(c["ads"]["variants"])]


def render_choice(cid: str, variant_index: int, style: str, seed: int = 7, image_pref: list[str] | None = None,
                  sizes=("square", "story", "aplus"), progress=None) -> list[dict]:
    """Render ONE chosen concept in ONE chosen style in all three proportions. Cached: re-picking is instant."""
    c = load_campaign(cid)
    v = c["ads"]["variants"][variant_index]
    if v["claims"]["verdict"] == "block":
        raise ValueError("This concept was blocked by the claims checker.")
    key = f"{variant_index}:{style}"
    cdir = OUTPUTS / cid
    have = c.get("renders", {}).get(key)
    if have and all(Path(a["path"]).exists() for a in have):
        assets = have
    else:
        assets = []
        for sz in sizes:
            _p(progress, "Rendering", f"{compose.SIZE_LABELS[sz]}")
            assets.append(compose.render_ad(c["product"] | {"body_text": ""}, v, sz, c["palette"],
                                            cdir / f"ad_c{variant_index + 1}_{style}_{sz}_en.jpg", seed=seed, style=style,
                                            fruit=c.get("fruit") or _fruit(c["product"]),
                                            engine_pref=image_pref or c.get("image_pref")))
    c.setdefault("renders", {})[key] = assets
    c["selected"] = {"variant": variant_index, "style": style}
    # keep the classic asset list in sync so packs / API / Telegram previews use the chosen ad
    c["ads"]["assets"] = [a | {"variant": variant_index} for a in assets]
    save_campaign(c)
    pack.build_pack(cdir, c)
    return assets


def save_campaign(c: dict) -> None:
    d = OUTPUTS / c["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "campaign.json").write_text(json.dumps(c, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def load_campaign(cid: str) -> dict | None:
    p = OUTPUTS / cid / "campaign.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def list_campaigns() -> list[dict]:
    out = []
    for p in sorted(OUTPUTS.glob("*/campaign.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": c["id"], "title": c["product"]["title"], "persona": c["persona"]["name"],
                        "created_at": c["created_at"], "status": c.get("status"), "languages": list(c.get("regional", {}).keys())})
        except Exception:
            pass
    return out


def regional(cid: str, languages: list[str] | None = None, make_video: bool = True, progress=None) -> dict:
    """Translate script + ad text (Sarvam Mayura), TTS (Bulbul v3), render localized ads and MP4s."""
    c = load_campaign(cid)
    if c is None:
        raise RuntimeError(f"campaign {cid} not found")
    if not sarvam.available():
        raise RuntimeError("SARVAM_API_KEY not set — regional versions need Sarvam translate + TTS.")
    langs = languages or brand_inputs()["languages"]
    cdir = OUTPUTS / cid
    product = c["product"] | {"body_text": ""}
    s = c["script15"]
    sel = c.get("selected") or {}
    v = c["ads"]["variants"][sel["variant"]] if sel else \
        next((x for x in c["ads"]["variants"] if x["claims"]["verdict"] != "block"), c["ads"]["variants"][0])
    style = sel.get("style")
    for lang in langs:
        _p(progress, "Translate", sarvam.LANG_NAMES.get(lang, lang))
        tv = {"headline": sarvam.translate(v["headline"], lang), "subline": sarvam.translate(v["subline"], lang),
              "cta": sarvam.translate(v["cta"], lang), "scene_prompt": v["scene_prompt"]}
        on_screen = [sarvam.translate(f["on_screen_text"], lang) for f in s["frames"]]
        vo = [sarvam.translate(f["voiceover"], lang) for f in s["frames"]]
        ads = []
        for sz in ("square", "story"):
            _p(progress, "Localized ad", f"{lang} · {sz}")
            ads.append(compose.render_ad(product, tv, sz, c["palette"], cdir / f"ad_{sz}_{lang}.jpg", lang=lang, seed=7,
                                         style=style, fruit=c.get("fruit", ""), engine_pref=c.get("image_pref")))
        vid = None
        if make_video:
            _p(progress, "Video", f"{lang} voiceover + render")
            try:
                vid = video.render_storyboard_video(product, s, c["palette"], cdir, lang=lang, engine_pref=c.get("image_pref"),
                                                    texts={"on_screen": on_screen, "voiceover": vo})
            except Exception as e:
                vid = {"error": str(e)[:400]}
        c["regional"][lang] = {"ad_text": tv, "on_screen": on_screen, "voiceover": vo, "ads": ads, "video": vid}
        save_campaign(c)
    c["status"] = "regional_ready"
    save_campaign(c)
    pack.build_pack(cdir, c)
    return c


def hero(cid: str, duration: int = 5) -> dict:
    c = load_campaign(cid)
    v = next((x for x in c["ads"]["variants"] if x["claims"]["verdict"] != "block"), c["ads"]["variants"][0])
    vo = " ".join(f["voiceover"] for f in c["script15"]["frames"][:2])
    r = video.hero_clip(c["product"] | {"body_text": ""}, v, c["palette"], OUTPUTS / cid, vo, duration=duration)
    c["hero"] = r
    save_campaign(c)
    pack.build_pack(OUTPUTS / cid, c)
    return r


# ======================= RADAR =======================

def radar(cat: str = "sunscreen", days: int = 45) -> dict:
    """Diff latest vs previous snapshot per brand, plus recent launches by created_at, plus draft counter-ad copy."""
    from .schemas import CounterAd
    out = {"brands": {}, "generated_at": time.strftime("%Y-%m-%d %H:%M")}
    for b in brand_list():
        dates = [d for d in catalog.snapshot_dates(b) if "seed" not in d]  # seeds are not observations
        entry = {"name": brand_name(b), "dates": dates[-2:], "diff": None}
        if len(dates) >= 2:
            entry["diff"] = catalog.diff_snapshots(catalog.load_snapshot(b, dates[-2]), catalog.load_snapshot(b, dates[-1]))
        entry["recent_launches"] = [{k: r[k] for k in ("title", "handle", "price", "created_at", "image", "url")}
                                    | {"in_category": catalog.in_category(r, cat)}
                                    for r in catalog.recent_launches(b, days=days)]
        out["brands"][b] = entry
    rival_launches = [dict(l, brand=b, brand_name=brand_name(b)) for b, e in out["brands"].items() if b != home_brand()
                      for l in e["recent_launches"] if l["in_category"]]
    out["rival_category_launches"] = sorted(rival_launches, key=lambda x: x["created_at"], reverse=True)
    out["n_changes"] = sum(len(e["diff"]["launches"]) + len(e["diff"]["price_changes"]) + len(e["diff"]["new_discounts"])
                           for e in out["brands"].values() if e["diff"])
    ca = None
    if out["rival_category_launches"]:
        top = out["rival_category_launches"][0]
        ins = load_insights(cat)
        strengths = [s["text"] for s in (ins or {}).get("strategy", {}).get("swot", {}).get("strengths", [])][:3]
        try:
            ca = llm.structured(f"A rival just launched: {top['brand_name']} — {top['title']} at ₹{top['price'] or 'n/a'}.\n"
                                f"Dot & Key's evidenced strengths in {cat}: {strengths}\nWrite a counter-ad for Dot & Key "
                                "(headline ≤7 words, body ≤25 words). Do NOT name or disparage the rival.",
                                CounterAd, system="You write ASCI-compliant Indian skincare ads.", purpose="counter-ad",
                                max_tokens=1000, effort="low").model_dump()
        except Exception:
            ca = {"headline": "Sun care your skin actually enjoys",
                  "body": (strengths[0] if strengths else "Loved for its lightweight feel.") + " Shop Dot & Key today.",
                  "rationale": "template (no LLM configured)"}
        ca["trigger"] = top
    out["counter_ad"] = ca
    (INSIGHTS / "radar.json").write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
    return out


def surprise_product(cat: str = "sunscreen") -> dict:
    """Demo flow: pick a random real D&K product (with its real image + description) from the snapshot."""
    ins = load_insights(cat)
    home = [p for p in (ins or {}).get("products", []) if p["brand"] == home_brand() and p.get("image")]
    return random.choice(home) if home else {}
