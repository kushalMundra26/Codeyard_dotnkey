"""One-command run: python scripts/run_pipeline.py --category sunscreen [--live] [--campaign]"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import pipeline  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="sunscreen")
    ap.add_argument("--live", action="store_true", help="re-scrape catalogues + review feeds")
    ap.add_argument("--refresh-reviews", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--campaign", action="store_true", help="also generate a campaign for the most-reviewed D&K product")
    ap.add_argument("--persona", default="college_commuter")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    last = [time.time()]

    def prog(step, detail="", frac=None):
        print(f"[{time.time() - last[0]:6.1f}s] {step:22s} {detail}", flush=True)

    ins = pipeline.run_analysis(a.category, live=a.live, use_llm=not a.no_llm, refresh_reviews=a.refresh_reviews, progress=prog)
    print(f"\n{len(ins['products'])} SKUs · {sum(ins['metrics']['n_reviews'].values())} reviews · labeller {ins['label_stats']['engine']}"
          f" · strategy {ins['strategy']['engine']} · {ins['elapsed_s']} s")
    if a.campaign:
        h = max((r for r in ins["metrics"]["ratings"] if r["brand"] == "dotandkey"), key=lambda r: r["n"])["handle"]
        c = pipeline.generate_campaign(a.category, h, a.persona, make_video=not a.no_video, progress=prog)
        print(f"campaign {c['id']} → data/outputs/{c['id']}/  engines: {c['engines']}")
