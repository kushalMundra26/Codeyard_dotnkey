from pathlib import Path

import requests
import streamlit as st

from app import ui
from core import costs, pipeline
from core.config import OUTPUTS, brand_inputs, env, save_brand_inputs
from core.creative import claims as claims_mod
from core.creative.brief import research_digest
from core.creative.compose import SIZES
from core.providers import higgsfield, sarvam, telegram

ui.setup("Creative studio", "Create",
         step=lambda i: "content" if i and ui.current_campaign(ui.current_product(i)["handle"]) else "brief")
ins = ui.need_insights()
p = ui.current_product(ins)
ctx = ui.context(ins, p["handle"])
bi = brand_inputs()

with st.sidebar:
    with st.expander("Brand inputs", expanded=False):
        tone = st.text_area("Tone of voice", bi["tone"], height=90)
        banned = st.text_area("Banned words (comma-separated)", ", ".join(bi["banned_words"]), height=70)
        langs = st.multiselect("Regional languages", ["hi", "bn", "ta", "mr"], default=bi["languages"],
                               format_func=lambda l: sarvam.LANG_NAMES.get(l, l))
        if st.button("Save brand inputs"):
            bi.update(tone=tone, banned_words=[w.strip() for w in banned.split(",") if w.strip()], languages=langs)
            save_brand_inputs(bi)
            st.success("Saved — applies to the next generation.")

ui.product_header(p, ctx)

# ---------- controls ----------
with st.container(border=True):
    c1, c2, c3, c4, c5 = st.columns([1.5, 1.2, 0.7, 0.55, 0.9], vertical_alignment="bottom")
    persona = c1.selectbox("Persona", bi["personas"], format_func=lambda x: x["name"],
                           help="The brief, ads and scripts are written for this person.")
    eng = c2.selectbox("Background engine", ["auto (free chain)", "cloudflare", "pollinations", "template"],
                       help="Models draw only the background scene. The real product photo and all text are composed in code.")
    make_vid = c3.toggle("Storyboard MP4", value=True)
    seed = c4.number_input("Seed", 1, 999, 7, help="Same seed + inputs → same output (deterministic, cached).")
    pref = None if eng.startswith("auto") else [eng, "template"]
    want_id = pipeline.campaign_id(p["handle"], persona["id"], int(seed))
    exists = any(c["id"] == want_id for c in pipeline.list_campaigns())
    go = c5.button("Regenerate" if exists else "Generate campaign", type="primary", width="stretch", disabled=not ui.can_act())
    st.markdown(f'<div class="meta">{"A campaign for this persona + seed already exists — it is shown below; regenerate to refresh it." if exists else "Generates a brief, 3 ad variants × 3 sizes, e-commerce copy, a listing rewrite, 15 s + 30 s scripts" + (" and a storyboard video" if make_vid else "") + ". Usually under a minute."}</div>',
                unsafe_allow_html=True)

GEN_STEPS = ["Brief", "Ad copy", "E-commerce copy", "Listing audit", "Scripts", "Static ads"] + (["Storyboard video"] if make_vid else [])

if go or st.session_state.pop("autogen", False):
    with st.status("Generating campaign", expanded=True) as status:
        box = st.empty()
        state = {"cur": None, "detail": ""}

        def draw():
            idx = GEN_STEPS.index(state["cur"]) if state["cur"] in GEN_STEPS else (len(GEN_STEPS) if state["cur"] == "Campaign" else -1)
            out = []
            for i, s_ in enumerate(GEN_STEPS):
                if i < idx:
                    out.append(f'<div class="small"><span style="color:var(--mint)">✓</span> {s_}</div>')
                elif i == idx:
                    out.append(f'<div class="small"><b>→ {s_}</b> <span class="meta">{ui.esc(state["detail"])}</span></div>')
                else:
                    out.append(f'<div class="small meta">· {s_}</div>')
            box.markdown("".join(out), unsafe_allow_html=True)

        def prog(step, detail="", frac=None):
            state["cur"], state["detail"] = step, detail
            k = GEN_STEPS.index(step) + 1 if step in GEN_STEPS else len(GEN_STEPS)
            status.update(label=f"Step {k} of {len(GEN_STEPS)} · {step} — {detail}", expanded=True)
            draw()
        try:
            camp = pipeline.generate_campaign(ins["category"], p["handle"], persona["id"], make_video=make_vid, seed=int(seed),
                                              progress=prog, image_pref=pref)
            status.update(label=f"Campaign ready in {camp['elapsed_s']} s", state="complete", expanded=False)
            st.session_state["campaign_id"] = camp["id"]
            ok = True
        except Exception as e:
            ok = False
            status.update(label="Generation failed", state="error")
            st.error(f"{e}")
    if ok:
        st.rerun()

