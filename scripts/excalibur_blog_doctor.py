#!/usr/bin/env python3
"""Minimal preflight for clean human-first Excalibur BLOG pipeline."""
from __future__ import annotations

import argparse
import importlib.util
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


def check(
    condition: bool,
    label: str,
    errors: list[str],
    warnings: list[str],
    *,
    warn: bool = False,
    verbose: bool = False,
) -> None:
    if condition:
        if verbose:
            print(f"OK {label}")
        return
    if warn:
        warnings.append(label)
        print(f"WARN {label}")
    else:
        errors.append(label)
        print(f"FAIL {label}")


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def merged_publish_env(root: Path) -> dict[str, str]:
    keys = {
        "PUBLIC_SITE_URL",
        "WP_HOME",
        "WP_SITE_URL",
        "FTP_HOST",
        "FTP_PORT",
        "FTP_USER",
        "FTP_PASS",
        "FTP_PASSWORD",
        "FTP_ROOT",
        "EXCALIBUR_BLOG_ALLOW_PUBLISH",
    }
    env = read_env_file(root / "memory/site.env.local")
    for key in keys:
        value = os.environ.get(key)
        if value:
            env[key] = value
    if not env.get("FTP_PASS") and env.get("FTP_PASSWORD"):
        env["FTP_PASS"] = env["FTP_PASSWORD"]
    return env


