"""Central configuration: paths, env vars, YAML configs."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
MARKET_DIR = ROOT / "data" / "marketplace"

# SIGNALSTUDIO_DATA_DIR lets UI development point at an isolated scratch fixture; the product always uses ./data
DATA = Path(os.environ.get("SIGNALSTUDIO_DATA_DIR") or (ROOT / "data"))
SNAPSHOTS = DATA / "snapshots"
REVIEWS = DATA / "reviews"
ENRICHED = DATA / "enriched"
INSIGHTS = DATA / "insights"
OUTPUTS = DATA / "outputs"
LABELS = DATA / "labels"
CACHE = DATA / "cache"
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
CONFIG = ROOT / "config"

for _p in (MARKET_DIR, SNAPSHOTS, REVIEWS, ENRICHED, INSIGHTS, OUTPUTS, LABELS, CACHE, FONTS):
    _p.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 SignalStudio/1.0"
)


def env(name: str, default: str = "") -> str:
    """Read env at call time (so the Streamlit sidebar / .env edits are picked up)."""
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def env_float(name: str, default: float) -> float:
    try:
        return float(env(name, str(default)))
    except ValueError:
        return default


def dry_run() -> bool:
    return env("DRY_RUN", "0") in ("1", "true", "yes")


def _yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def brands() -> dict:
    return _yaml("brands.yaml")


def brand_list() -> list[str]:
    return list(brands()["brands"].keys())


def brand_name(key: str) -> str:
    return brands()["brands"].get(key, {}).get("name", key)


def brand_color(key: str) -> str:
    return brands()["brands"].get(key, {}).get("color", "#64686E")


def home_brand() -> str:
    return brands()["home"]


@lru_cache(maxsize=1)
def topics_cfg() -> dict:
    return _yaml("topics.yaml")


def categories() -> list[str]:
    return list(topics_cfg()["categories"].keys())


def category_cfg(cat: str) -> dict:
    return topics_cfg()["categories"][cat]


def topic_labels(cat: str) -> dict[str, str]:
    return {k: v["label"] for k, v in category_cfg(cat)["topics"].items()}


def brand_inputs() -> dict:
    return _yaml("brand_inputs.yaml")


def save_brand_inputs(d: dict) -> None:
    with open(CONFIG / "brand_inputs.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
