from pathlib import Path

import requests
import streamlit as st

from app import ui
from core import pipeline
from core.config import OUTPUTS, env
from core.creative.compose import SIZE_LABELS
from core.providers import sarvam, telegram

ins = ui.setup("Review & approve", "Create & approve · step 9", step="approve",
               intro="One last look before hand-off. Download the pack, or send it to the approver on Telegram.")
ui.gate("render_done", "Render an ad first", "Pick a concept and style in the Ad studio and render it.", "ads", "Go to Ad studio")
camp = ui.active_campaign()
p = ui.current_product(ins)
cdir = OUTPUTS / camp["id"]

# ---------- summary ----------
rk = st.session_state.get("rendered", "")
assets = st.session_state.get("render_assets") or []
sq = next((a for a in assets if a["size"] == "square" and Path(a["path"]).exists()), None)
v = camp["ads"]["variants"][int(rk.split(":")[0])] if rk else camp["ads"]["variants"][0]
vids = [x for x in camp.get("videos", []) if x.get("path") and Path(x["path"]).exists()]
langs = list(camp.get("regional", {}).keys())
n_flag = sum(1 for c in camp.get("ecom_claims", []) if c["verdict"] != "ok")

a, b = st.columns([0.4, 0.6], gap="large")
if sq:
    a.image(sq["path"], caption=SIZE_LABELS.get("square"), width="stretch")
rows = [("Product", ui.friendly_name(p["title"], 60)), ("Persona", camp["persona"]["name"]),
        ("Key message", f'“{camp["brief"]["key_message"]}”'), ("Chosen ad", v["headline"]),
        ("Style", pipeline.STYLES.get(rk.split(":")[-1], {}).get("name", "—") if rk else "—"),
        ("Sizes", f"{len(assets)} (feed, story, A+)"), ("Video", f"{len(vids)} storyboard MP4" + ("s" if len(vids) != 1 else "")),
        ("Languages", ", ".join(["English"] + [sarvam.LANG_NAMES.get(l, l) for l in langs])),
        ("Claims", f"ad {v['claims']['verdict']} · {n_flag} listing line(s) flagged")]
b.markdown('<div class="facts" style="border-left:none;padding-left:0">' + "".join(
    f'<div class="r"><span class="k">{ui.esc(k)}</span><span class="v">{ui.esc(val)}</span></div>' for k, val in rows) + "</div>",
    unsafe_allow_html=True)

# ---------- actions ----------
st.markdown('<div class="next-row"></div>', unsafe_allow_html=True)
approved = st.session_state.get("approved")
status = "approved" if approved else ("sent — awaiting reply" if st.session_state.get(f"sent_{camp['id']}") else "draft")
st.markdown(f'<div class="meta" style="margin-bottom:10px">Status '
            f'{ui.status_tag({"approved": "ok"}.get(status, "warn"), status)}</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3, gap="medium")
zipf = next(iter(sorted(cdir.glob("campaign_pack_*.zip"))), None)
if zipf:
    c1.download_button("Download pack (ZIP)", zipf.read_bytes(), file_name=zipf.name, width="stretch")
else:
    c1.button("No pack saved", disabled=True, width="stretch")

if c2.button("Send for approval", width="stretch", disabled=not ui.is_live() or not ui.can_act(),
             help="Telegram message with Approve / Reject buttons" if ui.is_live() else "Live mode only"):
    hook = env("N8N_APPROVAL_WEBHOOK_URL")
    try:
        if hook:
            requests.post(hook, json={"campaign_id": camp["id"], "product": p["handle"], "persona": camp["persona"]["id"],
                                      "category": ins["category"], "languages": langs}, timeout=15)
            st.session_state[f"sent_{camp['id']}"] = True
            st.success("Sent — watch Telegram for the approval message.")
        elif telegram.available():
            img = sq["path"] if sq else next((x["path"] for x in camp["ads"]["assets"] if x["size"] == "square"), None)
            base, tok = env("PUBLIC_BASE_URL", "http://localhost:8000"), env("API_TOKEN")
            btn = [("Approve", f"{base}/api/campaign/{camp['id']}/decision?d=approve&token={tok}"),
                   ("Reject", f"{base}/api/campaign/{camp['id']}/decision?d=reject&token={tok}")]
            telegram.send_file("sendPhoto", img, f"<b>Approval needed</b>\n{p['title']}\n{camp['brief']['key_message']}", btn)
            st.session_state[f"sent_{camp['id']}"] = True
            st.success("Sent to Telegram.")
        else:
            st.warning("No approval channel configured (n8n webhook or Telegram bot) — see Settings & data.")
    except Exception as ex:
        st.error(f"Send failed: {ex}")

if not approved:
    if c3.button("Approve", type="primary", width="stretch"):
        st.session_state["approved"] = True
        if ui.is_live():
            camp["status"] = "approved"
            pipeline.save_campaign(camp)
        st.rerun()
else:
    if c3.button("Reopen as draft", width="stretch"):
        st.session_state.pop("approved", None)
        st.rerun()
    st.markdown('<div class="reason"><div class="h">Approved</div><div class="l"><span class="tick">✓</span>'
                'The campaign is signed off. The pack above has every asset, the copy and the evidence behind it.</div></div>',
                unsafe_allow_html=True)
ui.caption("In Demo, approval is kept for this session only; in Live it is saved to the campaign.")
