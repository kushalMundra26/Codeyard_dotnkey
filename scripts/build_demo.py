"""Build the committed demo state from a REAL run: analysis for sunscreen (+ lip balm if possible),
one campaign per persona for the hero product, regional Hindi + Bengali if Sarvam is configured."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import pipeline  # noqa: E402
from core.config import brand_inputs  # noqa: E402
from core.providers import sarvam  # noqa: E402

if __name__ == "__main__":
    pr = lambda s, d="", f=None: print(f"{s:22s} {d}", flush=True)
    for cat in ("sunscreen", "lip_balm"):
        try:
            ins = pipeline.run_analysis(cat, progress=pr)
        except Exception as e:
            print(cat, "skipped:", e)
            continue
        h = max((r for r in ins["metrics"]["ratings"] if r["brand"] == "dotandkey"), key=lambda r: r["n"])["handle"]
        personas = brand_inputs()["personas"] if cat == "sunscreen" else brand_inputs()["personas"][:1]
        for p in personas:
            c = pipeline.generate_campaign(cat, h, p["id"], make_video=(p is personas[0]), progress=pr)
            if p is personas[0] and sarvam.available():
                pipeline.regional(c["id"], ["hi", "bn"], progress=pr)
    pipeline.radar("sunscreen")
    print("demo built")
