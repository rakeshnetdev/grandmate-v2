#!/usr/bin/env python3
"""Fail if any relative link or heading anchor in the public docs does not resolve.

Every `final_docs/...` link in `docs/` was dead for months — that directory is a submodule
on a private repository, so the links resolved on the author's machine and nowhere else.
Nothing caught it, because a broken Markdown link is invisible until a reader clicks it.
This is the cheap check that would have.

Scope is deliberately the *public* documentation only (`docs/`, `README.md`): those are
what a reviewer reads, and they are required to stand alone. External URLs are not fetched
— that would make CI depend on the network and on third-party uptime.

    uv run python scripts/check_doc_links.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = [REPO_ROOT / "docs", REPO_ROOT / "README.md"]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def anchor(heading: str) -> str:
    """GitHub's slug: lowercase, drop punctuation, spaces to hyphens."""
    slug = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", slug)


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        files.extend(sorted(target.rglob("*.md")) if target.is_dir() else [target])
    return files


def main() -> int:
    files = markdown_files()
    anchors = {f: {anchor(h) for h in HEADING.findall(f.read_text(encoding="utf-8"))} for f in files}
    failures: list[str] = []

    for path in files:
        rel = path.relative_to(REPO_ROOT)
        for match in LINK.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, anchor_part = target.partition("#")

            if file_part and not (path.parent / file_part).exists():
                failures.append(f"{rel}: broken path -> {target}")
                continue

            if not anchor_part:
                continue
            resolved = path if not file_part else (path.parent / file_part).resolve()
            known = next((a for f, a in anchors.items() if f.resolve() == resolved), None)
            # `known is None` means the anchor points into a file outside the checked set,
            # which is not something this check can verify — the path already resolved.
            if known is not None and anchor_part not in known:
                failures.append(f"{rel}: broken anchor -> {target}")

    if failures:
        print(f"{len(failures)} broken documentation link(s):\n", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"All relative links and anchors resolve across {len(files)} documentation files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
