"""One-click campaign pack: ZIP with images, copy, A+ text, scripts, MP4s and a one-page brief (Markdown)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


def brief_markdown(c: dict) -> str:
    b = c["brief"]
    L = [f"# Campaign brief — {c['product']['title']}", "", f"**Persona:** {b['persona']}  ", f"**Tone:** {b['tone']}", "",
         f"## Insight\n{b['insight']}", f"## Key message\n**{b['key_message']}**", "## Proof points"]
    L += [f"- {p['text']}  _(evidence: {', '.join(p['evidence'])})_" for p in b["proof_points"]]
    L += ["", "## Ads"]
    for v in c["ads"]["variants"]:
        L.append(f"- **{v['headline']}** — {v['subline']} [{v['cta']}]  \n  _Why:_ {v['why']}  \n  _Claims:_ {v.get('claims', {}).get('verdict', 'n/a')}")
    e = c["ecom"]
    L += ["", "## Product description", e["product_description"], "", "## Amazon title", e["amazon_title"], "", "## Bullets"]
    L += [f"- {x}" for x in e["bullets"]]
    L += ["", "## A+ modules"] + [f"### {m['title']}\n{m['body']}\n_Image:_ {m['image_idea']}" for m in e["aplus"]]
    L += ["", "## SEO keywords (customers' own words)", ", ".join(e["seo_keywords"])]
    for k in ("script15", "script30"):
        s = c.get(k)
        if s:
            L += ["", f"## Script — {s['duration_s']}s: {s['title']}", f"_Hook:_ {s['hook']}", "",
                  "| Time | Visual | On-screen | Voiceover |", "|---|---|---|---|"]
            L += [f"| {f['t_start']}–{f['t_end']}s | {f['visual']} | {f['on_screen_text']} | {f['voiceover']} |" for f in s["frames"]]
            L += ["", f"**Video concept:** {s['video_concept']}  ", f"**Music:** {s['music_mood']}"]
    return "\n".join(L)


def build_pack(campaign_dir: Path, campaign: dict) -> Path:
    md = campaign_dir / "brief.md"
    md.write_text(brief_markdown(campaign), encoding="utf-8")
    z = campaign_dir / f"campaign_pack_{campaign['id']}.zip"
    # what a marketer ships: the chosen ad in 3 sizes, regional ads, final videos, brief + copy (no intermediates)
    keep = {Path(a["path"]).name for a in campaign["ads"].get("assets", [])}
    keep |= {Path(a["path"]).name for r in campaign.get("regional", {}).values() for a in r.get("ads", [])}
    keep |= {Path(v["path"]).name for v in campaign.get("videos", []) if v.get("path")}
    keep |= {Path(r["video"]["path"]).name for r in campaign.get("regional", {}).values() if (r.get("video") or {}).get("path")}
    if (campaign.get("hero") or {}).get("path"):
        keep.add(Path(campaign["hero"]["path"]).name)
    keep |= {"brief.md", "campaign.json"}
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:  # jpg/mp4 are already compressed
        for name in sorted(keep):
            p = campaign_dir / name
            if p.exists():
                zf.write(p, name)
        zf.writestr("copy.json", json.dumps({k: campaign[k] for k in ("ecom", "ads", "brief")}, ensure_ascii=False, indent=1))
    return z
