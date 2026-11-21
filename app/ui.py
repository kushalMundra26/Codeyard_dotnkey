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
    "overview": "pages/1_Overview.py", "product": "pages/2_Product.py", "strategy": "pages/3_Strategy.py",
    "audit": "pages/4_Audit.py", "studio": "pages/5_Studio.py", "radar": "pages/6_Radar.py",
    "packs": "pages/7_Packs.py", "trust": "pages/8_Trust.py", "label": "pages/9_Label.py",
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
                    "Every page here reads the analysis output. Run it once from Market overview — in Demo mode it uses the "
                    "saved catalogue snapshots and takes seconds.", "overview", "Go to Market overview")
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


# ---------------- shell ----------------

def setup(title: str, eyebrow: str = "", step: str | None = None, badge: bool = True) -> dict | None:
    """CSS + sidebar + page header + flow progress. Returns the insights dict (or None)."""
    st.markdown(CSS, unsafe_allow_html=True)
    ins = sidebar()
    passcode_box()
    if callable(step):
        step = step(ins)
    if step in ("insight",):
        st.session_state["seen_insight"] = True
    cat = st.session_state.get("cat", "sunscreen").replace("_", " ")
    eb = f'<div class="eyebrow">{esc(eyebrow)}{" · " + esc(cat) if eyebrow else esc(cat)}</div>'
    st.markdown(f'{eb}<div class="ph"><h1>{esc(title)}</h1>{mode_badge(ins) if badge else ""}</div>', unsafe_allow_html=True)
    if step:
        flow_progress(step, ins)
    return ins


def mode_badge(ins: dict | None) -> str:
    live = st.session_state.get("mode") == "Live"
    dot = TOKENS["orange"] if live else TOKENS["mute"]
    parts = [f'<span class="dot" style="background:{dot}"></span><b>{"Live" if live else "Demo"}</b>']
    sd = snapshot_date()
    if sd:
        parts.append(f"snapshot {sd}")
    if ins:
        parts.append(f'labels <b>{esc((ins.get("label_stats") or {}).get("engine", "?"))}</b>')
    prov = llm.provider()
    parts.append(f'LLM <b>{esc(prov if prov != "none" else "off")}</b>')
    return f'<span class="modebadge">{" · ".join(parts)}</span>'


FLOW = [("research", "Research", "Catalogues + reviews"), ("insight", "Insight", "Rivals, topics, SWOT"),
        ("brief", "Brief", "Evidence-led brief"), ("content", "Content", "Ads, copy, video"), ("approve", "Approve", "Review & ship")]


def flow_state(ins: dict | None) -> dict:
    s = {k: (False, "") for k, *_ in FLOW}
    if not ins:
        return s | {"research": (False, "analysis not run")}
    n_rev = sum(ins["metrics"].get("n_reviews", {}).values())
    s["research"] = (True, f"{len(ins['products'])} SKUs · {n_rev:,} reviews")
    s["insight"] = (bool(st.session_state.get("seen_insight")), "product deep-dive & SWOT")
    p = current_product(ins)
    camp = current_campaign(p["handle"])
    if camp:
        s["insight"] = (True, s["insight"][1])
        s["brief"] = (True, camp["persona"]["name"].split(",")[0] + " persona")
        langs = list(camp.get("regional", {}).keys())
        n_ads = len(camp["ads"]["assets"])
        vids = sum(1 for v in camp.get("videos", []) if v.get("path"))
        s["content"] = (n_ads > 0, f"{n_ads} ads · {vids} video" + (f" · {'/'.join(langs)}" if langs else " · EN only"))
        st_ = camp.get("status") or "draft"
        s["approve"] = (st_ == "approved", {"approved": "approved", "rejected": "rejected"}.get(
            st_, "sent — awaiting reply" if st.session_state.get(f"sent_{camp['id']}") else "not sent yet"))
    else:
        s["brief"] = (False, "no campaign for this product")
        s["content"] = (False, "—")
        s["approve"] = (False, "—")
    return s


