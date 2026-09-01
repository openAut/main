from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path

import yaml


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
    metadata, _ = manual_archive.frontmatter(manual)
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
