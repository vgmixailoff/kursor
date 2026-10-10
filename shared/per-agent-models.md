# Per-agent models (Cursor) — как роли получают свою модель

Проверено по официальной документации Cursor 06.10.2026:
[Subagents](https://cursor.com/docs/subagents),
[Grok 4.7](https://cursor.com/docs/models/grok-4-7).

## Механика

1. Каждый агент в `.cursor/agents/<name>.md` имеет frontmatter-поле
   **`model`**: `inherit` (модель родителя) или конкретный model ID.
   https://cursor.com/docs/subagents
2. Для ролей кроме Writer frontmatter и Task используют один slug
   allowlist: `grok-4.7-medium` (Medium, Fast выключен).
   Скобочный id ран Cloud не применяет и роняет роль в дефолт
   High + Fast. Голый `grok-4.7` на Pro — тоже High + Fast.
   `inherit` копирует родителя. Пустой `model` платформа подменяет на FAST.
   Запрещены `grok-4.7-high`, `grok-4.7-xhigh` и любой slug с `-fast`.
3. В **том же** Cloud-ране Task берёт явный `model` вызова.
   Для ролей кроме Writer передавай slug `grok-4.7-medium`. Это **не** отдельный VM.
4. Отдельный VM: только `/in-cloud` или `environment=cloud` — у нас запрещены
   (`shared/cloud-cost-rules.md`).
5. В Automations API поле `customSubagents` (name/description/prompt +
   optional `model`), до 20 штук.
   https://cursor.com/docs/cloud-agent/api/endpoints
6. Точный список ID/параметров для аккаунта: `GET https://api.cursor.com/v1/models`.
   Документированный ID: `gemini-3.8-flash`
   (https://cursor.com/docs/models/gemini-3-8-flash).
   В allowlist инструмента Task этого рана: `gemini-3.8-flash-high` /
   `medium` / `low` (effort). Директор для текста передаёт
   **`gemini-3.8-flash-high`**.

## Расклад (HARD)

Модель субагентов, кроме Writer, — **Grok 4.7 Medium, Fast выключен**.
Во frontmatter: `grok-4.7-medium`.
В каждом Task, кроме Writer: **`model=grok-4.7-medium`**.
Поле не опускать: пустой `model` платформа подменяет на FAST.
`inherit` копирует родителя, а голый `grok-4.7` — это High + Fast.

Исключение одно: текст для людей пишет Writer на Gemini.
Slug с `-fast` запрещён.

| Роль | Модель |
|------|--------|
| **Директор / оркестратор** | В каждой Automation выбрать в UI Grok 4.7, Medium, Fast выключен; frontmatter `grok-4.7-medium` не переключает уже сохранённый родительский ран |
| **Writer / Gemini** | `gemini-3.8-flash` → Task `gemini-3.8-flash-high` (TITLE, DESCRIPTION, BODY, COVER, INLINE) |
| Scout, Research, Cover, Inline Visuals, Schema, Indexer, Publish, Fixer, Learner | frontmatter `grok-4.7-medium`; Task `model=grok-4.7-medium` |

## Когда frontmatter применяется

- Роль **спавнится** `Task` из `.cursor/agents/` (или `customSubagents`).
- Если Директор только читает skill и пишет сам — остаётся на своей модели,
  Gemini **не** запускается. Поэтому Директор **обязан** звать Writer через Task.

Fallback Cursor (план/админ) может подставить совместимую модель — гейты
текста всё равно держат канон. Фактическую модель проверяй в карточке Task.
