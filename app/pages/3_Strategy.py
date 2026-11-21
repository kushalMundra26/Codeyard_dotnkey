import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ui
from core.config import brand_name, home_brand

ui.setup("SWOT & market gaps", "Insight", step="insight")
ins = ui.need_insights()
s = ins["strategy"]
HOME = brand_name(home_brand())


def points(items, key, cls=""):
    if not items:
        st.markdown('<div class="meta">Nothing evidenced for this quadrant.</div>', unsafe_allow_html=True)
    for i, it in enumerate(items):
        ev = it.get("evidence", [])
        rids, labs, notes = ui.resolve_evidence(ins, ev)
        c1, c2 = st.columns([0.84, 0.16], vertical_alignment="top", gap="small")
        txt = it.get("text") or it.get("change") or ""
        extra = f'<div class="meta">{ui.esc(it["rationale"])}</div>' if it.get("rationale") else ""
        c1.markdown(f'<div class="swot {cls}">{ui.esc(txt)}{extra}<div class="meta small">{ui.esc(" · ".join(notes[:3]))}</div></div>',
                    unsafe_allow_html=True)
        with c2:
            ui.evidence_count_button(len(rids), txt[:80], rids, f"{key}_{i}", labels=labs,
                                     note="Evidence ids: " + ", ".join(ev[:6]))


sw = s.get("swot", {})
n_points = sum(len(v) for v in sw.values())
st.markdown(f'<div class="lead" style="font-size:16px;max-width:90ch">{ui.esc(s.get("summary", ""))}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="meta" style="margin-top:4px">{ui.engine_badge(s.get("engine"))} &nbsp;<span class="num">{n_points}</span> evidenced points · '
            f'<span class="num">{s.get("dropped_without_evidence", 0)}</span> dropped by the validator for missing evidence</div>',
            unsafe_allow_html=True)

ui.section("SWOT", "every point cites metric or review ids")
q1, q2 = st.columns(2, gap="large")
for col, (k, title, cls) in zip([q1, q2, q1, q2], [("strengths", "Strengths", "s"), ("weaknesses", "Weaknesses", "w"),
                                                  ("opportunities", "Opportunities", "o"), ("threats", "Threats", "t")]):
    with col:
        st.markdown(f"### {title} <span class='meta num'>· {len(sw.get(k, []))}</span>", unsafe_allow_html=True)
        points(sw.get(k, []), k, cls)

# ---------- gap map ----------
ui.section("Gap map", "price vs how much customers like it · bubble = labelled reviews")
gm = ui.df(ins["gap_map"]).dropna(subset=["price_per_ml", "satisfaction"]) if ins.get("gap_map") else pd.DataFrame()
if gm.empty:
    st.markdown('<div class="meta">Needs sizes (₹/ml) and labelled reviews.</div>', unsafe_allow_html=True)
else:
    xm, ym = float(gm["price_per_ml"].median()), float(gm["satisfaction"].median())
    home = gm[gm["brand"] == home_brand()]
    sweet = home[(home["price_per_ml"] <= xm) & (home["satisfaction"] >= ym)]
    risk = home[(home["price_per_ml"] > xm) & (home["satisfaction"] < ym)]
    ui.takeaway(f"<b>{len(sweet)}</b> of {len(home)} {HOME} SKUs sit in “loved & affordable”; "
                f"<b>{len(risk)}</b> are in “pricey & disliked”"
                + (f" — e.g. {ui.esc(ui.friendly_name(risk.iloc[0]['title'], 40))}." if len(risk) else "."))
    fig = go.Figure()
    sz = gm["n_reviews_labelled"].clip(lower=1)
    smax = float(sz.max())
    for is_home, d in gm.groupby(gm["brand"] == home_brand()):
        fig.add_trace(go.Scatter(
            x=d["price_per_ml"], y=d["satisfaction"], mode="markers", name=HOME if is_home else "Rivals",
            marker=dict(size=8 + 22 * (d["n_reviews_labelled"].clip(lower=1) / smax) ** 0.5,
                        color=ui.TOKENS["orange"] if is_home else ui.TOKENS["mute"], opacity=0.95 if is_home else 0.7,
                        line=dict(color="#FFFFFF", width=2)),
            customdata=list(zip(d["brand_name"], d["title"].map(lambda t: ui.friendly_name(t, 44)), d["price"], d["n_reviews_labelled"])),
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>₹%{customdata[2]:.0f} · ₹%{x:.2f}/ml · "
                          "net %{y:+.2f} · n=%{customdata[3]}<extra></extra>"))
    fig.add_hline(y=ym, line_color="#D9D6CF", line_width=1)
    fig.add_vline(x=xm, line_color="#D9D6CF", line_width=1)
    x0, x1 = float(gm["price_per_ml"].min()), float(gm["price_per_ml"].max())
    y0, y1 = float(gm["satisfaction"].min()), float(gm["satisfaction"].max())
    for x, y, t, xa, ya in ((x0, y1, "Loved & affordable", "left", "top"), (x1, y1, "Loved & premium", "right", "top"),
                            (x0, y0, "Cheap & disliked", "left", "bottom"), (x1, y0, "Pricey & disliked", "right", "bottom")):
        fig.add_annotation(x=x, y=y, text=t, showarrow=False, xanchor=xa, yanchor=ya,
                           font=dict(size=11, color="#64686E"))
    fig.update_xaxes(title="₹ per ml")
    fig.update_yaxes(title="topic satisfaction (net)")
    ui.chart(fig, 420, key="gap")
    ui.caption("Grey rules = category medians. Satisfaction = mean net sentiment across a SKU's labelled topics.")

