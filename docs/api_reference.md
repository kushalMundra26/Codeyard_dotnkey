# API Reference (verified against official docs, 2026-11-21)

Every fact cites its source URL. "UNVERIFIED" = could not confirm in official docs.

---

## 1. Sarvam AI

Auth for all Sarvam REST calls: header `api-subscription-key: <KEY>`.
Source: https://docs.sarvam.ai/api/api-guides-tutorials/text-processing/translation.md

### 1a. Text translation
Source: https://docs.sarvam.ai/api-reference-docs/text/translate.md and https://docs.sarvam.ai/api/api-guides-tutorials/text-processing/translation.md

- `POST https://api.sarvam.ai/translate`, `Content-Type: application/json`
- Request fields:
  | Field | Req | Values |
  |---|---|---|
  | `input` | yes | max **1000 chars** (`mayura:v1`), **2000 chars** (`sarvam-translate:v1`) |
  | `source_language_code` | yes | BCP-47 code, or `auto` (auto only with `mayura:v1`) |
  | `target_language_code` | yes | BCP-47 code (no `auto`) |
  | `model` | no | `mayura:v1` (11 langs + English, all modes, output_script, auto-detect) or `sarvam-translate:v1` (22 scheduled langs, `formal` only). Default model: UNVERIFIED |
  | `mode` | no | `formal` (default), `modern-colloquial`, `classic-colloquial`, `code-mixed` (non-formal = mayura only) |
  | `speaker_gender` | no | `Male`, `Female` |
  | `output_script` | no | `roman`, `fully-native`, `spoken-form-in-native`; default null; mayura only |
  | `numerals_format` | no | `international` (default) or `native` |
- Response 200: `{ "request_id": str|null, "translated_text": str, "source_language_code": str }`
- Errors: `{ "error": { "request_id", "message", "code" } }`; 400 invalid_request_error, 422 text too long / unsupported pair, 403, 429, 500.
- Language codes: Hindi `hi-IN`, Bengali `bn-IN`, Tamil `ta-IN`, Marathi `mr-IN`, English `en-IN`. mayura:v1 set: bn, en, gu, hi, kn, ml, mr, od, pa, ta, te (all `-IN`). sarvam-translate adds as, brx, doi, kok, ks, mai, mni, ne, sa, sat, sd, ur.

### 1b. Text-to-speech (Bulbul)
Sources: https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert.md , https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/rest-api.md , https://docs.sarvam.ai/api/api-guides-tutorials/models/bulbul.md , https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/how-to/change-the-speaker-voice.md , https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/voices.md

- `POST https://api.sarvam.ai/text-to-speech`
- **SURPRISE:** language field is `language_code` (NOT `target_language_code`); text field is `text` (NOT `inputs` list). bulbul:v2 is no longer listed in the API enum.
- Models (enum): `bulbul:v3` (default when `model` omitted), `bulbul:v4-flash` (latest, "recommended for new integrations").
- Request fields:
  | Field | Req | Default | Values |
  |---|---|---|---|
  | `text` | yes | - | 1–**2500 chars** (REST) |
  | `language_code` | yes | - | `bn-IN en-IN gu-IN hi-IN kn-IN ml-IN mr-IN od-IN pa-IN ta-IN te-IN` |
  | `model` | no | `bulbul:v3` | `bulbul:v3`, `bulbul:v4-flash` |
  | `speaker` | no | `shubh` (v3) / `shubh_enhi_ads` (v4-flash) | must match model, else 400 listing valid speakers; lowercase, case-sensitive |
  | `pace` | no | 1.0 | 0.5–2.0 |
  | `pitch` | no | 0.0 | -0.5–0.5 |
  | `loudness` | no | 1.0 | 0.1–2.5 |
  | `temperature` | no | 0.6 | 0.01–1.0 |
  | `speech_sample_rate` | no | 22050 | 8000, 16000, 22050, 24000, 32000, 44100, 48000 |
  | `output_audio_codec` | no | `wav` | wav, mp3, aac, flac, linear16, mulaw, alaw, opus (opus fails at 22050; use 8000/16000/24000/48000) |
  | `enable_preprocessing` | no | false | normalizes English words/numbers |
  | `dict_id` | no | - | `p_` + 8 hex |
