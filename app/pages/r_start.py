import streamlit as st

from app import ui
from core import pipeline
from core.config import brand_name, home_brand

ins = ui.setup("What should we study?", "Research · step 1", step="start",
               intro="Pick a category and a Dot &amp; Key product. SignalStudio reads every rival catalogue and thousands of "
                     "real customer reviews, then shows you where the product wins and where it is exposed.")

CATS = [("sunscreen", "Sunscreen", "11 brands · catalogues + reviews", True),
        ("lip_balm", "Lip balm", "Coming soon", False)]
FLOW_KEYS = [k for k, *_ in ui.FLOW]


def reset_flow():
    for k in FLOW_KEYS:
        st.session_state.pop(k, None)
    st.session_state.pop("campaign_id", None)


# ---------- category ----------
st.markdown("### 1. Category")
cols = st.columns(len(CATS) + 1, gap="medium")
for col, (cid, name, sub, enabled) in zip(cols, CATS):
    sel = enabled and st.session_state.get("cat") == cid
    key = ("tilesel_" if sel else "tile_" if enabled else "tileoff_") + f"cat_{cid}"
    with col.container(border=True, key=key):
        st.markdown(f'<div class="cat-ico">{ui.esc(name)}</div><div class="tile-s">{ui.esc(sub)}</div>', unsafe_allow_html=True)
        if enabled:
            if st.button("Selected" if sel else "Select", key=f"pick_cat_{cid}", disabled=sel, width="stretch"):
                st.session_state["cat"] = cid
                reset_flow()
                st.rerun()
        else:
            st.button("Not available yet", key=f"pick_cat_{cid}", disabled=True, width="stretch")

if not ins:
    ui.empty_state("No saved analysis for this category",
                   "Switch to Live in Settings &amp; data to scrape the catalogues and reviews for the first time.",
                   "settings", "Open Settings & data")
    st.stop()

# ---------- product ----------
st.markdown("### 2. Dot &amp; Key product")
home = ui.home_products(ins)
counts = {r["handle"]: r["n"] for r in ins["metrics"].get("ratings", []) if r["brand"] == home_brand()}
analysed = [p for p in home if counts.get(p["handle"], 0) > 0]
cur = st.session_state.get("handle")
if cur not in {p["handle"] for p in analysed} and analysed:
    cur = analysed[0]["handle"]
    st.session_state["handle"] = cur
cols = st.columns(3, gap="medium")
for i, p in enumerate(home[:6]):
    ok = p in analysed
    sel = ok and p["handle"] == cur
    key = ("tilesel_" if sel else "tile_" if ok else "tileoff_") + f"prod_{i}"
    with cols[i % 3].container(border=True, key=key):
        src = ui.img_src(p.get("image"), 400)
        if src:
            st.markdown(f'<img class="tile-img" src="{src}" alt=""/>', unsafe_allow_html=True)
        st.markdown(f'<div class="tile-t">{ui.esc(ui.friendly_name(p["title"], 70))}</div>'
                    f'<div class="tile-s">{ui.inr(p.get("price"))}'
                    f'{" · " + format(counts.get(p["handle"], 0), ",") + " reviews collected" if ok else " · not analysed yet"}</div>',
                    unsafe_allow_html=True)
        if ok:
            if st.button("Selected" if sel else "Select", key=f"pick_p_{i}", disabled=sel, width="stretch"):
                st.session_state["handle"] = p["handle"]
                reset_flow()
                st.rerun()
ui.caption(f"{len(analysed)} of {len(home)} {brand_name(home_brand())} {ui.esc(ins['category'].replace('_', ' '))} "
           "products have collected reviews today; others appear here once they are analysed.")

handle = ui.selected_handle(ins)

# ---------- run ----------
st.markdown('<div class="next-row"></div>', unsafe_allow_html=True)
done = st.session_state.get("research_done")
c1, c2 = st.columns([0.62, 0.38], vertical_alignment="center")
c1.markdown('<div class="meta">' + ("<b>Live</b>: re-scrapes 11 stores and review feeds, then re-runs every layer (minutes)."
                                    if ui.is_live() else "<b>Demo</b>: replays the saved analysis — no network, no keys.")
            + "</div>", unsafe_allow_html=True)
run = c2.button("Analyse again" if done else "Analyse the market", type="primary", width="stretch",
                disabled=ui.is_live() and not ui.can_act())

if run:
    reset_flow()
    if ui.is_live():
        with st.status("Running live analysis", expanded=True) as status:
            try:
                pipeline.run_analysis(ins["category"], live=True,
                                      progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                status.update(label="Analysis complete", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Analysis failed", state="error")
                st.error(f"{e}. Switch to Demo in Settings & data to use the saved analysis.")
                st.stop()
        st.cache_data.clear()
        ins = ui.insights()
    else:
        ui.reasoning("Reading the market", ui.research_lines(ins, handle), seconds=7.5)
    st.session_state["research_done"] = True
    st.session_state["handle"] = handle
    st.rerun()

if st.session_state.get("research_done"):
    lines = ui.research_lines(ins, handle)
    st.markdown('<div class="reason"><div class="h">What we found</div>' +
                "".join(f'<div class="l"><span class="tick">✓</span>{x}</div>' for x in lines) + "</div>",
                unsafe_allow_html=True)
    ui.continue_to("market", "See the market", "Complaints, rivals, price ladder and marketplace listings.")
