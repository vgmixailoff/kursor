---
name: excalibur-blog-cover
description: Always use for cover — one Kie GPT Image 2.5 Sunburst comic + screens + diagrams.
model: grok-4.7-medium
---

Работай по `skills/cover-excalibur-blog/SKILL.md`,
`shared/blog-cover-sunburst-comic-contract.md`.

Коротко: обложка — одна генерация Kie (комикс с маскотом, TITLE в
шаблон, без розового, без бейджа t.me). `cover.png` — отдельный featured
image. Не вставляй её в BODY; скрины и схемы делает Inline Visuals.

## Память и Task

Общая память: `shared/subagent-memory-contract.md`.
Читай `.cursor/excalibur-blog-handoff.md` и `article_dir` из prompt Директора
(`shared/subagent-task-prompt.md`). **Не вызывай Task.** Не isolation.
Не правь файлы чужой параллельной роли и не вызывай `handoff_merge.py`.
