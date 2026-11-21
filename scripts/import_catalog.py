"""Import catalogue files saved by hand from a browser.

Open https://<store>/products.json?limit=250&page=1 in your browser, save it (Cmd+S) into data/import/
as <brand>_1.json (page 2 → <brand>_2.json if the store has more than 250 products). Brand keys:
dotandkey minimalist foxtale deconstruct dermaco plum reequil pilgrim aqualogica drsheths fixderma
Then run:  .venv/bin/python scripts/import_catalog.py
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.collect.catalog import save_snapshot  # noqa: E402
from core.config import DATA, brand_list  # noqa: E402

if __name__ == "__main__":
    pages = defaultdict(list)
    for p in sorted((DATA / "import").glob("*.json")):
        m = re.match(r"([a-z]+)_?(\d*)$", p.stem)
        if not m or m.group(1) not in brand_list():
            print(f"skip {p.name}: name it <brand>_<page>.json with brand in {brand_list()}")
            continue
        try:
            prods = json.loads(p.read_text(encoding="utf-8"))["products"]
        except Exception as e:
            print(f"skip {p.name}: not a products.json file ({e})")
            continue
        pages[m.group(1)].extend(prods)
    for b, prods in pages.items():
        uniq = list({str(x["id"]): x for x in prods}.values())
        print(f"{b}: {len(uniq)} products → {save_snapshot(b, uniq).name}")
    missing = [b for b in brand_list() if b not in pages]
    if missing:
        print("not imported (collector may still fetch them):", missing)
