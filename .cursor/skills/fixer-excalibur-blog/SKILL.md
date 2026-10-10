# Excalibur BLOG — Fixer

## Когда запускаться

После `PIPELINE DONE` или после жёсткой остановки — и только если в
`memory/pipeline-fix-queue.md` есть `status: open`.

Fixer не участвует в производстве статьи. Это контур улучшения пайплайна
после запуска.

## Вход

- `memory/pipeline-fix-queue.md`
- `shared/pipeline-incident-fix-contract.md`
- файлы из «Suggested files to inspect/change» каждого инцидента
- текущий git diff/status

## Порядок

1. Прочитай весь `memory/pipeline-fix-queue.md`.
2. Возьми open-инциденты этого запуска. Если запуск не указан — все open,
   сгруппированные по корню проблемы.
3. По каждому ответь:
   - это ошибка промпта / контракта роли?
   - ошибка skill-инструкции?
   - не хватает проверки в скрипте или плохой fallback?
   - это env/API-блокер, который кодом не чинится?
4. Чини причину в постоянном месте:
   - `agents/` и `.cursor/agents/` — короткий контракт роли;
   - `skills/` и `.cursor/skills/` — подробная инструкция;
   - `shared/` — общие контракты;
   - `scripts/` — автоматическая проверка / fallback.
5. Правишь `agents/` — синхронизируй копию в `.cursor/agents/`.
   То же для `skills/`.
6. Прогони минимально нужные проверки:
   - `python3 -m py_compile` для изменённых скриптов;
   - разбор JSON для изменённых JSON;
   - соответствующий гейт / dry-run;
   - `rg` на старые ошибочные строки.
7. Обнови каждый инцидент:

```markdown
status: fixed
fixed_at: YYYY-MM-DD
fix_summary:
- ...
files_changed:
- `...`
checks_run:
- ...
commit: <hash>
```

Если надолго починить нельзя:

```markdown
status: needs-human
reason:
- ...
needed_decision_or_secret:
- ...
```

## Хороший fix — это когда

- Следующий запуск получает более точный контракт до ошибки.
- Ошибку ловит ранний гейт/скрипт вместо поздней ручной правки.
- Retry/fallback описан так, что не плодит дублей (картинки, посты, строки
  ledger).
- Fix не раскрывает секреты и не привязан к путям конкретной машины.

## Итог для Директора

```text
=== EXCALIBUR BLOG FIXER ===
status: fixed | needs-human | no-open-incidents
incidents:
- INC-...
files_changed:
- ...
checks:
- ...
blockers: none | ...
```

## Запреты

- **Не возвращать старую схему пайплайна** и убранные роли (Glavred,
  Reader Panel, Critic, Thesis, Sol и др.). Канон сейчас:
  `Research → Gemini → Description → Cover → Publish`.
- **Не воскрешать Sol/Тележеньку** — финальный текст пишет Gemini.
  `shared/writer-master-prompt.md` меняет только человек.
- **Не удалять/не ослаблять** `shared/topic-focus-contract.md` и
  focus-гейты. Не возвращать PageSpeed/Метрику/GA4/Вебмастер/Директ
  как темы.
- Не лечить симптом в артефакте текущей статьи, если причина в контракте
  пайплайна.
- Не запускать публикацию/генерацию картинок без явной нужды для проверки.
- Не закрывать open-инцидент молча.
- Не писать секреты в memory, handoff, PR или логи.
