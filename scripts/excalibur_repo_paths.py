"""Repo-relative paths for JSON reports (no local usernames in git)."""

from __future__ import annotations

from pathlib import Path


def project_root_from(anchor: Path) -> Path:
    return anchor.resolve().parents[1]


def resolve_article_dir(path: Path | str, root: Path) -> Path:
    """Resolve ``--article-dir`` for gate/CLI scripts.

    - absolute → as-is
    - bare ``.`` / empty → ``Path.cwd()`` (INC-20260730-0313: ``root / Path('.')``
      collapses to the project root and looks for ``schema.jsonld`` there)
    - other relative → ``root / path`` (canonical agent usage from repo root)
    """
    p = Path(path)
    if p.is_absolute():
        return p
    if str(p) in (".", "") or p.parts == (".",):
        return Path.cwd().resolve()
    return (root / p).resolve()


def repo_relative(path: Path, root: Path | None = None) -> str:
    p = path.resolve()
    base = (root or project_root_from(Path(__file__))).resolve()
    try:
        return p.relative_to(base).as_posix()
    except ValueError:
        return p.as_posix()


def resolve_article_output(
    output: Path | str | None,
    *,
    article_dir: Path,
    root: Path,
    default_name: str,
) -> Path:
    """Resolve gate ``-o`` without nesting under ``article_dir``.

    Canonical agent usage is a bare filename (``schema-gate.json``,
    ``freshness-report.json``) → written under ``article_dir``.

    Agents sometimes pass a repo-relative path
    (``memory/blog/articles/Bxx-slug/schema-gate.json``). Joining that against
    ``article_dir`` nests a second ``memory/blog/...`` tree
    (INC-20260726-0813). Multi-component relative paths that already land under
    ``article_dir`` when resolved from ``root`` use the root join instead.
    """
    if output is None or str(output).strip() == "":
        return article_dir / default_name
    p = Path(output)
    if p.is_absolute():
        return p
    if len(p.parts) == 1:
        return article_dir / p
    via_root = (root / p).resolve()
    article_resolved = article_dir.resolve()
    try:
        via_root.relative_to(article_resolved)
        return via_root
    except ValueError:
        return (article_dir / p).resolve()
