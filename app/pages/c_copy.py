from pathlib import Path

import streamlit as st

from app import ui
from core import pipeline
from core.config import brand_inputs
from core.creative import claims as claims_mod
from core.creative.compose import SIZES
from core.providers import sarvam

ins = ui.setup("Copy & video", "Create & approve · step 8", step="ads",
               intro="Everything else the launch needs, written from the same brief: listing copy, scripts, a storyboard video "
                     "and regional versions — each line run through the claims checker.")
ui.gate("render_done", "Render an ad first", "Pick a concept and style in the Ad studio and render it.", "ads", "Go to Ad studio")
camp = ui.active_campaign()
p = ui.current_product(ins)
ctx = ui.context(ins, p["handle"])
bi = brand_inputs()
tabs = st.tabs(["E-commerce copy", "Scripts & video", "Claims check", "Hindi & Bengali"])
with tabs[0]:
    e = camp["ecom"]
    bad = {c["text"]: c for c in camp["ecom_claims"] if c["verdict"] != "ok"}

    def flag(text):
        c = bad.get(text)
        return (" " + ui.verdict_tag(c["verdict"])) if c else ""
    st.markdown(f'<div class="meta">{ui.engine_badge(camp["engines"].get("ecom"))} · {len(bad)} line(s) flagged by the claims checker</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="eyebrow" style="margin-top:8px">Amazon title · {len(e["amazon_title"])} chars</div>'
                f'<div style="font-weight:600">{ui.esc(e["amazon_title"])}{flag(e["amazon_title"])}</div>', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow" style="margin-top:10px">Bullets</div>' +
                "".join(f'<div class="small" style="padding:3px 0;border-bottom:1px solid var(--rule)">• {ui.esc(x)}{flag(x)}</div>'
                        for x in e["bullets"]), unsafe_allow_html=True)
    st.markdown(f'<div class="eyebrow" style="margin-top:10px">Product description</div>'
                f'<div class="small" style="line-height:1.55">{ui.esc(e["product_description"])}{flag(e["product_description"])}</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="eyebrow" style="margin-top:10px">A+ modules</div>', unsafe_allow_html=True)
    for m in e["aplus"]:
        st.markdown(f'<div class="swot o"><div style="font-weight:700">{ui.esc(m["title"])}</div><div class="small">{ui.esc(m["body"])}</div>'
                    f'<div class="meta">Image: {ui.esc(m["image_idea"])} · {ui.esc(" ".join(m["evidence"]))}</div></div>',
                    unsafe_allow_html=True)
    st.markdown('<div class="eyebrow" style="margin-top:10px">SEO keywords · customers\' own words</div>' +
                "".join(ui.tag(k) for k in e["seo_keywords"]), unsafe_allow_html=True)
    for c in bad.values():
        st.markdown(f'<div class="meta">{ui.verdict_tag(c["verdict"])} {ui.esc(c["text"][:100])} — '
                    + "; ".join(ui.esc(r["reason"]) for r in c["reasons"]) + "</div>", unsafe_allow_html=True)
with tabs[1]:
    vids = [v for v in camp.get("videos", [])]
    for v in vids:
        if v.get("path") and Path(v["path"]).exists():
            vc1, vc2 = st.columns([0.45, 0.55], gap="medium")
            vc1.video(v["path"])
            vc2.markdown(f'<div class="meta">{v.get("duration", "?")} s · 720×1280 · voice-over: {ui.esc(v.get("voiceover", "none"))}<br/>'
                         f'frames: {ui.esc(", ".join(sorted(set(v.get("frame_engines", [])))))}</div>', unsafe_allow_html=True)
        elif v.get("error"):
            st.error(f"Video render failed: {v['error']}")
    if not vids:
        st.markdown('<div class="meta">No storyboard video — turn on “Storyboard MP4” and regenerate.</div>', unsafe_allow_html=True)
    for k in ("script15", "script30"):
        s = camp[k]
        st.markdown(f'<div class="sect" style="margin-top:10px;padding-top:8px"><h3>{s["duration_s"]} s · {ui.esc(s["title"])}</h3>'
                    f'<span class="meta">{ui.engine_badge(camp["engines"].get(k))}</span></div>'
                    f'<div class="meta">Hook: <i>{ui.esc(s["hook"])}</i> · Concept: {ui.esc(s["video_concept"])} · Music: {ui.esc(s["music_mood"])}</div>',
                    unsafe_allow_html=True)
        fr = ui.df(s["frames"])
        fr["time"] = fr["t_start"].map(lambda x: f"{x:g}") + "–" + fr["t_end"].map(lambda x: f"{x:g}s")
        st.dataframe(fr[["time", "visual", "on_screen_text", "voiceover"]], hide_index=True, width="stretch",
                     column_config={"time": st.column_config.TextColumn("t", width="small"),
                                    "on_screen_text": "On screen", "voiceover": "Voice-over", "visual": "Visual"})
