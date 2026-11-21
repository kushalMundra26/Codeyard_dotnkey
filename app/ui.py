"""Shared UI: design tokens, CSS, data loaders, flow progress, product header, evidence drawer, small components.

Design: calm, dense internal workspace. Fraunces for page/section headings only, Plus Jakarta Sans elsewhere,
tabular numerals for metrics. Accents are functional: orange = Dot & Key / "you are here", pink = negative,
mint = positive, blue = spec/info, yellow = warning.
"""
from __future__ import annotations

import base64
import html
import mimetypes
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import costs, llm, pipeline  # noqa: E402
from core.config import INSIGHTS, brand_color, brand_inputs, brand_list, brand_name, home_brand  # noqa: E402
from core.collect import catalog  # noqa: E402

TOKENS = {
    "canvas": "#FAF9F6", "surface": "#FFFFFF", "rule": "#E6E4DF", "ink": "#1E2022", "slate": "#64686E",
    "mute": "#B8B5AE", "neutral": "#EDEBE6",
    "orange": "#FF803A", "blue": "#22BCE0", "pink": "#F4576C", "mint": "#71B61A", "yellow": "#F5C518",
}
# Sentiment: pink (negative) → neutral → mint (positive). Used by heatmap, bars, tags and quotes alike.
SENT_SCALE = [[0, "#F4576C"], [0.5, "#EDEBE6"], [1, "#71B61A"]]

PAGES = {
    "start": "pages/r_start.py", "market": "pages/r_market.py", "product": "pages/i_product.py",
    "swot": "pages/i_swot.py", "audit": "pages/i_audit.py", "brief": "pages/c_brief.py", "ads": "pages/c_ads.py",
    "copy": "pages/c_copy.py", "approve": "pages/c_approve.py", "trust": "pages/8_Trust.py", "label": "pages/9_Label.py",
    "settings": "pages/10_Settings.py",
}

