"""Static ad composer: model-made background scene + the REAL product photo (cut out) + text laid out in code.
Latin text: Pillow. Devanagari / Bengali / Tamil: HarfBuzz-shaped (core/creative/shaping.py)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import FONTS
from ..providers import images
from . import shaping
from .brandkit import CANVAS, INK, cutout, fetch_image

SIZES = {"square": (1080, 1080), "story": (1080, 1920), "aplus": (970, 600)}
SIZE_LABELS = {"square": "Feed 1:1 · 1080×1080", "story": "Story / Reel 9:16 · 1080×1920", "aplus": "Amazon A+ · 970×600"}

# Ad styles the user picks from (tiles). Each changes the AI background scene and the type treatment;
# the real packshot and the copy stay the same.
STYLES = {
    "juicy": {"name": "Fresh & juicy", "blurb": "Fruit-active splash, bright and playful — the classic Dot & Key feel.",
              "scene": "{fruit} slices and water droplets splashing on wet pale stone, bright morning light, fresh and juicy",
              "panel": (250, 249, 246, 226), "ink": (30, 32, 34), "sub": (70, 74, 80), "accent": None},
    "clinical": {"name": "Clean clinical", "blurb": "Calm apothecary studio, lots of white space — lets the science speak.",
                 "scene": "minimal pale ceramic studio backdrop, soft diffused light, subtle shadow, clean apothecary mood",
                 "panel": (255, 255, 255, 0), "ink": (30, 32, 34), "sub": (100, 104, 110), "accent": "#22BCE0"},
    "lifestyle": {"name": "Sunlit everyday", "blurb": "Real Indian day-in-the-life light: balcony, commute, harsh sun.",
                  "scene": "sunlit Indian apartment balcony with potted plants at golden hour, warm harsh sunlight, no people",
                  "panel": (24, 24, 26, 170), "ink": (255, 255, 255), "sub": (235, 235, 235), "accent": "#FF803A"},
}


def style_scene(style: str, fruit: str) -> str:
    return STYLES.get(style, STYLES["juicy"])["scene"].format(fruit=fruit or "fresh fruit")
SCRIPT_FONTS = {"hi": "NotoSansDevanagari.ttf", "mr": "NotoSansDevanagari.ttf", "bn": "NotoSansBengali.ttf",
                "ta": "NotoSansTamil.ttf"}


def hex_rgb(h):
    return images.hex_rgb(h)


def readable(rgb, max_lum: float = 0.6, fallback=(244, 87, 108)):
    """Accent for a white-text button: too light → Dot & Key watermelon pink instead of a muddy darkened tint."""
    r, g, b = rgb
    return (r, g, b) if (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 <= max_lum else fallback


@dataclass(frozen=True)
class FontSpec:
    path: str
    size: int
    weight: str
    complex: bool

    @property
    def pil(self) -> ImageFont.FreeTypeFont:
        return _pil_font(self.path, self.size, self.weight)


@lru_cache(maxsize=64)
def _pil_font(path: str, size: int, weight: str) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def font(kind: str, size: int, lang: str = "en", weight: str = "Bold") -> FontSpec:
    if lang in SCRIPT_FONTS:
        return FontSpec(str(FONTS / SCRIPT_FONTS[lang]), size, weight, True)
    name = "Fraunces.ttf" if kind == "serif" else "PlusJakartaSans.ttf"
    return FontSpec(str(FONTS / name), size, weight, False)


def text_w(text: str, f: FontSpec) -> float:
    if f.complex:
        return shaping.width(text, f.path, f.size, f.weight)
    return ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f.pil)


def draw_text(canvas: Image.Image, xy: tuple[int, int], text: str, f: FontSpec, fill, anchor: str = "la") -> Image.Image:
    """anchor: 'la' left-top, 'ma' centre-top, 'mm' centre-middle (enough for our layouts)."""
    x, y = xy
    if not f.complex:
        ImageDraw.Draw(canvas).text((x, y), text, font=f.pil, fill=fill, anchor=anchor)
        return canvas
    im = shaping.render(text, f.path, f.size, tuple(fill[:3]), f.weight)
    w = text_w(text, f)
    if anchor[0] == "m":
        x = int(x - w / 2)
    if anchor[1] == "m":
        y = int(y - im.height / 2 + f.size * 0.12)
    canvas.alpha_composite(im, (max(0, int(x - f.size // 6)), max(0, int(y - f.size * 0.08))))
    return canvas


def wrap(text: str, f: FontSpec, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if text_w(cand, f) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(text, kind, max_w, max_h, start, lang, min_size=22, weight="Bold", spacing=1.12):
    size = start
    lh = 1.45 if lang in SCRIPT_FONTS else spacing
    while size >= min_size:
        f = font(kind, size, lang, weight)
        lines = wrap(text, f, max_w)
        if int(len(lines) * size * lh) <= max_h:
            return f, lines, size, lh
        size -= 4
    f = font(kind, min_size, lang, weight)
    return f, wrap(text, f, max_w), min_size, lh


def product_layer(product: dict, max_w: int, max_h: int) -> Image.Image | None:
    try:
        im = cutout(fetch_image(product["image"], 1200))
    except Exception:
        return None
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def render_ad(product: dict, variant: dict, size: str, palette: list[str], out: Path, lang: str = "en",
              seed: int = 7, scene_img: Image.Image | None = None, engine_pref: list[str] | None = None,
              allow_paid: bool = False, style: str | None = None, fruit: str = "") -> dict:
    W, H = SIZES[size]
    st_ = STYLES.get(style or "juicy", STYLES["juicy"])
    prompt = style_scene(style, fruit) if style else variant["scene_prompt"]
    if scene_img is None:
        bg, engine = images.scene(prompt, W, H, palette, seed=seed, prefer=engine_pref, allow_paid=allow_paid)
    else:
        bg, engine = scene_img.resize((W, H)), "provided"
    canvas = bg.convert("RGBA")
    accent = readable(hex_rgb(st_["accent"] or palette[0]))
    ink = st_["ink"]
    pad = int(W * 0.065)
    if size == "aplus":
        x0, y0, x1, ymax = pad, pad, int(W * 0.52), H - pad
        prod_box = (int(W * 0.55), int(H * 0.08), W - pad, H - int(H * 0.06))
        hstart, sstart, cstart = 0.06, 0.028, 0.026
    elif size == "story":
        x0, y0, x1, ymax = pad, int(H * 0.08), W - pad, int(H * 0.44)
        prod_box = (int(W * 0.16), int(H * 0.46), W - int(W * 0.16), int(H * 0.92))
        hstart, sstart, cstart = 0.095, 0.038, 0.034
    else:
        x0, y0, x1, ymax = pad, int(H * 0.09), int(W * 0.58), H - int(H * 0.09)
        prod_box = (int(W * 0.58), int(H * 0.12), W - pad // 2, H - int(H * 0.07))
        hstart, sstart, cstart = 0.085, 0.034, 0.03
    tw = x1 - x0

    # ---- layout pass (positions only) ----
    wm = font("sans", int(W * 0.026), "en", "ExtraBold")
    y = y0 + int(W * 0.07)
    area_h = ymax - y
    hf, hl, hs, hlh = fit_text(variant["headline"], "serif", tw, int(area_h * 0.5), int(W * hstart), lang)
    head_y = y
    y += int(len(hl) * hs * hlh) + int(W * 0.018)
    sf, sl, ss, slh = fit_text(variant["subline"], "sans", tw, int(area_h * 0.3), int(W * sstart), lang, min_size=18,
                               weight="Medium", spacing=1.35)
    sub_y = y
    y += int(len(sl) * ss * slh) + int(W * 0.03)
    cf = font("sans", int(W * cstart), lang, "Bold")
    ctw = text_w(variant["cta"], cf)
    ch = int(cf.size * 2.0)
    cy = y
    bottom = cy + ch

    # ---- panel hugging the content ----
    panel = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    if style == "clinical":  # white type block, thin rule instead of a card
        ImageDraw.Draw(panel).rectangle((x0 - pad // 2, y0 - pad // 2, x1 + pad // 3, bottom + pad // 2), fill=(255, 255, 255, 205))
        ImageDraw.Draw(panel).line((x0, bottom + pad // 3, x1, bottom + pad // 3), fill=(230, 228, 223, 255), width=2)
    else:
        ImageDraw.Draw(panel).rounded_rectangle((x0 - pad // 2, y0 - pad // 2, x1 + pad // 3, bottom + pad // 2),
                                                radius=int(W * 0.025), fill=st_["panel"])
    canvas = Image.alpha_composite(canvas, panel)

    # ---- real packshot with grounded shadow ----
    pl = product_layer(product, prod_box[2] - prod_box[0], prod_box[3] - prod_box[1])
    if pl is not None:
        px = prod_box[0] + (prod_box[2] - prod_box[0] - pl.width) // 2
        py = prod_box[3] - pl.height
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((px + pl.width * 0.1, py + pl.height - 18, px + pl.width * 0.9, py + pl.height + 22),
                                   fill=(30, 32, 34, 90))
        canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(14)))
        canvas.alpha_composite(pl, (px, py))

    # ---- text ----
    d = ImageDraw.Draw(canvas)
    d.text((x0, y0), "DOT & KEY", font=wm.pil, fill=ink)
    d.line((x0, y0 + int(W * 0.04), x0 + int(W * 0.06), y0 + int(W * 0.04)), fill=accent, width=4)
    yy = head_y
    for line in hl:
        draw_text(canvas, (x0, yy), line, hf, ink)
        yy += int(hs * hlh)
    yy = sub_y
    for line in sl:
        draw_text(canvas, (x0, yy), line, sf, st_["sub"])
        yy += int(ss * slh)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x0, cy, x0 + ctw + cf.size * 2, cy + ch), radius=ch // 2, fill=accent)
    draw_text(canvas, (int(x0 + cf.size + ctw / 2), cy + ch // 2), variant["cta"], cf, (255, 255, 255), anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=92)
    return {"path": str(out), "engine": engine, "size": size, "lang": lang, "style": style or "juicy", "label": SIZE_LABELS[size]}


def render_frame(product: dict, frame: dict, palette: list[str], W: int, H: int, out: Path, idx: int, n: int,
                 lang: str = "en", seed: int = 11, subtitle: str | None = None, show_product: bool = True,
                 engine_pref: list[str] | None = None) -> dict:
    bg, engine = images.scene(frame["scene_prompt"], W, H, palette, seed=seed + idx, prefer=engine_pref)
    canvas = bg.convert("RGBA")
    if show_product:
        scale = 0.62 if idx == n - 1 else 0.42
        pl = product_layer(product, int(W * scale), int(H * scale * 0.8))
        if pl is not None:
            canvas.alpha_composite(pl, ((W - pl.width) // 2, int(H * (0.40 if idx == n - 1 else 0.48))))
    accent = hex_rgb(palette[0])
    f, lines, s, lh = fit_text(frame["on_screen_text"], "serif", int(W * 0.84), int(H * 0.2), int(W * 0.1), lang)
    y = int(H * 0.10)
    box_h = int(len(lines) * s * lh + s * 0.5)
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle((int(W * 0.05), y - int(s * 0.3), int(W * 0.95), y + box_h),
                                         radius=int(W * 0.03), fill=hex_rgb(CANVAS) + (225,))
    canvas = Image.alpha_composite(canvas, ov)
    for line in lines:
        draw_text(canvas, (W // 2, y), line, f, hex_rgb(INK), anchor="ma")
        y += int(s * lh)
    ImageDraw.Draw(canvas).text((int(W * 0.06), int(H * 0.035)), "DOT & KEY",
                                font=font("sans", int(W * 0.035), "en", "ExtraBold").pil, fill=hex_rgb(INK))
    if subtitle:
        sf, sl, ss, slh = fit_text(subtitle, "sans", int(W * 0.86), int(H * 0.14), int(W * 0.045), lang, min_size=18,
                                   weight="SemiBold", spacing=1.3)
        sy = int(H * 0.88) - int(len(sl) * ss * slh)
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).rounded_rectangle((int(W * 0.04), sy - int(ss * 0.4), int(W * 0.96), sy + int(len(sl) * ss * slh + ss * 0.3)),
                                             radius=int(W * 0.02), fill=(20, 20, 22, 165))
        canvas = Image.alpha_composite(canvas, ov)
        for line in sl:
            draw_text(canvas, (W // 2, sy), line, sf, (255, 255, 255), anchor="ma")
            sy += int(ss * slh)
    if idx == n - 1:
        cf = font("sans", int(W * 0.045), lang, "Bold")
        txt = frame.get("cta") or "Shop now"
        tw = text_w(txt, cf)
        ch = int(cf.size * 2)
        cx, cy = int((W - tw - cf.size * 2) // 2), int(H * 0.30)
        ImageDraw.Draw(canvas).rounded_rectangle((cx, cy, cx + tw + cf.size * 2, cy + ch), radius=ch // 2, fill=accent)
        draw_text(canvas, (W // 2, cy + ch // 2), txt, cf, (255, 255, 255), anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=92)
    return {"path": str(out), "engine": engine}
