#!/usr/bin/env python3
"""Build an independent pure-Python vendor artifact from a reviewed offline wheelhouse."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def build(lock, wheelhouse, output):
    lock, wheelhouse, output = (Path(p).resolve() for p in (lock, wheelhouse, output))
    if not lock.is_file() or not wheelhouse.is_dir() or not output.parent.is_dir():
        raise ValueError("lock, wheelhouse and output parent must exist")
    if output.exists():
        raise ValueError("refusing to replace an existing runtime")
    wheels = list(wheelhouse.glob("*.whl"))
    if not wheels or any(not p.name.endswith("-py3-none-any.whl") for p in wheels):
        raise ValueError("this portable builder accepts only py3-none-any wheels")
    # The reviewed lock must contain package pins/hashes only. Disallow direct URLs
    # and pip options that could override offline selection or introduce another index.
    for line in lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entry = line.removesuffix("\\").strip()
        pin = r"[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*"
        digest = r"--hash=sha256:[0-9a-f]{64}"
        if not re.fullmatch(rf"(?:{pin}(?:\s+{digest})*|{digest})", entry):
            raise ValueError("lock must contain offline package pins and SHA-256 hashes only")
    with tempfile.TemporaryDirectory(prefix="edge-vendor-", dir=output.parent) as temporary:
        target = Path(temporary) / "vendor"
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR"}}
        environment["PIP_CONFIG_FILE"] = os.devnull
        subprocess.run([
            sys.executable, "-I", "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
            "--no-index", "--only-binary=:all:", "--require-hashes", "--no-compile",
            "--find-links", str(wheelhouse), "--requirement", str(lock), "--target", str(target),
        ], check=True, env=environment)
        if any(p.is_symlink() for p in target.rglob("*")):
            raise ValueError("vendor artifact must not contain symlinks")
        target.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock")
    parser.add_argument("wheelhouse")
    parser.add_argument("output")
    args = parser.parse_args()
    build(args.lock, args.wheelhouse, args.output)


if __name__ == "__main__":
    main()
