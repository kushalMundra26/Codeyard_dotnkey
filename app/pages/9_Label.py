import json
import random

import pandas as pd
import streamlit as st

from app import ui
from core.config import LABELS, brand_name, category_cfg

ui.setup("Label reviews", "Trust & settings · gold set")
ins = ui.need_insights()
cat = ins["category"]
topics = category_cfg(cat)["topics"]
gold_p = LABELS / f"gold_{cat}.json"
gold = json.loads(gold_p.read_text()) if gold_p.exists() else {}
revs = list(ui.reviews_by_id().values())
rnd = random.Random(42)
sample = [r for r in rnd.sample(revs, min(len(revs), 200)) if len((r.get("body") or "")) > 40][:60]
todo = [r for r in sample if r["review_id"] not in gold]
TARGET = 30

done = len(gold)
st.markdown(f'<div class="lead" style="font-size:16px"><b>{done}</b> of {TARGET} reviews labelled. Mark each topic the review '
            f'talks about as positive, neutral or negative; leave the rest blank.</div>', unsafe_allow_html=True)
st.progress(min(1.0, done / TARGET))
ui.caption("The sample is fixed (seed 42) so the evaluation on Accuracy & method is reproducible.")
if not todo:
    st.success("Sample fully labelled — run scripts/eval_accuracy.py to score the labeller.")
    st.stop()


def save(gold):
    gold_p.write_text(json.dumps(gold, ensure_ascii=False, indent=1))
    rows = [{"review_id": k, "topic": x["topic"], "sentiment": x["sentiment"]} for k, v in gold.items() for x in v] or \
           [{"review_id": k, "topic": "", "sentiment": ""} for k in gold]
    pd.DataFrame(rows).to_csv(LABELS / "gold.csv", index=False)


r = todo[0]
left, right = st.columns([0.5, 0.5], gap="large")
with left:
    ui.section("Review", f"{ui.stars(r.get('rating'))} · {ui.esc(brand_name(r['brand']))}", first=True)
    with st.container(border=True):
        st.markdown(f'<div style="font-weight:700">{ui.esc(r.get("title") or "")}</div>'
                    f'<div style="font-size:15px;line-height:1.55">{ui.esc(r.get("body"))}</div>'
                    f'<div class="meta" style="margin-top:6px"><code>{ui.esc(r["review_id"])}</code></div>', unsafe_allow_html=True)
with right:
    ui.section("Topics", "blank = not mentioned", first=True)
    picked = {}
    for t, cfg in topics.items():
        c1, c2 = st.columns([0.5, 0.5], vertical_alignment="center")
        c1.markdown(f'<div class="small">{ui.esc(cfg["label"])}</div>', unsafe_allow_html=True)
        picked[t] = c2.segmented_control(cfg["label"], ["−1", "0", "+1"], key=f"g_{r['review_id']}_{t}",
                                         label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button("Save & next", type="primary", width="stretch"):
        gold[r["review_id"]] = [{"topic": t, "sentiment": {"+1": 1, "0": 0, "−1": -1}[v]} for t, v in picked.items() if v]
        save(gold)
        st.rerun()
    if c2.button("No topics — skip", width="stretch"):
        gold[r["review_id"]] = []
        save(gold)
        st.rerun()
