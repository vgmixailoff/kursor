#!/usr/bin/env python3
"""Shared article.meta.json index for cannibalization / scout / research_start.

INC-20260728-1852: orphan alt-slug dirs after slug rename (e.g. B102-avtovoronka-…
vs canonical B102-nastroika-…) keep live article.meta.json and hard-fail every
later GEO cannibalization check. Loaders must skip STALE markers and dedupe by
topic_id preferring ledger/published canonical dirs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


META_NAME = "article.meta.json"
STALE_META_SUFFIX = ".STALE-DUPLICATE"
TOPIC_DIR_RE = re.compile(r"^(B\d+)-", re.IGNORECASE)


def is_stale_article_dirname(name: str) -> bool:
    """Skip dirs quarantined as stale duplicates (name contains .STALE)."""
    upper = (name or "").upper()
    return ".STALE" in upper


def is_live_meta_path(meta_path: Path) -> bool:
    """True only for canonical article.meta.json (not *.STALE-DUPLICATE)."""
    return meta_path.is_file() and meta_path.name == META_NAME


def topic_id_from_dirname(dirname: str) -> str:
    m = TOPIC_DIR_RE.match(dirname or "")
    return m.group(1).upper() if m else ""


def load_ledger_topic_slugs(root: Path) -> dict[str, str]:
    """topic_id → latest ledger slug (later rows win)."""
    path = root / "shared" / "published-articles.md"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower() == "date" or set(cells[0]) <= {"-", ":"}:
            continue
        topic_id = (cells[1] or "").strip().upper()
        slug = (cells[2] or "").strip().strip("/")
        if not topic_id or topic_id == "TOPIC_ID":
            continue
        if slug:
            out[topic_id] = slug
    return out


def load_ledger_topic_statuses(root: Path) -> dict[str, str]:
    """topic_id → latest ledger status (later rows win)."""
    path = root / "shared" / "published-articles.md"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower() == "date" or set(cells[0]) <= {"-", ":"}:
            continue
        topic_id = (cells[1] or "").strip().upper()
        status = (cells[4] or "").strip().lower()
        if not topic_id or topic_id == "TOPIC_ID":
            continue
        out[topic_id] = status
    return out


def _meta_rank(
    article_dir: Path,
    meta: dict[str, Any],
    *,
    ledger_slugs: dict[str, str],
) -> tuple[int, int, int, str]:
    """Higher tuple wins when multiple dirs share topic_id.

    Prefer: ledger slug match > wp-publish-result > structure-gate > dir name.
    """
    tid = str(meta.get("topic_id") or topic_id_from_dirname(article_dir.name) or "").upper()
    meta_slug = str(meta.get("slug") or "").strip().strip("/")
    ledger_slug = (ledger_slugs.get(tid) or "").strip().strip("/")
    slug_match = 0
    if ledger_slug and (
        meta_slug == ledger_slug
        or article_dir.name == f"{tid}-{ledger_slug}"
        or article_dir.name.lower() == f"{tid.lower()}-{ledger_slug.lower()}"
    ):
        slug_match = 2
    elif ledger_slug and ledger_slug in article_dir.name:
        slug_match = 1

    has_wp = 1 if (article_dir / "wp-publish-result.json").is_file() else 0
    has_structure = 1 if (
        (article_dir / "structure-gate.json").is_file()
        or (article_dir / "geo-qa-gate.json").is_file()
    ) else 0
    return (slug_match, has_wp, has_structure, article_dir.name)


def quarantine_stale_meta(meta_path: Path) -> Path | None:
    """Rename article.meta.json → article.meta.json.STALE-DUPLICATE (idempotent)."""
    if not is_live_meta_path(meta_path):
        return None
    dest = meta_path.with_name(meta_path.name + STALE_META_SUFFIX)
    if dest.exists():
        # Keep existing quarantine; drop the live duplicate meta.
        meta_path.unlink()
        return dest
    meta_path.rename(dest)
    return dest


def quarantine_sibling_topic_dirs(
    articles_dir: Path,
    *,
    topic_id: str,
    keep_dir: Path,
) -> list[Path]:
    """Quarantine live meta in other Bxx-* dirs for the same topic_id.

    Called from research_start after creating/selecting the canonical article dir
    so a slug rename does not leave a colliding orphan meta.
    """
    tid = (topic_id or "").strip().upper()
    if not tid or not articles_dir.is_dir():
        return []
    keep = keep_dir.resolve()
    quarantined: list[Path] = []
    prefix = f"{tid}-"
    for path in sorted(articles_dir.iterdir()):
        if not path.is_dir() or is_stale_article_dirname(path.name):
            continue
        if not path.name.upper().startswith(prefix):
            continue
        if path.resolve() == keep:
            continue
        meta_path = path / META_NAME
        if not is_live_meta_path(meta_path):
            continue
        dest = quarantine_stale_meta(meta_path)
        if dest is not None:
            quarantined.append(dest)
    return quarantined


def iter_candidate_meta_paths(blog_dir: Path) -> list[Path]:
    """All live article.meta.json under blog_dir, skipping STALE dirnames."""
    if not blog_dir.is_dir():
        return []
    out: list[Path] = []
    for article_dir in sorted(blog_dir.iterdir()):
        if not article_dir.is_dir() or is_stale_article_dirname(article_dir.name):
            continue
        meta_path = article_dir / META_NAME
        if is_live_meta_path(meta_path):
            out.append(meta_path)
    return out


def resolve_project_root(blog_dir: Path, root: Path | None = None) -> Path:
    if root is not None:
        return root
    resolved = blog_dir.resolve()
    # memory/blog/articles → project root
    if resolved.name == "articles" and resolved.parent.name == "blog":
        return resolved.parents[2]
    if (resolved / "shared").is_dir():
        return resolved
    return Path.cwd()


def load_article_metas(
    blog_dir: Path,
    *,
    root: Path | None = None,
    dedupe_topic_id: bool = True,
) -> list[dict[str, Any]]:
    """Load article metas for cannibalization / uniqueness checks.

    - Skips dirs whose name contains ``.STALE`` (INC-20260728-1852).
    - Only reads canonical ``article.meta.json`` (not ``*.STALE-DUPLICATE``).
    - When ``dedupe_topic_id``, keeps one dir per topic_id (ledger slug /
      published artifacts win). Orphan alt-slug losers are omitted from the
      index (caller may quarantine separately).
    """
    project_root = resolve_project_root(blog_dir, root)
    ledger_slugs = load_ledger_topic_slugs(project_root)
    candidates: list[dict[str, Any]] = []

    for meta_path in iter_candidate_meta_paths(blog_dir):
        article_dir = meta_path.parent
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        tid = str(meta.get("topic_id") or topic_id_from_dirname(article_dir.name) or "").strip().upper()
        if not tid:
            tid = article_dir.name
        primary = str(meta.get("primary_query") or "").strip()
        secondary = meta.get("secondary_queries") or []
        if not isinstance(secondary, list):
            secondary = []
        row = {
            "topic_id": tid,
            "dir_name": article_dir.name,
            "primary_query": primary,
            "secondary_queries": [str(x) for x in secondary if str(x).strip()],
            "slug": str(meta.get("slug") or "").strip().strip("/"),
            "meta_path": meta_path,
            "article_dir": article_dir,
            "_rank": _meta_rank(article_dir, meta, ledger_slugs=ledger_slugs),
        }
        candidates.append(row)

    if not dedupe_topic_id:
        for row in candidates:
            row.pop("_rank", None)
        return candidates

    best: dict[str, dict[str, Any]] = {}
    for row in candidates:
        tid = row["topic_id"]
        prev = best.get(tid)
        if prev is None or row["_rank"] > prev["_rank"]:
            best[tid] = row

    out: list[dict[str, Any]] = []
    for row in sorted(best.values(), key=lambda r: r["dir_name"]):
        row.pop("_rank", None)
        out.append(row)
    return out
