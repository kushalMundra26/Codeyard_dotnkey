import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ui
from core import marketplace, pipeline
from core.config import brand_name, home_brand

ins = ui.setup("Product deep-dive", "Insight", step="insight")
ins = ui.need_insights()
p = ui.current_product(ins)
ctx = ui.context(ins, p["handle"])
HOME = brand_name(home_brand())
ui.product_header(p, ctx)

own = [t for t in ctx["own_topics"] if t["n"] >= 3]
own_all = ctx["own_topics"]
labels_here = [l for l in ins["labels"] if l["handle"] == p["handle"] and l["brand"] == home_brand()]

# best rival score per topic among the top-5 matched rivals (n >= 3)
best_rival: dict = {}
for r in ctx["rivals"]:
    for t in pipeline.product_topics(ins, r["brand"], r["handle"]):
        if t["n"] < 3:
            continue
        cur = best_rival.get(t["topic"])
        if cur is None or t["net"] > cur["net"]:
            best_rival[t["topic"]] = t | {"brand_name": r["brand_name"], "title": r["title"]}

# ---------- topic sentiment vs best rival ----------
ui.section("What customers say about this product", "net sentiment per topic, −1 to +1 · vs best of the top-5 rivals",
           first=True)
if not own:
    ui.empty_state("Not enough labelled reviews for this product",
                   f"Topics need at least 3 mentions to chart; this product has {sum(t['n'] for t in own_all)} topic mentions. "
                   "Pick a product with more reviews in the sidebar, or re-run the analysis in Live mode to collect more.")
else:
    best = max(own, key=lambda t: (t["net"], t["n"]))
    worst = min(own, key=lambda t: (t["net"], -t["n"]))
    msg = (f"Strongest on <b>{ui.esc(best['label'].lower())}</b> (net <b>{best['net']:+.2f}</b>, n={best['n']}); "
           f"weakest on <b>{ui.esc(worst['label'].lower())}</b> (net <b>{worst['net']:+.2f}</b>, n={worst['n']})")
    br = best_rival.get(worst["topic"])
    if br and br["net"] > worst["net"]:
        msg += f" — where {ui.esc(br['brand_name'])} scores <b>{br['net']:+.2f}</b>."
    else:
        msg += "."
    ui.takeaway(msg)
    left, right = st.columns([0.56, 0.44], gap="large")
    with left:
        d = sorted(own, key=lambda t: t["n"])
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[t["net"] for t in d], y=[t["label"] for t in d], orientation="h", name="This product",
            marker=dict(color=[ui.sent_color(t["net"]) for t in d], line=dict(width=0)), width=0.55,
            customdata=[[t["n"]] for t in d], hovertemplate="%{y}: net %{x:+.2f} (n=%{customdata[0]})<extra>this product</extra>"))
        rx = [best_rival.get(t["topic"]) for t in d]
        fig.add_trace(go.Scatter(
            x=[r["net"] if r else None for r in rx], y=[t["label"] for t in d], mode="markers", name="Best rival",
            marker=dict(symbol="diamond", size=10, color="#FFFFFF", line=dict(color=ui.TOKENS["ink"], width=2)),
            customdata=[[r["brand_name"] if r else "", r["n"] if r else 0] for r in rx],
            hovertemplate="%{customdata[0]}: net %{x:+.2f} (n=%{customdata[1]})<extra>best rival</extra>"))
        fig.update_xaxes(range=[-1.08, 1.08], zeroline=True, zerolinecolor="#B8B5AE", zerolinewidth=1,
                         tickvals=[-1, -0.5, 0, 0.5, 1], ticktext=["−1 negative", "−0.5", "0", "+0.5", "+1 positive"])
        fig.update_yaxes(showgrid=False)
        ui.chart(fig, 60 + 30 * len(d), key="topic_div")
        ui.caption("Bars: this product (pink negative · mint positive). Hollow diamond: the best-scoring of its five closest "
                   "rivals on that topic. Topics need n ≥ 3.")
    with right:
        st.markdown('<div class="eyebrow" style="margin-bottom:4px">Topic ledger · click n to read the reviews</div>',
                    unsafe_allow_html=True)
        ledger = st.container(key="ledger_topics")
        for t in own_all[:11]:
            c1, c2, c3 = ledger.columns([0.5, 0.32, 0.18], vertical_alignment="center", gap="small")
            c1.markdown(f'<div class="small" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{ui.esc(t["label"])}'
                        f' <span class="meta num">{t["net"]:+.2f}</span></div>', unsafe_allow_html=True)
            c2.markdown(ui.div_bar(t["net"]), unsafe_allow_html=True)
            with c3:
                ui.evidence_count_button(t["n"], f"{ui.friendly_name(p['title'], 40)} · {t['label']}", t["review_ids"],
                                         f"pt_{t['topic']}", labels=[l for l in labels_here if l["topic"] == t["topic"]])

