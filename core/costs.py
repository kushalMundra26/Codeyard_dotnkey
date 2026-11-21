"""Cost ledger + budget guard for every paid call (Anthropic, Gemini, Higgsfield, Sarvam, Cloudflare)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from .config import DATA, dry_run, env_float

LEDGER = DATA / "cost_log.jsonl"

# USD per 1M tokens (input, output) — from Anthropic's published pricing table (2026-11).
ANTHROPIC_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-2": (8.00, 40.00),
}
INR_PER_USD = 84.0


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class CostEntry:
    provider: str
    model: str
    purpose: str
    est_usd: float
    actual_usd: float | None = None
    units: str = ""
    cached: bool = False
    dry_run: bool = False


def log(entry: CostEntry) -> None:
    rec = entry.__dict__ | {"ts": time.time()}
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def entries() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def spent(provider: str) -> float:
    return sum((e.get("actual_usd") if e.get("actual_usd") is not None else e.get("est_usd", 0)) or 0
               for e in entries() if e.get("provider") == provider and not e.get("cached") and not e.get("dry_run"))


def total_usd() -> float:
    return sum((e.get("actual_usd") if e.get("actual_usd") is not None else e.get("est_usd", 0)) or 0
               for e in entries() if not e.get("cached") and not e.get("dry_run"))


def guard_higgsfield(est_usd: float) -> None:
    cap = env_float("HIGGSFIELD_MAX_USD", 5.0)
    if spent("higgsfield") + est_usd > cap:
        raise BudgetExceeded(
            f"Higgsfield budget cap ${cap:.2f} would be exceeded "
            f"(spent ${spent('higgsfield'):.2f} + this ${est_usd:.2f})."
        )


def anthropic_cost(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = ANTHROPIC_PRICES.get(model, (4.0, 20.0))
    return in_tok / 1e6 * pin + out_tok / 1e6 * pout


def is_dry() -> bool:
    return dry_run()
