"""Brand kit: dominant colours from real D&K product images (Pillow + k-means) + tone-of-voice stats."""
from __future__ import annotations

import io
import json
import re
from collections import Counter

import numpy as np
import requests
from PIL import Image

from .. import cache
from ..config import INSIGHTS, USER_AGENT

DK_PALETTE = ["#FF803A", "#22BCE0", "#F4576C", "#71B61A", "#F5C518"]  # brand accent system
INK = "#1E2022"
CANVAS = "#FAF9F6"


def fetch_image(url: str, width: int = 1024) -> Image.Image:
    if not url.startswith("http"):  # local file (tests / uploaded packshots)
        return Image.open(url)
    if "cdn.shopify.com" in url and "width=" not in url:
        url = url + ("&" if "?" in url else "?") + f"width={width}"
    ck = {"u": url}
    hit = cache.get("img", ck)
    if hit:
        import base64
        return Image.open(io.BytesIO(base64.b64decode(hit)))
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    import base64
    cache.put("img", ck, base64.b64encode(r.content).decode())
    return Image.open(io.BytesIO(r.content))


def kmeans_colors(img: Image.Image, k: int = 5, seed: int = 0) -> list[tuple[str, float]]:
    a = np.asarray(img.convert("RGB").resize((96, 96))).reshape(-1, 3).astype(float)
    # drop near-white / near-black background pixels
    lum = a.mean(axis=1)
    a = a[(lum > 30) & (lum < 235)]
    if len(a) < k:
        return []
    rng = np.random.default_rng(seed)
    c = a[rng.choice(len(a), k, replace=False)]
    for _ in range(15):
        lab = ((a[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        c = np.array([a[lab == i].mean(0) if (lab == i).any() else c[i] for i in range(k)])
    cnt = Counter(lab.tolist())
    tot = sum(cnt.values())
    out = [("#%02X%02X%02X" % tuple(int(x) for x in c[i]), cnt[i] / tot) for i in range(k)]
    return sorted(out, key=lambda x: -x[1])


def product_palette(product: dict) -> list[str]:
    try:
        cols = kmeans_colors(fetch_image(product["image"], 400))
        sat = [h for h, _ in cols if _saturation(h) > 0.25]
        return (sat + DK_PALETTE)[:5]
    except Exception:
        return DK_PALETTE


def _saturation(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def tone_of_voice(dk_rows: list[dict]) -> dict:
    """Simple, measurable voice stats from D&K's own descriptions (used in briefs + UI)."""
    text = " ".join(r.get("body_text", "") for r in dk_rows)
    words = re.findall(r"[A-Za-z']+", text.lower())
    sents = [s for s in re.split(r"[.!?]", text) if s.strip()]
    stop = set("the a an and or of to in for with is it your you this that on as are be by from at its our".split())
    top = [w for w, _ in Counter(w for w in words if w not in stop and len(w) > 3).most_common(25)]
    fruits = [f for f in ("watermelon", "strawberry", "mango", "lime", "dragon", "blueberry", "raspberry", "kiwi",
                          "cherry", "papaya", "orange", "vitamin") if f in words]
    out = {"avg_sentence_words": round(len(words) / max(1, len(sents)), 1), "top_words": top,
           "fruit_actives": fruits, "exclamations_per_100_sent": round(text.count("!") / max(1, len(sents)) * 100, 1),
           "second_person_ratio": round((words.count("you") + words.count("your")) / max(1, len(words)) * 100, 2)}
    (INSIGHTS / "brand_voice.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def cutout(img: Image.Image, tol: int = 28) -> Image.Image:
    """Remove a near-uniform light background (Shopify packshots are usually on white/cream).
    Flood-fills from the borders so the product's own light areas survive."""
    from PIL import ImageDraw, ImageFilter
    im = img.convert("RGBA")
    w, h = im.size
    rgb = im.convert("RGB")
    corners = [rgb.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
    bg = tuple(int(np.median([c[i] for c in corners])) for i in range(3))
    spread = max(sum(abs(a[i] - b[i]) for i in range(3)) for a in corners for b in corners)
    if sum(bg) / 3 < 170 or spread > 90:  # dark or multi-colour (lifestyle) packshot: rounded card, no ragged cut-out  # dark/busy background: keep as a rounded card instead of a cut-out
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=int(min(w, h) * 0.06), fill=255)
        im.putalpha(mask)
        return im
    marker = (255, 0, 255)
    work = rgb.copy()
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)):
        try:
            ImageDraw.floodfill(work, seed, marker, thresh=tol)
        except Exception:
            pass
    a = np.asarray(work)
    mask = ~((a[:, :, 0] == 255) & (a[:, :, 1] == 0) & (a[:, :, 2] == 255))
    m = Image.fromarray((mask * 255).astype("uint8")).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(m)
    bbox = m.getbbox()
    return im.crop(bbox) if bbox else im