# ---------- rivals ----------
ui.section("Five closest rivals", "one product per brand")
if ctx["rivals"]:
    r0 = ctx["rivals"][0]
    ui.takeaway(f"Closest match is {ui.esc(r0['brand_name'])}'s {ui.esc(ui.friendly_name(r0['title'], 50))} "
                f"(<b>{r0['match']['score']:.2f}</b>) at <b>{ui.inr(r0['price'])}</b> vs our <b>{ui.inr(p['price'])}</b>.")
    rows = [{"Brand": r["brand_name"], "Product": ui.friendly_name(r["title"], 60), "Price": r["price"],
             "₹/ml": r.get("price_per_ml"), "SPF": (r.get("spec") or {}).get("spf"), "Match": r["match"]["score"],
             "Why it matches": r["match"]["reason"], "Link": r.get("url")} for r in ctx["rivals"]]
    st.dataframe(ui.df(rows), hide_index=True, width="stretch",
                 column_config={"Match": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f", width="small"),
                                "Price": st.column_config.NumberColumn(format="₹%d"),
                                "₹/ml": st.column_config.NumberColumn(format="₹%.2f"),
                                "Why it matches": st.column_config.TextColumn(width="large"),
                                "Link": st.column_config.LinkColumn(display_text="open ↗", width="small")})
    ui.caption("match = 0.35 format/category + 0.25 ingredient & claim overlap + 0.20 price-band closeness + 0.20 skin-type overlap.")
else:
    st.markdown('<div class="meta">No rivals scored for this product.</div>', unsafe_allow_html=True)

# ---------- heatmap + quotes ----------
left, right = st.columns([0.58, 0.42], gap="large")
with left:
    ui.section("Brand × topic sentiment", "category-wide · n in each cell")
    bt = ui.df(ins["metrics"]["brand_topic"])
    if bt.empty:
        st.markdown('<div class="meta">No labelled topics yet.</div>', unsafe_allow_html=True)
    else:
        bt = bt[bt["n"] >= 3]
        piv = bt.pivot_table(index="brand", columns="label", values="net")
        nn = bt.pivot_table(index="brand", columns="label", values="n")
        # order: D&K on top, then by mean net; topics by total mentions
        topics = bt.groupby("label")["n"].sum().sort_values(ascending=False).index.tolist()
        order = [b for b in piv.mean(axis=1).sort_values(ascending=False).index if b != home_brand()]
        order = ([home_brand()] if home_brand() in piv.index else []) + order
        piv, nn = piv.reindex(index=order, columns=topics), nn.reindex(index=order, columns=topics)
        if home_brand() in piv.index:
            gaps = (piv.max(axis=0) - piv.loc[home_brand()]).dropna().sort_values(ascending=False)
            if len(gaps) and gaps.iloc[0] > 0:
                t = gaps.index[0]
                leader = piv[t].idxmax()
                ui.takeaway(f"{HOME}'s biggest gap to the field is <b>{ui.esc(t.lower())}</b>: "
                            f"<b>{piv.loc[home_brand(), t]:+.2f}</b> vs {ui.esc(brand_name(leader))}'s <b>{piv.loc[leader, t]:+.2f}</b>.")
        ylab = [f"<b>{brand_name(i)}</b>" if i == home_brand() else brand_name(i) for i in piv.index]
        text = [[f"{v:+.2f}<br><span style='font-size:9px'>n={int(n)}</span>" if v == v else "" for v, n in zip(rv, rn)]
                for rv, rn in zip(piv.values, nn.fillna(0).values)]
        fig = go.Figure(go.Heatmap(z=piv.values, x=list(piv.columns), y=ylab, zmin=-1, zmax=1, colorscale=ui.SENT_SCALE,
                                   text=text, texttemplate="%{text}", textfont={"size": 10, "color": "#1E2022"}, xgap=2, ygap=2,
                                   hovertemplate="%{y} · %{x}: net %{z:+.2f}<extra></extra>",
                                   colorbar=dict(title=dict(text="net", font=dict(size=11)), thickness=8, len=0.6,
                                                 tickvals=[-1, 0, 1], ticktext=["−1", "0", "+1"])))
        fig.update_xaxes(tickangle=-35, side="bottom", showgrid=False)
        fig.update_yaxes(autorange="reversed", showgrid=False)
        ui.chart(fig, 120 + 34 * len(piv.index), legend=False, key="heat")
        ui.caption("Net sentiment = mean of −1/0/+1 topic labels. Blank cells have fewer than 3 mentions. Computed in pandas.")
