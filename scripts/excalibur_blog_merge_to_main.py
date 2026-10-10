#!/usr/bin/env python3
"""Merge the current Cloud Agent branch into origin/main (this repo's git).

Хранилище канона — **git origin/main этого репо**, не GitHub Pull Request
и не Cursor `open_git_pr`. Следующий cron читает main; ветка PR сама по
себе следующий запуск не видит.

Usage:
  python3 scripts/excalibur_blog_merge_to_main.py
  python3 scripts/excalibur_blog_merge_to_main.py --dry-run
  python3 scripts/excalibur_blog_merge_to_main.py --via-pr   # legacy GitHub PR
  python3 scripts/excalibur_blog_merge_to_main.py --pr 95

Default: fast-forward-only `git push origin HEAD:main`.
`--via-pr` / `--pr` — старый путь через `gh pr merge` (не канон).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    env_root = os.environ.get("EXCALIBUR_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def gh_json(args: list[str], *, cwd: Path) -> object:
    proc = run(["gh", *args], cwd=cwd, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh failed").strip())
    text = (proc.stdout or "").strip()
    if not text:
        return None
    return json.loads(text)


def current_branch(cwd: Path) -> str:
    proc = run(["git", "branch", "--show-current"], cwd=cwd)
    return (proc.stdout or "").strip()


def default_branch(cwd: Path) -> str:
    try:
        data = gh_json(["repo", "view", "--json", "defaultBranchRef"], cwd=cwd)
        if isinstance(data, dict):
            ref = data.get("defaultBranchRef") or {}
            if isinstance(ref, dict) and ref.get("name"):
                return str(ref["name"])
    except Exception:  # noqa: BLE001
        pass
    return "main"


def find_pr_for_branch(branch: str, *, cwd: Path, base: str) -> dict[str, object] | None:
    data = gh_json(
        [
            "pr",
            "list",
            "--head",
            branch,
            "--base",
            base,
            "--state",
            "open",
            "--json",
            "number,url,isDraft,title,mergeable,state",
        ],
        cwd=cwd,
    )
    if isinstance(data, list) and data:
        item = data[0]
        return item if isinstance(item, dict) else None
    return None


def pr_view(number: int, *, cwd: Path) -> dict[str, object]:
    data = gh_json(
        [
            "pr",
            "view",
            str(number),
            "--json",
            "number,url,isDraft,title,mergeable,state,baseRefName,headRefName",
        ],
        cwd=cwd,
    )
    if not isinstance(data, dict):
        raise RuntimeError(f"PR #{number} not found")
    return data


def direct_push_to_base(*, cwd: Path, base: str, dry_run: bool) -> int:
    """Persist the current HEAD to main when PR creation is unavailable.

    This is intentionally fast-forward-only: origin/base must be an ancestor of
    HEAD. If another commit landed on main after this branch was created, the
    push is blocked instead of overwriting anything.
    """

    print("fallback=direct_push_head_to_base")
    fetch = run(["git", "fetch", "origin", base], cwd=cwd, check=False)
    if fetch.returncode != 0:
        print("❌ MERGE BLOCKER: cannot fetch base before direct push")
        print((fetch.stderr or fetch.stdout or "").strip())
        print("merge_status=blocker_direct_push_fetch")
        return 6

    base_ref = f"origin/{base}"
    ancestor = run(["git", "merge-base", "--is-ancestor", base_ref, "HEAD"], cwd=cwd, check=False)
    if ancestor.returncode != 0:
        print(f"❌ MERGE BLOCKER: {base_ref} is not an ancestor of HEAD")
        print("Refuse direct push because it would not be a fast-forward update.")
        print("merge_status=blocker_direct_push_not_fast_forward")
        return 7

    if dry_run:
        print("dry_run=1")
        print(f"would: git push origin HEAD:{base}")
        print("merge_status=dry_run_direct_push")
        return 0

    pushed = run(["git", "push", "origin", f"HEAD:{base}"], cwd=cwd, check=False)
    if pushed.returncode != 0:
        print("❌ MERGE BLOCKER: direct push to base failed")
        print((pushed.stderr or pushed.stdout or "").strip())
        print("merge_status=blocker_direct_push_failed")
        return 8

    print(f"OK pushed HEAD to {base} (fast-forward)")
    print("merge_status=direct_pushed")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Merge current Cloud PR into main")
    ap.add_argument("--pr", type=int, help="PR number (default: open PR for current branch)")
    ap.add_argument("--base", default="", help="Base branch (default: repo default / main)")
    ap.add_argument("--dry-run", action="store_true", help="Print actions only")
    ap.add_argument(
        "--keep-branch",
        action="store_true",
        help="Do not delete head branch after --via-pr merge",
    )
    ap.add_argument(
        "--via-pr",
        action="store_true",
        help="Legacy: merge via GitHub PR (gh pr merge). Default is origin/main git push.",
    )
    ap.add_argument(
        "--no-direct-push-fallback",
        action="store_true",
        help="Block instead of fast-forward pushing HEAD to base (only with --via-pr)",
    )
    args = ap.parse_args()

    root = project_root()
    base = args.base.strip() or default_branch(root)
    branch = current_branch(root)

    if branch and branch == base:
        print(f"SKIP already on {base}; nothing to merge")
        print("merge_status=skipped_on_base")
        return 0

    # Канон: писать в git origin/main. GitHub PR — не хранилище.
    if not args.pr and not args.via_pr:
        return direct_push_to_base(cwd=root, base=base, dry_run=args.dry_run)

    if args.pr:
        pr = pr_view(args.pr, cwd=root)
    else:
        found = find_pr_for_branch(branch, cwd=root, base=base) if branch else None
        if not found:
            branch_label = branch or "detached HEAD"
            print(f"WARN no open PR for head={branch_label} base={base}")
            if not args.no_direct_push_fallback:
                return direct_push_to_base(cwd=root, base=base, dry_run=args.dry_run)
            print("❌ MERGE BLOCKER: no open PR and direct-push fallback disabled")
            print("merge_status=blocker_no_pr")
            return 2
        pr = found

    number = int(pr["number"])
    url = str(pr.get("url") or f"PR #{number}")
    is_draft = bool(pr.get("isDraft"))
    mergeable = str(pr.get("mergeable") or "")
    title = str(pr.get("title") or "")

    print(f"branch={branch}")
    print(f"base={base}")
    print(f"pr={number}")
    print(f"url={url}")
    print(f"title={title}")
    print(f"isDraft={is_draft}")
    print(f"mergeable={mergeable}")

    if args.dry_run:
        print("dry_run=1")
        if is_draft:
            print(f"would: gh pr ready {number}")
        merge_flags = ["--merge"]
        if not args.keep_branch:
            merge_flags.append("--delete-branch")
        print(f"would: gh pr merge {number} {' '.join(merge_flags)}")
        print("merge_status=dry_run")
        return 0

    if is_draft:
        ready = run(["gh", "pr", "ready", str(number)], cwd=root, check=False)
        if ready.returncode != 0:
            print("❌ MERGE BLOCKER: cannot mark PR ready (still draft?)")
            print((ready.stderr or ready.stdout or "").strip())
            print("merge_status=blocker_draft")
            return 3
        print(f"OK marked PR #{number} ready for review")

    # Refresh mergeable after ready
    pr = pr_view(number, cwd=root)
    mergeable = str(pr.get("mergeable") or "")
    if mergeable and mergeable.upper() not in {"MERGEABLE", "UNKNOWN", ""}:
        print(f"❌ MERGE BLOCKER: PR not mergeable ({mergeable})")
        print("merge_status=blocker_not_mergeable")
        return 4

    merge_cmd = ["gh", "pr", "merge", str(number), "--merge"]
    if not args.keep_branch:
        merge_cmd.append("--delete-branch")
    merged = run(merge_cmd, cwd=root, check=False)
    if merged.returncode != 0:
        err = (merged.stderr or merged.stdout or "").strip()
        print("❌ MERGE BLOCKER: gh pr merge failed")
        print(err)
        if "allow_auto_merge" in err.lower() or "auto merge" in err.lower():
            print("HINT: repo allow_auto_merge is optional; this script uses direct merge.")
        print("merge_status=blocker_merge_failed")
        return 5

    print(f"OK merged PR #{number} into {base}")
    print(f"permalink_pr={url}")
    print("merge_status=merged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
