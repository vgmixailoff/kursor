# Pipeline fix queue

Активная очередь инцидентов. Храним **только open**; закрытые/noted записи
не храним (история — в git log и заголовках published-titles).

Канон: gemini-evening-v1 (Scout?/viral-06 → Research → Gemini Writer
→ Schema‖Cover(обложка) → Inline Visuals(картинки в BODY) → Indexer
→ Publish → Content-learner → Fixer?).

Формат записи:

```text
## INC-YYYYMMDD-HHMM — <коротко>
status: open
topic_id: B…
symptom: …
```

Fixer запускается только если `rg '^status: open' memory/pipeline-fix-queue.md`
что-то нашёл. Пусто → fixer-прохода нет.

## INC-20260916-1153-content-learner-metrika-query-error
status: needs-human
run_date: 2026-09-16
role: excalibur-blog-content-learner
topic_id: B172
article_dir: memory/blog/articles/B172-cursor-nokia-razobrala-50-mln-strok
severity: blocker
category: api

### What went wrong
- `python3 scripts/excalibur_blog_metrika_fetch.py --days 30 --ingest` → METRIKA API HTTP 400 `query_error`: "Query is too complicated. Please reduce the date interval or sampling."
- Credentials are present: Management API `GET /management/v1/counter/{id}` HTTP 200 (permission=own, status=Active, activity_status=high, type=simple, pro=0).
- Reports API fails for the same counter on every probed query: `--days 30` default, `--limit 500`, `date1=today`, `yesterday`, 1-day, 7-day, 14-day, 2025-09-16, no dimensions (`ym:s:visits` only), `preset=sources_summary`, `stat/v1/data/bytime`, `accuracy=full|medium|low|1`.
- Counter `code_status=CS_ERR_UNKNOWN` (code not verified by Metrika). Not a missing-env/token case (would be HTTP 401/403, not 400 query_error).
- No `memory/analytics/metrika-latest.json` written; ingest did not run.

### How the agent recovered this run
- Did not invent Metrika rows or CTR/retention causality.
- Lesson recorded as LOW_SAMPLE (B172 age 0d) + METRIKA FEEDBACK BLOCKER.
- Durable content rules / writer prompt: unchanged.

### Durable fix needed before next run
- Human: restore Reports API for this counter (install/verify JS snippet so `code_status` leaves CS_ERR_UNKNOWN; GDPR/agreement; Yandex support if Active + query_error remains). Repo cannot flip Metrika `code_status`.
- Do not mark Content-learner Metrika as optional; next run must still call `--days 30 --ingest` once.

### Suggested files to inspect/change
- `scripts/excalibur_blog_metrika_fetch.py`
- `skills/content-learner-excalibur-blog/SKILL.md`
- Cloud Secrets: `YANDEX_METRIKA_OAUTH_TOKEN`, `YANDEX_METRIKA_COUNTER_ID` (token already authorized: Management HTTP 200)

### Secrets
- none recorded

### Fixer resolution
status: needs-human
fixed_at: 2026-09-16
reason:
- Reports API HTTP 400 `query_error` + Management `code_status=CS_ERR_UNKNOWN` is a Yandex counter condition. Script limit/accuracy fallback cannot restore data (confirmed live: Management 200 Active + Reports 400 even with credentials present).
fix_summary:
- Script now preflights Management API, classifies `query_error` / `CS_ERR_UNKNOWN` as JSON `METRIKA FEEDBACK BLOCKER` with `do_not_retry: true` (no raw HTTP dump, no token/counter id).
- Content-learner skill/agent/contract: one `--days 30 --ingest` call; do not probe today/accuracy/preset/bytime when `do_not_retry` is set. Metrika remains mandatory.
needed_decision_or_secret:
- Install/verify Metrika JS on the live site until `code_status` is not CS_ERR_UNKNOWN.
- If snippet is already on the site: Metrika UI GDPR/agreement + Yandex support. Token/counter id already match an Active counter (not a missing-env case).
files_changed:
- `scripts/excalibur_blog_metrika_fetch.py`
- `tests/test_metrika_fetch.py`
- `skills/content-learner-excalibur-blog/SKILL.md`
- `.cursor/skills/content-learner-excalibur-blog/SKILL.md`
- `agents/excalibur-blog-content-learner.md`
- `.cursor/agents/excalibur-blog-content-learner.md`
- `shared/content-learning-contract.md`
checks_run:
- `python3 -m py_compile scripts/excalibur_blog_metrika_fetch.py tests/test_metrika_fetch.py`
- `python3 -m unittest tests.test_metrika_fetch -v` (9 tests OK)
- `--dry-run-ledger` PASS
- live `--days 30` → exit 2 JSON BLOCKER reason=query_error code_status=CS_ERR_UNKNOWN do_not_retry=true (token/counter not in stdout)
commit: cda89743

