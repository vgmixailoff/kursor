---
name: publish-excalibur-blog
description: Публикация выпуска через сайт (WP → Дзен) — пост, обложка, инлайны, schema, ledger.
---

# Excalibur BLOG — Publish (шаг ⑥)

**Когда:** после Indexer (шаг ⑤), когда гейты PASS, обложка, schema и
llms готовы. Директор вызывает эту роль через Task в том же ране.

## Жёсткий гейт перед публикацией

До загрузки проверь `article.meta.json.theme_blocks`: faq, quiz и
side_stickers = `skip`. После загрузки обязателен
`excalibur_blog_live_page_gate.py` по `shared/live-page-contract.md`.
Только live-page PASS разрешает publish PASS / PIPELINE DONE.

Если live-гейт ругается на FAQ только из-за тире (`--` ↔ `—`) — это
WP wptexturize, не ошибка schema. Не переписывай `schema.jsonld` ради
этого; сверь локальную schema со статьёй и перезапусти гейт.

## Твоя зона (скрипт — инструмент, не замена тебе)

Ты читаешь контракт и сам принимаешь решения. Ты обязан понимать:

1. **URL постов на сайте = `/{slug}/`**, не `/blog/{slug}/`.
2. **Медиабиблиотека WP** для каждой картинки (обложка + инлайны):
   - alt — осмысленный русский текст из registry / `<img alt>`
   - подпись (caption) — тот же осмысленный alt
   - описание — alt (+ раздел H2 для инлайнов)
   - В dry-run смотри `cover_media` / `inline_media` — все флаги `true`.
     Если `false` — чини registry/HTML **до** публикации, не надейся на скрипт.
3. Если HTML менялся после Indexer — перезапусти `link_verify`.
4. **`llms.txt` на сайте** — после публикации задеплой
   (`excalibur_blog_llms_deploy.py` или `--deploy-llms`).
5. Скрипт подстраховывает (не пустит без гейтов), но ответственность на тебе.

## Контракт

`shared/excalibur-wp-publish-contract.md`

## Условия старта (все обязательны)

| Проверка | Файл / env |
|----------|------------|
| Гейты | `structure-gate.json` → PASS (canon, links, CTA, gemini, description) |
| Ссылки | `link-verify.json` → pass |
| Обложка | `cover/cover.png` + alt в `cover-registry.json` |
| Schema | `schema.jsonld` + `schema-gate.json` PASS |
| Канон | `pipeline_canon=gemini-evening-v1`, `editorial_swarm=false` |
| Доступы | `FTP_HOST`/`FTP_USER`/`FTP_PASS`/`FTP_ROOT=.` + `PUBLIC_SITE_URL` |
| Флаг | `EXCALIBUR_BLOG_ALLOW_PUBLISH=yes` |

Пароль FTP = пароль SFTP. Сразу SFTP с `FTP_*`; отдельный `SSH_PASS` не
требуй. Root = `.` (домашняя папка логина).

**Ожидаемый WARN (не инцидент):** `--env-check` → `root: configured-non-dot`
и/или SFTP ENOENT → auto-retry `.` — значит в Cloud Secret `FTP_ROOT`
стоит путь панели. Publish пройдёт через fallback; в handoff одна строка
«expected WARN FTP_ROOT non-dot». Чинит человек: Secrets `FTP_ROOT=.`.

Нет флага allow → **`❌ PUBLISH BLOCKER`** (молча не пропускаем).

### Перезаливка медиа (уже опубликованный пост)

Когда нужно только обновить картинки на живом посте (hotfix обложки):

```bash
python3 scripts/excalibur_blog_link_verify.py \
  memory/blog/articles/<topic_id>-<slug>/article.html \
  -o memory/blog/articles/<topic_id>-<slug>/link-verify.json \
  --site-base "$PUBLIC_SITE_URL"

python3 scripts/excalibur_blog_wp_publish.py \
  --article-dir memory/blog/articles/<topic_id>-<slug> \
  --media-refresh --dry-run

python3 scripts/excalibur_blog_wp_publish.py \
  --article-dir memory/blog/articles/<topic_id>-<slug> \
  --media-refresh
```

`--media-refresh` требует ledger `status=published` для `topic_id` и
свежий link-verify. Это **не** `--skip-gates`.

## Порядок работы

### 0. Тема сайта

```bash
python3 scripts/excalibur_blog_theme_contract_deploy.py --deploy
```

Идемпотентно, с backup. Без этого live-гейт заблокирует generic
FAQ/quiz/stickers темы.

### 1. Проверка ссылок

```bash
python3 scripts/excalibur_blog_link_verify.py \
  memory/blog/articles/<topic_id>-<slug>/article.html \
  -o memory/blog/articles/<topic_id>-<slug>/link-verify.json \
  --site-base "$PUBLIC_SITE_URL"
```

