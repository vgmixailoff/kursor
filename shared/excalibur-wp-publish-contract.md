# Excalibur BLOG — WordPress publish contract

## Future articles: theme suppression and live verification

`article.meta.json.theme_blocks` must set `faq`, `quiz`, `side_stickers` to
`skip`. The body contains exactly one topic-specific FAQ. After upload, run
`scripts/excalibur_blog_live_page_gate.py` per
`shared/live-page-contract.md`. `live-page-report.json` PASS is mandatory;
otherwise `LIVE PAGE BLOCKER` and no PIPELINE DONE.

Excalibur BLOG готовит артефакты локально; публикация — через `scripts/excalibur_blog_wp_publish.py` и SFTP bootstrap.

## Prerequisites

- `article.html`, `article.meta.json` (`pipeline_canon` stamp, `theme_blocks.*.skip`)
- `schema.jsonld` + `schema-gate.json` PASS
- `cover/cover.png` + `cover-registry.json` (alt)
- `link-verify.json` (verdict pass)
- Cloud Secrets / env vars или `memory/site.env.local` — SFTP доступ + `PUBLIC_SITE_URL` + `EXCALIBUR_BLOG_ALLOW_PUBLISH=yes`
- **Секреты:** `FTP_HOST` / `FTP_USER` / `FTP_PASS` (или `FTP_PASSWORD`) / `FTP_ROOT=.` — это **SFTP** под именами FTP. Отдельный SSH-пароль не нужен: `SSH_*` = те же значения. Transport всегда SFTP/SSH; plain FTP не вызывается.
- Env precedence: переменные окружения перекрывают `memory/site.env.local`.
- Root: канон `FTP_ROOT=.` (SFTP login cwd с `wp-load.php`). Пустой или `/` нормализуется в `.`.
- **Non-dot root (acknowledged_env):** если Cloud Secret `FTP_ROOT`/`SSH_ROOT` —
  путь панели хостинга, `--env-check` покажет `root: configured-non-dot` +
  `human_action` WARN; bootstrap/llms сделают ENOENT → auto-retry `.`
  (`dot_fallback_enabled`). Publish может PASS. Это **не** новый incident —
  нужен человек: Dashboard → Secrets → `FTP_ROOT=.` (и `SSH_ROOT=.` если
  задан). Код секреты не меняет (INC-20260807-2022).

## Скрипт

```bash
python3 scripts/excalibur_blog_link_verify.py \
  memory/blog/articles/B01-slug/article.html \
  -o memory/blog/articles/B01-slug/link-verify.json \
  --site-base https://example.com

python3 scripts/excalibur_blog_wp_publish.py \
  --article-dir memory/blog/articles/B01-slug
```

`--dry-run` — проверка payload без SFTP upload.

### Soft social link-verify (не FAIL)

Cloud egress часто ломает DNS/TLS к соцхостам и VK Video auth redirects.
`excalibur_blog_link_verify.py` soft-pass (warning + `ok: true`) для:

- hosts: `t.me` / `telegram.me` / `wa.me` / `vk.com` / `vkvideo.ru` /
  `max.ru` (+ `www.*`);
- DNS/timeout/unreachable без HTTP status (INC-20260713-2014);
- `vkvideo.ru` → `login.vk.ru` urllib «infinite loop» / synthetic HTTP 302
  (INC-20260806-1628).

Не soft-pass: product CDN 403 (`www.make.com`, `www.npmjs.com` /
`npmjs.com`, `openai.com/index/*`, `securityweek.com` /
`www.securityweek.com`, `cursor.com/dashboard/*` и т.п.) —
early denylist hard FAIL до live HTTP. Для npm-пакетов в статье:
`https://registry.npmjs.org/<pkg>` или GitHub repo (INC-20260807-0828),
не `www.npmjs.com/package/*`. Для постов OpenAI Blog (`openai.com/index/*`):
кликабельный primary = Wayback / same-day press / GitHub; канон URL —
в research notes (INC-20260809-1619). **Не** банить весь `*.openai.com`:
`deploymentsafety.openai.com` / `platform.openai.com` / `cdn.openai.com`
остаются allowed при HTTP 200. Для SecurityWeek (`securityweek.com/*`):
кликабельный primary = Infosecurity Magazine / vendor blog / GitHub;
канон URL в research notes; не полагаться на Wayback как sole primary
(archive.org часто 429; INC-20260810-2028).
CTA `vkvideo.ru/playlist/...` в статье оставлять — не вырезать из‑за soft flake.

## Что делает publish

1. **Preflight gates** (обязательно, иначе BLOCKER; emergency `--skip-gates`):
   - `link-verify.json` → `verdict: pass`
   - `schema.jsonld`, `schema-gate.json` PASS, `cover/cover.png`
   - `article.html` + `article.meta.json` с `pipeline_canon` stamp
   - `freshness-report.json` — только если файл есть → PASS
2. **MEDIA REFRESH** (`--media-refresh`) для уже published ledger-поста:
   - те же gates, что выше, **кроме** freshness: `status=STALE` допускается;
   - ledger `status=published` обязателен;
   - **не** используй blanket `--skip-gates` (INC-20260723-1235);
   - алиас только freshness: `--allow-stale-freshness`
