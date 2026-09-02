from __future__ import annotations

import importlib.util
import os
import stat
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml
import pytest


SCRIPT = Path(__file__).parents[1] / "skills" / "manual-ingest" / "scripts" / "manual_archive.py"
SPEC = importlib.util.spec_from_file_location("manual_archive", SCRIPT)
assert SPEC and SPEC.loader
manual_archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manual_archive)


def ingest_args(repo: Path, source: Path, markdown: Path, **overrides: Any) -> Namespace:
    values = {
        "repo": repo,
        "source": source,
        "markdown": markdown,
        "manufacturer": "Siemens",
        "family": "Desigo PXC4",
        "model": "PXC4.E16",
        "document_type": "engineering-manual",
        "document_number": "A6V12345678",
        "revision": "2025-04",
        "language": "en",
        "title": None,
        "protocol": ["BACnet"],
        "tag": ["controller"],
        "conversion_method": "ai-assisted",
    }
    values.update(overrides)
    return Namespace(**values)


def ingest_example(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "manuals"
    repo.mkdir()
    source = tmp_path / "A6V12345678.pdf"
    source.write_bytes(b"example manual bytes")
    markdown = tmp_path / "converted.md"
    markdown.write_text("# Engineering manual\n\nRegister 1 is temperature.\n", encoding="utf-8")
    path = manual_archive.ingest(ingest_args(repo, source, markdown))
    return repo, path


def create_symlink_or_skip(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except NotImplementedError as exc:
        pytest.skip(f"symbolic links are unavailable in this test environment: {exc}")
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"symbolic links require an unavailable Windows privilege: {exc}")
        raise


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


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory modes do not apply on Windows")
def test_published_product_inherits_archive_directory_mode(tmp_path: Path) -> None:
    repo, manual = ingest_example(tmp_path)

    product_status = manual.parents[5].stat()
    parent_status = manual.parents[6].stat()
    assert stat.S_IMODE(product_status.st_mode) == stat.S_IMODE(parent_status.st_mode)
    assert product_status.st_gid == parent_status.st_gid


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
    create_symlink_or_skip(repo / "manufacturers", outside, directory=True)
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"source")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# Manual\n", encoding="utf-8")

    with pytest.raises(manual_archive.ArchiveError, match="links and reparse points"):
        manual_archive.ingest(ingest_args(repo, source, markdown, protocol=[], tag=[]))
    assert list(outside.iterdir()) == []


def test_catalog_rejects_symlink_without_touching_target(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    outside = tmp_path / "outside.yaml"
    outside.write_text("do not replace\n", encoding="utf-8")
    create_symlink_or_skip(repo / "catalog.yaml", outside)

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


def test_ingest_failure_leaves_no_partial_product_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "manuals"
    repo.mkdir()
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"source")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# Manual\n", encoding="utf-8")
    args = ingest_args(repo, source, markdown)
    original_publish = manual_archive.publish_no_replace

    def fail_publish(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(manual_archive, "publish_no_replace", fail_publish)
    with pytest.raises(OSError, match="simulated publish failure"):
        manual_archive.ingest(args)

    product = repo / "manufacturers" / "siemens" / "desigo-pxc4" / "pxc4-e16"
    assert not product.exists()
    assert list(tmp_path.glob(".manuals-manual-ingest-*")) == []

    monkeypatch.setattr(manual_archive, "publish_no_replace", original_publish)
    assert manual_archive.ingest(args).is_file()


def test_publish_no_replace_preserves_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "new.txt").write_text("new\n", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    marker = destination / "existing.txt"
    marker.write_text("existing\n", encoding="utf-8")

    with pytest.raises(manual_archive.ArchiveError, match="destination already exists"):
        manual_archive.publish_no_replace(source, destination)

    assert marker.read_text(encoding="utf-8") == "existing\n"
    assert (source / "new.txt").is_file()


def test_staging_setup_failure_is_cleaned_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "manuals"
    repo.mkdir()
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"source")
    markdown = tmp_path / "manual.md"
    markdown.write_text("# Manual\n", encoding="utf-8")

    def fail_chmod(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("simulated chmod failure")

    monkeypatch.setattr(manual_archive.os, "chmod", fail_chmod)
    with pytest.raises(OSError, match="simulated chmod failure"):
        manual_archive.ingest(ingest_args(repo, source, markdown))

    assert list(tmp_path.glob(".manuals-manual-ingest-*")) == []


def test_ingest_rejects_product_display_name_slug_collision(tmp_path: Path) -> None:
    repo, _ = ingest_example(tmp_path)
    source = tmp_path / "second.pdf"
    source.write_bytes(b"second source")
    markdown = tmp_path / "second.md"
    markdown.write_text("# Second manual\n", encoding="utf-8")

    with pytest.raises(manual_archive.ArchiveError, match="existing manufacturer"):
        manual_archive.ingest(
            ingest_args(
                repo,
                source,
                markdown,
                manufacturer="SIEMENS",
                revision="2025-05",
            )
        )


def test_existing_product_ingest_failure_leaves_no_partial_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = ingest_example(tmp_path)
    source = tmp_path / "second.pdf"
    source.write_bytes(b"second source")
    markdown = tmp_path / "second.md"
    markdown.write_text("# Second manual\n", encoding="utf-8")
    args = ingest_args(repo, source, markdown, revision="2025-05")
    original_copy = manual_archive.atomic_copy

    def fail_copy(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("simulated copy failure")

    monkeypatch.setattr(manual_archive, "atomic_copy", fail_copy)
    with pytest.raises(OSError, match="simulated copy failure"):
        manual_archive.ingest(args)

    revision = (
        repo
        / "manufacturers"
        / "siemens"
        / "desigo-pxc4"
        / "pxc4-e16"
        / "documents"
        / "engineering-manual"
        / "en"
        / "a6v12345678"
        / "rev-2025-05"
    )
    assert not revision.exists()
    assert list(tmp_path.glob(".manuals-manual-ingest-*")) == []

    monkeypatch.setattr(manual_archive, "atomic_copy", original_copy)
    assert manual_archive.ingest(args).is_file()
