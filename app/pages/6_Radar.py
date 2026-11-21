import pandas as pd
import streamlit as st

from app import ui
from core import pipeline
from core.config import brand_name, home_brand

ins = ui.setup("Launch radar", "Research", step="research")
cat = st.session_state.get("cat", "sunscreen")

c1, c2 = st.columns([0.2, 0.8], vertical_alignment="center")
refresh = c1.button("Refresh radar", type="primary", width="stretch")
c2.markdown('<div class="meta">A daily job (n8n, 08:00 IST) diffs today\'s catalogue snapshot against the previous one: '
            'launches, removals, price changes, new discounts, stock-outs.</div>', unsafe_allow_html=True)
if refresh or "radar" not in st.session_state:
    with st.spinner("Diffing snapshots…"):
        st.session_state["radar"] = pipeline.radar(cat)
rd = st.session_state["radar"]

with_diff = [e for e in rd["brands"].values() if e["diff"]]
rl = rd["rival_category_launches"]
lead = f"<b>{rd['n_changes']}</b> catalogue changes in the latest diff across <b>{len(with_diff)}</b> of {len(rd['brands'])} brands"
lead += (f"; <b>{len(rl)}</b> rival {ui.esc(cat.replace('_', ' '))} launches in the last 45 days, most recently "
         f"<b>{ui.esc(rl[0]['brand_name'])}</b> ({str(rl[0]['created_at'])[:10]})." if rl else "; no rival category launches in 45 days.")
st.markdown(f'<div class="lead" style="max-width:80ch">{lead}</div>', unsafe_allow_html=True)

if rd.get("counter_ad"):
    ca = rd["counter_ad"]
    t = ca["trigger"]
    ui.section("Draft counter-ad", f"trigger: {ui.esc(t['brand_name'])} · {ui.esc(ui.friendly_name(t['title'], 50))} · {ui.inr(t['price'])}")
    a, b = st.columns([0.6, 0.4], gap="large")
    a.markdown(f'<div style="font-family:Fraunces,Georgia,serif;font-size:22px;font-weight:600;line-height:1.2">'
               f'{ui.esc(ca["headline"])}</div><div style="margin-top:6px;font-size:14px">{ui.esc(ca["body"])}</div>',
               unsafe_allow_html=True)
    b.markdown(f'<div class="meta">{ui.esc(ca.get("rationale", ""))}<br/>Never names or disparages the rival. '
               f'Run it through the claims checker in Creative studio before use.</div>', unsafe_allow_html=True)

left, right = st.columns([0.55, 0.45], gap="large")
with left:
    ui.section("Snapshot diffs", "latest vs previous snapshot per brand")
    rows, base = [], []
    for b, e in rd["brands"].items():
        d = e["diff"]
        if not d:
            base.append(e["name"] + ("" if e["dates"] else " (no snapshot)"))
            continue
        n = {k: len(v) for k, v in d.items()}
        rows.append({"Brand": e["name"], "Window": " → ".join(x[5:] for x in e["dates"]),
                     "New": n["launches"], "Price": n["price_changes"], "Discounts": n["new_discounts"],
                     "Stock-outs": n["stockouts"], "Removed": n["removed"]})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.markdown('<div class="meta">No brand has two snapshots yet.</div>', unsafe_allow_html=True)
    if base:
        ui.caption(f"Baseline only (first diff after the next daily run): {ui.esc(', '.join(base))}.")
    details = [(e["name"], x) for e in rd["brands"].values() if e["diff"] for x in e["diff"]["price_changes"][:5]]
    if details:
        st.markdown('<div class="eyebrow" style="margin-top:10px">Price changes</div>', unsafe_allow_html=True)
        for name, x in details:
            col = "var(--mint)" if x["change_pct"] < 0 else "var(--pink)"
            st.markdown(f'<div class="row"><span class="k">{ui.esc(name)}</span><span style="flex:1">{ui.esc(ui.friendly_name(x["title"], 50))}</span>'
                        f'<span class="num">{ui.inr(x["old"])} → {ui.inr(x["new"])} <b style="color:{col}">{x["change_pct"]:+.1f}%</b></span></div>',
                        unsafe_allow_html=True)
    news = [(e["name"], x) for e in rd["brands"].values() if e["diff"] for x in e["diff"]["launches"][:5]]
    if news:
        st.markdown('<div class="eyebrow" style="margin-top:10px">New in the latest snapshot</div>', unsafe_allow_html=True)
        for name, x in news:
            st.markdown(f'<div class="row"><span class="k">{ui.esc(name)}</span><span style="flex:1">{ui.esc(ui.friendly_name(x["title"], 60))}</span>'
                        f'<span class="num meta">{ui.inr(x["price"])}</span></div>', unsafe_allow_html=True)
with right:
    ui.section("Rival category launches", "last 45 days · created_at")
    if not rl:
        st.markdown('<div class="meta">No rival launches in this category in the window.</div>', unsafe_allow_html=True)
    for l in rl[:10]:
        src = ui.img_src(l.get("image"), 120)
        img = f'<img src="{src}" style="width:44px;height:44px;object-fit:contain;border:1px solid var(--rule);border-radius:4px;background:#fff"/>' if src else ""
        st.markdown(f'<div class="row" style="align-items:center">{img}<span style="flex:1"><b>{ui.esc(l["brand_name"])}</b> · '
                    f'{ui.esc(ui.friendly_name(l["title"], 56))}<br/><span class="meta num">{ui.inr(l["price"])} · created '
                    f'{str(l["created_at"])[:10]} · <a href="{ui.esc(l["url"])}" target="_blank">open ↗</a></span></span></div>',
                    unsafe_allow_html=True)

with st.expander("All recent launches, every brand and category"):
    allr = [dict(x, brand=brand_name(b)) for b, e in rd["brands"].items() for x in e["recent_launches"]]
    if allr:
        st.dataframe(ui.df(allr)[["brand", "title", "price", "created_at", "in_category", "url"]], hide_index=True,
                     width="stretch",
                     column_config={"price": st.column_config.NumberColumn(format="₹%d"),
                                    "in_category": st.column_config.CheckboxColumn("in category"),
                                    "url": st.column_config.LinkColumn(display_text="open ↗")})
    else:
        st.markdown('<div class="meta">None.</div>', unsafe_allow_html=True)

ui.next_step("product", "Compare in product deep-dive", "See how your selected product stacks up against these rivals.")
