"""L1 Collect — Shopify catalogue snapshots, normalisation, category filter and snapshot diff."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .. import http
from ..config import SNAPSHOTS, brand_list, brands, category_cfg, home_brand

SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|mL|ML|g|gm|gms|G|grams?|gram)\b")
PACK_RE = re.compile(r"(?:pack\s*of|set\s*of)\s*(\d+)|(\d+)\s*x\b|\b(duo|trio)\b", re.I)


def today() -> str:
    return dt.date.today().isoformat()


def fetch_catalog(brand: str, max_pages: int = 20) -> list[dict]:
    """Page through https://{domain}/products.json?limit=250&page=N until empty."""
    domain = brands()["brands"][brand]["domain"]
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        r = http.get(f"https://{domain}/products.json", params={"limit": 250, "page": page}, min_gap=3.0, max_tries=2)
        if r.status_code != 200:
            raise RuntimeError(f"{brand}: HTTP {r.status_code} on page {page}")
        prods = r.json().get("products", [])
        if not prods:
            break
        out.extend(prods)
        if len(prods) < 250:
            break
    return out


def snapshot_path(brand: str, date: str) -> Path:
    return SNAPSHOTS / f"catalog_{brand}_{date}.json"


def save_snapshot(brand: str, products: list[dict], date: str | None = None) -> Path:
    p = snapshot_path(brand, date or today())
    p.write_text(json.dumps({"brand": brand, "date": date or today(), "products": products}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def snapshot_dates(brand: str) -> list[str]:
    return sorted(p.stem.split("_")[-1] for p in SNAPSHOTS.glob(f"catalog_{brand}_*.json"))


def load_snapshot(brand: str, date: str | None = None) -> list[dict]:
    dates = snapshot_dates(brand)
    if not dates:
        return []
    d = date or dates[-1]
    return json.loads(snapshot_path(brand, d).read_text(encoding="utf-8"))["products"]


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ")).strip()


def parse_size(*texts: str) -> tuple[float | None, str | None]:
    """Return (size, unit) with unit in {'ml','g'}; first match wins. 1 g is treated ≈ 1 ml downstream."""
    for t in texts:
        if not t:
            continue
        m = SIZE_RE.search(t)
        if m:
            val = float(m.group(1))
            unit = "ml" if m.group(2).lower() == "ml" else "g"
            if 1 <= val <= 1000:
                return val, unit
    return None, None


def parse_pack(title: str) -> int:
    m = PACK_RE.search(title or "")
    if not m:
        return 1
    if m.group(1):
        return int(m.group(1))
    if m.group(2):
        return int(m.group(2))
    return {"duo": 2, "trio": 3}[m.group(3).lower()]


def normalise(brand: str, p: dict) -> dict:
    variants = p.get("variants") or []
    v0 = min(variants, key=lambda v: float(v.get("price") or 1e9)) if variants else {}
    price = float(v0.get("price") or 0) or None
    mrp = float(v0.get("compare_at_price") or 0) or None
    if mrp and price and mrp < price:
        mrp = None
    body = html_to_text(p.get("body_html"))
    opts = " ".join(" ".join(o.get("values", [])) for o in (p.get("options") or []))
    size, unit = parse_size(v0.get("title", ""), p.get("title", ""), opts, body[:600])
    pack = parse_pack(p.get("title", ""))
    eff_size = size * pack if size else None
    images = [i.get("src") for i in (p.get("images") or []) if i.get("src")]
    available = any(v.get("available", True) for v in variants) if variants else None
    return {
        "brand": brand,
        "product_id": str(p.get("id")),
        "handle": p.get("handle"),
        "title": p.get("title", "").strip(),
        "product_type": (p.get("product_type") or "").strip(),
        "tags": p.get("tags") or [],
        "price": price,
        "mrp": mrp,
        "discount_pct": round((1 - price / mrp) * 100, 1) if price and mrp else 0.0,
        "size": size,
        "unit": unit,
        "pack": pack,
        "price_per_ml": round(price / eff_size, 2) if price and eff_size else None,
        "image": images[0] if images else None,
        "images": images[:6],
        "available": available,
        "created_at": p.get("created_at"),
        "published_at": p.get("published_at"),
        "updated_at": p.get("updated_at"),
        "body_text": body[:4000],
        "url": f"https://{brands()['brands'][brand]['domain']}/products/{p.get('handle')}",
        "n_variants": len(variants),
        "source": p.get("_source"),  # set on seed rows: where each field came from
    }


def rows(brand: str, date: str | None = None) -> list[dict]:
    return [normalise(brand, p) for p in load_snapshot(brand, date)]


def in_category(row: dict, cat: str) -> bool:
    cfg = category_cfg(cat)
    t = f" {row['title'].lower()} "
    pt = row["product_type"].lower()
    if any(x in pt for x in cfg.get("require_product_type_not", [])):
        return False
    if row.get("pack", 1) > 1:
        return False
    hay = t + " " + pt
    if not any(k in hay for k in cfg["include"]):
        return False
    if cat == "sunscreen":
        # lip products with SPF are lip care, not sunscreen; tinted/serum SPF hybrids stay in
        if " lip" in t:
            return False
    if any(x in t for x in cfg["exclude"]):
        # allow 'spf' moisturisers only if they clearly say sunscreen
        if not ("sunscreen" in t and not any(x in t for x in ("kit", "combo", "duo", "pack of", "set", "bundle", "trio"))):
            return False
    return bool(row.get("price")) or bool(row.get("source"))  # seed rows may lack a verified price


def category_rows(cat: str, brands_: list[str] | None = None) -> list[dict]:
    out = []
    for b in brands_ or brand_list():
        out.extend(r for r in rows(b) if in_category(r, cat))
    return out


def collect_all(progress=None) -> dict:
    """Fetch every brand, write today's snapshot. Returns {brand: count | error}."""
    status = {}
    for b in brand_list():
        try:
            prods = fetch_catalog(b)
            save_snapshot(b, prods)
            status[b] = len(prods)
        except Exception as e:  # keep going; a single store failing must not kill the run
            status[b] = f"error: {e}"
        if progress:
            progress(b, status[b])
    return status


# ---------- diff (Launch Radar) ----------

def diff_snapshots(old: list[dict], new: list[dict]) -> dict:
    """Compare two raw Shopify snapshots → launches, removals, price changes, new discounts, stock-outs."""
    o = {str(p["id"]): p for p in old}
    n = {str(p["id"]): p for p in new}

    def first_variant(p):
        vs = p.get("variants") or [{}]
        return min(vs, key=lambda v: float(v.get("price") or 1e9))

    launches = [n[k] for k in n.keys() - o.keys()]
    removed = [o[k] for k in o.keys() - n.keys()]
    price_changes, new_discounts, stockouts, restocks = [], [], [], []
    for k in n.keys() & o.keys():
        a, b = first_variant(o[k]), first_variant(n[k])
        pa, pb = float(a.get("price") or 0), float(b.get("price") or 0)
        if pa and pb and abs(pa - pb) >= 1:
            price_changes.append({"id": k, "title": n[k]["title"], "handle": n[k]["handle"], "old": pa, "new": pb,
                                  "change_pct": round((pb - pa) / pa * 100, 1)})
        ca, cb = float(a.get("compare_at_price") or 0), float(b.get("compare_at_price") or 0)
        if cb > pb and not (ca > pa):
            new_discounts.append({"id": k, "title": n[k]["title"], "handle": n[k]["handle"], "price": pb, "mrp": cb,
                                  "discount_pct": round((1 - pb / cb) * 100, 1)})
        av_a = any(v.get("available", True) for v in o[k].get("variants") or [])
        av_b = any(v.get("available", True) for v in n[k].get("variants") or [])
        if av_a and not av_b:
            stockouts.append({"id": k, "title": n[k]["title"], "handle": n[k]["handle"]})
        if av_b and not av_a:
            restocks.append({"id": k, "title": n[k]["title"], "handle": n[k]["handle"]})
    slim = lambda p: {"id": str(p["id"]), "title": p["title"], "handle": p["handle"],
                      "product_type": p.get("product_type"), "created_at": p.get("created_at"),
                      "price": float(first_variant(p).get("price") or 0),
                      "image": ((p.get("images") or [{}])[0] or {}).get("src")}
    return {
        "launches": [slim(p) for p in launches],
        "removed": [slim(p) for p in removed],
        "price_changes": price_changes,
        "new_discounts": new_discounts,
        "stockouts": stockouts,
        "restocks": restocks,
    }


def recent_launches(brand: str, days: int = 60) -> list[dict]:
    """Launch signal from created_at (published_at resets on republish, so we use created_at)."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = []
    for r in rows(brand):
        try:
            c = dt.datetime.fromisoformat(r["created_at"])
        except Exception:
            continue
        if c >= cutoff:
            out.append(r)
    return sorted(out, key=lambda r: r["created_at"], reverse=True)
