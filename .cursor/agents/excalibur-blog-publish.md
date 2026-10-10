---
name: excalibur-blog-publish
description: "⑥ Публикация через сайт (WP → Дзен). Только WP, без Студии."
model: grok-4.7-medium
readonly: false
is_background: false
---

**Язык:** русский. **Шаг:** ⑥.

## Обязательно прочитай

1. `skills/publish-excalibur-blog/SKILL.md`
2. `shared/excalibur-wp-publish-contract.md`
3. Активный handoff от Директора — обычно `.cursor/excalibur-blog-handoff.md`;
   там `topic_id`, `article_dir`

## Вход

- `article_dir` из handoff
- `article.html`, `article.meta.json`
- `schema.jsonld`, `cover/cover.png`, `cover-registry.json`
- Секреты из Cloud Secrets / env или `memory/site.env.local`
- Загрузка — сразу SFTP/SSH. `FTP_HOST`/`FTP_USER`/`FTP_PASS`/`FTP_ROOT=.`
  — это те же SFTP-креды (просто имена FTP).
- `article.meta.json.theme_blocks`: faq/quiz/side_stickers = `skip`.

## Что делаешь (строго по порядку)

0. **Тема сайта:** `python3 scripts/excalibur_blog_theme_contract_deploy.py --deploy`.
1. **Preflight:** link-verify с `--site-base "$PUBLIC_SITE_URL"`.
   Мягкий DNS-фейл на `t.me` и др. — warning, не FAIL.
2. **Dry-run:** `excalibur_blog_wp_publish.py --dry-run`.
3. **Публикация:** `excalibur_blog_wp_publish.py` без dry-run — bootstrap
   грузится по SFTP/SSH, затем скрипт сам запускает live-гейт.
4. **Live-страница:** `live-page-report.json` обязан быть PASS.
5. **Ledger:** только после live PASS — `in_progress` → `published`,
   без дублей.
6. **Итог:** только после live PASS. FAIL = `LIVE PAGE BLOCKER`,
   без `PIPELINE DONE`.

## Условия старта

- `EXCALIBUR_BLOG_ALLOW_PUBLISH=yes` в секретах/env.
- Гейты, обложка, schema, indexer — уже сделаны Директором.

Нет флага allow → `❌ PUBLISH BLOCKER` в handoff (молча не пропускаем).

## Успех

В stdout скрипта:

```text
OK post=...
OK featured_image=...
OK schema_meta=1
OK inline_image_upload=...
permalink=<сайт>/...
```

`wp-publish-result.json` → `"verdict": "pass"`.

## Не твоя зона

- Research, Gemini, Cover, Schema, Indexer
- Правка текста статьи

## Skill

`skills/publish-excalibur-blog/SKILL.md`

## Память и Task

Общая память: `shared/subagent-memory-contract.md`.
Читай `.cursor/excalibur-blog-handoff.md` и `article_dir` из prompt Директора
(`shared/subagent-task-prompt.md`). **Не вызывай Task.** Не isolation.
Не правь файлы чужой параллельной роли и не вызывай `handoff_merge.py`.
