# Excalibur BLOG — карта задач

Директор **не** Task на себя. Роли — `Task(excalibur-blog-*)`.

```text
[Д] Директор (чат / оркестратор)
  ├─ Task scout / viral-06 (ViralDzen) при needs_scout
  ├─ shell: today + research_start (+ titles-only)
  ├─ Task research → Task Gemini Writer (3.8 Flash, весь русский текст)
  ├─ shell: pipeline_canon --stamp + html_linter
  │         (gemini_article_gate — один раз после materialize Writer)
  ├─ Task schema ‖ Task cover (только отдельная обложка)
  ├─ Task inline-visuals (скрины + максимум одна схема в BODY)
  ├─ Task indexer (llms only) → Task publish (WP)
  └─ Task content-learner → Task fixer(open only) → merge_to_main → purge
```

Cloud cost: `shared/cloud-cost-rules.md`. Память: `shared/subagent-memory-contract.md`.

## Кто трогает текст

| Роль | Проза |
|------|-------|
| **Gemini (Writer Task, 3.8 Flash)** | Весь русский → `gemini-article.json` / `article.html` / description-brief / cover-text |
| **Sol** | DISABLED |
| Cover | Только `cover/cover.png` — featured image |
| Inline Visuals | Только `<figure>` внутри BODY и PNG; строки уже в JSON Writer |

## Правила

1. Gemini → JSON + materialize + gemini_article_gate (один раз)
2. `pipeline_canon.py --stamp` + html_linter
3. Cover Sunburst i2i (обложка) + Inline Visuals (картинки в BODY)
4. Indexer; Publish WP only
