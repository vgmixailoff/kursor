#!/usr/bin/env python3
"""Prepare and place one fact-checked, in-article AI visual (not the cover)."""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from asset_download import download_url_bytes
from excalibur_blog_inline_fact_card import inject_inline_figures
from image_validate import validate_image_file

TYPES = {
    "process": "a left-to-right process with hand-drawn arrows",
    "comparison": "two clearly separated comparison columns",
    "table": "a spacious hand-ruled table",
    "stats": "large exact figures with short supporting labels",
    "relationships": "a central concept linked to surrounding nodes",
    "decision": "a clear branching decision tree",
}
MODEL = "gpt-image-2-text-to-image"
FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _write_box(draw: ImageDraw.ImageDraw, label: str, box: tuple[int, int, int, int],
               *, size: int = 27) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, outline="black", width=3)
    font = _font(size)
    max_width = x1 - x0 - 32
    words = label.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    line_height = size + 12
    if len(lines) * line_height > y1 - y0 - 22:
        raise ValueError(f"label cannot fit in fallback diagram: {label!r}")
    for i, line in enumerate(lines):
        if draw.textbbox((0, 0), line, font=font)[2] > max_width:
            raise ValueError(f"label too wide for fallback diagram: {label!r}")
        draw.text((x0 + 16, y0 + 14 + i * line_height), line, fill="black", font=font)


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    draw.line((*start, *end), fill="black", width=3)
    x, y = end
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        draw.line((x - 12, y - 8, x, y, x - 12, y + 8), fill="black", width=3)
    else:
        draw.line((x - 8, y - 12, x, y, x + 8, y - 12), fill="black", width=3)


