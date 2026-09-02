#!/usr/bin/env python3
"""Create, validate, and catalog an openAut technical-manual archive."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import yaml


DOCUMENT_TYPES = {
    "installation-manual",
    "engineering-manual",
    "operation-manual",
    "programming-manual",
    "service-manual",
    "datasheet",
    "protocol-reference",
    "wiring-diagram",
    "certificate",
    "other",
}
TRUST_LEVELS = {"untrusted", "quarantine", "verified", "superseded"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ArchiveError(ValueError):
    """Raised when archive content violates the contract."""


def archive_root(repo: Path) -> Path:
    """Return a canonical archive root, rejecting a missing root or any symlink boundary."""
    absolute = repo.absolute()
    try:
        mode = absolute.lstat().st_mode
    except OSError as exc:
        raise ArchiveError(f"archive root is not accessible: {absolute}: {exc}") from exc
    if stat.S_ISLNK(mode):
        raise ArchiveError(f"archive root must not be a symbolic link: {absolute}")
    if not stat.S_ISDIR(mode):
        raise ArchiveError(f"archive root is not a directory: {absolute}")
    return absolute.resolve(strict=True)


def safe_path(repo: Path, path: Path) -> Path:
    """Keep a path beneath repo and reject symlinks in every existing component."""
    root = archive_root(repo)
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ArchiveError(f"path escapes archive root: {candidate}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ArchiveError(f"cannot inspect archive path {current}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise ArchiveError(f"symbolic links are not allowed in the archive: {current}")

    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ArchiveError(f"resolved path escapes archive root: {candidate}")
    return candidate


def atomic_write_text(repo: Path, path: Path, text: str) -> None:
    """Write UTF-8 through a regular temporary file and atomically replace the target."""
    target = safe_path(repo, path)
    safe_path(repo, target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(repo, target.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.is_symlink() or not temporary.is_file():
            raise ArchiveError(f"temporary output is not a regular file: {temporary}")
        os.replace(temporary, target)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def atomic_copy(repo: Path, source: Path, destination: Path) -> None:
    """Copy source bytes to a temporary regular file, then atomically install them."""
    target = safe_path(repo, destination)
    safe_path(repo, target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(repo, target.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        if temporary.is_symlink() or not temporary.is_file():
            raise ArchiveError(f"temporary output is not a regular file: {temporary}")
        os.replace(temporary, target)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    result = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not result:
        raise ArchiveError(f"cannot derive an ID from {value!r}")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def product_parts(manufacturer: str, family: str, model: str) -> dict[str, str]:
    manufacturer_id = slug(manufacturer)
    family_id = slug(family)
    model_id = slug(model)
    return {
        "manufacturer": manufacturer.strip(),
        "manufacturer_id": manufacturer_id,
        "product_family": family.strip(),
        "product_family_id": family_id,
        "model": model.strip(),
        "model_id": model_id,
        "product_id": f"{manufacturer_id}.{family_id}.{model_id}",
    }


def product_directory(repo: Path, product: dict[str, str]) -> Path:
    return (
        repo
        / "manufacturers"
        / product["manufacturer_id"]
        / product["product_family_id"]
        / product["model_id"]
    )


def load_yaml(repo: Path, path: Path) -> dict[str, Any]:
    safe_path(repo, path)
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ArchiveError(f"{path}: cannot read YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchiveError(f"{path}: expected a YAML mapping")
    return value


def frontmatter(repo: Path, path: Path) -> tuple[dict[str, Any], str]:
    safe_path(repo, path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ArchiveError(f"{path}: cannot read Markdown: {exc}") from exc
    if not text.startswith("---\n"):
        raise ArchiveError(f"{path}: missing YAML frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ArchiveError(f"{path}: frontmatter is not closed")
    try:
        metadata = yaml.safe_load(text[4:marker])
    except yaml.YAMLError as exc:
        raise ArchiveError(f"{path}: invalid frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ArchiveError(f"{path}: frontmatter must be a mapping")
    return metadata, text[marker + 5 :]


def expected_product_yaml(product: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "openaut-product/v1",
        "product_id": product["product_id"],
        "manufacturer": product["manufacturer"],
        "manufacturer_id": product["manufacturer_id"],
        "product_family": product["product_family"],
        "product_family_id": product["product_family_id"],
        "model": product["model"],
        "model_id": product["model_id"],
        "aliases": [],
        "tags": [],
    }


def write_yaml(repo: Path, path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(repo, path, yaml.safe_dump(value, sort_keys=False, allow_unicode=True))


def ensure_product(repo: Path, product: dict[str, str]) -> Path:
    directory = product_directory(repo, product)
    safe_path(repo, directory)
    directory.mkdir(parents=True, exist_ok=True)
    safe_path(repo, directory)
    path = directory / "product.yaml"
    expected = expected_product_yaml(product)
    safe_path(repo, path)
    if path.exists() or path.is_symlink():
        actual = load_yaml(repo, path)
        for key in (
            "schema",
            "product_id",
            "manufacturer_id",
            "product_family_id",
            "model_id",
        ):
            if actual.get(key) != expected[key]:
                raise ArchiveError(f"{path}: existing {key} does not match requested product")
    else:
        write_yaml(repo, path, expected)
    return directory


def normalized_terms(values: list[str]) -> list[str]:
    return sorted({slug(value) for value in values if value.strip()})


def ingest(args: argparse.Namespace) -> Path:
    repo = archive_root(args.repo)
    source = args.source.resolve()
    markdown = args.markdown.resolve()
    if not source.is_file():
        raise ArchiveError(f"source does not exist: {source}")
    if not markdown.is_file():
        raise ArchiveError(f"converted Markdown does not exist: {markdown}")
    if args.document_type not in DOCUMENT_TYPES:
        raise ArchiveError(f"unsupported document type: {args.document_type}")
    if not LANGUAGE_RE.fullmatch(args.language):
        raise ArchiveError(f"invalid BCP 47 language tag: {args.language}")
    try:
        body = markdown.read_text(encoding="utf-8").lstrip("\ufeff\n")
    except (OSError, UnicodeError) as exc:
        raise ArchiveError(f"cannot read converted Markdown: {exc}") from exc
    if not body.strip():
        raise ArchiveError("converted Markdown is empty")

    product = product_parts(args.manufacturer, args.family, args.model)
    root = ensure_product(repo, product)
    document_number_id = slug(args.document_number)
    revision_id = slug(args.revision)
    language_path = args.language.lower()
    destination = safe_path(
        repo,
        root
        / "documents"
        / args.document_type
        / language_path
        / document_number_id
        / f"rev-{revision_id}",
    )
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"document revision already exists: {destination}")
    destination.mkdir(parents=True)
    safe_path(repo, destination)

    suffix = source.suffix.lower() or ".bin"
    stored_source = destination / f"source{suffix}"
    atomic_copy(repo, source, stored_source)
    source_hash = sha256_file(stored_source)
    document_id = ".".join(
        (
            product["product_id"],
            args.document_type,
            document_number_id,
            language_path,
            revision_id,
        )
    )
    metadata: dict[str, Any] = {
        "schema": "openaut-manual/v1",
        "document_id": document_id,
        "title": args.title or f"{product['manufacturer']} {product['model']} {args.document_type}",
        "product_id": product["product_id"],
        "manufacturer": product["manufacturer"],
        "product_family": product["product_family"],
        "model": product["model"],
        "document_type": args.document_type,
        "document_number": args.document_number,
        "revision": args.revision,
        "language": args.language,
        "protocols": normalized_terms(args.protocol),
        "tags": normalized_terms(args.tag),
        "source": {
            "original_filename": source.name,
            "stored_filename": stored_source.name,
            "media_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            "sha256": source_hash,
        },
        "conversion": {
            "method": args.conversion_method,
            "converted_at": date.today().isoformat(),
        },
        "trust_level": "quarantine",
    }
    rendered = "---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + "---\n\n" + body
    atomic_write_text(repo, destination / "manual.md", rendered)
    return destination / "manual.md"


def validate_product(repo: Path, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load_yaml(repo, path)
    except ArchiveError as exc:
        return [str(exc)]
    required = (
        "schema",
        "product_id",
        "manufacturer",
        "manufacturer_id",
        "product_family",
        "product_family_id",
        "model",
        "model_id",
    )
    for key in required:
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"{path}: missing or invalid {key}")
    if errors:
        return errors
    if data["schema"] != "openaut-product/v1":
        errors.append(f"{path}: unsupported schema {data['schema']!r}")
    expected_id = f"{data['manufacturer_id']}.{data['product_family_id']}.{data['model_id']}"
    if data["product_id"] != expected_id:
        errors.append(f"{path}: product_id must be {expected_id}")
    for key in ("manufacturer_id", "product_family_id", "model_id"):
        if not ID_RE.fullmatch(data[key]):
            errors.append(f"{path}: {key} must be a lowercase ASCII slug")
    expected_path = (
        Path("manufacturers")
        / data["manufacturer_id"]
        / data["product_family_id"]
        / data["model_id"]
        / "product.yaml"
    )
    if path.relative_to(repo) != expected_path:
        errors.append(f"{path}: path does not match product IDs")
    return errors


def validate_manual(repo: Path, path: Path) -> tuple[list[str], dict[str, Any] | None]:
    errors: list[str] = []
    try:
        data, body = frontmatter(repo, path)
    except ArchiveError as exc:
        return [str(exc)], None
    required_strings = (
        "schema",
        "document_id",
        "title",
        "product_id",
        "manufacturer",
        "product_family",
        "model",
        "document_type",
        "document_number",
        "revision",
        "language",
        "trust_level",
    )
    for key in required_strings:
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"{path}: missing or invalid {key}")
    if errors:
        return errors, data
    if data["schema"] != "openaut-manual/v1":
        errors.append(f"{path}: unsupported schema {data['schema']!r}")
    if data["document_type"] not in DOCUMENT_TYPES:
        errors.append(f"{path}: unsupported document_type {data['document_type']!r}")
    if data["trust_level"] not in TRUST_LEVELS:
        errors.append(f"{path}: unsupported trust_level {data['trust_level']!r}")
    if not LANGUAGE_RE.fullmatch(data["language"]):
        errors.append(f"{path}: invalid language tag {data['language']!r}")
    if not body.strip():
        errors.append(f"{path}: Markdown body is empty")
    for key in ("protocols", "tags"):
        terms = data.get(key)
        if not isinstance(terms, list) or any(
            not isinstance(term, str) or not ID_RE.fullmatch(term) for term in terms
        ):
            errors.append(f"{path}: {key} must be a list of lowercase ASCII slugs")
    conversion = data.get("conversion")
    if not isinstance(conversion, dict) or not isinstance(conversion.get("method"), str):
        errors.append(f"{path}: conversion.method is required")
    elif not isinstance(conversion.get("converted_at"), str):
        errors.append(f"{path}: conversion.converted_at must be an ISO date string")
    else:
        try:
            date.fromisoformat(conversion["converted_at"])
        except ValueError:
            errors.append(f"{path}: conversion.converted_at must be an ISO date string")

    product_tokens = data["product_id"].split(".")
    if len(product_tokens) != 3:
        errors.append(f"{path}: product_id must contain manufacturer.family.model")
        return errors, data
    product_path = repo / "manufacturers" / Path(*product_tokens) / "product.yaml"
    if not product_path.is_file():
        errors.append(f"{path}: missing product record {product_path}")
    else:
        try:
            product = load_yaml(repo, product_path)
        except ArchiveError as exc:
            errors.append(str(exc))
        else:
            for manual_key, product_key in (
                ("product_id", "product_id"),
                ("manufacturer", "manufacturer"),
                ("product_family", "product_family"),
                ("model", "model"),
            ):
                if data[manual_key] != product.get(product_key):
                    errors.append(f"{path}: {manual_key} does not match {product_path}")

    expected_document_id = ".".join(
        (
            data["product_id"],
            data["document_type"],
            slug(data["document_number"]),
            data["language"].lower(),
            slug(data["revision"]),
        )
    )
    if data["document_id"] != expected_document_id:
        errors.append(f"{path}: document_id must be {expected_document_id}")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append(f"{path}: source must be a mapping")
    else:
        stored_filename = source.get("stored_filename")
        expected_hash = source.get("sha256")
        if not isinstance(source.get("original_filename"), str):
            errors.append(f"{path}: source.original_filename is required")
        if not isinstance(source.get("media_type"), str):
            errors.append(f"{path}: source.media_type is required")
        if not isinstance(stored_filename, str) or Path(stored_filename).name != stored_filename:
            errors.append(f"{path}: invalid source.stored_filename")
        else:
            source_path = path.parent / stored_filename
            try:
                safe_path(repo, source_path)
            except ArchiveError as exc:
                errors.append(str(exc))
                source_path = None
            if source_path is None:
                pass
            elif not source_path.is_file():
                errors.append(f"{path}: missing stored source {source_path}")
            elif not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
                errors.append(f"{path}: invalid source.sha256")
            elif sha256_file(source_path) != expected_hash:
                errors.append(f"{path}: stored source SHA-256 mismatch")

    expected_path = Path(
        "manufacturers",
        *product_tokens,
        "documents",
        data["document_type"],
        data["language"].lower(),
        slug(data["document_number"]),
        f"rev-{slug(data['revision'])}",
        "manual.md",
    )
    if path.relative_to(repo) != expected_path:
        errors.append(f"{path}: path does not match document metadata")
    return errors, data


def inventory_archive(repo: Path) -> tuple[list[str], list[Path], list[Path]]:
    """Inventory all contract files without following symlinks."""
    errors: list[str] = []
    products: list[Path] = []
    manuals: list[Path] = []
    sources: list[Path] = []

    for current_name, directory_names, file_names in os.walk(repo, followlinks=False):
        current = Path(current_name)
        if current == repo and ".git" in directory_names:
            directory_names.remove(".git")
        for name in list(directory_names):
            path = current / name
            try:
                mode = path.lstat().st_mode
            except OSError as exc:
                errors.append(f"{path}: cannot inspect archive entry: {exc}")
                directory_names.remove(name)
                continue
            if stat.S_ISLNK(mode):
                errors.append(f"{path}: symbolic links are not allowed in the archive")
                directory_names.remove(name)
        for name in file_names:
            path = current / name
            try:
                mode = path.lstat().st_mode
            except OSError as exc:
                errors.append(f"{path}: cannot inspect archive entry: {exc}")
                continue
            if stat.S_ISLNK(mode):
                errors.append(f"{path}: symbolic links are not allowed in the archive")
                continue
            if not stat.S_ISREG(mode):
                errors.append(f"{path}: archive entries must be regular files")
                continue
            if name == "product.yaml":
                products.append(path)
            elif name == "manual.md":
                manuals.append(path)
            elif name.startswith("source."):
                sources.append(path)

    valid_products: list[Path] = []
    for path in sorted(products):
        parts = path.relative_to(repo).parts
        if len(parts) != 5 or parts[0] != "manufacturers" or parts[-1] != "product.yaml":
            errors.append(f"{path}: product.yaml is outside the required product path")
        else:
            valid_products.append(path)

    valid_manuals: list[Path] = []
    valid_revision_directories: set[Path] = set()
    for path in sorted(manuals):
        parts = path.relative_to(repo).parts
        if (
            len(parts) != 10
            or parts[0] != "manufacturers"
            or parts[4] != "documents"
            or parts[-1] != "manual.md"
        ):
            errors.append(f"{path}: manual.md is outside the required revision path")
            continue
        valid_manuals.append(path)
        valid_revision_directories.add(path.parent)
        try:
            entries = list(path.parent.iterdir())
        except OSError as exc:
            errors.append(f"{path.parent}: cannot inventory revision directory: {exc}")
            continue
        source_files = [entry for entry in entries if entry.name.startswith("source.") and entry.is_file()]
        if len(entries) != 2 or len(source_files) != 1:
            errors.append(
                f"{path.parent}: revision directory must contain exactly manual.md and one source file"
            )

    for source in sorted(sources):
        if source.parent not in valid_revision_directories:
            errors.append(f"{source}: source file has no correctly placed manual.md")

    return errors, valid_products, valid_manuals


def scan(repo: Path) -> tuple[list[str], list[tuple[Path, dict[str, Any]]]]:
    try:
        repo = archive_root(repo)
    except ArchiveError as exc:
        return [str(exc)], []
    errors, products, manuals = inventory_archive(repo)
    documents: list[tuple[Path, dict[str, Any]]] = []
    for product in products:
        errors.extend(validate_product(repo, product))
    seen: dict[str, Path] = {}
    for manual in manuals:
        manual_errors, data = validate_manual(repo, manual)
        errors.extend(manual_errors)
        if data is not None:
            document_id = data.get("document_id")
            if isinstance(document_id, str):
                if document_id in seen:
                    errors.append(f"{manual}: duplicate document_id also used by {seen[document_id]}")
                seen[document_id] = manual
            documents.append((manual, data))
    orphan_products = [p for p in products if not any(p.parent in m.parents for m, _ in documents)]
    errors.extend(f"{path}: product has no manual revisions" for path in orphan_products)
    return errors, documents


def build_catalog(repo: Path, documents: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    repo = archive_root(repo)
    product_paths = sorted((repo / "manufacturers").glob("*/*/*/product.yaml"))
    products = [
        load_yaml(repo, path) | {"path": path.relative_to(repo).as_posix()}
        for path in product_paths
    ]
    entries: list[dict[str, Any]] = []
    for path, metadata in documents:
        safe_path(repo, path)
        source_path = path.parent / metadata["source"]["stored_filename"]
        safe_path(repo, source_path)
        relative = path.relative_to(repo).as_posix()
        entries.append(
            {
                "document_id": metadata["document_id"],
                "product_id": metadata["product_id"],
                "title": metadata["title"],
                "document_type": metadata["document_type"],
                "document_number": metadata["document_number"],
                "revision": metadata["revision"],
                "language": metadata["language"],
                "protocols": metadata.get("protocols", []),
                "tags": metadata.get("tags", []),
                "trust_level": metadata["trust_level"],
                "path": relative,
                "source_path": source_path.relative_to(repo).as_posix(),
                "source_sha256": metadata["source"]["sha256"],
                "markdown_sha256": sha256_file(path),
                "forge_uri": f"forge://openaut/manuals/{relative}",
            }
        )
    return {
        "schema": "openaut-manual-catalog/v1",
        "generated_by": "manual-ingest/scripts/manual_archive.py",
        "products": products,
        "documents": entries,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    ingest_parser = commands.add_parser("ingest", help="add one converted manual revision")
    ingest_parser.add_argument("--repo", type=Path, required=True)
    ingest_parser.add_argument("--source", type=Path, required=True)
    ingest_parser.add_argument("--markdown", type=Path, required=True)
    ingest_parser.add_argument("--manufacturer", required=True)
    ingest_parser.add_argument("--family", required=True)
    ingest_parser.add_argument("--model", required=True)
    ingest_parser.add_argument("--document-type", required=True, choices=sorted(DOCUMENT_TYPES))
    ingest_parser.add_argument("--document-number", required=True)
    ingest_parser.add_argument(
        "--revision",
        required=True,
        help="manufacturer revision identifier, for example 2025-04; use 'unknown' only if unmarked",
    )
    ingest_parser.add_argument("--language", required=True)
    ingest_parser.add_argument("--title")
    ingest_parser.add_argument("--protocol", action="append", default=[])
    ingest_parser.add_argument("--tag", action="append", default=[])
    ingest_parser.add_argument("--conversion-method", default="ai-assisted")

    for name in ("validate", "catalog"):
        command = commands.add_parser(name)
        command.add_argument("--repo", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "ingest":
            path = ingest(args)
            print(path)
            return 0
        repo = archive_root(args.repo)
        errors, documents = scan(repo)
        if errors:
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
            return 1
        if args.command == "catalog":
            write_yaml(repo, repo / "catalog.yaml", build_catalog(repo, documents))
            print(repo / "catalog.yaml")
        else:
            print(f"validated {len(documents)} document revision(s)")
        return 0
    except ArchiveError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
