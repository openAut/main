#!/usr/bin/env python3
"""Check that relative Markdown links resolve to files that exist.

Catches dangling links like a SKILL.md pointing at references/protocol.md or a
baseline pointing at docs/SUPPRESSION.md before those files exist. External
(http/https/mailto) and pure-anchor (#...) links are ignored. Exits non-zero on
any broken relative link.
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIX = ("http://", "https://", "mailto:", "#", "tel:", "forge://")


def check(md: pathlib.Path) -> list[str]:
    errs: list[str] = []
    for target in LINK.findall(md.read_text(encoding="utf-8", errors="replace")):
        t = target.strip()
        if not t or t.startswith(SKIP_PREFIX):
            continue
        path_part = t.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        resolved = (md.parent / path_part).resolve()
        if not resolved.exists():
            errs.append(f"broken link -> {target}")
    return errs


def main() -> int:
    failed = 0
    for md in sorted(REPO.rglob("*.md")):
        if ".git" in md.parts:
            continue
        errs = check(md)
        if errs:
            failed += 1
            rel = md.relative_to(REPO)
            for e in errs:
                print(f"FAIL {rel}: {e}")
    print(f"\n{failed} file(s) with broken links" if failed else "\nAll relative links resolve")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
