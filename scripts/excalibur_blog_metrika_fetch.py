#!/usr/bin/env python3
"""Fetch and analyse Yandex Metrica Reports API stats for published articles.

Requires Cloud Secrets / env:
  YANDEX_METRIKA_OAUTH_TOKEN  (metrika:read)
  YANDEX_METRIKA_COUNTER_ID

Docs: https://yandex.ru/dev/metrika/
Reports: GET https://api-metrika.yandex.net/stat/v1/data
Management preflight: GET /management/v1/counter/{id}

On Reports HTTP 400 query_error or Management code_status=CS_ERR_UNKNOWN,
prints JSON METRIKA FEEDBACK BLOCKER with do_not_retry=true (exit 2).
Do not shrink --days/accuracy; restore the counter in Yandex UI.
Content-learner still must call --days 30 --ingest once per run.

Output (default): memory/site-feedback-metrika.json  {rows:[raw metrics...]}
Then ingest:
  python3 scripts/excalibur_blog_site_feedback_ingest.py --input memory/analytics/metrika-latest.json --actionable-only
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.excalibur_blog_site_base import (  # noqa: E402
    REDACTED_LITERAL,
    SITE_BASE_PLACEHOLDER,
    SITE_HOST_PLACEHOLDER,
    find_live_site_host_hits,
    redact_site_base,
    redact_structure,
)


API_BASE = "https://api-metrika.yandex.net/stat/v1/data"
MANAGEMENT_COUNTER_URL = "https://api-metrika.yandex.net/management/v1/counter/{counter_id}"
# Never persist live YANDEX_METRIKA_COUNTER_ID into git-bound artifacts.
COUNTER_ID_REDACTED = REDACTED_LITERAL
_PATH_PREFIXES = (
    SITE_BASE_PLACEHOLDER,
    SITE_HOST_PLACEHOLDER,
    REDACTED_LITERAL,
)
UNVERIFIED_CODE_STATUSES = frozenset(
    {
        "CS_ERR_UNKNOWN",
        "CS_ERR_HTML_CODE",
    }
)
QUERY_ERROR_MARKERS = (
    "query_error",
    "query is too complicated",
    "reduce the date interval",
)


class MetrikaHttpError(Exception):
    """HTTP error from Metrika Management or Reports API (body already truncated)."""

    def __init__(self, http_code: int, body: str) -> None:
        self.http_code = http_code
        self.body = body or ""
        super().__init__(f"HTTP {http_code}")


class MetrikaNetworkError(Exception):
    """Transport error talking to Metrika (no HTTP status)."""


def redact_metrika_secrets(text: str, *, token: str = "", counter_id: str = "") -> str:
    """Strip OAuth token and counter id from any log/blocker string."""
    out = text or ""
    if token:
        out = out.replace(token, REDACTED_LITERAL)
        compact = token.strip()
        if compact and compact != token:
            out = out.replace(compact, REDACTED_LITERAL)
    if counter_id:
        out = out.replace(str(counter_id), COUNTER_ID_REDACTED)
    return out


def parse_api_error_body(body: str) -> dict[str, Any]:
    """Best-effort parse of Metrika JSON error; never assumes a single schema."""
    error_type = ""
    message = ""
    messages: list[str] = []
    try:
        data = json.loads(body) if body else None
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        message = str(data.get("message") or "")
        items = data.get("errors")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                et = str(item.get("error_type") or item.get("error-type") or "")
                msg = str(item.get("message") or "")
                if et and not error_type:
                    error_type = et
                if msg:
                    messages.append(msg)
                    if not message:
                        message = msg
        if not error_type:
            error_type = str(data.get("error_type") or data.get("error") or "")
    elif body:
        message = body.strip()[:400]
    blob = f"{error_type} {message} {body}".lower()
    if not error_type and "query_error" in blob:
        error_type = "query_error"
    if not error_type and any(marker in blob for marker in QUERY_ERROR_MARKERS[1:]):
        error_type = "query_error"
    return {"error_type": error_type, "message": message, "messages": messages}


def is_query_error(error_type: str, message: str, body: str = "") -> bool:
    blob = f"{error_type} {message} {body}".lower()
    if (error_type or "").lower() == "query_error":
        return True
    return any(marker in blob for marker in QUERY_ERROR_MARKERS)


def is_unverified_code_status(code_status: str | None) -> bool:
    return (code_status or "").strip().upper() in UNVERIFIED_CODE_STATUSES


def build_metrika_blocker(
    *,
    http_code: int | None,
    body: str,
    token: str,
    counter_id: str,
    code_status: str | None = None,
    counter_status: str | None = None,
    permission: str | None = None,
    source: str = "reports",
) -> dict[str, Any]:
    """Structured BLOCKER for Content-learner. No token/counter id in the payload."""
    parsed = parse_api_error_body(body)
    safe_message = redact_metrika_secrets(
        parsed["message"], token=token, counter_id=counter_id
    )[:300]
    query_err = is_query_error(parsed["error_type"], parsed["message"], body)
    unverified = is_unverified_code_status(code_status)
    auth_fail = http_code in {401, 403}
    transient = http_code == 429 or (http_code is not None and http_code >= 500)

    if auth_fail:
        blocker = "METRIKA CREDENTIALS BLOCKER"
        reason = "http_auth"
        do_not_retry = True
    elif query_err:
        blocker = "METRIKA FEEDBACK BLOCKER"
        reason = "query_error"
        do_not_retry = True
    elif unverified:
        blocker = "METRIKA FEEDBACK BLOCKER"
        reason = "counter_code_unverified"
        do_not_retry = True
    elif http_code is None:
        blocker = "METRIKA FEEDBACK BLOCKER"
        reason = "network"
        do_not_retry = False
    else:
        blocker = "METRIKA FEEDBACK BLOCKER"
        reason = f"http_{http_code}"
        do_not_retry = not transient

    errors: list[str] = []
    if auth_fail:
        errors.append(
            f"Metrika {source} HTTP {http_code} — token/permission, not a query shape issue."
        )
    if query_err:
        errors.append(
            "Reports API query_error — not 401/403; shrinking --days/accuracy will not help "
            "when even ym:s:visits / today fails."
        )
        if safe_message:
            errors.append(safe_message)
    if unverified:
        errors.append(
            f"Management code_status={code_status} (counter code not verified by Yandex)."
        )
    if not errors:
        if http_code is not None:
            errors.append(f"Metrika {source} HTTP {http_code}")
        if safe_message:
            errors.append(safe_message)
        if not errors:
            errors.append("Metrika API failed")

    needed_human: list[str] = []
    if auth_fail:
        needed_human.append(
            "Replace YANDEX_METRIKA_OAUTH_TOKEN with a token that has metrika:read "
            "for this counter (Management would otherwise be HTTP 200)."
        )
    if query_err or unverified:
        needed_human.extend(
            [
                "Verify the Metrika JS snippet is installed and reachable on the live site "
                "(code_status must leave CS_ERR_UNKNOWN).",
                "In Metrika UI: GDPR/agreement, counter Active, then Yandex support if "
                "Reports API still returns query_error on a 1-metric today query.",
            ]
        )

    do_not: list[str] = []
    if do_not_retry and (query_err or unverified):
        do_not = [
            "Do not retry with smaller --days, date1=today, accuracy=low|medium, "
            "limit, preset, or bytime",
            "Do not invent Metrika rows; next run must still call --days 30 --ingest once",
        ]

    return {
        "status": "BLOCKER",
        "blocker": blocker,
        "reason": reason,
        "http_status": http_code,
        "code_status": code_status or None,
        "counter_status": counter_status or None,
        "permission": permission,
        "source": source,
        "do_not_retry": do_not_retry,
        "errors": errors,
        "needed_human": needed_human,
        "do_not": do_not,
    }


def print_blocker(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2


def print_metrika_exception_blocker(
    exc: MetrikaHttpError | MetrikaNetworkError,
    *,
    token: str,
    counter_id: str,
    source: str,
    code_status: str | None = None,
    counter_status: str | None = None,
    permission: str | None = None,
) -> int:
    if isinstance(exc, MetrikaNetworkError):
        payload = build_metrika_blocker(
            http_code=None,
            body=str(exc),
            token=token,
            counter_id=counter_id,
            code_status=code_status,
            counter_status=counter_status,
            permission=permission,
            source=source,
        )
        return print_blocker(payload)
    payload = build_metrika_blocker(
        http_code=exc.http_code,
        body=exc.body,
        token=token,
        counter_id=counter_id,
        code_status=code_status,
        counter_status=counter_status,
        permission=permission,
        source=source,
    )
    return print_blocker(payload)


def _load_env_file(root: Path) -> None:
    for name in ("memory/site.env.local", ".env"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def parse_ledger(root: Path) -> dict[str, dict[str, str]]:
    """slug -> published article metadata from shared/published-articles.md."""
    path = root / "shared" / "published-articles.md"
    out: dict[str, dict[str, str]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower() == "date" or set(cells[0]) <= {"-", ":"}:
            continue
        published_date, topic_id, slug, status = cells[0], cells[1], cells[2], cells[4]
        if not slug or slug.lower() == "slug":
            continue
        slug_norm = slug.strip("/").lower()
        out[slug_norm] = {
            "published_date": published_date,
            "topic_id": topic_id,
            "slug": slug_norm,
            "status": status,
        }
    return out


def normalize_path(value: str) -> str:
    """Return path-only landing path (/slug), never scheme+host or placeholders.

    Handles Metrika quirks and git-safe masks:
    - https://host/slug → /slug
    - /https://host/slug (malformed startURLPath) → /slug
    - {{SITE_BASE}}/slug, {{SITE_HOST}}/slug, [REDACTED]/slug → /slug
    When PUBLIC_SITE_URL is set, also strips live host via redact_site_base.
    """
    text = (value or "").strip()
    if not text:
        return ""
    # Live host → placeholder first (needs PUBLIC_SITE_URL / WP_SITE_URL in env).
    text = redact_site_base(text)
    # Strip placeholder / tool-mask prefixes (may repeat after redact).
    changed = True
    while changed:
        changed = False
        for prefix in _PATH_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :] or "/"
                changed = True
                break
            # Malformed "/{{SITE_BASE}}/slug" after leading slash.
            if text.startswith("/" + prefix):
                text = text[1 + len(prefix) :] or "/"
                changed = True
                break
    # Absolute URL or malformed "/https://host/..." → path only.
    stripped = text.lstrip("/")
    lower_stripped = stripped.lower()
    if lower_stripped.startswith("http://") or lower_stripped.startswith("https://"):
        try:
            text = urllib.parse.urlparse(stripped).path or "/"
        except Exception:
            slash = stripped.find("/", stripped.find("://") + 3)
            text = stripped[slash:] if slash >= 0 else "/"
    elif "://" in text:
        try:
            text = urllib.parse.urlparse(text).path or "/"
        except Exception:
            pass
    text = text.split("?", 1)[0].split("#", 1)[0]
    text = text.strip()
    if not text.startswith("/"):
        text = "/" + text
    if len(text) > 1 and text.endswith("/"):
        text = text[:-1]
    # Drop accidental host-shaped first segment left after failed parse.
    # e.g. /example.com/slug when scheme was missing — only if PUBLIC host matches.
    live_hits = find_live_site_host_hits(text)
    if live_hits:
        text = redact_site_base(text)
        for prefix in _PATH_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :] or "/"
            elif text.startswith("/" + prefix):
                text = text[1 + len(prefix) :] or "/"
        if not text.startswith("/"):
            text = "/" + text
        if len(text) > 1 and text.endswith("/"):
            text = text[:-1]
    return text.lower()


def path_to_slug(path: str) -> str:
    path = normalize_path(path)
    if not path or path == "/":
        return ""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return ""
    # prefer last segment (post slug)
    return parts[-1]


def http_get_json(url: str, token: str, *, timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"OAuth {token}",
            "Accept": "application/json",
            "User-Agent": "excalibur-blog-metrika-fetch/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:2000]
        raise MetrikaHttpError(exc.code, body) from None
    except urllib.error.URLError as exc:
        raise MetrikaNetworkError(str(exc.reason) if getattr(exc, "reason", None) else str(exc)) from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("METRIKA API: response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SystemExit("METRIKA API: response is not a JSON object")
    return data


def api_get(token: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{API_BASE}?{query}"
    return http_get_json(url, token)


def fetch_counter_preflight(token: str, counter_id: str) -> dict[str, Any]:
    """Management API: counter health without persisting id/login/code."""
    url = MANAGEMENT_COUNTER_URL.format(
        counter_id=urllib.parse.quote(str(counter_id), safe="")
    )
    data = http_get_json(url, token)
    counter = data.get("counter") if isinstance(data.get("counter"), dict) else {}
    return {
        "http_status": 200,
        "code_status": str(counter.get("code_status") or ""),
        "status": str(counter.get("status") or ""),
        "permission": str(counter.get("permission") or ""),
        "activity_status": str(counter.get("activity_status") or ""),
        "type": str(counter.get("type") or ""),
        "pro": counter.get("pro"),
    }


def fetch_article_metrics(
    token: str, counter_id: str, date1: str, date2: str, limit: int
) -> list[dict[str, Any]]:
    """Return session metrics by landing URL path, not a pageviews/users proxy."""
    data = api_get(
        token,
        {
            "ids": counter_id,
            "metrics": (
                "ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,"
                "ym:s:avgVisitDurationSeconds,ym:s:pageDepth"
            ),
            # Session metrics require a session dimension. startURLPath is the
            # landing page for the visit, so each row remains attributable to
            # an article without mixing hit/session prefixes.
            "dimensions": "ym:s:startURLPath",
            "date1": date1,
            "date2": date2,
            "limit": limit,
            "accuracy": "full",
        },
    )
    rows: list[dict[str, Any]] = []
    for item in data.get("data") or []:
        dims = item.get("dimensions") or []
        metrics = item.get("metrics") or []
        name = ""
        if dims and isinstance(dims[0], dict):
            name = str(dims[0].get("name") or dims[0].get("id") or "")
        visits = float(metrics[0]) if len(metrics) > 0 else 0.0
        users = float(metrics[1]) if len(metrics) > 1 else 0.0
        pageviews = float(metrics[2]) if len(metrics) > 2 else 0.0
        bounce_rate = float(metrics[3]) if len(metrics) > 3 else None
        avg_visit_duration_seconds = float(metrics[4]) if len(metrics) > 4 else None
        page_depth = float(metrics[5]) if len(metrics) > 5 else None
        rows.append(
            {
                "url_path": normalize_path(name),
                "visits": visits,
                "pageviews": pageviews,
                "users": users,
                "bounce_rate": bounce_rate,
                "avg_visit_duration_seconds": avg_visit_duration_seconds,
                "page_depth": page_depth,
            }
        )
    return rows


def load_messenger_goal_id(root: Path) -> int | None:
    """Return the explicitly configured messenger-click goal, if available."""
    path = root / "memory" / "conversion-goals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = (data.get("goals") or {}).get("messenger_click", {}).get("goal_id")
        return int(value) if value is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def fetch_goal_metrics(
    token: str, counter_id: str, goal_id: int, date1: str, date2: str, limit: int
) -> dict[str, dict[str, float]]:
    """Return goal visits and conversion rate by session landing path."""
    data = api_get(
        token,
        {
            "ids": counter_id,
            "metrics": f"ym:s:goal{goal_id}visits,ym:s:goal{goal_id}conversionRate",
            "dimensions": "ym:s:startURLPath",
            "date1": date1,
            "date2": date2,
            "limit": limit,
            "accuracy": "full",
        },
    )
    result: dict[str, dict[str, float]] = {}
    for item in data.get("data") or []:
        dims = item.get("dimensions") or []
        metrics = item.get("metrics") or []
        path = normalize_path(str((dims[0] if dims else {}).get("name") or ""))
        if path:
            result[path] = {
                "messenger_goal_visits": float(metrics[0]) if metrics else 0.0,
                "messenger_conversion_rate": float(metrics[1]) if len(metrics) > 1 else 0.0,
            }
    return result


def _published_age_days(published_date: str, today: date) -> int | None:
    try:
        return max(0, (today - date.fromisoformat(published_date)).days)
    except ValueError:
        return None


def _cohort(age_days: int | None, maturity_days: int) -> str:
    if age_days is None:
        return "unknown"
    if age_days < maturity_days:
        return "fresh"
    if age_days < 28:
        return "recent"
    return "established"


def _median(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return round(float(statistics.median(values)), 2) if values else None


def analyse_rows(
    rows: list[dict[str, Any]], *, today: date, maturity_days: int, min_users: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify article-level signals against age cohorts; never invent retention."""
    eligible = [
        row
        for row in rows
        if (row.get("article_age_days") or 0) >= maturity_days
        and float(row.get("users") or 0) >= min_users
    ]
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in eligible:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)

    benchmark_keys = (
        "visits",
        "bounce_rate",
        "avg_visit_duration_seconds",
        "page_depth",
        "messenger_conversion_rate",
    )
    enriched: list[dict[str, Any]] = []
    actionable_count = 0

    for row in rows:
        item = dict(row)
        age_days = item.get("article_age_days")
        users = float(item.get("users") or 0)
        cohort_rows = by_cohort.get(str(item.get("cohort"))) or []
        reference_rows = cohort_rows if len(cohort_rows) >= 3 else eligible
        benchmarks = {key: _median(reference_rows, key) for key in benchmark_keys}

        analysis: dict[str, Any] = {
            "status": "insufficient_data",
            "confidence": "low",
            "signal": "insufficient_data",
            "priority": "none",
            # Prose coaching is content-learner owned — never invent here.
            "recommended_action": None,
            "do_not_do": [],
            "cohort_size": len(reference_rows),
            "benchmarks": benchmarks,
        }
        if age_days is not None and int(age_days) < maturity_days:
            analysis["reason"] = f"article_age_days<{maturity_days}"
        elif users < min_users:
            analysis["reason"] = f"users<{min_users}"
        elif len(reference_rows) < 3 or any(
            benchmarks[key] is None for key in benchmark_keys[:-1]
        ):
            analysis["reason"] = "cohort_has_fewer_than_3_eligible_articles"
        else:
            visits = float(item.get("visits") or 0)
            bounce = float(item.get("bounce_rate") or 0)
            duration = float(item.get("avg_visit_duration_seconds") or 0)
            depth = float(item.get("page_depth") or 0)
            b_visits = float(benchmarks["visits"] or 0)
            b_bounce = float(benchmarks["bounce_rate"] or 0)
            b_duration = float(benchmarks["avg_visit_duration_seconds"] or 0)
            b_depth = float(benchmarks["page_depth"] or 0)
            b_messenger = benchmarks["messenger_conversion_rate"]
            messenger_rate = item.get("messenger_conversion_rate")
            confidence = "high" if users >= 100 and len(reference_rows) >= 5 else "medium"
            analysis.update({"status": "observed", "confidence": confidence})

            if visits >= b_visits and (bounce >= max(55.0, b_bounce + 12.0) or duration <= b_duration * 0.65):
                analysis.update(
                    {
                        "signal": "promise_body_mismatch",
                        "priority": "high",
                    }
                )
            elif visits < b_visits * 0.6 and bounce <= b_bounce and duration >= b_duration:
                analysis.update(
                    {
                        "signal": "discovery_opportunity",
                        "priority": "medium",
                    }
                )
            elif bounce <= b_bounce and duration >= b_duration and depth <= b_depth * 0.8:
                if isinstance(messenger_rate, (int, float)) and isinstance(b_messenger, (int, float)) and b_messenger > 0 and messenger_rate < b_messenger * 0.6:
                    analysis.update(
                        {
                            "signal": "messenger_cta_opportunity",
                            "priority": "medium",
                        }
                    )
                else:
                    analysis.update(
                        {
                            "signal": "next_step_opportunity",
                            "priority": "medium",
                        }
                    )
            elif visits >= b_visits * 1.3 and bounce <= b_bounce and duration >= b_duration:
                analysis.update(
                    {
                        "signal": "strong_engagement_pattern",
                        "priority": "low",
                    }
                )
            else:
                analysis.update(
                    {
                        "signal": "watch",
                        "priority": "none",
                    }
                )

        item["analytics"] = analysis
        item["actionable"] = bool(
            analysis["status"] == "observed" and analysis["priority"] in {"high", "medium", "low"}
        )
        if item["actionable"]:
            actionable_count += 1
        enriched.append(item)

    return enriched, {
        "eligible_articles": len(eligible),
        "actionable_articles": actionable_count,
        "maturity_days": maturity_days,
        "min_users": min_users,
        "cohorts": {key: len(value) for key, value in by_cohort.items()},
        "generated_for": today.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--days", type=int, default=30, help="Lookback days")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument(
        "--published-only",
        action="store_true",
        default=True,
        help="Keep only paths matching published-articles.md slugs (default)",
    )
    parser.add_argument(
        "--all-paths",
        action="store_true",
        help="Do not filter by published ledger",
    )
    parser.add_argument(
        "--min-pageviews",
        type=float,
        default=1.0,
        help="Drop rows below this pageviews threshold",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="memory/site-feedback-metrika.json",
    )
    parser.add_argument(
        "--csv-out",
        default="memory/site-feedback-metrika.csv",
    )
    parser.add_argument(
        "--analytics-out",
        default="memory/analytics/metrika-latest.json",
        help="Cohort analysis output relative to root",
    )
    parser.add_argument(
        "--maturity-days",
        type=int,
        default=7,
        help="Do not judge articles newer than this number of days",
    )
    parser.add_argument(
        "--analytics-min-users",
        type=int,
        default=30,
        help="Minimum users before an article can receive a recommendation",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Also run site_feedback_ingest.py on the output JSON",
    )
    parser.add_argument(
        "--dry-run-ledger",
        action="store_true",
        help="Only parse published-articles.md and print slug count (no API)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    _load_env_file(root)
    ledger = parse_ledger(root)

    if args.dry_run_ledger:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "ledger_slugs": len(ledger),
                    "sample": list(ledger.keys())[:10],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    token = (os.environ.get("YANDEX_METRIKA_OAUTH_TOKEN") or "").strip()
    counter = (os.environ.get("YANDEX_METRIKA_COUNTER_ID") or "").strip()
    if not token or not counter:
        print(
            json.dumps(
                {
                    "status": "BLOCKER",
                    "blocker": "METRIKA CREDENTIALS BLOCKER",
                    "reason": "missing_env",
                    "do_not_retry": True,
                    "errors": [
                        "Set YANDEX_METRIKA_OAUTH_TOKEN and YANDEX_METRIKA_COUNTER_ID in Cloud Secrets/env",
                        "Docs: https://yandex.ru/dev/metrika/ — OAuth metrika:read + counter id",
                    ],
                    "do_not": [
                        "Do not invent Metrika rows; next run must still call --days 30 --ingest once",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    date2 = date.today()
    date1 = date2 - timedelta(days=max(1, args.days))

    preflight: dict[str, Any] = {}
    try:
        preflight = fetch_counter_preflight(token, counter)
    except (MetrikaHttpError, MetrikaNetworkError) as exc:
        return print_metrika_exception_blocker(
            exc, token=token, counter_id=counter, source="management"
        )

    code_status = str(preflight.get("code_status") or "")
    counter_status = str(preflight.get("status") or "")
    permission = str(preflight.get("permission") or "")

    try:
        raw_rows = fetch_article_metrics(
            token,
            counter,
            date1.isoformat(),
            date2.isoformat(),
            max(1, args.limit),
        )
    except (MetrikaHttpError, MetrikaNetworkError) as exc:
        return print_metrika_exception_blocker(
            exc,
            token=token,
            counter_id=counter,
            source="reports",
            code_status=code_status,
            counter_status=counter_status,
            permission=permission,
        )
    messenger_goal_id = load_messenger_goal_id(root)
    try:
        messenger_metrics = (
            fetch_goal_metrics(
                token,
                counter,
                messenger_goal_id,
                date1.isoformat(),
                date2.isoformat(),
                max(1, args.limit),
            )
            if messenger_goal_id
            else {}
        )
    except (MetrikaHttpError, MetrikaNetworkError) as exc:
        return print_metrika_exception_blocker(
            exc,
            token=token,
            counter_id=counter,
            source="reports_goals",
            code_status=code_status,
            counter_status=counter_status,
            permission=permission,
        )

    filter_ledger = not args.all_paths
    out_rows: list[dict[str, Any]] = []
    unmatched = 0
    for item in raw_rows:
        path = item["url_path"]
        slug = path_to_slug(path)
        pageviews = float(item["pageviews"])
        users = float(item["users"])
        if pageviews < args.min_pageviews:
            continue
        meta = ledger.get(slug)
        if filter_ledger and (not meta or str(meta.get("status") or "").lower() != "published"):
            unmatched += 1
            continue
        topic_id = (meta or {}).get("topic_id") or "n/a"
        published_date = str((meta or {}).get("published_date") or "")
        article_age_days = _published_age_days(published_date, date2)
        messenger = messenger_metrics.get(path, {})
        out_rows.append(
            {
                "topic_id": topic_id,
                "slug": slug or path,
                "url_path": path,
                "published_date": published_date,
                "article_age_days": article_age_days,
                "cohort": _cohort(article_age_days, max(1, args.maturity_days)),
                "visits": float(item["visits"]),
                "pageviews": pageviews,
                "users": users,
                "bounce_rate": item["bounce_rate"],
                "avg_visit_duration_seconds": item["avg_visit_duration_seconds"],
                "page_depth": item["page_depth"],
                "messenger_goal_id": messenger_goal_id,
                "messenger_goal_visits": messenger.get("messenger_goal_visits"),
                "messenger_conversion_rate": messenger.get("messenger_conversion_rate"),
                "ctr": "",
                "source": "yandex_metrika",
                "period_days": args.days,
                "date1": date1.isoformat(),
                "date2": date2.isoformat(),
            }
        )

    payload = {
        "schema_version": 1,
        "source": "yandex_metrika_reports_api",
        "fetched_at": date2.isoformat(),
        "date1": date1.isoformat(),
        "date2": date2.isoformat(),
        "raw_paths": len(raw_rows),
        "matched_rows": len(out_rows),
        "unmatched_paths_skipped": unmatched if filter_ledger else 0,
        "messenger_goal_id": messenger_goal_id,
        "rows": out_rows,
    }
    # Scrub leftover live host in string fields; set counter_id after redact
    # because redact_site_base maps [REDACTED] → {{SITE_BASE}}.
    payload = redact_structure(payload)
    payload["counter_id"] = COUNTER_ID_REDACTED

    out_json = root / args.output
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_csv = root / args.csv_out
    headers = [
        "topic_id",
        "slug",
        "url_path",
        "visits",
        "pageviews",
        "users",
        "bounce_rate",
        "avg_visit_duration_seconds",
        "page_depth",
        "messenger_goal_visits",
        "messenger_conversion_rate",
        "ctr",
    ]
    lines = [",".join(headers)]
    for row in out_rows:
        cells = []
        for h in headers:
            val = str(row.get(h, "")).replace('"', "'")
            if h == "url_path":
                val = normalize_path(val)
            val = redact_site_base(val)
            if "," in val or ";" in val:
                val = f'"{val}"'
            cells.append(val)
        lines.append(",".join(cells))
    out_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    analysed_rows, analytics_summary = analyse_rows(
        out_rows,
        today=date2,
        maturity_days=max(1, args.maturity_days),
        min_users=max(1, args.analytics_min_users),
    )
    analytics_payload = {
        "schema_version": 1,
        "source": "yandex_metrika_reports_api",
        "generated_at": date2.isoformat(),
        "date1": date1.isoformat(),
        "date2": date2.isoformat(),
        "messenger_goal_id": messenger_goal_id,
        "analysis": analytics_summary,
        "rows": analysed_rows,
        "limitations": [
            "Metrika page/session behavior is not SERP CTR; use Webmaster/GSC for CTR.",
            "CTA conversion needs a configured goal; next_step_opportunity is a hypothesis.",
            "Fresh or low-sample articles are not actionable.",
        ],
    }
    analytics_payload = redact_structure(analytics_payload)
    analytics_out = root / args.analytics_out
    analytics_out.parent.mkdir(parents=True, exist_ok=True)
    analytics_out.write_text(
        json.dumps(analytics_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = {
        "status": "PASS" if out_rows else "PASS_EMPTY",
        "json": str(out_json.relative_to(root)).replace("\\", "/"),
        "csv": str(out_csv.relative_to(root)).replace("\\", "/"),
        "analytics": str(analytics_out.relative_to(root)).replace("\\", "/"),
        "matched_rows": len(out_rows),
        "actionable_rows": analytics_summary["actionable_articles"],
        "messenger_goal_id": messenger_goal_id,
        "raw_paths": len(raw_rows),
        "unmatched_paths_skipped": unmatched if filter_ledger else 0,
        "date1": date1.isoformat(),
        "date2": date2.isoformat(),
        "code_status": code_status or None,
        "counter_status": counter_status or None,
        "do_not_retry": False,
        "note": (
            "Metrika gives on-site behavior; use Webmaster/GSC for SERP CTR"
            if out_rows
            else (
                "API OK but 0 ledger-matched rows — not a credentials blocker; "
                "do not invent lessons; check path matching / freshness"
            )
        ),
    }
    if is_unverified_code_status(code_status):
        result["note"] = (
            f"{result['note']}; WARN code_status={code_status} "
            "(snippet not verified — data may be incomplete, not a Reports query_error)"
        )
        print(
            f"WARN Metrika code_status={code_status}: tracking code not verified",
            file=sys.stderr,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.ingest:
        if not out_rows:
            print(
                "WARN metrika ingest skipped: matched_rows=0 (PASS_EMPTY)",
                file=sys.stderr,
            )
            return 0
        ingest = root / "scripts" / "excalibur_blog_site_feedback_ingest.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(ingest),
                "--input",
                str(analytics_out),
                "--root",
                str(root),
                "--dedupe-existing",
                "--actionable-only",
            ],
            check=False,
        )
        if proc.returncode != 0:
            return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
