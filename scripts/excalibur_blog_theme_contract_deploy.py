#!/usr/bin/env python3
"""Idempotently teach the WP theme to respect future Excalibur post meta."""
from __future__ import annotations

import argparse
import os
import posixpath
from datetime import datetime, timezone
from pathlib import Path


def patch_functions(text: str) -> str:
    old = "if ( is_single() && 'post' === get_post_type() ) {"
    new = (
        "if ( is_single() && 'post' === get_post_type() "
        "&& ! ( '1' === get_post_meta( get_the_ID(), "
        "'_excalibur_blog_skip_theme_faq', true ) "
        "&& '1' === get_post_meta( get_the_ID(), "
        "'_excalibur_blog_skip_engagement_quiz', true ) ) ) {"
    )
    if new not in text:
        function_start = text.find("function custom_theme_add_faq_to_single")
        filter_anchor = text.find(
            "add_filter( 'the_content', 'custom_theme_add_faq_to_single', 99 );"
        )
        if function_start < 0 or filter_anchor < function_start:
            raise ValueError("functions.php FAQ function bounds not found")
        faq_function = text[function_start:filter_anchor]
        if old not in faq_function:
            raise ValueError("functions.php FAQ anchor not found")
        patched_function = faq_function.replace(old, new, 1)
        text = text[:function_start] + patched_function + text[filter_anchor:]

    schema_marker = "function excalibur_blog_output_schema_jsonld()"
    if schema_marker not in text:
        anchor = "add_filter( 'the_content', 'custom_theme_add_faq_to_single', 99 );"
        if anchor not in text:
            raise ValueError("functions.php FAQ filter anchor not found")
        schema_hook = r"""

// Excalibur future posts own their schema and topic FAQ.
function excalibur_blog_output_schema_jsonld() {
	if ( ! is_single() || '1' !== get_post_meta( get_the_ID(), '_excalibur_blog_skip_engagement_quiz', true ) ) {
		return;
	}
	$schema = get_post_meta( get_the_ID(), '_excalibur_blog_schema_jsonld', true );
	if ( is_string( $schema ) && '' !== trim( $schema ) ) {
		echo '<script type="application/ld+json">' . $schema . '</script>' . PHP_EOL; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
	}
}
add_action( 'wp_head', 'excalibur_blog_output_schema_jsonld', 20 );
"""
        text = text.replace(anchor, anchor + schema_hook, 1)

    rss_marker = "function excalibur_blog_rss_enclosure()"
    if rss_marker not in text:
        rss_hook = r"""

// Dzen article cover = RSS enclosure from featured image (not a second body figure).
function excalibur_blog_rss_enclosure() {
	if ( ! has_post_thumbnail() ) {
		return;
	}
	$url = get_the_post_thumbnail_url( get_the_ID(), 'full' );
	if ( ! is_string( $url ) || '' === $url ) {
		return;
	}
	$mime = get_post_mime_type( get_post_thumbnail_id() );
	if ( ! is_string( $mime ) || '' === $mime ) {
		$mime = 'image/png';
	}
	echo '<enclosure url="' . esc_url( $url ) . '" type="' . esc_attr( $mime ) . '" />' . "\n";
}
add_action( 'rss2_item', 'excalibur_blog_rss_enclosure', 11 );
"""
        text = text.rstrip() + rss_hook
    return text


