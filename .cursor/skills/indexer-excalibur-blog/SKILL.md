---
name: indexer-excalibur-blog
description: Indexer — llms.txt из заголовков (+ текущая статья); исторические тексты не храним.
---

# Indexer — только заголовки (+ текущая статья)

Долгосрочная память = `shared/published-titles.md` (заголовки ≤30 дней).
Старые `article.html` и картинки не сканируем и не храним.

```bash
# Канон: индекс заголовков + опционально текущая статья
python3 scripts/excalibur_blog_llms_generator.py \
  --mode titles+current \
  --titles shared/published-titles.md \
  --article-dir memory/blog/articles/<topic_id>-<slug> \
  --blog-path / \
  --out-dir memory/blog

# Сначала освежи окно заголовков (если нужно)
python3 scripts/excalibur_blog_published_titles.py --days 30
```

В git-артефакты пиши `{{SITE_BASE}}` / `{{SITE_HOST}}`, не живой домен.
Файлы llms в git не коммитим — они пересоздаются каждый запуск
(см. `.gitignore`).

Выход: `memory/blog/llms.txt` (индекс заголовков), `llms-full.txt`
(только текущая статья, если передана; иначе заглушка без старых текстов).
Без правок `article.html`, без перелинковки.
