"""Fetch today's catalogue snapshot for every brand — patiently.
Each round tries each missing brand once; on 429 we wait (default 10 min) and try again later. No evasion."""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.collect.catalog import fetch_catalog, save_snapshot, snapshot_dates, today  # noqa: E402
from core.config import brand_list  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--wait", type=int, default=600, help="seconds between rounds")
    a = ap.parse_args()
    todo = [b for b in brand_list() if today() not in snapshot_dates(b)]
    for rnd in range(a.rounds):
        failed = []
        for b in todo:
            try:
                prods = fetch_catalog(b)
                save_snapshot(b, prods)
                print(f"round {rnd + 1}: {b} OK {len(prods)}", flush=True)
            except Exception as e:
                failed.append(b)
                print(f"round {rnd + 1}: {b} {e}", flush=True)
            time.sleep(5)
        todo = failed
        if not todo:
            print("ALL DONE", flush=True)
            break
        print(f"waiting {a.wait}s; still missing: {todo}", flush=True)
        time.sleep(a.wait)
