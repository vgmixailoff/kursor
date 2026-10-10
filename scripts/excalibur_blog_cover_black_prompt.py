#!/usr/bin/env python3
"""Build Kie GPT Image 2 text-to-image batch for black-canvas evening cover.

Reads cover/cover-text.json (from gemini materialize). Writes cover/t2i-batch.json.
Letters are drawn by the image model — no PIL/Playfair overlay.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


DIGIT_RE = re.compile(r"\d")


def build_prompt(cover_text: dict[str, Any]) -> str:
    line1 = str(cover_text.get("line1") or cover_text.get("hook") or "").strip()
    line2 = str(cover_text.get("line2") or "").strip()
    scene = str(cover_text.get("cover_prompt") or "").strip()
    if not line1 or not scene:
        raise ValueError("cover-text.json needs line1/COVER_LINE1 and cover_prompt")
    for label, val in (("COVER_LINE1", line1), ("COVER_LINE2", line2)):
        if DIGIT_RE.search(val):
            raise ValueError(f"{label} must not contain digits/dates: {val!r}")

    return (
        "16:9 editorial article cover. Solid pure black canvas filling the entire frame. "
        "Caravaggio-style chiaroscuro oil painting grows from darkness at the BOTTOM only — "
        "not a letterbox bar, not a brown room filling the frame, not a pink collage. "
        f"Scene (no letters in the painting itself): {scene}. "
        "TOP-LEFT: thin elegant white handwritten script, phone-readable, NOT filling the upper third — "
        f"line1 larger/bolder exactly «{line1}», "
        f"line2 thinner exactly «{line2}». "
        "TOP-RIGHT: official product logo only, medium size, white/clean, no badges. "
        "FORBIDDEN: pink ribbon, hot-pink sticky, t.me badge, Telegram watermark, "
        "hard horizontal divider, laptops, phone UI, screenshots, digits, dates, "
        "Playfair overlay, collage paper/tape, letterbox black plank under the scene. "
        "Single photoreal-painterly image, no collage grid."
    )


def build_batch(cover_text: dict[str, Any]) -> dict[str, Any]:
    prompt = build_prompt(cover_text)
    return {
        "canon": "black_canvas_t2i",
        "jobs": [
            {
                "id": "cover-t2i",
                "mcp_args": {
                    "prompt": prompt,
                    "aspect_ratio": "16:9",
                    "resolution": "1K",
                },
            }
        ],
        "validation": {
            "prompt_chars": len(prompt),
            "line1": cover_text.get("line1") or cover_text.get("hook"),
            "line2": cover_text.get("line2"),
            "no_input_urls": True,
            "model": "gpt-image-2-text-to-image",
        },
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

    text_path = article_dir / "cover" / "cover-text.json"
    if not text_path.is_file():
        print(json.dumps({"status": "FAIL", "errors": ["cover/cover-text.json missing"]}, ensure_ascii=False))
        return 1
    cover_text = json.loads(text_path.read_text(encoding="utf-8"))
    try:
        batch = build_batch(cover_text)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    out = article_dir / "cover" / "t2i-batch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "batch": str(out), "prompt_chars": batch["validation"]["prompt_chars"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