`link-verify.json` → pass. Иначе FIX или BLOCKER.

Скрипт ходит по живому сайту, но файл пишет git-safe: внутренние URL с
`{{SITE_BASE}}`, без живого домена.

Мягкие соц-хосты (`t.me` / `telegram.me` / `wa.me` / `vk.com` /
`vkvideo.ru`): DNS-ошибки и таймауты → warning + `ok: true`, не FAIL.
Не удаляй `t.me` из статьи из-за такого флейка.

**Жёсткий denylist (не soft-pass):** `www.make.com/*`, `npmjs.com/*`
(пакеты → `https://registry.npmjs.org/<pkg>` или GitHub),
`openai.com/index/*` (→ Wayback / пресса того же дня / GitHub;
сабдомены `deploymentsafety` / `platform` / `cdn` не банить),
`securityweek.com/*` (→ Infosecurity / блог вендора / GitHub),
`cursor.com/automations*`, `cursor.com/dashboard/*`. При FAIL — замени
href в `article.html` (текст Gemini не переписывай) и перезапусти гейт.

### 2. Проверка окружения

```bash
python3 scripts/excalibur_blog_wp_publish.py --env-check
```

Проверяет флаг, публичный URL и SFTP-переменные без вывода секретов.

### 3. Dry-run

```bash
python3 scripts/excalibur_blog_wp_publish.py \
  --article-dir memory/blog/articles/<topic_id>-<slug> \
  --dry-run
```

Смотри: slug, заголовок, размер payload, флаги медиа.

### Плейсхолдер сайта

Indexer/schema/cover оставляют `{{SITE_BASE}}` в коммитнутых артефактах
(не живой домен): `schema.jsonld`, llms, `link-verify.json`,
`cover/t2i-batch.json`, `wp-publish-result.json`. Скрипт раскрывает
`{{SITE_BASE}}` → `PUBLIC_SITE_URL` только в момент публикации.
Ledger пишет путь `/slug/` без домена.

### 4. Публикация

```bash
python3 scripts/excalibur_blog_wp_publish.py \
  --article-dir memory/blog/articles/<topic_id>-<slug>
```

Скрипт:
- грузит bootstrap сразу через **SFTP/SSH** (порт 22), без FTP-попытки;
- при ENOENT настроенного root один раз пробует `.` (expected WARN);
- создаёт/обновляет пост;
- загружает обложку и пишет в медиабиблиотеку alt/подпись/описание/title;
- загружает все локальные инлайн-`<img>`, пишет те же meta и подменяет
  `src` на WP media URL;
- пишет post meta `_excalibur_blog_schema_jsonld`;
- по `--deploy-llms` грузит `llms.txt` в корень WP.

### 5. Fallback через WebFetch

Если локальный HTTP-триггер bootstrap упал (timeout):

1. Скрипт печатает `=== FALLBACK_TRIGGER_URL ===`.
2. Открой URL через WebFetch и сохрани ответ в `memory/webfetch-response.txt`.
3. Скрипт продолжит и прочитает ответ из файла.

Не останавливайся на первом timeout.

### 6. После публикации

| Файл | Что делать |
|------|------------|
| `wp-publish-result.json` | создаёт скрипт (verdict pass/fail) |
| `memory/blog/wp-publish-log.md` | runtime-лог (в git не коммитим) |
| `shared/published-articles.md` | строка topic_id: in_progress → published (date/url), без дублей |
| `memory/pipeline-fix-queue.md` | если дописал инцидент — закоммить вместе с ledger |
| handoff | блок `=== EXCALIBUR BLOG PUBLISH ===` + permalink в `PIPELINE DONE` |

### 7. Память после публикации (HARD)

Перелинковки нет. После PASS обнови заголовки и **удали** локальный
`article_dir` — картинки и тексты в git не оставляем:

```bash
python3 scripts/excalibur_blog_published_titles.py --days 30
python3 scripts/excalibur_blog_memory_purge.py --drop-topic <topic_id>
```

Долгосрочная память = только заголовки в `shared/published-titles.md`
(30 дней).

## Блок итога (шаблон)

```text
=== EXCALIBUR BLOG PUBLISH ===
topic_id:
slug:
article_dir:
publish_date:
verdict: PASS|FAIL
permalink:
post_id:
featured_image:
inline_images:
schema_meta: ok|fail
blockers:
```

## Блокеры

- `❌ PUBLISH BLOCKER` — гейты не PASS, нет обложки/schema/доступов/флага
- `❌ PUBLISH FAIL` — скрипт вернул fail (смотри `raw_output`)

## Запрещено

- Писать или переписывать текст статьи
- Генерировать обложку/schema с нуля
- Пропускать dry-run
- `--skip-gates` для перезаливки медиа
- Завершать пайплайн без записи в `published-articles.md` при успехе
