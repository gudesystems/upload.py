#!/usr/bin/env python3
"""
Bump the next dev release version based on existing git tags.

Tag format: vX.Y.Z-dev
Behavior:
- Finds highest existing dev tag and increments patch by one.
- Updates pyproject.toml version to X.Y.Z.dev0 (PEP 440).
- Updates WebUI sidebar version text in webui/index.html to X.Y.Z-dev.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


DEV_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-dev$")
BASE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def run_git_tags(repo_root: Path) -> list[str]:
    out = subprocess.check_output(["git", "tag"], cwd=repo_root, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def next_base_version_from_tags(tags: list[str]) -> str:
    found: list[tuple[int, int, int]] = []
    for tag in tags:
        m = DEV_TAG_RE.match(tag)
        if not m:
            continue
        found.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))

    if not found:
        return "0.0.1"

    major, minor, patch = max(found)
    return f"{major}.{minor}.{patch + 1}"


def update_pyproject(pyproject_path: Path, pyproject_version: str) -> bool:
    text = pyproject_path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'(?m)^version\s*=\s*"[^"]+"',
        f'version = "{pyproject_version}"',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not find project version line in pyproject.toml")
    if new_text == text:
        return False
    pyproject_path.write_text(new_text, encoding="utf-8")
    return True


def update_index_html(index_path: Path, ui_version: str) -> bool:
    text = index_path.read_text(encoding="utf-8")
    pattern = r'(<div class="fs-10 text-700">Version:\s*)([^<]+)(</div>)'
    new_text, count = re.subn(
        pattern,
        r"\g<1>" + ui_version + r"\g<3>",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not find sidebar version line in webui/index.html")
    if new_text == text:
        return False
    index_path.write_text(new_text, encoding="utf-8")
    return True


def set_output(name: str, value: str, output_file: Path | None) -> None:
    print(f"{name}={value}")
    if output_file is None:
        return
    with output_file.open("a", encoding="utf-8") as fh:
        fh.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump dev version and update files.")
    parser.add_argument(
        "--base-version",
        help="Use explicit X.Y.Z instead of auto-incrementing from tags.",
    )
    parser.add_argument(
        "--github-output",
        help="Path to GITHUB_OUTPUT file to write step outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print computed versions, do not modify files.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    pyproject_path = repo_root / "pyproject.toml"
    index_path = repo_root / "webui" / "index.html"
    output_file = Path(args.github_output) if args.github_output else None

    if args.base_version:
        if not BASE_VERSION_RE.match(args.base_version):
            raise ValueError("--base-version must match X.Y.Z")
        base_version = args.base_version
    else:
        tags = run_git_tags(repo_root)
        base_version = next_base_version_from_tags(tags)

    ui_version = f"{base_version}-dev"
    pyproject_version = f"{base_version}.dev0"
    tag = f"v{ui_version}"

    if not args.dry_run:
        update_pyproject(pyproject_path, pyproject_version)
        update_index_html(index_path, ui_version)

    set_output("base_version", base_version, output_file)
    set_output("ui_version", ui_version, output_file)
    set_output("pyproject_version", pyproject_version, output_file)
    set_output("tag", tag, output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