3. `wp_insert_post` / `wp_update_post` — title, slug, content, excerpt
   - **HARD (Dzen/RSS):** `post_excerpt` = тизер от агента **Description**
     (`description-brief.json` → meta.description). RSS emits excerpt as
     `<description>` (карточка в ленте Дзена — см.
     `shared/dzen-description-rules.md` / rss-modify.html) and the body as
     `<content:encoded>`.
   - Excerpt must **not** clone the opening (INC-20260805-2240) and must
     **not** near-duplicate the title (иначе на карточке заголовок дважды).
   - `rss_safe_excerpt()` **raises** on bad excerpt — never falls back to H1.
4. Featured image из `cover/cover.png` + **Media Library meta**:
   - **Атрибут alt** ← `cover-registry.json` `alt` / `cover_alt_text` / asset `alt`
   - **Подпись (caption)** ← осмысленный alt → `post_excerpt`; deprecated `meme_caption_ru` игнорировать (он обязан быть пуст)
   - **Описание (description)** ← alt → `post_content`
   - **Заголовок** ← укороченный alt → `post_title`
   - **HARD:** `data-slot="cover"` **вырезается** из `post_content`. Обложка
     на сайте — только герой темы; в Дзене — RSS `<enclosure>` (не первый
     `<figure>` в `content:encoded`, иначе картинка дважды).
5. **Inline images** — все локальные `<img src="cover/...">` загружаются в Media Library:
   - alt из HTML `alt="..."` или registry asset `alt` → `_wp_attachment_image_alt`
   - caption / description / title аналогично (description дополняется `h2_anchor` из registry, если есть)
   - `src` в `post_content` заменяется на WP media URL (HTML `alt` в теле поста сохраняется)
   - **Видимая подпись в Дзене:** каждый `<figure>` в `article.html` обязан
     нести `<figcaption>` с русским текстом (= alt). Дзен рендерит
     `content:encoded` как есть; `alt` и поля медиабиблиотеки видимой
     подписи не дают.
6. **Media completeness**: `WARN cover` / неполный inline upload → publish **fail** (не `OK post=` alone)
7. Post meta `_excalibur_blog_schema_jsonld` — JSON-LD для `single.php`
8. Post meta `_excalibur_blog_skip_theme_faq` = `1` — сигнал теме **не** добавлять глобальный FAQ-блок
9. Опционально `--deploy-llms` / `excalibur_blog_llms_deploy.py` — upload `llms.txt` + `llms-full.txt` в корень WP

Маппинг полей WP Media Library:

| Админка WP | Поле attachment | Источник пайплайна |
|------------|-----------------|--------------------|
| Атрибут alt | `_wp_attachment_image_alt` | registry / `<img alt>` |
| Подпись | `post_excerpt` | caption / meme / alt |
| Описание | `post_content` | description / alt (+ h2) |
| Заголовок | `post_title` | укороченный alt |

## Дубли FAQ на live-странице (важно)

Excalibur кладёт в `post_content` **один** FAQ по теме (`<h2>Частые вопросы</h2>`).

Тема example.com может **дописывать** после контента второй блок «Часто задаваемые вопросы по теме (FAQ)» с универсальными вопросами про контент-завод — это **не** часть `article.html`.

**Исправление в теме WordPress** (`single.php` или фильтр `the_content`):

```php
$skip_theme_faq = get_post_meta(get_the_ID(), '_excalibur_blog_skip_theme_faq', true);
if ($skip_theme_faq === '1') {
    // не выводить глобальный FAQ-блок темы для постов Excalibur BLOG
}
```

Publish-скрипт выставляет meta `_excalibur_blog_skip_theme_faq` автоматически при каждой публикации.

## Артефакты после publish

```text
memory/blog/articles/<topic_id>-<slug>/wp-publish-result.json
memory/blog/wp-publish-log.md
```

## Schema в теме WP

```php
$schema = get_post_meta(get_the_ID(), '_excalibur_blog_schema_jsonld', true);
if ($schema) {
    echo '<script type="application/ld+json">' . wp_kses_post($schema) . '</script>';
}
```

## Blockers

- `❌ PUBLISH BLOCKER` — QA не PASS, link-verify fail, нет credentials
- Production HTML не должен содержать MCP URLs — только WP media для featured image

Skill: `skills/publish-excalibur-blog/SKILL.md`

## SITE_BASE placeholder

Git-safe artifacts **must** use `{{SITE_BASE}}` instead of the live host (Cursor secret scan blocks commits with `PUBLIC_SITE_URL`).
Never write tool-display mask `[REDACTED]` into schema/llms as a fake URL.
Publish expands `{{SITE_BASE}}` → `PUBLIC_SITE_URL` in the WP payload only (`load_article`); committed files keep `{{SITE_BASE}}`.
Dry-run reports `schema_placeholder_remaining` and exits non-zero if expand failed.
`shared/published-articles.md` stores path-only URLs (`/slug/`) via `ledger_url_for_commit`.

