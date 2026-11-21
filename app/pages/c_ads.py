from pathlib import Path

import streamlit as st

from app import ui
from core import pipeline
from core.creative.compose import SIZE_LABELS, SIZES

ins = ui.setup("Ad studio", "Create & approve · step 7", step="ads",
               intro="Choose one concept and one visual style. We render that ad in all three sizes: feed, story and Amazon A+.")
ui.gate("brief_done", "Write the brief first",
        "Ad concepts come from the brief. Pick a persona and write the brief.", "brief", "Go to Brief")
camp = ui.active_campaign()
if not camp:
    ui.gate("__never__", "Write the brief first", "The saved brief could not be loaded.", "brief", "Go to Brief")
cid = camp["id"]
concepts = pipeline.ad_concepts(camp)
STY = pipeline.STYLES
ok_concepts = [c for c in concepts if c["verdict"] != "block"]
st.session_state.setdefault("concept", ok_concepts[0]["index"] if ok_concepts else 0)
st.session_state.setdefault("style", next(iter(STY)))


def saved_render(vi: int, style: str) -> list[dict] | None:
    a = (camp.get("renders") or {}).get(f"{vi}:{style}")
    return a if a and all(Path(x["path"]).exists() for x in a) else None


def fallback_render(vi: int) -> list[dict] | None:
    """Demo fallback: the campaign's original saved render of this concept (its own scene, no style applied)."""
    ok_idx = [c["index"] for c in concepts if c["verdict"] != "block"] or [c["index"] for c in concepts]
    if vi not in ok_idx:
        return None
    a = [x for x in camp["ads"].get("assets", []) if x.get("variant") == ok_idx.index(vi) and Path(x["path"]).exists()]
    return a if len(a) >= 3 else None


# ---------- concepts ----------
st.markdown("### 1. Concept")
cols = st.columns(len(concepts), gap="medium")
for col, c in zip(cols, concepts):
    vi = c["index"]
    blocked = c["verdict"] == "block"
    sel = not blocked and st.session_state["concept"] == vi
    key = ("tilesel_" if sel else "tileoff_" if blocked else "tile_") + f"concept_{vi}"
    with col.container(border=True, key=key):
        reasons = "".join(f'<div class="tile-s">✕ {ui.esc(r["reason"])}</div>' for r in c["reasons"]) if blocked else ""
        st.markdown(f'<div class="eyebrow">Concept {vi + 1} {ui.verdict_tag(c["verdict"])}</div>'
                    f'<div class="tile-big" style="margin-top:6px">{ui.esc(c["headline"])}</div>'
                    f'<div class="tile-s" style="margin-top:4px">{ui.esc(c["subline"])} · <b>{ui.esc(c["cta"])}</b></div>'
                    f'<div class="tile-s" style="margin-top:8px;border-top:1px solid var(--rule);padding-top:6px">'
                    f'<b style="color:var(--ink)">Why</b> · {ui.esc(c["why"])}</div>{reasons}', unsafe_allow_html=True)
        rids, labs, notes = ui.resolve_evidence(ins, c["evidence"])
        if rids:
            ui.evidence_count_button(len(rids), c["headline"], rids, f"cev_{vi}", labels=labs, label=f"evidence · n = {len(rids)}")
        if blocked:
            st.button("Locked by claims checker", key=f"pick_c_{vi}", disabled=True, width="stretch")
        elif st.button("Selected" if sel else "Select", key=f"pick_c_{vi}", disabled=sel, width="stretch"):
            st.session_state["concept"] = vi
            st.rerun()

# ---------- styles ----------
st.markdown("### 2. Style")
vi = st.session_state["concept"]
cols = st.columns(len(STY), gap="medium")
for col, (sid, s) in zip(cols, STY.items()):
    sel = st.session_state["style"] == sid
    with col.container(border=True, key=("tilesel_" if sel else "tile_") + f"style_{sid}"):
        pre = saved_render(vi, sid)
        sq = next((a["path"] for a in pre or [] if a["size"] == "square"), None)
        src = ui.img_src(sq) if sq else None
        if src:
            st.markdown(f'<img class="tile-img" style="object-fit:cover" src="{src}" alt=""/>', unsafe_allow_html=True)
        st.markdown(f'<div class="tile-t">{ui.esc(s["name"])}</div><div class="tile-s">{ui.esc(s["blurb"])}</div>'
                    + ("" if pre or ui.is_live() else '<div class="tile-s" style="margin-top:4px">Not pre-rendered for this concept</div>'),
                    unsafe_allow_html=True)
        if st.button("Selected" if sel else "Select", key=f"pick_s_{sid}", disabled=sel, width="stretch"):
            st.session_state["style"] = sid
            st.rerun()

