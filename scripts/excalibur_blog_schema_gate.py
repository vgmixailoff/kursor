#!/usr/bin/env python3
"""Validate Excalibur BLOG schema.jsonld for secret-scan-safe site base URLs."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from excalibur_blog_html_linter import extract_faq_answer_after_h3
from excalibur_repo_paths import resolve_article_dir, resolve_article_output


REDACTED_LITERAL = "[REDACTED]"
SITE_BASE_PLACEHOLDER = "{{SITE_BASE}}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def validate_schema_text(text: str) -> list[str]:
    errors: list[str] = []
    if not text.strip():
        errors.append("schema.jsonld is empty")
        return errors
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"schema.jsonld is not valid JSON: {exc}")
        return errors
    if REDACTED_LITERAL in text:
        errors.append(
            f"schema.jsonld contains literal {REDACTED_LITERAL!r}; "
            f"use {SITE_BASE_PLACEHOLDER} (git-safe) or live PUBLIC_SITE_URL only in runtime expand, never copy from old schemas/tool display"
        )
    if re.search(r"(?:\{\{SITE_BASE\}\}|https?://[^\"']+)/blog/", text):
        errors.append("schema article URLs must be {{SITE_BASE}}/<slug>/, not /blog/<slug>/")
    return errors


def _objects(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_objects(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_objects(child))
    return found


def _normalize_faq_plain(text: str) -> str:
    """Strip tags and normalize spaces so inline <a> strip does not false-FAIL.

    Replacing tags with spaces leaves artifacts like ``гайда ,`` vs ``гайда,``.
    Collapse whitespace, then drop spaces before closing punctuation and after
    opening punctuation so schema JSON-LD and visible HTML compare equal.

    Also collapse em/en dash and ``--+`` to ``-`` so local parity matches
    live-page gate after WP wptexturize (INC-20260721-1655).
    """
    plain = html.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    plain = re.sub(r"\s+", " ", plain).strip()
    plain = re.sub(r"\s+([,.;:!?…»\)\]])", r"\1", plain)
    plain = re.sub(r"([«\(\[])\s+", r"\1", plain)
    plain = plain.replace("\u2014", "-").replace("\u2013", "-")
    plain = re.sub(r"-{2,}", "-", plain)
    return plain


def faq_parity_errors(schema_text: str, article_html: str) -> list[str]:
    try:
        data = json.loads(schema_text)
    except json.JSONDecodeError:
        return []
    faq_nodes = [
        item for item in _objects(data) if str(item.get("@type") or "") == "FAQPage"
    ]
    schema_pairs: list[tuple[str, str]] = []
    for node in faq_nodes:
        for question in node.get("mainEntity") or []:
            if isinstance(question, dict) and question.get("name"):
                answer = question.get("acceptedAnswer")
                answer_text = answer.get("text") if isinstance(answer, dict) else ""
                schema_pairs.append(
                    (
                        _normalize_faq_plain(str(question["name"])),
                        _normalize_faq_plain(str(answer_text)),
                    )
                )

    match = re.search(
        r"<h2\b[^>]*>\s*(?:Частые вопросы|Часто задаваемые вопросы|FAQ).*?</h2>(.*?)(?=<h2\b|$)",
        article_html,
        flags=re.I | re.S,
    )
    visible_pairs: list[tuple[str, str]] = []
    if match:
        chunks = re.split(r"(?=<h3\b)", match.group(1), flags=re.I)
        for chunk in chunks:
            question = re.search(r"<h3\b[^>]*>(.*?)</h3>", chunk, flags=re.I | re.S)
            if not question:
                continue
            # First <p> only — ignore trailing CTA/interlink siblings
            # (INC-20260726-1615).
            answer_html = extract_faq_answer_after_h3(chunk[question.end() :])
            visible_pairs.append(
                (
                    _normalize_faq_plain(question.group(1)),
                    _normalize_faq_plain(answer_html),
                )
            )
    if schema_pairs == visible_pairs:
        return []
    errors = [
        "FAQPage questions and acceptedAnswer.text must exactly match visible "
        f"thematic FAQ (schema={len(schema_pairs)}, visible={len(visible_pairs)})"
    ]
    limit = max(len(schema_pairs), len(visible_pairs))
    for index in range(limit):
        if index >= len(schema_pairs):
            errors.append(f"FAQ mismatch at Q{index + 1}: missing in schema")
            continue
        if index >= len(visible_pairs):
            errors.append(f"FAQ mismatch at Q{index + 1}: missing in visible HTML")
            continue
        schema_q, schema_a = schema_pairs[index]
        visible_q, visible_a = visible_pairs[index]
        if (schema_q, schema_a) == (visible_q, visible_a):
            continue
        # Short char-diff for invisible space/punctuation mismatches.
        if schema_q != visible_q:
            errors.append(
                f"FAQ mismatch at Q{index + 1} question: "
                f"schema={schema_q!r} visible={visible_q!r}"
            )
        if schema_a != visible_a:
            errors.append(
                f"FAQ mismatch at Q{index + 1} answer: "
                f"schema={schema_a!r} visible={visible_a!r}"
            )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate: schema.jsonld must not contain [REDACTED]")
    ap.add_argument("--article-dir", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, default=None, help="Write JSON report (default: <article-dir>/schema-gate.json)")
    args = ap.parse_args()

    root = project_root()
    article_dir = resolve_article_dir(args.article_dir, root)
    schema_path = article_dir / "schema.jsonld"
    # Bare ``-o schema-gate.json`` only in agent prompts. Repo-relative ``-o``
    # is accepted but resolved vs project root (INC-20260726-0813).
    out_path = resolve_article_output(
        args.output,
        article_dir=article_dir,
        root=root,
        default_name="schema-gate.json",
    )

    errors: list[str] = []
    warnings: list[str] = []
    has_placeholder = False
    if not schema_path.is_file():
        errors.append(f"missing {schema_path}")
        text = ""
    else:
        text = schema_path.read_text(encoding="utf-8")
        errors.extend(validate_schema_text(text))
        try:
            schema_data = json.loads(text)
        except json.JSONDecodeError:
            schema_data = {}
        objects = _objects(schema_data)
        types = [
            str(item.get("@type") or "")
            for item in objects
            if isinstance(item, dict)
        ]
        if "BlogPosting" not in types:
            errors.append("schema.jsonld must contain BlogPosting")
        meta: dict[str, Any] = {}
        meta_path = article_dir / "article.meta.json"
        if meta_path.is_file():
            try:
                loaded_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded_meta, dict):
                    meta = loaded_meta
            except json.JSONDecodeError:
                pass
        slug = str(meta.get("slug") or article_dir.name.split("-", 1)[-1]).strip("/")
        posting_urls: list[str] = []
        for item in objects:
            if str(item.get("@type") or "") != "BlogPosting":
                continue
            for key in ("url", "@id", "mainEntityOfPage"):
                value = item.get(key)
                if isinstance(value, str):
                    posting_urls.append(value)
                elif isinstance(value, dict):
                    posting_urls.extend(
                        str(value.get(k) or "") for k in ("@id", "url")
                    )
        expected_suffix = f"/{slug}/"
        expected_url = f"{SITE_BASE_PLACEHOLDER}{expected_suffix}"
        if expected_url not in posting_urls:
            errors.append(
                f"BlogPosting URL/@id must include exact canonical {expected_url}"
            )
        article_path = article_dir / "article.html"
        if article_path.is_file():
            errors.extend(
                faq_parity_errors(
                    text, article_path.read_text(encoding="utf-8")
                )
            )
        has_placeholder = SITE_BASE_PLACEHOLDER in text
        if text and not has_placeholder and "://" in text and REDACTED_LITERAL not in text:
            warnings.append(
                "schema.jsonld has absolute http(s) URLs without {{SITE_BASE}}; "
                "Cursor secret scan may block git commit of PUBLIC_SITE_URL — prefer {{SITE_BASE}} in committed artifacts"
            )

    status = "PASS" if not errors else "FAIL"
    report: dict[str, Any] = {
        "status": status,
        "article_dir": str(article_dir.relative_to(root) if root in article_dir.parents else article_dir),
        "schema_path": str(schema_path.relative_to(root) if root in schema_path.parents else schema_path),
        "has_site_base_placeholder": has_placeholder,
        "errors": errors,
        "warnings": warnings,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
