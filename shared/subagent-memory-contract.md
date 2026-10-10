# Общая память субагентов (HARD)

Канон: [cursor.com/docs/subagents](https://cursor.com/docs/subagents).

Субагент **не видит** чат Директора. У него чистое окно. Общая память —
**файлы одного checkout**, не история сообщений и не User Rules.

## Что общее

| Слой | Путь | Кто пишет |
|------|------|-----------|
| Канон / правила | `AGENTS.md`, `shared/*`, `.cursor/rules/` | репо (все роли читают) |
| Слот и тема | `.cursor/excalibur-blog-handoff.md` | Директор + Scout |
| Статья | `memory/blog/articles/<topic_id>-<slug>/` | Research → Gemini → дальше |
| Параллельные роли | `.cursor/excalibur-blog-fragments/<role>.md` | Schema / Cover |
| Anti-dup | `shared/published-titles.md` | только после publish |

Handoff в git **не коммитить**. Fragments мержит **только Директор**
(`scripts/excalibur_blog_handoff_merge.py`) отдельным шагом после волны.
В начале каждого run Директор заново создаёт handoff с текущей датой и
слотом и очищает старые fragments до Scout. Пустого файла из git нет.

## Как Директор передаёт контекст

Каждый `Task(...)` обязан в `prompt` явно дать:

- `topic_id`, `article_dir`, `slot`
- путь handoff
- `signal_urls` (если уже есть)
- какие файлы читать; какие писать
- «не запускай вложенный Task»

Resume: при FAIL гейта Gemini передай `resume` = agent id прошлого Writer,
а не поднимай третьего автора.

## Параллель без порчи файлов

Субагенты делят **один** checkout (isolation / worktree / `environment=cloud`
**запрещены** — иначе не будет общей папки статьи).

Параллельно только роли, которые пишут **разные** файлы:

- Schema ‖ Cover (Cover не трогает schema.jsonld; Schema не трогает PNG)
- Inline Visuals запускается после этой волны и один редактирует `article.html`.

Нельзя двум ролям одновременно править `article.html` или handoff.

## Что не общее

- User Rules родителя могут **не** дойти до субагента — HARD держим в
  `AGENTS.md` + skill/agent файле роли.
- `~/.cursor/subagents/` — логи фона, не канон выпуска.
