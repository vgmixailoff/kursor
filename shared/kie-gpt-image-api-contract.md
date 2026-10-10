# Kie GPT Image 2 API Contract

Primary Cloud path for Excalibur BLOG cover generation.

## Evening canon (preferred): Sunburst comic i2i

```bash
python3 scripts/excalibur_blog_cover_sunburst_i2i.py --article-dir <dir>
python3 scripts/excalibur_blog_kie_gpt_image2_api.py \
  --article-dir <dir> \
  --batch cover/t2i-batch.json \
  --result cover/t2i-result.json \
  --model gpt-image-2-5-sunburst-image-to-image
python3 scripts/excalibur_blog_cover_black_apply.py --article-dir <dir>
```

- Model: `gpt-image-2-5-sunburst-image-to-image`
- Resolution: **1K**, aspect **16:9**, background **opaque**
- Batch: `cover/t2i-batch.json` — `canon: sunburst_i2i`, mascot via
  `prefer_local_reference` (`memory/cover/assets/cover-mascot.png`)
- Gemini COVER_PROMPT **не** уходит в Kie: TITLE заполняет
  `shared/cover-sunburst-comic-prompt.txt`
- Одна createTask на обложку (не 3–4 «на красоту»)
- См. `shared/blog-cover-sunburst-comic-contract.md`

Legacy black-canvas t2i (`gpt-image-2-text-to-image`, без `input_urls`)
остаётся в скрипте для старых batch. Ниже — retry/ошибки Kie API.

## Order of preference (mandatory)

```text
1. KIE_API_KEY set  → scripts/excalibur_blog_kie_gpt_image2_api.py only
2. KIE_API_KEY missing → legacy MCP gpt-image-2 (async tools if present; sync once max)
```

If `KIE_API_KEY` is present in Cloud Secrets/env, **do not** call sync MCP `gpt-image-2` first.
Director/Task prompts must not force «ONE MCP gpt-image-2» as the primary path.

## Why

Cursor Cloud can terminate long sync MCP tool calls before GPT Image 2 finishes
generation. The direct Kie API is asynchronous:

```text
createTask -> taskId -> recordInfo polling -> resultUrls[0]
```

This keeps waiting in the shell process instead of a single MCP request.

## Auth

- Env var: `KIE_API_KEY`
- Store only in Cursor Cloud Secrets / environment.
- Never commit, print, or copy the key into handoff, PR bodies, article files, or logs.

## Cover command

```bash
python scripts/excalibur_blog_kie_gpt_image2_api.py \
  --article-dir memory/blog/articles/<topic_id>-<slug>
```

The script reads:

- `cover/t2i-batch.json` -> `jobs[0].mcp_args`

The script writes:

- `cover/kie-image-task.json` -> `task_id` and non-secret status
- `cover/t2i-result.json` -> generated URL, consumed by `excalibur_blog_cover_black_apply.py`

Then run:

```bash
python scripts/excalibur_blog_cover_black_apply.py \
  --article-dir memory/blog/articles/<topic_id>-<slug>
```

## API shape

Create:

```json
{
  "model": "gpt-image-2-image-to-image",
  "input": {
    "prompt": "...",
    "input_urls": ["https://.../ava.jpg"],
    "aspect_ratio": "16:9",
    "resolution": "2K"
  }
}
```

Poll:

```text
GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=<taskId>
```

Terminal states:

- `success`: parse `data.resultJson` and use `resultUrls[0]`
- `fail` with failCode=`500` / failMsg containing «try again later»: **one** controlled new `createTask` (default `--max-create-retries 1`); do **not** keep polling the failed `taskId`
- `fail` with failCode=`400` / failMsg «image fetch failed» (or «use our File Upload API»): **one** File Upload + new `createTask` (see below); not a permanent blocker on first hit
- `fail` with failCode=`422` / failMsg «sensitive» (input/output flagged): **agent** softens prompt once + **one** recreate (see below); not a permanent blocker on first hit
- other `fail`: stop with `KIE API BLOCKER`
- poll-window timeout (still `waiting`/`generating` past `--max-wait`): **one final** `recordInfo` before `KIE API BLOCKER` (INC-20260730-0834). If that final call is terminal `fail` 500 / try-again (or 400 image-fetch), take the same recreate path as an in-window terminal fail — do **not** hard-stop solely because the client poll clock expired. Only if the final call is still non-terminal (or recordInfo itself errors) → `KIE API BLOCKER`

