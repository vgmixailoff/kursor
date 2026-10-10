# Excalibur BLOG — Cloud cost rules

Жёсткие правила для Cursor Cloud Automation.

## Главное

Один Automation-run = **один** cloud-агент (Директор). Роли — это
`Task(excalibur-blog-*)` **в том же ране**, тот же checkout.
Так работает смена модели (Gemini 3.8 Flash на Writer).

Отдельный VM поднимают `/in-cloud` и `Task(..., environment=cloud)`.
Именно это сжигало токены (Trigger=Subagent каждые 1–4 мин). **Не путать**
с обычным `Task` внутри рана.

Документация: `shared/cursor-subagents.md`,
[cursor.com/docs/subagents](https://cursor.com/docs/subagents).

## HARD

1. **Одна статья / один Automation-run / один cloud VM.**
2. **Обязательно** `Task(excalibur-blog-scout|research|writer|…)` на каждую
   роль. Директор сам не пишет BODY и не рисует обложку.
3. **Запрещено** `environment=cloud`, `/in-cloud`, `/autopilot`,
   `Task(excalibur-blog-director)`.
4. Субагенты **не** запускают вложенный Task.
5. Isolation / отдельный worktree для роли — **запрещены** (нужна общая
   папка статьи). См. `shared/subagent-memory-contract.md`.
6. Не читать чужие `article.html`, live-сайт, `llms-full.txt` целиком, весь
   `memory/blog`, `memory/topics/`.
7. Anti-dup = `shared/published-titles.md` (published, ≤30 дней).
8. Fixer: сначала `rg '^status: open' memory/pipeline-fix-queue.md` —
   если пусто (или только пример в шаблоне), не делай fixer-проход.
9. После publish+merge:
   `published_titles.py --days 30` + `memory_purge.py --drop-topic <ID>`.
10. doctor + today — один раз в начале (Директор, не Scout). Doctor не
    запускается повторно при установке среды; по умолчанию печатает только
    ошибки и итог, полный список проверок — `--verbose`.
11. Игнорировать stale Automation Memory / старый swarm и старый бан
    «вообще без Task».
12. Хранилище — **git origin/main** этого репо. Не Cursor `open_git_pr`.
13. Длину BODY Writer не считает программой со статьёй внутри
    (calibrate / test_precise / test_target). Одна команда
    `excalibur_blog_body_len.py`; ориентир 3000–6000, допускается 2500–6500,
    затем не больше 3 правок абзацев.

## UI

- Промпт только из `CLOUD-AUTOMATION.md`.
- В поле Model каждой действующей Automation выбрать Grok 4.7,
  effort Medium и выключить Fast. Это модель родительского Директора;
  frontmatter ролей и параметры Task не меняют её.
- Все роли, кроме Writer: frontmatter `grok-4.7-medium`
  и в Task явный `model=grok-4.7-medium`. Пустой `model` платформа меняет
  на FAST. `inherit` копирует родителя. Slug с `-fast` запрещён.
- Текстовые роли: `gemini-3.8-flash` / Task slug `gemini-3.8-flash-high`.
  Только Writer. Title / Description / Cover-text удалены.
- Security review / Agent approval — OFF.
