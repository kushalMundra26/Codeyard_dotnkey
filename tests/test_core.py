import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.collect.catalog import diff_snapshots, normalise, parse_pack, parse_size
from core.creative import claims
from core.enrich import rule_spec
from core.evidence import EvidenceIndex, validate
from core.reviews_intel import lexicon_label, verify_quote
from core.rivals import score, top_rivals


def test_parse_size():
    assert parse_size("Watermelon Sunscreen 50g") == (50.0, "g")
    assert parse_size("", "Gel 80 ML pack") == (80.0, "ml")
    assert parse_size("no size here") == (None, None)
    assert parse_size("SPF 50 cream 30 gm") == (30.0, "g")


def test_parse_pack():
    assert parse_pack("Sunscreen - Pack of 2") == 2
    assert parse_pack("Sunscreen Duo") == 2
    assert parse_pack("Single sunscreen") == 1


def test_normalise_price_per_ml():
    p = {"id": 1, "title": "Cooling Sunscreen 50g", "handle": "x", "product_type": "Sunscreen", "tags": [],
         "variants": [{"price": "495.00", "compare_at_price": "550.00", "title": "50g", "available": True}],
         "images": [{"src": "https://cdn.shopify.com/a.jpg"}], "options": [], "body_html": "<p>SPF 50 PA++++</p>",
         "created_at": "2026-01-01T00:00:00+05:30"}
    r = normalise("dotandkey", p)
    assert r["price"] == 495 and r["mrp"] == 550 and r["price_per_ml"] == 9.9 and r["discount_pct"] == 10.0


def test_diff_snapshots():
    old = [{"id": 1, "title": "A", "handle": "a", "variants": [{"price": "100", "available": True}]},
           {"id": 2, "title": "B", "handle": "b", "variants": [{"price": "200", "available": True}]}]
    new = [{"id": 1, "title": "A", "handle": "a", "variants": [{"price": "120", "compare_at_price": "150", "available": False}]},
           {"id": 3, "title": "C", "handle": "c", "variants": [{"price": "300"}]}]
    d = diff_snapshots(old, new)
    assert [x["id"] for x in d["launches"]] == ["3"]
    assert [x["id"] for x in d["removed"]] == ["2"]
    assert d["price_changes"][0]["new"] == 120 and d["price_changes"][0]["change_pct"] == 20.0
    assert d["new_discounts"][0]["discount_pct"] == 20.0
    assert d["stockouts"][0]["id"] == "1"


def _p(brand, spf, fmt, ings, skin, price, ppm):
    return {"brand": brand, "price": price, "price_per_ml": ppm,
            "spec": {"spf": spf, "format": fmt, "key_ingredients": ings, "claims": [], "skin_types": skin, "tinted": None}}


def test_rival_scoring_prefers_similar():
    me = _p("dotandkey", 50, "gel", ["niacinamide", "watermelon"], ["oily"], 495, 9.9)
    close = _p("a", 50, "gel", ["niacinamide"], ["oily"], 499, 10.0)
    far = _p("b", 30, "stick", ["zinc oxide"], ["dry"], 1200, 40.0)
    assert score(me, close)["score"] > score(me, far)["score"]
    assert "Same SPF 50" in score(me, close)["reason"]
    top = top_rivals(me, [me, close, far], k=1)
    assert top[0]["brand"] == "a"


def test_evidence_validator_drops_unbacked():
    idx = EvidenceIndex(reviews={"r:dk:1": {"label": "x"}}, metrics={"m:complaint:white_cast": {"label": "y"}})
    items = [{"text": "ok", "evidence": ["r:dk:1"]}, {"text": "made up", "evidence": ["r:dk:999"]},
             {"text": "none", "evidence": []}, {"text": "metric", "evidence": ["m:complaint:white_cast", "bogus"]}]
    kept, dropped = validate(items, idx)
    assert [k["text"] for k in kept] == ["ok", "metric"]
    assert kept[1]["evidence"] == ["m:complaint:white_cast"]
    assert len(dropped) == 2


def test_claims_checker_blocks():
    spec = {"spf": 50, "pa": "PA++++"}
    own = {"white_cast": {"net": -0.4, "n": 12, "review_ids": ["r:dk:1"]}, "texture": {"net": 0.8, "n": 40, "review_ids": []}}
    assert claims.check("Zero white cast", spec, own)["verdict"] == "block"
    assert claims.check("SPF 60 protection", spec, own)["verdict"] == "block"
    assert claims.check("Cures acne", spec, own)["verdict"] == "block"
    assert claims.check("Better than Minimalist", spec, own)["verdict"] == "block"
    assert claims.check("Lightweight texture, SPF 50", spec, own)["verdict"] == "ok"


def test_lexicon_and_quote_check():
    r = {"review_id": "r:x:1", "rating": 5, "title": "", "body": "No white cast at all. Smells lovely!"}
    labs = {l["topic"]: l for l in lexicon_label(r, "sunscreen")}
    assert labs["white_cast"]["sentiment"] == 1
    assert verify_quote(r, labs["white_cast"]["quote"])
    assert not verify_quote(r, "this text is not in the review")


def test_rule_spec():
    row = {"title": "Watermelon Cooling Sunscreen SPF 50 PA++++ Gel", "product_type": "Sunscreen", "tags": [],
           "body_text": "With niacinamide and hyaluronic acid. No white cast. For oily skin."}
    s = rule_spec(row)
    assert s["spf"] == 50 and s["pa"] == "PA++++" and s["format"] == "gel"
    assert "niacinamide" in s["key_ingredients"] and "no white cast" in s["claims"] and "oily" in s["skin_types"]
