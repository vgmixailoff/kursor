#!/usr/bin/env python3
"""Git-safe site base helpers for Excalibur BLOG artifacts.

Committed article artifacts must use {{SITE_BASE}}, never a live PUBLIC_SITE_URL
host and never the tool-display mask [REDACTED]. Publish/Cover runtime expands
the placeholder with PUBLIC_SITE_URL when calling live APIs.
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse


SITE_BASE_PLACEHOLDER = "{{SITE_BASE}}"
SITE_HOST_PLACEHOLDER = "{{SITE_HOST}}"
REDACTED_LITERAL = "[REDACTED]"


def host_from_public_base(public_base: str | None = None) -> str:
    """Hostname from PUBLIC_SITE_URL / given base (no scheme). Empty if unknown."""
    base = normalize_public_base(public_base or resolve_public_base_from_env())
    if not base:
        return ""
    return (urlparse(base).hostname or "").strip()


def normalize_public_base(base: str | None) -> str:
    return (base or "").strip().rstrip("/")


def resolve_public_base_from_env() -> str:
    return normalize_public_base(
        os.environ.get("PUBLIC_SITE_URL")
        or os.environ.get("WP_HOME")
        or os.environ.get("WP_SITE_URL")
    )


def expand_site_base(text: str, public_base: str) -> str:
    """Expand git-safe {{SITE_BASE}} with live PUBLIC_SITE_URL at runtime."""
    if not text or SITE_BASE_PLACEHOLDER not in text:
        return text
    base = normalize_public_base(public_base)
    if not base:
        raise ValueError(
            f"{SITE_BASE_PLACEHOLDER} present but PUBLIC_SITE_URL/--public-base/--site-base is empty"
        )
    if REDACTED_LITERAL in base:
        raise ValueError("public base must not be the tool-mask literal [REDACTED]")
    return text.replace(SITE_BASE_PLACEHOLDER, base)


def _candidate_bases(public_base: str | None) -> list[str]:
    bases: list[str] = []
    for raw in (public_base, resolve_public_base_from_env()):
        base = normalize_public_base(raw)
        if base and base not in bases:
            bases.append(base)
        if base.startswith("https://"):
            alt = "http://" + base[len("https://") :]
            if alt not in bases:
                bases.append(alt)
        elif base.startswith("http://"):
            alt = "https://" + base[len("http://") :]
            if alt not in bases:
                bases.append(alt)
    return bases


def redact_site_base(text: str, public_base: str | None = None) -> str:
    """Replace live site base, bare hostname, and [REDACTED] masks for git artifacts.

    Full URL bases become {{SITE_BASE}}; remaining bare hostname (e.g. in prose)
    becomes {{SITE_HOST}}. Order matters: replace full bases before bare host.
    """
    if not text:
        return text
    out = text
    # Tool-display / legacy mask used as a fake host prefix.
    if REDACTED_LITERAL in out:
        out = out.replace(f"{REDACTED_LITERAL}/", f"{SITE_BASE_PLACEHOLDER}/")
        out = out.replace(REDACTED_LITERAL, SITE_BASE_PLACEHOLDER)
    for base in _candidate_bases(public_base):
        if base and base in out:
            out = out.replace(base, SITE_BASE_PLACEHOLDER)
    host = host_from_public_base(public_base)
    if host and host in out:
        # Word-ish boundaries so we do not rewrite substrings inside other domains.
        out = re.sub(
            rf"(?<![A-Za-z0-9.-]){re.escape(host)}(?![A-Za-z0-9.-])",
            SITE_HOST_PLACEHOLDER,
            out,
        )
    return out


def redact_structure(value: Any, public_base: str | None = None) -> Any:
    """Recursively redact site base inside JSON-compatible structures."""
    if isinstance(value, str):
        return redact_site_base(value, public_base)
    if isinstance(value, list):
        return [redact_structure(item, public_base) for item in value]
    if isinstance(value, dict):
        return {key: redact_structure(item, public_base) for key, item in value.items()}
    return value


def find_live_site_host_hits(text: str, public_base: str | None = None) -> list[str]:
    """Return live site host/base literals still present in text (secret-scan risk).

    Detects full URL base and bare hostname from PUBLIC_SITE_URL / WP_SITE_URL.
    Placeholders {{SITE_BASE}} / {{SITE_HOST}} and path-only ``/slug/`` are fine.
    Does not detect the tool-display mask — use ``find_redacted_mask_hits`` /
    ``find_secret_scan_hits`` for that (INC-20260718-2040).
    """
    if not text:
        return []
    hits: list[str] = []
    for base in _candidate_bases(public_base):
        if base and base in text and base not in hits:
            hits.append(base)
    host = host_from_public_base(public_base)
    if host and re.search(
        rf"(?<![A-Za-z0-9.-]){re.escape(host)}(?![A-Za-z0-9.-])",
        text,
    ):
        if host not in hits:
            hits.append(host)
    return hits


def find_redacted_mask_hits(text: str) -> list[str]:
    """Return tool-display mask literals that must not appear in committed artifacts.

    Cursor secret-scan flags the mask even in negative proof text
    («no [REDACTED]» / «нет [REDACTED]»). Prefer Notes phrasing
    ``placeholders only / no live host`` (INC-20260718-2040).
    """
    if text and REDACTED_LITERAL in text:
        return [REDACTED_LITERAL]
    return []


def find_secret_scan_hits(text: str, public_base: str | None = None) -> list[str]:
    """Union of live-host hits and forbidden tool-display mask hits."""
    hits = list(find_live_site_host_hits(text, public_base))
    for hit in find_redacted_mask_hits(text):
        if hit not in hits:
            hits.append(hit)
    return hits


def to_git_safe_site_url(url: str, public_base: str | None = None) -> str:
    """Normalize a site/media URL for committed artifacts."""
    value = (url or "").strip()
    if not value:
        return value
    value = redact_site_base(value, public_base)
    if value == REDACTED_LITERAL or value.startswith(f"{REDACTED_LITERAL}/"):
        value = redact_site_base(value, public_base)
    return value


def is_placeholder_site_url(url: str) -> bool:
    value = (url or "").strip()
    return value.startswith(SITE_BASE_PLACEHOLDER)


def path_from_site_url(url: str) -> str:
    """Return path portion for {{SITE_BASE}}/path or absolute URL."""
    value = (url or "").strip()
    if value.startswith(SITE_BASE_PLACEHOLDER):
        return value[len(SITE_BASE_PLACEHOLDER) :] or "/"
    if "://" in value:
        return urlparse(value).path or "/"
    return value
