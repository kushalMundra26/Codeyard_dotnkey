from collections import Counter
from pathlib import Path

import streamlit as st

from app import ui
from core import pipeline
from core.config import OUTPUTS
from core.providers import sarvam

ui.setup("Campaign packs", "Approve", step="approve")
camps = pipeline.list_campaigns()
if not camps:
    ui.empty_state("No campaigns yet",
                   "Generate one in the Creative studio — each campaign becomes a pack here with its ads, copy, scripts, "
                   "videos and a ZIP for hand-off.", "studio", "Open Creative studio")
    st.stop()

cnt = Counter((c["status"] or "draft") for c in camps)
st.markdown(f'<div class="lead" style="max-width:80ch"><b>{len(camps)}</b> campaign{"s" if len(camps) != 1 else ""} — '
            f'<b>{cnt.get("approved", 0)}</b> approved, <b>{cnt.get("regional_ready", 0)}</b> with regional versions, '
            f'<b>{cnt.get("draft", 0)}</b> still in draft.</div>', unsafe_allow_html=True)

STATUS_KIND = {"approved": "ok", "regional_ready": "blue", "rejected": "block", "draft": "warn"}
flt = st.segmented_control("Show", ["All", "Draft", "Regional ready", "Approved", "Rejected"], default="All",
                           label_visibility="collapsed")
key = {"Draft": "draft", "Regional ready": "regional_ready", "Approved": "approved", "Rejected": "rejected"}.get(flt or "All")
shown = [c for c in camps if key is None or (c["status"] or "draft") == key]
if not shown:
    st.markdown('<div class="meta">No campaigns with this status.</div>', unsafe_allow_html=True)

for c in shown:
    full = pipeline.load_campaign(c["id"])
    if not full:
        continue
    st.markdown('<div class="sect" style="margin-top:10px;padding-top:12px"></div>', unsafe_allow_html=True)
    a, b, cc = st.columns([0.36, 0.42, 0.22], gap="medium", vertical_alignment="top")
    imgs = [x["path"] for x in full["ads"]["assets"] if x["size"] == "square"][:3]
    imgs += [x["path"] for r in full.get("regional", {}).values() for x in r["ads"] if x["size"] == "square"][:2]
    thumbs = "".join(f'<img src="{ui.img_src(i)}" style="width:72px;height:72px;object-fit:cover;border:1px solid var(--rule);'
                     f'border-radius:4px;margin:0 6px 6px 0"/>' for i in imgs if ui.img_src(i))
    a.markdown(f'<div style="display:flex;flex-wrap:wrap">{thumbs or "<span class=meta>no ads rendered</span>"}</div>',
               unsafe_allow_html=True)
    st_ = c["status"] or "draft"
    vids = [v for v in full.get("videos", []) if v.get("path")]
    b.markdown(f'<div style="font-weight:700">{ui.esc(ui.friendly_name(c["title"], 70))}</div>'
               f'<div class="meta">{ui.esc(c["persona"])} · {ui.esc(c["created_at"])}</div>'
               f'<div style="margin-top:4px">{ui.tag(st_.replace("_", " "), STATUS_KIND.get(st_, ""))}'
               + "".join(ui.tag(sarvam.LANG_NAMES.get(l, l), "blue") for l in c["languages"]) +
               f'</div><div class="meta" style="margin-top:2px">“{ui.esc(full["brief"]["key_message"])}”</div>'
               f'<div class="meta num">{len(full["ads"]["assets"])} ads · {len(vids)} video · '
               f'{sum(1 for v in full["ads"]["variants"] if v["claims"]["verdict"] == "block")} variant(s) blocked</div>',
               unsafe_allow_html=True)
    with cc:
        z = next(iter(sorted((OUTPUTS / c["id"]).glob("campaign_pack_*.zip"))), None)
        if z:
            st.download_button("Download ZIP", z.read_bytes(), file_name=z.name, key=f"z_{c['id']}", width="stretch")
        if st_ != "approved":
            if st.button("Mark approved", key=f"ap_{c['id']}", type="primary", width="stretch",
                         help="Manual approval (use when the reviewer signed off outside Telegram)."):
                full["status"] = "approved"
                pipeline.save_campaign(full)
                st.rerun()
        else:
            if st.button("Reopen as draft", key=f"re_{c['id']}", width="stretch"):
                full["status"] = "draft"
                pipeline.save_campaign(full)
                st.rerun()
        if st.button("Open in studio", key=f"op_{c['id']}", type="tertiary"):
            st.session_state["handle"] = full["product"]["handle"]
            st.session_state["campaign_id"] = c["id"]
            st.switch_page(ui.PAGES["studio"])
    if vids:
        with st.expander("Videos"):
            vc = st.columns(min(3, len(vids)))
            for col, v in zip(vc, vids[:3]):
                if Path(v["path"]).exists():
                    col.video(v["path"])
