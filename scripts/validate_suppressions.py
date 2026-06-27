#!/usr/bin/env python3
"""Enforce the SkillSpector baseline policy (docs/SUPPRESSION.md).

A suppression is only acceptable if it is a reviewed false positive with a
concrete reason. This check fails CI on the ways a baseline can quietly rot:
generic/placeholder reasons, missing reasons, duplicate fingerprints, and broad
glob `rules` without a concrete justification. It does NOT decide whether a
finding is a true or false positive — that is the human reviewer's job; it
keeps the recorded justification honest and auditable.
"""
from __future__ import annotations

import pathlib
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required: pip install pyyaml\n")
    sys.exit(2)

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"

# Placeholder reasons that are not real justifications.
GENERIC = (
    "auto-generated baseline",
    "accepted finding (auto-generated",
)
MIN_REASON_LEN = 12


def _bad_reason(reason) -> str | None:
    if not isinstance(reason, str) or not reason.strip():
        return "missing reason"
    low = reason.strip().lower()
    for g in GENERIC:
        if g in low:
            return f"generic/placeholder reason ({reason!r})"
    if len(reason.strip()) < MIN_REASON_LEN:
        return f"reason too short to be a justification ({reason!r})"
    return None


def check(bl: pathlib.Path) -> list[str]:
    errs: list[str] = []
    try:
        data = yaml.safe_load(bl.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"not valid YAML: {e}"]
    if not isinstance(data, dict):
        return ["baseline did not parse to a mapping"]

    # Broad glob rules must carry their own concrete reason.
    rules = data.get("rules") or []
    if isinstance(rules, list):
        for i, r in enumerate(rules):
            if not isinstance(r, dict):
                errs.append(f"rules[{i}] is not a mapping")
                continue
            bad = _bad_reason(r.get("reason"))
            if bad:
                errs.append(f"glob rule {r.get('pattern', i)}: {bad}")
    else:
        errs.append("'rules' must be a list")

    seen: set[tuple] = set()
    fps = data.get("fingerprints") or []
    if not isinstance(fps, list):
        return errs + ["'fingerprints' must be a list"]
    for i, fp in enumerate(fps):
        if not isinstance(fp, dict):
            errs.append(f"fingerprints[{i}] is not a mapping")
            continue
        for req in ("hash", "rule_id", "file"):
            if not fp.get(req):
                errs.append(f"fingerprints[{i}] missing '{req}'")
        key = (fp.get("hash"), fp.get("rule_id"), fp.get("file"))
        if key in seen:
            errs.append(f"duplicate fingerprint {key}")
        seen.add(key)
        bad = _bad_reason(fp.get("reason"))
        if bad:
            errs.append(f"{fp.get('file')} [{fp.get('rule_id')}]: {bad}")
    return errs


def main() -> int:
    baselines = sorted(SKILLS.glob("*/.skillspector-baseline.yaml"))
    if not baselines:
        print("No baselines to check")
        return 0
    failed = 0
    for bl in baselines:
        errs = check(bl)
        rel = bl.relative_to(REPO)
        if errs:
            failed += 1
            for e in errs:
                print(f"FAIL {rel}: {e}")
        else:
            print(f"ok   {rel}")
    print(f"\n{failed} baseline(s) failed policy" if failed else "\nAll baselines comply with docs/SUPPRESSION.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
