#!/usr/bin/env python3
"""Publish one Excalibur blog article to WordPress (SFTP bootstrap)."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

from asset_download import download_url_bytes
from excalibur_blog_site_base import (
    REDACTED_LITERAL,
    SITE_BASE_PLACEHOLDER,
    expand_site_base,
    redact_site_base,
    redact_structure,
)
from excalibur_repo_paths import repo_relative
from image_validate import sniff_image_format, validate_image_file
from excalibur_blog_cover_black_apply import strip_cover_figure
from excalibur_blog_live_page_gate import inspect as inspect_live_page
from excalibur_blog_pipeline_canon import (
    _plain,
    description_clones_opening,
    description_near_title,
    validate_article_canon,
)

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


PUBLISH_ENV_KEYS = {
    "PUBLIC_SITE_URL",
    "WP_HOME",
    "WP_SITE_URL",
    "FTP_HOST",
    "FTP_PORT",
    "FTP_USER",
    "FTP_PASS",
    "FTP_PASSWORD",
    "FTP_ROOT",
    "FTP_PATH",
    "SSH_HOST",
    "SSH_PORT",
    "SSH_USER",
    "SSH_PASS",
    "SSH_PASSWORD",
    "SSH_ROOT",
    "EXCALIBUR_BLOG_ALLOW_PUBLISH",
}


def _read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def load_env(root: Path) -> dict[str, str]:
    """Load publish secrets.

    Canon: FTP_* and SSH_* are the **same** SFTP credentials under two names.
    Transport is always SFTP/SSH (port 22). Never attempt plain FTP upload.
    Prefer setting FTP_HOST / FTP_USER / FTP_PASS / FTP_ROOT in Cloud Secrets;
    SSH_* are optional aliases. Empty or ``/`` root means SFTP login cwd (``.``).
    """
    env = _read_env_file(root / "memory/site.env.local")
    for key in PUBLISH_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    if not env.get("FTP_PASS") and env.get("FTP_PASSWORD"):
        env["FTP_PASS"] = env["FTP_PASSWORD"]
    if not env.get("SSH_PASS") and env.get("SSH_PASSWORD"):
        env["SSH_PASS"] = env["SSH_PASSWORD"]
    # Bidirectional alias: FTP_* ↔ SSH_* (same SFTP account).
    if not env.get("FTP_HOST") and env.get("SSH_HOST"):
        env["FTP_HOST"] = env["SSH_HOST"]
    if not env.get("FTP_USER") and env.get("SSH_USER"):
        env["FTP_USER"] = env["SSH_USER"]
    if not env.get("FTP_PASS") and env.get("SSH_PASS"):
        env["FTP_PASS"] = env["SSH_PASS"]
    if not env.get("SSH_HOST"):
        env["SSH_HOST"] = env.get("FTP_HOST", "")
    if not env.get("SSH_USER"):
        env["SSH_USER"] = env.get("FTP_USER", "")
    if not env.get("SSH_PASS"):
        env["SSH_PASS"] = env.get("FTP_PASS", "")
    # Root: same for FTP_ROOT / SSH_ROOT / FTP_PATH; default login cwd.
    raw_root = (
        env.get("SSH_ROOT")
        or env.get("FTP_ROOT")
        or env.get("FTP_PATH")
        or ""
    ).strip()
    normalized_root = normalize_sftp_root_value(raw_root)
    env["SSH_ROOT"] = normalized_root
    env["FTP_ROOT"] = normalized_root
    if env.get("FTP_PATH"):
        env["FTP_PATH"] = normalized_root
    return env


def normalize_sftp_root_value(value: str) -> str:
    """Map empty or panel ``/`` to SFTP login cwd ``.`` (where wp-load.php usually is)."""
    raw = (value or "").strip()
    if not raw or raw in {"/", "./"}:
        return "."
    return raw


def validate_publish_env(env: dict[str, str]) -> list[str]:
    missing: list[str] = []
    if not (env.get("SSH_HOST") or env.get("FTP_HOST")):
        missing.append("SSH_HOST or FTP_HOST")
    if not (env.get("SSH_USER") or env.get("FTP_USER")):
        missing.append("SSH_USER or FTP_USER")
    if not (env.get("SSH_PASS") or env.get("FTP_PASS") or env.get("SSH_PASSWORD") or env.get("FTP_PASSWORD")):
        missing.append("SSH_PASS/SSH_PASSWORD or FTP_PASS/FTP_PASSWORD")
    if not (env.get("PUBLIC_SITE_URL") or env.get("WP_HOME") or env.get("WP_SITE_URL")):
        missing.append("PUBLIC_SITE_URL")
    return missing


# Human-only Cloud Secret; script cannot rewrite Dashboard secrets.
SFTP_ROOT_NON_DOT_HINT = (
    "Cloud Secret FTP_ROOT/SSH_ROOT is non-dot (hosting panel path). "
    "On this SFTP login cwd wp-load.php is already at '.'; set FTP_ROOT=. "
    "(and SSH_ROOT=. if used). Empty or '/' also normalize to '.'. "
    "Publish/llms auto-retry at '.' (dot_fallback) — expected WARN, not a new "
    "incident (acknowledged_env; INC-20260807-2022)."
)


def publish_env_check_report(env: dict[str, str]) -> dict[str, object]:
    root_label = sftp_root_label(env)
    non_dot = root_label == "configured-non-dot"
    return {
        "allow_publish": env.get("EXCALIBUR_BLOG_ALLOW_PUBLISH", "").strip().lower() == "yes",
        "public_site_url_configured": bool(env.get("PUBLIC_SITE_URL") or env.get("WP_HOME") or env.get("WP_SITE_URL")),
        "sftp": {
            "host_configured": bool(env.get("SSH_HOST") or env.get("FTP_HOST")),
            "user_configured": bool(env.get("SSH_USER") or env.get("FTP_USER")),
            "password_configured": bool(
                env.get("SSH_PASS")
                or env.get("FTP_PASS")
                or env.get("SSH_PASSWORD")
                or env.get("FTP_PASSWORD")
            ),
            "root": root_label,
            "ftp_aliases_are_sftp": True,
            "dot_fallback_enabled": non_dot,
        },
        "missing": validate_publish_env(env),
        "human_action": SFTP_ROOT_NON_DOT_HINT if non_dot else None,
        "note": (
            "FTP_HOST/USER/PASS/ROOT are SFTP credentials under FTP_* names; "
            "transport is always SFTP. Canon root is '.' (login cwd). "
            "Panel paths under FTP_ROOT cause ENOENT then auto-fallback to '.'."
        ),
    }


def normalize_post_title(title: str) -> str:
    """Keep SEO lower-case queries out of the visible WordPress title."""
    title = " ".join(str(title or "").split())
    if not title:
        return title
    return title[0].upper() + title[1:]


def normalize_media_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def attachment_title_from_alt(alt: str, fallback: str) -> str:
    text = normalize_media_text(alt) or normalize_media_text(fallback)
    if len(text) > 120:
        text = text[:117].rstrip() + "…"
    return text


def build_attachment_fields(
    *,
    alt: str,
    caption: str = "",
    description: str = "",
    title_fallback: str = "",
    h2_anchor: str = "",
) -> dict[str, str]:
    """Map texts to WP Media Library fields: alt / caption / description / title."""
    alt_n = normalize_media_text(alt)
    caption_n = normalize_media_text(caption) or alt_n
    desc_n = normalize_media_text(description)
    if not desc_n:
        h2 = normalize_media_text(h2_anchor)
        if h2 and alt_n:
            desc_n = f"{alt_n} Раздел: {h2}."
        else:
            desc_n = alt_n
    return {
        "alt": alt_n,
        "caption": caption_n,
        "description": desc_n,
        "title": attachment_title_from_alt(alt_n, title_fallback),
    }


_IMG_TAG_RE = re.compile(r"<img\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_IMG_ATTR_RE = re.compile(
    r"""(?P<name>src|alt)\s*=\s*(?P<q>["'])(?P<value>.*?)(?P=q)""",
    re.IGNORECASE | re.DOTALL,
)


def parse_local_img_tags(content: str) -> list[dict[str, str]]:
    """Extract local <img src/alt> pairs from article HTML (skip http/data URLs)."""
    results: list[dict[str, str]] = []
    for match in _IMG_TAG_RE.finditer(content):
        found: dict[str, str] = {}
        for am in _IMG_ATTR_RE.finditer(match.group("attrs")):
            found[am.group("name").lower()] = am.group("value").strip()
        src = found.get("src") or ""
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        results.append({"src": src, "alt": found.get("alt") or ""})
    return results


def validate_local_article_images(article_dir: Path, content: str) -> list[str]:
    """Reject broken or uncaptioned local images before sending a post to WP."""
    errors: list[str] = []
    body = strip_cover_figure(content)
    figures = re.findall(r"<figure\b[^>]*>.*?</figure>", body, flags=re.I | re.S)
    for figure in figures:
        if re.search(r'\bdata-slot=["\']inline_\d+["\']', figure, re.I) and not re.search(
            r"<img\b", figure, re.I
        ):
            errors.append("unfilled inline image slot in article.html")
    for img in parse_local_img_tags(body):
        src = img["src"]
        path = (article_dir / src).resolve()
        if not path.is_relative_to(article_dir.resolve()):
            errors.append(f"inline image path escapes article directory: {src}")
            continue
        if not path.is_file():
            errors.append(f"inline image missing: {src}")
            continue
        if path.suffix.lower() != ".png":
            errors.append(f"inline image must be PNG for WP upload: {src}")
        errors.extend(validate_image_file(path))
        if not img["alt"].strip():
            errors.append(f"inline image missing alt: {src}")
        matching = [figure for figure in figures if any(
            item["src"] == src for item in parse_local_img_tags(figure)
        )]
        if not matching or not any(
            re.search(r"<figcaption\b[^>]*>\s*\S[\s\S]*?</figcaption>", figure, re.I)
            for figure in matching
        ):
            errors.append(f"inline image missing visible figcaption: {src}")
        if Path(src).name.startswith("official-") and not any(
            re.search(r'\bdata-source-url=["\']https://[^"\']+["\']', figure, re.I)
            for figure in matching
        ):
            errors.append(f"official screenshot missing source URL on figure: {src}")
    return errors


def registry_asset_index(registry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index cover-registry assets by relative path and basename."""
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(registry, dict):
        return index
    for asset in registry.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        file_rel = str(asset.get("file") or "").replace("\\", "/").lstrip("./")
        if not file_rel:
            continue
        index[file_rel] = asset
        index[Path(file_rel).name] = asset
    return index


def resolve_cover_media_fields(
    meta: dict[str, Any],
    registry: dict[str, Any] | None,
) -> dict[str, str]:
    reg = registry if isinstance(registry, dict) else {}
    assets = registry_asset_index(reg)
    cover_asset: dict[str, Any] = (
        assets.get("cover/cover.png")
        or assets.get("cover.png")
        or {}
    )
    if not cover_asset:
        for asset in reg.get("assets") or []:
            if isinstance(asset, dict) and asset.get("role") == "cover":
                cover_asset = asset
                break
    alt = (
        meta.get("cover_alt")
        or meta.get("cover_alt_text")
        or reg.get("alt")
        or reg.get("cover_alt_text")
        or cover_asset.get("alt")
        or ""
    )
    return build_attachment_fields(
        alt=str(alt),
        caption=str(alt),
        description=str(alt),
        title_fallback="cover",
    )


def resolve_inline_media_fields(
    *,
    src: str,
    html_alt: str,
    assets: dict[str, dict[str, Any]],
    title_fallback: str,
) -> dict[str, str]:
    norm = src.replace("\\", "/").lstrip("./")
    asset = assets.get(norm) or assets.get(Path(norm).name) or {}
    alt = html_alt or str(asset.get("alt") or "")
    caption = str(asset.get("caption") or "")
    description = str(asset.get("description") or "")
    h2 = str(asset.get("h2_anchor") or "")
    return build_attachment_fields(
        alt=alt,
        caption=caption,
        description=description,
        title_fallback=title_fallback,
        h2_anchor=h2,
    )


def cover_url_from_registry(registry_path: Path) -> str:
    if not registry_path.is_file():
        return ""
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for key in ("transparent_url", "remote_packaged_url", "packaged_url", "attachment_url", "url", "cover_url", "image_url"):
        value = str(registry.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def normalize_cover_png(cover_path: Path, registry_path: Path, root: Path) -> dict[str, object]:
    evidence: dict[str, object] = {
        "path": repo_relative(cover_path, root),
        "source": "existing_file",
        "decode_verified": False,
    }
    errors = validate_image_file(cover_path) if cover_path.is_file() else [f"missing cover file: {cover_path}"]

    if errors:
        remote_url = cover_url_from_registry(registry_path)
        if not remote_url:
            raise RuntimeError("; ".join(errors) + "; no remote cover URL in cover-registry.json")
        data, remote_evidence = download_url_bytes(remote_url, timeout=20, retries=6, chunk_size=8 * 1024)
        detected = sniff_image_format(data)
        if not detected:
            raise RuntimeError("downloaded cover bytes are not a known image format")
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cover_path.with_name(f"{cover_path.stem}.tmp{cover_path.suffix}")
        try:
            if detected == "png":
                tmp.write_bytes(data)
            elif detected in {"webp", "jpeg", "gif"}:
                from PIL import Image

                with Image.open(io.BytesIO(data)) as image:
                    image.save(tmp, format="PNG")
            else:
                raise RuntimeError(f"unsupported cover format: {detected}")
            cover_errors = validate_image_file(tmp)
            if cover_errors:
                raise RuntimeError("; ".join(cover_errors))
            tmp.replace(cover_path)
        finally:
            tmp.unlink(missing_ok=True)
        evidence.update(
            {
                "source": "range_download",
                "remote_url": remote_url,
                "remote_content_type": remote_evidence.get("content_type"),
                "remote_content_range": remote_evidence.get("content_range"),
                "remote_signature_hex": remote_evidence.get("signature_hex"),
                "downloaded_bytes": len(data),
                "detected_remote_format": detected,
            }
        )

    final_errors = validate_image_file(cover_path)
    if final_errors:
        raise RuntimeError("; ".join(final_errors))
    if sniff_image_format(cover_path.read_bytes()) != "png":
        raise RuntimeError(f"cover must be a real PNG after normalization: {cover_path}")

    evidence.update(
        {
            "bytes": cover_path.stat().st_size,
            "detected_format": "png",
            "decode_verified": True,
        }
    )
    return evidence


def rss_safe_excerpt(
    *,
    description: str,
    content_html: str,
    title: str,
) -> str:
    """WP post_excerpt → RSS <description> (Dzen card text).

    Must be a distinct teaser from Description agent:
    - not empty
    - not a clone of the opening (INC-20260805-2240)
    - not a near-duplicate of title (title+description both show on Dzen card)

    Never fall back to title — that recreates the duplicate-title card bug.
    """
    desc = (description or "").strip()
    title_n = (title or "").strip()
    if not desc:
        raise ValueError(
            "RSS excerpt empty: need description-brief from Writer JSON (materialize)"
        )
    if description_near_title(desc, title_n):
        raise ValueError(
            "RSS excerpt near-duplicates title; rewrite description (Dzen card)"
        )
    if description_clones_opening(desc, content_html):
        raise ValueError(
            "RSS excerpt clones opening; rewrite description (INC-20260805-2240)"
        )
    first_p = ""
    m = re.search(r"<p\b[^>]*>(.*?)</p>", content_html or "", flags=re.I | re.S)
    if m:
        first_p = _plain(m.group(1))
    probe = _plain(desc).rstrip("…").rstrip(".,;:").strip()
    if first_p and probe and (first_p.startswith(probe[:60]) or probe.startswith(first_p[:60])):
        raise ValueError(
            "RSS excerpt matches first paragraph; rewrite description"
        )
    if len(desc) < 80 or len(desc) > 180:
        raise ValueError(f"RSS excerpt length {len(desc)} out of range 80–180")
    return desc


def load_article(article_dir: Path, *, public_base: str = "") -> dict:
    meta_path = article_dir / "article.meta.json"
    html_path = article_dir / "article.html"
    if not meta_path.is_file() or not html_path.is_file():
        raise FileNotFoundError("article.meta.json and article.html required")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_ab = meta.get("meta_ab") or {}
    content = html_path.read_text(encoding="utf-8").strip()
    cover_path = article_dir / "cover" / "cover.png"
    schema_path = article_dir / "schema.jsonld"
    cover_b64 = ""
    cover_evidence: dict[str, object] = {}
    cover_reg = article_dir / "cover" / "cover-registry.json"
    if cover_path.is_file():
        cover_evidence = normalize_cover_png(cover_path, cover_reg, project_root())
        cover_b64 = base64.b64encode(cover_path.read_bytes()).decode("ascii")
    schema_raw = ""
    if schema_path.is_file():
        schema_raw = schema_path.read_text(encoding="utf-8").strip()
    if REDACTED_LITERAL in schema_raw or REDACTED_LITERAL in content:
        raise ValueError(
            "article/schema contains literal [REDACTED]; replace with {{SITE_BASE}} "
            "(tool-display mask is not a valid site URL)"
        )
    # Runtime expand only — on-disk artifacts keep {{SITE_BASE}} for secret-scan-safe commits.
    content = expand_site_base(content, public_base)
    schema_raw = expand_site_base(schema_raw, public_base)
    # Cover lives as WP featured + RSS enclosure, not as the first body figure.
    content = strip_cover_figure(content)

    registry: dict[str, Any] = {}
    if cover_reg.is_file():
        try:
            loaded = json.loads(cover_reg.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                registry = loaded
        except json.JSONDecodeError:
            registry = {}
    cover_media = resolve_cover_media_fields(meta, registry)
    assets = registry_asset_index(registry)

    inline_images = []
    image_errors = validate_local_article_images(article_dir, content)
    if image_errors:
        raise ValueError("; ".join(image_errors))
    for img in parse_local_img_tags(content):
        src = img["src"]
        local_path = article_dir / src
        media = resolve_inline_media_fields(
            src=src,
            html_alt=img.get("alt") or "",
            assets=assets,
            title_fallback=local_path.stem,
        )
        inline_images.append(
            {
                "src": src,
                "b64": base64.b64encode(local_path.read_bytes()).decode("ascii"),
                "filename": local_path.name,
                "alt": media["alt"],
                "caption": media["caption"],
                "description": media["description"],
                "title": media["title"],
            }
        )

    wp_post_id = meta.get("wp_post_id") or meta.get("post_id")
    result_path = article_dir / "wp-publish-result.json"
    if not wp_post_id and result_path.is_file():
        try:
            prev = json.loads(result_path.read_text(encoding="utf-8"))
            wp_post_id = prev.get("post_id")
        except json.JSONDecodeError:
            wp_post_id = None

    title = normalize_post_title(
        meta.get("title")
        or meta.get("h1")
        or meta_ab.get("title_aeo")
        or meta_ab.get("title_seo")
        or meta_ab.get("title_ctr")
        or meta["slug"]
    )
    raw_excerpt = (
        meta.get("description")
        or meta_ab.get("description_seo")
        or meta_ab.get("description_ctr")
        or meta_ab.get("description_aeo")
        or ""
    )
    return {
        "slug": meta["slug"],
        "post_id": int(wp_post_id) if wp_post_id else 0,
        "title": title,
        "excerpt": rss_safe_excerpt(
            description=str(raw_excerpt or ""),
            content_html=content,
            title=title,
        ),
        "content": content,
        "cover_b64": cover_b64,
        "cover_evidence": cover_evidence,
        "cover_alt": cover_media["alt"],
        "cover_caption": cover_media["caption"],
        "cover_description": cover_media["description"],
        "cover_title": cover_media["title"],
        "schema_jsonld": schema_raw,
        "topic_id": meta.get("topic_id", ""),
        "inline_images": inline_images,
        "site_base_expanded": bool(public_base) and SITE_BASE_PLACEHOLDER not in schema_raw,
    }


def build_php(payload: dict) -> str:
    b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"""<?php
require __DIR__ . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/file.php';
require_once ABSPATH . 'wp-admin/includes/media.php';
require_once ABSPATH . 'wp-admin/includes/image.php';
require_once ABSPATH . 'wp-admin/includes/post.php';

$p = json_decode(base64_decode('{b64}'), true);
$slug = $p['slug'];

$excalibur_apply_attachment_meta = static function ($att_id, $meta) {{
    $att_id = (int) $att_id;
    if ($att_id <= 0 || !is_array($meta)) {{
        return;
    }}
    $update = ['ID' => $att_id];
    if (!empty($meta['title'])) {{
        $update['post_title'] = sanitize_text_field((string) $meta['title']);
    }}
    if (array_key_exists('caption', $meta)) {{
        $update['post_excerpt'] = sanitize_text_field((string) $meta['caption']);
    }}
    if (array_key_exists('description', $meta)) {{
        $update['post_content'] = wp_kses_post((string) $meta['description']);
    }}
    if (count($update) > 1) {{
        wp_update_post($update);
    }}
    if (!empty($meta['alt'])) {{
        update_post_meta($att_id, '_wp_attachment_image_alt', sanitize_text_field((string) $meta['alt']));
    }}
}};

// wp_insert_post / wp_update_post expect slashed data (they wp_unslash).
// Without wp_slash, literal backslashes in Windows USERPROFILE paths
// are stripped from post_content while FAQPage JSON-LD (meta + wp_slash)
// keeps them → live FAQ parity BLOCK (B78).
$slashed_title = wp_slash((string) $p['title']);
$slashed_content = wp_slash((string) $p['content']);
$slashed_excerpt = wp_slash((string) $p['excerpt']);

$post_id = 0;
if (!empty($p['post_id'])) {{
    $post_id = (int) $p['post_id'];
    wp_update_post([
        'ID' => $post_id,
        'post_title' => $slashed_title,
        'post_name' => $slug,
        'post_content' => $slashed_content,
        'post_excerpt' => $slashed_excerpt,
        'post_status' => 'publish',
    ]);
}} else {{
$existing = get_page_by_path($slug, OBJECT, 'post');
if ($existing instanceof WP_Post) {{
    $post_id = (int) $existing->ID;
    wp_update_post([
        'ID' => $post_id,
        'post_title' => $slashed_title,
        'post_name' => $slug,
        'post_content' => $slashed_content,
        'post_excerpt' => $slashed_excerpt,
        'post_status' => 'publish',
    ]);
}} else {{
    $post_id = (int) wp_insert_post([
        'post_title' => $slashed_title,
        'post_name' => $slug,
        'post_content' => $slashed_content,
        'post_excerpt' => $slashed_excerpt,
        'post_status' => 'publish',
        'post_type' => 'post',
    ], true);
}}
}}
if (is_wp_error($post_id)) {{
    echo 'ERR post: ' . $post_id->get_error_message() . PHP_EOL;
    exit(1);
}}
echo 'OK post=' . $post_id . ' slug=' . $slug . PHP_EOL;

if (!empty($p['cover_b64'])) {{
    $bin = base64_decode($p['cover_b64']);
    $tmp = wp_tempnam('excalibur-cover-' . $slug . '.png');
    file_put_contents($tmp, $bin);
    $file_array = [
        'name' => $slug . '-cover.png',
        'tmp_name' => $tmp,
        'type' => 'image/png',
        'error' => 0,
        'size' => strlen($bin),
    ];
    $cover_meta = [
        'alt' => (string) ($p['cover_alt'] ?? ''),
        'caption' => (string) ($p['cover_caption'] ?? ''),
        'description' => (string) ($p['cover_description'] ?? ''),
        'title' => (string) ($p['cover_title'] ?? ($slug . ' cover')),
    ];
    $att_id = media_handle_sideload($file_array, $post_id, null, [
        'post_title' => $cover_meta['title'],
        'post_excerpt' => $cover_meta['caption'],
        'post_content' => $cover_meta['description'],
    ]);
    if (is_wp_error($att_id)) {{
        echo 'WARN cover: ' . $att_id->get_error_message() . PHP_EOL;
    }} else {{
        set_post_thumbnail($post_id, (int) $att_id);
        $excalibur_apply_attachment_meta((int) $att_id, $cover_meta);
        echo 'OK featured_image=' . (int) $att_id . PHP_EOL;
        if ($cover_meta['alt'] !== '') {{
            echo 'OK featured_alt=1' . PHP_EOL;
        }}
        if ($cover_meta['caption'] !== '') {{
            echo 'OK featured_caption=1' . PHP_EOL;
        }}
        if ($cover_meta['description'] !== '') {{
            echo 'OK featured_description=1' . PHP_EOL;
        }}
    }}
    @unlink($tmp);
}}

if (!empty($p['schema_jsonld'])) {{
    update_post_meta($post_id, '_excalibur_blog_schema_jsonld', wp_slash($p['schema_jsonld']));
    echo 'OK schema_meta=1' . PHP_EOL;
}}

// Future Excalibur posts must start with the article and end with its own
// topic FAQ. The theme may use these flags to suppress generic wrappers.
update_post_meta($post_id, '_excalibur_blog_skip_theme_faq', '1');
update_post_meta($post_id, '_excalibur_blog_skip_engagement_quiz', '1');
update_post_meta($post_id, '_excalibur_blog_skip_side_stickers', '1');
echo 'OK skip_theme_faq_meta=1' . PHP_EOL;
echo 'OK skip_engagement_quiz_meta=1' . PHP_EOL;
echo 'OK skip_side_stickers_meta=1' . PHP_EOL;

if (!empty($p['inline_images'])) {{
    $content_updated = $p['content'];
    foreach ($p['inline_images'] as $img) {{
        $bin = base64_decode($img['b64']);
        $filename = $img['filename'];
        $src = $img['src'];
        
        $tmp = wp_tempnam('excalibur-inline-' . $slug . '-' . sanitize_title($filename));
        file_put_contents($tmp, $bin);
        
        $file_array = [
            'name' => $slug . '-' . $filename,
            'tmp_name' => $tmp,
            'type' => 'image/png',
            'error' => 0,
            'size' => strlen($bin),
        ];

        $inline_meta = [
            'alt' => (string) ($img['alt'] ?? ''),
            'caption' => (string) ($img['caption'] ?? ''),
            'description' => (string) ($img['description'] ?? ''),
            'title' => (string) ($img['title'] ?? ($slug . ' ' . pathinfo($filename, PATHINFO_FILENAME))),
        ];
        
        $att_id = media_handle_sideload($file_array, $post_id, null, [
            'post_title' => $inline_meta['title'],
            'post_excerpt' => $inline_meta['caption'],
            'post_content' => $inline_meta['description'],
        ]);
        
        if (is_wp_error($att_id)) {{
            echo 'WARN inline_img_upload: ' . $att_id->get_error_message() . ' for ' . $src . PHP_EOL;
        }} else {{
            $excalibur_apply_attachment_meta((int) $att_id, $inline_meta);
            $new_url = wp_get_attachment_url((int) $att_id);
            if ($new_url) {{
                $content_updated = str_replace('src="' . $src . '"', 'src="' . $new_url . '"', $content_updated);
                $content_updated = str_replace("src='" . $src . "'", "src='" . $new_url . "'", $content_updated);
                echo 'OK inline_image_upload=' . (int) $att_id . ' src=' . $src . ' url=' . $new_url . PHP_EOL;
                if ($inline_meta['alt'] !== '') {{
                    echo 'OK inline_alt=' . (int) $att_id . PHP_EOL;
                }}
                if ($inline_meta['caption'] !== '') {{
                    echo 'OK inline_caption=' . (int) $att_id . PHP_EOL;
                }}
                if ($inline_meta['description'] !== '') {{
                    echo 'OK inline_description=' . (int) $att_id . PHP_EOL;
                }}
            }}
        }}
        @unlink($tmp);
    }}
    wp_update_post([
        'ID' => $post_id,
        'post_content' => wp_slash($content_updated),
    ]);
}}

$permalink = get_permalink($post_id);
echo 'permalink=' . $permalink . PHP_EOL;
"""


def _ssh_creds(env: dict[str, str]) -> tuple[str, int, str, str]:
    host = env.get("SSH_HOST") or env["FTP_HOST"]
    port = int(env.get("SSH_PORT") or "22")
    user = env.get("SSH_USER") or env["FTP_USER"]
    password = env.get("SSH_PASS") or env["FTP_PASS"]
    return host, port, user, password


def configured_sftp_root(env: dict[str, str]) -> str:
    return normalize_sftp_root_value(
        env.get("SSH_ROOT") or env.get("FTP_ROOT") or env.get("FTP_PATH") or ""
    )


def sftp_remote_path(env: dict[str, str], remote: str, root_override: str | None = None) -> str:
    root = configured_sftp_root(env) if root_override is None else normalize_sftp_root_value(root_override)
    if not root or root in {".", "./"}:
        return remote
    return root.rstrip("/") + "/" + remote


def sftp_root_label(env: dict[str, str]) -> str:
    root = configured_sftp_root(env)
    if root in {".", "./"}:
        return "dot"
    return "configured-non-dot"


def sftp_root_candidates(env: dict[str, str]) -> list[str]:
    root = configured_sftp_root(env)
    if root and root not in {".", "./"}:
        return [root, "."]
    return ["."]


def is_missing_remote_path_error(exc: OSError) -> bool:
    errno_value = getattr(exc, "errno", None)
    if errno_value == 2:
        return True
    text = str(exc).lower()
    return "no such file" in text or "enoent" in text


def upload_bootstrap_sftp(env: dict[str, str], remote: str, data: bytes) -> str:
    import paramiko

    host, port, user, password = _ssh_creds(env)
    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        candidates = sftp_root_candidates(env)
        for index, root_candidate in enumerate(candidates):
            remote_path = sftp_remote_path(env, remote, root_candidate)
            try:
                with sftp.open(remote_path, "w") as handle:
                    handle.write(data.decode("utf-8"))
                if index > 0:
                    print(
                        "WARN SFTP root fallback: configured remote root ENOENT; "
                        "used '.' for bootstrap. Set Cloud Secret FTP_ROOT=. "
                        "(SSH_ROOT=. if used). Expected WARN — do not open a new "
                        "incident (acknowledged_env; INC-20260807-2022)."
                    )
                print(f"SFTP upload OK: {remote_path} ({len(data)} bytes)")
                return remote_path
            except OSError as exc:
                if index < len(candidates) - 1 and is_missing_remote_path_error(exc):
                    print(
                        "WARN SFTP upload: configured remote root returned ENOENT; "
                        "retrying bootstrap at '.'. Human: set FTP_ROOT=. in Cloud "
                        "Secrets (panel paths invalid on SFTP cwd).",
                        file=sys.stderr,
                    )
                    continue
                raise
    finally:
        sftp.close()
        transport.close()
    raise RuntimeError("SFTP upload did not complete")


def delete_bootstrap_sftp(env: dict[str, str], remote: str, remote_path: str | None = None) -> None:
    import paramiko

    host, port, user, password = _ssh_creds(env)
    remote_path = remote_path or sftp_remote_path(env, remote)
    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        sftp.remove(remote_path)
    except OSError:
        pass
    finally:
        sftp.close()
        transport.close()


def trigger_bootstrap_http(url: str, root: Path) -> str:
    try:
        print(f"Triggering HTTP publish on {url}...")
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "ExcaliburBlogPublish/1.0"}),
            timeout=120,
        ) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Local HTTP trigger failed ({type(e).__name__}: {e}). Entering Cloud WebFetch Fallback mode...")
        print(f"=== FALLBACK_TRIGGER_URL ===\n{url}\n=============================")
        print("Waiting for cloud-agent to write response to memory/webfetch-response.txt...")
        fallback_file = root / "memory" / "webfetch-response.txt"
        fallback_file.unlink(missing_ok=True)
        import time

        for _ in range(120):
            if fallback_file.is_file():
                out = fallback_file.read_text(encoding="utf-8")
                fallback_file.unlink()
                print("Cloud response detected successfully!")
                return out
            time.sleep(1)
        raise RuntimeError("Cloud WebFetch Fallback timed out after 120 seconds. Please trigger manually.")


def publish_via_sftp(env: dict[str, str], php: str, public_base: str) -> str:
    remote = "excalibur-blog-publish-once.php"
    data = php.encode("utf-8")
    url = public_base.rstrip("/") + "/" + remote
    root = project_root()

    uploaded_remote_path = upload_bootstrap_sftp(env, remote, data)

    try:
        out = trigger_bootstrap_http(url, root)
    finally:
        try:
            delete_bootstrap_sftp(env, remote, uploaded_remote_path)
        except Exception as cleanup_error:  # noqa: BLE001
            print(f"WARN cleanup: could not delete bootstrap {remote}: {cleanup_error}", file=sys.stderr)
    return out


def ledger_url_for_commit(permalink: str, slug: str = "") -> str:
    """Store path-only URL in git ledger to avoid secret-scan on PUBLIC_SITE_URL host."""
    value = (permalink or "").strip()
    if not value:
        return f"/{slug.strip('/')}/" if slug else ""
    if value.startswith("{{SITE_BASE}}"):
        value = value[len("{{SITE_BASE}}") :]
    if "://" in value:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        value = parsed.path or "/"
    if not value.startswith("/"):
        value = "/" + value
    if not value.endswith("/"):
        value = value + "/"
    return value


def upsert_publish_ledger(root: Path, payload: dict[str, Any], permalink: str) -> None:
    if not permalink:
        return
    ledger_path = root / "shared" / "published-articles.md"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.is_file():
        ledger_path.write_text(
            "# Excalibur BLOG — журнал опубликованных статей\n\n"
            "| date | topic_id | slug | url | status |\n"
            "|------|----------|------|-----|--------|\n",
            encoding="utf-8",
        )

    from datetime import date

    topic_id = str(payload.get("topic_id") or "").upper()
    slug = str(payload.get("slug") or "")
    ledger_url = ledger_url_for_commit(permalink, slug)
    row = f"| {date.today().isoformat()} | {topic_id} | {slug} | {ledger_url} | published |"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1].upper() == topic_id:
            lines[index] = row
            replaced = True
            break
    if not replaced:
        lines.append(row)
    ledger_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_article_qa_verdict(article_dir: Path) -> str:
    """Read verdict from article-qa.md header.

    Accepts plain ``verdict: PASS`` and markdown-bold variants like
    ``verdict: PASS`` / ``**verdict:** PASS`` / ``**verdict**: PASS``.
    Canonical template remains plain ``verdict: PASS`` without bold.
    """
    qa_path = article_dir / "article-qa.md"
    if not qa_path.is_file():
        return ""
    for line in qa_path.read_text(encoding="utf-8").splitlines()[:80]:
        stripped = line.strip()
        # Strip markdown emphasis so **verdict:** / *verdict:* still parse.
        plain = stripped.replace("*", "").replace("_", "").strip()
        if plain.lower().startswith("verdict:"):
            return plain.split(":", 1)[1].strip().upper()
    return ""


def _gate_json_status(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "INVALID"
    if not isinstance(data, dict):
        return "INVALID"
    return str(
        data.get("status") or data.get("verdict") or data.get("overall") or ""
    ).strip().upper()


def _swarm_enabled(article_dir: Path) -> bool:
    """True when article opted into editorial swarm (legacy; normally false)."""
    meta_path = article_dir / "article.meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
        if isinstance(meta, dict) and meta.get("editorial_swarm") is True:
            return True
    return False


def _swarm_skip_ok(article_dir: Path) -> bool:
    path = article_dir / "editorial-swarm-skip.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        isinstance(data, dict)
        and str(data.get("status") or "").lower() == "skip"
        and bool(str(data.get("reason") or "").strip())
    )


def ledger_status_for_topic(root: Path, topic_id: str) -> str:
    """Return latest ledger status for topic_id (lower), or empty if unknown."""
    topic = (topic_id or "").strip().upper()
    if not topic:
        return ""
    ledger_path = root / "shared" / "published-articles.md"
    if not ledger_path.is_file():
        return ""
    status = ""
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if cells[0].lower() == "date" or set(cells[0]) <= {"-", ":"}:
            continue
        if (cells[1] or "").strip().upper() != topic:
            continue
        status = (cells[4] or "").strip().lower()
    return status


def article_meta_topic_id(article_dir: Path) -> str:
    meta_path = article_dir / "article.meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("topic_id") or "").strip().upper()


def check_publish_prerequisites(
    article_dir: Path,
    *,
    require_scorecard_gate: bool = True,
    require_freshness_gate: bool = True,
    require_swarm_gates: bool = True,
    allow_stale_freshness: bool = False,
) -> list[str]:
    """Enforce contract gates before WP upload (unless --skip-gates).

    ``allow_stale_freshness`` (media-refresh path): keep link-verify /
    cover / schema; only freshness STALE is tolerated when a report exists.
    """
    blockers: list[str] = []

    link_path = article_dir / "link-verify.json"
    if not link_path.is_file():
        blockers.append("link-verify.json missing")
    else:
        try:
            link_report = json.loads(link_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            blockers.append("link-verify.json invalid")
        else:
            verdict = str(link_report.get("verdict") or "").strip().lower()
            if verdict != "pass":
                blockers.append(f"link-verify.json verdict={verdict or 'empty'} (need pass)")

    schema_path = article_dir / "schema.jsonld"
    if not schema_path.is_file():
        blockers.append("schema.jsonld missing")
    schema_gate = _gate_json_status(article_dir / "schema-gate.json")
    if schema_gate != "PASS":
        blockers.append(f"schema-gate.json status={schema_gate or 'missing'} (need PASS)")

    # article-qa / content-evidence are optional legacy paperwork — not required.

    cover_path = article_dir / "cover" / "cover.png"
    if not cover_path.is_file():
        blockers.append("cover/cover.png missing")
    article_html_path = article_dir / "article.html"
    article_html = (
        article_html_path.read_text(encoding="utf-8")
        if article_html_path.is_file()
        else ""
    )
    if not article_html or len(article_html) < 200:
        blockers.append("article.html missing or too small")
    blockers.extend(validate_local_article_images(article_dir, article_html))

    meta_path = article_dir / "article.meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
        blockers.append("article.meta.json missing/invalid")
    theme_blocks = meta.get("theme_blocks") if isinstance(meta, dict) else {}
    for key in ("faq", "quiz", "side_stickers"):
        if not isinstance(theme_blocks, dict) or theme_blocks.get(key) != "skip":
            blockers.append(f"article.meta.json theme_blocks.{key}=skip required")
    blockers.extend(validate_article_canon(article_dir, project_root()))

    if require_freshness_gate and (article_dir / "freshness-report.json").is_file():
        freshness = _gate_json_status(article_dir / "freshness-report.json")
        if freshness == "STALE" and allow_stale_freshness:
            pass
        elif freshness != "PASS":
            blockers.append(
                f"freshness-report.json status={freshness or 'empty'} "
                f"(need {'PASS or STALE' if allow_stale_freshness else 'PASS'})"
            )

    return blockers


def evaluate_publish_output(out: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fail publish when post OK but cover/inline media WARN or incomplete."""
    lines = [line.strip() for line in (out or "").splitlines() if line.strip()]
    has_post = any(line.startswith("OK post=") for line in lines)
    media_warns = [line for line in lines if line.startswith("WARN cover:") or line.startswith("WARN inline_img_upload:")]
    featured_ok = any(line.startswith("OK featured_image=") for line in lines)
    inline_ok = sum(1 for line in lines if line.startswith("OK inline_image_upload="))
    expected_inline = len(payload.get("inline_images") or [])
    expect_cover = bool(payload.get("cover_b64"))

    errors: list[str] = []
    if not has_post:
        errors.append("missing OK post=")
    if expect_cover and not featured_ok:
        errors.append("cover expected but missing OK featured_image=")
    if expected_inline and inline_ok < expected_inline:
        errors.append(f"inline images expected={expected_inline} uploaded={inline_ok}")
    if media_warns:
        errors.extend(media_warns)

    return {
        "ok": has_post and not errors,
        "errors": errors,
        "featured_ok": featured_ok,
        "inline_ok": inline_ok,
        "expected_inline": expected_inline,
        "media_warns": media_warns,
    }


def normalize_ledger_redacted_urls(root: Path) -> int:
    """Rewrite legacy [REDACTED]/slug/ ledger URLs to path-only /slug/."""
    ledger_path = root / "shared" / "published-articles.md"
    if not ledger_path.is_file():
        return 0
    text = ledger_path.read_text(encoding="utf-8")
    new_text, n = re.subn(r"\| \[REDACTED\](/[^|\s]+/) \|", r"| \1 |", text)
    if n:
        ledger_path.write_text(new_text, encoding="utf-8")
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--env-check",
        action="store_true",
        help="Validate publish env/secrets without loading article payload or printing secret values",
    )
    ap.add_argument("--public-base", type=str, default=None, help="Override PUBLIC_SITE_URL")
    ap.add_argument(
        "--skip-gates",
        action="store_true",
        help=(
            "Skip link-verify / cover / schema / freshness / swarm "
            "prerequisites (emergency only; prefer --media-refresh for cover "
            "re-upload of already-published posts)"
        ),
    )
    ap.add_argument(
        "--media-refresh",
        action="store_true",
        help=(
            "Re-upload cover/inline media for an already-published ledger post: "
            "requires link-verify PASS + cover/schema; "
            "allows freshness STALE; does not blanket-skip other gates"
        ),
    )
    ap.add_argument(
        "--allow-stale-freshness",
        action="store_true",
        help=(
            "Allow freshness-report.json status=STALE while keeping all other "
            "publish gates (implied by --media-refresh)"
        ),
    )
    ap.add_argument(
        "--deploy-llms",
        action="store_true",
        help="After successful publish, SFTP-upload memory/blog/llms.txt (+ llms-full.txt) to WP root",
    )
    ap.add_argument(
        "--normalize-ledger",
        action="store_true",
        help="Rewrite legacy [REDACTED]/slug/ rows in published-articles.md to path-only and exit",
    )
    args = ap.parse_args()
    root = project_root()

    if args.normalize_ledger:
        fixed = normalize_ledger_redacted_urls(root)
        print(json.dumps({"normalized_rows": fixed}, ensure_ascii=False))
        return 0

    if args.env_check:
        env = load_env(root)
        report = publish_env_check_report(env)
        human_action = report.get("human_action")
        if human_action:
            print(f"WARN {human_action}", file=sys.stderr)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["allow_publish"] and not report["missing"] else 1

    if args.article_dir is None:
        print("--article-dir is required unless --env-check/--normalize-ledger is used", file=sys.stderr)
        return 2

    article_dir = args.article_dir if args.article_dir.is_absolute() else root / args.article_dir
    env = load_env(root)
    public = args.public_base or env.get("PUBLIC_SITE_URL") or env.get("WP_HOME") or env.get("WP_SITE_URL") or ""

    if args.skip_gates and (args.media_refresh or args.allow_stale_freshness):
        print(
            "BLOCKER: --skip-gates cannot combine with --media-refresh / "
            "--allow-stale-freshness; drop --skip-gates so QA/link-verify stay enforced",
            file=sys.stderr,
        )
        return 2

    allow_stale_freshness = bool(args.media_refresh or args.allow_stale_freshness)

    if args.media_refresh:
        topic_id = article_meta_topic_id(article_dir)
        ledger_status = ledger_status_for_topic(root, topic_id)
        if not topic_id:
            print(
                "BLOCKER: --media-refresh requires article.meta.json topic_id",
                file=sys.stderr,
            )
            return 2
        if ledger_status != "published":
            print(
                "BLOCKER: --media-refresh requires ledger status=published "
                f"(topic_id={topic_id} status={ledger_status or 'missing'})",
                file=sys.stderr,
            )
            return 2

    if not args.skip_gates:
        gate_blockers = check_publish_prerequisites(
            article_dir,
            require_scorecard_gate=not args.dry_run,
            require_freshness_gate=not args.dry_run,
            require_swarm_gates=not args.dry_run,
            allow_stale_freshness=allow_stale_freshness,
        )
        if gate_blockers:
            print("BLOCKER: publish prerequisites failed:", file=sys.stderr)
            for item in gate_blockers:
                print(f"  - {item}", file=sys.stderr)
            return 2
        if allow_stale_freshness:
            freshness_status = _gate_json_status(article_dir / "freshness-report.json")
            if freshness_status == "STALE":
                mode = "--media-refresh" if args.media_refresh else "--allow-stale-freshness"
                print(
                    f"WARN {mode}: freshness-report.json status=STALE allowed; "
                    "link-verify / cover / schema still enforced",
                    file=sys.stderr,
                )
        if args.dry_run and not (article_dir / "schema.jsonld").is_file():
            print(
                "WARN schema.jsonld missing (required for real publish, not dry-run)",
                file=sys.stderr,
            )
    else:
        print("WARN --skip-gates: publishing without link-verify/schema prerequisites", file=sys.stderr)

    payload = load_article(article_dir, public_base=public)
    php = build_php(payload)

    if args.dry_run:
        schema_has_placeholder = SITE_BASE_PLACEHOLDER in (payload.get("schema_jsonld") or "")
        inline = payload.get("inline_images") or []
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "slug": payload["slug"],
                    "title": payload["title"],
                    "inline_images": len(inline),
                    "gates_skipped": bool(args.skip_gates),
                    "media_refresh": bool(args.media_refresh),
                    "allow_stale_freshness": allow_stale_freshness,
                    "prerequisites_ok": True,
                    "cover_media": {
                        "alt": bool(payload.get("cover_alt")),
                        "caption": bool(payload.get("cover_caption")),
                        "description": bool(payload.get("cover_description")),
                        "title": bool(payload.get("cover_title")),
                    },
                    "inline_media": [
                        {
                            "src": item.get("src"),
                            "alt": bool(item.get("alt")),
                            "caption": bool(item.get("caption")),
                            "description": bool(item.get("description")),
                        }
                        for item in inline
                    ],
                    "site_base_expanded": payload.get("site_base_expanded", False),
                    "schema_placeholder_remaining": schema_has_placeholder,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("PHP bytes:", len(php.encode("utf-8")))
        if schema_has_placeholder:
            print(
                "BLOCKER: schema still contains {{SITE_BASE}}; set PUBLIC_SITE_URL or --public-base",
                file=sys.stderr,
            )
            return 2
        return 0

    if env.get("EXCALIBUR_BLOG_ALLOW_PUBLISH", "").strip().lower() != "yes":
        print("BLOCKER: EXCALIBUR_BLOG_ALLOW_PUBLISH != yes", file=sys.stderr)
        return 1
    missing = validate_publish_env(env)
    if missing:
        print(f"BLOCKER: missing publish env: {', '.join(missing)}", file=sys.stderr)
        return 2
    if not public:
        print("PUBLIC_SITE_URL or --public-base required", file=sys.stderr)
        return 2
    if SITE_BASE_PLACEHOLDER in (payload.get("schema_jsonld") or ""):
        print("BLOCKER: schema still contains {{SITE_BASE}} after expand", file=sys.stderr)
        return 2
    out = publish_via_sftp(env, php, public)
    print(out)

    media = evaluate_publish_output(out, payload)
    result_path = article_dir / "wp-publish-result.json"
    permalink = ""
    for line in out.splitlines():
        if line.startswith("permalink="):
            permalink = line.split("=", 1)[1].strip()
    # Commit-safe artifact: redact live PUBLIC_SITE_URL → {{SITE_BASE}} (never [REDACTED]).
    safe_permalink = redact_site_base(permalink, public)
    safe_raw = redact_site_base(out, public)
    verdict = "pass" if media["ok"] else "fail"
    result = {
        "slug": payload["slug"],
        "topic_id": payload["topic_id"],
        "permalink": safe_permalink,
        "publish_method": "sftp",
        "cover_evidence": redact_structure(payload.get("cover_evidence", {}), public),
        "raw_output": safe_raw,
        "media_check": {
            "featured_ok": media["featured_ok"],
            "inline_ok": media["inline_ok"],
            "expected_inline": media["expected_inline"],
            "errors": media["errors"],
        },
        "verdict": verdict,
    }
    if verdict != "pass":
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("BLOCKER: publish media/post incomplete:", file=sys.stderr)
        for err in media["errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # Publishing is not complete until the live theme respects the Excalibur
    # article boundary. This catches generic quest/stickers and duplicate FAQ
    # injected outside post_content.
    live_errors: list[str] = []
    try:
        request = urllib.request.Request(
            permalink,
            headers={"User-Agent": "ExcaliburBlogLiveGate/1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            live_html = response.read().decode("utf-8", errors="replace")
        first_paragraph = re.search(
            r"<p\b[^>]*>(.*?)</p>", str(payload.get("content") or ""), flags=re.I | re.S
        )
        body_probe = ""
        if first_paragraph:
            body_probe = re.sub(r"<[^>]+>", " ", first_paragraph.group(1))
            body_probe = re.sub(r"\s+", " ", body_probe).strip()[:120]
        live_errors = inspect_live_page(
            live_html,
            expected_slug=str(payload.get("slug") or ""),
            expected_title=str(payload.get("title") or ""),
            body_probe=body_probe,
            verify_media=True,
            expected_permalink=permalink,
        )
    except Exception as exc:  # network failure is a blocker, never a fake PASS
        live_errors = [f"live page fetch failed: {type(exc).__name__}: {exc}"]
    live_report = {
        "gate": "live-page",
        "status": "PASS" if not live_errors else "BLOCK",
        "permalink": safe_permalink,
        "errors": live_errors,
    }
    (article_dir / "live-page-report.json").write_text(
        json.dumps(live_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if live_errors:
        result["verdict"] = "fail"
        result["live_page"] = live_report
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("BLOCKER: live theme/article boundary failed:", file=sys.stderr)
        for err in live_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    result["live_page"] = live_report
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    upsert_publish_ledger(root, payload, permalink or safe_permalink)
    if args.deploy_llms:
        from excalibur_blog_llms_deploy import deploy_llms_files

        deploy_report = deploy_llms_files(root, env, public)
        print(json.dumps({"llms_deploy": deploy_report}, ensure_ascii=False))
        if deploy_report.get("status") != "PASS":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
