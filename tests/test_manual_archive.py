from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path

import yaml
import pytest


SCRIPT = Path(__file__).parents[1] / "skills" / "manual-ingest" / "scripts" / "manual_archive.py"
SPEC = importlib.util.spec_from_file_location("manual_archive", SCRIPT)
assert SPEC and SPEC.loader
manual_archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manual_archive)


def ingest_example(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "manuals"
    repo.mkdir()
    source = tmp_path / "A6V12345678.pdf"
    source.write_bytes(b"example manual bytes")
    markdown = tmp_path / "converted.md"
    markdown.write_text("# Engineering manual\n\nRegister 1 is temperature.\n", encoding="utf-8")
    path = manual_archive.ingest(
        Namespace(
            repo=repo,
            source=source,
            markdown=markdown,
            manufacturer="Siemens",
            family="Desigo PXC4",
            model="PXC4.E16",
            document_type="engineering-manual",
            document_number="A6V12345678",
            revision="2025-04",
            language="en",
            title=None,
            protocol=["BACnet"],
            tag=["controller"],
            conversion_method="ai-assisted",
        )
    )
    return repo, path


def test_ingest_validate_and_catalog(tmp_path: Path) -> None:
    repo, manual = ingest_example(tmp_path)
    errors, documents = manual_archive.scan(repo)
    assert errors == []
    assert len(documents) == 1
    assert "trust_level: quarantine" in manual.read_text(encoding="utf-8")

    catalog = manual_archive.build_catalog(repo, documents)
    assert catalog["products"][0]["product_id"] == "siemens.desigo-pxc4.pxc4-e16"
    assert catalog["documents"][0]["protocols"] == ["bacnet"]
    assert catalog["documents"][0]["forge_uri"].startswith("forge://openaut/manuals/")


def test_source_tampering_is_detected(tmp_path: Path) -> None:
    repo, manual = ingest_example(tmp_path)
    metadata, _ = manual_archive.frontmatter(repo, manual)
    (manual.parent / metadata["source"]["stored_filename"]).write_bytes(b"changed")
    errors, _ = manual_archive.scan(repo)
    assert any("SHA-256 mismatch" in error for error in errors)


def test_catalog_is_serializable_yaml(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    errors, documents = manual_archive.scan(repo)
    assert errors == []
    rendered = yaml.safe_dump(manual_archive.build_catalog(repo, documents), sort_keys=False)
    loaded = yaml.safe_load(rendered)
    assert loaded["schema"] == "openaut-manual-catalog/v1"


def test_cli_validate_and_catalog(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    assert manual_archive.main(["validate", "--repo", str(repo)]) == 0
    assert manual_archive.main(["catalog", "--repo", str(repo)]) == 0
    catalog = yaml.safe_load((repo / "catalog.yaml").read_text(encoding="utf-8"))
    assert len(catalog["documents"]) == 1


def test_ingest_rejects_manufacturers_directory_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "manuals"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "manufacturers").symlink_to(outside, target_is_directory=True)
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"source")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# Manual\n", encoding="utf-8")

    with pytest.raises(manual_archive.ArchiveError, match="symbolic links"):
        manual_archive.ingest(
            Namespace(
                repo=repo,
                source=source,
                markdown=markdown,
                manufacturer="Siemens",
                family="Desigo PXC4",
                model="PXC4.E16",
                document_type="engineering-manual",
                document_number="A6V12345678",
                revision="2025-04",
                language="en",
                title=None,
                protocol=[],
                tag=[],
                conversion_method="ai-assisted",
            )
        )
    assert list(outside.iterdir()) == []


def test_catalog_rejects_symlink_without_touching_target(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    outside = tmp_path / "outside.yaml"
    outside.write_text("do not replace\n", encoding="utf-8")
    (repo / "catalog.yaml").symlink_to(outside)

    assert manual_archive.main(["catalog", "--repo", str(repo)]) == 1
    assert outside.read_text(encoding="utf-8") == "do not replace\n"
    assert (repo / "catalog.yaml").is_symlink()


def test_scan_reports_misplaced_contract_file(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    misplaced = repo / "manufacturers" / "siemens" / "manual.md"
    misplaced.write_text("# Misplaced\n", encoding="utf-8")

    errors, _ = manual_archive.scan(repo)
    assert any("outside the required revision path" in error for error in errors)


def test_scan_rejects_extra_revision_file(tmp_path: Path) -> None:
    repo, manual = ingest_example(tmp_path)
    (manual.parent / "notes.txt").write_text("unexpected", encoding="utf-8")

    errors, _ = manual_archive.scan(repo)
    assert any("must contain exactly manual.md and one source file" in error for error in errors)
