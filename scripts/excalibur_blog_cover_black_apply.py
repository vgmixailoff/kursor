#!/usr/bin/env python3
"""Download Kie cover URL → cover/cover.png (featured / RSS enclosure).

Evening canon: NO maya_pro badge on cover. Inlines get badge separately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_download import download_url_bytes  # noqa: E402


def project_root() -> Path:
    env_root = os.environ.get("EXCALIBUR_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


COVER_FIGURE_RE = re.compile(
    r'<figure\s+(?=[^>]*\bdata-slot="cover")[^>]*>[\s\S]*?</figure>\s*',
    re.I,
)


def strip_cover_figure(html: str) -> str:
    """Remove the cover figure from post body.

    Featured image + RSS ``enclosure`` carry the cover. Leaving the same
    PNG as the first ``<figure>`` duplicates it on the site hero and in
    Dzen ``content:encoded``.
    """
    return COVER_FIGURE_RE.sub("", html or "", count=1).lstrip()


def inject_cover_first(html: str, *, alt: str, src: str = "cover/cover.png") -> str:
    figure = (
        f'\n<figure class="inline-visual" data-slot="cover">\n'
        f'<img src="{src}" alt="{alt}" />\n'
        f"<figcaption>{alt}</figcaption>\n"
        f"</figure>\n"
    )
    html = strip_cover_figure(html or "")
    # Place cover as the very first element in the local article.html.
    return figure + html.lstrip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--inject-html", action="store_true")
    ap.add_argument("--result", default="cover/t2i-result.json")
    args = ap.parse_args()

    root = project_root()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = root / article_dir
    cover_dir = article_dir / "cover"
    cover_dir.mkdir(parents=True, exist_ok=True)

    url = args.url.strip()
    result_path = article_dir / args.result
    preserved: dict[str, Any] = {}
    # Also accept legacy quad-mcp-result.json when used for t2i.
    if not url:
        for candidate in (result_path, cover_dir / "t2i-result.json", cover_dir / "quad-mcp-result.json"):
            if candidate.is_file():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                preserved = data if isinstance(data, dict) else {}
                url = str(data.get("url") or "").strip()
                if url:
                    break
    elif result_path.is_file():
        data = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            preserved = data
    if not url:
        print("❌ COVER T2I APPLY BLOCKER: pass --url or cover/t2i-result.json", file=sys.stderr)
        return 1

    png_path = cover_dir / "cover.png"
    blob, _ = download_url_bytes(url)
    png_path.write_bytes(blob)
    model = str(preserved.get("model") or "").strip()
    canon = str(preserved.get("canon") or "").strip()
    if not canon:
        canon = "sunburst_i2i" if "sunburst" in model else "black_canvas_t2i"
    record = {
        "url": url,
        "canon": canon,
        "bytes": len(blob),
    }
    if model:
        record["model"] = model
    if preserved.get("task_id"):
        record["task_id"] = preserved["task_id"]
    if preserved.get("source"):
        record["source"] = preserved["source"]
    (cover_dir / "t2i-result.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK cover={png_path} bytes={len(blob)}")

    # Gate: reject obvious pink/ribbon leftovers is Cover-agent responsibility;
    # here we only ensure file exists and optionally inject.
    if args.inject_html:
        alt = "обложка"
        ct = cover_dir / "cover-text.json"
        if ct.is_file():
            raw = json.loads(ct.read_text(encoding="utf-8"))
            alt = str(raw.get("cover_alt") or raw.get("line1") or alt).strip() or alt
        html_path = article_dir / "article.html"
        if not html_path.is_file():
            print("❌ article.html missing for inject", file=sys.stderr)
            return 1
        html = html_path.read_text(encoding="utf-8")
        html_path.write_text(inject_cover_first(html, alt=alt), encoding="utf-8")
        print("OK injected cover figure as first frame")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
