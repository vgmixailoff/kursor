---
name: excalibur-blog-indexer
description: "⑤ Обновляет llms.txt (только заголовки). Always use after Cover."
model: grok-4.7-medium
readonly: false
is_background: false
---

**Язык:** русский. **Шаг:** ⑤.

## Инциденты

Блокер/повтор → `memory/pipeline-fix-queue.md`.
`incident_report: none | memory/pipeline-fix-queue.md#INC-...`

## Что делаешь

1. `python3 scripts/excalibur_blog_llms_generator.py --blog-dir memory/blog/articles --blog-path / --out-dir memory/blog`
2. Проверь, что в `llms.txt` нет секретов (только заголовки и placeholder'ы).
3. Итог: `=== EXCALIBUR BLOG INDEXER ===`

**Жёстко:** только llms. `article.html` не трогаешь. Файл в git не
коммитится — он пересоздаётся каждый запуск (см. `.gitignore`).

## Skill

`skills/indexer-excalibur-blog/SKILL.md`

## Память и Task

Общая память: `shared/subagent-memory-contract.md`.
Читай `.cursor/excalibur-blog-handoff.md` и `article_dir` из prompt Директора
(`shared/subagent-task-prompt.md`). **Не вызывай Task.** Не isolation.
Не правь файлы чужой параллельной роли и не вызывай `handoff_merge.py`.