cid = want_id if exists else None
camp = pipeline.load_campaign(cid) if cid else ui.current_campaign(p["handle"])
if camp and camp["persona"]["id"] != persona["id"] and not exists:
    st.markdown(f'<div class="meta">Showing the latest campaign for this product (persona <b>{ui.esc(camp["persona"]["name"])}</b>). '
                'Press Generate to write one for the selected persona.</div>', unsafe_allow_html=True)

left, right = st.columns([0.55, 0.45], gap="large")

# ---------- LEFT: research → brief ----------
with left:
    if camp:
        b = camp["brief"]
        ui.section("Brief", f'{ui.esc(b["persona"])} · {ui.engine_badge(camp["engines"].get("brief"))}', first=True)
        st.markdown(f'<div class="eyebrow">Insight</div><div style="font-size:14px;margin-bottom:8px">{ui.esc(b["insight"])}</div>'
                    f'<div class="eyebrow">Key message</div><div style="font-family:Fraunces,Georgia,serif;font-size:22px;'
                    f'font-weight:600;line-height:1.25;margin:2px 0 10px 0">“{ui.esc(b["key_message"])}”</div>'
                    f'<div class="eyebrow">Proof points · click n for the reviews</div>', unsafe_allow_html=True)
        ledger = st.container(key="ledger_pp")
        for i, pp in enumerate(b["proof_points"]):
            c_a, c_b = ledger.columns([0.84, 0.16], vertical_alignment="center")
            c_a.markdown(f'<div class="small" style="padding:3px 0;border-bottom:1px solid var(--rule)">{ui.esc(pp["text"])}</div>',
                         unsafe_allow_html=True)
            with c_b:
                rids, labs, _ = ui.resolve_evidence(ins, pp["evidence"])
                if rids:
                    ui.evidence_count_button(len(rids), pp["text"][:70], rids, f"pp_{i}", labels=labs)
                else:
                    st.markdown(f'<span class="meta small">{ui.esc(" ".join(pp["evidence"])[:30])}</span>', unsafe_allow_html=True)
        if b.get("avoid"):
            st.markdown('<div class="meta" style="margin-top:6px">Never say: ' + ", ".join(ui.esc(a) for a in b["avoid"][:8]) + "</div>",
                        unsafe_allow_html=True)
    else:
        ui.section("Brief", "not written yet", first=True)
        ui.empty_state("No campaign for this product yet",
                       "Pick a persona above and press <b>Generate campaign</b>. The brief is written only from the customer "
                       "signal below — every proof point links to the reviews it came from.")

    ui.section("Customer signal", "this product · net sentiment")
    ledger = st.container(key="ledger_sig")
    for t in ctx["own_topics"][:7]:
        c1, c2, c3 = ledger.columns([0.46, 0.36, 0.18], vertical_alignment="center", gap="small")
        c1.markdown(f'<div class="small">{ui.esc(t["label"])} <span class="meta num">{t["net"]:+.2f}</span></div>', unsafe_allow_html=True)
        c2.markdown(ui.div_bar(t["net"]), unsafe_allow_html=True)
        with c3:
            ui.evidence_count_button(t["n"], t["label"], t["review_ids"], f"sig_{t['topic']}",
                                     labels=[l for l in ins["labels"] if l["handle"] == p["handle"] and l["topic"] == t["topic"]])
    for q in ctx["quotes"][:3]:
        st.markdown(ui.quote_html(q, show_brand=False), unsafe_allow_html=True)

    ui.section("Rivals the brief positions against")
    for r in ctx["rivals"]:
        st.markdown(f'<div class="row"><span class="k">{ui.esc(r["brand_name"])}</span><span class="num small" style="min-width:36px">'
                    f'{r["match"]["score"]:.2f}</span><span class="small meta" style="flex:1">{ui.esc(r["match"]["reason"])}</span></div>',
                    unsafe_allow_html=True)
    with st.expander("Exact research context sent to the model"):
        st.code(research_digest(ctx), language=None)

