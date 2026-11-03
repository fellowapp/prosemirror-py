"""Post or update a PR comment when total coverage differs from the base branch.

Usage: coverage_comment.py HEAD_JSON BASE_JSON PR_NUMBER

Both inputs are ``coverage json`` reports. The comment is created only when the
total changes, updated in place on later pushes, and never fails the build: a
coverage drop is reported, not enforced. Needs ``gh`` with ``GH_TOKEN`` and
``GITHUB_REPOSITORY`` in the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MARKER = "<!-- coverage-delta-comment -->"


def load(path: Path) -> tuple[float, dict[str, float]]:
    data = json.loads(path.read_text())
    files = {
        name: info["summary"]["percent_covered"] for name, info in data["files"].items()
    }
    return data["totals"]["percent_covered"], files


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def delta(value: float) -> str:
    return f"{value:+.2f}%"


def build_body(
    base_total: float,
    head_total: float,
    base_files: dict[str, float],
    head_files: dict[str, float],
) -> str:
    lines = [
        MARKER,
        f"### Coverage: {pct(base_total)} → {pct(head_total)} "
        f"({delta(head_total - base_total)})",
        "",
    ]
    rows = []
    for name in sorted(set(base_files) | set(head_files)):
        base = base_files.get(name)
        head = head_files.get(name)
        if base is None:
            change = "new file"
        elif head is None:
            change = "removed"
        elif round(head - base, 2) == 0:
            continue
        else:
            change = delta(head - base)
        rows.append(f"| `{name}` | {pct(base)} | {pct(head)} | {change} |")
    if rows:
        lines += ["| File | Base | PR | Change |", "|---|---|---|---|", *rows]
    return "\n".join(lines)


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def find_comment(repo: str, pr: str) -> str | None:
    ids = gh(
        "api",
        "--paginate",
        f"repos/{repo}/issues/{pr}/comments",
        "--jq",
        f'.[] | select(.body | contains("{MARKER}")) | .id',
    ).split()
    return ids[0] if ids else None


def main() -> None:
    head_path, base_path, pr = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    repo = os.environ["GITHUB_REPOSITORY"]
    if not base_path.exists():
        print("No base coverage report; skipping comment.")
        return

    head_total, head_files = load(head_path)
    base_total, base_files = load(base_path)
    changed = round(head_total - base_total, 2) != 0
    existing = find_comment(repo, pr)

    if changed:
        body = build_body(base_total, head_total, base_files, head_files)
    elif existing:
        body = f"{MARKER}\n### Coverage: unchanged at {pct(head_total)}"
    else:
        print(f"Coverage unchanged at {pct(head_total)}; no comment needed.")
        return

    if existing:
        gh(
            "api",
            "-X",
            "PATCH",
            f"repos/{repo}/issues/comments/{existing}",
            "-f",
            f"body={body}",
        )
        print(f"Updated comment {existing}.")
    else:
        gh(
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{pr}/comments",
            "-f",
            f"body={body}",
        )
        print("Created comment.")


if __name__ == "__main__":
    main()
