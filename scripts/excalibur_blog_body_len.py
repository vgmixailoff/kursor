#!/usr/bin/env python3
"""Print visible BODY length. One short check — not a rewrite of the article.

Writer records gemini-article.json, then runs this once. If the text is
outside 2500–6500, edit a couple of paragraphs in that JSON and run this
again (at most 3 times). Do not generate Python that embeds the article.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from excalibur_blog_gemini_article_gate import visible_text  # noqa: E402

MIN_CHARS = 2500
MAX_CHARS = 6500


def project_root() -> Path:
    return ROOT


def length_scripts(article_dir: Path) -> list[str]:
    found: list[str] = []
    if not article_dir.is_dir():
        return found
    for path in sorted(article_dir.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        if "__pycache__" in path.parts:
            continue
        found.append(str(path.relative_to(article_dir)))
    return found


def measure_body(body: str) -> dict[str, Any]:
    n = len(visible_text(body or ""))
    if n < MIN_CHARS:
        status = "SHORT"
        delta = MIN_CHARS - n
    elif n > MAX_CHARS:
        status = "LONG"
        delta = n - MAX_CHARS
    else:
        status = "IN_RANGE"
        delta = 0
    return {
        "visible": n,
        "min": MIN_CHARS,
        "max": MAX_CHARS,
        "status": status,
        "delta": delta,
    }


def measure_dir(article_dir: Path) -> dict[str, Any]:
    gemini_path = article_dir / "gemini-article.json"
    if not gemini_path.is_file():
        return {"error": "gemini-article.json missing", "status": "MISSING"}
    try:
        loaded = json.loads(gemini_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "gemini-article.json invalid JSON", "status": "INVALID"}
    if not isinstance(loaded, dict):
        return {"error": "gemini-article.json is not an object", "status": "INVALID"}
    measured = measure_body(str(loaded.get("BODY") or ""))
    scripts = length_scripts(article_dir)
    measured["length_scripts"] = scripts
    return measured


def format_report(report: dict[str, Any]) -> str:
    if report.get("error"):
        return f"status={report.get('status')}\nerror={report['error']}"
    lines = [
        f"visible={report['visible']}",
        f"range={report['min']}-{report['max']}",
        f"status={report['status']}",
    ]
    if report["status"] == "SHORT":
        lines.append(f"add_about={report['delta']}")
    elif report["status"] == "LONG":
        lines.append(f"cut_about={report['delta']}")
    scripts = report.get("length_scripts") or []
    if scripts:
        lines.append("length_scripts=FORBIDDEN")
        lines.extend(f"script={name}" for name in scripts)
    else:
        lines.append("length_scripts=none")
    return "\n".join(lines)


def exit_code(report: dict[str, Any]) -> int:
    if report.get("status") in {"MISSING", "INVALID"}:
        return 1
    if report.get("length_scripts"):
        return 3
    if report.get("status") != "IN_RANGE":
        return 2
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-dir", type=Path, required=True)
    args = parser.parse_args()
    article_dir = args.article_dir
    if not article_dir.is_absolute():
        article_dir = project_root() / article_dir
    report = measure_dir(article_dir)
    print(format_report(report))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
