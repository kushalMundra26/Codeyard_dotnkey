"""Complex-script text rendering (Devanagari, Bengali, Tamil) without libraqm.

Pillow's basic layout can't form conjuncts (e.g. गर्मी). We shape with HarfBuzz (uharfbuzz) and rasterise the
shaped glyph ids with FreeType (freetype-py), then hand Pillow an RGBA image. Latin text keeps using Pillow."""
from __future__ import annotations

from functools import lru_cache

import freetype
import numpy as np
import uharfbuzz as hb
from PIL import Image

WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700, "ExtraBold": 800}


@lru_cache(maxsize=16)
def _blob(path: str):
    with open(path, "rb") as f:
        return f.read()


@lru_cache(maxsize=64)
def _faces(path: str, size: int, weight: str):
    data = _blob(path)
    hb_face = hb.Face(data)
    hb_font = hb.Font(hb_face)
    w = WEIGHTS.get(weight, 700)
    try:
        hb_font.set_variations({"wght": w})
    except Exception:
        pass
    hb_font.scale = (size * 64, size * 64)
    ft = freetype.Face(path)
    ft.set_char_size(size * 64)
    try:
        axes = ft.get_variation_info().axes
        coords = [w if a.tag == "wght" else a.default for a in axes]
        ft.set_var_design_coords(coords)
    except Exception:
        pass
    return hb_font, ft


def shape(text: str, path: str, size: int, weight: str = "Bold"):
    hb_font, _ = _faces(path, size, weight)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})
    return buf.glyph_infos, buf.glyph_positions


def width(text: str, path: str, size: int, weight: str = "Bold") -> float:
    _, pos = shape(text, path, size, weight)
    return sum(p.x_advance for p in pos) / 64


def render(text: str, path: str, size: int, color=(30, 32, 34), weight: str = "Bold") -> Image.Image:
    """Return an RGBA image of the shaped text; baseline sits at y = ascent."""
    infos, pos = shape(text, path, size, weight)
    _, ft = _faces(path, size, weight)
    asc = int(ft.size.ascender / 64)
    desc = int(-ft.size.descender / 64)
    W = int(sum(p.x_advance for p in pos) / 64) + size
    H = asc + desc + size // 3
    canvas = np.zeros((H, W), dtype=np.uint8)
    x = size // 6
    for info, p in zip(infos, pos):
        ft.load_glyph(info.codepoint, freetype.FT_LOAD_DEFAULT | freetype.FT_LOAD_TARGET_NORMAL)
        ft.glyph.render(freetype.FT_RENDER_MODE_NORMAL)
        bm = ft.glyph.bitmap
        if bm.width and bm.rows:
            g = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width]
            gx = int(x + p.x_offset / 64 + ft.glyph.bitmap_left)
            gy = int(asc - p.y_offset / 64 - ft.glyph.bitmap_top)
            y0, x0 = max(gy, 0), max(gx, 0)
            y1, x1 = min(gy + bm.rows, H), min(gx + bm.width, W)
            if y1 > y0 and x1 > x0:
                sub = g[y0 - gy:y1 - gy, x0 - gx:x1 - gx]
                canvas[y0:y1, x0:x1] = np.maximum(canvas[y0:y1, x0:x1], sub)
        x += p.x_advance / 64
    img = Image.new("RGBA", (W, H), tuple(color) + (0,))
    solid = Image.new("RGBA", (W, H), tuple(color) + (255,))
    img.paste(solid, (0, 0), Image.fromarray(canvas))
    return img
