#!/usr/bin/env python3
"""Create, validate, and catalog an openAut technical-manual archive."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import shutil
import sys
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


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ArchiveError(f"{path}: cannot read YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchiveError(f"{path}: expected a YAML mapping")
    return value


def frontmatter(path: Path) -> tuple[dict[str, Any], str]:
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


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def ensure_product(repo: Path, product: dict[str, str]) -> Path:
    directory = product_directory(repo, product)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "product.yaml"
    expected = expected_product_yaml(product)
    if path.exists():
        actual = load_yaml(path)
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
        write_yaml(path, expected)
    return directory


def normalized_terms(values: list[str]) -> list[str]:
    return sorted({slug(value) for value in values if value.strip()})


def ingest(args: argparse.Namespace) -> Path:
    repo = args.repo.resolve()
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
    destination = (
        root
        / "documents"
        / args.document_type
        / language_path
        / document_number_id
        / f"rev-{revision_id}"
    )
    if destination.exists():
        raise ArchiveError(f"document revision already exists: {destination}")
    destination.mkdir(parents=True)

    suffix = source.suffix.lower() or ".bin"
    stored_source = destination / f"source{suffix}"
    shutil.copyfile(source, stored_source)
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
    (destination / "manual.md").write_text(rendered, encoding="utf-8")
    return destination / "manual.md"


def validate_product(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = load_yaml(path)
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
    expected_path = Path(data["manufacturer_id"]) / data["product_family_id"] / data["model_id"] / "product.yaml"
    if Path(*path.parts[-4:]) != expected_path:
        errors.append(f"{path}: path does not match product IDs")
    return errors


def validate_manual(repo: Path, path: Path) -> tuple[list[str], dict[str, Any] | None]:
    errors: list[str] = []
    try:
        data, body = frontmatter(path)
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
            product = load_yaml(product_path)
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
        stored = source.get("stored_filename")
        expected_hash = source.get("sha256")
        if not isinstance(source.get("original_filename"), str):
            errors.append(f"{path}: source.original_filename is required")
        if not isinstance(source.get("media_type"), str):
            errors.append(f"{path}: source.media_type is required")
        if not isinstance(stored, str) or Path(stored).name != stored:
            errors.append(f"{path}: invalid source.stored_filename")
        else:
            source_path = path.parent / stored
            if not source_path.is_file():
                errors.append(f"{path}: missing stored source {source_path}")
            elif not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
                errors.append(f"{path}: invalid source.sha256")
            elif sha256_file(source_path) != expected_hash:
                errors.append(f"{path}: stored source SHA-256 mismatch")

    expected_suffix = Path(
        data["document_type"],
        data["language"].lower(),
        slug(data["document_number"]),
        f"rev-{slug(data['revision'])}",
        "manual.md",
    )
    if Path(*path.parts[-5:]) != expected_suffix:
        errors.append(f"{path}: path does not match document metadata")
    return errors, data


def scan(repo: Path) -> tuple[list[str], list[tuple[Path, dict[str, Any]]]]:
    errors: list[str] = []
    documents: list[tuple[Path, dict[str, Any]]] = []
    products = sorted((repo / "manufacturers").glob("*/*/*/product.yaml"))
    manuals = sorted((repo / "manufacturers").glob("*/*/*/documents/*/*/*/*/manual.md"))
    for product in products:
        errors.extend(validate_product(product))
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
    product_paths = sorted((repo / "manufacturers").glob("*/*/*/product.yaml"))
    products = [load_yaml(path) | {"path": path.relative_to(repo).as_posix()} for path in product_paths]
    entries: list[dict[str, Any]] = []
    for path, metadata in documents:
        source_path = path.parent / metadata["source"]["stored_filename"]
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
    ingest_parser.add_argument("--revision", required=True)
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
        repo = args.repo.resolve()
        errors, documents = scan(repo)
        if errors:
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
            return 1
        if args.command == "catalog":
            write_yaml(repo / "catalog.yaml", build_catalog(repo, documents))
            print(repo / "catalog.yaml")
        else:
            print(f"validated {len(documents)} document revision(s)")
        return 0
    except ArchiveError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
