import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ui
from core import marketplace, pipeline
from core.config import brand_name, home_brand

ins = ui.setup("Market overview", "Research", step="research")
cat = st.session_state.get("cat", "sunscreen")
live = st.session_state.get("mode") == "Live"
HOME = brand_name(home_brand())

STEPS = ["Catalogue", "Enrich", "Reviews", "Review intelligence", "Rivals", "Market gaps", "Strategy", "Done"]

# ---------- actions ----------
a1, a2, a3 = st.columns([0.2, 0.2, 0.6], vertical_alignment="center")
run = a1.button("Re-run analysis" if ins else "Run analysis", type="primary", width="stretch", disabled=not ui.can_act())
surprise = a2.button("Surprise me", width="stretch", disabled=not ins,
                     help="Pick a random real Dot & Key product and jump straight to the Creative studio")
a3.markdown(f'<div class="meta">{"<b>Live</b>: re-scrapes 11 stores + review feeds, then re-runs every layer (minutes)." if live else "<b>Demo</b>: re-computes from saved snapshots and review files (seconds). Switch to Live in the sidebar to re-scrape."}</div>',
            unsafe_allow_html=True)

if surprise:
    p = pipeline.surprise_product(cat)
    if p:
        st.session_state["handle"] = p["handle"]
        st.session_state["autogen"] = True
        st.switch_page(ui.PAGES["studio"])

if run:
    with st.status("Running analysis", expanded=True) as status:
        seen = []

        def prog(step, detail="", frac=None):
            if step not in seen:
                seen.append(step)
                st.markdown(f'<div class="meta"><b style="color:var(--ink)">{ui.esc(step)}</b> · {ui.esc(detail)}</div>',
                            unsafe_allow_html=True)
            k = STEPS.index(step) + 1 if step in STEPS else len(seen)
            status.update(label=f"Step {min(k, 7)} of 7 · {step} — {detail}", expanded=True)
        try:
            if live or not ins:
                ins = pipeline.run_analysis(cat, live=True, progress=prog)
            else:
                ins = pipeline.run_analysis(cat, live=False, progress=prog)
            status.update(label=f"Analysis complete in {ins['elapsed_s']} s — {len(ins['products'])} SKUs", state="complete",
                          expanded=False)
        except Exception as e:
            status.update(label="Analysis failed", state="error")
            st.error(f"{e}. If the stores rate-limited us, switch to Demo mode and re-run from the saved snapshots.")
            st.stop()
    st.cache_data.clear()
    time.sleep(0.2)
    st.rerun()

if not ins:
    ui.empty_state("No analysis yet",
                   "Press <b>Run analysis</b> above. The first run scrapes the 11 Shopify catalogues and review feeds "
                   "(a few minutes); later runs re-use the saved files.")
    st.stop()

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

# ---------- lead insight ----------
lead = [f"We read <b>{n_rev:,}</b> customer reviews across <b>{len(prods)}</b> {ui.esc(cat.replace('_', ' '))} SKUs from "
        f"<b>{len(brands_)}</b> brands."]
if not cs.empty:
    top = cs.iloc[0]
    lead.append(f"The category's #1 complaint is <span class='hl'><b>{ui.esc(top['label'].lower())}</b></span> — "
                f"<b>{top['share_of_complaints'] * 100:.0f}%</b> of all complaints.")
if not brand_rt.empty and home_brand() in set(brand_rt["brand"]):
    rank = int(brand_rt.index[brand_rt["brand"] == home_brand()][0]) + 1
    avg = float(brand_rt.loc[brand_rt["brand"] == home_brand(), "avg"].iloc[0])
    lead.append(f"{HOME} ranks <b>#{rank} of {len(brand_rt)}</b> on collected rating (<b>{avg:.2f}★</b>)")
    if ins.get("category_rivals"):
        r0 = ins["category_rivals"][0]
        lead[-1] += f"; its closest rival is <b>{ui.esc(r0['name'])}</b> (match {r0['avg_match']:.2f})."
    else:
        lead[-1] += "."

left, right = st.columns([0.64, 0.36], gap="large")
left.markdown(f'<div class="lead">{" ".join(lead)}</div>', unsafe_allow_html=True)
facts = [("Dot & Key SKUs in category", f"{len(home)}"), ("Products in all catalogues", f"{sum(ins['catalog_counts'].values()):,}"),
         ("Reviews labelled by", lab.get("engine", "?")), ("Snapshot", ui.snapshot_date() or "—"),
         ("Last run", f"{ins['generated_at']} · {ins['elapsed_s']:.0f} s")]
right.markdown('<div class="facts">' + "".join(f'<div class="r"><span class="k">{ui.esc(k)}</span><span class="v">{ui.esc(v)}</span></div>'
                                                for k, v in facts) + "</div>", unsafe_allow_html=True)

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

# ---------- strategy + launches ----------
left, right = st.columns([0.56, 0.44], gap="large")
with left:
    s = ins.get("strategy", {})
    ui.section("Strategy in one paragraph", ui.engine_badge(s.get("engine")))
    st.markdown(f'<div style="font-size:14px;line-height:1.55">{ui.esc(s.get("summary", ""))}</div>', unsafe_allow_html=True)
    sw = s.get("swot", {})
    for k, cls, name in (("strengths", "s", "Top strength"), ("weaknesses", "w", "Top weakness")):
        if sw.get(k):
            st.markdown(f'<div class="swot {cls}" style="margin-top:8px"><div class="eyebrow">{name}</div>'
                        f'{ui.esc(sw[k][0].get("text", ""))}</div>', unsafe_allow_html=True)
with right:
    la = [l for l in ins.get("launches", []) if l["in_category"]][:8]
    ui.section("Recent category launches", "last 90 days · Shopify created_at")
    if not la:
        st.markdown('<div class="meta">No category launches in the last 90 days.</div>', unsafe_allow_html=True)
    for l in la:
        st.markdown(f'<div class="row"><span class="k">{ui.esc(brand_name(l["brand"]))}</span>'
                    f'<span style="flex:1">{ui.esc(ui.friendly_name(l["title"], 54))}</span>'
                    f'<span class="meta num">{ui.inr(l["price"])} · {str(l["created_at"])[:10]}</span></div>',
                    unsafe_allow_html=True)

ui.next_step("product", "Open product deep-dive",
             f"See how <b>{ui.esc(ui.friendly_name(ui.current_product(ins)['title'], 50))}</b> compares with its five closest rivals, topic by topic.")
