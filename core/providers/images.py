"""Background-scene image chain: Higgsfield → Cloudflare FLUX schnell → Pollinations → Pillow template.
Models only ever draw the SCENE. The real product photo and all text are composited in code."""
from __future__ import annotations

import io
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from .. import cache
from . import cloudflare, higgsfield, pollinations

SCENE_SUFFIX = (", empty background scene for a skincare product advertisement, no product, no bottle, no tube, "
                "no text, no letters, no logo, no watermark, soft natural light, shallow depth of field, "
                "clean composition with open space in the centre, high-end editorial photography")


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def template_scene(w: int, h: int, palette: list[str], seed: int = 7) -> Image.Image:
    """Deterministic Pillow background: soft two-tone gradient + blurred 'fruit' orbs in brand colours."""
    import numpy as np
    rnd = random.Random(seed)
    c1, c2 = np.array(hex_rgb(palette[0]), float), np.array(hex_rgb(palette[1 % len(palette)]), float)
    t = np.linspace(0, 1, h)[:, None]
    top = c1 * 0.35 + 255 * 0.65
    bot = c2 * 0.45 + 250 * 0.55
    grad = (top[None, :] * (1 - t) + bot[None, :] * t).astype(np.uint8)  # (h, 3)
    base = Image.fromarray(np.repeat(grad[:, None, :], w, axis=1), "RGB")
    sw, sh = max(1, w // 4), max(1, h // 4)  # draw orbs small, blur, upscale: fast and smooth
    orbs = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(orbs)
    for i in range(7):
        col = hex_rgb(palette[i % len(palette)])
        r = rnd.randint(int(min(sw, sh) * 0.12), int(min(sw, sh) * 0.32))
        cx, cy = rnd.randint(-r // 2, sw + r // 2), rnd.randint(-r // 2, sh + r // 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col + (rnd.randint(70, 130),))
    orbs = orbs.filter(ImageFilter.GaussianBlur(min(sw, sh) * 0.06)).resize((w, h), Image.BICUBIC)
    base = Image.alpha_composite(base.convert("RGBA"), orbs).convert("RGB")
    noise = np.random.default_rng(seed).normal(0, 3.0, (h, w, 1))
    arr = np.clip(np.asarray(base, float) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def scene(prompt: str, w: int, h: int, palette: list[str], seed: int = 7, prefer: list[str] | None = None,
          allow_paid: bool = False) -> tuple[Image.Image, str]:
    """Return (image, engine). Cached per (prompt, size, seed, engine)."""
    order = prefer or (["higgsfield"] if allow_paid else []) + ["cloudflare", "pollinations", "template"]
    full = prompt.strip().rstrip(".") + SCENE_SUFFIX
    for eng in order:
        # one generation per (engine, prompt, seed) at 1024² — every ad size / frame is a crop of it
        ck = {"e": eng, "p": full, "s": seed}
        hit = cache.get("scene", ck)
        if hit and eng != "template":
            try:
                import base64
                return _fit(Image.open(io.BytesIO(base64.b64decode(hit))), w, h), eng
            except Exception:
                pass
        try:
            if eng == "higgsfield" and higgsfield.available():
                ar = "1:1" if abs(w - h) < 50 else ("9:16" if h > w else "16:9")
                data = higgsfield.text_to_image(full, aspect_ratio=ar, seed=seed)
            elif eng == "cloudflare" and cloudflare.available():
                data = cloudflare.generate(full, seed=seed)
            elif eng == "pollinations":
                data = pollinations.generate(full, width=1024, height=1024, seed=seed)
            elif eng == "template":
                return template_scene(w, h, palette, seed), "template"
            else:
                continue
            import base64
            cache.put("scene", ck, base64.b64encode(data).decode())
            return _fit(Image.open(io.BytesIO(data)), w, h), eng
        except Exception:
            continue
    return template_scene(w, h, palette, seed), "template"