CSS = """
<style>
:root{
  --canvas:#FAF9F6; --surface:#FFFFFF; --rule:#E6E4DF; --ink:#1E2022; --slate:#64686E; --mute:#B8B5AE;
  --orange:#FF803A; --blue:#22BCE0; --pink:#F4576C; --mint:#71B61A; --yellow:#F5C518;
}
.stApp{ background:var(--canvas); color:var(--ink); }
[data-testid="stHeader"]{ background:transparent; height:2.2rem; }
.block-container{ padding-top:1.6rem !important; padding-bottom:3rem; max-width:1440px; }
h1,h2,h3{ letter-spacing:-0.01em; color:var(--ink); }
h1{ font-size:1.75rem !important; line-height:1.15 !important; padding:0 0 .1rem 0 !important; }
h2{ font-size:1.2rem !important; padding:.2rem 0 .1rem 0 !important; }
h3{ font-size:1rem !important; padding:.1rem 0 !important; }
.stMarkdown p{ margin-bottom:.35rem; }
section[data-testid="stSidebar"] .block-container, section[data-testid="stSidebarUserContent"]{ padding-top:.6rem; }
div[data-testid="stVerticalBlockBorderWrapper"]{ box-shadow:none !important; }
.stButton>button, .stDownloadButton>button{ box-shadow:none; font-weight:600; transition:border-color 120ms, background 120ms; }
.stButton>button[kind="primary"]{ background:var(--ink); border-color:var(--ink); color:#fff; }
.stButton>button[kind="primary"]:hover{ background:#000; border-color:#000; color:#fff; }
/* evidence affordance: tertiary buttons read as underlined tabular counts */
.stButton>button[kind="tertiary"]{ padding:0 2px; min-height:0; height:auto; font-size:12.5px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink); text-decoration:underline; text-decoration-color:var(--mute);
  text-underline-offset:3px; }
.stButton>button[kind="tertiary"]:hover{ text-decoration-color:var(--orange); color:var(--ink); }
[data-baseweb="tab-list"]{ gap:0; border-bottom:1px solid var(--rule); }
[data-baseweb="tab"]{ font-weight:600; color:var(--slate); padding:6px 14px; }
[data-baseweb="tab"][aria-selected="true"]{ color:var(--ink); }
[data-baseweb="tab-highlight"]{ background:var(--orange) !important; height:2px; }
hr{ border-color:var(--rule) !important; margin:.8rem 0 !important; }
[data-testid="stPageLink"] a{ border:1px solid var(--rule); border-radius:6px; background:var(--surface); padding:2px 10px; }
[data-testid="stPageLink"] a:hover{ border-color:var(--ink); }
[data-testid="stPageLink"] a p{ font-weight:600; font-size:13px; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a{ border:none; background:transparent; }

.eyebrow{ font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--slate); font-weight:700; }
.meta{ color:var(--slate); font-size:12.5px; line-height:1.45; }
.meta a, .lead a{ color:var(--ink); }
.num{ font-variant-numeric:tabular-nums; }
.small{ font-size:12px; }

/* page header */
.ph{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap; margin-bottom:6px; }
.ph h1{ margin:0 !important; }
.modebadge{ font-size:11.5px; color:var(--slate); border:1px solid var(--rule); border-radius:4px; padding:3px 8px;
  background:var(--surface); white-space:nowrap; font-variant-numeric:tabular-nums; }
.modebadge b{ color:var(--ink); font-weight:600; }
.modebadge .dot{ display:inline-block; width:6px; height:6px; border-radius:50%; margin-right:5px; vertical-align:1px; }

/* flow progress */
.flow{ display:flex; align-items:stretch; border:1px solid var(--rule); border-radius:6px; background:var(--surface);
  overflow:hidden; margin:6px 0 4px 0; }
.flow .st{ flex:1 1 0; padding:7px 12px 6px 12px; border-right:1px solid var(--rule); min-width:0; position:relative; }
.flow .st:last-child{ border-right:none; }
.flow .st .n{ font-size:10.5px; color:var(--slate); font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.flow .st .l{ font-size:13px; font-weight:600; color:var(--slate); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.flow .st .d{ font-size:11.5px; color:var(--slate); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.flow .st.done .l{ color:var(--ink); }
.flow .st.done .n:after{ content:" ✓"; color:var(--mint); }
.flow .st.cur{ box-shadow: inset 0 -2px 0 var(--orange); }
.flow .st.cur .l{ color:var(--ink); }

/* lead insight */
.lead{ font-size:19px; line-height:1.5; color:var(--ink); font-weight:400; max-width:60ch; }
.lead b{ font-weight:700; font-variant-numeric:tabular-nums; }
.lead .hl{ box-shadow: inset 0 -0.38em 0 rgba(255,128,58,.22); }
.facts{ border-left:1px solid var(--rule); padding-left:16px; }
.facts .r{ display:flex; justify-content:space-between; gap:12px; padding:5px 0; border-bottom:1px solid var(--rule); font-size:13px; }
.facts .r:last-child{ border-bottom:none; }
.facts .r .k{ color:var(--slate); }
.facts .r .v{ font-weight:600; font-variant-numeric:tabular-nums; text-align:right; }

.takeaway{ font-size:14.5px; font-weight:600; color:var(--ink); margin:2px 0 6px 0; line-height:1.4; }
.takeaway b{ font-variant-numeric:tabular-nums; }
.sect{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; border-top:1px solid var(--rule);
  padding-top:14px; margin-top:14px; flex-wrap:wrap; }
.sect h2{ margin:0 !important; padding:0 !important; }
.sect .meta{ font-size:12px; }

/* product header */
.prod{ display:flex; gap:14px; align-items:center; background:var(--surface); border:1px solid var(--rule); border-radius:6px;
  padding:10px 14px; margin:6px 0 8px 0; flex-wrap:wrap; }
.prod img{ width:56px; height:56px; object-fit:contain; border-radius:4px; background:var(--canvas); border:1px solid var(--rule); }
.prod .nm{ font-weight:700; font-size:15px; line-height:1.25; }
.prod .sub{ font-size:12.5px; color:var(--slate); font-variant-numeric:tabular-nums; margin-top:2px; }
.prod .sub s{ color:var(--mute); }
.prod .grow{ flex:1 1 280px; min-width:0; }
.prod .stats{ display:flex; gap:20px; font-variant-numeric:tabular-nums; flex-wrap:wrap; }
.prod .stats div{ font-size:12px; color:var(--slate); }
.prod .stats b{ display:block; font-size:16px; color:var(--ink); font-weight:700; }

/* tags */
.tag{ display:inline-block; font-size:11px; font-weight:600; padding:1px 7px; border-radius:4px; border:1px solid var(--rule);
  color:var(--ink); background:#fff; margin:0 4px 3px 0; letter-spacing:.01em; white-space:nowrap; line-height:1.6; }
.tag.ok{ border-color:#b9dc8c; color:#3f6b0c; background:#f3f9ea; }
.tag.warn{ border-color:#f3dc84; color:#6f5400; background:#fffaeb; }
.tag.block{ border-color:#f7b3bd; color:#a3162b; background:#fff1f3; }
.tag.blue{ border-color:#a7e2f1; color:#0d6c83; background:#effafd; }
.tag.orange{ border-color:#ffc6a6; color:#a34511; background:#fff4ec; }
.tag.quiet{ color:var(--slate); }
.engine{ font-size:11px; color:var(--slate); border:1px dashed var(--rule); border-radius:4px; padding:0 6px; white-space:nowrap; }

/* quotes */
.quote{ border-left:2px solid var(--rule); padding:3px 0 3px 12px; margin:6px 0; font-size:13.5px; color:var(--ink); line-height:1.45; }
.quote.pos{ border-left-color:var(--mint);} .quote.neg{ border-left-color:var(--pink);}
.quote .src{ display:block; color:var(--slate); font-size:11.5px; margin-top:2px; }
.quote code{ font-size:10.5px; color:var(--slate); background:transparent; padding:0; }

/* ledger rows (label · bar · value) */
.lg{ display:flex; align-items:center; gap:10px; font-size:13px; min-height:26px; }
.lg .lab{ flex:0 0 42%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lg .bar{ flex:1 1 auto; height:8px; background:#F1EFEA; border-radius:4px; position:relative; overflow:hidden; }
.lg .bar i{ position:absolute; top:0; bottom:0; border-radius:4px; }
.lg .val{ flex:0 0 52px; text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }
.divbar{ height:8px; background:#F1EFEA; border-radius:4px; position:relative; }
.divbar:after{ content:""; position:absolute; left:50%; top:-3px; bottom:-3px; width:1px; background:var(--mute); }
.divbar i{ position:absolute; top:0; bottom:0; border-radius:4px; }

.row{ display:flex; gap:14px; align-items:baseline; border-bottom:1px solid var(--rule); padding:7px 0; font-size:13px; }
.row .k{ color:var(--slate); font-size:12.5px; min-width:120px; }
.swot{ border-left:3px solid var(--rule); padding:2px 0 2px 14px; margin-bottom:8px; }
.swot.s{ border-left-color:var(--mint);} .swot.w{ border-left-color:var(--pink);} .swot.o{ border-left-color:var(--blue);} .swot.t{ border-left-color:var(--orange);}
.empty{ border:1px dashed var(--mute); border-radius:6px; padding:18px 20px; background:var(--surface); }
.empty .t{ font-weight:700; font-size:15px; margin-bottom:4px; }
.wordmark{ font-weight:800; letter-spacing:.14em; font-size:12.5px; color:var(--ink); }
.wordmark span{ color:var(--orange); }
.board-h{ font-size:11px; color:var(--slate); font-weight:700; letter-spacing:.06em; text-transform:uppercase; margin-bottom:2px; }
[data-testid="stImage"] img{ border:1px solid var(--rule); border-radius:4px; }
[data-testid="stImageCaption"]{ font-size:11.5px; color:var(--slate); }
.adcopy{ font-size:15px; font-weight:700; line-height:1.3; }
.adsub{ font-size:13px; color:var(--slate); }
[class*="st-key-ledger"], [class*="st-key-ledger"] [data-testid="stVerticalBlock"]{ gap:0 !important; }
[class*="st-key-ledger"] [data-testid="stHorizontalBlock"]{ min-height:28px; }
[class*="st-key-ledger"] .stButton{ text-align:right; }
[class*="st-key-ledger"] [data-testid="stHorizontalBlock"]{ flex-wrap:nowrap !important; gap:.5rem !important; }
[class*="st-key-ledger"] [data-testid="stColumn"]{ min-width:0 !important; }
[class*="st-key-board"] [data-testid="stHorizontalBlock"]{ flex-wrap:nowrap !important; }
[class*="st-key-board"] [data-testid="stColumn"]{ min-width:0 !important; }
@media (max-width: 640px){
  .flow .st .d{ display:none; } .flow .st{ padding:6px 6px; } .flow .st .l{ font-size:11.5px; }
  .lead{ font-size:16.5px; } .facts{ border-left:none; padding-left:0; }
  .lg .lab{ flex-basis:38%; }
}
</style>
"""