- Response 200: `{ "request_id": "...", "audios": ["<base64>"] }` — base64 audio in requested codec (WAV by default); decode `audios[0]`.
- **bulbul:v3 speakers (37)** (genders from change-the-speaker-voice page):
  - Male: shubh (default), aditya, rahul, rohan, amit, dev, ratan, varun, manan, sumit, kabir, aayan, ashutosh, advait, anand, tarun, sunny, mani, gokul, vijay, mohit, rehan, soham
  - Female: ritu, priya, neha, pooja, simran, kavya, ishita, shreya, roopa, tanya, shruti, suhani, kavitha, rupali
  - Note: docs advise `varun` is deep/dramatic, not a neutral default (voices.md).
- **bulbul:v4-flash**: 200+ persona IDs of form `<name>_<language>_<style>`, e.g. `simran_en_customer`, `shubh_enhi_ads` (default). Full list on voices.md; exact IDs per language not extracted — UNVERIFIED beyond those two examples.
- Streaming variants exist (HTTP stream max 3500 chars; WebSocket) — not needed here.

### 1c. Chat completions
Source: https://docs.sarvam.ai/api/token-factory/chat-completions.md

- V1 `POST https://api.sarvam.ai/v1/chat/completions` — models `sarvam-105b`, `sarvam-105b-conversations`.
- V2 `POST https://api.sarvam.ai/v2/chat/completions` — "OpenAI-compatible"; models `sarvam-105b`, `glm5.3`, `glm5.3-flash`, `gemma4`, `deepseekv4.1-flash-1017`. `GET /v2/models` lists served IDs.
- Auth: `api-subscription-key`, or `Authorization: Bearer <key>` for OpenAI tooling.
- Body: `model`, `messages`, `temperature`, `top_p`, `max_tokens` (default 2048 on V1 sarvam-105b; reasoning tokens count), `response_format` (`json_schema`/`json_object`/`text`), `tools`, `stream`, `n` must be 1.
- Response: OpenAI shape `choices[0].message.content` (+ `reasoning_content`).
- Pricing: UNVERIFIED.

---

## 2. Higgsfield API

Sources: https://higgsfield.ai/blog/higgsfield-api , https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api , https://docs.higgsfield.ai/docs , https://docs.higgsfield.ai/docs/quickstart.md

- Base URL: `https://api.higgsfield.ai`. Console/keys: https://console.higgsfield.ai (help center also mentions open.higgsfield.ai).
- Auth: **key ID + secret** in one header: `Authorization: Key <HF_API_KEY_ID>:<HF_API_KEY_SECRET>`; `Content-Type: application/json`; optional `Idempotency-Key: <uuid>` on submit. (quickstart.md)
- Flow is async: POST to model path -> get `request_id` -> poll or webhook -> download.
- Submit response: `{ "status": "queued", "request_id": "...", "status_url": ".../requests/{id}/status", "cancel_url": ".../requests/{id}/cancel" }` (+ `expires_after` seconds). Source: https://docs.higgsfield.ai/docs/concepts/requests.md
- Poll: `GET https://api.higgsfield.ai/requests/{request_id}/status` (same auth). Start at 2 s, back off ×1.5 up to 10 s, add jitter. Source: https://docs.higgsfield.ai/docs/concepts/polling.md
- Status values: `queued`, `in_progress` (non-terminal); `completed`, `failed`, `nsfw`, `canceled` (terminal). (requests.md)
- Result location on `completed`: video -> `video.url`; image -> `images[].url`; audio -> `audio.url`. (requests.md)
- Cancel: `POST /requests/{id}/cancel` (202, only while queued). Delete data: `DELETE /requests/{id}`.
- Webhook: add `?hf_webhook=<url-encoded https URL>` to the submit URL; payload `{request_id, status, error, payload:{video|images|audio}}`. Source: https://docs.higgsfield.ai/docs/how-to/webhooks.md
- Outputs retained ≥7 days; download before `expires_at`. 20 concurrent requests per key. Failed requests not charged. Min top-up $5. (help center page)