with right:
    ui.section("In their words", "exact quotes")
    qs = ctx["quotes"]
    pos = [q for q in qs if q["sentiment"] > 0][:4]
    neg = [q for q in qs if q["sentiment"] < 0][:4]
    if not qs:
        st.markdown('<div class="meta">No quotes for this product yet.</div>', unsafe_allow_html=True)
    for q in pos + neg:
        st.markdown(ui.quote_html(q, show_brand=False), unsafe_allow_html=True)
    if ctx["unmet"]:
        st.markdown('<div class="eyebrow" style="margin-top:12px">Unmet needs · “I wish…”</div>', unsafe_allow_html=True)
        seen_u = set()
        uniq = [u for u in ctx["unmet"] if not (u["quote"].lower() in seen_u or seen_u.add(u["quote"].lower()))]
        for u in uniq[:5]:
            st.markdown(f'<div class="quote">“{ui.esc(u["quote"])}”<span class="src">{ui.esc(brand_name(u["brand"]))} · '
                        f'<code>{ui.esc(u["review_id"])}</code></span></div>', unsafe_allow_html=True)

# ---------- marketplace ----------
STOP = {"dot", "key", "sunscreen", "spf", "pa", "with", "and", "the", "for", "in", "vivo", "tested", "50", "gel", "cream",
        "fixture", "face", "sun", "ml", "g", "of", "a"}


def words(t: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if w not in STOP and len(w) > 1}


mk = [r for r in marketplace.load() if r.get("brand_key") == home_brand()]
ui.section("Marketplace snapshot", ui.MARKET_LABEL)
if mk:
    pw = words(ui.friendly_name(p["title"], 200))
    match = [r for r in mk if len(pw & words(r.get("product_name_on_listing"))) >= 1]
    if match:
        ui.takeaway(f"{len(match)} marketplace listing{'s' if len(match) > 1 else ''} match this product by name.")
    else:
        st.markdown(f'<div class="meta">No listing matched this product by name — showing all {len(mk)} {HOME} rows.</div>',
                    unsafe_allow_html=True)
    ui.marketplace_table(match or mk, key="mk_prod")
    comp = [c for r in (match or mk) for c in (r.get("top_complaints") or [])]
    if comp:
        st.markdown('<div class="eyebrow" style="margin-top:8px">Complaints quoted on marketplace listings</div>',
                    unsafe_allow_html=True)
        for c in comp[:4]:
            st.markdown(f'<div class="quote neg">“{ui.esc(c["snippet"])}”<span class="src">{ui.esc(c.get("theme", ""))} · '
                        f'marketplace listing (not in review stats)</span></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="meta">No {HOME} rows in the marketplace snapshot.</div>', unsafe_allow_html=True)

# ---------- rival quotes ----------
ui.section("Rival customers on the same topics", "from the five closest rivals")
lab = ui.df(ins["labels"])
if not lab.empty and own_all:
    rv_keys = {(r["brand"], r["handle"]) for r in ctx["rivals"]}
    d = lab[[(b, h) in rv_keys for b, h in zip(lab["brand"], lab["handle"])]]
    tabs = st.tabs([t["label"] for t in own_all[:6]])
    for tab, t in zip(tabs, own_all[:6]):
        with tab:
            dd = d[d["topic"] == t["topic"]].sort_values("sentiment")
            if dd.empty:
                st.markdown('<div class="meta">No rival mentions of this topic.</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2, gap="large")
            for i, (_, q) in enumerate(dd.head(6).iterrows()):
                (c1 if i % 2 == 0 else c2).markdown(ui.quote_html(q.to_dict()), unsafe_allow_html=True)

ui.next_step("studio", "Turn this into a brief",
             "The Creative studio writes a brief from exactly this evidence, then ads, listing copy and a storyboard video.")
