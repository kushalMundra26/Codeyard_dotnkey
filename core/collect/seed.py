"""Seed catalogue for when Shopify /products.json is rate-limited.

Builds Shopify-shaped product rows ONLY from verifiable sources:
  • product ids verified on each store's own pages (docs/review_endpoints.md)
  • product name / packshot / rating from that store's public review-widget feed (Judge.me JSON / HTML, Yotpo)
  • price / MRP from the marketplace snapshot (Nykaa / Flipkart listing, collected with source URLs)
Every product carries `_source` so the UI can say where each field came from. Saved as
catalog_<brand>_0000-seed.json: any real dated snapshot sorts after it and wins; the radar ignores seeds.
"""
import json
import re

from bs4 import BeautifulSoup

from .. import http, marketplace
from ..config import SNAPSHOTS
from .catalog import snapshot_dates
from .reviews import PROVIDERS

# (brand, handle, shopify product id, marketplace title keywords for price matching) — ids from docs/review_endpoints.md
SEEDS = [
    ("dotandkey", "watermelon-cooling-spf-50-face-sunscreen", "8152049385637", ["watermelon"]),
    ("minimalist", "light-fluid-spf-50-sunscreen", "7883925880993", ["light fluid"]),
    ("foxtale", "matte-finish-sunscreen", "7725413564663", ["spf 70"]),
    ("reequil", "oxybenzone-free-sunscreen-spf-50-for-oily-acne-prone-skin", "8356331421882", ["oxybenzone"]),
    ("deconstruct", "gel-sunscreen-for-oily-skin-30gm", "15427857711385", ["gel sunscreen"]),
    ("deconstruct", "salicylic-acid-gel-sunscreen", "10667195269401", []),
    ("dermaco", "1-hyaluronic-sunscreen-aqua-gel-with-spf-50-pa-80g", "9791516082423", ["hyaluronic"]),
    ("plum", "green-tea-zinc-super-matte-spf-50-sunscreen-gel-for-oily-acne-prone-skin-30g", "8924254076988", []),
    ("aqualogica", "illuminate-dewy-sunscreen-spf-50-pa-with-wild-berries-alpha-arbutin-125-g", "8634637156577", []),
    ("pilgrim", "5-vitamin-c-complex-brightening-serum-sunscreen-spf-50-pa", "9417536995557", []),
    ("fixderma", "roll-on-sunscreen-for-face", "8076579012834", []),
]


def judgeme_meta(brand, pid):
    shop = PROVIDERS[brand]["shop"]
    r = http.get("https://judge.me/reviews/reviews_for_widget", params={"url": shop, "shop_domain": shop, "platform": "shopify",
                 "product_id": pid, "page": 1, "per_page": 5, "sort_by": "created_at", "sort_dir": "desc"}, max_tries=2)
    if r.status_code != 200:
        return {}
    d = r.json()
    if "reviews" in d:
        return {"title": d.get("product_name"), "image": d.get("image_url"), "count": d.get("number_of_reviews"),
                "avg": d.get("average_rating"), "summary": d.get("ai_summary_text") or d.get("review_summary_text")}
    s = BeautifulSoup(d.get("html") or "", "html.parser")
    el = s.select_one("div.jdgm-rev")
    title = el.get("data-product-title") if el else None
    if not title and el:
        a = el.select_one("a.jdgm-rev__prod-link")
        title = a.get_text(strip=True) if a else None
    return {"title": title, "count": d.get("total_count")}


def yotpo_meta(brand, pid):
    key = PROVIDERS[brand]["app_key"]
    r = http.get(f"https://api-cdn.yotpo.com/v1/widget/{key}/products/{pid}/reviews.json", params={"per_page": 1, "page": 1}, max_tries=2)
    if r.status_code != 200:
        return {}
    resp = r.json().get("response", {})
    prods = resp.get("products") or [{}]
    p = prods[0] if prods else {}
    img = (p.get("images") or [{}])[0].get("image_url") if p.get("images") else p.get("image_url")
    return {"title": p.get("name"), "image": img, "count": resp.get("bottomline", {}).get("total_review"),
            "avg": resp.get("bottomline", {}).get("average_score")}


def price_from_marketplace(brand, kws):
    if not kws:
        return None
    for m in marketplace.load():
        if m.get("brand_key") == brand and m.get("price_inr") and all(k in m["product_name_on_listing"].lower() for k in kws):
            return m
    return None


def humanise(handle):
    return re.sub(r"\s+", " ", handle.replace("-", " ")).strip().title()


def build_seed(log=print) -> list[str]:

    by_brand = {}
    for brand, handle, pid, kws in SEEDS:
        if any(not d.endswith("seed") for d in snapshot_dates(brand)):
            log(f"{brand}: real snapshot exists — skip seed")
            continue
        kind = PROVIDERS[brand]["kind"]
        meta = judgeme_meta(brand, pid) if kind == "judgeme" else yotpo_meta(brand, pid) if kind == "yotpo" else {}
        mk = price_from_marketplace(brand, kws)
        title = meta.get("title") or (mk or {}).get("product_name_on_listing") or humanise(handle)
        size = re.search(r"(\d+)\s*-?\s*(g|gm|ml)\b", handle + " " + title, re.I)
        prod = {
            "id": int(pid), "title": title, "handle": handle, "product_type": "Sunscreen", "tags": [],
            "body_html": "", "created_at": None, "published_at": None, "updated_at": None, "options": [],
            "variants": [{"price": str(mk["price_inr"]) if mk else None,
                          "compare_at_price": str(mk["mrp_inr"]) if mk and mk.get("mrp_inr") else None,
                          "title": f"{size.group(1)}{size.group(2)}" if size else "", "available": True}],
            "images": [{"src": meta["image"]}] if meta.get("image") else [],
            "_source": {"catalog": "seed (Shopify blocked: 429)", "id": "verified on store page",
                        "title_image": f"{kind} review widget" if meta else "handle",
                        "price": f"{mk['marketplace']} listing {mk['url']}" if mk else None,
                        "widget_rating": meta.get("avg"), "widget_count": meta.get("count"),
                        "widget_summary": meta.get("summary")},
        }
        by_brand.setdefault(brand, []).append(prod)
        log(f"{brand:12s} {title[:60]:60s} ₹{(mk or {}).get('price_inr')}  img={'yes' if meta.get('image') else 'no'}  reviews={meta.get('count')}")
    for b, prods in by_brand.items():
        (SNAPSHOTS / f"catalog_{b}_0000-seed.json").write_text(
            json.dumps({"brand": b, "date": "0000-seed", "seed": True, "products": prods}, ensure_ascii=False), encoding="utf-8")
    log("seeded:", list(by_brand))
    return list(by_brand)