with tabs[2]:
    st.markdown('<div class="small">The checker blocks medical/absolute claims, banned words, wrong SPF/PA, competitor names, '
                'and any claim where <b>our own reviews disagree</b>. Probes run against this product:</div>', unsafe_allow_html=True)
    for i, c in enumerate(camp["claims_probe"]):
        c1, c2 = st.columns([0.82, 0.18], vertical_alignment="top")
        c1.markdown(f'<div style="padding:4px 0;border-bottom:1px solid var(--rule)">{ui.verdict_tag(c["verdict"])} <b>{ui.esc(c["text"])}</b>'
                    + "".join(f'<div class="meta">{ui.esc(r["reason"])}</div>' for r in c["reasons"]) + "</div>",
                    unsafe_allow_html=True)
        with c2:
            if c.get("evidence"):
                ui.evidence_count_button(len(c["evidence"]), c["text"], c["evidence"], f"probe_{i}")
    test = st.text_input("Test your own claim", "Zero white cast, all day")
    if test:
        r = claims_mod.check(test, p.get("spec", {}), pipeline.own_topic_net(ctx, ins))
        st.markdown(f'{ui.verdict_tag(r["verdict"])} ' + (" ".join(ui.esc(x["reason"]) for x in r["reasons"]) or
                                                          '<span class="meta">No issues found.</span>'), unsafe_allow_html=True)
with tabs[3]:
    have = camp.get("regional", {})
    if ui.is_live() and not sarvam.available():
        ui.empty_state("Regional versions need a Sarvam key",
                       "Add <code>SARVAM_API_KEY</code> to .env to make Hindi / Bengali versions (Mayura translate + Bulbul v3 "
                       "voice). Ads are re-rendered with native-script fonts and the storyboard gets a regional voice-over.")
    if ui.is_live():
        rl = st.multiselect("Languages", ["hi", "bn", "ta", "mr"], default=bi["languages"],
                            format_func=lambda l: sarvam.LANG_NAMES[l])
        if st.button("Make regional versions", disabled=not sarvam.available() or not rl or not ui.can_act(), type="primary"):
            with st.status("Localising", expanded=True) as status:
                pipeline.regional(camp["id"], rl, progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                status.update(label="Regional versions ready", state="complete")
            st.rerun()
    elif not have:
        st.markdown('<div class="meta">No saved regional versions for this campaign. Switch to Live to make them.</div>',
                    unsafe_allow_html=True)
    for lang, r in have.items():
        st.markdown(f'<div class="sect" style="margin-top:8px;padding-top:8px"><h3>{ui.esc(sarvam.LANG_NAMES.get(lang, lang))}</h3>'
                    f'<span class="meta">{ui.esc(r["ad_text"]["headline"])}</span></div>', unsafe_allow_html=True)
        ads = sorted(r["ads"], key=lambda a: 0 if a["size"] == "story" else 1)
        cols = st.columns([SIZES[a["size"]][0] / SIZES[a["size"]][1] for a in ads] + ([0.5625] if r.get("video") and r["video"].get("path") else []))
        for col, a in zip(cols, ads):
            if Path(a["path"]).exists():
                col.image(a["path"], caption=f"{a['size']} · {lang}", width="stretch")
        if r.get("video") and r["video"].get("path") and Path(r["video"]["path"]).exists():
            cols[-1].video(r["video"]["path"])

ui.continue_to("approve", "Review & approve", "Download the campaign pack and send it for sign-off.")
