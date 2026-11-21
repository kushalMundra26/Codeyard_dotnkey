"""Evidence IDs and validation.

IDs:  r:<brand>:<review_id>   → a stored review
      m:<metric-name>         → a pandas-computed metric in the insights file
      p:<brand>:<handle>      → a catalogue row
Anything an LLM writes must cite ≥1 id that actually exists; otherwise it is dropped.
"""
from __future__ import annotations

from typing import Iterable


class EvidenceIndex:
    def __init__(self, reviews: dict[str, dict] | None = None, metrics: dict[str, dict] | None = None,
                 products: dict[str, dict] | None = None):
        self.reviews = reviews or {}
        self.metrics = metrics or {}
        self.products = products or {}

    def exists(self, eid: str) -> bool:
        eid = eid.strip()
        return eid in self.reviews or eid in self.metrics or eid in self.products

    def resolve(self, eid: str) -> dict | None:
        eid = eid.strip()
        if eid in self.reviews:
            return {"kind": "review", **self.reviews[eid]}
        if eid in self.metrics:
            return {"kind": "metric", **self.metrics[eid]}
        if eid in self.products:
            return {"kind": "product", **self.products[eid]}
        return None

    def clean(self, ids: Iterable[str]) -> list[str]:
        return [i.strip() for i in ids if self.exists(i)]


def validate(items: list, index: EvidenceIndex, field: str = "evidence") -> tuple[list, list]:
    """Keep items (pydantic models or dicts) with ≥1 valid evidence id. Returns (kept, dropped)."""
    kept, dropped = [], []
    for it in items:
        ids = getattr(it, field, None) if not isinstance(it, dict) else it.get(field)
        good = index.clean(ids or [])
        if good:
            if isinstance(it, dict):
                it[field] = good
            else:
                setattr(it, field, good)
            kept.append(it)
        else:
            dropped.append(it)
    return kept, dropped
