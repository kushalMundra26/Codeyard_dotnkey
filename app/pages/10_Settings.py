import os

import streamlit as st

from app import ui
from core import admin, costs, marketplace, pipeline
from core.collect import catalog
from core.config import brand_list, brand_name, env

ui.setup("Settings & data", "Setup", badge=False)
hosted = bool(os.environ.get("STREAMLIT_SHARING_MODE") or os.environ.get("HOSTNAME", "").startswith("streamlit"))

# ---------------- connections ----------------
ui.section("Connections", "keys live in .env locally, or in Streamlit Secrets when hosted", first=True)
ks = admin.key_status()
n_set = sum(k["set"] for k in ks)
ui.takeaway(f"<b>{n_set} of {len(ks)}</b> integrations configured · AI engine: <b>{ui.esc(__import__('core.llm', fromlist=['x']).provider())}</b>")
rows = "".join(f'<div class="row"><span class="k">{ui.esc(k["label"])}</span>{ui.status_tag("ok" if k["set"] else "warn", "set" if k["set"] else "missing")}'
               f'<span class="meta">{ui.esc(k["purpose"])}</span></div>' for k in ks)
st.markdown(rows, unsafe_allow_html=True)
c1, c2 = st.columns([1, 3])
if c1.button("Test connections", disabled=not ui.can_act()):
    with st.spinner("Testing…"):
        st.session_state["conn"] = admin.test_connections()
if st.session_state.get("conn"):
    r = st.session_state["conn"]
    c2.markdown(" ".join(ui.status_tag("ok" if (v is True or v == "ok" or (k == "llm" and v != "none")) else "warn", f"{k}: {v}")
                         for k, v in r.items()), unsafe_allow_html=True)

with st.expander("Add or change keys", expanded=n_set < 3):
    if hosted:
        st.info("On the hosted demo, set keys in the app's **Settings → Secrets** on share.streamlit.io; values typed here last only until the app restarts.")
    with st.form("keys"):
        vals = {k["key"]: st.text_input(k["label"], type="password", placeholder="set — leave blank to keep" if k["set"] else "", help=k["purpose"])
                for k in ks}
        if st.form_submit_button("Save keys", type="primary", disabled=not ui.can_act()):
            changed = admin.save_keys(vals)
            st.success(f"Saved: {', '.join(changed) or 'nothing changed'}")
            st.rerun()

# ---------------- data ----------------
ui.section("Data", "where everything comes from")
snap = {b: catalog.snapshot_dates(b) for b in brand_list()}
real = [b for b, d in snap.items() if any("seed" not in x for x in d)]
seed = [b for b, d in snap.items() if d and all("seed" in x for x in d)]
ui.takeaway(f"Catalogues: <b>{len(real)}</b> stores from a live Shopify snapshot, <b>{len(seed)}</b> from the seed catalogue "
            f"(review-widget feeds + marketplace prices) · marketplace listings: <b>{len(marketplace.load())}</b>")
st.markdown("".join(f'<div class="row"><span class="k">{ui.esc(brand_name(b))}</span>'
                    f'{ui.status_tag("ok", "live snapshot") if b in real else ui.status_tag("warn", "seed") if b in seed else ui.status_tag("block", "none")}'
                    f'<span class="meta">{", ".join(d for d in snap[b] if "seed" not in d) or "—"}</span></div>' for b in brand_list()),
            unsafe_allow_html=True)
log = st.empty()
d1, d2, d3, d4 = st.columns(4)
if d1.button("Fetch catalogues", help="One polite request per store. Stores that rate-limit us are skipped, not retried.",
             disabled=not ui.can_act()):
    lines = []
    admin.fetch_catalogues(log=lambda s: (lines.append(s), log.code("\n".join(lines))))
if d2.button("Build seed catalogue", help="From verified product ids + review-widget metadata + marketplace prices.",
             disabled=not ui.can_act()):
    lines = []
    admin.seed_catalogue(log=lambda s: (lines.append(str(s)), log.code("\n".join(lines))))
if d3.button("Refresh reviews", help="Re-download reviews for every category product (slow, polite).", disabled=not ui.can_act()):
    with st.status("Refreshing reviews and re-running analysis…") as s:
        pipeline.run_analysis(st.session_state.get("cat", "sunscreen"), refresh_reviews=True,
                              progress=lambda a, b="", c=None: s.update(label=f"{a} — {b}"))
        s.update(state="complete", label="Done")
    st.cache_data.clear()
if d4.button("Re-run analysis", type="primary", disabled=not ui.can_act()):
    with st.status("Running…") as s:
        pipeline.run_analysis(st.session_state.get("cat", "sunscreen"), progress=lambda a, b="", c=None: s.update(label=f"{a} — {b}"))
        s.update(state="complete", label="Done")
    st.cache_data.clear()

with st.expander("Import a marketplace snapshot (Amazon / Nykaa / Flipkart)"):
    st.markdown('<div class="meta">Paste the JSON array produced by the Gemini marketplace prompt in the README. Rows without a URL are dropped; '
                'quotes must be verbatim. Shown as “verify links” data and never mixed into review statistics.</div>', unsafe_allow_html=True)
    up = st.file_uploader("JSON file", type=["json"])
    txt = st.text_area("…or paste JSON", height=140)
    if st.button("Import", disabled=not ui.can_act() or not (up or txt.strip())):
        try:
            n = admin.import_marketplace_json(up.read().decode() if up else txt)
            st.success(f"Imported — {n} listings in the latest snapshot.")
        except Exception as e:
            st.error(f"Could not import: {e}")

# ---------------- budget ----------------
ui.section("Spend guardrails")
cap = float(env("HIGGSFIELD_MAX_USD", "5"))
ui.takeaway(f"Spent <b>${costs.total_usd():.2f}</b> in total · Higgsfield <b>${costs.spent('higgsfield'):.2f}</b> of a <b>${cap:.2f}</b> cap · "
            f"dry-run {'<b>on</b>' if costs.is_dry() else 'off'}")
dr = st.toggle("Dry run (skip every paid call)", value=costs.is_dry(), disabled=not ui.can_act())
if dr != costs.is_dry():
    admin.save_keys({"DRY_RUN": "1" if dr else "0"})
    st.rerun()
