"""FastAPI — thin wrapper over core/ for n8n, the MCP server and Telegram approval links.
Auth: header `X-API-Token: $API_TOKEN` (or ?token= for Telegram link buttons)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from core import pipeline  # noqa: E402
from core.config import OUTPUTS, env  # noqa: E402
from core.providers import telegram  # noqa: E402

app = FastAPI(title="SignalStudio API", version="1.0")


def auth(x_api_token: str | None = Header(None), token: str | None = Query(None)):
    expected = env("API_TOKEN")
    if expected and (x_api_token or token) != expected:
        raise HTTPException(401, "bad token")


class RunReq(BaseModel):
    category: str = "sunscreen"
    live: bool = False


class CampaignReq(BaseModel):
    category: str = "sunscreen"
    product: str | None = None
    persona: str | None = None
    languages: list[str] | None = None
    make_video: bool = True


class RegionalReq(BaseModel):
    languages: list[str] | None = None


@app.get("/api/health")
def health():
    from core import llm
    from core.providers import higgsfield, sarvam
    return {"ok": True, "llm": llm.provider(), "sarvam": sarvam.available(), "higgsfield": higgsfield.available(),
            "telegram": telegram.available(), "categories": pipeline.available_categories()}


@app.post("/api/run", dependencies=[Depends(auth)])
def run(req: RunReq):
    ins = pipeline.run_analysis(req.category, live=req.live)
    return {"category": req.category, "products": len(ins["products"]), "reviews": sum(ins["metrics"]["n_reviews"].values()),
            "elapsed_s": ins["elapsed_s"], "summary": ins["strategy"].get("summary")}


@app.get("/api/radar", dependencies=[Depends(auth)])
def radar(category: str = "sunscreen", days: int = 45):
    r = pipeline.radar(category, days=days)
    launches = r["rival_category_launches"][:5]
    lines = [f"• {l['brand_name']}: {l['title']} (₹{l['price'] or 0:.0f}, {str(l['created_at'])[:10]})" for l in launches]
    ca = r.get("counter_ad") or {}
    text = ("<b>🛰 Launch Radar — " + category + "</b>\n" + (f"{r['n_changes']} catalogue changes since last snapshot\n" if r["n_changes"] else "")
            + ("\n".join(lines) or "No new rival launches.") + (f"\n\n<b>Counter-ad:</b> {ca.get('headline')}\n{ca.get('body')}" if ca else ""))
    return {"has_changes": bool(r["n_changes"] or launches), "n_changes": r["n_changes"], "launches": launches,
            "counter_ad": ca, "telegram_text": text, "link": env("PUBLIC_BASE_URL", "") + "/"}


@app.post("/api/campaign", dependencies=[Depends(auth)])
def campaign(req: CampaignReq):
    ins = pipeline.load_insights(req.category)
    if ins is None:
        raise HTTPException(400, "run analysis first")
    handle = req.product or max((r for r in ins["metrics"]["ratings"] if r["brand"] == "dotandkey"), key=lambda r: r["n"])["handle"]
    c = pipeline.generate_campaign(req.category, handle, req.persona, make_video=req.make_video)
    base = env("PUBLIC_BASE_URL", "http://localhost:8000")
    sq = next((a["path"] for a in c["ads"]["assets"] if a["size"] == "square"), None)
    return {"id": c["id"], "title": c["product"]["title"], "key_message": c["brief"]["key_message"],
            "preview_url": f"{base}/api/campaign/{c['id']}/file/{Path(sq).name}" if sq else None,
            "preview_path": sq, "pack_url": f"{base}/api/campaign/{c['id']}/pack",
            "telegram_caption": f"<b>Approval needed</b>\n{c['product']['title']}\n“{c['brief']['key_message']}”"}


@app.post("/api/campaign/{cid}/regional", dependencies=[Depends(auth)])
def regional(cid: str, req: RegionalReq):
    c = pipeline.regional(cid, req.languages)
    base = env("PUBLIC_BASE_URL", "http://localhost:8000")
    return {"id": cid, "languages": list(c["regional"].keys()), "pack_url": f"{base}/api/campaign/{cid}/pack"}


@app.get("/api/campaign/{cid}/decision", response_class=HTMLResponse, dependencies=[Depends(auth)])
def decision(cid: str, bg: BackgroundTasks, d: str = "approve"):
    """Fallback approval endpoint used when n8n isn't running (Telegram link buttons point here)."""
    c = pipeline.load_campaign(cid)
    if not c:
        raise HTTPException(404)
    c["status"] = "approved" if d == "approve" else "rejected"
    pipeline.save_campaign(c)
    if d == "approve":
        def work():
            try:
                pipeline.regional(cid)
                if telegram.available():
                    z = next(iter(sorted((OUTPUTS / cid).glob("campaign_pack_*.zip"))), None)
                    telegram.send_message(f"Campaign pack ready ✅ {c['product']['title']}\n{env('PUBLIC_BASE_URL')}/api/campaign/{cid}/pack")
                    if z:
                        telegram.send_file("sendDocument", z, "Campaign pack")
            except Exception as e:
                if telegram.available():
                    telegram.send_message(f"Regional build failed: {e}")
        bg.add_task(work)
    return f"<h3>Campaign {cid}: {c['status']}</h3><p>{'Building Hindi + Bengali versions…' if d == 'approve' else ''}</p>"


@app.post("/api/counter-ad", dependencies=[Depends(auth)])
def counter_ad(category: str = "sunscreen"):
    return pipeline.radar(category).get("counter_ad") or {}


@app.get("/api/campaign/{cid}/pack")
def pack_file(cid: str):
    z = next(iter(sorted((OUTPUTS / cid).glob("campaign_pack_*.zip"))), None)
    if not z:
        raise HTTPException(404)
    return FileResponse(z, filename=z.name)


@app.get("/api/campaign/{cid}/file/{name}")
def campaign_file(cid: str, name: str):
    p = (OUTPUTS / cid / name).resolve()
    if not str(p).startswith(str((OUTPUTS / cid).resolve())) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)