# ---------- RIGHT: content ----------
with right:
    if not camp:
        ui.section("Content", "", first=True)
        ui.empty_state("Content appears here",
                       "Ads (3 variants × feed, story, A+), Amazon title + bullets + A+ modules, 15 s and 30 s scripts, a storyboard "
                       "MP4, claims checks and regional versions — each traceable to the brief on the left.")
        st.stop()
    cdir = OUTPUTS / camp["id"]
    tabs = st.tabs(["Ads", "E-commerce", "Script & video", "Claims", "Regional", "Hero clip"])
    with tabs[0]:
        variants = camp["ads"]["variants"]
        ok_vs = [x for x in variants if x["claims"]["verdict"] != "block"] or variants
        n_block = sum(1 for v in variants if v["claims"]["verdict"] == "block")
        st.markdown(f'<div class="meta">{len(variants)} variants · {n_block} blocked by the claims checker · '
                    f'story 1080×1920 · feed 1080×1080 · A+ 970×600 · background {ui.esc(", ".join(sorted({a["engine"] for a in camp["ads"]["assets"]})) or "—")} · '
                    f'{ui.engine_badge(camp["engines"].get("ads"))}</div>', unsafe_allow_html=True)
        ORDER = ["story", "square", "aplus"]
        LABEL = {"story": "9:16 story", "square": "1:1 feed", "aplus": "A+ banner"}
        for vi, v in enumerate(variants):
            st.markdown('<div class="sect" style="margin-top:10px;padding-top:10px"></div>', unsafe_allow_html=True)
            h1, h2 = st.columns([0.7, 0.3], vertical_alignment="top")
            h1.markdown(f'<div class="board-h">Variant {vi + 1}</div><div class="adcopy">{ui.esc(v["headline"])}</div>'
                        f'<div class="adsub">{ui.esc(v["subline"])} · <b>{ui.esc(v["cta"])}</b></div>', unsafe_allow_html=True)
            h2.markdown(f'<div style="text-align:right">{ui.verdict_tag(v["claims"]["verdict"])}</div>', unsafe_allow_html=True)
            for r in v["claims"]["reasons"]:
                st.markdown(f'<div class="meta">{ui.status_tag(r["level"], "✕" if r["level"] == "block" else "!")} {ui.esc(r["reason"])}</div>',
                            unsafe_allow_html=True)
            imgs = [a for a in camp["ads"]["assets"] if a["variant"] == ok_vs.index(v)] if v in ok_vs else []
            imgs = sorted([a for a in imgs if Path(a["path"]).exists()], key=lambda a: ORDER.index(a["size"]) if a["size"] in ORDER else 9)
            if imgs:
                widths = [SIZES[a["size"]][0] / SIZES[a["size"]][1] for a in imgs]
                cols = st.container(key=f"board_{vi}").columns(widths, gap="small")
                for col, a in zip(cols, imgs):
                    w, h = SIZES[a["size"]]
                    col.image(a["path"], caption=LABEL.get(a["size"], a["size"]), width="stretch")
            else:
                st.markdown('<div class="empty meta" style="padding:10px">Not rendered — blocked by the claims checker.</div>',
                            unsafe_allow_html=True)
            with st.expander("Why this line?"):
                st.markdown(f'<div class="small">{ui.esc(v["why"])}</div>', unsafe_allow_html=True)
                rids, labs, notes = ui.resolve_evidence(ins, v["evidence"])
                if notes:
                    st.markdown(f'<div class="meta">metrics: {ui.esc(" · ".join(notes))}</div>', unsafe_allow_html=True)
                if rids:
                    ui.evidence_count_button(len(rids), v["headline"], rids, f"why_{vi}", labels=labs,
                                             label=f"reviews behind it · n = {len(rids)}")
        st.markdown('<div class="meta" style="margin-top:8px">Palette from the product photo: ' +
                    "".join(f'<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:{c};'
                            f'border:1px solid var(--rule);margin:0 3px -2px 0"></span>' for c in camp["palette"]) + "</div>",
                    unsafe_allow_html=True)
    with tabs[1]:
        e = camp["ecom"]
        bad = {c["text"]: c for c in camp["ecom_claims"] if c["verdict"] != "ok"}

        def flag(text):
            c = bad.get(text)
            return (" " + ui.verdict_tag(c["verdict"])) if c else ""
        st.markdown(f'<div class="meta">{ui.engine_badge(camp["engines"].get("ecom"))} · {len(bad)} line(s) flagged by the claims checker</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="eyebrow" style="margin-top:8px">Amazon title · {len(e["amazon_title"])} chars</div>'
                    f'<div style="font-weight:600">{ui.esc(e["amazon_title"])}{flag(e["amazon_title"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="eyebrow" style="margin-top:10px">Bullets</div>' +
                    "".join(f'<div class="small" style="padding:3px 0;border-bottom:1px solid var(--rule)">• {ui.esc(x)}{flag(x)}</div>'
                            for x in e["bullets"]), unsafe_allow_html=True)
        st.markdown(f'<div class="eyebrow" style="margin-top:10px">Product description</div>'
                    f'<div class="small" style="line-height:1.55">{ui.esc(e["product_description"])}{flag(e["product_description"])}</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="eyebrow" style="margin-top:10px">A+ modules</div>', unsafe_allow_html=True)
        for m in e["aplus"]:
            st.markdown(f'<div class="swot o"><div style="font-weight:700">{ui.esc(m["title"])}</div><div class="small">{ui.esc(m["body"])}</div>'
                        f'<div class="meta">Image: {ui.esc(m["image_idea"])} · {ui.esc(" ".join(m["evidence"]))}</div></div>',
                        unsafe_allow_html=True)
        st.markdown('<div class="eyebrow" style="margin-top:10px">SEO keywords · customers\' own words</div>' +
                    "".join(ui.tag(k) for k in e["seo_keywords"]), unsafe_allow_html=True)
        for c in bad.values():
            st.markdown(f'<div class="meta">{ui.verdict_tag(c["verdict"])} {ui.esc(c["text"][:100])} — '
                        + "; ".join(ui.esc(r["reason"]) for r in c["reasons"]) + "</div>", unsafe_allow_html=True)
    with tabs[2]:
        vids = [v for v in camp.get("videos", [])]
        for v in vids:
            if v.get("path") and Path(v["path"]).exists():
                vc1, vc2 = st.columns([0.45, 0.55], gap="medium")
                vc1.video(v["path"])
                vc2.markdown(f'<div class="meta">{v.get("duration", "?")} s · 720×1280 · voice-over: {ui.esc(v.get("voiceover", "none"))}<br/>'
                             f'frames: {ui.esc(", ".join(sorted(set(v.get("frame_engines", [])))))}</div>', unsafe_allow_html=True)
            elif v.get("error"):
                st.error(f"Video render failed: {v['error']}")
        if not vids:
            st.markdown('<div class="meta">No storyboard video — turn on “Storyboard MP4” and regenerate.</div>', unsafe_allow_html=True)
        for k in ("script15", "script30"):
            s = camp[k]
            st.markdown(f'<div class="sect" style="margin-top:10px;padding-top:8px"><h3>{s["duration_s"]} s · {ui.esc(s["title"])}</h3>'
                        f'<span class="meta">{ui.engine_badge(camp["engines"].get(k))}</span></div>'
                        f'<div class="meta">Hook: <i>{ui.esc(s["hook"])}</i> · Concept: {ui.esc(s["video_concept"])} · Music: {ui.esc(s["music_mood"])}</div>',
                        unsafe_allow_html=True)
            fr = ui.df(s["frames"])
            fr["time"] = fr["t_start"].map(lambda x: f"{x:g}") + "–" + fr["t_end"].map(lambda x: f"{x:g}s")
            st.dataframe(fr[["time", "visual", "on_screen_text", "voiceover"]], hide_index=True, width="stretch",
                         column_config={"time": st.column_config.TextColumn("t", width="small"),
                                        "on_screen_text": "On screen", "voiceover": "Voice-over", "visual": "Visual"})
    with tabs[3]:
        st.markdown('<div class="small">The checker blocks medical/absolute claims, banned words, wrong SPF/PA, competitor names, '
                    'and any claim where <b>our own reviews disagree</b>. Probes run against this product:</div>', unsafe_allow_html=True)
        for i, c in enumerate(camp["claims_probe"]):
            c1, c2 = st.columns([0.82, 0.18], vertical_alignment="top")
            c1.markdown(f'<div style="padding:4px 0;border-bottom:1px solid var(--rule)">{ui.verdict_tag(c["verdict"])} <b>{ui.esc(c["text"])}</b>'
                        + "".join(f'<div class="meta">{ui.esc(r["reason"])}</div>' for r in c["reasons"]) + "</div>",
                        unsafe_allow_html=True)
            with c2:
                if c.get("evidence"):
                    ui.evidence_count_button(len(c["evidence"]), c["text"], c["evidence"], f"probe_{i}")
        test = st.text_input("Test your own claim", "Zero white cast, all day")
        if test:
            r = claims_mod.check(test, p.get("spec", {}), pipeline.own_topic_net(ctx, ins))
            st.markdown(f'{ui.verdict_tag(r["verdict"])} ' + (" ".join(ui.esc(x["reason"]) for x in r["reasons"]) or
                                                              '<span class="meta">No issues found.</span>'), unsafe_allow_html=True)
    with tabs[4]:
        have = camp.get("regional", {})
        if not sarvam.available():
            ui.empty_state("Regional versions need a Sarvam key",
                           "Add <code>SARVAM_API_KEY</code> to .env to make Hindi / Bengali versions (Mayura translate + Bulbul v3 "
                           "voice). Ads are re-rendered with native-script fonts and the storyboard gets a regional voice-over.")
        rl = st.multiselect("Languages", ["hi", "bn", "ta", "mr"], default=bi["languages"], format_func=lambda l: sarvam.LANG_NAMES[l])
        if st.button("Make regional versions", disabled=not sarvam.available() or not rl or not ui.can_act(), type="primary" if sarvam.available() else "secondary"):
            with st.status("Localising", expanded=True) as status:
                pipeline.regional(camp["id"], rl, progress=lambda s, d="", f=None: status.update(label=f"{s} — {d}"))
                status.update(label="Regional versions ready", state="complete")
            st.rerun()
        for lang, r in have.items():
            st.markdown(f'<div class="sect" style="margin-top:8px;padding-top:8px"><h3>{ui.esc(sarvam.LANG_NAMES.get(lang, lang))}</h3>'
                        f'<span class="meta">{ui.esc(r["ad_text"]["headline"])}</span></div>', unsafe_allow_html=True)
            ads = sorted(r["ads"], key=lambda a: 0 if a["size"] == "story" else 1)
            cols = st.columns([SIZES[a["size"]][0] / SIZES[a["size"]][1] for a in ads] + ([0.5625] if r.get("video") and r["video"].get("path") else []))
            for col, a in zip(cols, ads):
                col.image(a["path"], caption=f"{a['size']} · {lang}", width="stretch")
            if r.get("video") and r["video"].get("path"):
                cols[-1].video(r["video"]["path"])
    with tabs[5]:
        est = higgsfield.estimate_i2v(5)
        st.markdown(f'<div class="small">Animate the finished 9:16 ad with <b>Higgsfield Kling 2.5 Turbo</b> (image-to-video, 5 s), then add '
                    f'the voice-over and an end card.</div><div class="meta num" style="margin-top:4px">Estimated <b>${est:.2f}</b> '
                    f'(≈₹{est * costs.INR_PER_USD:.0f}) · spent ${costs.spent("higgsfield"):.2f} of '
                    f'${float(env("HIGGSFIELD_MAX_USD", "5")):.2f} cap</div>', unsafe_allow_html=True)
        if camp.get("hero") and Path(camp["hero"]["path"]).exists():
            st.video(camp["hero"]["path"])
        if not higgsfield.available():
            st.markdown('<div class="meta">Set HIGGSFIELD_API_KEY and HIGGSFIELD_API_SECRET in .env to enable.</div>', unsafe_allow_html=True)
        confirm = st.checkbox(f"I approve spending ${est:.2f} on Higgsfield", disabled=not higgsfield.available())
        if st.button("Render hero clip (paid)", disabled=not (higgsfield.available() and confirm and ui.can_act())):
            with st.spinner("Higgsfield is rendering (1–3 min)…"):
                try:
                    pipeline.hero(camp["id"])
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

    # ---------- approval ----------
    st.markdown('<div class="sect" style="margin-top:16px"><h2>Approve</h2>'
                f'<span class="meta">status {ui.status_tag({"approved": "ok", "rejected": "block"}.get(camp.get("status"), "warn"), camp.get("status") or "draft")}'
                f' · {ui.esc(camp["created_at"])} · {camp["elapsed_s"]} s</span></div>', unsafe_allow_html=True)
    a1, a2 = st.columns(2)
    zipf = next(iter(sorted(cdir.glob("campaign_pack_*.zip"))), None)
    if zipf:
        a1.download_button("Download pack (ZIP)", zipf.read_bytes(), file_name=zipf.name, width="stretch")
    if a2.button("Send for approval", type="primary", width="stretch", disabled=not ui.can_act(), help="n8n webhook → Telegram with Approve / Reject"):
        hook = env("N8N_APPROVAL_WEBHOOK_URL")
        try:
            if hook:
                requests.post(hook, json={"campaign_id": camp["id"], "product": p["handle"], "persona": camp["persona"]["id"],
                                          "category": ins["category"], "languages": bi["languages"]}, timeout=15)
                st.session_state[f"sent_{camp['id']}"] = True
                st.success("Sent to n8n — watch Telegram for the approval message.")
            elif telegram.available():
                img = next((a["path"] for a in camp["ads"]["assets"] if a["size"] == "square"), None)
                base = env("PUBLIC_BASE_URL", "http://localhost:8000")
                tok = env("API_TOKEN")
                btn = [("Approve", f"{base}/api/campaign/{camp['id']}/decision?d=approve&token={tok}"),
                       ("Reject", f"{base}/api/campaign/{camp['id']}/decision?d=reject&token={tok}")]
                telegram.send_file("sendPhoto", img, f"<b>Approval needed</b>\n{p['title']}\n{camp['brief']['key_message']}", btn)
                st.session_state[f"sent_{camp['id']}"] = True
                st.success("Sent directly to Telegram (n8n webhook not configured).")
            else:
                st.warning("No approval channel configured: set N8N_APPROVAL_WEBHOOK_URL, or TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, "
                           "in .env. You can still approve manually on Campaign packs.")
        except Exception as ex:
            st.error(f"Send failed: {ex}")

ui.next_step("packs", "Review in Campaign packs", "All generated campaigns, their status and downloadable packs in one place.")
