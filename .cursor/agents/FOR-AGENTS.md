# Excalibur BLOG — роли

Карта: [shared/pipeline-task-map.md](../../shared/pipeline-task-map.md)

Стоимость: [shared/cloud-cost-rules.md](../../shared/cloud-cost-rules.md) —
один ран; роли через `Task()`; `/in-cloud` запрещён. Fixer — только при
открытых инцидентах.

Слоты МСК: 06 вирал (ViralDzen) / 10 новость / 14 кейс / 18 новость.
См. `CLOUD-AUTOMATION.md`, `shared/cursor-subagents.md`.

## Директор (оркестратор, не Task на себя)

`excalibur-blog-director.md` + skill `director-excalibur-blog`

## Роли (Task в том же ране)

| # | Роль | Что делает | Модель |
|---|------|------------|--------|
| 🔍 | scout | Тема по слоту | grok-4.7-medium |
| ① | research | Факты (+ official_screenshot_urls) | grok-4.7-medium |
| ② | writer=Gemini | весь русский: TITLE, DESCRIPTION, BODY, COVER, INLINE | gemini-3.8-flash |
| ②b | **sol** | **выключен** | — |
| ④b | schema | JSON-LD | grok-4.7-medium |
| ④c | cover | Только отдельная обложка Kie | grok-4.7-medium |
| ④d | inline-visuals | Скрины и одна полезная схема внутри BODY | grok-4.7-medium |
| ⑤ | indexer | llms | grok-4.7-medium |
| ⑥ | publish | Только WP | grok-4.7-medium |
| ⑦ | content-learner | Метрика → урок в merge | grok-4.7-medium |
| ⑦b | fixer | Инциденты (**только open**) | grok-4.7-medium |

Title / Description / Cover-text **удалены**. Writer отдаёт один JSON.
После Gemini → shell `pipeline_canon --stamp` + html_linter
(`gemini_article_gate` один раз после Writer; opening_meta / sol_rewrite — не в рантайме).