# ---------------- formatting helpers ----------------

def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def inr(x, dec: int = 0) -> str:
    if x is None or x != x:
        return "—"
    return f"₹{x:,.{dec}f}"


def pct(x, dec: int = 0) -> str:
    return "—" if x is None or x != x else f"{x * 100:.{dec}f}%"


def friendly_name(title: str, n: int = 60) -> str:
    """'Dot & Key Watermelon Cooling Sunscreen SPF 50+ PA++++ - 50ml' → 'Watermelon Cooling Sunscreen'."""
    t = title or ""
    t = re.sub(r"^\s*dot\s*(&|and)\s*key\s*", "", t, flags=re.I)
    t = re.sub(r"\s*[-–|,]\s*\d+(\.\d+)?\s*(ml|g|gm)\b.*$", "", t, flags=re.I)
    t = re.sub(r"\bSPF\s*\d+\+?\s*(PA\+*)?", "", t, flags=re.I)
    t = re.sub(r"\bPA\+{2,}", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–,|")
    return (t[: n - 1] + "…") if len(t) > n else t


def sent_kind(net: float) -> str:
    return "ok" if net >= 0.25 else "block" if net <= -0.15 else "warn"


def sent_color(net: float) -> str:
    return TOKENS["mint"] if net >= 0.15 else TOKENS["pink"] if net <= -0.15 else TOKENS["mute"]


@st.cache_data(show_spinner=False, max_entries=512)
def _data_uri(path: str, mtime: float) -> str:
    mt = mimetypes.guess_type(path)[0] or "image/png"
    try:
        from PIL import Image
        import io
        im = Image.open(path)
        im.thumbnail((240, 240))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return f"data:{mt};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def img_src(src: str | None, width: int = 200) -> str | None:
    """Usable <img src> for a Shopify URL (resized) or a local packshot (inlined)."""
    if not src:
        return None
    if src.startswith("http"):
        if "cdn.shopify.com" in src and "width=" not in src:
            src += ("&" if "?" in src else "?") + f"width={width}"
        return src
    p = Path(src)
    return _data_uri(str(p), p.stat().st_mtime) if p.exists() else None


def st_img(src: str | None, width: int = 500):
    """Argument for st.image: local path as-is, Shopify URL resized."""
    if not src:
        return None
    if src.startswith("http"):
        return img_src(src, width)
    return src if Path(src).exists() else None


# ---------------- data loaders ----------------

@st.cache_data(show_spinner=False)
def _load(cat: str, mtime: float):
    return pipeline.load_insights(cat)


def insights(cat: str | None = None) -> dict | None:
    cat = cat or st.session_state.get("cat", "sunscreen")
    p = INSIGHTS / f"{cat}.json"
    if not p.exists():
        return None
    return _load(cat, p.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _reviews(cat: str, mtime: float) -> dict:
    ins = pipeline.load_insights(cat)
    return {r["review_id"]: r for r in pipeline.all_reviews(ins)}


def reviews_by_id(cat: str | None = None) -> dict:
    cat = cat or st.session_state.get("cat", "sunscreen")
    p = INSIGHTS / f"{cat}.json"
    return _reviews(cat, p.stat().st_mtime) if p.exists() else {}


@st.cache_data(show_spinner=False)
def _ctx(cat: str, mtime: float, handle: str) -> dict:
    return pipeline.product_context(pipeline.load_insights(cat), handle)


def context(ins: dict, handle: str) -> dict:
    p = INSIGHTS / f"{ins['category']}.json"
    return _ctx(ins["category"], p.stat().st_mtime, handle)


def need_insights() -> dict:
    ins = insights()
    if not ins:
        empty_state("No analysis for this category yet",
                    "Every page here reads the analysis output. Start with Research.", "start", "Start with Research")
        st.stop()
    return ins


def home_products(ins: dict) -> list[dict]:
    return [p for p in ins["products"] if p["brand"] == home_brand()]


def current_product(ins: dict) -> dict:
    h = st.session_state.get("handle")
    home = home_products(ins)
    return next((p for p in home if p["handle"] == h), home[0] if home else ins["products"][0])


def campaigns_for(handle: str) -> list[dict]:
    return [c for c in pipeline.list_campaigns() if c["id"].startswith(handle[:40])]


def current_campaign(handle: str) -> dict | None:
    cid = st.session_state.get("campaign_id")
    if not cid or not cid.startswith(handle[:40]):
        cs = campaigns_for(handle)
        cid = cs[0]["id"] if cs else None
    return pipeline.load_campaign(cid) if cid else None


def snapshot_date() -> str | None:
    ds = [d for b in brand_list() for d in catalog.snapshot_dates(b)]
    return max(ds) if ds else None


# ---------------- shell: guided flow ----------------

FLOW = [("research_done", "Research", "start"), ("insight_done", "Insight", "product"),
        ("brief_done", "Brief", "brief"), ("render_done", "Ads", "ads"), ("approved", "Approve", "approve")]

FLOW_CSS = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"]{ display:none !important; }
.block-container{ max-width:1120px !important; padding-left:clamp(16px,3vw,40px) !important; padding-right:clamp(16px,3vw,40px) !important;
  padding-top:3.6rem !important; }
h1{ font-size:2rem !important; }
.topline{ display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; margin:0 0 18px 0; }
.steps{ display:flex; gap:0; flex-wrap:wrap; font-size:12px; color:var(--slate); font-weight:600; }
.steps span{ padding:2px 10px 2px 0; margin-right:10px; border-right:1px solid var(--rule); white-space:nowrap; }
.steps span:last-child{ border-right:none; }
.steps .done{ color:var(--ink); } .steps .done:before{ content:"✓ "; color:var(--mint); }
.steps .cur{ color:var(--ink); box-shadow: inset 0 -2px 0 var(--orange); }
.intro{ font-size:16px; line-height:1.55; color:var(--slate); max-width:64ch; margin:2px 0 22px 0; }
.empty{ padding:28px 28px; border-style:solid; border-color:var(--rule); }
.reason{ background:var(--surface); border:1px solid var(--rule); border-radius:8px; padding:20px 24px; margin:8px 0 18px 0; }
.reason .h{ font-family:Fraunces,Georgia,serif; font-size:18px; font-weight:600; margin-bottom:10px; }
.reason .l{ font-size:14px; line-height:1.5; padding:5px 0; color:var(--ink); }
.reason .l .tick{ color:var(--mint); font-weight:700; margin-right:8px; }
.reason .l.now{ color:var(--slate); }
.reason .l.now .tick{ color:var(--orange); }
.reason .l b{ font-variant-numeric:tabular-nums; }
[class*="st-key-tile"]{ background:var(--surface); border-radius:8px; transition:outline-color 120ms; }
[class*="st-key-tilesel"]{ outline:2px solid var(--ink); outline-offset:-1px; }
[class*="st-key-tileoff"]{ opacity:.55; }
.tile-img{ width:100%; aspect-ratio:1/1; max-height:260px; object-fit:contain; background:var(--canvas); border-radius:6px; border:1px solid var(--rule); }
.tile-t{ font-weight:700; font-size:15px; line-height:1.3; margin-top:8px; }
.tile-s{ font-size:12.5px; color:var(--slate); line-height:1.45; margin-top:2px; }
.tile-big{ font-family:Fraunces,Georgia,serif; font-size:20px; font-weight:600; line-height:1.2; }
.cat-ico{ font-family:Fraunces,Georgia,serif; font-size:26px; font-weight:600; }
.next-row{ border-top:1px solid var(--rule); margin-top:28px; padding-top:18px; }
@media (max-width: 640px){ .block-container{ padding-top:3rem !important; } h1{ font-size:1.6rem !important; } }
</style>
"""


def is_live() -> bool:
    return st.session_state.get("mode") == "Live"


def flags() -> dict:
    return {k: bool(st.session_state.get(k)) for k, *_ in FLOW}


def setup(title: str, eyebrow: str = "", step: str | None = None, badge: bool = True, intro: str = "") -> dict | None:
    """CSS + top line (progress + mode badge) + page header. Returns the insights dict (or None)."""
    st.markdown(CSS + FLOW_CSS, unsafe_allow_html=True)
    st.session_state.setdefault("cat", "sunscreen")
    st.session_state.setdefault("mode", "Demo")
    ins = insights(st.session_state["cat"])
    f = flags()
    cells = []
    for k, label, key in FLOW:
        cls = "done" if f[k] else ("cur" if key == step else "")
        cells.append(f'<span class="{cls}">{esc(label)}</span>')
    st.markdown(f'<div class="topline"><div class="steps">{"".join(cells)}</div>{mode_badge(ins) if badge else ""}</div>',
                unsafe_allow_html=True)
    if eyebrow:
        st.markdown(f'<div class="eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"# {title}")
    if intro:
        st.markdown(f'<div class="intro">{intro}</div>', unsafe_allow_html=True)
    return ins


def mode_badge(ins: dict | None) -> str:
    live = is_live()
    dot = TOKENS["orange"] if live else TOKENS["mute"]
    parts = [f'<span class="dot" style="background:{dot}"></span><b>{"Live" if live else "Demo"}</b>']
    if not live:
        parts.append("saved data · no paid calls")
    return f'<span class="modebadge">{" · ".join(parts)}</span>'


def gate(flag: str, title: str, body: str, page: str, cta: str):
    """Calm empty state pointing at the previous step; stops the page."""
    if st.session_state.get(flag):
        return
    empty_state(title, body)
    if st.button(f"{cta}  →", type="primary", key=f"gate_{flag}_{page}"):
        st.switch_page(PAGES[page])
    st.stop()


def continue_to(page: str, label: str, why: str = "", key: str | None = None):
    st.markdown('<div class="next-row"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([0.62, 0.38], vertical_alignment="center")
    if why:
        c1.markdown(f'<div class="meta"><span class="eyebrow">Next</span><br/>{why}</div>', unsafe_allow_html=True)
    if c2.button(f"{label}  →", type="primary", width="stretch", key=key or f"next_{page}"):
        st.switch_page(PAGES[page])


def reasoning(title: str, lines: list[str], seconds: float = 7.0, box=None):
    """Reveal a narrative of real numbers line by line (trusted HTML lines)."""
    import time
    box = box or st.empty()
    per = max(0.35, seconds / max(1, len(lines)))
    for i in range(len(lines) + 1):
        out = []
        for j, ln in enumerate(lines[:i + 1]):
            if j < i:
                out.append(f'<div class="l"><span class="tick">✓</span>{ln}</div>')
            elif j < len(lines):
                out.append(f'<div class="l now"><span class="tick">→</span>{ln}</div>')
        box.markdown(f'<div class="reason"><div class="h">{esc(title)}</div>{"".join(out)}</div>', unsafe_allow_html=True)
        if i < len(lines):
            time.sleep(per)
    return box


def research_lines(ins: dict, handle: str) -> list[str]:
    m = ins["metrics"]
    n_rev = sum(m.get("n_reviews", {}).values())
    brands_ = {p["brand"] for p in ins["products"]}
    cs = m.get("complaint_share") or []
    p = next((x for x in ins["products"] if x["handle"] == handle), ins["products"][0])
    ctx = context(ins, handle)
    out = [f"Loaded <b>{sum(ins.get('catalog_counts', {}).values()):,}</b> products from <b>{len(brands_)}</b> brand catalogues "
           f"and kept <b>{len(ins['products'])}</b> {esc(ins['category'].replace('_', ' '))} SKUs",
           f"Read <b>{n_rev:,}</b> customer reviews from <b>{len(m.get('n_reviews', {}))}</b> brands' own review feeds",
           f"Labelled <b>{len(ins.get('labels') or []):,}</b> topic × sentiment mentions, each with an exact quote"]
    if cs:
        out.append(f"<b>{esc(cs[0]['label'])}</b> is the category's #1 complaint (<b>{cs[0]['share_of_complaints'] * 100:.0f}%</b> of complaints)"
                   + (f", then {esc(cs[1]['label'].lower())} (<b>{cs[1]['share_of_complaints'] * 100:.0f}%</b>)" if len(cs) > 1 else ""))
    if ctx["rivals"]:
        r0 = ctx["rivals"][0]
        out.append(f"Matched <b>{len(ctx['rivals'])}</b> closest rivals to {esc(friendly_name(p['title'], 40))} — nearest is "
                   f"<b>{esc(r0['brand_name'])}</b> (match {r0['match']['score']:.2f}, {esc(r0['match']['reason'])})")
    out.append("Built the price ladder (₹/ml) and the marketplace snapshot")
    return out


def selected_handle(ins: dict) -> str:
    h = st.session_state.get("handle")
    if h and any(p["handle"] == h for p in ins["products"]):
        return h
    return home_products(ins)[0]["handle"]


def demo_campaign(handle: str, persona_id: str | None = None) -> dict | None:
    """Latest saved campaign for the product (and persona if given); prefers college_commuter."""
    cs = campaigns_for(handle)
    if persona_id:
        cs = [c for c in cs if f"-{persona_id}-" in c["id"]]
    else:
        cs = sorted(cs, key=lambda c: "college_commuter" not in c["id"])
    return pipeline.load_campaign(cs[0]["id"]) if cs else None


def active_campaign() -> dict | None:
    cid = st.session_state.get("campaign_id")
    return pipeline.load_campaign(cid) if cid else None



# ---------------- building blocks ----------------

def section(title: str, meta: str = "", first: bool = False):
    style = ' style="border-top:none;margin-top:4px;padding-top:4px"' if first else ""
    st.markdown(f'<div class="sect"{style}><h2>{esc(title)}</h2><span class="meta">{meta}</span></div>',
                unsafe_allow_html=True)


def takeaway(text_html: str):
    """Plain-language headline above a chart. Pass trusted HTML (numbers in <b>)."""
    st.markdown(f'<div class="takeaway">{text_html}</div>', unsafe_allow_html=True)


def caption(text: str):
    st.markdown(f'<div class="meta" style="margin-top:-4px">{text}</div>', unsafe_allow_html=True)


def empty_state(title: str, body: str, page: str | None = None, cta: str | None = None):
    st.markdown(f'<div class="empty"><div class="t">{esc(title)}</div><div class="meta">{body}</div></div>',
                unsafe_allow_html=True)
    if page and cta:
        if st.button(f"{cta}  →", key=f"empty_{page}_{abs(hash(title)) % 10000}"):
            st.switch_page(PAGES[page])


def tag(text: str, kind: str = "") -> str:
    return f'<span class="tag {kind}">{esc(text)}</span>'


def status_tag(kind: str, text: str | None = None) -> str:
    """ok / warn / block status tag, always with a glyph + word (never colour alone)."""
    default = {"ok": "✓ ok", "warn": "! check", "block": "✕ blocked"}
    return tag(text or default.get(kind, kind), kind)


def verdict_tag(v: str) -> str:
    return status_tag(v, {"ok": "✓ claims ok", "warn": "! check claim", "block": "✕ blocked"}.get(v))


def engine_badge(name: str | None) -> str:
    return f'<span class="engine">engine · {esc(name or "?")}</span>'


def lg_bar(label: str, value: float, vmax: float, text: str, color: str = "#F4576C") -> str:
    w = 0 if not vmax else max(2, min(100, value / vmax * 100))
    return (f'<div class="lg"><span class="lab" title="{esc(label)}">{esc(label)}</span><span class="bar">'
            f'<i style="left:0;width:{w:.1f}%;background:{color}"></i></span><span class="val">{text}</span></div>')


def div_bar(net: float) -> str:
    """Diverging bar for a net sentiment in [-1, 1] around a centre rule."""
    net = max(-1.0, min(1.0, float(net or 0)))
    w = abs(net) * 50
    left = 50 if net >= 0 else 50 - w
    return f'<div class="divbar"><i style="left:{left:.1f}%;width:{max(w, 1):.1f}%;background:{sent_color(net)}"></i></div>'


def stars(r) -> str:
    return "—" if r is None or r != r else f"★ {float(r):.1f}"


def product_header(p: dict, ctx: dict | None = None, extra: str = ""):
    """Persistent product identity on product-scoped pages."""
    s = p.get("spec") or {}
    tags = [f"SPF {s['spf']}" if s.get("spf") else None, s.get("pa"), s.get("format"), s.get("finish"), s.get("filter_type")]
    tag_html = "".join(tag(t, "blue") for t in tags if t)
    price = f"<b style='color:var(--ink)'>{inr(p.get('price'))}</b>"
    if p.get("mrp"):
        price += f" <s>{inr(p['mrp'])}</s> · {p.get('discount_pct', 0):.0f}% off"
    size = f"{p['size']:.0f} {p['unit']}" if p.get("size") else "size n/a"
    ppm = f"₹{p['price_per_ml']:.2f}/ml" if p.get("price_per_ml") else ""
    cov = (ctx or {}).get("coverage") or {}
    rt = (ctx or {}).get("rating") or {}
    shown = cov.get("shown_avg")
    stats = []
    if shown or rt.get("avg_rating"):
        stats.append(f"<div><b>{stars(shown or rt.get('avg_rating'))}</b>{'on store' if shown else 'collected'}"
                     f"{' · ' + format(int(cov['shown_count']), ',') if cov.get('shown_count') else ''}</div>")
    if rt:
        stats.append(f"<div><b>{rt.get('n', 0):,}</b>reviews read</div>")
    if ctx is not None:
        stats.append(f"<div><b>{len(ctx.get('rivals', []))}</b>rivals tracked</div>")
    src = img_src(p.get("image"), 160)
    img = f'<img src="{src}" alt=""/>' if src else '<img alt=""/>'
    st.markdown(f'<div class="prod">{img}<div class="grow"><div class="nm">{esc(friendly_name(p["title"], 90))}</div>'
                f'<div class="sub">{price} · {size}{" · " + ppm if ppm else ""} · <a href="{esc(p.get("url", ""))}" target="_blank" '
                f'style="color:var(--slate)">store listing ↗</a></div><div style="margin-top:4px">{tag_html}{extra}</div></div>'
                f'<div class="stats">{"".join(stats)}</div></div>', unsafe_allow_html=True)


# ---------------- evidence drawer ----------------

@st.dialog("Evidence", width="large")
def evidence_dialog(title: str, review_ids: list[str], labels: list[dict] | None = None, note: str = ""):
    revs = reviews_by_id()
    st.markdown(f"**{esc(title)}**")
    if note:
        st.caption(note)
    lab: dict = {}
    for l in labels or []:
        lab.setdefault(l["review_id"], []).append(l)
    shown = [rid for rid in review_ids if rid in revs]
    n_pos = sum(1 for rid in shown if any(l["sentiment"] > 0 for l in lab.get(rid, [])))
    n_neg = sum(1 for rid in shown if any(l["sentiment"] < 0 for l in lab.get(rid, [])))
    st.markdown(f'<div class="meta num">n = {len(review_ids)} reviews behind this number'
                f'{f" · {n_pos} positive · {n_neg} negative" if lab else ""} · showing up to 40 · '
                f'highlighted text is the exact quote the labeller used</div>', unsafe_allow_html=True)
    for rid in review_ids[:40]:
        r = revs.get(rid)
        if not r:
            st.markdown(f'<div class="quote"><code>{esc(rid)}</code></div>', unsafe_allow_html=True)
            continue
        ls = lab.get(rid, [])
        cls = "pos" if any(l["sentiment"] > 0 for l in ls) else "neg" if any(l["sentiment"] < 0 for l in ls) else ""
        body = esc((r.get("title") + " — " if r.get("title") else "") + (r.get("body") or ""))[:700]
        for l in ls:
            q = esc(l["quote"])
            body = body.replace(q, f"<mark style='background:#fff1c2;padding:0 1px'>{q}</mark>", 1)
        st.markdown(f'<div class="quote {cls}">{body}<span class="src">{stars(r.get("rating"))} · {esc(brand_name(r["brand"]))} · '
                    f'{esc(friendly_name(r["handle"].replace("-", " "), 40))} · {str(r.get("date") or "")[:10]} · '
                    f'{"verified buyer" if r.get("verified") else "unverified"} · <code>{esc(rid)}</code></span></div>',
                    unsafe_allow_html=True)


def evidence_count_button(n: int | None, title: str, review_ids: list[str], key: str, labels=None, note: str = "",
                          label: str | None = None):
    """Clickable 'n = 42' — opens the reviews behind a number."""
    ids = [i for i in review_ids if str(i).startswith("r:")]
    text = label or f"n = {n if n is not None else len(ids)}"
    if not ids:
        st.markdown(f'<span class="meta num">{esc(text)}</span>', unsafe_allow_html=True)
        return
    if st.button(text, key=key, type="tertiary", help="Open the reviews behind this number"):
        evidence_dialog(title, ids, labels, note)


def evidence_button(label: str, title: str, review_ids: list[str], key: str, labels=None, note: str = "",
                    kind: str = "tertiary"):
    evidence_count_button(None, title, review_ids, key, labels, note, label=label)


def review_ids(ev: list[str]) -> list[str]:
    return [i for i in ev or [] if str(i).startswith("r:")]


def resolve_evidence(ins: dict, ev: list[str]) -> tuple[list[str], list[dict], list[str]]:
    """Mixed evidence ids → (review ids, matching labels for highlighting, human-readable metric notes).
    m:net:<brand>:<topic>[|handle] and m:complaint:<topic> resolve to the reviews behind them."""
    rids, labs, notes = [], [], []
    labels = ins.get("labels", [])
    for e in ev or []:
        e = str(e)
        if e.startswith("r:"):
            rids.append(e)
            continue
        parts = e.split(":")
        if len(parts) >= 4 and parts[1] == "net":
            brand, rest = parts[2], ":".join(parts[3:])
            topic, _, handle = rest.partition("|")
            ls = [l for l in labels if l["brand"] == brand and l["topic"] == topic and (not handle or l["handle"] == handle)]
            rids += [l["review_id"] for l in ls]
            labs += ls
            notes.append(f"{brand_name(brand)} · {topic.replace('_', ' ')} sentiment")
        elif len(parts) >= 3 and parts[1] == "complaint":
            ls = [l for l in labels if l["topic"] == parts[2] and l["sentiment"] < 0]
            rids += [l["review_id"] for l in ls]
            labs += ls
            notes.append(f"complaints · {parts[2].replace('_', ' ')}")
        elif len(parts) >= 3 and parts[1] == "price":
            notes.append(f"{brand_name(parts[2])} price ladder")
        else:
            notes.append(e.replace("m:", ""))
    return list(dict.fromkeys(rids)), labs, notes


def quote_html(q: dict, show_brand=True) -> str:
    cls = "pos" if q["sentiment"] > 0 else "neg" if q["sentiment"] < 0 else ""
    topic = (q.get("topic") or "").replace("_", " ")
    src = f'{brand_name(q["brand"])} · {topic}' if show_brand else topic
    return (f'<div class="quote {cls}">“{esc(q["quote"][:220])}”<span class="src">{esc(src)} · '
            f'<code>{esc(q["review_id"])}</code></span></div>')


# ---------------- charts ----------------

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def plotly_layout(fig, h=360, legend=True):
    fig.update_layout(height=h, margin=dict(l=4, r=12, t=8, b=4), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                      font=dict(family="Plus Jakarta Sans, Helvetica Neue, Arial, sans-serif", size=12, color="#1E2022"),
                      hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E6E4DF", font=dict(color="#1E2022", size=12)),
                      showlegend=legend,
                      legend=dict(orientation="h", y=-0.14, x=0, font=dict(size=11, color="#64686E"), title=None))
    fig.update_xaxes(gridcolor="#F1EFEA", zerolinecolor="#E6E4DF", linecolor="#E6E4DF", tickfont=dict(color="#64686E"),
                     title_font=dict(color="#64686E", size=11))
    fig.update_yaxes(gridcolor="#F1EFEA", zerolinecolor="#E6E4DF", linecolor="#E6E4DF", tickfont=dict(color="#64686E"),
                     title_font=dict(color="#64686E", size=11))
    return fig


def chart(fig, h=360, legend=True, key=None):
    st.plotly_chart(plotly_layout(fig, h, legend), width="stretch", config=PLOTLY_CONFIG, key=key)


def brand_colors() -> dict:
    return {brand_name(b): brand_color(b) for b in brand_list()}


def emphasis_colors(names: list[str]) -> dict:
    """Dot & Key in orange, every rival muted — the story is always 'us vs the field'."""
    home = brand_name(home_brand())
    return {n: (TOKENS["orange"] if n == home else TOKENS["mute"]) for n in names}


def df(records) -> pd.DataFrame:
    return pd.DataFrame(records or [])


# ---------------- marketplace snapshot ----------------

MARKET_LABEL = "Marketplace snapshot · collected via Gemini + Google Search · verify links"


def marketplace_table(rows: list[dict], key: str | None = None):
    if not rows:
        st.markdown('<div class="meta">No marketplace rows for this selection.</div>', unsafe_allow_html=True)
        return
    d = pd.DataFrame([{
        "Brand": r.get("brand"), "Marketplace": r.get("marketplace"),
        "Listing": r.get("product_name_on_listing"), "Price": r.get("price_inr"), "MRP": r.get("mrp_inr"),
        "Off": r.get("discount_pct"),
        "Rating": r.get("rating"), "Ratings": r.get("rating_count"), "Bestseller rank": r.get("bestseller_rank") or "—",
        "Link": r.get("url"), "Checked": r.get("checked_at")} for r in rows])
    st.dataframe(d, hide_index=True, width="stretch", key=key,
                 column_config={
                     "Listing": st.column_config.TextColumn(width="large"),
                     "Price": st.column_config.NumberColumn(format="₹%d"),
                     "MRP": st.column_config.NumberColumn(format="₹%d"),
                     "Off": st.column_config.NumberColumn(format="%.0f%%"),
                     "Rating": st.column_config.NumberColumn(format="★ %.1f"),
                     "Ratings": st.column_config.NumberColumn(format="localized"),
                     "Link": st.column_config.LinkColumn(display_text="open ↗"),
                 })


# ---------------- access gate for hosted demos ----------------

def can_act() -> bool:
    """If APP_PASSCODE is set (e.g. in Streamlit Cloud secrets), actions that call paid/rate-limited APIs
    need the passcode once per session. Browsing the committed data never does."""
    import os
    code = os.environ.get("APP_PASSCODE", "")
    return not code or st.session_state.get("unlocked") is True


def passcode_box():
    import os
    code = os.environ.get("APP_PASSCODE", "")
    if not code or st.session_state.get("unlocked"):
        return
    with st.container():
        v = st.text_input("Demo passcode", type="password", help="Needed to generate new content on the hosted demo.")
        if v and v == code:
            st.session_state["unlocked"] = True
            st.rerun()
        elif v:
            st.caption("Wrong passcode.")
