#!/usr/bin/env python3
"""Hard gate: one allowed article CTA + ban dead kovcheg_ai channel.

Choose exactly one href:
  https://t.me/maya_pro
  https://max.ru/maya_pro
  https://kv-ai.ru/obuchenie-po-make

Forbidden: t.me/kovcheg_ai (channel does not exist).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CTA_URLS = (
    "https://t.me/maya_pro",
    "https://max.ru/maya_pro",
    "https://kv-ai.ru/obuchenie-po-make",
)

TELEGRAM_RE = re.compile(
    r"""https?://(?:t\.me|telegram\.me)/maya_pro(?:/|\b|"|'|>)""",
    re.I,
)
MAX_RE = re.compile(r"""https?://(?:www\.)?max\.ru/maya_pro(?:/|\b|"|'|>)""", re.I)
TRAINING_RE = re.compile(
    r"""https?://(?:www\.)?kv-ai\.ru/obuchenie-po-make(?:/|\b|"|'|>)""",
    re.I,
)
KOVCHEG_AI_RE = re.compile(
    r"""https?://(?:t\.me|telegram\.me)/(?:s/)?kovcheg_ai\b|ковчег\s*ai""",
    re.I,
)


def check_html(html: str) -> list[str]:
    errors: list[str] = []
    matches = [
        href for href in re.findall(r'''href=["']([^"']+)["']''', html or "", re.I)
        if href.split("?", 1)[0].split("#", 1)[0].rstrip("/") in CTA_URLS
    ]
    if len(matches) != 1:
        errors.append("exactly one allowed CTA href required in article")
    if KOVCHEG_AI_RE.search(html or ""):
        errors.append("forbidden t.me/kovcheg_ai / «Ковчег AI» — use t.me/maya_pro only")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("-o", "--output", default="community-cta-gate.json")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()

    html_path = article_dir / "article.html"
    errors: list[str] = []
    if not html_path.is_file():
        errors.append("article.html missing")
        html = ""
    else:
        html = html_path.read_text(encoding="utf-8")
        errors.extend(check_html(html))

    status = "PASS" if not errors else "FAIL"
    report = {
        "status": status,
        "article_dir": str(article_dir.relative_to(root)).replace("\\", "/"),
        "allowed": list(CTA_URLS),
        "telegram_present": bool(TELEGRAM_RE.search(html)),
        "max_present": bool(MAX_RE.search(html)),
        "training_present": bool(TRAINING_RE.search(html)),
        "kovcheg_ai_forbidden": bool(KOVCHEG_AI_RE.search(html)),
        "errors": errors,
    }
    out_name = Path(args.output).name
    out_path = article_dir / out_name
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