def patch_single(text: str) -> str:
    # Premium kz-single templates dropped theme stickers/quiz; skip-meta
    # is enough because those blocks are absent from the markup.
    has_legacy_stickers = 'article-side-stickers' in text
    has_legacy_quiz = 'article-signal-cards' in text
    if not has_legacy_stickers and not has_legacy_quiz:
        return text

    marker = """\t\tthe_post();

\t\t$excalibur_skip_side_stickers = '1' === get_post_meta( get_the_ID(), '_excalibur_blog_skip_side_stickers', true );
\t\t$excalibur_skip_quiz = '1' === get_post_meta( get_the_ID(), '_excalibur_blog_skip_engagement_quiz', true );
"""
    if "$excalibur_skip_side_stickers" not in text:
        anchor = "\t\tthe_post();\n"
        if anchor not in text:
            raise ValueError("single.php the_post anchor not found")
        text = text.replace(anchor, marker, 1)

    side_open = '\t\t<div class="article-side-stickers"'
    side_guard = "\t\t<?php if ( ! $excalibur_skip_side_stickers ) : ?>\n" + side_open
    if side_guard not in text:
        if side_open not in text:
            raise ValueError("single.php side stickers anchor not found")
        text = text.replace(side_open, side_guard, 1)
        side_end = """\t\t</div>

\t\t<article id="post-<?php the_ID(); ?>"""
        guarded_end = """\t\t</div>
\t\t<?php endif; ?>

\t\t<article id="post-<?php the_ID(); ?>"""
        if side_end not in text:
            raise ValueError("single.php side stickers terminator not found")
        text = text.replace(side_end, guarded_end, 1)

    signal_open = '\t\t\t<section class="article-signal-cards"'
    signal_guard = "\t\t\t<?php if ( ! $excalibur_skip_quiz ) : ?>\n" + signal_open
    if signal_guard not in text:
        if signal_open not in text:
            raise ValueError("single.php signal cards anchor not found")
        text = text.replace(signal_open, signal_guard, 1)
        quiz_end = """\t\t\t</section>

\t\t\t<?php if ( has_post_thumbnail() ) : ?>"""
        guarded_quiz_end = """\t\t\t</section>
\t\t\t<?php endif; ?>

\t\t\t<?php if ( has_post_thumbnail() ) : ?>"""
        if quiz_end not in text:
            raise ValueError("single.php quiz terminator not found")
        text = text.replace(quiz_end, guarded_quiz_end, 1)
    return text


def _settings() -> tuple[str, str, str, int, list[str]]:
    values = dict(os.environ)
    local = Path(__file__).resolve().parents[1] / "memory/site.env.local"
    if local.is_file():
        for raw in local.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip("\"'"))
    host = values.get("FTP_HOST") or values.get("SSH_HOST") or ""
    user = values.get("FTP_USER") or values.get("SSH_USER") or ""
    password = (
        values.get("FTP_PASS")
        or values.get("FTP_PASSWORD")
        or values.get("SSH_PASS")
        or values.get("SSH_PASSWORD")
        or ""
    )
    if not all((host, user, password)):
        raise RuntimeError("SFTP credentials missing")
    port = int(values.get("SSH_PORT") or 22)
    configured_root = (values.get("SSH_ROOT") or values.get("FTP_ROOT") or ".").strip()
    if configured_root in {"", "/"}:
        configured_root = "."
    roots = list(dict.fromkeys((configured_root, ".")))
    return host, user, password, port, roots


def deploy() -> None:
    import paramiko

    host, user, password, port, roots = _settings()
    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    base = ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    try:
        for root in roots:
            candidate = posixpath.normpath(
                posixpath.join(root, "wp-content/themes/kov4eg-mcp-theme")
            )
            try:
                sftp.stat(candidate)
                base = candidate
                break
            except OSError:
                continue
        if not base:
            raise RuntimeError("WordPress theme path not found in configured root or login cwd")
        for name, patcher in (
            ("functions.php", patch_functions),
            ("single.php", patch_single),
        ):
            remote = posixpath.join(base, name)
            with sftp.open(remote, "r") as handle:
                original = handle.read().decode("utf-8")
            patched = patcher(original)
            if patched == original:
                print(f"OK unchanged={name}")
                continue
            backup = f"{remote}.bak-excalibur-{stamp}"
            with sftp.open(backup, "w") as handle:
                handle.write(original.encode("utf-8"))
            with sftp.open(remote, "w") as handle:
                handle.write(patched.encode("utf-8"))
            print(f"OK patched={name} backup={posixpath.basename(backup)}")
    finally:
        sftp.close()
        transport.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Patch remote theme over SFTP; otherwise only validates local fixture args",
    )
    args = parser.parse_args()
    if not args.deploy:
        parser.error("--deploy required")
    deploy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