def git_ls_files(root: Path, pathspec: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", pathspec],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Excalibur BLOG preflight doctor")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="show every passing check")
    args = parser.parse_args()

    root = project_root()
    errors: list[str] = []
    warnings: list[str] = []
    if args.verbose:
        print(f"EXCALIBUR_ROOT={root}")

    def report(condition: bool, label: str, *, warn: bool = False) -> None:
        check(condition, label, errors, warnings, warn=warn, verbose=args.verbose)

    required = (
        "AGENTS.md",
        "shared/writer-master-prompt.md",
        "shared/dzen-content-rules.md",
        "shared/dzen-description-rules.md",
        "shared/rf-blocked-entities.json",
        "shared/pipeline-canon.json",
        "shared/published-titles.md",
        "shared/topic-focus-contract.md",
        "scripts/excalibur_blog_topic_focus.py",
        "agents/excalibur-blog-writer.md",
        "agents/excalibur-blog-research.md",
        "agents/excalibur-blog-publish.md",
        "skills/writer-excalibur-blog/SKILL.md",
        "skills/dzen-article-writing/SKILL.md",
        "skills/director-excalibur-blog/SKILL.md",
        "shared/gemini-article-contract.md",
        "shared/HOW-WE-SHIP.md",
        "shared/article-images-contract.md",
        "shared/morning-viral-slot.md",
        "shared/blog-cover-sunburst-comic-contract.md",
        "shared/cover-sunburst-comic-prompt.txt",
        "memory/cover/assets/cover-mascot.png",
        "shared/cursor-subagents.md",
        "shared/subagent-memory-contract.md",
        "shared/subagent-task-prompt.md",
        "scripts/excalibur_blog_gemini_article_gate.py",
        "scripts/excalibur_blog_body_len.py",
        "scripts/excalibur_blog_gemini_materialize.py",
        "scripts/excalibur_blog_cover_sunburst_i2i.py",
        "scripts/excalibur_blog_cover_black_prompt.py",
        "skills/viraldzen-collect/SKILL.md",
        "scripts/excalibur_blog_research_start.py",
        "scripts/excalibur_blog_published_titles.py",
        "scripts/excalibur_blog_pipeline_canon.py",
        "scripts/excalibur_blog_structure_gate.py",
        "scripts/excalibur_blog_opening_meta_gate.py",
        "scripts/excalibur_blog_sol_rewrite_depth_gate.py",
        "scripts/excalibur_blog_description_gate.py",
        "scripts/excalibur_blog_cover_text_gate.py",
        "scripts/excalibur_blog_wp_publish.py",
        "scripts/excalibur_blog_merge_to_main.py",
    )
    for rel in required:
        report((root / rel).is_file(), f"{rel} exists")

    report((root / ".cursor/agents").is_dir(), ".cursor/agents exists")
    report(module_available("PIL"), "Pillow available")
    report(module_available("numpy"), "numpy available")

    topics_dir = root / "memory/topics"
    report(
        not topics_dir.exists(),
        "memory/topics/ removed (no blog-topics pool)",
    )

    forbidden = (
        "agents/excalibur-blog-sol.md",
        "skills/sol-excalibur-blog/SKILL.md",
        "agents/excalibur-blog-title.md",
        "agents/excalibur-blog-description.md",
        "agents/excalibur-blog-cover-text.md",
        ".cursor/agents/excalibur-blog-title.md",
        ".cursor/agents/excalibur-blog-description.md",
        ".cursor/agents/excalibur-blog-cover-text.md",
        "skills/title-excalibur-blog/SKILL.md",
        "skills/description-excalibur-blog/SKILL.md",
        "skills/cover-text-excalibur-blog/SKILL.md",
        ".cursor/skills/title-excalibur-blog/SKILL.md",
        ".cursor/skills/description-excalibur-blog/SKILL.md",
        ".cursor/skills/cover-text-excalibur-blog/SKILL.md",
        "shared/SOUL.md",
        "shared/lebedev-style.md",
        "shared/soul-examples",
        "shared/blog-cover-quad-canvas-contract.md",
        "scripts/excalibur_blog_quad_manifest.py",
        "scripts/excalibur_blog_cover_quad_prompt.py",
        "scripts/excalibur_blog_cover_quad_split.py",
        "scripts/excalibur_blog_quad_apply.py",
        "scripts/excalibur_blog_hero_reference_url.py",
        "scripts/excalibur_blog_writer_ready_gate.py",
        "scripts/excalibur_blog_content_evidence_gate.py",
        "scripts/excalibur_blog_slim_blog_topics.py",
        "scripts/excalibur_blog_contract_freshness.py",
        "agents/excalibur-blog-lead.md",
        "agents/excalibur-blog-article-editor.md",
        "agents/excalibur-blog-geo-qa.md",
        "agents/excalibur-blog-hook.md",
        "skills/lead-excalibur-blog/SKILL.md",
        "skills/article-editor-excalibur-blog/SKILL.md",
        "skills/excalibur-geo-qa/SKILL.md",
        "skills/hook-excalibur-blog/SKILL.md",
        "scripts/excalibur_blog_lead_meta_gate.py",
        "scripts/excalibur_blog_geo_qa_gate.py",
        "scripts/excalibur_blog_editor_choice_gate.py",
        "scripts/excalibur_blog_writer_finalize.py",
        "agents/excalibur-blog-writing-critic.md",
        "agents/excalibur-blog-reader-panel.md",
        "agents/excalibur-blog-glavred.md",
        "agents/excalibur-blog-visual-qa.md",
        "agents/excalibur-blog-thesis-editor.md",
        "agents/excalibur-blog-headline-director.md",
        "agents/excalibur-blog-metrika-analyst.md",
        "agents/excalibur-blog-policy-learner.md",
        "agents/excalibur-blog-voice-curator.md",
        "agents/excalibur-blog-reader-sim.md",
        "skills/excalibur/SKILL.md",
        "skills/excalibur-wp-publish/SKILL.md",
        "scripts/excalibur_blog_interlinker.py",
        "scripts/excalibur_blog_draft_meta_upsert.py",
        "scripts/excalibur_blog_editorial_swarm_gate.py",
        "scripts/excalibur_blog_visual_qa_gate.py",
        "scripts/excalibur_blog_content_experiments.py",
        "scripts/excalibur_blog_scorecard_coverage_report.py",
        "shared/golden-benchmark",
        "shared/editorial-swarm-contract.md",
        "shared/anti-template-contract.md",
        "shared/quality-blog.md",
        "shared/writer-operating-system.md",
        "shared/writer-brief-slim.md",
        "shared/agent-pipeline-pitfalls.md",
        "shared/pipeline-speed-contract.md",
        "shared/blog-visual-pipeline-contract.md",
        "shared/cover-hook-contract.md",
        "shared/mcp-image-async-contract.md",
        "shared/excalibur-blog-cover-index.md",
        "shared/editorial-read-bundle.md",
        "shared/editorial-utility-only.md",
        "shared/contract-freshness-contract.md",
        "shared/excalibur-blog-handoff.template.md",
        "shared/cloud-preflight-workflow.yml.example",
        "CURSOR-CLOUD-RUNBOOK.md",
        "CURSOR-CLOUD-AGENT-PIPELINE-FROM-SCRATCH.md",
        "SUBAGENTS.md",
        "memory/topics/blog-topics.md",
    )
    for rel in forbidden:
        report(not (root / rel).exists(), f"garbage removed: {rel}")

    report(
        not git_ls_files(root, "shared/excalibur-blog-handoff.md")
        and not git_ls_files(root, ".cursor/excalibur-blog-handoff.md")
        and not git_ls_files(root, ".cursor/excalibur-blog-fragments"),
        "runtime handoff not tracked",
    )

    env = merged_publish_env(root)
    report(bool(env.get("PUBLIC_SITE_URL") or env.get("WP_SITE_URL") or env.get("WP_HOME")), "site URL configured")
    report(bool(env.get("FTP_HOST")), "SFTP host configured")
    report(bool(env.get("FTP_USER")), "SFTP user configured")
    report(bool(env.get("FTP_PASS")), "SFTP password configured")
    ftp_root_raw = (env.get("FTP_ROOT") or "").strip()
    ftp_root_ok = (not ftp_root_raw) or ftp_root_raw in {".", "./", "/"}
    report(
        ftp_root_ok,
        "FTP_ROOT is '.' (or empty/slash); non-dot panel path -> ENOENT WARN + auto-fallback (set Cloud Secret FTP_ROOT=.)",
        warn=True,
    )
    if args.publish:
        report(env.get("EXCALIBUR_BLOG_ALLOW_PUBLISH", "").lower() == "yes", "EXCALIBUR_BLOG_ALLOW_PUBLISH=yes")

    # Dzen + RF canon must be readable before Scout
    rf_path = root / "shared/rf-blocked-entities.json"
    dzen_path = root / "shared/dzen-content-rules.md"
    if rf_path.is_file():
        try:
            rf = json.loads(rf_path.read_text(encoding="utf-8"))
            heroes = {h.get("id") for h in rf.get("hard_deny_heroes", [])}
            report(
                {"meta", "instagram", "facebook"}.issubset(heroes),
                "rf-blocked-entities has meta/instagram/facebook",
            )
        except json.JSONDecodeError:
            report(False, "rf-blocked-entities.json valid JSON")
    dzen_text = dzen_path.read_text(encoding="utf-8") if dzen_path.is_file() else ""
    report(
        "rules.html" in dzen_text and "Meta" in dzen_text and "Instagram" in dzen_text,
        "dzen-content-rules covers rules.html + Meta/Instagram",
    )
    print("NOTE read shared/dzen-content-rules.md + rf-blocked-entities.json BEFORE Scout")

    print(f"SUMMARY errors={len(errors)} warnings={len(warnings)}")
    if errors:
        print("ERRORS: " + "; ".join(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