### Image input
Source: https://docs.higgsfield.ai/docs/concepts/file-uploads.md
- If image is on a public HTTPS URL, pass it as `image_url`.
- Otherwise `POST https://api.higgsfield.ai/files/generate-upload-url` body `{"content_type":"image/jpeg"}` -> `{public_url, upload_url, content_type, upload_headers}`; `PUT` file to `upload_url` with all `upload_headers` (no HF auth); use `public_url` as `image_url`. Upload URL expires in 1 h.

### Image-to-video: Kling 2.5 Turbo Standard (cheapest listed video model)
Source: https://docs.higgsfield.ai/docs/models/kling-2-5-turbo/standard-image-to-video.md
- `POST https://api.higgsfield.ai/kling-video/v2.5-turbo/standard/image-to-video`
- Fields: `prompt` (str, req), `image_url` (uri, req), `duration` (int 5|10, default 5), `cfg_scale` (0–1, default 0.5), `negative_prompt` (str, default "").
- **No aspect_ratio / resolution / sound field** (aspect follows input image — inference, UNVERIFIED).
- Pro variant `/kling-video/v2.5-turbo/pro/image-to-video` appears only in the supplementary OpenAPI spec (https://docs.higgsfield.ai/docs/openapi.json), same fields.
- Also in OpenAPI spec: `/minimax/hailuo-2.3/standard/image-to-video` (`prompt`, `image_url`, `duration` 6|10 default 6, `prompt_optimizer` bool default true).
- Seedance 2.5 / Kling 2.6 / 3.0 endpoint paths: UNVERIFIED (model pages exist at https://docs.higgsfield.ai/docs/models/seedance-2-5.md, .../kling-2-6.md, .../kling-3.md but timed out).
- Starting prices (blog): Kling 2.5 **$0.042/s**, Kling 2.6 $0.07/s, Seedance 2.5 $0.0738/s, Kling 3.0 $0.112/s, PixVerse 6 $0.115/s, MiniMax H3 $0.13/s, LTX 2.5 Pro $0.17/s, Wan 3.0 $0.20/s, Seedance 2.0 $0.9332/s; DoP $0.125/generation. Rates vary by resolution/audio.

### Text-to-image: Soul
- Soul 2 (current): `POST https://api.higgsfield.ai/higgsfield-ai/soul/v2/standard`, body `{"prompt": "..."}` (quickstart.md). Full field list for v2: UNVERIFIED. Price $0.0032/image 720p, $0.0057/image 1080p (https://open.higgsfield.ai/models/higgsfield-ai/soul/v2/standard/playground).
- Soul (v1) `POST https://api.higgsfield.ai/higgsfield-ai/soul/standard` (https://docs.higgsfield.ai/docs/models/soul-standard/generate.md): `prompt` (req), `aspect_ratio` (`9:16`,`16:9`,`4:3`,`3:4`,`1:1`,`2:3`,`3:2`; default `4:3`), `resolution` (`720p`|`1080p`, default `720p`), `enhance_prompt` (bool), `style_id` (uuid), `style_strength` (0–1), `seed` (1–1000000), `batch_size` (1|4), `image_reference_url`, `custom_reference_id`. Output `images[].url`.
  - Note: the OpenAPI spec lists different enums for soul/standard (`resolution` 2K/4K, `num_images`) — conflict; prefer the model page.

### Python SDK
Source: https://docs.higgsfield.ai/docs/how-to/sdk.md
- `pip install higgsfield-client`; `import higgsfield_client`; env `HF_KEY="<key_id>:<key_secret>"`.
- `result = higgsfield_client.subscribe("higgsfield-ai/soul/v2/standard", arguments={"prompt": "..."})` -> `result["images"][0]["url"]` (video models: `result["video"]["url"]`). Also `submit`, `submit_async`, `upload`, `upload_file`, `upload_image`.
- TS: `@higgsfield/client` (import from `@higgsfield/client/v2`).

---

## 3. Cloudflare Workers AI — FLUX.1 [schnell]
Source: https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/

- `POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell`
- Header `Authorization: Bearer <CLOUDFLARE_API_TOKEN>`
- Body: `prompt` (str, req, 1–2048 chars), `steps` (int, **max 8, default 4**), `seed` (shown in examples only; type not formally documented).
- Response: `{"result": {"image": "<base64>"}, "success": true, ...}` — `image` is base64; examples treat it as **JPEG** (`data:image/jpeg;base64,...`). The `result` envelope is the standard REST wrapper (UNVERIFIED on this page explicitly).
- No width/height params documented. Pricing not on page (UNVERIFIED).

---

## 4. Pollinations
Sources: https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md (current), https://raw.githubusercontent.com/pollinations/pollinations/master/APIDOCS.md ("Classic API")

- **Current API**: base `https://gen.pollinations.ai`
  - `GET /image/{prompt}` params: `model` (default `tongyi-mai/z-image-turbo`), `width`/`height` (default 1024), `seed` (default 0; -1 random; model-dependent), `safe`, `quality` (GPT-image/grok only). `nologo` / `enhance` NOT documented.
  - Also OpenAI-compatible `POST /v1/images/generations` (default model `black-forest-labs/flux.1-schnell`, `response_format` `b64_json`).
  - **Key required**: secret `sk_` key via `Authorization: Bearer sk_...` (or `?key=` for GET image URLs). `pk_` keys get 401. Keys at enter.pollinations.ai. Free usage via "Quest" balance (details UNVERIFIED).
  - Model ids now namespaced, e.g. `black-forest-labs/flux.1-schnell`, `tongyi-mai/z-image-turbo`; live list `GET /image/models`.
- **Classic API** (kept "stable for existing apps"): `GET https://image.pollinations.ai/prompt/{prompt}`; params `width`/`height` (default 768), `seed` (default 42), `safe` (default false); one model; **no key needed**, anonymous rate limit per IP: one image at a time, ≥45 s apart, else 402. `model`/`nologo`/`enhance` not documented there (UNVERIFIED).

---

## 5. Google Gemini API
Sources: https://aistudio.google.com/llms.txt , https://aistudio.google.com/docs/models , https://aistudio.google.com/docs/pricing.md , https://aistudio.google.com/docs/structured-output.md?generate-content=true , https://aistudio.google.com/api-reference/generate-content

- **SURPRISE:** ai.google.dev docs now 301-redirect to aistudio.google.com/docs; the docs label `generateContent` as **legacy** and recommend the **Interactions API** (`POST https://generativelanguage.googleapis.com/v1beta/interactions`, header `Api-Revision: 2026-05-20`, body `{"model":..., "input":...}`).
- generateContent still documented: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, header `x-goog-api-key: <KEY>`, body `{"contents":[{"parts":[{"text":"..."}]}], "generationConfig": {...}}`. Response text at `candidates[0].content.parts[0].text`; if blocked, no candidates — check `promptFeedback`.
- JSON output (REST, current docs): `generationConfig.responseFormat.text = {"mimeType": "APPLICATION_JSON", "schema": {...}}`. SDK samples use `responseMimeType: "application/json"` + `responseJsonSchema`; API reference still lists `responseMimeType` and `responseJsonSchema` in GenerationConfig. Classic `responseSchema` not mentioned in current docs (whether it still works: UNVERIFIED).
- Models with free tier (pricing.md): `gemini-3.5-flash-lite` ($0.30/$2.50 per 1M paid), `gemini-3.1-flash-lite` ($0.25/$1.50), `gemini-3.8-flash`, `gemini-3.6-flash` ($0.75/$3.75), `gemini-4-hydrogen` ($1.50/$7.50), `gemini-2.5-flash-lite` ($0.10/$0.40, served "until further notice").
- Deprecated: `gemini-2.5-flash` (routes to `gemini-3.5-flash-lite` on 2026-12-01), `gemini-2.5-pro`. Shut down: `gemini-2.0-flash*`. Recommended for new work: "Gemini 4 Hydrogen or 3.5 Flash-Lite" (models page).
- Free-tier RPM/RPD for these models: UNVERIFIED (rate-limits page defers to AI Studio).
- Recommendation for cheap JSON: `gemini-3.5-flash-lite` (or `gemini-2.5-flash-lite`).

---

## 6. Telegram Bot API (v10.4, 2026-11-09)
Source: https://core.telegram.org/bots/api

- URL: `https://api.telegram.org/bot<TOKEN>/<method>`; JSON, form-urlencoded, or multipart/form-data.
- `sendMessage`: `chat_id`, `text` (1–4096 chars after entity parsing), `parse_mode` (`HTML`, `MarkdownV2`, `Markdown`), `reply_markup`, `link_preview_options`.
- `sendPhoto`: `chat_id`, `photo` (file_id | HTTP URL | multipart upload), `caption` (0–1024), `parse_mode`, `reply_markup`. Photo ≤10 MB, width+height ≤10000, ratio ≤20.
- `sendVideo`: `chat_id`, `video`, `caption`, `duration`, `width`, `height`, `supports_streaming` (bool — confirmed for InputMediaVideo; on sendVideo standard but not re-confirmed in fetched excerpt), `thumbnail`, `reply_markup`. Bots send video ≤50 MB.
- `sendDocument`: `chat_id`, `document`, `caption` (0–1024), `disable_content_type_detection`, `reply_markup`. ≤50 MB.
- Limits: by URL photos 5 MB / others 20 MB (sendDocument by URL only .PDF/.ZIP); multipart photos 10 MB / others 50 MB; file_id no limit.
- Multipart (requests): `requests.post(url, data={"chat_id": cid, "caption": c, "reply_markup": json.dumps(kb)}, files={"photo": open(p,"rb")})` — `reply_markup` must be a JSON-serialized string in multipart.
- Inline keyboard: `reply_markup = {"inline_keyboard": [[{"text": "Open", "url": "https://..."}]]}` (Array of Array of InlineKeyboardButton; `url` = HTTP or tg:// URL; exactly one action field per button besides text/icon/style).

---

## 7. n8n
Sources: https://github.com/n8n-io/n8n/releases , https://docs.n8n.io/changelog , node sources at https://github.com/n8n-io/n8n/tree/n8n@2.48.7/packages/nodes-base/nodes , https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait/

- Latest stable: **n8n 2.48.7** (2026-11-20); beta 2.49.3.
- Workflow JSON essentials (official docs page doesn't spell out schema; structure UNVERIFIED-by-doc but standard): `{"name", "nodes": [{"id","name","type","typeVersion","position":[x,y],"parameters":{},"credentials":{}}], "connections": {"<SourceNodeName>": {"main": [[{"node":"<TargetName>","type":"main","index":0}]]}}, "settings": {}}`. IF node: `main[0]` = true branch, `main[1]` = false. Export contains credential names/IDs (https://docs.n8n.io/workflows/export-import/).
- Node types / typeVersions (from source at tag n8n@2.48.7):
  | Node | type | versions (latest) |
  |---|---|---|
  | Schedule Trigger | `n8n-nodes-base.scheduleTrigger` | 1–1.4 (**1.4**) |
  | HTTP Request | `n8n-nodes-base.httpRequest` | 1–4.5 (default **4.5**) |
  | IF | `n8n-nodes-base.if` | 1, 2–2.4 (default **2.4**) |
  | Telegram | `n8n-nodes-base.telegram` | 1, 1.1, **1.2** |
  | Webhook | `n8n-nodes-base.webhook` | 1, 1.1, 2, 2.1, **2.2** |
  | Wait | `n8n-nodes-base.wait` | 1, **1.1** |
- Wait node: parameter `resume` values `timeInterval`, `specificTime`, `webhook`, `form`. With `resume: "webhook"`, the execution resumes when its unique URL `{{ $execution.resumeUrl }}` is called (HTTP method configurable; optional limitWaitTime; webhook suffix must be appended manually). Waits <65 s stay in memory. (Wait docs + Wait.node.ts)
