#!/usr/bin/env python3
"""Fail-closed validation for a staged IOT2050 deployment bundle."""
from __future__ import annotations

import hashlib
import importlib.util
import ipaddress
import re
import sys
from pathlib import Path

EXPECTED_FILES = {"points.json", "edge.env", "ca.crt", "node.crt", "node.key"}
EXPECTED_ENV = {
    "EMQX_HOST",
    "EMQX_TLS_PORT",
    "OPENAUT_POINTS",
    "OPENAUT_CERT_DIR",
    "OPENAUT_SPOOL",
    "OPENAUT_SPOOL_MAX_ROWS",
    "OPENAUT_MQTT_MAX_INFLIGHT",
    "OPENAUT_READY_FILE",
}
FIXED_ENV = {
    "OPENAUT_POINTS": "/etc/openaut/current/points.json",
    "OPENAUT_CERT_DIR": "/etc/openaut/current/certs",
    "OPENAUT_SPOOL": "/var/lib/openaut/spool.sqlite",
    "OPENAUT_READY_FILE": "/var/lib/openaut/mqtt.ready",
}
HOSTNAME = re.compile(
    r"(?=.{1,253}\Z)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*",
    flags=re.ASCII,
)
MANIFEST_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", flags=re.ASCII)


def load_edge_agent(release_dir: Path):
    path = release_dir / "scripts" / "edge_agent.py"
    spec = importlib.util.spec_from_file_location("openaut_edge_agent_bundle", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load edge_agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_manifest(config_dir: Path):
    actual_files = {path.name for path in config_dir.iterdir()}
    if actual_files != EXPECTED_FILES | {"manifest.sha256"}:
        raise ValueError("deployment directory must contain exactly five files plus manifest.sha256")
    manifest = config_dir / "manifest.sha256"
    if not manifest.is_file():
        raise ValueError("deployment bundle is missing manifest.sha256")
    entries = {}
    for raw_line in manifest.read_text(encoding="ascii").splitlines():
        match = MANIFEST_LINE.fullmatch(raw_line)
        if match is None:
            raise ValueError("manifest.sha256 contains a non-canonical line")
        digest, filename = match.groups()
        if filename in entries:
            raise ValueError(f"manifest.sha256 repeats {filename}")
        entries[filename] = digest
    if set(entries) != EXPECTED_FILES:
        raise ValueError("manifest.sha256 must name exactly the five deployment files")
    for filename, expected in entries.items():
        path = config_dir / filename
        if not path.is_file():
            raise ValueError(f"deployment bundle is missing {filename}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch for {filename}")


def parse_env(path: Path):
    values = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"edge.env line {line_number} is not KEY=VALUE")
        key, value = line.split("=", 1)
        if key not in EXPECTED_ENV or key in values or not value or value != value.strip():
            raise ValueError(f"edge.env line {line_number} is invalid or duplicated")
        values[key] = value
    if set(values) != EXPECTED_ENV:
        raise ValueError("edge.env must define exactly the approved environment keys")
    if values["EMQX_HOST"] == "broker.example.invalid":
        raise ValueError("edge.env still contains the example broker")
    try:
        ipaddress.ip_address(values["EMQX_HOST"])
    except ValueError:
        if HOSTNAME.fullmatch(values["EMQX_HOST"]) is None:
            raise ValueError("EMQX_HOST is not a canonical IP address or DNS hostname") from None
    port = int(values["EMQX_TLS_PORT"])
    if not 1 <= port <= 65535:
        raise ValueError("EMQX_TLS_PORT must be between 1 and 65535")
    for key in ("OPENAUT_SPOOL_MAX_ROWS", "OPENAUT_MQTT_MAX_INFLIGHT"):
        if int(values[key]) <= 0:
            raise ValueError(f"{key} must be positive")
    for key, expected in FIXED_ENV.items():
        if values[key] != expected:
            raise ValueError(f"{key} must be {expected}")


def verify_bundle(config_dir: Path, release_dir: Path):
    if not config_dir.is_dir() or not release_dir.is_dir():
        raise ValueError("CONFIG_DIR and RELEASE_DIR must be directories")
    verify_manifest(config_dir)
    parse_env(config_dir / "edge.env")
    edge_agent = load_edge_agent(release_dir)
    config = edge_agent.load_config(config_dir / "points.json")
    return f"{config['site']}/{config['node']}"


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: verify_bundle.py CONFIG_DIR RELEASE_DIR")
    try:
        identity = verify_bundle(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    except (OSError, UnicodeError, ValueError) as exc:
        sys.exit(f"bundle validation failed: {exc}")
    print(identity)


if __name__ == "__main__":
    main()
