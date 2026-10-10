#!/usr/bin/env python3
"""Build GPT Image 2.5 Sunburst i2i batch from TITLE + fixed comic prompt.

Gemini no longer writes the Kie image prompt. Cover fills
{{ЗАГОЛОВОК_СТАТЬИ}} in shared/cover-sunburst-comic-prompt.txt and
sends the mascot as the image-to-image reference.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TITLE_TOKEN = "{{ЗАГОЛОВОК_СТАТЬИ}}"
DEFAULT_TEMPLATE = "shared/cover-sunburst-comic-prompt.txt"
DEFAULT_MASCOT = "memory/cover/assets/cover-mascot.png"
PLACEHOLDER_URL = "https://unused.invalid/cover-mascot.png"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_title(article_dir: Path, cli_title: str) -> str:
    title = (cli_title or "").strip()
    if title:
        return title
    gemini = article_dir / "gemini-article.json"
    if gemini.is_file():
        data = json.loads(gemini.read_text(encoding="utf-8"))
        title = str(data.get("TITLE") or "").strip()
        if title:
            return title
    meta = article_dir / "article.meta.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        title = str(data.get("title") or data.get("h1") or "").strip()
        if title:
            return title
    raise ValueError("need --title, gemini-article.json TITLE, or article.meta.json title")


def fill_prompt(template: str, title: str) -> str:
    title = (title or "").strip()
    if not title:
        raise ValueError("empty article title")
    if TITLE_TOKEN not in template:
        raise ValueError(f"cover template missing {TITLE_TOKEN}")
    return template.replace(TITLE_TOKEN, title)


def build_batch(
    *,
    title: str,
    template: str,
    mascot_rel: str = DEFAULT_MASCOT,
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    background: str = "opaque",
) -> dict[str, Any]:
    prompt = fill_prompt(template, title)
    return {
        "canon": "sunburst_i2i",
        "cover_hero_mode": "mascot",
        "prefer_local_reference": True,
        "local_reference": mascot_rel,
        "jobs": [
            {
                "id": "cover-i2i-sunburst",
                "mcp_args": {
                    "prompt": prompt,
                    "input_urls": [PLACEHOLDER_URL],
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "background": background,
                },
            }
        ],
        "validation": {
            "prompt_chars": len(prompt),
            "title": title,
            "model": "gpt-image-2-5-sunburst-image-to-image",
            "mascot": mascot_rel,
            "input_url_count": 1,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--mascot", default=DEFAULT_MASCOT)
    ap.add_argument("--aspect-ratio", default="16:9")
    ap.add_argument("--resolution", default="1K")
    ap.add_argument("--background", default="opaque")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()

    template_path = Path(args.template)
    if not template_path.is_absolute():
        template_path = root / template_path
    if not template_path.is_file():
        print(json.dumps({"status": "FAIL", "errors": [f"missing {template_path}"]}, ensure_ascii=False))
        return 1

    mascot_path = Path(args.mascot)
    if not mascot_path.is_absolute():
        mascot_path = root / mascot_path
    if not mascot_path.is_file():
        print(json.dumps({"status": "FAIL", "errors": [f"missing mascot {mascot_path}"]}, ensure_ascii=False))
        return 1
    try:
        mascot_rel = str(mascot_path.resolve().relative_to(root))
    except ValueError:
        mascot_rel = str(mascot_path)

    try:
        title = load_title(article_dir, args.title)
        batch = build_batch(
            title=title,
            template=template_path.read_text(encoding="utf-8"),
            mascot_rel=mascot_rel,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            background=args.background,
        )
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False))
        return 1

    out = article_dir / "cover" / "t2i-batch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "batch": str(out),
                "title": title,
                "prompt_chars": batch["validation"]["prompt_chars"],
                "model": batch["validation"]["model"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