## Retry (transient 500)

`excalibur_blog_kie_gpt_image2_api.py` handles this automatically:

```text
createTask → poll recordInfo
  → state=fail + failCode=500 / «try again later»
  → wait --retry-wait (default 15s)
  → ONE new createTask (not re-poll failed taskId)
  → poll new taskId

# also (INC-20260730-0834):
createTask → poll until --max-wait exhausted (still waiting/generating)
  → ONE final recordInfo
  → if terminal fail 500 / «try again later» → same max-1 recreate path
  → if still non-terminal → KIE API BLOCKER
```

Flags:

- `--max-create-retries 1` (default) — extra createTask attempts after retryable terminal fail only
- `--retry-wait 15` — pause before the new create
- `--max-wait 900` — poll window; exhaustion triggers one final `recordInfo`, not an immediate hard stop when terminal 500 is already visible

### Director same-batch re-run after 500 exhausted (B102–B106 / B116 / B117)

When the script exits `KIE API BLOCKER` because `--max-create-retries` is exhausted (typically failCode=`500` ×2), Cover must **not** raise `--max-create-retries`, soften the prompt, or switch to MCP while `KIE_API_KEY` is set. Script stderr now states the batch is ready for Director same-batch re-run (Cover: no third create).

Approved recovery (Director, same article run):

```text
Cover fragment (500×2 exhausted):
  status: BLOCKER
  blockers: KIE API BLOCKER
  summary: 500×2 exhausted; batch ready for Director same-batch re-run;
           Cover will NOT invent a third create — apply-only after Director
  + incident (max-1 recreate already done by script)
Director (when Kie healthy again):
  python3 scripts/excalibur_blog_kie_gpt_image2_api.py --article-dir <dir>
  # unchanged cover/t2i-batch.json — no prompt/quality rewrite
  # File Upload fallback on 400 image-fetch is OK inside this same-batch re-run
Cover apply-only:
  python3 scripts/excalibur_blog_cover_black_apply.py --article-dir <dir> --inject-html
```

Rules:

- Same batch only. Do **not** regenerate manifest/prompt «for quality».
- Do **not** count this Director re-run as a quality multi-gen (INC-20260724-2120).
- Cover after Director success: **apply/split/inject only** — no second Cover createTask loop / no third createTask.
- Keep script default `--max-create-retries 1`; longer waits / extra recreates only under explicit Director policy, not Cover autodrift.
- Still write/keep the open incident so Fixer can confirm docs; ops transient 500 remains possible.
- **Policy (recurring upstream):** each new 500×2 cluster is the same approved path — annotate proven topic_id, do **not** invent Cover-side retry bumps / MCP fallback / swarm restore. Fixer closes as fixed after Director same-batch success + annotation.
- Proven on B102/B103/B104/B105/B106/B116/B117 (B105: Director same-batch + File Upload after 400 → success → apply-only; B106/B116/B117: Director same-batch after 500×2 → success → apply-only → publish).

## Retry (pre-taskId TCP / Connection reset) — INC-20260725-1631

If `createTask` fails **before** any `taskId` is returned / before `cover/kie-image-task.json` is written, with a transport error such as:

- `Connection reset by peer`
- `[Errno 104]`
- `Kie API network error: … connection reset …`

then **one** controlled re-run of the **same** Kie script (same `t2i-batch.json`, no prompt/quality rewrite) is allowed.

```text
POST createTask
  → TCP reset / Connection reset by peer (no taskId, no kie-image-task.json)
  → wait --retry-wait (default 15s)
  → ONE new createTask (same batch)
  → poll new taskId
```