def flow_progress(current: str, ins: dict | None = None):
    s = flow_state(ins)
    cells = []
    for i, (k, label, _) in enumerate(FLOW):
        done, detail = s[k]
        cls = ("done " if done else "") + ("cur" if k == current else "")
        cells.append(f'<div class="st {cls}"><div class="n">Step {i + 1}</div><div class="l">{esc(label)}</div>'
                     f'<div class="d">{esc(detail)}</div></div>')
    st.markdown(f'<div class="flow">{"".join(cells)}</div>', unsafe_allow_html=True)


def next_step(page: str, label: str, why: str = ""):
    """One clear call-to-action at the end of a page."""
    st.markdown('<div class="sect"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([0.62, 0.38], vertical_alignment="center")
    if why:
        c1.markdown(f'<div class="meta"><span class="eyebrow">Next step</span><br/>{why}</div>', unsafe_allow_html=True)
    c2.page_link(PAGES[page], label=f"{label}  →", width="stretch")


def sidebar() -> dict | None:
    with st.sidebar:
        st.markdown('<div class="wordmark">DOT <span>&amp;</span> KEY · SIGNALSTUDIO</div>'
                    '<div class="meta" style="margin-bottom:8px">Market signal → evidence-led content</div>',
                    unsafe_allow_html=True)
        from core.config import categories
        cats = [c for c in pipeline.available_categories() if c in categories()] or ["sunscreen"]
        cur_cat = st.session_state.get("cat")
        cat = st.selectbox("Category", cats, index=cats.index(cur_cat) if cur_cat in cats else 0,
                           format_func=lambda c: c.replace("_", " ").title(), key="cat_select")
        st.session_state["cat"] = cat
        ins = insights(cat)
        if ins:
            home = home_products(ins)
            handles = [p["handle"] for p in home]
            by_h = {p["handle"]: p for p in home}
            cur = st.session_state.get("handle")
            if cur not in handles:
                counts = {r["handle"]: r["n"] for r in ins["metrics"].get("ratings", []) if r["brand"] == home_brand()}
                cur = max(handles, key=lambda h: counts.get(h, 0)) if handles else None
            if handles:
                h = st.selectbox("Dot & Key product", handles, index=handles.index(cur),
                                 format_func=lambda h: f"{friendly_name(by_h[h]['title'], 40)} · {inr(by_h[h]['price'])}",
                                 help="Every product-scoped page (deep-dive, audit, studio) follows this selection.")
                st.session_state["handle"] = h
        st.radio("Data mode", ["Demo", "Live"], horizontal=True, key="mode",
                 help="Demo replays saved catalogue snapshots and review files — no keys, seconds. "
                      "Live re-scrapes 11 stores and review feeds, then re-runs every layer.")
        prov = llm.provider()
        usd = costs.total_usd()
        lines = [f'LLM · <b>{esc(prov)}</b> {esc(llm.model_name()) if prov != "none" else "(lexicon + templates)"}']
        if ins:
            lines.append(f'Last run {esc(ins.get("generated_at", ""))} · {ins.get("elapsed_s", 0):.0f} s')
        lines.append(f'Spend <span class="num">₹{usd * costs.INR_PER_USD:,.0f} (${usd:.2f})</span>')
        st.markdown('<div class="meta" style="border-top:1px solid var(--rule);padding-top:8px;margin-top:4px">'
                    + "<br/>".join(lines) + "</div>", unsafe_allow_html=True)
    return ins


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
        st.page_link(PAGES[page], label=f"{cta}  →")


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
    with st.sidebar:
        v = st.text_input("Demo passcode", type="password", help="Needed to generate new content on the hosted demo.")
        if v and v == code:
            st.session_state["unlocked"] = True
            st.rerun()
        elif v:
            st.caption("Wrong passcode.")
