import json

import pandas as pd
import streamlit as st

from app import ui
from core import costs
from core.collect.reviews import coverage
from core.config import INSIGHTS, brand_name

ui.setup("Accuracy & method", "Trust & settings")
ins = ui.need_insights()
ls = ins.get("label_stats", {})

ui.section("AI labelling accuracy", "against a hand-labelled gold set", first=True)
ev = INSIGHTS / f"eval_{ins['category']}.json"
if ev.exists():
    e = json.loads(ev.read_text())
    st.markdown(f'<div class="lead" style="max-width:80ch">On <b>{e["n_reviews"]}</b> hand-labelled reviews the '
                f'{ui.esc(e["engine"])} labeller finds topics with F1 <b>{e["topic_f1"]:.2f}</b> (precision {e["topic_precision"]:.2f}, '
                f'recall {e["topic_recall"]:.2f}) and agrees on sentiment <b>{e["sentiment_agreement"]:.0%}</b> of the time.</div>',
                unsafe_allow_html=True)
    pt = ui.df(e.get("per_topic"))
    if not pt.empty:
        st.dataframe(pt, hide_index=True, width="stretch")
else:
    ui.empty_state("No gold set yet",
                   f"Label 30 reviews on <b>Label reviews</b>, then run <code>python scripts/eval_accuracy.py --category "
                   f"{ui.esc(ins['category'])}</code> to measure precision, recall and sentiment agreement.", "label", "Label reviews")
st.markdown(f'<div class="meta" style="margin-top:8px">Labeller: <b>{ui.esc(ls.get("engine", "?"))}</b> · '
            f'<span class="num">{ls.get("labelled", 0):,}</span> labels kept · dropped <span class="num">{ls.get("dropped_bad_quote", 0)}</span> '
            f'whose quote was not an exact substring · <span class="num">{ls.get("dropped_bad_topic", 0)}</span> with unknown topics · '
            f'<span class="num">{ls.get("llm_errors", 0)}</span> LLM batch errors (fell back to lexicon)</div>', unsafe_allow_html=True)

ui.section("Review coverage", "what we could and couldn't read")
cov = ui.df(list(coverage().values()))
if not cov.empty:
    ok = int(cov["available"].astype(bool).sum())
    ui.takeaway(f"<b>{ok}</b> of {len(cov)} products have a public review feed; <b>{int(cov['collected'].sum()):,}</b> reviews collected.")
    cov["shown_avg"] = pd.to_numeric(cov["shown_avg"], errors="coerce")
    cov["brand"] = cov["brand"].map(brand_name)
    cov["title"] = cov["title"].map(lambda t: ui.friendly_name(t, 60))
    st.dataframe(cov[["brand", "title", "provider", "available", "collected", "shown_count", "shown_avg", "reason"]], hide_index=True,
                 width="stretch",
                 column_config={"available": st.column_config.CheckboxColumn("feed"), "shown_count": st.column_config.NumberColumn("on store", format="localized"),
                                "shown_avg": st.column_config.NumberColumn("store ★", format="%.1f")})
    ui.caption("Reviews are read from each store's own public review widget feed (Judge.me, Yotpo, Nector, Fera). Never generated.")

ui.section("Cost log")
ce = ui.df(costs.entries())
if ce.empty:
    st.markdown('<div class="meta">No paid calls logged yet.</div>', unsafe_allow_html=True)
else:
    ce["time"] = pd.to_datetime(ce["ts"], unit="s").dt.strftime("%H:%M:%S")
    g = ce[~ce["cached"].astype(bool)].groupby("provider")[["est_usd"]].sum().reset_index()
    ui.takeaway(f"Total <b>${g['est_usd'].sum():.3f}</b> (≈₹{g['est_usd'].sum() * costs.INR_PER_USD:,.0f}) · "
                + " · ".join(f"{ui.esc(r.provider)} ${r.est_usd:.3f}" for r in g.itertuples())
                + f" · {int(ce['cached'].astype(bool).sum())} cached calls cost nothing")
    st.dataframe(ce[["time", "provider", "model", "purpose", "est_usd", "units", "cached"]].iloc[::-1].head(200), hide_index=True,
                 width="stretch", column_config={"est_usd": st.column_config.NumberColumn("est $", format="%.4f")})

ui.section("Method")
st.markdown("""
- **Catalogue** — every brand's public Shopify `/products.json`, paged, saved as dated snapshots. Size parsed from variant/title (1 g ≈ 1 ml for ₹/ml).
- **Specs** — deterministic regex/lexicon extractor + one cached LLM call per product; regex-found SPF/PA always win; unknown = null.
- **Rivals** — `0.35·format + 0.25·ingredient & claim Jaccard + 0.20·price-band closeness + 0.20·skin-type overlap`, one product per brand.
- **Reviews** — LLM labels topic × sentiment in batches of 40 with a quote; quotes must be exact substrings (checked in code). All statistics in pandas.
- **Strategy** — the LLM sees only metric ids + review ids; every point must cite ≥ 1 valid id or it is dropped.
- **Creative** — scene-only backgrounds (no product, no text) → real packshot cut-out → text laid out in code. The claims checker gates every line.
- **Marketplace snapshot** — Nykaa / Flipkart / Amazon listing facts collected via Gemini + Google Search; shown with links, never mixed into review statistics.
- **Estimates** — opportunity score and the review-velocity forecast are labelled *estimate*; launch trends use `created_at` (approximate).
""")
