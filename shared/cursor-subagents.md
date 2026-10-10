# Cursor: субагенты, оркестратор, модели

Сводка официальных доков (проверено 2026-09-14). Полный текст:
[cursor.com/docs/subagents](https://cursor.com/docs/subagents),
[cursor.com/docs/models/gemini-3-8-flash](https://cursor.com/docs/models/gemini-3-8-flash),
[cursor.com/docs/rules](https://cursor.com/docs/rules),
[Cloud Agents API / customSubagents](https://cursor.com/docs/cloud-agent/api/endpoints).

## Субагент ≠ отдельный Cloud Agent

| Механизм | Где крутится | Когда у нас |
|----------|--------------|-------------|
| `Task(subagent_type=excalibur-blog-*)` | тот же ран / тот же checkout | **обязателен** для ролей |
| `/in-cloud` или `Task(..., environment=cloud)` | **новый** VM и ветка | **запрещён** |
| Skill | та же сессия, без изоляции контекста | шпаргалка роли; работу делает субагент |

Файлы ролей: `.cursor/agents/*.md` (и копия `agents/` для плагина).
Frontmatter: `name`, `description` (фразы вроде «Always use for…»),
`model`, `readonly`, `is_background`.

## Оркестратор

Директор — родительский агент чата. Он **не** `Task(excalibur-blog-director)`.
Он зовёт специалистов, мержит fragments, гоняет shell-гейты.

Независимые роли — несколько `Task` в одном сообщении (параллель).
Последовательные — foreground, ждём результат.

Субагенты с Cursor 2.5 умеют вложенность, но у нас **запрещена**:
роль не поднимает Task. Resume — через agent id, не новый рой.

## Модели

Текстовые роли: **Gemini 3.8 Flash**.

- Frontmatter Writer: `model: gemini-3.8-flash`
- Вызов Task Writer: `model: gemini-3.8-flash-high`
  (slug allowlist; high = дефолтный effort 3.8 Flash)
- Все остальные роли, включая Директора: frontmatter
  `grok-4.7-medium`; в Task `model=grok-4.7-medium`.
  Пустой `model` платформа подменяет на FAST. `inherit` копирует родителя.
  Slug с `-fast` запрещён. Frontmatter Директора не меняет уже запущенный ран.

Картинки Gemini **не** рисует. Cover делает отдельную обложку через Kie;
Inline Visuals отдельно работает с изображениями внутри BODY.
Единственный текстовый Gemini — Writer. Title / Description / Cover-text удалены.

## Скрипты и команды

- Скрипты пайплайна — `scripts/excalibur_blog_*.py` (гейты, materialize,
  WP, Kie). Их гоняет Директор или роль, не «вместо» субагента.
- Slash-команда: `commands/excalibur-blog-run.md`.

## Память

См. `shared/subagent-memory-contract.md`. `AGENTS.md` подхватывается
вложенно; чат родителя — нет.
