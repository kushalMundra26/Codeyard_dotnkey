import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ui
from core import marketplace
from core.config import brand_name, home_brand

ins = ui.setup("The market", "Research · step 2", step="start",
               intro="What customers complain about across the category, who the closest rivals are, and where prices sit.")
ui.gate("research_done", "Start with Research",
        "Pick a category and a Dot &amp; Key product, then press <b>Analyse the market</b>. Results appear here.",
        "start", "Start with Research")
cat = ins["category"]
HOME = brand_name(home_brand())
m = ins["metrics"]
n_rev = sum(m.get("n_reviews", {}).values())
prods = ins["products"]
home = ui.home_products(ins)
brands_ = sorted({p["brand"] for p in prods})
cs = ui.df(m.get("complaint_share"))
rt = ui.df(m.get("ratings"))
lab = ins.get("label_stats", {})

# brand ratings (collected reviews), weighted by n
brand_rt = pd.DataFrame()
if not rt.empty:
    brand_rt = (rt.assign(w=rt["avg_rating"].fillna(0) * rt["n"], low=rt["pct_1_2"].fillna(0) * rt["n"])
                .groupby("brand").agg(reviews=("n", "sum"), w=("w", "sum"), low=("low", "sum")).reset_index())
    brand_rt["avg"] = brand_rt["w"] / brand_rt["reviews"].clip(lower=1)
    brand_rt["low_share"] = brand_rt["low"] / brand_rt["reviews"].clip(lower=1)
    brand_rt = brand_rt.sort_values("avg", ascending=False).reset_index(drop=True)

# ---------- complaints + rivals ----------
left, right = st.columns([0.56, 0.44], gap="large")
with left:
    ui.section("What the category complains about", "share of negative reviews · click n to read them")
    if cs.empty:
        st.markdown('<div class="meta">No negative topic mentions found.</div>', unsafe_allow_html=True)
    else:
        top = cs.iloc[0]
        second = cs.iloc[1] if len(cs) > 1 else None
        ui.takeaway(f"{ui.esc(top['label'])} leads with <b>{top['share_of_complaints'] * 100:.0f}%</b> of complaints"
                    + (f", ahead of {ui.esc(second['label'].lower())} (<b>{second['share_of_complaints'] * 100:.0f}%</b>)."
                       if second is not None else "."))
        labels = ins["labels"]
        vmax = float(cs["share_of_complaints"].max())
        ledger = st.container(key="ledger_cs")
        for i, r in cs.head(9).iterrows():
            c1, c2 = ledger.columns([0.84, 0.16], vertical_alignment="center", gap="small")
            c1.markdown(ui.lg_bar(r["label"], r["share_of_complaints"], vmax, f"{r['share_of_complaints'] * 100:.0f}%",
                                  ui.TOKENS["pink"]), unsafe_allow_html=True)
            with c2:
                ids = [l["review_id"] for l in labels if l["topic"] == r["topic"] and l["sentiment"] < 0]
                ui.evidence_count_button(int(r["neg_reviews"]), f"Complaints · {r['label']}", ids, f"cs_{r['topic']}",
                                         labels=[l for l in labels if l["topic"] == r["topic"]])
        ui.caption(f"A review can raise several complaints; shares are of reviews with ≥1 negative topic. "
                   f"Labelled by {ui.esc(lab.get('engine', '?'))}.")
with right:
    ui.section("Closest rivals", "avg best-match over D&K SKUs")
    cr = ui.df(ins.get("category_rivals"))
    if cr.empty:
        st.markdown('<div class="meta">No rivals scored.</div>', unsafe_allow_html=True)
    else:
        ui.takeaway(f"{ui.esc(cr.iloc[0]['name'])} overlaps most with {HOME}'s range "
                    f"(match <b>{cr.iloc[0]['avg_match']:.2f}</b> of 1).")
        st.dataframe(cr[["name", "avg_match", "n"]], hide_index=True, width="stretch",
                     column_config={"name": "Brand",
                                    "avg_match": st.column_config.ProgressColumn("Match", min_value=0, max_value=1, format="%.2f"),
                                    "n": st.column_config.NumberColumn("D&K SKUs matched")})
        ui.caption("match = 0.35 format + 0.25 ingredient & claim overlap + 0.20 price-band closeness + 0.20 skin-type overlap.")

