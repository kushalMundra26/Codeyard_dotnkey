"""Compare hand-labelled gold reviews (data/labels/gold_<cat>.json, built on the 'Label reviews' page)
against the pipeline's labels. Reports topic F1 (micro) and sentiment agreement separately."""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import INSIGHTS, LABELS  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="sunscreen")
    a = ap.parse_args()
    gold = json.loads((LABELS / f"gold_{a.category}.json").read_text())
    pred_store = json.loads((INSIGHTS / f"labels_{a.category}.json").read_text())
    tp = fp = fn = 0
    agree = both = 0
    per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    engines = set()
    for rid, g in gold.items():
        p = pred_store.get(rid, {"topics": [], "engine": "missing"})
        engines.add(p["engine"])
        gt = {x["topic"]: x["sentiment"] for x in g}
        pt = {x["topic"]: x["sentiment"] for x in p["topics"]}
        for t in gt.keys() | pt.keys():
            if t in gt and t in pt:
                tp += 1; per[t]["tp"] += 1; both += 1; agree += int(gt[t] == pt[t])
            elif t in pt:
                fp += 1; per[t]["fp"] += 1
            else:
                fn += 1; per[t]["fn"] += 1
    P = tp / max(1, tp + fp); R = tp / max(1, tp + fn); F = 2 * P * R / max(1e-9, P + R)
    out = {"n_reviews": len(gold), "topic_precision": round(P, 3), "topic_recall": round(R, 3), "topic_f1": round(F, 3),
           "sentiment_agreement": round(agree / max(1, both), 3), "engine": "/".join(sorted(engines)),
           "per_topic": [{"topic": t, **v, "f1": round(2 * v["tp"] / max(1, 2 * v["tp"] + v["fp"] + v["fn"]), 3)} for t, v in sorted(per.items())]}
    (INSIGHTS / f"eval_{a.category}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "per_topic"}, indent=1))
