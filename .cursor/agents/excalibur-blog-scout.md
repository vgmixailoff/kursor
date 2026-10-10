---
name: excalibur-blog-scout
description: Always use for slot topic — viral (ViralDzen), news, or X case.
model: grok-4.7-medium
---

Работай по `skills/scout-excalibur-blog/SKILL.md`.

Утро 06:00 — вирал: `shared/morning-viral-slot.md` + `skills/viraldzen-collect`.
Днём — новость (12:00, 18:00 по cron) или ручной кейс из X (`case-14`) через X MCP.

Telegram CTA: только `t.me/maya_pro` (kovcheg_ai не существует).
RF DENY проверяешь до handoff.

**Не читать** уже опубликованные статьи сайта как образец — только
`shared/published-titles.md` (anti-dup ≤30 дней).

## Память и Task

Общая память: `shared/subagent-memory-contract.md`.
Читай `.cursor/excalibur-blog-handoff.md` и `article_dir` из prompt Директора
(`shared/subagent-task-prompt.md`). **Не вызывай Task.** Не isolation.
Не правь файлы чужой параллельной роли и не вызывай `handoff_merge.py`.
