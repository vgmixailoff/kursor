#!/usr/bin/env python3
"""Gate: Dzen/RSS description must be distinct from title and opening.

Reads description-brief.json and/or article.meta.json description fields.
Official card text path: WP post_excerpt → RSS <description> (Dzen card).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from excalibur_blog_plain_language import allowlist_from_title, plain_language_errors


MIN_CHARS = 80
MAX_CHARS = 180


def _plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _norm(text: str) -> str:
    t = _plain(text).casefold()
    t = re.sub(r"[\"«»„“”]+", "", t)
    t = re.sub(r"[.!?…]+$", "", t).strip()
    return re.sub(r"\s+", " ", t)


def _first_paragraph(html: str) -> str:
    m = re.search(r"<p\b[^>]*>(.*?)</p>", html or "", flags=re.I | re.S)
    return _plain(m.group(1)) if m else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def near_duplicate(a: str, b: str, *, min_ratio: float = 0.82) -> bool:
    """True when strings are equal or one is almost the other."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) < 24:
        return longer.startswith(shorter) and len(shorter) / max(len(longer), 1) >= 0.7
    if longer.startswith(shorter) and len(shorter) / len(longer) >= min_ratio:
        return True
    # shared prefix length
    n = 0
    for ca, cb in zip(shorter, longer):
        if ca != cb:
            break
        n += 1
    return n >= min_ratio * len(shorter) and n >= 40


def clones_opening(description: str, opening: str, *, min_chars: int = 48) -> bool:
    desc = _norm(description)
    body = _norm(opening)
    if len(desc) < min_chars or not body:
        return False
    probe = desc[: min(len(desc), 80)]
    return body.startswith(probe) or desc.startswith(body[: min(len(body), 80)])


def check_article(article_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    brief = _load_json(article_dir / "description-brief.json")
    meta = _load_json(article_dir / "article.meta.json")
    title_brief = _load_json(article_dir / "title-brief.json")
    html_path = article_dir / "article.html"
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""

    description = str(
        brief.get("description")
        or meta.get("description")
        or (meta.get("meta_ab") or {}).get("description_seo")
        or ""
    ).strip()
    title = str(
        title_brief.get("h1")
        or title_brief.get("title")
        or meta.get("h1")
        or meta.get("title")
        or ""
    ).strip()
    opening = _first_paragraph(html)

    if not (article_dir / "description-brief.json").is_file():
        errors.append("description-brief.json missing (Writer JSON DESCRIPTION → materialize)")
    elif str(brief.get("verdict") or "").upper() != "PASS":
        errors.append(f"description-brief verdict={brief.get('verdict')!r} (need PASS)")

    if not description:
        errors.append("description empty")
    else:
        n = len(description)
        if n < MIN_CHARS:
            errors.append(f"description too short: {n} < {MIN_CHARS}")
        if n > MAX_CHARS:
            errors.append(f"description too long: {n} > {MAX_CHARS}")
        if re.search(r"<[^>]+>", description):
            errors.append("description contains HTML")
        if re.search(r"https?://|www\.", description, re.I):
            errors.append("description contains URL")
        if re.search(r"[\U0001F300-\U0001FAFF]", description):
            errors.append("description contains emoji")
        if title and near_duplicate(description, title):
            errors.append("description near-duplicate of title/h1")
        if opening and clones_opening(description, opening):
            errors.append("description clones article opening paragraph")
        if re.search(r"лебедев|тележеньк", description, re.I):
            errors.append("description must not name Lebedev/Telezhka")
        allow = allowlist_from_title(
            title,
            str(title_brief.get("subject") or ""),
        )
        errors.extend(
            plain_language_errors(
                description,
                allow=allow,
                max_latin=1,
                max_jargon=0,
                label="description",
            )
        )

    status = "PASS" if not errors else "BLOCK"
    return {
        "gate": "description",
        "status": status,
        "errors": errors,
        "description": description,
        "title": title,
        "char_count": len(description),
        "article_dir": str(article_dir),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", type=Path, required=True)
    ap.add_argument("-o", "--output", type=str, default="description-gate.json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    article_dir = args.article_dir if args.article_dir.is_absolute() else root / args.article_dir
    if not article_dir.is_dir():
        print(f"BLOCKER: article-dir not found: {article_dir}", file=sys.stderr)
        return 2
    report = check_article(article_dir)
    out_path = article_dir / Path(args.output).name
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