style = st.session_state["style"]
chosen = next(c for c in concepts if c["index"] == vi)

st.markdown('<div class="next-row"></div>', unsafe_allow_html=True)
c1, c2 = st.columns([0.62, 0.38], vertical_alignment="center")
c1.markdown(f'<div class="meta">Concept {vi + 1} · <b>{ui.esc(STY[style]["name"])}</b> · '
            + ("<b>Live</b>: draws a new background (free image chain), then composes the real packshot and text in code."
               if ui.is_live() else "<b>Demo</b>: shows the saved render — no image calls.") + "</div>", unsafe_allow_html=True)
go = c2.button("Render this ad", type="primary", width="stretch",
               disabled=chosen["verdict"] == "block" or (ui.is_live() and not ui.can_act()))

if go:
    lines = [f"Concept {vi + 1}: <b>“{ui.esc(chosen['headline'])}”</b> — {ui.esc(chosen['why'][:140])}",
             f"Claims checker on the headline and subline: <b>{ui.esc(chosen['verdict'])}</b>",
             f"Background scene in the <b>{ui.esc(STY[style]['name'])}</b> style — scene only, no product, no text",
             "Placed the real packshot cut-out from the store listing",
             "Set headline, subline and CTA in code with the Dot &amp; Key type scale",
             "Exported Feed 1:1 (1080×1080), Story 9:16 (1080×1920) and Amazon A+ (970×600)"]
    if ui.is_live():
        with st.status("Rendering", expanded=True) as status:
            try:
                pipeline.render_choice(cid, vi, style, progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                status.update(label="Rendered", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Render failed", state="error")
                st.error(str(e))
                st.stop()
        camp = pipeline.load_campaign(cid)
    else:
        got = saved_render(vi, style)
        note = ""
        if not got:
            got = fallback_render(vi)
            note = (f"“{STY[style]['name']}” is not pre-rendered for this concept in Demo, so this is the concept's saved "
                    "render with its original scene. Switch to Live to render the chosen style.")
            if not got:
                st.warning("This concept × style is not pre-rendered in Demo. Pick a style with a preview, or switch to "
                           "Live in Settings & data.")
                st.stop()
            lines[2] = "Used the saved background scene for this concept (style not pre-rendered in Demo)"
        ui.reasoning("Rendering the ad", lines, seconds=6)
        st.session_state["render_assets"] = got
        st.session_state["render_note"] = note
    if ui.is_live():
        st.session_state["render_assets"] = (camp.get("renders") or {}).get(f"{vi}:{style}")
        st.session_state["render_note"] = ""
    st.session_state["rendered"] = f"{vi}:{style}"
    st.session_state["render_done"] = True
    st.rerun()

rk = st.session_state.get("rendered") if st.session_state.get("render_done") else None
assets = st.session_state.get("render_assets") if rk else None
if not assets:
    st.stop()

rvi, rst = rk.split(":")
rc = next(c for c in concepts if c["index"] == int(rvi))
ui.section("Your ad in three sizes", f"Concept {int(rvi) + 1} · {ui.esc(STY.get(rst, {}).get('name', rst))}")
st.markdown(f'<div class="adcopy">{ui.esc(rc["headline"])}</div><div class="adsub">{ui.esc(rc["subline"])}</div>',
            unsafe_allow_html=True)
if st.session_state.get("render_note"):
    ui.caption(ui.esc(st.session_state["render_note"]))
ORDER = ["square", "story", "aplus"]
imgs = sorted([a for a in assets if Path(a["path"]).exists()], key=lambda a: ORDER.index(a["size"]) if a["size"] in ORDER else 9)
cols = st.columns([SIZES[a["size"]][0] / SIZES[a["size"]][1] for a in imgs], gap="medium")
for col, a in zip(cols, imgs):
    col.image(a["path"], caption=a.get("label") or SIZE_LABELS.get(a["size"], a["size"]), width="stretch")

ui.continue_to("copy", "Copy & video", "Listing copy, A+ modules, scripts, the storyboard video and Hindi / Bengali versions.")
