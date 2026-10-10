#!/usr/bin/env python3
"""Helper script for Excalibur BLOG Scout Agent to find next IDs and avoid keyword cannibalization."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from excalibur_blog_article_meta_index import load_article_metas
from excalibur_blog_topic_focus import focus_check

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def load_published_topics(root: Path) -> set[str]:
    ledger_path = root / "shared/published-articles.md"
    published = set()
    if not ledger_path.is_file():
        return published
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 20"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5 and cells[4].lower() in {"published", "in_progress", "draft_ready"}:
                published.add(cells[1].upper())
    return published


def load_published_rows(root: Path) -> list[dict[str, str]]:
    ledger_path = root / "shared/published-articles.md"
    rows: list[dict[str, str]] = []
    if not ledger_path.is_file():
        return rows
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        rows.append(
            {
                "date": cells[0],
                "topic_id": cells[1].upper(),
                "slug": cells[2],
                "url": cells[3],
                "status": cells[4].lower(),
            }
        )
    return rows


def fetch_recent_wp_topics(limit: int = 40) -> list[dict[str, str]]:
    site_url = (os.environ.get("PUBLIC_SITE_URL") or os.environ.get("WP_SITE_URL") or "").strip()
    if not site_url:
        return []
    endpoint = urljoin(
        site_url.rstrip("/") + "/",
        f"wp-json/wp/v2/posts?per_page={limit}&orderby=date&order=desc&_fields=date,slug,title",
    )
    try:
        with urlopen(Request(endpoint, headers={"User-Agent": "ExcaliburScoutHelper/1.0"}), timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    topics: list[dict[str, str]] = []
    for item in payload:
        title = item.get("title", {}).get("rendered", "") if isinstance(item.get("title"), dict) else ""
        title = re.sub(r"<[^>]+>", " ", str(title))
        slug = str(item.get("slug") or "")
        if not slug:
            continue
        topics.append(
            {
                "topic_id": f"LIVE-{slug[:24]}".upper(),
                "primary_query": " ".join([slug.replace("-", " "), title]).strip(),
                "slug": slug,
                "priority": "live",
            }
        )
    return topics


def load_active_article_topics(root: Path) -> set[str]:
    articles_dir = root / "memory" / "blog" / "articles"
    if not articles_dir.is_dir():
        return set()
    active: set[str] = set()
    for path in articles_dir.iterdir():
        if not path.is_dir():
            continue
        match = re.match(r"(B\d+)-", path.name, flags=re.IGNORECASE)
        if match:
            active.add(match.group(1).upper())
    return active


def load_existing_topics(root: Path) -> list[dict[str, str]]:
    # memory/topics/ permanently removed — no on-disk topic pool.
    _ = root
    return []


def load_published_as_topics(root: Path) -> list[dict[str, str]]:
    topics: list[dict[str, str]] = []
    for row in load_published_rows(root):
        if row["status"] not in {"published", "in_progress", "draft_ready"}:
            continue
        slug = row.get("slug") or ""
        if not slug:
            continue
        topics.append(
            {
                "topic_id": row["topic_id"],
                "primary_query": slug.replace("-", " "),
                "slug": slug,
                "priority": row["status"],
            }
        )
    return topics


def load_article_meta_primaries(root: Path) -> list[dict[str, str]]:
    """Real primary_query from article.meta.json (stronger than slug-derived).

    INC-20260713-1215: slug-only check misses exact primary collisions like
    B25/B30 «ai агенты для бизнеса».
    INC-20260728-1852: skip STALE dirs / orphan alt-slug duplicates.
    """
    articles_dir = root / "memory" / "blog" / "articles"
    topics: list[dict[str, str]] = []
    for row in load_article_metas(articles_dir, root=root, dedupe_topic_id=True):
        primary = str(row.get("primary_query") or "").strip()
        if not primary:
            continue
        tid = str(row.get("topic_id") or "").strip().upper()
        slug = str(row.get("slug") or row.get("dir_name") or "").strip().strip("/")
        topics.append(
            {
                "topic_id": tid,
                "primary_query": primary,
                "slug": slug,
                "priority": "article_meta",
            }
        )
    return topics

# Cyrillic→Latin for Russian SEO slugs (passport-ish; matches ledger WP* paths).
# INC-20260727-0805: «автопостинг вк» must overlap slug avtoposting-vk-*.
_CYR_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "j",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

# Whole-word brand/channel aliases (Cyrillic query ↔ Latin slug tokens).
_WORD_ALIASES = {
    "вк": "vk",
    "вконтакте": "vk",
    "телеграм": "telegram",
    "телеграмм": "telegram",
    "тг": "telegram",
    "дзен": "dzen",
    "яндекс": "yandeks",
    "инстаграм": "instagram",
    "instagram": "instagram",
    "пинтерест": "pinterest",
    "ютуб": "youtube",
    "ютьюб": "youtube",
    "youtube": "youtube",
    "автопостинг": "avtoposting",
    "кросспостинг": "krossposting",
    "crossposting": "krossposting",
}

_STOPWORDS = {
    "в",
    "на",
    "и",
    "или",
    "с",
    "по",
    "для",
    "как",
    "что",
    "это",
    "the",
    "a",
    "an",
    "to",
    "of",
    "and",
    "or",
}


def transliterate_ru(text: str) -> str:
    """Map Cyrillic letters to Latin used in published-articles slugs."""
    out: list[str] = []
    for ch in text.lower():
        if ch in _CYR_TO_LAT:
            out.append(_CYR_TO_LAT[ch])
        else:
            out.append(ch)
    return "".join(out)


def _stem_token(word: str) -> str:
    w = word.strip().lower()
    if not w:
        return ""
    w = _WORD_ALIASES.get(w, w)
    if any("а" <= c <= "я" or c in "ё" for c in w):
        w = transliterate_ru(w)
        w = _WORD_ALIASES.get(w, w)
    if not w or w in _STOPWORDS:
        return ""
    return w[:5] if len(w) > 4 else w


def normalize_and_tokenize(text: str) -> set[str]:
    """Token stems; Cyrillic queries get Latin stems so they match ledger slugs."""
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    tokens: set[str] = set()
    for raw in text.split():
        stem = _stem_token(raw)
        if stem:
            tokens.add(stem)
    return tokens


def topic_comparable_text(topic: dict[str, str]) -> str:
    """primary_query + slug so path-only WP* ledger rows participate in overlap."""
    return " ".join(
        [
            str(topic.get("primary_query") or "").strip(),
            str(topic.get("slug") or "").strip().replace("-", " "),
        ]
    ).strip()


def check_overlap(new_query: str, existing_topics: list[dict[str, str]], reserved_ids: set[str]) -> list[dict[str, Any]]:
    new_tokens = normalize_and_tokenize(new_query)
    warnings = []
    seen_keys: set[tuple[str, str, str]] = set()

    for t in existing_topics:
        comparable = topic_comparable_text(t)
        ext_tokens = normalize_and_tokenize(comparable)
        if not new_tokens or not ext_tokens:
            continue
        intersection = new_tokens.intersection(ext_tokens)
        union = new_tokens.union(ext_tokens)
        similarity = len(intersection) / len(union) if union else 0.0

        status = "reserved" if t["topic_id"] in reserved_ids else "in_pool"
        primary = (t.get("primary_query") or "").strip()
        slug = (t.get("slug") or "").strip().strip("/")
        topic_id = t.get("topic_id") or ""

        def _emit(severity: str, sim: float, message: str) -> None:
            key = (str(topic_id).upper(), severity, message[:80])
            if key in seen_keys:
                return
            seen_keys.add(key)
            warnings.append(
                {
                    "severity": severity,
                    "topic_id": topic_id,
                    "similarity": sim,
                    "status": status,
                    "slug": slug,
                    "message": message,
                }
            )

        if primary and primary.lower() == new_query.strip().lower():
            _emit(
                "CRITICAL",
                1.0,
                f"EXACT MATCH found with topic {topic_id} ({status})! Primary query: '{primary}'",
            )
            continue

        # Query stems fully covered by ledger/live slug tokens (Cyrillic↔Latin).
        # INC-20260727-0805: «автопостинг вк» ⊂ avtoposting-vk-make-google-sheets.
        substantial = {tok for tok in new_tokens if len(tok) >= 4}
        if (
            len(new_tokens) >= 2
            and new_tokens.issubset(ext_tokens)
            and substantial
            and slug
        ):
            _emit(
                "CRITICAL",
                1.0,
                (
                    f"SLUG KEYWORD COVER: query stems {sorted(new_tokens)} all appear in "
                    f"ledger/live slug '/{slug}/' ({topic_id}, {status}). "
                    "Do NOT append — pick another channel/angle."
                ),
            )
            continue

        if similarity >= 0.35:
            _emit(
                "WARNING",
                round(similarity, 2),
                (
                    f"High overlap ({round(similarity * 100)}%) with topic {topic_id} ({status}). "
                    f"Query/slug: '{comparable}'"
                ),
            )
    return warnings


def check_slug(new_slug: str, existing_topics: list[dict[str, str]]) -> list[dict[str, Any]]:
    slug = new_slug.strip().strip("/").lower()
    if not slug:
        return []
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for t in existing_topics:
        existing_slug = (t.get("slug") or "").strip().strip("/").lower()
        if existing_slug == slug:
            key = ((t.get("topic_id") or "").upper(), existing_slug)
            if key in seen:
                continue
            seen.add(key)
            topic_id = t.get("topic_id") or ""
            source = "live_wp" if str(topic_id).upper().startswith("LIVE-") else "ledger_or_pool"
            warnings.append(
                {
                    "severity": "CRITICAL",
                    "topic_id": topic_id,
                    "similarity": 1.0,
                    "status": "slug_exists",
                    "source": source,
                    "message": (
                        f"SLUG MATCH found with {topic_id}: '{slug}' "
                        f"({'live WordPress — topic taken even if ledger empty' if source == 'live_wp' else 'ledger/pool'})"
                    ),
                }
            )
    return warnings


def ledger_slugs(root: Path) -> set[str]:
    return {
        (row.get("slug") or "").strip().strip("/").lower()
        for row in load_published_rows(root)
        if row.get("status") in {"published", "in_progress", "draft_ready"} and row.get("slug")
    }


def report_ledger_drift(root: Path, live_topics: list[dict[str, str]], limit: int = 20) -> list[dict[str, str]]:
    """Live WP slugs missing from shared/published-articles.md (ledger lag)."""
    known = ledger_slugs(root)
    drift: list[dict[str, str]] = []
    for t in live_topics:
        slug = (t.get("slug") or "").strip().strip("/").lower()
        if not slug or slug in known:
            continue
        drift.append(
            {
                "slug": slug,
                "topic_id": t.get("topic_id") or "",
                "suggested_ledger_row": (
                    f"| YYYY-MM-DD | WP<post_id> | {slug} | /{slug}/ | published |"
                ),
            }
        )
        if len(drift) >= limit:
            break
    return drift


def main() -> int:
    ap = argparse.ArgumentParser(description="Helper for Excalibur BLOG Scout Agent")
    ap.add_argument("--suggest-next", action="store_true", help="Print next available Topic ID and summary")
    ap.add_argument("--check-query", type=str, default="", help="Check new primary query for overlaps")
    ap.add_argument("--check-slug", type=str, default="", help="Check new slug against ledger and recent live WP posts")
    ap.add_argument(
        "--report-ledger-drift",
        action="store_true",
        help="List recent live WP slugs missing from shared/published-articles.md",
    )
    ap.add_argument(
        "--live-limit",
        type=int,
        default=40,
        help="How many recent live WP posts to fetch for slug/drift checks (default 40)",
    )
    ap.add_argument(
        "--check-focus",
        type=str,
        default=None,
        help="HARD topic-focus gate: h1 + primary_query + slug (shared/topic-focus-contract.md)",
    )
    args = ap.parse_args()
    
    # Reconfigure stdout for utf-8 on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    
    root = project_root()
    published = load_published_topics(root)
    active = load_active_article_topics(root)
    reserved = published | active
    existing = load_existing_topics(root)
    published_topics = load_published_as_topics(root)
    meta_primaries = load_article_meta_primaries(root)
    live_limit = max(1, min(int(args.live_limit or 40), 100))
    live_topics = fetch_recent_wp_topics(limit=live_limit)
    # Prefer article.meta.json primaries over slug-derived ledger rows.
    comparable = existing + meta_primaries + published_topics + live_topics
    
    if args.check_focus is not None:
        print("=== EXCALIBUR TOPIC FOCUS ===")
        verdict = focus_check(args.check_focus)
        print(f"status={verdict['status']}")
        print(f"reason={verdict['reason']}")
        if verdict.get("deny_hit"):
            print(f"deny_hit={verdict['deny_hit']}")
        if verdict.get("allow_hit"):
            print(f"allow_hit={verdict['allow_hit']}")
        if verdict["status"] != "PASS":
            print(
                "BLOCKER: TOPIC FOCUS BLOCKER — do NOT append topic card. "
                "See shared/topic-focus-contract.md (Cursor/subagents/leadgen/"
                "autopost only; no PageSpeed/Metrika/Webmaster/Direct/indexing)."
            )
            return 1
        print("✅ TOPIC FOCUS PASS")
        return 0

    if args.suggest_next:
        print("=== EXCALIBUR SCOUT HELPER ===")
        max_num = 0
        for source in (existing, [{"topic_id": x} for x in reserved]):
            for t in source:
                m = re.match(r"B(\d+)", str(t.get("topic_id") or ""), flags=re.I)
                if m:
                    max_num = max(max_num, int(m.group(1)))
        # Also scan article dirs / ledger rows for highest B-number.
        for tid in reserved:
            m = re.match(r"B(\d+)", tid, flags=re.I)
            if m:
                max_num = max(max_num, int(m.group(1)))

        next_id = f"B{max_num + 1:02d}" if max_num else "B01"
        print(f"Next available topic ID: {next_id}")
        print("Topic pool: none (memory/topics/ deleted — Scout title goes to handoff only)")
        print(f"Total articles written/in_progress: {len(reserved)}")
        print(f"Active article dirs: {sorted(active)}")
        print(
            "Director next: python3 scripts/excalibur_blog_research_start.py "
            f'--topic-id {next_id} --title "<short title>"'
        )
        
        unwritten = [t["topic_id"] for t in existing if t["topic_id"] not in reserved]
        print(f"Unwritten topic IDs in pool: {unwritten}")
        on_focus = []
        for t in existing:
            if t["topic_id"] in reserved:
                continue
            blob = " ".join(
                [
                    str(t.get("topic_id") or ""),
                    str(t.get("h1") or ""),
                    str(t.get("primary_query") or ""),
                    str(t.get("slug") or ""),
                ]
            )
            if focus_check(blob)["status"] == "PASS":
                on_focus.append(t["topic_id"])
        print(f"Unwritten on-focus topic IDs: {on_focus}")
        drift = report_ledger_drift(root, live_topics)
        if drift:
            print(f"⚠️ LEDGER DRIFT: {len(drift)} live WP slug(s) missing from published-articles.md")
            for item in drift[:5]:
                print(f"  - /{item['slug']}/ ({item['topic_id']}) — do not reuse; sync ledger")
        else:
            print("✅ LEDGER DRIFT: none in recent live WP window")
        return 0

    if args.report_ledger_drift:
        print("=== EXCALIBUR SCOUT LEDGER DRIFT ===")
        if not live_topics:
            print("⚠️ No live WP posts fetched (PUBLIC_SITE_URL/WP_SITE_URL missing or API error).")
            return 2
        drift = report_ledger_drift(root, live_topics)
        if not drift:
            print("✅ No ledger drift in recent live WP window.")
            return 0
        print(f"❌ {len(drift)} live slug(s) missing from shared/published-articles.md:")
        for item in drift:
            print(f"  - slug: {item['slug']} ({item['topic_id']})")
            print(f"    suggested: {item['suggested_ledger_row']}")
        print("Rule: live slug collision = topic taken even if ledger empty. Sync ledger before next scout.")
        return 1
        
    if args.check_query:
        focus = focus_check(args.check_query)
        if focus["status"] != "PASS":
            print("❌ TOPIC FOCUS BLOCKER:")
            print(f"  reason: {focus['reason']}")
            if focus.get("deny_hit"):
                print(f"  deny_hit: {focus['deny_hit']}")
            print(
                "BLOCKER: off-focus query — do NOT append topic card. "
                "Core only: Cursor/subagents/rules/skills/MCP/leadgen/autopost/Make. "
                "Banned: PageSpeed, Metrika/GA4/Webvisor/UTM, Webmaster/GSC, Direct, indexing."
            )
            return 1
        warnings = check_overlap(args.check_query, comparable, reserved)
        if warnings:
            print("❌ OVERLAP DETECTED:")
            for w in warnings:
                print(f"  [{w['severity']}] Similarity: {w['similarity']} | Topic: {w['topic_id']} ({w['status']})")
                print(f"  Message: {w['message']}")
            critical = [w for w in warnings if w.get("severity") == "CRITICAL"]
            if critical:
                slug_cover = any("SLUG KEYWORD COVER" in str(w.get("message") or "") for w in critical)
                if slug_cover:
                    print(
                        "BLOCKER: Query keywords covered by ledger/live WP slug "
                        "(Cyrillic↔Latin) — do NOT append topic card. "
                        "Channel/topic already published; pick another angle."
                    )
                else:
                    print(
                        "BLOCKER: EXACT primary_query match — do NOT append topic card. "
                        "Choose a distinct primary (angle/economics cluster ≠ sibling topic)."
                    )
            return 1
        print("✅ NO CANNIBALIZATION RISK: Query is clean and unique.")
        print("✅ TOPIC FOCUS PASS")
        return 0

    if args.check_slug:
        warnings = check_slug(args.check_slug, comparable)
        if warnings:
            print("❌ SLUG ALREADY EXISTS:")
            for w in warnings:
                print(f"  [{w['severity']}] Topic: {w['topic_id']} ({w['status']})")
                print(f"  Message: {w['message']}")
            return 1
        print("✅ NO SLUG COLLISION: Slug is clean and unique.")
        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
