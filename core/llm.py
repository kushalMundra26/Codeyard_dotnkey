"""LLM adapter. One analysis LLM (Anthropic Claude, or Gemini if that's the only key).

Returns validated pydantic objects. Retries once on schema failure. Every call is cached by
hash(provider, model, system, prompt, schema) and logged to the cost ledger.
"""
from __future__ import annotations

import json
import re
from typing import Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from . import cache, costs
from .config import env

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    pass


def provider() -> str:
    p = env("LLM_PROVIDER", "anthropic").lower()
    if p == "anthropic" and env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if p == "gemini" and env("GEMINI_API_KEY"):
        return "gemini"
    # auto-fallback to whichever key exists
    if env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env("GEMINI_API_KEY"):
        return "gemini"
    return "none"


def available() -> bool:
    return provider() != "none"


def model_name(bulk: bool = False) -> str:
    if provider() == "gemini":
        if bulk:  # bulk labelling/enrichment: higher free-tier rate limit, ~2 s latency
            return env("GEMINI_MODEL_BULK", "gemini-3.5-flash-lite")
        return env("GEMINI_MODEL", "gemini-3.5-flash")
    return env("LLM_MODEL_BULK" if bulk else "LLM_MODEL", "claude-opus-5-5")


def _extract_json(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return text[start:]


def _anthropic(system: str, prompt: str, schema: Type[T], model: str, max_tokens: int,
               effort: str, purpose: str, images: list[dict] | None) -> T:
    import anthropic

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"), max_retries=3)
    content: list = []
    for im in images or []:
        content.append({"type": "image", "source": im})
    content.append({"type": "text", "text": prompt})
    kwargs = dict(model=model, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": content}],
                  output_config={"effort": effort})
    try:
        # Structured outputs: client.messages.parse(output_format=<pydantic>) → response.parsed_output
        resp = client.messages.parse(output_format=schema, **kwargs)
        obj = resp.parsed_output
        if obj is None:
            raise ValidationError.from_exception_data(schema.__name__, [])
    except (anthropic.BadRequestError, TypeError, ValidationError):
        # Fallback: plain JSON instructions + local validation (one retry)
        kwargs["system"] = system + "\n\nReturn ONLY JSON matching this schema:\n" + json.dumps(schema.model_json_schema())
        resp = client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            obj = schema.model_validate_json(_extract_json(text))
        except ValidationError as e:
            kwargs["messages"].append({"role": "assistant", "content": text})
            kwargs["messages"].append({"role": "user", "content": f"That JSON failed validation: {e}. Return corrected JSON only."})
            resp = client.messages.create(**kwargs)
            text = "".join(b.text for b in resp.content if b.type == "text")
            obj = schema.model_validate_json(_extract_json(text))
    u = resp.usage
    costs.log(costs.CostEntry("anthropic", model, purpose,
                              est_usd=costs.anthropic_cost(model, u.input_tokens, u.output_tokens),
                              actual_usd=costs.anthropic_cost(model, u.input_tokens, u.output_tokens),
                              units=f"{u.input_tokens} in / {u.output_tokens} out"))
    return obj


def _gemini(system: str, prompt: str, schema: Type[T], model: str, max_tokens: int, purpose: str) -> T:
    # generateContent REST: POST /v1beta/models/{model}:generateContent, header x-goog-api-key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt + "\n\nReturn ONLY JSON matching this JSON schema:\n"
                                                 + json.dumps(schema.model_json_schema())}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": max_tokens},
    }
    last = None
    for _ in range(2):
        for wait in (0, 20, 40, 60):  # free tier: back off on 429 / 503
            if wait:
                import time
                time.sleep(wait)
            r = requests.post(url, json=body, headers={"x-goog-api-key": env("GEMINI_API_KEY")}, timeout=90)
            if r.status_code not in (429, 503):
                break
        if r.status_code != 200:
            raise LLMUnavailable(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        try:
            obj = schema.model_validate_json(_extract_json(text))
            um = data.get("usageMetadata", {})
            costs.log(costs.CostEntry("gemini", model, purpose, est_usd=0.0,
                                      units=f"{um.get('promptTokenCount')} in / {um.get('candidatesTokenCount')} out"))
            return obj
        except ValidationError as e:
            last = e
            body["contents"].append({"role": "model", "parts": [{"text": text}]})
            body["contents"].append({"role": "user", "parts": [{"text": f"Validation failed: {e}. Return corrected JSON only."}]})
    raise last  # type: ignore[misc]


def structured(prompt: str, schema: Type[T], *, system: str = "", purpose: str = "", bulk: bool = False,
               max_tokens: int = 16000, effort: str = "medium", images: list[dict] | None = None,
               use_cache: bool = True) -> T:
    """Call the analysis LLM and return a validated `schema` instance."""
    prov = provider()
    if prov == "none":
        raise LLMUnavailable("No LLM key configured (ANTHROPIC_API_KEY or GEMINI_API_KEY).")
    model = model_name(bulk)
    ck = {"prov": prov, "model": model, "system": system, "prompt": prompt, "schema": schema.__name__,
          "imgs": [i.get("url") or str(len(i.get("data", ""))) for i in images or []]}
    if use_cache:
        hit = cache.get("llm", ck)
        if hit is not None:
            costs.log(costs.CostEntry(prov, model, purpose, est_usd=0.0, cached=True))
            return schema.model_validate(hit)
    if costs.is_dry():
        raise LLMUnavailable("DRY_RUN=1 — LLM call skipped.")
    if prov == "anthropic":
        obj = _anthropic(system, prompt, schema, model, max_tokens, effort, purpose, images)
    else:
        try:
            obj = _gemini(system, prompt, schema, model, max_tokens, purpose)
        except Exception:
            fb = model_name(bulk=True)
            if fb == model:
                raise
            obj = _gemini(system, prompt, schema, fb, max_tokens, purpose + ":fallback")  # e.g. Flash → Flash-Lite
    cache.put("llm", ck, obj.model_dump())
    return obj
