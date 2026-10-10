#!/usr/bin/env python3
"""Excalibur BLOG HTML Tag Linter & Sanitizer.

Enforces strict whitelist of HTML tags, prevents unclosed tags, and checks for malformed markup.
Allowed tags: h2, h3, p, b, strong, i, em, a, ul, ol, li, blockquote, table, thead, tbody, tr, th, td
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Whitelist tags based on excalibur contract and cover inline figure injection.
# Keep in sync with shared/gemini-article-contract.md (body tags).
ALLOWED_TAGS: set[str] = {
    "h2",
    "h3",
    "p",
    "b",
    "strong",
    "i",
    "em",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "figure",
    "figcaption",
    "img",
    "br",
}


def detect_anchor_toc(html: str) -> list[str]:
    """Fail if article contains in-body table of contents (anchor link list)."""
    errors: list[str] = []
    # Block: ol/ul with 3+ li containing href="#..."
    list_blocks = re.findall(r"<(?:ol|ul)[^>]*>(.*?)</(?:ol|ul)>", html, flags=re.IGNORECASE | re.DOTALL)
    for block in list_blocks:
        anchor_links = re.findall(
            r'<li[^>]*>\s*<a\s+[^>]*href=["\']#([^"\']+)["\']',
            block,
            flags=re.IGNORECASE,
        )
        if len(anchor_links) >= 3:
            errors.append(
                "Forbidden in-body TOC: list with 3+ anchor links to headings "
                f"(#{', #'.join(anchor_links[:5])}{'...' if len(anchor_links) > 5 else ''}). "
                "Remove <ol>/<ul> navigation after opening; see gemini-article-contract.md."
            )
    return errors


def is_faq_section_heading(text: str) -> bool:
    """True only for thematic FAQ section titles, not how-to H2 that mention faq.html/faq.mdc.

    Substring match on ``faq`` caused false positives on FAQ-topic articles (B16):
    H2 like «создайте faq.html» / «правило faq.mdc» were treated as FAQ sections.
    """
    t = re.sub(r"\s+", " ", text.strip().lower())
    if not t:
        return False
    # File/path mentions are how-to headings, not the FAQ block.
    if re.search(r"faq\.(?:html|mdc|md|json|txt|xml|yml|yaml)|[/\\]faq\b|\.faq\b", t):
        return False
    # Exact / near-exact section titles.
    if re.fullmatch(r"(?:faq|частые вопросы|часто задаваемые вопросы)[\s\?\!\.\:]*", t):
        return True
    # Section openers: «FAQ: …», «Частые вопросы о …», «FAQ по теме …».
    if re.match(r"^(?:faq|частые вопросы|часто задаваемые вопросы)\b", t):
        return True
    # Russian variants without leading «часто».
    if re.match(r"^задаваемые вопросы\b", t):
        return True
    return False


def detect_duplicate_faq_sections(html: str) -> list[str]:
    """Fail if article has more than one thematic FAQ heading block."""
    errors: list[str] = []
    faq_headings = re.findall(
        r"<h2[^>]*>\s*(.*?)\s*</h2>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    faq_like = []
    for raw in faq_headings:
        text = re.sub(r"<[^>]+>", "", raw).strip().lower()
        if is_faq_section_heading(text):
            faq_like.append(text)
    if len(faq_like) > 1:
        errors.append(
            "Forbidden duplicate FAQ sections in article.html: "
            + "; ".join(faq_like[:4])
            + ". Keep exactly one <h2>Частые вопросы</h2> block."
        )
    for raw in faq_headings:
        text = re.sub(r"<[^>]+>", "", raw).strip().lower()
        text_norm = re.sub(r"\s+", " ", text)
        if re.search(r"(?:задаваемые вопросы по теме|faq по теме)\b", text_norm) and is_faq_section_heading(
            text_norm
        ):
            errors.append(
                "Forbidden second FAQ block title (e.g. «Часто задаваемые вопросы по теме»). "
                "Use only one thematic FAQ section."
            )
            break
    return errors


# schema_gate / live_page_gate extract visible FAQ only from <h3> inside the FAQ
# section. Single-paragraph «Q? A» FAQ → visible=0 (INC-20260721-0131).
MIN_FAQ_H3_PAIRS = 1


def extract_thematic_faq_bodies(html: str) -> list[str]:
    """Return bodies of thematic FAQ sections (content after matching H2 until next H2)."""
    bodies: list[str] = []
    for match in re.finditer(
        r"<h2\b[^>]*>(.*?)</h2>(.*?)(?=<h2\b|$)",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        heading = re.sub(r"<[^>]+>", "", match.group(1))
        heading = re.sub(r"\s+", " ", heading).strip()
        if is_faq_section_heading(heading):
            bodies.append(match.group(2))
    return bodies


def extract_faq_answer_after_h3(chunk_after_h3: str) -> str:
    """Thematic FAQ answer = first <p> after <h3> only (INC-20260726-1615).

    Sibling CTA/interlink paragraphs after the answer must not enter
    acceptedAnswer / live FAQ parity. If no <p> exists, fall back to the
    remaining chunk (legacy markup).
    """
    match = re.search(r"<p\b[^>]*>.*?</p>", chunk_after_h3, flags=re.I | re.S)
    if match:
        return match.group(0)
    return chunk_after_h3


def detect_faq_h3_markup(html: str) -> list[str]:
    """If FAQ exists, require <h3>question?</h3><p>answer</p>.

    Rejects p-only FAQ (`<p>Вопрос? Ответ…</p>`) that passes whitelist but fails
    schema_gate FAQ parity (visible=0).
    """
    errors: list[str] = []
    bodies = extract_thematic_faq_bodies(html)
    if not bodies:
        return []

    # Duplicate titles already reported; still validate each body shape.
    for index, body in enumerate(bodies):
        label = "FAQ section" if len(bodies) == 1 else f"FAQ section #{index + 1}"
        h3_count = len(re.findall(r"<h3\b", body, flags=re.IGNORECASE))
        # Paragraphs that look like combined Q+A (question mark in first ~120 chars).
        p_blocks = re.findall(r"<p\b[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL)
        p_only_qa = 0
        for raw_p in p_blocks:
            plain = re.sub(r"<[^>]+>", "", raw_p)
            plain = re.sub(r"\s+", " ", plain).strip()
            if not plain:
                continue
            head = plain[:120]
            if "?" in head or "？" in head:
                # Likely «Вопрос? Ответ…» in one <p> when h3 is missing/low.
                p_only_qa += 1

        if h3_count < MIN_FAQ_H3_PAIRS:
            hint = ""
            if h3_count == 0 and p_only_qa > 0:
                hint = (
                    f" Found {p_only_qa} <p>…?…</p> block(s) without <h3> — "
                    "convert each to <h3>question?</h3><p>answer</p>."
                )
            errors.append(
                f"{label}: need ≥{MIN_FAQ_H3_PAIRS} <h3>question?</h3><p>answer</p> "
                f"pairs (found h3={h3_count}). schema_gate reads visible FAQ from "
                f"<h3> only; p-only FAQ → visible=0.{hint}"
            )
            continue

        # Each h3 should be followed by answer content before the next h3.
        chunks = re.split(r"(?=<h3\b)", body, flags=re.IGNORECASE)
        empty_answers = 0
        for chunk in chunks:
            q = re.search(r"<h3\b[^>]*>(.*?)</h3>", chunk, flags=re.IGNORECASE | re.DOTALL)
            if not q:
                continue
            after = chunk[q.end() :]
            answer_plain = re.sub(r"<[^>]+>", " ", after)
            answer_plain = re.sub(r"\s+", " ", answer_plain).strip()
            if len(answer_plain) < 20:
                empty_answers += 1
        if empty_answers:
            errors.append(
                f"{label}: {empty_answers} <h3> pair(s) lack a following answer "
                f"(need <p>…</p> with ≥20 chars of text after each question)."
            )
    return errors


class HTMLTagLinter(HTMLParser):
    def __init__(self, whitelist: set[str]) -> None:
        super().__init__()
        self.whitelist = whitelist
        self.errors: list[str] = []
        self.tag_stack: list[tuple[str, int, int]] = []  # (tag, line, col)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        line, col = self.getpos()

        # Check whitelist
        if tag_lower not in self.whitelist:
            self.errors.append(f"Line {line}, Col {col}: Forbidden HTML tag <{tag}> used.")

        # Check nested structure
        # Self-closing tags in HTML5 parser like <img> don't need closing, but we stack block elements
        self_closing = {"img", "br", "hr"}
        if tag_lower not in self_closing:
            self.tag_stack.append((tag_lower, line, col))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        line, col = self.getpos()
        self_closing = {"img", "br", "hr"}
        if tag_lower in self_closing:
            return

        if not self.tag_stack:
            self.errors.append(f"Line {line}, Col {col}: Unexpected closing tag </{tag_lower}> with no matching open tag.")
            return

        # Find matching open tag in stack
        expected_tag, o_line, o_col = self.tag_stack.pop()
        if expected_tag != tag_lower:
            self.errors.append(
                f"Line {line}, Col {col}: Tag mismatch. Closed </{tag_lower}> but expected </{expected_tag}> "
                f"opened at Line {o_line}, Col {o_col}."
            )
            # Re-push expected tag to stack to keep linting subsequent tags gracefully
            self.tag_stack.append((expected_tag, o_line, o_col))

    def check_unclosed_tags(self) -> None:
        while self.tag_stack:
            tag, line, col = self.tag_stack.pop()
            self.errors.append(f"Line {line}, Col {col}: Unclosed HTML tag <{tag}> at end of document.")


def lint_html_file(html_path: Path, whitelist: set[str]) -> dict[str, Any]:
    html_content = html_path.read_text(encoding="utf-8")
    linter = HTMLTagLinter(whitelist)
    linter.feed(html_content)
    linter.check_unclosed_tags()
    linter.errors.extend(detect_anchor_toc(html_content))
    linter.errors.extend(detect_duplicate_faq_sections(html_content))
    linter.errors.extend(detect_faq_h3_markup(html_content))

    return {
        "file": str(html_path.name),
        "verdict": "pass" if not linter.errors else "fail",
        "total_errors": len(linter.errors),
        "errors": linter.errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Excalibur BLOG HTML Whitelist & Nesting Linter")
    ap.add_argument("html", type=Path, help="Path to article.html")
    ap.add_argument("-o", "--output", type=Path, help="Path to write html-linter-report.json")
    args = ap.parse_args()

    if not args.html.is_file():
        print(f"File not found: {args.html}", file=sys.stderr)
        return 2

    report = lint_html_file(args.html, ALLOWED_TAGS)
    text = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")

    print(f"HTML Linter Verdict: {report['verdict'].upper()}")
    if report["errors"]:
        print(f"Found {report['total_errors']} HTML errors/warnings:")
        for err in report["errors"]:
            print(f" - {err}")
    else:
        print("All HTML tags are clean, validated, and conform to whitelist!")

    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
