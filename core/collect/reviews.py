"""L1 Collect — customer reviews from each store's public review-widget feed.

Endpoints were discovered from each store's own product pages on 2026-11-21 and are documented in
docs/review_endpoints.md. We only read what the widget itself shows shoppers. Never fabricated.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import http
from ..config import REVIEWS, brands

PROVIDERS = {
    "dotandkey":   {"kind": "judgeme", "shop": "dot-key.myshopify.com"},
    "deconstruct": {"kind": "judgeme", "shop": "thedeconstruct.myshopify.com"},
    "dermaco":     {"kind": "judgeme", "shop": "thedermaco.myshopify.com"},
    "plum":        {"kind": "judgeme", "shop": "plumgoodness-2.myshopify.com"},
    "pilgrim":     {"kind": "judgeme", "shop": "discoverpilgrim.myshopify.com"},
    "aqualogica":  {"kind": "judgeme", "shop": "aqualogicaprod.myshopify.com"},
    "drsheths":    {"kind": "judgeme", "shop": "dr-sheths.myshopify.com"},
    "fixderma":    {"kind": "judgeme", "shop": "fixderma-skincare.myshopify.com"},
    "minimalist":  {"kind": "yotpo", "app_key": "Sphwk8Wj9Cg1x0FxDDivWxXcFjrv9ApHjy7kM0pR"},
    "reequil":     {"kind": "nector", "api_key": "ak_cc929cfb9abd57e3329c3a4a3261b3c01e3eabb1267b0346e6b3fb1ab14c1afd"},
    "foxtale":     {"kind": "foxtale", "next_action": "7f78a3fbae72e53c9a03f1e707e84a2103879974ac"},
}


def _clean(html: str | None) -> str:
    if not html:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ")).strip()


def _rec(brand, handle, pid, rid, rating, title, body, author, date, verified) -> dict:
    return {"review_id": f"r:{brand}:{rid}", "brand": brand, "handle": handle, "product_id": str(pid),
            "rating": float(rating) if rating not in (None, "") else None, "title": (title or "").strip(),
            "body": (body or "").strip(), "author": (author or "").strip(), "date": date,
            "verified": bool(verified)}


# ---------- Judge.me ----------
def judgeme(brand: str, handle: str, pid: str, limit: int) -> tuple[list[dict], dict]:
    shop = PROVIDERS[brand]["shop"]
    url = "https://judge.me/reviews/reviews_for_widget"
    out: dict[str, dict] = {}
    agg: dict = {}
    # 1) every low-rated review first (≤3★) — recency sampling alone misses complaints on highly rated products
    for page in range(1, 6):
        r = http.get(url, params={"url": shop, "shop_domain": shop, "platform": "shopify", "product_id": pid,
                                  "page": page, "per_page": 30, "sort_by": "rating", "sort_dir": "asc"}, min_gap=1.2)
        if r.status_code != 200:
            break
        d = r.json()
        if "reviews" in d:
            batch = [(x.get("uuid") or x.get("id"), x.get("rating"), x.get("title"), _clean(x.get("body_html") or x.get("body")),
                      x.get("reviewer_name"), x.get("created_at"), x.get("verified_buyer")) for x in d["reviews"]]
            if d.get("histogram"):
                agg["histogram"] = {h["rating"]: h["frequency"] for h in d["histogram"]}
        else:
            batch = []
            for el in BeautifulSoup(d.get("html") or "", "html.parser").select("div.jdgm-rev"):
                sc = el.select_one(".jdgm-rev__rating")
                tm = el.select_one("time.jdgm-rev__timestamp") or el.select_one(".jdgm-rev__timestamp")
                gt = lambda sel: (el.select_one(sel) or BeautifulSoup("", "html.parser")).get_text(" ", strip=True)
                batch.append((el.get("data-review-id"), sc.get("data-score") if sc else None, gt(".jdgm-rev__title"),
                              gt(".jdgm-rev__body"), gt(".jdgm-rev__author"),
                              (tm.get("datetime") or tm.get("data-content")) if tm else None, el.get("data-verified-buyer") == "true"))
        low = [b for b in batch if b[1] is not None and float(b[1]) <= 3]
        for b in low:
            rec = _rec(brand, handle, pid, *b)
            out[rec["review_id"]] = rec
        if len(low) < len(batch) or not batch:
            break
    for sort_dir in ("desc", "asc"):
        page = 1
        while len(out) < limit:
            r = http.get(url, params={"url": shop, "shop_domain": shop, "platform": "shopify", "product_id": pid,
                                      "page": page, "per_page": 30, "sort_by": "created_at", "sort_dir": sort_dir},
                         min_gap=1.2)
            if r.status_code != 200:
                break
            d = r.json()
            new = 0
            if "reviews" in d:  # JSON mode
                agg = {"count": d.get("number_of_reviews"), "avg": d.get("average_rating")}
                for x in d["reviews"]:
                    rec = _rec(brand, handle, pid, x.get("uuid") or x.get("id"), x.get("rating"), x.get("title"),
                               _clean(x.get("body_html") or x.get("body")), x.get("reviewer_name"),
                               x.get("created_at"), x.get("verified_buyer"))
                    if rec["review_id"] not in out:
                        out[rec["review_id"]] = rec
                        new += 1
                total_pages = (d.get("pagination") or {}).get("total_pages") or 0
                done = page >= min(total_pages or 0, 33) or not d["reviews"]
            else:  # HTML mode
                agg = {"count": d.get("total_count"), "avg": None}
                soup = BeautifulSoup(d.get("html") or "", "html.parser")
                revs = soup.select("div.jdgm-rev")
                for el in revs:
                    sc = el.select_one(".jdgm-rev__rating")
                    tm = el.select_one("time.jdgm-rev__timestamp") or el.select_one(".jdgm-rev__timestamp")
                    rec = _rec(brand, handle, pid, el.get("data-review-id"),
                               sc.get("data-score") if sc else None,
                               (el.select_one(".jdgm-rev__title") or BeautifulSoup("", "html.parser")).get_text(" ", strip=True),
                               (el.select_one(".jdgm-rev__body") or BeautifulSoup("", "html.parser")).get_text(" ", strip=True),
                               (el.select_one(".jdgm-rev__author") or BeautifulSoup("", "html.parser")).get_text(" ", strip=True),
                               (tm.get("datetime") or tm.get("data-content")) if tm else None,
                               el.get("data-verified-buyer") == "true")
                    if rec["review_id"] not in out:
                        out[rec["review_id"]] = rec
                        new += 1
                done = len(revs) < 30 or page >= 33
            if done or new == 0:
                break
            page += 1
        if len(out) >= limit or (agg.get("count") or 0) <= 990:
            break
    if agg.get("avg") is None and out:
        rs = [x["rating"] for x in out.values() if x["rating"]]
        agg["avg_collected"] = round(sum(rs) / len(rs), 2) if rs else None
    return list(out.values())[:limit], agg


# ---------- Yotpo ----------
def yotpo(brand: str, handle: str, pid: str, limit: int) -> tuple[list[dict], dict]:
    key = PROVIDERS[brand]["app_key"]
    out, agg, page = [], {}, 1
    while len(out) < limit:
        r = http.get(f"https://api-cdn.yotpo.com/v1/widget/{key}/products/{pid}/reviews.json",
                     params={"per_page": 150, "page": page, "sort": "date"}, min_gap=1.2)
        if r.status_code != 200:
            break
        resp = r.json().get("response", {})
        bl = resp.get("bottomline", {})
        agg = {"count": bl.get("total_review"), "avg": bl.get("average_score")}
        revs = resp.get("reviews", [])
        for x in revs:
            out.append(_rec(brand, handle, pid, x.get("id"), x.get("score"), x.get("title"), _clean(x.get("content")),
                            (x.get("user") or {}).get("display_name"), x.get("created_at"), x.get("verified_buyer")))
        if len(revs) < 150:
            break
        page += 1
    return out[:limit], agg


# ---------- Nector ----------
def nector(brand: str, handle: str, pid: str, limit: int) -> tuple[list[dict], dict]:
    key = PROVIDERS[brand]["api_key"]
    out, agg, page = [], {}, 1
    while len(out) < limit:
        r = http.get("https://cachefront.nector.io/api/v2/merchant/reviews",
                     params={"page": page, "limit": 100, "sort": "posted_at", "sort_op": "DESC",
                             "reference_product_id": pid, "reference_product_source": "shopify"},
                     headers={"x-apikey": key, "x-source": "web"}, min_gap=1.2)
        if r.status_code != 200:
            break
        d = r.json().get("data", {})
        items = d.get("items", [])
        agg = {"count": d.get("count"), "avg": None, "stats": d.get("stats")}
        for x in items:
            out.append(_rec(brand, handle, pid, x.get("_id"), x.get("rating"), x.get("title"), _clean(x.get("description")),
                            x.get("name"), x.get("posted_at"), x.get("is_verified")))
        if len(items) < 100:
            break
        page += 1
    rs = [x["rating"] for x in out if x["rating"]]
    agg["avg_collected"] = round(sum(rs) / len(rs), 2) if rs else None
    return out[:limit], agg


# ---------- Foxtale (headless Next.js; Fera-backed server action) ----------
def _rsc_parse(b: bytes) -> dict:
    rows, i = {}, 0
    while i < len(b):
        m = re.match(rb"([0-9a-f]+):", b[i:])
        if not m:
            i += 1
            continue
        k = m.group(1).decode()
        i += m.end()
        if b[i:i + 1] == b"T":
            c = b.index(b",", i)
            n = int(b[i + 1:c], 16)
            rows[k] = b[c + 1:c + 1 + n].decode("utf-8", "replace")
            i = c + 1 + n
        else:
            e = b.find(b"\n", i)
            e = len(b) if e < 0 else e
            try:
                rows[k] = json.loads(b[i:e])
            except Exception:
                rows[k] = None
            i = e + 1

    def res(x, depth=0):
        if depth > 50:
            return x
        if isinstance(x, str) and x.startswith("$") and x[1:] in rows:
            return res(rows[x[1:]], depth + 1)
        if isinstance(x, dict):
            return {k: res(v, depth + 1) for k, v in x.items()}
        if isinstance(x, list):
            return [res(v, depth + 1) for v in x]
        return x
    return res(rows.get("1")) or {}


def foxtale(brand: str, handle: str, pid: str, limit: int) -> tuple[list[dict], dict]:
    domain = brands()["brands"][brand]["domain"]
    ids = pid
    agg: dict = {}
    try:  # grouped_product_ids metafield lives in the server-rendered PDP
        h = http.get(f"https://{domain}/products/{handle}", min_gap=3.0, max_tries=2)
        if h.status_code == 200:
            m = re.search(r'grouped_product_ids[\\"]*\s*[,:]\s*[\\"]*value[\\"]*\s*:\s*[\\"]*([0-9,]+)', h.text) or \
                re.search(r'grouped_product_ids.{0,120}?([0-9]{10,}(?:,[0-9]{10,})+)', h.text, re.S)
            if m:
                ids = m.group(1)
            a = re.search(r'avg_rating.{0,60}?([0-9]\.[0-9]+)', h.text, re.S)
            t = re.search(r'total_reviews.{0,60}?([0-9]{1,6})', h.text, re.S)
            agg = {"avg": float(a.group(1)) if a else None, "count": int(t.group(1)) if t else None}
    except Exception:
        pass
    out, page = [], 1
    while len(out) < limit:
        try:
            r = http.SESSION.post(f"https://{domain}/products/{handle}",
                                  data=json.dumps([{"productIds": ids, "page": page, "limit": 100}]),
                                  headers={"Next-Action": PROVIDERS[brand]["next_action"], "Accept": "text/x-component",
                                           "Content-Type": "text/plain;charset=UTF-8"}, timeout=30)
        except Exception:
            break
        if r.status_code != 200:
            break
        d = _rsc_parse(r.content)
        items = d.get("data") or []
        for x in items:
            c = x.get("customer") or {}
            out.append(_rec(brand, handle, pid, x.get("id"), x.get("rating"), x.get("heading") or x.get("subject"),
                            x.get("body"), c.get("generated_display_name") or c.get("name"), x.get("created_at"),
                            x.get("is_verified")))
        meta = d.get("meta") or {}
        agg.setdefault("count", meta.get("total_count"))
        if not items or page >= (meta.get("page_count") or 1):
            break
        page += 1
        time.sleep(1.5)
    return out[:limit], agg


FETCHERS = {"judgeme": judgeme, "yotpo": yotpo, "nector": nector, "foxtale": foxtale}


def review_path(brand: str, handle: str) -> Path:
    return REVIEWS / f"{brand}_{handle}.json"


def fetch_product_reviews(row: dict, limit: int = 300, refresh: bool = False) -> dict:
    p = review_path(row["brand"], row["handle"])
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    prov = PROVIDERS.get(row["brand"])
    if not prov:
        rec = {"brand": row["brand"], "handle": row["handle"], "reviews_available": False,
               "reason": "no public review feed found", "reviews": []}
    else:
        try:
            revs, agg = FETCHERS[prov["kind"]](row["brand"], row["handle"], row["product_id"], limit)
            rec = {"brand": row["brand"], "handle": row["handle"], "product_id": row["product_id"],
                   "provider": prov["kind"], "reviews_available": True, "aggregate": agg,
                   "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "reviews": revs}
        except Exception as e:
            rec = {"brand": row["brand"], "handle": row["handle"], "reviews_available": False,
                   "reason": f"fetch error: {e}"[:300], "reviews": []}
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def collect_for(rows: list[dict], per_product: int = 200, home_per_product: int = 400, progress=None,
                refresh: bool = False) -> dict:
    from ..config import home_brand
    cov = {}
    for i, r in enumerate(rows):
        lim = home_per_product if r["brand"] == home_brand() else per_product
        rec = fetch_product_reviews(r, limit=lim, refresh=refresh)
        cov[f"{r['brand']}:{r['handle']}"] = {"brand": r["brand"], "handle": r["handle"], "title": r["title"],
                                             "provider": rec.get("provider"), "available": rec["reviews_available"],
                                             "collected": len(rec["reviews"]),
                                             "shown_count": (rec.get("aggregate") or {}).get("count"),
                                             "shown_avg": (rec.get("aggregate") or {}).get("avg"),
                                             "reason": rec.get("reason")}
        if progress:
            progress(i + 1, len(rows), r["title"], len(rec["reviews"]))
    path = REVIEWS / "coverage.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old.update(cov)
    path.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    return cov


def load_reviews(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        p = review_path(r["brand"], r["handle"])
        if p.exists():
            out.extend(json.loads(p.read_text(encoding="utf-8")).get("reviews", []))
    seen, uniq = set(), []
    for x in out:
        if x["review_id"] not in seen:
            seen.add(x["review_id"])
            uniq.append(x)
    return uniq


def coverage() -> dict:
    p = REVIEWS / "coverage.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
