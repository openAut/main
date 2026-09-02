from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_skills", SCRIPT)
assert SPEC and SPEC.loader
validate_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_skills)


def write_skill(tmp_path: Path, frontmatter: str) -> Path:
    directory = tmp_path / "example-skill"
    directory.mkdir()
    path = directory / "SKILL.md"
    path.write_text(f"---\n{frontmatter}\n---\n\n# Example\n", encoding="utf-8")
    return path


def test_rejects_duplicate_permission_declarations(tmp_path: Path) -> None:
    path = write_skill(
        tmp_path,
        """name: example-skill
description: Example skill used for validator testing.
permissions:
  knowledge_only: true
metadata:
  openaut-permissions: '{"knowledge_only":true}'""",
    )
    errors = validate_skills.check(path)
    assert any("declare permissions exactly once" in error for error in errors)


def test_rejects_invalid_permission_json(tmp_path: Path) -> None:
    path = write_skill(
        tmp_path,
        """name: example-skill
description: Example skill used for validator testing.
metadata:
  openaut-permissions: '{invalid-json}'""",
    )
    errors = validate_skills.check(path)
    assert any("not valid JSON" in error for error in errors)


def test_rejects_permission_json_that_is_not_an_object(tmp_path: Path) -> None:
    path = write_skill(
        tmp_path,
        """name: example-skill
description: Example skill used for validator testing.
metadata:
  openaut-permissions: '[]'""",
    )
    errors = validate_skills.check(path)
    assert any("must decode to an object" in error for error in errors)
