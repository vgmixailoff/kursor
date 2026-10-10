#!/usr/bin/env python3
"""Verify hyperlinks in Excalibur article.html (HTTP HEAD/GET)."""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from excalibur_blog_site_base import (
    SITE_BASE_PLACEHOLDER,
    expand_site_base,
    normalize_public_base,
    redact_site_base,
    redact_structure,
    resolve_public_base_from_env,
)


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr = {k: (v or "") for k, v in attrs}
        href = attr.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            return
        self.links.append({"href": href, "text_hint": ""})


def extract_links(html: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    seen: set[str] = set()
    out: list[str] = []
    for item in parser.links:
        href = item["href"]
        if href not in seen:
            seen.add(href)
            out.append(href)
    return out


def check_url(url: str, timeout: float, user_agent: str) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": user_agent},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return {
                "url": url,
                "status": resp.status,
                "ok": 200 <= resp.status < 400,
                "method": "HEAD",
                "error": None,
            }
    except urllib.error.HTTPError as e:
        # Some CDNs (TikTok CG, etc.) answer HEAD 404 while GET 200.
        # Also retry when HEAD is disallowed / blocked (405/501/403/418).
        # VK kittenx (dev.vk.com) returns 418 on HEAD while GET 200 (B110).
        if e.code in (404, 405, 501, 403, 418):
            return _get_fallback(url, timeout, user_agent, ctx, str(e))
        return {
            "url": url,
            "status": e.code,
            "ok": False,
            "method": "HEAD",
            "error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        return _get_fallback(url, timeout, user_agent, ctx, str(e))


def _get_fallback(
    url: str, timeout: float, user_agent: str, ctx: ssl.SSLContext, head_error: str
) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return {
                "url": url,
                "status": resp.status,
                "ok": 200 <= resp.status < 400,
                "method": "GET",
                "error": None if resp.status < 400 else head_error,
            }
    except urllib.error.HTTPError as e:
        return {
            "url": url,
            "status": e.code,
            "ok": False,
            "method": "GET",
            "error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "url": url,
            "status": None,
            "ok": False,
            "method": "GET",
            "error": str(e),
        }


def classify_link(href: str, site_base: str | None) -> str:
    if href.startswith("/"):
        return "internal_relative"
    parsed = urlparse(href)
    if not parsed.scheme:
        return "internal_relative"
    if site_base:
        base = urlparse(site_base if "://" in site_base else f"https://{site_base}")
        if parsed.netloc == base.netloc:
            return "internal_absolute"
    return "external"


# Social hosts that often flake under Cloud DNS/egress. Resolver errors and
# timeouts are warnings, not FAIL (INC-20260713-2014).
# Do NOT add product CDNs here (e.g. www.make.com, www.npmjs.com,
# openai.com/index, securityweek.com): HTTP 403 with a status code is a hard
# FAIL — Writer must use apps.make.com / help.make.com (INC-20260715-0821),
# registry.npmjs.org / GitHub (INC-20260807-0828), Wayback/press for
# openai.com/index (INC-20260809-1619), or vendor/Infosecurity (not
# securityweek.com) for press (INC-20260810-2028). Soft path only covers
# errors without HTTP status, plus VK Video auth redirect-loops
# (INC-20260806-1628).
SOFT_EXTERNAL_HOSTS = frozenset(
    {
        "t.me",
        "telegram.me",
        "wa.me",
        "vk.com",
        "vkvideo.ru",
        "www.vkvideo.ru",
        "max.ru",
        "www.max.ru",
    }
)
SOFT_EXTERNAL_ERROR_TOKENS = (
    "timed out",
    "timeout",
    "ssl",
    "network",
    "name or service not known",
    "errno -2",
    "errno -3",
    "getaddrinfo",
    "gaierror",
    "nodename nor servname",
    "temporary failure in name resolution",
    "unreachable",
    "failed to resolve",
)
# urllib follows VK Video → login.vk.ru autologin and reports a synthetic
# HTTP 302 "infinite loop" — not a real dead link (B142 / INC-20260806-1628).
SOFT_EXTERNAL_REDIRECT_LOOP_TOKENS = (
    "infinite loop",
    "redirect error that would lead to an infinite loop",
)

# Product hosts that occasionally reset TLS mid-check under Cloud egress.
# Retry 1–2× on connection-reset *without* HTTP status; never soft-pass 403
# (INC-20260718-0818). Do not add these to SOFT_EXTERNAL_HOSTS.
CONNECTION_RESET_RETRY_HOSTS = frozenset({"kv-ai.ru", "www.kv-ai.ru"})
CONNECTION_RESET_ERROR_TOKENS = (
    "connection reset by peer",
    "errno 104",
    "econnreset",
    "connection reset",
)
CONNECTION_RESET_MAX_RETRIES = 2
CONNECTION_RESET_RETRY_SLEEP_S = 1.5

# Akamai (GlobeNewswire and similar) tarpits unknown and browser User-Agents
# from Cloud egress while HTTP 200 is served to curl. One retry, not a soft-pass.
CURL_COMPAT_USER_AGENT = "curl/8.5.0"
TARPIT_TIMEOUT_TOKENS = ("timed out", "timeout")

# Early hard FAIL for known-bad Make hrefs (before live HTTP).
# INC-20260715-0821 (www.make.com 403) + INC-20260715-1700 (help.make.com/http 404).
# Prefer apps.make.com/http and apps.make.com/telegram; live help.make.com pages OK.
KNOWN_BAD_MAKE_HELP_PATHS = frozenset({"/http"})

# Early hard FAIL for Cursor product UI paths that return bot/CDN/auth 403.
# INC-20260724-1230: cursor.com/automations and /automations/new → 403 under link_verify.
# INC-20260725-0827: cursor.com/dashboard/* (e.g. /dashboard/spending) → 403 under link_verify.
# Prefer plain-text UI path in prose + docs/help 200 links
# (e.g. docs cloud-agent/automations; help models-and-usage/usage-limits).
# Do NOT soft-pass or add cursor.com to SOFT_EXTERNAL_HOSTS.


def known_bad_make_href_reason(href: str) -> str | None:
    """Return a clear fail reason for banned Make article hrefs, else None."""
    parsed = urlparse(href.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    path = (parsed.path or "").rstrip("/") or ""
    if host == "www.make.com":
        # Covers homepage, /en/*, legacy /en/help/tools/http, etc.
        return (
            "banned Make host www.make.com/* (bot/CDN 403); "
            "use https://apps.make.com/telegram or https://apps.make.com/http "
            "(or a live help.make.com page with HTTP 200 — not /http)"
        )
    if host == "help.make.com" and path in KNOWN_BAD_MAKE_HELP_PATHS:
        return (
            "dead Make help path help.make.com/http (404 coming soon); "
            "use https://apps.make.com/http "
            "(+ https://help.make.com/connect-to-any-web-service-using-oauth-20 if OAuth)"
        )
    return None


def _cursor_com_host_and_path(href: str) -> tuple[str, str] | None:
    """Return (host_without_www, path) for http(s) cursor.com hrefs, else None."""
    parsed = urlparse(href.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    if host != "cursor.com":
        return None
    path = (parsed.path or "").rstrip("/") or ""
    return host, path


def known_bad_cursor_automations_href_reason(href: str) -> str | None:
    """Return fail reason for cursor.com/automations* product UI hrefs, else None."""
    parsed_host_path = _cursor_com_host_and_path(href)
    if parsed_host_path is None:
        return None
    _host, path = parsed_host_path
    # Only product UI /automations* — not docs/.../automations or blog/help paths.
    if path == "/automations" or path.startswith("/automations/"):
        return (
            "banned cursor.com/automations* href (bot/CDN 403); "
            "use plain text «cursor.com/automations» (no <a href>) + "
            "https://cursor.com/docs/cloud-agent/automations "
            "(or another docs/help/blog Automations URL with HTTP 200)"
        )
    return None


def known_bad_cursor_dashboard_href_reason(href: str) -> str | None:
    """Return fail reason for cursor.com/dashboard/* auth UI hrefs, else None."""
    parsed_host_path = _cursor_com_host_and_path(href)
    if parsed_host_path is None:
        return None
    _host, path = parsed_host_path
    # Authenticated dashboard UI (Spending, Usage, billing, settings, …).
    # Docs/help/pricing live outside /dashboard and remain allowed.
    if path == "/dashboard" or path.startswith("/dashboard/"):
        return (
            "banned cursor.com/dashboard/* href (bot/CDN/auth 403); "
            "use plain text «cursor.com/dashboard/spending» (no <a href>) + "
            "https://cursor.com/help/models-and-usage/usage-limits "
            "(or another docs/help URL with HTTP 200)"
        )
    return None


# Early hard FAIL for npmjs marketing/CDN package pages (bot 403 under Cloud).
# INC-20260807-0828: www.npmjs.com/package/@aws/n8n-nodes-agentcore → 403.
# Prefer registry.npmjs.org/<pkg> (HTTP 200) or the package GitHub repo.
# Do NOT soft-pass or add npmjs.com to SOFT_EXTERNAL_HOSTS.
# registry.npmjs.org and docs.npmjs.com remain allowed.


def known_bad_npmjs_href_reason(href: str) -> str | None:
    """Return fail reason for npmjs.com / www.npmjs.com article hrefs, else None."""
    parsed = urlparse(href.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    if host != "npmjs.com":
        return None
    # Marketing site /package/* (and other www paths) bot/CDN 403 under egress.
    # registry.npmjs.org is a different host and is the writer-safe substitute.
    return (
        "banned npmjs.com/* href (bot/CDN 403); "
        "use https://registry.npmjs.org/<pkg> "
        "(e.g. https://registry.npmjs.org/@scope/name) "
        "or the package GitHub repo URL with HTTP 200"
    )


# Early hard FAIL for openai.com blog index pages (Cloudflare/bot 403 under Cloud).
# INC-20260809-1619 (B153) + B152/B119: openai.com/index/... → CF 403.
# Prefer web.archive.org snapshot of the same post, same-day press, or GitHub
# artifact as the clickable primary. Keep canonical URL in research notes only.
# Do NOT soft-pass or blanket-ban *.openai.com — deploymentsafety / platform /
# cdn subdomains remain allowed when they return HTTP 200.


def known_bad_openai_index_href_reason(href: str) -> str | None:
    """Return fail reason for apex openai.com/index/* blog hrefs, else None."""
    parsed = urlparse(href.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    # Apex blog only — not deploymentsafety.openai.com / platform / cdn / etc.
    if host != "openai.com":
        return None
    path = (parsed.path or "").rstrip("/") or ""
    if path == "/index" or path.startswith("/index/"):
        return (
            "banned openai.com/index/* href (Cloudflare/bot 403 under Cloud egress); "
            "use a web.archive.org snapshot of the same post, same-day press URL, "
            "or GitHub artifact with HTTP 200; keep canonical openai.com URL in "
            "research notes only (not as sole article <a href>)"
        )
    return None


# Early hard FAIL for securityweek.com press (bot/CDN 403 under Cloud egress).
# INC-20260810-2028 (B157): www.securityweek.com/... → HTTP 403.
# Prefer Infosecurity Magazine / primary vendor blog / GitHub as clickable
# primary. Keep SecurityWeek URL in research notes only.
# Do NOT soft-pass 403. Do NOT rely on web.archive.org as sole primary:
# archive.org often returns HTTP 429 under the same Cloud egress.


def known_bad_securityweek_href_reason(href: str) -> str | None:
    """Return fail reason for securityweek.com article hrefs, else None."""
    parsed = urlparse(href.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    if host != "securityweek.com":
        return None
    return (
        "banned securityweek.com/* href (bot/CDN 403 under Cloud egress); "
        "use Infosecurity Magazine / primary vendor blog / GitHub with HTTP 200 "
        "as clickable primary; keep SecurityWeek URL in research notes only "
        "(do not rely on web.archive.org — often HTTP 429 under Cloud egress)"
    )


def known_bad_external_href_reason(href: str) -> str | None:
    """Aggregate early denylist reasons for known-bad external article hrefs."""
    return (
        known_bad_make_href_reason(href)
        or known_bad_cursor_automations_href_reason(href)
        or known_bad_cursor_dashboard_href_reason(href)
        or known_bad_npmjs_href_reason(href)
        or known_bad_openai_index_href_reason(href)
        or known_bad_securityweek_href_reason(href)
    )


def _href_host(href: str) -> str:
    parsed = urlparse(href)
    return (parsed.netloc or "").lower().split(":", 1)[0]


def is_soft_external_failure(href: str, result: dict[str, Any]) -> bool:
    """Treat flaky social DNS/timeouts as warnings, not publish blockers."""
    host = _href_host(href)
    if host.startswith("www."):
        host = host[4:]
    if host not in SOFT_EXTERNAL_HOSTS:
        return False
    error = str(result.get("error") or "").lower()
    # VK Video playlist/channel URLs often bounce through login.vk.ru autologin
    # under Cloud egress; urllib then raises a synthetic 302 infinite-loop.
    if any(token in error for token in SOFT_EXTERNAL_REDIRECT_LOOP_TOKENS):
        return True
    if result.get("status") is not None:
        return False
    # DNS/egress flakes on social hosts must not block publish (Cloud often cannot
    # resolve t.me). Match timeouts, TLS, generic network, and resolver failures.
    return any(token in error for token in SOFT_EXTERNAL_ERROR_TOKENS)


def is_connection_reset_retryable(href: str, result: dict[str, Any]) -> bool:
    """True when allowlisted product host failed with connection-reset, no HTTP status."""
    host = _href_host(href)
    if host not in CONNECTION_RESET_RETRY_HOSTS:
        return False
    if result.get("status") is not None:
        return False
    if result.get("ok"):
        return False
    error = str(result.get("error") or "").lower()
    return any(token in error for token in CONNECTION_RESET_ERROR_TOKENS)


def is_tarpit_timeout(result: dict[str, Any]) -> bool:
    """True when the check died on read timeout and never got an HTTP status."""
    if result.get("ok") or result.get("status") is not None:
        return False
    error = str(result.get("error") or "").lower()
    return any(token in error for token in TARPIT_TIMEOUT_TOKENS)


def check_url_with_connection_reset_retry(
    url: str, timeout: float, user_agent: str
) -> dict[str, Any]:
    """HTTP check; soft-retry connection-reset on allowlisted hosts (INC-20260718-0818)."""
    result = check_url(url, timeout, user_agent)
    retries = 0
    while is_connection_reset_retryable(url, result) and retries < CONNECTION_RESET_MAX_RETRIES:
        retries += 1
        time.sleep(CONNECTION_RESET_RETRY_SLEEP_S)
        result = check_url(url, timeout, user_agent)
        result["connection_reset_retries"] = retries
    if retries and not result.get("connection_reset_retries"):
        result["connection_reset_retries"] = retries
    if is_tarpit_timeout(result) and user_agent != CURL_COMPAT_USER_AGENT:
        retry = check_url(url, min(timeout, 20.0), CURL_COMPAT_USER_AGENT)
        retry["curl_ua_retry"] = True
        if retry.get("ok") or retry.get("status") is not None:
            return retry
    return result


def resolve_runtime_site_base(site_base: str | None) -> str | None:
    """Resolve live base for HTTP checks; expand {{SITE_BASE}} from env if needed."""
    raw = normalize_public_base(site_base)
    if not raw:
        raw = resolve_public_base_from_env()
    if not raw:
        return None
    if SITE_BASE_PLACEHOLDER in raw or raw == SITE_BASE_PLACEHOLDER:
        live = resolve_public_base_from_env()
        if not live:
            raise ValueError(
                f"--site-base {SITE_BASE_PLACEHOLDER} requires PUBLIC_SITE_URL/WP_SITE_URL in env"
            )
        return live
    return raw


def git_safe_link_report(report: dict[str, Any], public_base: str | None) -> dict[str, Any]:
    """Rewrite report for commit: internal urls use {{SITE_BASE}}/path, not live host."""
    safe = redact_structure(report, public_base)
    links = safe.get("links")
    if not isinstance(links, list):
        return safe
    for item in links:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        url = str(item.get("url") or "")
        checked = item.get("checked_url")
        if kind in ("internal_relative", "internal_absolute"):
            # Prefer path-style display under {{SITE_BASE}} for secret-scan-safe commits.
            if url.startswith("/"):
                item["url"] = f"{SITE_BASE_PLACEHOLDER}{url}"
            elif url.startswith(SITE_BASE_PLACEHOLDER):
                item["url"] = url
            elif "://" in url:
                path = urlparse(url).path or "/"
                item["url"] = f"{SITE_BASE_PLACEHOLDER}{path}"
            if checked:
                item["checked_url"] = redact_site_base(str(checked), public_base)
        elif checked:
            item["checked_url"] = redact_site_base(str(checked), public_base)
    return safe


def verify_article(
    html_path: Path,
    *,
    site_base: str | None = None,
    timeout: float = 15.0,
    skip_external: bool = False,
) -> dict[str, Any]:
    html = html_path.read_text(encoding="utf-8")
    links = extract_links(html)
    user_agent = "ExcaliburBlogLinkVerify/1.0"
    runtime_base = resolve_runtime_site_base(site_base)
    results: list[dict[str, Any]] = []
    for href in links:
        kind = classify_link(href, runtime_base)
        bad_href = known_bad_external_href_reason(href)
        if kind == "external" and bad_href:
            results.append(
                {
                    "url": href,
                    "kind": kind,
                    "status": None,
                    "ok": False,
                    "skipped": False,
                    "method": "denylist",
                    "error": bad_href,
                }
            )
            continue
        if skip_external and kind == "external":
            results.append(
                {
                    "url": href,
                    "kind": kind,
                    "status": None,
                    "ok": True,
                    "skipped": True,
                    "method": None,
                    "error": None,
                }
            )
            continue
        check_target = href
        # Expand {{SITE_BASE}}/slug BEFORE any base-join. Joining first produced
        # https://host/{{SITE_BASE}}/slug → https://host/https://host/slug (false 404).
        if SITE_BASE_PLACEHOLDER in check_target:
            if not runtime_base:
                results.append(
                    {
                        "url": href,
                        "kind": kind,
                        "status": None,
                        "ok": False,
                        "skipped": False,
                        "method": None,
                        "error": f"{SITE_BASE_PLACEHOLDER} in href requires PUBLIC_SITE_URL",
                    }
                )
                continue
            check_target = expand_site_base(check_target, runtime_base)
        elif kind == "internal_relative" and runtime_base:
            base = runtime_base.rstrip("/")
            check_target = f"{base}{href if href.startswith('/') else '/' + href}"
        elif kind == "internal_relative":
            results.append(
                {
                    "url": href,
                    "kind": kind,
                    "status": None,
                    "ok": True,
                    "skipped": True,
                    "method": None,
                    "error": "relative link; pass --site-base or set PUBLIC_SITE_URL to verify",
                }
            )
            continue
        r = check_url_with_connection_reset_retry(check_target, timeout, user_agent)
        r["kind"] = kind
        r["skipped"] = False
        # Keep original href in url; live target only in checked_url (redacted on write).
        r["url"] = href
        if kind in ("internal_relative", "internal_absolute") or check_target != href:
            r["checked_url"] = check_target
        if kind == "external" and is_soft_external_failure(href, r):
            r["ok"] = True
            err_l = str(r.get("error") or "").lower()
            if any(token in err_l for token in SOFT_EXTERNAL_REDIRECT_LOOP_TOKENS):
                r["warning"] = (
                    "soft external social auth redirect-loop "
                    "(e.g. vkvideo.ru → login.vk.ru); verify manually if needed"
                )
            else:
                r["warning"] = (
                    "soft external social DNS/network flake; verify manually if needed"
                )
        results.append(r)

    failed = [r for r in results if not r.get("ok")]
    return {
        "source": str(html_path).replace("\\", "/"),
        "total_links": len(results),
        "failed_count": len(failed),
        "verdict": "pass" if not failed else "fail",
        "links": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify links in Excalibur article.html")
    ap.add_argument("html", type=Path, help="Path to article.html")
    ap.add_argument("-o", "--output", type=Path, help="Write link-verify.json")
    ap.add_argument(
        "--site-base",
        type=str,
        default=None,
        help="Live base for HTTP checks (PUBLIC_SITE_URL). Output file always redacts to {{SITE_BASE}}.",
    )
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--skip-external", action="store_true")
    args = ap.parse_args()

    if not args.html.is_file():
        print(f"Not found: {args.html}", file=sys.stderr)
        return 2

    try:
        report = verify_article(
            args.html,
            site_base=args.site_base,
            timeout=args.timeout,
            skip_external=args.skip_external,
        )
    except ValueError as exc:
        print(f"BLOCKER: {exc}", file=sys.stderr)
        return 2

    runtime_base = None
    try:
        runtime_base = resolve_runtime_site_base(args.site_base)
    except ValueError:
        runtime_base = resolve_public_base_from_env() or None

    # stdout may show live checked_url for the agent; -o is always git-safe.
    text_live = json.dumps(report, ensure_ascii=False, indent=2)
    print(text_live)
    if args.output:
        safe_report = git_safe_link_report(report, runtime_base)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
