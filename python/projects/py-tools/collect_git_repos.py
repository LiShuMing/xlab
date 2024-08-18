#!/usr/bin/env python3
"""
Recursively find Git repositories under a root directory and write a Markdown
file listing `git clone <remote-url>` commands (nested repos included).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class RepoInfo:
    """One discovered repository and its preferred clone URL."""

    path: Path
    clone_url: str | None
    remote_name: str | None


class GitRepoCollector:
    """Walk a filesystem tree and collect Git remote URLs for each repo root."""

    def __init__(
        self,
        root: Path,
        *,
        remote_preference: str = "origin",
        skip_hidden_dirs: bool = True,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.remote_preference = remote_preference
        self.skip_hidden_dirs = skip_hidden_dirs

    def _is_git_work_tree(self, path: Path) -> bool:
        git_entry = path / ".git"
        return git_entry.is_dir() or git_entry.is_file()

    def _git(self, repo: Path, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _remote_url(self, repo: Path, remote: str) -> str | None:
        r = self._git(repo, "remote", "get-url", remote)
        if r.returncode == 0:
            return r.stdout.strip() or None
        return None

    def _first_remote_name(self, repo: Path) -> str | None:
        r = self._git(repo, "remote")
        if r.returncode != 0:
            return None
        names = [line.strip() for line in r.stdout.splitlines() if line.strip()]
        return names[0] if names else None

    def clone_url_for(self, repo: Path) -> tuple[str | None, str | None]:
        """Return (url, remote_used). Tries preferred remote, then first listed remote."""
        url = self._remote_url(repo, self.remote_preference)
        if url:
            return url, self.remote_preference
        first = self._first_remote_name(repo)
        if first and first != self.remote_preference:
            u = self._remote_url(repo, first)
            if u:
                return u, first
        return None, None

    def iter_repo_roots(self) -> list[Path]:
        """Depth-first walk; skips `.git` directories; detects nested repos."""
        if not self.root.is_dir():
            return []

        found: list[Path] = []

        for dirpath, dirnames, _filenames in os.walk(self.root, topdown=True):
            p = Path(dirpath)

            if self.skip_hidden_dirs:
                # Do not descend into hidden segments (except root may be non-hidden).
                rel = p.relative_to(self.root)
                if any(part.startswith(".") for part in rel.parts):
                    dirnames[:] = []
                    continue

            if ".git" in dirnames:
                dirnames.remove(".git")

            if self._is_git_work_tree(p):
                found.append(p)

        # Stable, depth-first order already; sort by path for deterministic output.
        return sorted(found, key=lambda x: str(x).lower())

    def collect(self) -> list[RepoInfo]:
        repos = self.iter_repo_roots()
        out: list[RepoInfo] = []
        for path in repos:
            url, remote = self.clone_url_for(path)
            out.append(RepoInfo(path=path, clone_url=url, remote_name=remote))
        return out


def render_markdown(
    root: Path,
    items: list[RepoInfo],
    *,
    title: str | None = None,
) -> str:
    root_s = str(root)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = title or "Git repositories"

    lines: list[str] = [
        f"# {title}",
        "",
        f"- Root: `{root_s}`",
        f"- Generated: {when}",
        f"- Count: {len(items)}",
        "",
    ]

    for info in items:
        try:
            rel = info.path.relative_to(root)
            label = str(rel) if str(rel) != "." else "."
        except ValueError:
            label = str(info.path)

        lines.append(f"## `{label}`")
        lines.append("")
        if info.clone_url:
            lines.append("```bash")
            lines.append(f"git clone {info.clone_url}")
            lines.append("```")
            if info.remote_name:
                lines.append("")
                lines.append(f"_Remote: `{info.remote_name}`_")
        else:
            lines.append("_No remotes configured (or `git` failed)._")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect git clone commands for all repos under a directory tree.",
    )
    parser.add_argument(
        "-r",
        "--root",
        type=Path,
        default=Path("~/work"),
        help="Directory to scan (default: ~/work)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output Markdown file path",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Preferred remote name (default: origin)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Also descend into hidden directories (names starting with '.')",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Markdown H1 title (default: Git repositories)",
    )
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1

    collector = GitRepoCollector(
        root,
        remote_preference=args.remote,
        skip_hidden_dirs=not args.include_hidden,
    )
    try:
        items = collector.collect()
    except FileNotFoundError:
        print("error: `git` executable not found in PATH", file=sys.stderr)
        return 1

    md = render_markdown(collector.root, items, title=args.title)
    args.output = args.output.expanduser()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote {len(items)} repos to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
