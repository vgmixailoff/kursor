#!/usr/bin/env python3
"""Excalibur BLOG — step 0: date context + fresh web search for a topic."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from excalibur_blog_article_meta_index import load_ledger_topic_slugs
from excalibur_blog_published_titles import write_titles
from excalibur_blog_scout_helper import transliterate_ru
from excalibur_blog_site_base import redact_structure
from excalibur_blog_topic_focus import assert_topic_focus

USER_AGENT = "ExcaliburBlogResearch/1.0 (+research-start)"
DDG_HTML = "https://html.duckduckgo.com/html/"
DEFAULT_TZ = "Europe/Moscow"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def now_context(tz_name: str) -> dict[str, Any]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
        tz_name = "UTC"
    now = datetime.now(tz)
    month_names = {
        1: "январь",
        2: "февраль",
        3: "март",
        4: "апрель",
        5: "май",
        6: "июнь",
        7: "июль",
        8: "август",
        9: "сентябрь",
        10: "октябрь",
        11: "ноябрь",
        12: "декабрь",
    }
    weekday_names = [
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    ]
    return {
        "timezone": tz_name,
        "today_iso": now.date().isoformat(),
        "today_ru": now.strftime("%d.%m.%Y"),
        "year": now.year,
        "month": now.month,
        "month_name_ru": month_names.get(now.month, str(now.month)),
        "weekday_ru": weekday_names[now.weekday()],
    }


def slugify_title(title: str) -> str:
    lat = transliterate_ru(title or "")
    lat = re.sub(r"[^a-z0-9]+", "-", lat.lower())
    return re.sub(r"-+", "-", lat).strip("-")[:80]


def parse_topic_card(
    topic_id: str,
    *,
    title_override: str = "",
) -> dict[str, Any]:
    """Resolve topic title without memory/topics/.

    Prefer --title. Else published-titles.md / article.meta / ledger slug.
    """
    root = project_root()
    tid = topic_id.upper()
    title = (title_override or "").strip().rstrip(".:")

    if not title:
        titles_path = root / "shared" / "published-titles.md"
        if titles_path.is_file():
            for line in titles_path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 3 and cells[0].upper() == tid:
                    title = cells[2].strip()
                    break

    if not title:
        blog = root / "memory" / "blog" / "articles"
        if blog.is_dir():
            for path in sorted(blog.iterdir()):
                if path.is_dir() and path.name.upper().startswith(f"{tid}-"):
                    meta = path / "article.meta.json"
                    if meta.is_file():
                        try:
                            data = json.loads(meta.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            data = {}
                        title = str(
                            (data.get("title") if isinstance(data, dict) else "")
                            or (data.get("h1") if isinstance(data, dict) else "")
                            or ""
                        ).strip()
                    if not title:
                        title = path.name.split("-", 1)[-1].replace("-", " ")
                    break

    if not title:
        raise ValueError(
            f"topic_id {tid!r}: pass --title \"short title\" "
            "(memory/topics/ deleted; Scout puts title in handoff only)"
        )

    for token in (
        "без копипаста за вечер",
        "без копипаста",
        "за один вечер",
        "за вечер",
    ):
        if ":" in title:
            left, right = title.split(":", 1)
            if token in right.lower() and len(left.strip()) >= 8:
                title = left.strip()
                break

    ledger_slug = (load_ledger_topic_slugs(root).get(tid) or "").strip().strip("/")
    slug = ledger_slug or slugify_title(title) or tid.lower()

    return {
        "topic_id": tid,
        "title": title,
        "h1": title,
        "slug": slug,
        "primary_query": title,
        "priority": "P0",
    }


def build_search_queries(topic: dict[str, Any], ctx: dict[str, Any]) -> list[dict[str, str]]:
    year = str(ctx["year"])
    primary = topic.get("primary_query") or topic.get("title") or topic.get("h1") or topic["topic_id"]
    title = topic.get("title") or topic.get("h1") or primary
    queries: list[dict[str, str]] = [
        {"id": "primary_fresh", "query": f"{primary} {year}", "purpose": "актуальный SERP"},
        {"id": "title_fresh", "query": f"{title} {year}", "purpose": "SERP по человеческому title"},
        {"id": "official_docs", "query": f"{primary} official docs {year}", "purpose": "официальные docs"},
        {"id": "github_evidence", "query": f"site:github.com {primary} {year}", "purpose": "GitHub evidence"},
        {"id": "community_experience", "query": f"{primary} forum problems опыт {year}", "purpose": "форумы и живые проблемы"},
    ]
    return queries


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_result_link = False
        self._in_snippet = False
        self._current_href = ""
        self._current_title = ""
        self._current_snippet = ""
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = attr.get("class") or ""
        if tag == "a" and "result__a" in classes:
            self._in_result_link = True
            self._current_href = attr.get("href") or ""
            self._capture_title = True
            self._current_title = ""
        elif tag == "a" and "result__snippet" in classes:
            self._in_snippet = True
            self._capture_snippet = True
            self._current_snippet = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            self._in_result_link = False
            self._capture_title = False
            if self._current_href and self._current_title:
                self.results.append(
                    {
                        "title": self._current_title.strip(),
                        "url": self._unwrap_ddg_url(self._current_href),
                        "snippet": self._current_snippet.strip(),
                    }
                )
            self._current_href = ""
            self._current_title = ""
            self._current_snippet = ""
        elif tag == "a" and self._in_snippet:
            self._in_snippet = False
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title += data
        if self._capture_snippet:
            self._current_snippet += data

    @staticmethod
    def _unwrap_ddg_url(href: str) -> str:
        if href.startswith("//"):
            href = "https:" + href
        if "uddg=" in href:
            parsed = urllib.parse.urlparse(href)
            query = urllib.parse.parse_qs(parsed.query)
            if "uddg" in query:
                return urllib.parse.unquote(query["uddg"][0])
        return href


def search_web(query: str, *, max_results: int = 8, retries: int = 2) -> list[dict[str, str]]:
    body = urllib.parse.urlencode({"q": query, "kl": "ru-ru"}).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(DDG_HTML, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=20) as response:
                html = response.read().decode("utf-8", errors="replace")
            parser = DuckDuckGoResultParser()
            parser.feed(html)
            deduped: list[dict[str, str]] = []
            seen: set[str] = set()
            for item in parser.results:
                url = item.get("url") or ""
                if not url.startswith("http") or url in seen:
                    continue
                seen.add(url)
                deduped.append(item)
                if len(deduped) >= max_results:
                    break
            return deduped
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(min(1.0, 0.3 * attempt))
    raise RuntimeError(f"search failed for {query!r}: {last_error}")


def article_dir(root: Path, topic: dict[str, Any]) -> Path:
    slug = topic.get("slug") or topic["topic_id"].lower()
    return root / "memory" / "blog" / "articles" / f"{topic['topic_id']}-{slug}"


def run_research_start(
    *,
    topic_id: str,
    title: str,
    output_dir: Path | None,
    tz_name: str,
    max_results: int,
    dry_run: bool,
) -> dict[str, Any]:
    ctx = now_context(tz_name)
    topic = parse_topic_card(topic_id, title_override=title)
    root = project_root()
    assert_topic_focus(topic)
    queries = build_search_queries(topic, ctx)
    out_dir = output_dir or article_dir(root, topic)
    out_dir.mkdir(parents=True, exist_ok=True)

    serp_runs: list[dict[str, Any]] = []
    errors: list[str] = []
    if not dry_run:
        for item in queries:
            try:
                results = search_web(item["query"], max_results=max_results)
                serp_runs.append(
                    {
                        "query_id": item["id"],
                        "query": item["query"],
                        "purpose": item["purpose"],
                        "result_count": len(results),
                        "results": results,
                        "searched_at": ctx["today_iso"],
                    }
                )
                time.sleep(0.5)
            except RuntimeError as exc:
                errors.append(str(exc))
                serp_runs.append(
                    {
                        "query_id": item["id"],
                        "query": item["query"],
                        "purpose": item["purpose"],
                        "result_count": 0,
                        "results": [],
                        "error": str(exc),
                        "searched_at": ctx["today_iso"],
                    }
                )

    titles_info: dict[str, Any] | None = None
    if not dry_run:
        titles_info = write_titles(root, article_dir=out_dir)

    payload_context = {
        "agent": "excalibur-blog",
        "step": "research_start",
        "date_context": ctx,
        "topic": topic,
        "search_queries": queries,
        "next_step": "Research reads research-serp.json, does its own thinking and writes research-notes.md",
        "writer_allowed_sources": [
            "shared/writer-master-prompt.md",
            "shared/gemini-article-contract.md",
            "skills/dzen-article-writing/SKILL.md",
            "research-notes.md",
            "published-titles-only.md",
        ],
        "sol_disabled": True,
        "writer_titles_only": "published-titles-only.md",
        "forbidden_sources_for_writer": [
            "memory/blog/articles/*/article.html",
            "memory/blog/articles/*/drafts",
            "memory/topics/ (deleted — do not recreate)",
            "memory/content-lessons.md",
            "shared/golden-benchmark",
            "QA reports",
            "neighbor research-notes as prose exemplars",
            "old article bodies",
        ],
        "published_titles_count": (titles_info or {}).get("count", 0),
    }
    payload_serp = redact_structure(
        {
            "agent": "excalibur-blog",
            "date_context": ctx,
            "topic": topic,
            "searches": serp_runs,
            "errors": errors,
        }
    )

    context_path = out_dir / "research-context.json"
    serp_path = out_dir / "research-serp.json"
    if not dry_run:
        context_path.write_text(json.dumps(payload_context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        serp_path.write_text(json.dumps(payload_serp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "context_path": str(context_path),
        "serp_path": str(serp_path),
        "context": payload_context,
        "serp": payload_serp,
        "titles": titles_info,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic-id", required=True)
    parser.add_argument(
        "--title",
        default="",
        help="Short topic title from Scout handoff (required for new topics)",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timezone", default=DEFAULT_TZ)
    parser.add_argument("--max-results", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run_research_start(
        topic_id=args.topic_id.upper(),
        title=args.title,
        output_dir=args.output_dir,
        tz_name=args.timezone,
        max_results=args.max_results,
        dry_run=args.dry_run,
    )
    ctx = result["context"]["date_context"]
    print(f"OK date={ctx['today_ru']} year={ctx['year']} tz={ctx['timezone']}")
    print(f"topic={result['context']['topic']['topic_id']} slug={result['context']['topic'].get('slug')}")
    print(f"queries={len(result['context']['search_queries'])}")
    titles = result.get("titles") or {}
    if titles:
        print(f"published_titles={titles.get('count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
