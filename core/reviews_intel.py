"""L4 Review intelligence.

Labelling: the LLM labels reviews in batches → {review_id, topics:[{topic, sentiment, quote}]}.
Quotes must be exact substrings of the review (checked in code; bad labels are dropped).
If no LLM key is set, a deterministic lexicon labeller (English + Hinglish) runs instead and the
UI says so. All statistics are computed here with pandas — the LLM never computes numbers.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

import pandas as pd

from . import llm
from .config import INSIGHTS, category_cfg, topic_labels
from .schemas import ReviewLabelBatch

NEG_WORDS = ["not", "no", "never", "zero", "without", "doesn't", "doesnt", "didn't", "didnt", "don't", "dont",
             "isn't", "isnt", "nahi", "nahin", "na ", "bilkul nahi", "free from", "non"]
POS_WORDS = ["love", "loved", "great", "good", "amazing", "awesome", "best", "perfect", "nice", "excellent",
             "light", "lightweight", "smooth", "fresh", "pleasant", "superb", "accha", "acha", "badhiya", "mast",
             "worth", "affordable", "blends", "absorbs", "protects", "glow", "soothing", "happy", "recommend",
             "favourite", "favorite", "holy grail", "works"]
NEG_SENT = ["bad", "worst", "terrible", "hate", "horrible", "disappoint", "waste", "useless", "irritat", "burn",
            "sting", "break out", "breakout", "pimple", "rash", "greasy", "sticky", "heavy", "white cast",
            "expensive", "costly", "overpriced", "leak", "damaged", "pilling", "pills", "itch", "allerg",
            "bekaar", "bakwas", "ghatiya", "kharab", "strong smell", "pungent", "oily", "dark", "not worth",
            "tanned", "returned"]
PROBLEM_TOPICS = {"white_cast", "greasy_sticky", "breakouts", "eye_sting", "makeup_pilling", "darkening"}
UNMET_RE = re.compile(r"[^.!?\n]*(?:\bwish\b|should have|should be|would be better|would have been|if only|"
                      r"hope they|please (?:make|bring|launch|add)|needs? to be|could be|kash|need a|"
                      r"want(?:ed)? a|bigger size|smaller size|more quantity)[^.!?\n]*[.!?]?", re.I)


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?\n])\s+|\n+", text or "") if s.strip()]


def lexicon_label(review: dict, cat: str) -> list[dict]:
    text = f"{review.get('title') or ''}. {review.get('body') or ''}".strip(". ")
    topics = category_cfg(cat)["topics"]
    rating = review.get("rating")
    out = []
    for tkey, t in topics.items():
        for s in sentences(text):
            low = " " + s.lower() + " "
            hit = next((kw for kw in t["keywords"] if kw in low), None)
            if not hit:
                continue
            idx = low.find(hit)
            window = low[max(0, idx - 25): idx]
            negated = any(f"{w} " in window or window.endswith(w) for w in NEG_WORDS) or \
                      hit in ("no cast", "zero cast") or "free" in low[idx: idx + len(hit) + 8]
            if tkey in PROBLEM_TOPICS:
                sent = 1 if negated else -1
            else:
                pos = sum(w in low for w in POS_WORDS)
                neg = sum(w in low for w in NEG_SENT)
                if pos > neg:
                    sent = 1
                elif neg > pos:
                    sent = -1
                elif rating is not None:
                    sent = 1 if rating >= 4 else -1 if rating <= 2 else 0
                else:
                    sent = 0
            out.append({"topic": tkey, "sentiment": sent, "quote": s.strip()})
            break
    return out


SYSTEM = ("You label Indian e-commerce skincare reviews (English, Hindi, Hinglish, Bengali in Latin script). "
          "For each review return the topics it discusses from the allowed list, the sentiment toward that topic "
          "(-1 negative, 0 neutral/mixed, 1 positive) and a SHORT quote that is an EXACT substring copied character-"
          "for-character from the review. A complaint that something is ABSENT is positive (e.g. 'no white cast' → "
          "white_cast +1). Do not invent topics; skip reviews with no topical content (return empty topics).")


def llm_label_batch(batch: list[dict], cat: str) -> dict[str, list[dict]]:
    topics = category_cfg(cat)["topics"]
    allowed = "\n".join(f"- {k}: {v['label']}" for k, v in topics.items())
    items = "\n".join(json.dumps({"review_id": r["review_id"], "rating": r.get("rating"),
                                  "text": f"{r.get('title') or ''} {r.get('body') or ''}".strip()[:1200]},
                                 ensure_ascii=False) for r in batch)
    prompt = f"Allowed topics:\n{allowed}\n\nReviews (JSONL):\n{items}\n\nReturn labels for every review_id."
    res = llm.structured(prompt, ReviewLabelBatch, system=SYSTEM, purpose=f"label:{cat}", bulk=True,
                         max_tokens=12000, effort="low")
    return {l.review_id: [t.model_dump() for t in l.topics] for l in res.labels}


def verify_quote(review: dict, quote: str) -> bool:
    text = f"{review.get('title') or ''} {review.get('body') or ''}"
    q = (quote or "").strip().strip('"').strip()
    return bool(q) and (q in text or q.lower() in text.lower())


def label_reviews(reviews: list[dict], cat: str, use_llm: bool = True, batch_size: int = 40,
                  progress=None) -> tuple[list[dict], dict]:
    """Returns (labels, stats). labels: [{review_id, brand, handle, topic, sentiment, quote, engine}]."""
    path = INSIGHTS / f"labels_{cat}.json"
    store: dict = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    valid_topics = set(category_cfg(cat)["topics"].keys())
    todo = [r for r in reviews if r["review_id"] not in store]
    engine = "llm" if (use_llm and llm.available()) else "lexicon"
    stats = {"engine": engine, "dropped_bad_quote": 0, "dropped_bad_topic": 0, "labelled": 0, "llm_errors": 0}
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    results: dict[int, dict] = {}
    if engine == "llm" and batches:
        # label batches concurrently (each call is independent and cached); 6 workers fits the free tier
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def work(ix):
            try:
                return ix, llm_label_batch(batches[ix], cat), None
            except Exception as e:  # fall back per batch, keep going
                return ix, {}, str(e)[:300]
        done_n = 0
        with ThreadPoolExecutor(max_workers=6) as ex:
            for fut in as_completed([ex.submit(work, i) for i in range(len(batches))]):
                ix, res_, err = fut.result()
                results[ix] = res_
                if err:
                    stats["llm_errors"] += 1
                    stats["last_error"] = err
                done_n += len(batches[ix])
                if progress:
                    progress(done_n, len(todo))
    for bi, batch in enumerate(batches):
        res = results.get(bi, {})
        eng = "llm" if res else "lexicon"
        for r in batch:
            if eng == "llm" and r["review_id"] in res:
                raw = res[r["review_id"]]
            else:
                raw = lexicon_label(r, cat)
                eng_r = "lexicon"
            kept = []
            for t in raw:
                if t["topic"] not in valid_topics:
                    stats["dropped_bad_topic"] += 1
                    continue
                if not verify_quote(r, t["quote"]):
                    stats["dropped_bad_quote"] += 1
                    continue
                kept.append(t)
            store[r["review_id"]] = {"engine": eng if r["review_id"] in res else "lexicon", "topics": kept}
            stats["labelled"] += 1
        path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    flat = []
    by_id = {r["review_id"]: r for r in reviews}
    for rid, v in store.items():
        if rid not in by_id:
            continue
        r = by_id[rid]
        for t in v["topics"]:
            flat.append({"review_id": rid, "brand": r["brand"], "handle": r["handle"], "topic": t["topic"],
                         "sentiment": t["sentiment"], "quote": t["quote"], "engine": v["engine"],
                         "rating": r.get("rating")})
    return flat, stats


# ---------------- pandas metrics ----------------

def metrics(reviews: list[dict], labels: list[dict], cat: str) -> dict:
    tl = topic_labels(cat)
    rv = pd.DataFrame(reviews)
    lb = pd.DataFrame(labels) if labels else pd.DataFrame(columns=["review_id", "brand", "handle", "topic", "sentiment", "quote"])
    out: dict = {"topic_labels": tl}
    if rv.empty:
        return out | {"brand_topic": [], "complaint_share": [], "ratings": [], "unmet": []}
    n_by_brand = rv.groupby("brand")["review_id"].nunique()

    # brand × topic: n mentions, net sentiment, share of brand reviews mentioning it
    bt = []
    if not lb.empty:
        g = lb.groupby(["brand", "topic"])
        for (b, t), d in g:
            n = len(d)
            bt.append({"brand": b, "topic": t, "label": tl.get(t, t), "n": int(n),
                       "net": round(float(d["sentiment"].mean()), 3),
                       "pos": int((d["sentiment"] > 0).sum()), "neg": int((d["sentiment"] < 0).sum()),
                       "share": round(n / int(n_by_brand.get(b, 1)), 3),
                       "review_ids": d["review_id"].tolist()[:200]})
    out["brand_topic"] = bt

    # complaint share by topic (category-wide and per brand)
    cs = []
    if not lb.empty:
        neg = lb[lb["sentiment"] < 0]
        tot = rv["review_id"].nunique()
        for t, d in neg.groupby("topic"):
            cs.append({"topic": t, "label": tl.get(t, t), "neg_reviews": int(d["review_id"].nunique()),
                       "share_of_all_reviews": round(d["review_id"].nunique() / tot, 3)})
        cs.sort(key=lambda x: x["neg_reviews"], reverse=True)
        neg_total = neg["review_id"].nunique() or 1
        for c in cs:
            c["share_of_complaints"] = round(c["neg_reviews"] / neg_total, 3)
    out["complaint_share"] = cs

    # ratings per product (from collected reviews)
    rat = []
    for (b, h), d in rv.groupby(["brand", "handle"]):
        r = d["rating"].dropna()
        rat.append({"brand": b, "handle": h, "n": int(len(d)), "avg_rating": round(float(r.mean()), 2) if len(r) else None,
                    "pct_5": round(float((r == 5).mean()), 3) if len(r) else None,
                    "pct_1_2": round(float((r <= 2).mean()), 3) if len(r) else None})
    out["ratings"] = rat

    # unmet needs miner
    unmet = []
    for r in reviews:
        text = f"{r.get('title') or ''}. {r.get('body') or ''}"
        for m in UNMET_RE.finditer(text):
            s = m.group(0).strip()
            if 12 <= len(s) <= 260:
                unmet.append({"review_id": r["review_id"], "brand": r["brand"], "handle": r["handle"], "quote": s})
    out["unmet"] = unmet[:400]
    out["n_reviews"] = {b: int(n) for b, n in n_by_brand.items()}
    return out


def heatmap_frame(m: dict, min_n: int = 3) -> pd.DataFrame:
    bt = pd.DataFrame(m.get("brand_topic", []))
    if bt.empty:
        return bt
    bt = bt[bt["n"] >= min_n]
    return bt.pivot_table(index="brand", columns="label", values="net")


def brand_topic_lookup(m: dict) -> dict:
    return {(d["brand"], d["topic"]): d for d in m.get("brand_topic", [])}
