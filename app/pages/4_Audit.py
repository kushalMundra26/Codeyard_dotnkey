import streamlit as st

from app import ui
from core import pipeline
from core.audit import coverage_score

ui.setup("Listing audit", "Insight", step="insight")
ins = ui.need_insights()
p = ui.current_product(ins)
ctx = ui.context(ins, p["handle"])
ui.product_header(p, ctx)
base = coverage_score(ctx)
camp = ui.current_campaign(p["handle"])
aud = (camp or {}).get("audit", {}).get("llm")

rows = ui.df(base["rows"])
missing_good = rows[(~rows["in_listing"]) & (rows["net"] > 0.25)] if not rows.empty else rows
lead = (f"The store listing addresses <b>{base['score']}%</b> of what customers talk about — "
        f"<b>{len(base['covered'])}</b> of {len(rows)} topics, in {base['listing_words']} words.")
if len(missing_good):
    lead += (f" It never mentions <span class='hl'><b>{ui.esc(missing_good.iloc[0]['label'].lower())}</b></span>, "
             f"which customers praise (net {missing_good.iloc[0]['net']:+.2f}, n={int(missing_good.iloc[0]['mentions'])}).")
st.markdown(f'<div class="lead" style="max-width:80ch">{lead}</div>', unsafe_allow_html=True)

ui.section("What customers talk about vs what the listing says", "attention coverage = share of topic mentions the listing addresses")
if not rows.empty:
    ACT = {"Lead with it": "ok", "Keep": "ok", "Address honestly": "warn", "Consider": "quiet", "Remove / soften": "block"}
    head = st.columns([0.3, 0.28, 0.12, 0.12, 0.18])
    for c, h in zip(head, ["Topic", "Customer sentiment", "Mentions", "In listing", "Action"]):
        c.markdown(f'<div class="eyebrow">{h}</div>', unsafe_allow_html=True)
    ledger = st.container(key="ledger_audit")
    for i, r in rows.iterrows():
        c = ledger.columns([0.3, 0.28, 0.12, 0.12, 0.18], vertical_alignment="center")
        c[0].markdown(f'<div class="small">{ui.esc(r["label"])} <span class="meta num">{r["net"]:+.2f}</span></div>',
                      unsafe_allow_html=True)
        c[1].markdown(ui.div_bar(r["net"]), unsafe_allow_html=True)
        with c[2]:
            t = next((t for t in ctx["own_topics"] if t["topic"] == r["topic"]), None)
            if t:
                ui.evidence_count_button(int(r["mentions"]), f"{r['label']} · this product", t["review_ids"], f"au_{r['topic']}",
                                         labels=[l for l in ins["labels"] if l["handle"] == p["handle"] and l["topic"] == r["topic"]])
            else:
                st.markdown(f'<span class="meta num">{int(r["mentions"])}</span>', unsafe_allow_html=True)
        c[3].markdown(ui.status_tag("ok", "✓ yes") if r["in_listing"] else ui.tag("— no", "quiet"), unsafe_allow_html=True)
        c[4].markdown(ui.tag(r["action"], ACT.get(r["action"], "")), unsafe_allow_html=True)

ui.section("Before / after", ui.engine_badge((camp or {}).get("engines", {}).get("audit")) if aud else "")
a, b = st.columns(2, gap="large")
with a:
    st.markdown('<div class="eyebrow">Before · current store listing</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f'<div style="font-size:13.5px;line-height:1.55">{ui.esc(p.get("body_text") or "(empty description on the store)")}</div>',
                    unsafe_allow_html=True)
with b:
    st.markdown('<div class="eyebrow">After · evidence-led rewrite</div>', unsafe_allow_html=True)
    with st.container(border=True):
        if aud:
            st.markdown(f'<div style="font-size:13.5px;line-height:1.55">{ui.esc(aud["rewritten_description"])}</div>',
                        unsafe_allow_html=True)
            if aud.get("missing_topics"):
                st.markdown('<div class="meta" style="margin-top:8px">Adds: ' + "".join(ui.tag(t, "ok") for t in aud["missing_topics"]) + "</div>",
                            unsafe_allow_html=True)
            if aud.get("risky_lines"):
                st.markdown('<div class="meta" style="margin-top:6px">Over-promising lines in the current listing:</div>' +
                            "".join(ui.status_tag("block", l) for l in aud["risky_lines"]), unsafe_allow_html=True)
            st.markdown(f'<div class="meta" style="margin-top:6px">{ui.esc(aud.get("score_rationale", ""))}</div>', unsafe_allow_html=True)
            rids = ui.review_ids(aud.get("evidence", []))
            if rids:
                ui.evidence_count_button(len(rids), "Rewrite evidence", rids, "aud_ev", label=f"evidence · n = {len(rids)}")
        else:
            st.markdown('<div class="meta">The rewrite is produced as part of a campaign for this product. '
                        'Generate one here (no video, ~seconds) or in the Creative studio.</div>', unsafe_allow_html=True)
            if st.button("Generate rewrite", type="primary", disabled=not ui.can_act()):
                with st.status("Generating campaign (brief → copy → audit)", expanded=True) as status:
                    camp = pipeline.generate_campaign(ins["category"], p["handle"], make_video=False,
                                                      progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                    status.update(label="Rewrite ready", state="complete")
                st.session_state["campaign_id"] = camp["id"]
                st.rerun()

ui.next_step("studio", "Open Creative studio", "Use these gaps in the brief, ads and listing copy.")