# ---------- opportunity + whitespace ----------
a, b = st.columns([0.5, 0.5], gap="large")
with a:
    ui.section("Where to win", "opportunity · estimate")
    op = ui.df(ins.get("opportunity"))
    if op.empty:
        st.markdown('<div class="meta">No opportunity scores.</div>', unsafe_allow_html=True)
    else:
        o0 = op.iloc[0]
        ui.takeaway(f"Biggest opening: <b>{ui.esc(o0['label'].lower())}</b> — {o0['demand_share'] * 100:.0f}% of reviews "
                    f"mention it and {HOME} nets <b>{o0['dk_net']:+.2f}</b>"
                    + (f" (best rival {ui.esc(o0['best_rival'])} {o0['best_rival_net']:+.2f})." if o0.get("best_rival") else "."))
        vmax = float(op["opportunity"].max() or 1)
        ledger = st.container(key="ledger_opp")
        for _, r in op.head(8).iterrows():
            ledger.markdown(ui.lg_bar(r["label"], r["opportunity"], vmax, f"{r['opportunity']:.1f}", ui.TOKENS["blue"]),
                            unsafe_allow_html=True)
        ui.caption("estimate = share of reviews mentioning the topic × D&K weakness ((1 − net)/2) × 100.")
with b:
    ui.section("Whitespace", "feature × price band with few SKUs")
    ws = ui.df(ins.get("whitespace"))
    if ws.empty:
        st.markdown('<div class="meta">No whitespace rows.</div>', unsafe_allow_html=True)
    else:
        gaps = ws[~ws["dk_has"].astype(bool)]
        if len(gaps):
            g0 = gaps.iloc[0]
            ui.takeaway(f"{HOME} has nothing in <b>{ui.esc(g0['feature'])}</b> at {ui.esc(g0['price_band'])} "
                        f"(only {int(g0['n_skus'])} SKU{'s' if g0['n_skus'] != 1 else ''} in the market).")
        st.dataframe(ws.head(14)[["feature", "price_band", "n_skus", "n_brands", "dk_has", "satisfaction"]],
                     hide_index=True, width="stretch", height=330,
                     column_config={"feature": "Feature", "price_band": "Price band", "n_skus": "SKUs", "n_brands": "Brands",
                                    "dk_has": st.column_config.CheckboxColumn("D&K has"),
                                    "satisfaction": st.column_config.NumberColumn("Net", format="%+.2f")})

