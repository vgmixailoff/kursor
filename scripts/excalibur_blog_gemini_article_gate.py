#!/usr/bin/env python3
"""Gate Gemini article: visible length, one CTA, quote language, H2, title."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

CTA_URLS = (
    "https://t.me/maya_pro",
    "https://max.ru/maya_pro",
    "https://kv-ai.ru/obuchenie-po-make",
)
FORBIDDEN_URL_RE = re.compile(
    r"https?://(?:t\.me|telegram\.me)/(?:s/)?kovcheg_ai\b",
    re.I,
)
FORBIDDEN_H2 = (
    "чем это не является",
    "что сделать сегодня",
)
FORBIDDEN_TITLE_PATTERNS = (
    re.compile(r"пошагов(?:ая|ую|ой|ое)?\s+инструкци", re.I),
    re.compile(r"чек[- ]?лист", re.I),
    re.compile(r"полный\s+гайд", re.I),
    re.compile(r"без\s+копипаст", re.I),
    re.compile(r"за\s+(?:один\s+)?вечер", re.I),
)
EMOJI_RE = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]",
    flags=re.UNICODE,
)
KANTSELYARIT_RE = re.compile(
    r"\b(важно\s+отметить|следует\s+подчеркнуть|в\s+современном\s+мире|в\s+рамках\s+данн|осуществлять)\b",
    re.I,
)
# A quoted product name is not an untranslated English quotation.
GUILLEMETS = re.compile(r"«([^»]*)»")
# English inside <blockquote>
EN_WORD = re.compile(r"[A-Za-z]{4,}")
BRANDISH = {
    "cursor", "make", "claude", "openai", "google", "microsoft", "nvidia",
    "gemini", "grok", "anthropic", "chatgpt", "gmail", "telegram", "max",
    "codex", "mcp", "api", "ai", "gpt", "llm", "json",
}


class _VisibleText(HTMLParser):
    """Prose only: skip script/style and injected <figure> (cover/captions)."""

    _SKIP_TREE = frozenset({"script", "style", "figure"})

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._SKIP_TREE:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TREE and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def visible_text(html: str) -> str:
    p = _VisibleText()
    p.feed(html or "")
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def _h2_texts(html: str) -> list[str]:
    return [re.sub(r"\s+", " ", m).strip() for m in re.findall(
        r"<h2\b[^>]*>(.*?)</h2>", html or "", flags=re.I | re.S
    )]


def _blockquotes(html: str) -> list[str]:
    return re.findall(r"<blockquote\b[^>]*>(.*?)</blockquote>", html or "", flags=re.I | re.S)


def _cta_href_positions(html: str) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {u: [] for u in CTA_URLS}
    for m in re.finditer(r"""href=["']([^"']+)["']""", html or "", flags=re.I):
        href = m.group(1).split("?", 1)[0].split("#", 1)[0].rstrip("/")
        for url in CTA_URLS:
            if href == url.rstrip("/"):
                out[url].append(m.start())
    return out


def check_article(article_dir: Path, *, product_hint: str = "") -> dict[str, Any]:
    errors: list[str] = []
    gemini_path = article_dir / "gemini-article.json"
    html_path = article_dir / "article.html"
    title_brief = {}
    title_path = article_dir / "title-brief.json"
    if title_path.is_file():
        try:
            title_brief = json.loads(title_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append("title-brief.json invalid JSON")

    gemini: dict[str, Any] = {}
    if gemini_path.is_file():
        try:
            loaded = json.loads(gemini_path.read_text(encoding="utf-8"))
            gemini = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            errors.append("gemini-article.json invalid JSON")
    else:
        errors.append("gemini-article.json missing")

    if not html_path.is_file():
        errors.append("article.html missing")
        html = ""
    else:
        html = html_path.read_text(encoding="utf-8")

    title = str(
        gemini.get("TITLE")
        or title_brief.get("h1")
        or title_brief.get("title")
        or ""
    ).strip()
    if not title:
        errors.append("TITLE empty")
    else:
        # Product name: prefer COVER_LINE1 / subject / hint — must appear in title.
        product = (
            product_hint
            or str(gemini.get("COVER_LINE1") or "").strip()
            or str(title_brief.get("subject") or "").strip()
        )
        # First token-ish product words from COVER_LINE1 (often the product name).
        if product:
            # Require at least one significant token from product in TITLE.
            tokens = [t for t in re.split(r"\s+", product) if len(t) >= 3]
            title_cf = title.casefold()
            if tokens and not any(t.casefold() in title_cf for t in tokens[:3]):
                errors.append(
                    f"TITLE missing product name from COVER_LINE1/subject ({product!r})"
                )
        # Stack of Latin product names in title (3+ distinct Capitalized Latin tokens).
        caps = re.findall(r"\b[A-Z][A-Za-z0-9.+-]{1,}\b", title)
        if len(set(caps)) >= 3:
            errors.append(f"TITLE stacks too many Latin product names: {caps}")

        # Ban emojis in TITLE
        if EMOJI_RE.search(title):
            errors.append("TITLE contains forbidden emoji")

        # Ban SEO template titles in TITLE
        for rx in FORBIDDEN_TITLE_PATTERNS:
            if rx.search(title):
                errors.append(f"TITLE contains forbidden template phrase: {rx.pattern}")

    description = str(gemini.get("DESCRIPTION") or "").strip()
    if not description:
        errors.append("DESCRIPTION empty")
    else:
        n_desc = len(description)
        if n_desc < 80 or n_desc > 180:
            errors.append(f"DESCRIPTION length {n_desc} out of range 80–180")
        if re.search(r"<[^>]+>", description):
            errors.append("DESCRIPTION contains HTML")
        if title and description.casefold() == title.casefold():
            errors.append("DESCRIPTION duplicates TITLE")

    visible = visible_text(html)
    n = len(visible)
    if n < 2500 or n > 6500:
        errors.append(
            f"BODY visible chars {n} out of range 2500–6500; "
            "edit a paragraph in gemini-article.json and rerun "
            "excalibur_blog_body_len.py (do not emit a length script)"
        )

    if FORBIDDEN_URL_RE.search(html) or "ковчег ai" in visible.casefold():
        errors.append("forbidden kovcheg_ai / «Ковчег AI»")

    positions = _cta_href_positions(html)
    if sum(len(items) for items in positions.values()) != 1:
        errors.append("BODY needs exactly one CTA href from the allowed links")

    # Exactly one mid-article CTA paragraph cluster: first CTA after 25% and before 75%.
    all_pos = sorted(p for ps in positions.values() for p in ps)
    if all_pos and html:
        mid = all_pos[0]
        frac = mid / max(len(html), 1)
        if frac < 0.20 or frac > 0.80:
            errors.append(
                f"first CTA href at {frac:.0%} of HTML — need mid-article (~20–80%)"
            )

    for h2 in _h2_texts(html):
        plain = re.sub(r"<[^>]+>", "", h2).strip().casefold()
        for ban in FORBIDDEN_H2:
            if ban in plain:
                errors.append(f"forbidden H2: {h2!r}")

    # Check for канцелярит in visible body
    for m in KANTSELYARIT_RE.finditer(visible):
        errors.append(f"канцелярит forbidden in body: {m.group(0)!r}")

    for quoted in GUILLEMETS.findall(visible):
        words = re.findall(r"[A-Za-z]{3,}", quoted)
        if words and not re.search(r"[А-Яа-яЁё]", quoted) and any(
            word.lower() not in BRANDISH for word in words
        ):
            errors.append("untranslated English quotation inside «ёлочки»")
            break

    bqs = _blockquotes(html)
    for bq in bqs:
        plain = visible_text(bq)
        for w in EN_WORD.findall(plain):
            if w.lower() in BRANDISH:
                continue
            if len(w) >= 4:
                errors.append(f"English in <blockquote>: {w!r}")
                break

    # Keep product versions (e.g. GPT-5) on covers; only decorative years are banned.
    for key in ("COVER_LINE1", "COVER_LINE2"):
        line = str(gemini.get(key) or "").strip()
        if re.search(r"(?<!\w)20\d{2}(?!\w)", line):
            errors.append(f"{key} contains a decorative year — forbidden on cover")

    # Alt-тексты на русском (COVER_ALT / INLINE*_ALT).
    for key in ("COVER_ALT",) + tuple(f"INLINE{i}_ALT" for i in range(1, 5)):
        alt = str(gemini.get(key) or "").strip()
        if not alt:
            continue
        if not re.search(r"[А-Яа-яЁё]", alt):
            errors.append(f"{key} must be Russian (Cyrillic), got {alt!r}")

    # Optional official screenshots still need Writer-owned, paired Russian text.
    for i in range(1, 5):
        alt_key, caption_key = f"SCREENSHOT{i}_ALT", f"SCREENSHOT{i}_CAPTION"
        alt = str(gemini.get(alt_key) or "").strip()
        caption = str(gemini.get(caption_key) or "").strip()
        if bool(alt) != bool(caption):
            errors.append(f"{alt_key} and {caption_key} must be provided together")
        for key, value in ((alt_key, alt), (caption_key, caption)):
            if value and not re.search(r"[А-Яа-яЁё]", value):
                errors.append(f"{key} must be Russian (Cyrillic), got {value!r}")

    status = "PASS" if not errors else "FAIL"
    return {
        "gate": "gemini-article",
        "status": status,
        "title": title,
        "body_visible_chars": n,
        "blockquote_count": len(bqs),
        "cta_present": {u: bool(positions[u]) for u in CTA_URLS},
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--product-hint", default="")
    ap.add_argument("-o", "--output", default="gemini-article-gate.json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()

    report = check_article(article_dir, product_hint=args.product_hint)
    out = article_dir / Path(args.output).name
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
