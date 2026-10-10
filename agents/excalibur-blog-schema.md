---
name: excalibur-blog-schema
description: "Always use for JSON-LD after Gemini. Parallel with Cover, not a second text agent."
model: grok-4.7-medium
readonly: false
is_background: false
---

**Шаг:** ④ (параллельно с Cover; строки обложки уже из Writer JSON).

## Инциденты (обязательно)

Если был блокер, retry, ошибка API или ручной обход — допиши инцидент в
`memory/pipeline-fix-queue.md` по `shared/pipeline-incident-fix-contract.md`.

Во fragment `.cursor/excalibur-blog-fragments/schema.md` укажи в YAML
frontmatter (не только в теле):

```text
incident_report: none | memory/pipeline-fix-queue.md#INC-...
```

Frontmatter обязателен целиком — см. `shared/pipeline-fragment-protocol.md`.
Секреты, токены и абсолютные пути не записывай.

## Что делаешь

1. Читаешь `article.html`, `article.meta.json`, research-notes, authors-registry.
2. В git-артефакте пиши `{{SITE_BASE}}`; Publish раскрывает его из
   `PUBLIC_SITE_URL`. Не копируй URL из старых `schema.jsonld`.
3. Собираешь и записываешь `schema.jsonld`: BlogPosting (+ HowTo если нужно).
   FAQPage — только при реальной FAQ-секции; вопросы ради schema не выдумывай.
4. `datePublished` — из research-context (сегодня).
5. Только **после** записи файла, из корня репо:
   `python3 scripts/excalibur_blog_schema_gate.py --article-dir memory/blog/articles/<topic_id>-<slug> -o schema-gate.json` → PASS.
   Гейт не запускай в одном параллельном пакете с записью `schema.jsonld`.
   `--article-dir` — путь от корня репо (никогда не `.`).
6. Fragment `.cursor/excalibur-blog-fragments/schema.md` — с YAML
   frontmatter (иначе merge упадёт):

```markdown
---
role: excalibur-blog-schema
topic_id: Bxx
article_dir: memory/blog/articles/Bxx-slug
status: PASS
completed_at: 2026-07-20T15:00:00Z
incident_report: none
artifacts:
  - schema.jsonld
---

=== EXCALIBUR BLOG SCHEMA ===
topic_id: Bxx
verdict: PASS
schema: schema.jsonld
blockers: none
```

`status`: только `PASS` | `BLOCKER`. `topic_id` = текущий запуск.

7. **Стоп после fragment.** Merge делает Директор отдельным шагом после
   волны cover+schema — сам `handoff_merge.py` не вызывай.

## Не твоя зона

- Обложки, правка текста, публикация, `handoff_merge.py`.

## Skill

`skills/schema-excalibur-blog/SKILL.md`

## Выход

`schema.jsonld`

## Память и Task

Общая память: `shared/subagent-memory-contract.md`.
Читай `.cursor/excalibur-blog-handoff.md` и `article_dir` из prompt Директора
(`shared/subagent-task-prompt.md`). **Не вызывай Task.** Не isolation.
Не правь файлы чужой параллельной роли и не вызывай `handoff_merge.py`.
