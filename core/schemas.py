"""Pydantic schemas for every LLM output. `None` means unknown — never guessed."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProductSpec(BaseModel):
    spf: Optional[int] = Field(None, description="SPF number if stated, else null")
    pa: Optional[str] = Field(None, description="PA rating like 'PA++++' if stated, else null")
    filter_type: Optional[Literal["chemical", "mineral", "hybrid"]] = None
    finish: Optional[Literal["matte", "dewy", "natural", "tinted", "satin"]] = None
    tinted: Optional[bool] = None
    format: Optional[str] = Field(None, description="gel, cream, lotion, fluid, stick, spray, mist, serum, balm, etc.")
    key_ingredients: list[str] = Field(default_factory=list, description="lowercase INCI-ish names, e.g. 'niacinamide'")
    skin_types: list[str] = Field(default_factory=list, description="oily, dry, combination, sensitive, acne-prone, normal, all")
    claims: list[str] = Field(default_factory=list, description="short lowercase claims, e.g. 'no white cast','water resistant'")
    fragrance_free: Optional[bool] = None
    reef_safe: Optional[bool] = None


class TopicLabel(BaseModel):
    topic: str
    sentiment: Literal[-1, 0, 1]
    quote: str = Field(description="exact substring of the review that supports this label")


class ReviewLabel(BaseModel):
    review_id: str
    topics: list[TopicLabel] = Field(default_factory=list)


class ReviewLabelBatch(BaseModel):
    labels: list[ReviewLabel]


class EvidencedPoint(BaseModel):
    text: str
    evidence: list[str] = Field(description="evidence ids: review ids like 'r:dotandkey:123' or metric ids like 'm:...'")


class SWOT(BaseModel):
    strengths: list[EvidencedPoint]
    weaknesses: list[EvidencedPoint]
    opportunities: list[EvidencedPoint]
    threats: list[EvidencedPoint]


class ConceptCard(BaseModel):
    name: str
    one_liner: str
    target_gap: str
    key_ingredients: list[str]
    price_band: str
    why_now: str
    evidence: list[str]


class GTMRow(BaseModel):
    persona: str
    message: str
    channel: str
    city_language: str
    evidence: list[str]


class Improvement(BaseModel):
    change: str
    rationale: str
    evidence: list[str]


class StrategyPack(BaseModel):
    swot: SWOT
    improvements: list[Improvement]
    concepts: list[ConceptCard]
    gtm: list[GTMRow]
    summary: str


class Brief(BaseModel):
    insight: str
    key_message: str
    proof_points: list[EvidencedPoint]
    persona: str
    tone: str
    avoid: list[str]


class AdVariant(BaseModel):
    headline: str = Field(description="max 7 words")
    subline: str = Field(description="max 14 words, the proof point")
    cta: str
    scene_prompt: str = Field(description="background scene only — NO product, NO text, NO people's faces close-up")
    why: str = Field(description="one sentence: which insight this line answers")
    evidence: list[str]


class AdSet(BaseModel):
    variants: list[AdVariant]


class APlusModule(BaseModel):
    title: str
    body: str
    image_idea: str
    evidence: list[str]


class EcomCopy(BaseModel):
    product_description: str
    amazon_title: str
    bullets: list[str]
    aplus: list[APlusModule]
    seo_keywords: list[str]
    evidence: list[str]


class ListingAudit(BaseModel):
    covered_topics: list[str]
    missing_topics: list[str]
    risky_lines: list[str]
    score_rationale: str
    rewritten_description: str
    evidence: list[str]


class Frame(BaseModel):
    t_start: float
    t_end: float
    visual: str
    on_screen_text: str = Field(description="max 6 words")
    voiceover: str
    scene_prompt: str = Field(description="background scene for this frame — no product, no text")


class Script(BaseModel):
    title: str
    duration_s: int
    hook: str
    frames: list[Frame]
    video_concept: str
    music_mood: str
    evidence: list[str]


class ClaimVerdict(BaseModel):
    claim: str
    verdict: Literal["ok", "warn", "block"]
    reason: str


class ClaimReview(BaseModel):
    verdicts: list[ClaimVerdict]


class CounterAd(BaseModel):
    headline: str
    body: str
    rationale: str
