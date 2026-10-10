#!/usr/bin/env python3
"""Materialize gemini-article.json → html + title/description briefs + cover-text.

Does not rewrite Gemini phrases. Only structures files for the rest of the
pipeline (stamp, cover, publish). Writer owns TITLE/DESCRIPTION/COVER lines;
there is no Title/Description/Cover-text agent.
"""
from __future__ import annotations

import argparse
import json
import re
from html import escape
from pathlib import Path
from typing import Any


REQUIRED_KEYS = (
    "TITLE",
    "DESCRIPTION",
    "COVER_LINE1",
    "COVER_LINE2",
    "COVER_PROMPT",
    "COVER_ALT",
    "BODY",
)

INLINE_ONIMAGE_KEYS = tuple(f"INLINE{i}_ONIMAGE" for i in range(1, 5))
INLINE_ALT_KEYS = tuple(f"INLINE{i}_ALT" for i in range(1, 5))


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _strip_h1(body: str) -> str:
    return re.sub(r"<h1\b[^>]*>.*?</h1>", "", body or "", flags=re.I | re.S).strip()


def materialize(article_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED_KEYS if not str(data.get(k) or "").strip()]
    if missing:
        raise ValueError(f"gemini-article.json missing keys: {missing}")

    title = str(data["TITLE"]).strip()
    description = str(data["DESCRIPTION"]).strip()
    body = _strip_h1(str(data["BODY"]))
    topic_id = str(
        data.get("topic_id")
        or (article_dir.name.split("-", 1)[0] if article_dir.name else "")
    ).strip()

    article_dir.mkdir(parents=True, exist_ok=True)
    (article_dir / "article.html").write_text(body + "\n", encoding="utf-8")

    drafts = article_dir / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    (drafts / "writer.html").write_text(body + "\n", encoding="utf-8")
    (drafts / "variant-a.html").write_text(body + "\n", encoding="utf-8")

    title_brief = {
        "topic_id": topic_id,
        "h1": title,
        "title": title,
        "subject": str(data.get("subject") or data.get("COVER_LINE1") or "").strip(),
        "angle": "gemini-evening-v1",
        "verdict": "PASS",
        "text_author": "gemini-3.8-flash",
    }
    (article_dir / "title-brief.json").write_text(
        json.dumps(title_brief, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    description_brief = {
        "topic_id": topic_id,
        "title": title,
        "description": description,
        "char_count": len(description),
        "verdict": "PASS",
        "text_author": "gemini-3.8-flash",
    }
    (article_dir / "description-brief.json").write_text(
        json.dumps(description_brief, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    inline_labels: dict[str, list[str]] = {}
    for i in range(1, 5):
        on = str(data.get(f"INLINE{i}_ONIMAGE") or "").strip()
        if not on:
            continue
        # Split multi-line ONIMAGE into short labels for fact cards.
        parts = [p.strip() for p in re.split(r"[\n|;]+", on) if p.strip()]
        if len(parts) < 2:
            parts = [on[:40], on[40:80] or on[:40]]
        inline_labels[f"inline_{i}"] = parts[:6]

    cover_text = {
        "canon": "sunburst_i2i",
        "line1": str(data["COVER_LINE1"]).strip(),
        "line2": str(data["COVER_LINE2"]).strip(),
        "cover_prompt": str(data["COVER_PROMPT"]).strip(),
        "cover_alt": str(data["COVER_ALT"]).strip(),
        "hook": str(data["COVER_LINE1"]).strip(),
        "highlight": "",
        "sticky": "",
        "inline_labels": inline_labels,
        "inline_alts": {
            f"inline_{i}": str(data.get(f"INLINE{i}_ALT") or "").strip()
            for i in range(1, 5)
            if str(data.get(f"INLINE{i}_ONIMAGE") or "").strip()
        },
        "inline_onimage": {
            f"inline_{i}": str(data.get(f"INLINE{i}_ONIMAGE") or "").strip()
            for i in range(1, 5)
            if str(data.get(f"INLINE{i}_ONIMAGE") or "").strip()
        },
    }
    cover_dir = article_dir / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)
    (cover_dir / "cover-text.json").write_text(
        json.dumps(cover_text, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "title": title,
        "body_chars": len(re.sub(r"<[^>]+>", "", body)),
        "inline_panels": len(inline_labels),
        "files": [
            "article.html",
            "drafts/writer.html",
            "drafts/variant-a.html",
            "title-brief.json",
            "description-brief.json",
            "cover/cover-text.json",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()

    path = article_dir / "gemini-article.json"
    if not path.is_file():
        print(json.dumps({"status": "FAIL", "errors": ["gemini-article.json missing"]}, ensure_ascii=False))
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print(json.dumps({"status": "FAIL", "errors": ["gemini-article.json not an object"]}, ensure_ascii=False))
        return 1
    try:
        report = materialize(article_dir, data)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