# ---------- trends & forecast ----------
t1, t2 = st.columns(2, gap="large")
with t1:
    ui.section("Launch trends", "terms in category launches by quarter")
    tr = ui.df(ins.get("trends"))
    if tr.empty:
        st.markdown('<div class="meta">No launches with tracked terms.</div>', unsafe_allow_html=True)
    else:
        top = tr["term"].value_counts().head(5).index.tolist()
        g = tr[tr["term"].isin(top)].groupby(["quarter", "term"]).size().reset_index(name="launches")
        last_q = sorted(g["quarter"].unique())[-1]
        lead_t = tr[tr["quarter"] == last_q]["term"].value_counts()
        if len(lead_t):
            ui.takeaway(f"Most common in {ui.esc(last_q)} launches: <b>{ui.esc(lead_t.index[0])}</b> "
                        f"({int(lead_t.iloc[0])} launch{'es' if lead_t.iloc[0] != 1 else ''}).")
        colors = [ui.TOKENS[c] for c in ("orange", "blue", "pink", "mint", "yellow")]
        fig = go.Figure()
        for i, term in enumerate(top):
            d = g[g["term"] == term].sort_values("quarter")
            fig.add_trace(go.Bar(x=d["quarter"], y=d["launches"], name=term, marker=dict(color=colors[i], line=dict(width=0))))
        fig.update_layout(barmode="stack", bargap=0.35)
        fig.update_xaxes(tickangle=-35, type="category")
        fig.update_yaxes(title="launches")
        ui.chart(fig, 320, key="trends")
        ui.caption("Uses Shopify created_at — approximate (re-listings can reset dates). Top 5 terms only.")
with t2:
    ui.section("Demand proxy", "monthly reviews + 3-month projection · estimate")
    fc = ui.df(ins.get("forecast"))
    if fc.empty:
        st.markdown('<div class="meta">No dated reviews.</div>', unsafe_allow_html=True)
    else:
        fig = go.Figure()
        for b_, d in fc.groupby("brand"):
            is_home = b_ == home_brand()
            col = ui.TOKENS["orange"] if is_home else ui.TOKENS["mute"]
            for kind, dash in (("actual", "solid"), ("forecast", "dot")):
                dd = d[d["kind"] == kind].sort_values("month")
                if dd.empty:
                    continue
                fig.add_trace(go.Scatter(x=dd["month"], y=dd["reviews"], mode="lines", name=brand_name(b_),
                                         legendgroup=b_, showlegend=(kind == "actual" and is_home),
                                         line=dict(color=col, width=2.5 if is_home else 1.5, dash=dash),
                                         hovertemplate=f"{brand_name(b_)} · %{{x}}: %{{y:.0f}} reviews ({kind})<extra></extra>"))
        h = fc[(fc["brand"] == home_brand()) & (fc["kind"] == "actual")].sort_values("month")
        if len(h) >= 6:
            a3, p3 = h["reviews"].tail(3).mean(), h["reviews"].iloc[-6:-3].mean()
            ui.takeaway(f"{HOME} review velocity {'up' if a3 >= p3 else 'down'} <b>{abs(a3 - p3) / max(p3, 1) * 100:.0f}%</b> "
                        f"over the last 3 months vs the 3 before.")
        ui.chart(fig, 320, key="fc")
        ui.caption(f"{HOME} in orange, rivals grey; dotted = linear projection. Reviews lag sales and cover only stores with public feeds.")

# ---------- improvements, concepts, GTM ----------
a, b = st.columns([0.5, 0.5], gap="large")
with a:
    ui.section("Product improvements")
    points(s.get("improvements", []), "imp")
with b:
    ui.section("New product concepts")
    for i, c in enumerate(s.get("concepts", [])):
        st.markdown(f'<div class="swot o"><div style="font-weight:700">{ui.esc(c["name"])}</div>'
                    f'<div>{ui.esc(c["one_liner"])}</div><div style="margin-top:4px">{ui.tag(c["price_band"], "orange")}'
                    + "".join(ui.tag(x, "blue") for x in c.get("key_ingredients", [])[:4]) +
                    f'</div><div class="meta">Gap: {ui.esc(c["target_gap"])} · Why now: {ui.esc(c["why_now"])}</div></div>',
                    unsafe_allow_html=True)
ui.section("Go-to-market")
gtm = ui.df(s.get("gtm", []))
if not gtm.empty:
    gtm = gtm.assign(evidence=gtm["evidence"].map(lambda e: " ".join(e) if isinstance(e, list) else e))
    st.dataframe(gtm, hide_index=True, width="stretch",
                 column_config={"persona": "Persona", "message": st.column_config.TextColumn("Message", width="large"),
                                "channel": "Channel", "city_language": "City · language", "evidence": "Evidence ids"})

ui.next_step("audit", "Audit the product listing",
             "Check how much of what customers care about the current store listing actually says.")