Rules:

- Script auto-retries this once (`retry_kind=pre_task_connection_reset`). Agent may also re-run the same CLI once if an older script build exits immediately.
- This is **not** a quality-redo and does **not** count as host/sticky/style multi-gen.
- Do **not** switch to sync MCP `gpt-image-2` while `KIE_API_KEY` is set.
- If a `taskId` is already known (task record written or create response had `taskId`) — **poll** that task; do not blind-create a second billed job on network ambiguity.
- Second pre-taskId connection reset after the one controlled retry → `KIE API BLOCKER`.

## Image-fetch fallback (failCode 400 / File Upload)

WP media under `{{SITE_BASE}}/wp-content/...` may return HTTP 200 from Cloud shell while the **Kie crawler** still fails (`failCode=400`, `image fetch failed`). That is intermittent and environment-side — not a missing `input_urls` contract bug.

Script auto-path (default on; disable with `--no-file-upload-fallback`):

```text
createTask → poll recordInfo
  → state=fail + failCode=400 / «image fetch failed»
  → download expanded input_urls (if shell can) OR use memory/cover/assets/cover-mascot.png
  → POST kieai.redpandaai.co/api/file-stream-upload (uploadPath=excalibur-blog/hero)
     **with User-Agent** (script default `ExcaliburBlogKieFallback/1.0`; missing UA → CF1010)
  → replace runtime input_urls with data.downloadUrl (do NOT rewrite committed batch)
  → ONE new createTask → poll
```

Rules:

- t2i cover has no input_urls; batch stays git-safe.
- Local HTTP 200 on `ava.jpg` ≠ proof that Kie can fetch it.
- Do **not** fall back to sync MCP `gpt-image-2` when `KIE_API_KEY` is set.
- File Upload recreate is **once** per run (separate from `--max-create-retries` for 500).
- File Upload HTTP request **must** include `User-Agent`. Cloudflare on `kieai.redpandaai.co` may return **CF1010** / HTML challenge without it — do not strip UA or invent a manual curl workaround (INC-20260719-2030).

## Sensitive content (failCode 422) — agent prompt soften + one recreate

Kie may reject a cover prompt with `failCode=422` / «The input or output was flagged as sensitive» even when the batch schema is valid. This is often caused by **competitive/insult-adjacent cover hooks** or aggressive body language (pointing finger, facepalm) on AI-assistant topics — not by a broken `KIE_API_KEY`.

### Prefer soft stake **before** the first Kie call (B58)

On **Cursor / AI-assistant + marketplace / product-card** topics (карточка товара, WB/Ozon, описание SKU), high 422 risk comes from aggressive seller framing:

- Prefer first-attempt human stake: **поиск / клики / в выдаче** (e.g. `…: в поиске?`, `…: клики режет?`).
- Keep aggressive stakes like `продаж нет?` / shocked-shrug / pointing-seller poses as **secondary** — only after a 422 soften, not as the opening Kie prompt.
- First-attempt scene: calm seated / checklist / file→chat; avoid facepalm, shocked shrug, aggressive pointing.

### Prefer soft stake for AI video / text-to-video (B64 / INC-20260720-1241)

On **нейросеть для видео / Make+HeyGen / text-to-video** covers, high 422 risk comes from phone-with-video-preview props and aggressive «охват?/топ без файла» framing:

- Prefer first-attempt stake: **досмотр** (board-safe; `BENEFIT_MARKERS` includes `досмотр`). Example: `Нейросеть для создания видео — досмотр?`.
- First-attempt scene: calm desk + laptop / Make UI; meme like `Один MP4?`.
- Avoid on first Kie: phone showing vertical MP4 preview; captions `Топ без файла?` / aggressive «охват?» + shock props.
- Keep aggressive video-shock framing as **secondary** — only after a 422 soften.

### Prefer soft stake for payment / BIN / card (B90 / INC-20260726-0814)

On **Cursor payment / BIN / card / МИР / «оплатить из России»** covers, high 422 risk comes from dead-card / decline / ban framing:

- Prefer first-attempt stake: **аккаунт / Active Pro / на своём аккаунте** (e.g. `Pro на своём аккаунте`).
- First-attempt cover prop: tiny Active Pro badge (calm desk / account UI).
- Avoid on first Kie: «мёртв* карт*», declined-card props, decline/ban/МИР shock labels in scene_hint or inline.
- Keep card-decline / ban shock as **secondary** — only after a 422 soften.

Agent recovery (once per run; script does **not** auto-rewrite copy):

```text
createTask → poll recordInfo
  → state=fail + failCode=422 / «sensitive»
  → soften cover_hook / scene_hint, keep deprecated meme_caption_ru="" (calm editorial framing; no reaction gesture, competitor jab or joke caption)
  → on AI-assistant topics: avoid pointing-finger / facepalm as primary gesture; prefer neutral index→UI / checklist pose
  → marketplace+Cursor: swap «продаж нет?» → search/clicks stake; calm scene
  → AI video: swap phone-MP4 / «топ без файла» → desk+laptop + stake «досмотр?» + meme «Один MP4?»
  → payment/BIN/card: swap «мёртвая карта» / declined-card / ban → Active Pro / «на своём аккаунте»; calm badge prop
  → regenerate t2i-batch.json → ONE new createTask → poll
  → still 422 after that one soften+recreate → KIE API BLOCKER
```

Rules:

- Do **not** fall back to sync MCP `gpt-image-2` when `KIE_API_KEY` is set (even after 422).
- First 422 ≠ permanent `KIE API BLOCKER` if a controlled rewrite + one recreate is still available.
- Soften is **once**; do not loop prompt variants / billed jobs.
- Proactive soft stake on marketplace+Cursor, AI-video, and payment/BIN/card avoids burning the one soften slot on an avoidable first 422 (INC-20260718-2035, INC-20260720-1241, INC-20260726-0814).

Do **not**:

- blind-retry `createTask` while `state=waiting` / `generating`
- poll a failed `taskId` forever hoping it flips to success
- treat the first 500 «try again later» as a permanent blocker before the controlled recreate
- treat client `--max-wait` exhaustion alone as a permanent blocker without one final `recordInfo` (INC-20260730-0834); late terminal 500 must enter the max-1 recreate path
- after 500×2 / `--max-create-retries` exhausted: raise Cover retries, rewrite prompt/batch for «quality», invent a third create, or MCP — instead Director same-batch re-run when healthy + Cover apply-only (B102–B106 / B116 / B117)
- treat the first 400 «image fetch failed» as permanent before the File Upload recreate
- treat the first 422 «sensitive» as permanent before one prompt soften + recreate
- treat the first pre-`taskId` TCP / Connection reset as a permanent blocker before one same-batch retry
- patch and commit live Kie tempfile URLs into `t2i-batch.json`
- switch to MCP while `KIE_API_KEY` is set after any recoverable Kie fail (500 / 400 / 422 / pre-taskId connection reset)

## Guardrails

- One API task per article cover run (plus at most one pre-taskId connection-reset retry and/or one 500-recreate and/or one File Upload recreate and/or one agent 422 soften+recreate), not four separate images.
- **Forbidden quality multi-gen (INC-20260724-2120):** after a successful URL, do **not** createTask again because host/sticky/style looks wrong. Visual QA is skip-default and must not trigger Cover redo. Only Kie API terminal fails / pre-taskId transport reset above allow another billed gen.
- `input_urls` is required; text-only generation is a cover blocker.
- Do not retry createTask blindly after a network ambiguity if a `taskId` is known; poll the known task. Exception: after explicit terminal `fail` with 500 / «try again later» (including late terminal 500 discovered by the final `recordInfo` after `--max-wait`), or 400 image-fetch → File Upload, or agent 422 soften+recreate, or pre-`taskId` Connection reset (no task record), create a **new** task once.
- MCP sync is not a peer alternative when `KIE_API_KEY` is set; use Kie API only.