# ---------- price ladder + ratings ----------
left, right = st.columns([0.56, 0.44], gap="large")
with left:
    ui.section("Price ladder", "₹ per ml · 1 g ≈ 1 ml")
    pr = ui.df(prods).dropna(subset=["price_per_ml"])
    if pr.empty:
        st.markdown('<div class="meta">No sizes parsed, so ₹/ml is unavailable.</div>', unsafe_allow_html=True)
    else:
        pr["Brand"] = pr["brand"].map(brand_name)
        med = pr.groupby("Brand")["price_per_ml"].median().sort_values()
        cat_med = float(pr["price_per_ml"].median())
        if HOME in med.index:
            pos = list(med.index).index(HOME) + 1
            ui.takeaway(f"{HOME}'s median is <b>₹{med[HOME]:.1f}/ml</b> vs a category median of <b>₹{cat_med:.1f}/ml</b> — "
                        f"#{pos} cheapest of {len(med)} brands.")
        fig = go.Figure()
        order = list(med.index)
        for b in order:
            d = pr[pr["Brand"] == b]
            is_home = b == HOME
            fig.add_trace(go.Scatter(
                x=d["price_per_ml"], y=[b] * len(d), mode="markers", name=b, showlegend=False,
                marker=dict(size=11 if is_home else 9, color=ui.TOKENS["orange"] if is_home else ui.TOKENS["mute"],
                            line=dict(color="#FFFFFF", width=2), opacity=1 if is_home else 0.85),
                customdata=list(zip(d["title"].map(lambda t: ui.friendly_name(t, 48)), d["price"])),
                hovertemplate="%{customdata[0]}<br>₹%{customdata[1]:.0f} · ₹%{x:.2f}/ml<extra>" + b + "</extra>"))
        fig.add_trace(go.Scatter(x=med.values, y=order, mode="markers", name="brand median", showlegend=False,
                                 marker=dict(symbol="line-ns", size=16, line=dict(width=2, color=ui.TOKENS["ink"])),
                                 hovertemplate="median ₹%{x:.2f}/ml<extra>%{y}</extra>"))
        fig.add_vline(x=cat_med, line_color="#E6E4DF", line_width=1)
        fig.update_yaxes(categoryorder="array", categoryarray=order, showgrid=False)
        fig.update_xaxes(title="₹ per ml", rangemode="tozero")
        ui.chart(fig, 40 + 34 * len(order), legend=False)
        ui.caption("Dots = SKUs (Dot & Key in orange) · black tick = brand median · grey rule = category median.")
with right:
    ui.section("Ratings & review velocity", "collected reviews, not store averages")
    if not brand_rt.empty:
        fc = ui.df(ins.get("forecast"))
        spark = {}
        if not fc.empty:
            act = fc[fc["kind"] == "actual"].sort_values("month")
            for b, d in act.groupby("brand"):
                spark[b] = d["reviews"].tail(12).tolist()
        tbl = pd.DataFrame({
            "Brand": brand_rt["brand"].map(brand_name), "Avg": brand_rt["avg"].round(2),
            "1–2★": brand_rt["low_share"] * 100, "Reviews": brand_rt["reviews"].astype(int),
            "Monthly reviews (12 mo)": brand_rt["brand"].map(lambda b: spark.get(b, []))})
        best = tbl.iloc[0]
        ui.takeaway(f"{ui.esc(best['Brand'])} is best rated at <b>{best['Avg']:.2f}★</b> over <b>{best['Reviews']:,}</b> reviews.")
        st.dataframe(tbl, hide_index=True, width="stretch",
                     column_config={"Avg": st.column_config.NumberColumn(format="★ %.2f"),
                                    "1–2★": st.column_config.NumberColumn(format="%.0f%%", help="share of 1–2 star reviews"),
                                    "Monthly reviews (12 mo)": st.column_config.LineChartColumn(width="small")})
        ui.caption("Velocity = reviews per month, a rough demand proxy (reviews lag sales).")

# ---------- marketplace ----------
mk = marketplace.load()
ui.section("Marketplace snapshot", ui.MARKET_LABEL)
if mk:
    by_m = pd.DataFrame(mk)
    dk = by_m[by_m["brand_key"] == home_brand()]
    if not dk.empty and dk["rating_count"].notna().any():
        top = dk.sort_values("rating_count", ascending=False).iloc[0]
        ui.takeaway(f"{HOME}'s most-rated marketplace listing has <b>{int(top['rating_count']):,}</b> ratings on "
                    f"{ui.esc(top['marketplace'])} at <b>{top['rating']}★</b>"
                    + (f" · {ui.esc(top['bestseller_rank'])}" if top.get("bestseller_rank") else "") + ".")
    ui.marketplace_table(sorted(mk, key=lambda r: (r.get("brand_key") != home_brand(), r.get("brand") or "",
                                                   -(r.get("rating_count") or 0))), key="mk_all")
    ui.caption("Public listing data, kept separate from the review statistics above (those come only from each brand's "
               "own review feed). Open each link to verify before quoting.")
else:
    st.markdown('<div class="meta">No marketplace snapshot imported yet (data/marketplace/).</div>', unsafe_allow_html=True)

ui.section("Recent category launches", "last 90 days · Shopify created_at")
la = [l for l in ins.get("launches", []) if l["in_category"]][:8]
if not la:
    st.markdown('<div class="meta">No category launches in the last 90 days.</div>', unsafe_allow_html=True)
for l in la:
    st.markdown(f'<div class="row"><span class="k">{ui.esc(brand_name(l["brand"]))}</span>'
                f'<span style="flex:1">{ui.esc(ui.friendly_name(l["title"], 54))}</span>'
                f'<span class="meta num">{ui.inr(l["price"])} · {str(l["created_at"])[:10]}</span></div>',
                unsafe_allow_html=True)


ui.continue_to("product", "Generate insights", "Compare the product with its closest rivals, topic by topic, and build the SWOT.")
