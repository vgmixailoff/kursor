#!/usr/bin/env python3
"""Ingest site feedback metrics and append lesson candidates to content-lessons.md.

Accepts CSV or JSON ({rows:[...]} / list). Supports manual CTR rows and Metrika rows
(pageviews, users, retention, bounce_rate, notes, source=yandex_metrika).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = _load_json(path)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            return [x for x in data["rows"] if isinstance(x, dict)]
        raise SystemExit("JSON must be list or {rows:[...]}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    return rows


def _f(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = row.get(key)
        if val not in (None, ""):
            return str(val)
    return ""


def lesson_block(row: dict[str, Any], now: str) -> str:
    topic = str(row.get("topic_id") or row.get("slug") or "n/a")
    source = str(row.get("source") or "site-feedback")
    ctr = _f(row, "ctr", "CTR")
    retention = _f(row, "retention", "avg_read_pct")
    pageviews = _f(row, "pageviews")
    users = _f(row, "users")
    bounce = _f(row, "bounce_rate")
    analytics = row.get("analytics") if isinstance(row.get("analytics"), dict) else {}
    signal = str(analytics.get("signal") or row.get("signal") or "")
    confidence = str(analytics.get("confidence") or row.get("confidence") or "")
    action = str(analytics.get("recommended_action") or row.get("recommended_action") or "").strip()
    notes = str(action or row.get("notes") or row.get("insight") or "").strip()

    if not notes:
        bits = []
        if pageviews:
            bits.append(f"pageviews={pageviews}")
        if users:
            bits.append(f"users={users}")
        if retention:
            bits.append(f"retention={retention}")
        if ctr:
            bits.append(f"CTR={ctr}")
        if bounce:
            bits.append(f"bounce={bounce}")
        notes = "Проверить meta/hook: " + (", ".join(bits) if bits else "нет метрик")

    keep_line = (
        "Сохранять форматы/хуки с сильным on-site engagement (Metrika visits, bounce, duration)"
        if source == "yandex_metrika"
        else "Сохранять форматы/хуки с CTR выше медианы канала (если есть в notes)"
    )
    never_line = (
        "Не повторять lead/title с высоким bounce / слабым pageviews без правки hook"
        if source == "yandex_metrika"
        else "Не повторять title/hook с CTR ниже порога без A/B проверки"
    )

    return f"""## LESSON-{now}-{topic}-site-feedback
status: active
run_date: {now[:8]}
topic_id: {topic}
article_dir: n/a
overall_score: n/a
category: site_feedback
source: {source}
signal: {signal or "n/a"}
confidence: {confidence or "n/a"}
pageviews: {pageviews or "n/a"}
users: {users or "n/a"}
retention: {retention or "n/a"}
ctr: {ctr or "n/a"}

### Keep
- {keep_line}

### Change
- {notes}

### Never again
- {never_line}

### Proposed apply
- memory/content-meta-ab-learnings.md — зафиксировать слабый/сильный meta паттерн

### Durable applied
- none

### Content-learner resolution
status: recorded
"""


def feedback_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Stable key for one Metrika/manual feedback observation."""
    return tuple(
        str(row.get(key) or "")
        for key in ("source", "topic_id", "slug", "url_path", "date1", "date2", "pageviews", "users")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV or JSON with metrics rows")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--lessons",
        default="memory/content-lessons.md",
        help="Lessons file relative to root",
    )
    parser.add_argument(
        "--store",
        default="memory/site-feedback.json",
        help="Append raw feedback snapshot",
    )
    parser.add_argument("--min-ctr", type=float, default=0.0, help="Optional CTR floor for alerts")
    parser.add_argument(
        "--min-pageviews",
        type=float,
        default=0.0,
        help="Optional pageviews floor for Metrika alerts",
    )
    parser.add_argument(
        "--dedupe-existing",
        action="store_true",
        help="Do not append a lesson for an identical feedback observation already stored",
    )
    parser.add_argument(
        "--actionable-only",
        action="store_true",
        help="Append lessons only for rows whose analytics.actionable is true",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    src = Path(args.input)
    if not src.is_absolute():
        src = root / src
    if not src.is_file():
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        return 2

    rows = load_rows(src)
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    lessons_path = root / args.lessons
    store_path = root / args.store
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.parent.mkdir(parents=True, exist_ok=True)

    existing_store: dict[str, Any]
    if store_path.is_file():
        existing_store = _load_json(store_path)
        if not isinstance(existing_store, dict):
            existing_store = {"entries": []}
    else:
        existing_store = {"schema_version": 1, "entries": []}

    known_keys: set[tuple[str, ...]] = set()
    if args.dedupe_existing:
        for prior in existing_store.get("entries") or []:
            if not isinstance(prior, dict):
                continue
            for row in prior.get("rows") or []:
                if isinstance(row, dict):
                    known_keys.add(feedback_key(row))

    entry = {
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(src.name),
        "rows": rows,
    }
    existing_store.setdefault("entries", []).append(entry)
    store_path.write_text(json.dumps(existing_store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    blocks: list[str] = []
    duplicate_rows = 0
    non_actionable_rows = 0
    for row in rows:
        row = dict(row)
        if args.actionable_only and not bool(row.get("actionable")):
            non_actionable_rows += 1
            continue
        if args.dedupe_existing and feedback_key(row) in known_keys:
            duplicate_rows += 1
            continue
        ctr_raw = row.get("ctr") or row.get("CTR")
        try:
            ctr_val = float(ctr_raw) if ctr_raw not in (None, "") else None
        except (TypeError, ValueError):
            ctr_val = None
        if ctr_val is not None and ctr_val < args.min_ctr:
            row["notes"] = (str(row.get("notes") or "") + f" CTR {ctr_val} < min_ctr {args.min_ctr}").strip()

        pv_raw = row.get("pageviews")
        try:
            pv_val = float(pv_raw) if pv_raw not in (None, "") else None
        except (TypeError, ValueError):
            pv_val = None
        if pv_val is not None and args.min_pageviews > 0 and pv_val < args.min_pageviews:
            row["notes"] = (
                str(row.get("notes") or "") + f" pageviews {pv_val} < min_pageviews {args.min_pageviews}"
            ).strip()

        blocks.append(lesson_block(row, now))

    if blocks:
        with lessons_path.open("a", encoding="utf-8") as fh:
            fh.write("\n" + "\n".join(blocks))

    print(
        json.dumps(
            {
                "status": "PASS",
                "rows": len(rows),
                "lessons_appended": len(blocks),
                "duplicate_rows_skipped": duplicate_rows,
                "non_actionable_rows_skipped": non_actionable_rows,
                "store": str(store_path.relative_to(root)).replace("\\", "/"),
                "lessons": str(lessons_path.relative_to(root)).replace("\\", "/"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
