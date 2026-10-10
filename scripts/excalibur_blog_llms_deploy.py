#!/usr/bin/env python3
"""Deploy memory/blog/llms.txt (+ llms-full.txt) to WordPress site root via SFTP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from excalibur_blog_site_base import SITE_BASE_PLACEHOLDER, expand_site_base
from excalibur_blog_wp_publish import (
    load_env,
    project_root,
    sftp_remote_path,
    sftp_root_candidates,
    validate_publish_env,
    _ssh_creds,
    is_missing_remote_path_error,
)


def deploy_llms_files(root: Path, env: dict[str, str], public_base: str) -> dict[str, Any]:
    import paramiko

    llms_dir = root / "memory" / "blog"
    files = [
        ("llms.txt", llms_dir / "llms.txt"),
        ("llms-full.txt", llms_dir / "llms-full.txt"),
    ]
    missing = [name for name, path in files if not path.is_file()]
    if missing:
        return {"status": "FAIL", "errors": [f"missing local file: {name}" for name in missing]}

    env_missing = validate_publish_env(env)
    if env_missing:
        return {"status": "FAIL", "errors": [f"missing env: {', '.join(env_missing)}"]}

    host, port, user, password = _ssh_creds(env)
    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    uploaded: list[str] = []
    errors: list[str] = []
    try:
        candidates = sftp_root_candidates(env)
        for name, path in files:
            raw = path.read_text(encoding="utf-8")
            body = expand_site_base(raw, public_base)
            if SITE_BASE_PLACEHOLDER in body:
                errors.append(f"{name} still contains {{{{SITE_BASE}}}} after expand")
                continue
            data = body.encode("utf-8")
            placed = False
            for index, root_candidate in enumerate(candidates):
                remote_path = sftp_remote_path(env, name, root_candidate)
                try:
                    with sftp.open(remote_path, "w") as handle:
                        handle.write(data.decode("utf-8"))
                    uploaded.append(remote_path)
                    placed = True
                    if index > 0:
                        print(
                            "WARN SFTP root fallback used for llms deploy; "
                            "set Cloud Secret FTP_ROOT=. (SSH_ROOT=. if used). "
                            "Expected WARN — do not open a new incident "
                            "(acknowledged_env; INC-20260807-2022).",
                            file=sys.stderr,
                        )
                    break
                except OSError as exc:
                    if index < len(candidates) - 1 and is_missing_remote_path_error(exc):
                        continue
                    errors.append(f"{name}: {exc}")
                    break
            if not placed:
                errors.append(f"{name}: upload failed")
    finally:
        sftp.close()
        transport.close()

    status = "PASS" if uploaded and not errors else "FAIL"
    return {
        "status": status,
        "uploaded": uploaded,
        "errors": errors,
        "public_base_configured": bool(public_base),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SFTP-deploy llms.txt to WP root")
    ap.add_argument("--public-base", type=str, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = project_root()
    env = load_env(root)
    public = args.public_base or env.get("PUBLIC_SITE_URL") or env.get("WP_HOME") or env.get("WP_SITE_URL") or ""

    if args.dry_run:
        llms = root / "memory/blog/llms.txt"
        full = root / "memory/blog/llms-full.txt"
        report = {
            "dry_run": True,
            "llms_txt": llms.is_file(),
            "llms_full_txt": full.is_file(),
            "public_base_configured": bool(public),
            "placeholder_remaining": (
                (SITE_BASE_PLACEHOLDER in llms.read_text(encoding="utf-8")) if llms.is_file() and public else None
            ),
        }
        if public and llms.is_file():
            expanded = expand_site_base(llms.read_text(encoding="utf-8"), public)
            report["placeholder_remaining"] = SITE_BASE_PLACEHOLDER in expanded
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["llms_txt"] and report["llms_full_txt"] else 1

    if env.get("EXCALIBUR_BLOG_ALLOW_PUBLISH", "").strip().lower() != "yes":
        print("BLOCKER: EXCALIBUR_BLOG_ALLOW_PUBLISH != yes", file=sys.stderr)
        return 1
    if not public:
        print("BLOCKER: PUBLIC_SITE_URL or --public-base required", file=sys.stderr)
        return 2

    report = deploy_llms_files(root, env, public)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
