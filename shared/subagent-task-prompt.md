# Шаблон prompt для Task(excalibur-blog-*)

Директор копирует блок в каждый `Task`. Пустые поля не оставлять.

```text
role: excalibur-blog-<role>
model: grok-4.7-medium
topic_id: B…
slot: viral-06 | news-12 | case-14 | news-18
article_dir: memory/blog/articles/<topic_id>-<slug>
handoff: .cursor/excalibur-blog-handoff.md
signal_urls:
- <url>
read:
- shared/subagent-memory-contract.md
- <skill / контракт роли>
write:
- <только свои файлы>
rules:
- model=grok-4.7-medium. Исключение: Writer = gemini-3.8-flash-high
- не передавай slug с -fast и не опускай model
- не вызывай Task
- не isolation / не environment=cloud
- не правь article.html, если это не твоя роль
- не вызывай handoff_merge.py (это Директор)
```

После ответа роли Директор обновляет handoff (кроме параллельной волны —
тогда роль пишет fragment, merge отдельно).
