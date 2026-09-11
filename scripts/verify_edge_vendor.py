#!/usr/bin/env python3
"""Import-test a staged vendor tree using target Python with no site-package fallback."""

import argparse
import importlib
from pathlib import Path
import subprocess
import sys


def verify(vendor, modules):
    vendor = Path(vendor).resolve(strict=True)
    if not vendor.is_dir() or any(p.is_symlink() for p in vendor.rglob("*")):
        raise ValueError("vendor must be an independent directory without symlinks")
    if not (sys.flags.isolated and sys.flags.no_site):
        raise RuntimeError("verification requires python -I -S")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(vendor))
    for name in modules:
        module = importlib.import_module(name)
        origin = getattr(module, "__file__", None)
        if origin is None or not Path(origin).resolve().is_relative_to(vendor):
            raise ValueError(f"{name} was not imported from the selected vendor directory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor")
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args()
    if not (sys.flags.isolated and sys.flags.no_site):
        result = subprocess.run([
            sys.executable, "-I", "-S", str(Path(__file__).resolve()),
            str(Path(args.vendor).resolve()), *args.modules,
        ])
        raise SystemExit(result.returncode)
    verify(args.vendor, args.modules)
    print("EDGE_VENDOR_OK imports=isolated")


if __name__ == "__main__":
    main()