def render_fallback(article_dir: Path, plan: dict[str, Any], lines: list[str]) -> Path:
    """Exact-label monochrome fallback; never substitutes canned facts."""
    slot = str(plan["slot"])
    kind = str(plan["type"])
    out = article_dir / "cover" / f"inline-{int(slot.rsplit('_', 1)[1]):02d}.png"
    image = Image.new("RGB", (1200, 675), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(38)
    if draw.textbbox((0, 0), lines[0], font=title_font)[2] > 1072:
        title_font = _font(30)
    if draw.textbbox((0, 0), lines[0], font=title_font)[2] > 1072:
        raise ValueError("title too wide for fallback diagram")
    draw.text((64, 43), lines[0], fill="black", font=title_font)
    draw.line((64, 110, 1136, 110), fill="black", width=3)
    labels = lines[1:]
    count = len(labels)
    if kind in {"process", "comparison", "stats", "table"}:
        if kind == "process":
            gap = 24
            width = (1072 - gap * (count - 1)) // count
            boxes = [(64 + i * (width + gap), 230, 64 + i * (width + gap) + width, 425)
                     for i in range(count)]
            for i, (label, box) in enumerate(zip(labels, boxes)):
                _write_box(draw, label, box, size=23)
                if i:
                    _arrow(draw, (boxes[i - 1][2] + 3, 328), (box[0] - 4, 328))
        elif kind == "comparison":
            if count != 2:
                raise ValueError("comparison fallback requires exactly two labels")
            for label, box in zip(labels, [(64, 170, 578, 575), (622, 170, 1136, 575)]):
                _write_box(draw, label, box, size=30)
        else:
            gap = 16
            height = (480 - gap * (count - 1)) // count
            for i, label in enumerate(labels):
                y = 145 + i * (height + gap)
                _write_box(draw, label, (64, y, 1136, y + height), size=26)
    elif kind == "relationships":
        if count < 3:
            raise ValueError("relationships fallback requires a center and two related labels")
        center = (422, 180, 778, 320)
        _write_box(draw, labels[0], center, size=25)
        related = labels[1:]
        gap = 18
        width = (1072 - gap * (len(related) - 1)) // len(related)
        for i, label in enumerate(related):
            box = (64 + i * (width + gap), 435, 64 + i * (width + gap) + width, 575)
            _arrow(draw, (600, 320), ((box[0] + box[2]) // 2, 430))
            _write_box(draw, label, box, size=23)
    else:  # decision
        if count < 3:
            raise ValueError("decision fallback requires a choice and two branches")
        root = (422, 165, 778, 305)
        _write_box(draw, labels[0], root, size=25)
        branches = labels[1:]
        gap = 18
        width = (1072 - gap * (len(branches) - 1)) // len(branches)
        for i, label in enumerate(branches):
            box = (64 + i * (width + gap), 425, 64 + i * (width + gap) + width, 580)
            _arrow(draw, (600, 305), ((box[0] + box[2]) // 2, 420))
            _write_box(draw, label, box, size=23)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG")
    return out


def load_plan(article_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    plan = json.loads((article_dir / "cover" / "inline-visual-plan.json").read_text(encoding="utf-8"))
    article = json.loads((article_dir / "gemini-article.json").read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or not isinstance(article, dict):
        raise ValueError("plan and article must be JSON objects")
    slot = str(plan.get("slot") or "")
    kind = str(plan.get("type") or "")
    if slot not in {f"inline_{n}" for n in range(1, 5)}:
        raise ValueError("plan.slot must be inline_1 … inline_4")
    if kind not in TYPES:
        raise ValueError(f"plan.type must be one of {', '.join(TYPES)}")
    n = slot.rsplit("_", 1)[1]
    onimage = str(article.get(f"INLINE{n}_ONIMAGE") or "").strip()
    alt = str(article.get(f"INLINE{n}_ALT") or "").strip()
    lines = [line.strip() for line in onimage.replace("|", "\n").splitlines() if line.strip()]
    if not 3 <= len(lines) <= 6 or any(len(line) > 70 for line in lines):
        raise ValueError("INLINE*_ONIMAGE needs a title and 2–5 short verified labels (≤70 chars each)")
    if not alt:
        raise ValueError(f"INLINE{n}_ALT missing")
    body = str(article.get("BODY") or "")
    if body.count(f'data-slot="{slot}"') != 1:
        raise ValueError(f"BODY must have exactly one semantic {slot} figure slot")
    return plan, article, lines


def build_batch(plan: dict[str, Any], lines: list[str], style: str) -> dict[str, Any]:
    kind = str(plan["type"])
    labels = "\n".join(f"- {line}" for line in lines)
    prompt = (
        f"{style.strip()}\n\n"
        f"Layout: {TYPES[kind]}.\n"
        "Use ONLY these exact visible Russian labels, verbatim and in this order:\n"
        f"{labels}\n"
        "No other words, numbers, logos, invented facts, UI, colored elements, or watermark. "
        "If a label cannot fit, leave that space blank; never paraphrase or change a digit. "
        "Readable on a phone."
    )
    return {
        "canon": "article_inline_visual",
        "model": MODEL,
        "jobs": [{"id": f"{plan['slot']}-{kind}", "mcp_args": {
            "prompt": prompt, "aspect_ratio": "16:9", "resolution": "1K"
        }}],
        "validation": {"model": MODEL, "slot": plan["slot"], "type": kind, "labels": lines},
    }


def save_png(article_dir: Path, slot: str, url: str) -> Path:
    n = slot.rsplit("_", 1)[1]
    out = article_dir / "cover" / f"inline-{int(n):02d}.png"
    blob, _ = download_url_bytes(url)
    with Image.open(io.BytesIO(blob)) as image:
        image.convert("RGB").save(out, format="PNG")
    errors = validate_image_file(out)
    if errors:
        raise ValueError("; ".join(errors))
    return out


def inject(article_dir: Path, slot: str, alt: str) -> Path:
    n = slot.rsplit("_", 1)[1]
    image = article_dir / "cover" / f"inline-{int(n):02d}.png"
    if not image.is_file():
        raise ValueError(f"image missing: {image}")
    html_path = article_dir / "article.html"
    html = html_path.read_text(encoding="utf-8")
    if html.count(f'data-slot="{slot}"') != 1:
        raise ValueError(f"article.html must have exactly one {slot} slot")
    updated = inject_inline_figures(html, [{
        "slot": slot, "src": f"cover/{image.name}", "alt": alt,
    }])
    html_path.write_text(updated, encoding="utf-8")
    return html_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("prepare", "download", "inject", "fallback"))
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()
    try:
        plan, article, lines = load_plan(article_dir)
        slot = str(plan["slot"])
        n = slot.rsplit("_", 1)[1]
        if args.action == "prepare":
            style = (root / "shared" / "inline-visual-style.md").read_text(encoding="utf-8")
            batch = build_batch(plan, lines, style)
            out = article_dir / "cover" / "inline-visual-batch.json"
            out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif args.action == "download":
            result = json.loads((article_dir / "cover" / "inline-visual-kie-result.json").read_text(encoding="utf-8"))
            url = str(result.get("url") or "")
            if not url.startswith("https://"):
                raise ValueError("Kie result needs an https url")
            out = save_png(article_dir, slot, url)
        elif args.action == "fallback":
            out = render_fallback(article_dir, plan, lines)
            inject(article_dir, slot, str(article[f"INLINE{n}_ALT"]).strip())
        else:
            out = inject(article_dir, slot, str(article[f"INLINE{n}_ALT"]).strip())
        print(json.dumps({"status": "PASS", "action": args.action, "slot": slot, "path": str(out)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
