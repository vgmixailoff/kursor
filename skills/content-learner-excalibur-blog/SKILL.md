---
name: content-learner-excalibur-blog
description: Учится на выпуске — Метрика + гейты → короткий урок в merge.
---

# Excalibur BLOG — Content Learner

После publish, до fixer. Учимся на цифрах, а не на ощущениях.

## Вход

- `gemini-article-gate.json` — если есть;
- заголовки `shared/published-titles.md` (≤30 дней);
- `shared/content-learning-contract.md`;
- `shared/pipeline-canon.json`.

## Порядок

1. Если есть `gemini-article-gate.json` — посмотри отчёт гейта.
   Нет файла → это не блокер, иди дальше. Файл есть, но битый →
   `CONTENT EVIDENCE BLOCKER` + инцидент. Отчёт не выдумывай.
2. Сам запусти `excalibur_blog_metrika_fetch.py --days 30 --ingest` **один раз**,
   затем прочитай свежий `memory/analytics/metrika-latest.json`.
   Метрика **обязательна** всегда (не optional).
3. Ошибка ключей/API Метрики = `METRIKA FEEDBACK BLOCKER` + инцидент.
   Если скрипт вернул JSON `status: BLOCKER` и `do_not_retry: true`
   (`reason: query_error` и/или `code_status=CS_ERR_UNKNOWN`):
   это состояние счётчика Яндекса, не «слишком широкий --days».
   **Не** крутить today / yesterday / `--days 1` / `accuracy=low` / preset / bytime.
   Ряды не invent'ить. Инцидент + `needed_human` из JSON.
4. Сопоставь находки гейта с цифрами Метрики. Мало данных или слабая
   уверенность → урок с пометкой «мало данных», не причинный вывод.
5. Запиши урок: что оставить / что поменять / что больше не делать.
6. Менять правила в репо — только когда проблема повторилась минимум в
   двух запусках или это явный тяжёлый блокер. Запиши, как откатить.

## Запреты

- Не запускать LLM-судей и не считать рейтинги статей.
- Не выдумывать отчёт гейта, чтобы «закрыть» пропуск.
- Не переписывать текущий `article.html`.
- Не добавлять правила в `shared/writer-master-prompt.md` и Writer-роль
  автоматически — их меняет только человек.
- Уроки — коротко в сообщение merge-коммита, не файлом.

```text
=== EXCALIBUR BLOG CONTENT LEARNER ===
status:
topic_id:
article_dir:
metrika_feedback: PASS | BLOCKER
named_blockers:
lessons_recorded:
rollback_check:
incident_report:
```