### Reproduced
- 2026-09-22 topic B194, один вызов `--days 30 --ingest`: тот же JSON BLOCKER, reason=query_error, HTTP 400, code_status=CS_ERR_UNKNOWN, counter_status=Active, permission=own, do_not_retry=true. Повторных запросов не было. `memory/analytics/metrika-latest.json` не записан.
- Урок LESSON-20260922-0753-B194-auto-mode-low-sample: мало данных, без причинности, durable_applied none.
- status остаётся needs-human: репозиторий не чинит code_status. Новый open не открываю, чтобы Fixer не крутил тот же вывод.
- 2026-09-22 topic B195, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 194, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Урок LESSON-20260922-1551-B195-worker-previews-low-sample: мало данных, без причинности, durable_applied none. Новый open не открываю.
- 2026-09-23 topic B196, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 195, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B196 нет (age 0d). Урок LESSON-20260923-0354-B196-opus-price-low-sample: мало данных, без причинности, durable_applied none. Новый open не открываю.
- 2026-09-24 topic B201, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 195, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B201 нет (age 0d). Урок LESSON-20260924-0801-B201-rollouts-low-sample: мало данных, без причинности, durable_applied none. Новый open не открываю.
- 2026-09-26 topic B208, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 195, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B208 нет (age 0d). Урок LESSON-20260926-0358-B208-astra-low-sample: мало данных, без причинности, durable_applied none. Заметка: DESCRIPTION один раз содержала «и как», Writer поправил карточку, canon PASS; в meta_ab description_* старая фраза ещё лежит, в WP excerpt идёт meta.description без маркера. Повторного урока нет, правила не менял. Новый open не открываю.
- 2026-09-27 topic B212, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 196, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B212 нет (age 0d). Урок LESSON-20260927-0744-B212-prompt-audit-low-sample: мало данных, без причинности, durable_applied none. Заметка: html linter PASS после снятия code-тегов, один раз, правила Writer не менял. Новый open не открываю.
- 2026-09-27 topic B213, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 196, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B213 нет (age 0d). Урок LESSON-20260927-1132-B213-token-harness-low-sample: мало данных, без причинности, durable_applied none. Заметка: папка статьи снята, gemini-article-gate.json нет (evidence SKIP). Новый open не открываю.
- 2026-09-27 topic B214, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 196, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B214 нет (age 0d). Урок LESSON-20260927-1541-B214-effort-low-sample: мало данных, без причинности, durable_applied none. Заметка: html linter один раз снял теги code, правила Writer не менял. Новый open не открываю.
- 2026-09-28 topic B219, один вызов `--days 30 --ingest`: JSON status BLOCKER, reason=query_error, HTTP 400, code_status=CS_ERR_UNKNOWN, counter_status=Active, permission=own, do_not_retry=true. Повторов today/days 1/accuracy не было. `memory/analytics/metrika-latest.json` не записан. Строки B219 нет (age 0d). Урок LESSON-20260928-1547-B219-cf-cli-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 4260). Новый open не открываю.
- 2026-09-29 topic B220, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 208, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B220 нет (age 0d). Урок LESSON-20260929-0356-B220-openai-pause-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 4783). Новый open не открываю.
- 2026-09-29 topic B222, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 208, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B222 нет (age 0d). Урок LESSON-20260929-1547-B222-openshell-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 4271). В ledger вечерний выпуск — B222: B221 уже занят Turnstile Spin. Новый open не открываю.
- 2026-10-01 topic B230, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 209, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B230 нет (age 0d). Урок LESSON-20261001-1547-B230-waitlist-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 4200). Новый open не открываю.
- 2026-10-06 topic B231, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B231 нет (age 0d). Урок LESSON-20261006-0055-B231-harness-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5841, description ≠ title, CTA только t.me/maya_pro). Новый open не открываю.
- 2026-10-06 topic B232, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B232 нет (age 0d). Урок LESSON-20261006-0647-B232-plan-mode-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5300, description ≠ title, CTA только t.me/maya_pro). Новый open не открываю.
- 2026-10-06 topic B233, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B233 нет (age 0d). Урок LESSON-20261006-1232-B233-together-link-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 6152, description ≠ title, CTA только t.me/maya_pro). Publish PASS. Новый open не открываю.
- 2026-10-06 topic B234, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B234 нет (age 0d). Урок LESSON-20261006-1856-B234-cowork-lid-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5758, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21037. Новый open не открываю.
- 2026-10-07 topic B235, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B235 нет (age 0d). Урок LESSON-20261007-0648-B235-dots-computer-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5940, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21043. Новый open не открываю.
- 2026-10-07 topic B237, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B237 нет (age 0d). Урок LESSON-20261007-1851-B237-clef-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5651, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21054. Новый open не открываю.
- 2026-10-08 topic B238, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B238 нет (age 0d). Урок LESSON-20261008-0654-B238-wiki-agents-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5782, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21060. Новый open не открываю.
- 2026-10-08 topic B239, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B239 нет (age 0d). Урок LESSON-20261008-1258-B239-haiku-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 6405, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21066. Новый open не открываю.
- 2026-10-08 topic B240, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B240 нет (age 0d). Урок LESSON-20261008-1837-B240-gemini-mail-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 5488, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21072. Title 83 при h1 max 70 — второй раз после B239, правило не менял. Новый open не открываю.
- 2026-10-08 topic B241, один вызов `--days 30 --ingest`: JSON status PASS (не BLOCKER), rows 211, actionable 0, do_not_retry false. Reports API ответил, HTTP 400 query_error на этом прогоне нет. code_status по-прежнему CS_ERR_UNKNOWN, counter_status Active. Строки B241 нет (age 0d). Урок LESSON-20261008-2055-B241-copilot-sandbox-low-sample: мало данных, без причинности, durable_applied none. Гейт PASS (тело 6307, description ≠ title, CTA только t.me/maya_pro). Publish PASS, post_id 21076. Title 81 при h1 max 70 — третий раз после B239 и B240, правило не менял. Новый open не открываю.
