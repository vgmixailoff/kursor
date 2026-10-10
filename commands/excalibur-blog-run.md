---
description: Excalibur BLOG — живой прогон статьи через оркестратор и субагентов.
---

# Excalibur BLOG — запуск пайплайна

«Запусти Excalibur BLOG для темы **B01**»

## Параметры

- `topic_id`: B01 | all | P0-only
- `publish`: yes | no (default yes)

## Пайплайн (gemini-evening-v1)

```text
Scout?/viral-06 → Research → Gemini(Writer)
→ Schema‖Cover (отдельная обложка) → Inline Visuals (скрины и схемы в BODY)
→ Indexer (llms-only) → Publish (WP) → Content-learner → Fixer? → merge → purge
```

- **Writer** (`Task`, Gemini 3.8 Flash) → TITLE, DESCRIPTION, BODY, COVER, INLINE в одном JSON.
- **Sol** выключен — никто поверх не переписывает.
- Materialize → `description-brief.json` (Дзен/RSS карточка) и `cover/cover-text.json`.
- Агентов Title / Description / Cover-text нет.
- Тела старых статей и live-сайт не открывать.
- Research не пишет H2/FAQ/шаги.
- Publish BLOCK на служебном английском и старом pipeline.

Cloud UI / cost: `CLOUD-AUTOMATION.md` + `shared/cloud-cost-rules.md`.

## Оркестратор

Директор — основной агент чата (не Task на себя). Роли — `Task`.
Сценарий: [skills/director-excalibur-blog/SKILL.md](../skills/director-excalibur-blog/SKILL.md).

Handoff runtime: `.cursor/excalibur-blog-handoff.md`
Общая память: `shared/subagent-memory-contract.md`
