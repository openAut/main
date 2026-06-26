#!/usr/bin/env python3
"""Validate every skills/*/SKILL.md against the permissions schema.

Simple and strict. See docs/PERMISSIONS.md for the contract. Exits non-zero on
any violation so CI can gate on it.
"""
from __future__ import annotations

import pathlib
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required: pip install pyyaml\n")
    sys.exit(2)

ALLOWED_KEYS = {
    "knowledge_only", "tools", "exec", "network", "files", "credentials",
    "control_writes", "delegated_capabilities", "data_access", "external_services",
    "serial", "data_sensitivity",
}

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def _none(perms: dict, key: str) -> bool:
    """True if key is absent or its value is the string 'none'."""
    v = perms.get(key)
    return v is None or (isinstance(v, str) and v.strip().lower() == "none")


def check(md: pathlib.Path) -> list[str]:
    errs: list[str] = []
    raw = md.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        errs.append("file has a UTF-8 BOM before the frontmatter")
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    if not text.startswith("---"):
        return errs + ["no YAML frontmatter (must start with '---')"]
    try:
        end = text.index("\n---", 3)
    except ValueError:
        return errs + ["frontmatter is not closed with '---'"]
    try:
        fm = yaml.safe_load(text[3:end])
    except yaml.YAMLError as e:
        return errs + [f"frontmatter is not valid YAML: {e}"]
    if not isinstance(fm, dict):
        return errs + ["frontmatter did not parse to a mapping"]

    for key in ("name", "description"):
        v = fm.get(key)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"missing or empty '{key}'")

    perms = fm.get("permissions")
    if not isinstance(perms, dict):
        return errs + ["missing 'permissions' mapping"]

    ko = perms.get("knowledge_only")
    if not isinstance(ko, bool):
        errs.append("'permissions.knowledge_only' must be present and boolean")

    for k in perms:
        if k not in ALLOWED_KEYS:
            errs.append(f"unknown permissions key '{k}' (see docs/PERMISSIONS.md)")
    for k, v in perms.items():
        if not isinstance(v, (str, bool)):
            errs.append(f"permissions.{k} must be a string or bool")

    if ko is True:
        acting = not (_none(perms, "exec") and _none(perms, "network") and _none(perms, "tools"))
        if acting and not perms.get("delegated_capabilities"):
            errs.append(
                "knowledge_only: true but exec/network/tools are not 'none' and no "
                "'delegated_capabilities' is declared"
            )
    elif ko is False:
        if all(_none(perms, k) for k in ("exec", "network", "files")):
            errs.append(
                "knowledge_only: false but no capability declared "
                "(need at least one of exec/network/files != none)"
            )

    cw = perms.get("control_writes")
    if isinstance(cw, str) and cw.strip().lower() != "none" and "owner-confirmed" not in cw.lower():
        errs.append("control_writes must be 'none' or contain 'owner-confirmed'")

    return errs


def main() -> int:
    if not SKILLS.is_dir():
        sys.stderr.write(f"no skills/ directory at {SKILLS}\n")
        return 2
    failed = 0
    for md in sorted(SKILLS.glob("*/SKILL.md")):
        errs = check(md)
        rel = md.relative_to(REPO)
        if errs:
            failed += 1
            for e in errs:
                print(f"FAIL {rel}: {e}")
        else:
            print(f"ok   {rel}")
    print(f"\n{failed} skill(s) failed validation" if failed else "\nAll skills valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
