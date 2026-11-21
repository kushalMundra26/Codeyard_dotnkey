import streamlit as st

from app import ui
from core import pipeline
from core.config import brand_inputs

ins = ui.setup("Creative brief", "Create & approve · step 6", step="brief",
               intro="Choose who the campaign speaks to. The brief is written only from the customer evidence you just saw — "
                     "every proof point links to the reviews it came from.")
ui.gate("insight_done", "Generate insights first",
        "The brief is written from the product insights. Generate them on Product deep-dive.", "product", "Go to Product deep-dive")
p = ui.current_product(ins)
ctx = ui.context(ins, p["handle"])
ui.product_header(p, ctx)
bi = brand_inputs()
personas = bi["personas"]
st.session_state.setdefault("persona_id", "college_commuter" if any(x["id"] == "college_commuter" for x in personas)
                            else personas[0]["id"])

st.markdown("### Who is it for?")
cols = st.columns(len(personas), gap="medium")
for i, (col, per) in enumerate(zip(cols, personas)):
    sel = per["id"] == st.session_state["persona_id"]
    has = ui.is_live() or ui.demo_campaign(p["handle"], per["id"]) is not None
    key = ("tilesel_" if sel else "tile_" if has else "tileoff_") + f"per_{i}"
    with col.container(border=True, key=key):
        name, _, role = per["name"].partition("—")
        desc = per.get("description") or per.get("summary") or per.get("bio") or ""
        st.markdown(f'<div class="tile-big">{ui.esc(name.strip())}</div><div class="tile-s">{ui.esc(role.strip())}</div>'
                    + (f'<div class="tile-s" style="margin-top:6px">{ui.esc(str(desc)[:160])}</div>' if desc else "")
                    + ("" if has else '<div class="tile-s" style="margin-top:6px">Not pre-generated in Demo — switch to Live</div>'),
                    unsafe_allow_html=True)
        if st.button("Selected" if sel else "Select", key=f"pick_per_{i}", disabled=sel or not has, width="stretch"):
            st.session_state["persona_id"] = per["id"]
            st.session_state.pop("brief_done", None)
            st.session_state.pop("render_done", None)
            st.rerun()

persona = next(x for x in personas if x["id"] == st.session_state["persona_id"])


def brief_lines(c: dict) -> list[str]:
    b = c["brief"]
    out = [f"Read the evidence for <b>{ui.esc(ui.friendly_name(p['title'], 50))}</b>: "
           f"<b>{len(ctx['own_topics'])}</b> topics, <b>{len(ctx['quotes'])}</b> quotes, <b>{len(ctx['rivals'])}</b> rivals",
           f"Framed it for <b>{ui.esc(persona['name'])}</b>"]
    out.append(f"Customer insight: {ui.esc(b['insight'][:160])}")
    out.append(f"Picked <b>{len(b['proof_points'])}</b> proof points, each tied to review or metric ids")
    if b.get("avoid"):
        out.append(f"Listed <b>{len(b['avoid'])}</b> things never to say (e.g. “{ui.esc(b['avoid'][0])}”)")
    out.append(f"Key message: <b>“{ui.esc(b['key_message'])}”</b>")
    return out


st.markdown('<div class="next-row"></div>', unsafe_allow_html=True)
c1, c2 = st.columns([0.62, 0.38], vertical_alignment="center")
c1.markdown('<div class="meta">' + ("<b>Live</b>: writes the brief, three ad concepts, e-commerce copy and scripts (about a minute)."
                                    if ui.is_live() else "<b>Demo</b>: reveals the saved brief for this persona.") + "</div>",
            unsafe_allow_html=True)
go = c2.button("Rewrite the brief" if st.session_state.get("brief_done") else "Write the brief", type="primary",
               width="stretch", disabled=ui.is_live() and not ui.can_act())

if go:
    if ui.is_live():
        with st.status("Writing the brief", expanded=True) as status:
            try:
                camp = pipeline.generate_campaign(ins["category"], p["handle"], persona["id"], render_ads=False,
                                                  progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                status.update(label="Brief ready", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Failed", state="error")
                st.error(str(e))
                st.stop()
    else:
        camp = ui.demo_campaign(p["handle"], persona["id"])
        if not camp:
            st.warning("No saved brief for this persona in Demo. Switch to Live in Settings & data to write one.")
            st.stop()
        ui.reasoning("Writing the brief", brief_lines(camp), seconds=7)
    st.session_state["campaign_id"] = camp["id"]
    st.session_state["brief_done"] = True
    st.session_state.pop("render_done", None)
    st.rerun()

camp = ui.active_campaign() if st.session_state.get("brief_done") else None
if not camp:
    st.stop()

b = camp["brief"]
ui.section("The brief", f'{ui.esc(b["persona"])} · {ui.engine_badge(camp["engines"].get("brief"))}')
st.markdown(f'<div class="eyebrow">Key message</div><div style="font-family:Fraunces,Georgia,serif;font-size:26px;'
            f'font-weight:600;line-height:1.25;margin:4px 0 14px 0">“{ui.esc(b["key_message"])}”</div>'
            f'<div class="eyebrow">Customer insight</div><div style="font-size:15px;line-height:1.55;margin-bottom:14px;max-width:70ch">'
            f'{ui.esc(b["insight"])}</div><div class="eyebrow">Proof points · click n for the reviews</div>',
            unsafe_allow_html=True)
ledger = st.container(key="ledger_pp")
for i, pp in enumerate(b["proof_points"]):
    c_a, c_b = ledger.columns([0.84, 0.16], vertical_alignment="center")
    c_a.markdown(f'<div class="small" style="padding:5px 0;border-bottom:1px solid var(--rule)">{ui.esc(pp["text"])}</div>',
                 unsafe_allow_html=True)
    with c_b:
        rids, labs, _ = ui.resolve_evidence(ins, pp["evidence"])
        if rids:
            ui.evidence_count_button(len(rids), pp["text"][:70], rids, f"pp_{i}", labels=labs)
        else:
            st.markdown(f'<span class="meta small">{ui.esc(" ".join(pp["evidence"])[:30])}</span>', unsafe_allow_html=True)
if b.get("avoid"):
    st.markdown('<div class="meta" style="margin-top:10px">Never say: ' + ", ".join(ui.esc(a) for a in b["avoid"][:8]) + "</div>",
                unsafe_allow_html=True)

ui.continue_to("ads", "Design the ad", "Pick one of three evidence-led concepts and a visual style, then render it in three sizes.")
