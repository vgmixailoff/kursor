---
name: schema-excalibur-blog
description: Schema — BlogPosting (+ FAQPage при реальной FAQ), реестр авторов.
---

# Excalibur BLOG — Schema

## Вход

- `article.html`, `article.meta.json`, `research-notes.md`
- `shared/authors-registry.json`
- `PUBLIC_SITE_URL` из Cloud Secrets для публикации; в JSON-LD пиши плейсхолдер `{{SITE_BASE}}`

## Адрес сайта (обязательно)

1. Для `schema.jsonld` не нужен домен из старого брифа: используй
   `{{SITE_BASE}}`. Publish раскрывает его из `PUBLIC_SITE_URL`.
2. **Запрещено** копировать `Organization.url` / `@id` из соседних
   `schema.jsonld` — там может быть чужой или битый host.
3. **Запрещено** писать в файл литерал `[REDACTED]` — это маска вывода,
   не URL.
4. В git-артефактах — плейсхолдер `{{SITE_BASE}}` вместо живого домена
   (secret scan блокирует commit с доменом). Publish раскрывает
   `{{SITE_BASE}}` → `PUBLIC_SITE_URL` только в момент отправки в WP.
5. Канонический URL статьи: `{{SITE_BASE}}/<slug>/`. Без `/blog/` —
   WordPress публикует в корне.

## Задача

1. BlogPosting: headline, datePublished (сегодня из research-context),
   author Person + sameAs.
2. FAQPage — только если в статье есть настоящая секция FAQ. Нет FAQ —
   не создавай schema ради schema.
   - Видимый FAQ = только пары `<h3>вопрос?</h3><p>ответ</p>` в секции
     «Частые вопросы».
   - `acceptedAnswer.text` = **только первый `<p>`** после каждого `<h3>`
     (простой текст, без HTML). Хвостовые CTA-абзацы в FAQPage не входят.
   - Гейт нормализует пробелы после ссылок — пиши естественный текст,
     не подгоняй JSON под артефактный пробел.
3. HowTo / Review — только если формат статьи того требует.
4. **Сначала запиши, потом гоняй гейт:** полностью запиши `schema.jsonld`
   на диск, дождись завершения записи, и только потом отдельным шагом
   запускай гейт. Нельзя ставить запись и гейт в один параллельный пакет —
   гейт читает диск и не найдёт файл.

```bash
# из корня репо — не cd в article_dir
python3 scripts/excalibur_blog_schema_gate.py \
  --article-dir memory/blog/articles/<topic_id>-<slug> \
  -o schema-gate.json
```

**Жёстко:** `--article-dir` — путь от корня репо (никогда не `.`).
**Жёстко:** `-o` — только bare `schema-gate.json` (пишется внутрь
`--article-dir`).

Статус обязан быть `PASS` (валидный JSON, без `[REDACTED]`).

## Fragment (обязательно)

После PASS запиши `.cursor/excalibur-blog-fragments/schema.md` по
`shared/pipeline-fragment-protocol.md` — **с YAML frontmatter**, иначе
merge упадёт. Шаблон — в `agents/excalibur-blog-schema.md`.
В frontmatter обязателен `topic_id` текущего запуска.

### Merge — не зона Schema

Schema пишет только fragment и останавливается. `handoff_merge.py`
вызывает Директор отдельным шагом после волны cover+schema. Нельзя
ставить запись fragment и merge в один параллельный пакет — merge
прочитает старый fragment прошлой темы.

## Выход

`memory/blog/articles/<topic_id>-<slug>/schema.jsonld`
