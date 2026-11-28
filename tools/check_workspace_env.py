#!/usr/bin/env python3
"""Verify local ~/.ENVS primary toolchains and ~/.PROJECTS <-> ~/work/ sync.

Non-destructive host-level check kept separate from tools/healthcheck.sh
(which inspects only tracked repository state). Never reads ~/.env or prints
secrets.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

WORK_REPO_PATTERN = re.compile(r"~/work/([A-Za-z0-9._-]+)")
GITHUB_URL_PATTERN = re.compile(
    r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?=[\s`|),]|$)"
)

PRIMARY_TOOLCHAIN_CHECKS: tuple[tuple[str, str], ...] = (
    ("python3", "python3 --version"),
    ("pyenv", "pyenv --version"),
    ("uv", "uv --version"),
    ("jupyter", "jupyter --version | head -n 2"),
    ("pytest", "pytest --version"),
    ("ruff", "ruff --version"),
    ("rustc", "rustc --version"),
    ("cargo", "cargo --version"),
    ("clippy", "cargo clippy --version"),
    ("rustfmt", "rustfmt --version"),
    ("go", "go version"),
    ("golangci-lint", "golangci-lint --version | head -n 1"),
    ("node", "node --version"),
    ("npm", "npm --version"),
    ("tsc", "tsc --version"),
    ("tsx", "tsx --version | head -n 1"),
    ("pnpm", "pnpm --version"),
)

SUSPICIOUS_SECRET_NAMES = frozenset({".env", ".secrect_key", "id_rsa", "id_ed25519"})


@dataclass
class CheckReport:
    oks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)


def normalize_github_slug(url: str) -> str | None:
    """Normalize HTTPS or SSH GitHub remote URL to lowercase `owner/repo`."""
    match = GITHUB_URL_PATTERN.search(url.strip())
    if not match:
        return None
    slug = match.group(1).removesuffix(".git")
    return slug.lower()


def parse_projects_registry(text: str) -> dict[str, set[str]]:
    """Return mapping of repo directory name -> set of normalized GitHub slugs."""
    repos: dict[str, set[str]] = {}
    for line in text.splitlines():
        names = WORK_REPO_PATTERN.findall(line)
        if not names:
            continue
        slugs = {
            slug
            for m in GITHUB_URL_PATTERN.finditer(line)
            if (slug := normalize_github_slug(m.group(0))) is not None
        }
        for name in names:
            repos.setdefault(name, set()).update(slugs)
    return repos


def read_git_origin(repo_dir: Path) -> str | None:
    """Return origin remote URL if `repo_dir` is a git checkout with origin."""
    if not (repo_dir / ".git").exists():
        return None
    proc = subprocess.run(
        ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def check_projects_sync(
    projects_file: Path,
    work_dir: Path,
    report: CheckReport,
    check_remotes: bool = True,
) -> None:
    """Check that ~/work/ directories and ~/.PROJECTS entries stay in sync."""
    if not projects_file.is_file():
        report.fail(f"missing projects registry: {projects_file}")
        return
    if not work_dir.is_dir():
        report.fail(f"missing work directory: {work_dir}")
        return

    registry = parse_projects_registry(projects_file.read_text(encoding="utf-8"))
    actual_dirs = sorted(
        p.name for p in work_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    actual_set = set(actual_dirs)
    registered_set = set(registry.keys())

    missing_in_registry = sorted(actual_set - registered_set)
    stale_in_registry = sorted(registered_set - actual_set)

    for name in missing_in_registry:
        report.fail(f"unregistered repo in {work_dir.name}/: {name} (update {projects_file.name})")
    for name in stale_in_registry:
        report.warn(f"stale entry in {projects_file.name}: ~/work/{name} does not exist")

    if not missing_in_registry and not stale_in_registry:
        report.ok(
            f"{projects_file.name} matches {len(actual_dirs)} directories under {work_dir}"
        )

    if not check_remotes:
        return

    for name in sorted(actual_set & registered_set):
        origin = read_git_origin(work_dir / name)
        if origin is None:
            continue
        actual_slug = normalize_github_slug(origin)
        recorded_slugs = registry.get(name, set())
        if actual_slug and recorded_slugs and actual_slug not in recorded_slugs:
            report.fail(
                f"remote mismatch for {name}: git origin={actual_slug}, "
                f"{projects_file.name}={sorted(recorded_slugs)}"
            )
        elif actual_slug and not recorded_slugs:
            report.warn(f"no GitHub URL recorded in {projects_file.name} for {name}")


def check_envs_layout(envs_dir: Path, report: CheckReport) -> bool:
    """Verify ~/.ENVS/ structure and ensure no secret files live inside it."""
    if not envs_dir.is_dir():
        report.fail(f"missing toolchain directory: {envs_dir}")
        return False

    env_sh = envs_dir / "env.sh"
    readme = envs_dir / "README.md"
    ok_layout = True

    if env_sh.is_file():
        report.ok(f"found {env_sh}")
    else:
        report.fail(f"missing {env_sh}")
        ok_layout = False

    if readme.is_file():
        report.ok(f"found {readme}")
    else:
        report.warn(f"missing {readme}")

    for child in envs_dir.iterdir():
        if child.name in SUSPICIOUS_SECRET_NAMES or child.name.startswith(".env."):
            report.fail(
                f"secret-like file inside {envs_dir}: {child.name} "
                "(secrets must stay exclusively in ~/.env)"
            )
            ok_layout = False

    return ok_layout


def check_primary_toolchains(envs_dir: Path, report: CheckReport) -> None:
    """Source ~/.ENVS/env.sh in a clean bash subshell and verify primary tools."""
    env_sh = envs_dir / "env.sh"
    if not env_sh.is_file():
        return

    for name, cmd in PRIMARY_TOOLCHAIN_CHECKS:
        script = f'set -euo pipefail; source "{env_sh}"; {cmd}'
        proc = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            first_line = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
            summary = first_line[0] if first_line else "ok"
            report.ok(f"{name}: {summary}")
        else:
            err = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
            detail = err[0] if err else f"exit {proc.returncode}"
            report.fail(f"{name}: unavailable ({detail})")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    home = Path.home()
    parser = argparse.ArgumentParser(
        description="Verify local ~/.ENVS primary toolchains and ~/.PROJECTS <-> ~/work/ sync."
    )
    parser.add_argument(
        "--envs-dir",
        type=Path,
        default=home / ".ENVS",
        help="Path to unified toolchain directory (default: ~/.ENVS).",
    )
    parser.add_argument(
        "--projects-file",
        type=Path,
        default=home / ".PROJECTS",
        help="Path to cross-repo registry file (default: ~/.PROJECTS).",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=home / "work",
        help="Path to workspace directory holding repos (default: ~/work).",
    )
    parser.add_argument(
        "--skip-toolchains",
        action="store_true",
        help="Skip invoking primary language binaries (only check layout and ~/.PROJECTS).",
    )
    parser.add_argument(
        "--skip-remotes",
        action="store_true",
        help="Skip git remote verification against ~/.PROJECTS.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    env_report = CheckReport()
    layout_ok = check_envs_layout(args.envs_dir, env_report)
    if layout_ok and not args.skip_toolchains:
        check_primary_toolchains(args.envs_dir, env_report)

    proj_report = CheckReport()
    check_projects_sync(
        args.projects_file,
        args.work_dir,
        proj_report,
        check_remotes=not args.skip_remotes,
    )

    for title, rep in (
        ("Local Toolchain Environment (~/.ENVS)", env_report),
        ("Workspace Registry (~/.PROJECTS <-> ~/work)", proj_report),
    ):
        print(f"\n== {title} ==")
        for msg in rep.oks:
            print(f"OK: {msg}")
        for msg in rep.warnings:
            print(f"WARN: {msg}")
        for msg in rep.failures:
            print(f"FAIL: {msg}")

    total_warnings = len(env_report.warnings) + len(proj_report.warnings)
    total_failures = len(env_report.failures) + len(proj_report.failures)
    print("\n== Summary ==")
    print(f"warnings: {total_warnings}")
    print(f"failures: {total_failures}")
    return 1 if total_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
