# Edge reliability reference tools

These opt-in tools extract reusable lessons from the isolated POC. They do not install a service,
contain an equipment register map or replace the generic edge scaffold with a working field driver.

## POC boundary

The standalone staging commands below are for isolated lab experiments under a lightweight local
case, explicit operator confirmation, hash checks, verification and rollback. They do not require
building a production release pipeline to try the POC.

For production ingress, these are build primitives only: [ADR 0001](adr/0001-delivery-and-trust-model.md)
requires dependencies from the verified `refresh` cache to be included by `build` in the pinned,
self-contained signed Main release and SBOM. Standalone vendor transfer/installation outside that
release is not a production deployment path. These helpers verify neither release signatures nor
attestations; the production release verifier must do so before installation.

## Field reads and health

See [the FC04 adapter pattern](../skills/modbus/references/readonly-reliability.md) for explicit
register allow-listing, separate field health and bounded exception-triggered close/reopen.
Use only through a reviewed equipment profile and an approved deployment case.

## Independent offline dependencies

On a build host with Python and pip, prepare a separate directory for each integration:

```text
python scripts/build_edge_vendor.py requirements.lock /approved/wheelhouse /staging/reader-vendor
```

The lock must contain reviewed exact pins and SHA-256 hashes. The wheelhouse must contain only
portable `py3-none-any` wheels; native dependencies require a separately reviewed target-ABI build.
The builder runs pip under isolated Python, with no index, required hashes, no compilation, and
refuses an existing output. A failed build cannot replace the old runtime. Pin the Python/pip build environment and
record the lock and delivered artifact hashes with the case.

For the isolated POC, transfer the artifact using the approved management path. On the target,
without pip or venv:

```text
python3 scripts/verify_edge_vendor.py /staging/reader-vendor paho.mqtt.client pymodbus.client
```

The verifier invokes target Python with `-I -S`, adds only the selected vendor directory and checks
requested module origins. Ambient `PYTHONPATH`, user-site and system-site packages cannot make an
incomplete vendor tree appear functional. Symlinks are rejected. Execute only reviewed packages:
import verification executes package code and is not a sandbox for untrusted dependencies.

After successful staging verification, a separately approved installer must assign service-owned
paths and read-only permissions, preserve rollback, and verify imports as the runtime user. Disable
bytecode writes (`PYTHONDONTWRITEBYTECODE=1`) and user-site imports in the unit. Neither tool changes
ownership, permissions, service units or running processes. Do not point one service at another's
vendor directory. Repeat target verification for the actual Python version and architecture.

## Replay boundary

The existing reference publisher creates event IDs before SQLite persistence. Regression tests
exercise failed publish, process-style reopen of a file-backed spool, byte-identical legacy/new
payload replay and PUBACK deletion. Broker PUBACK still does not prove database commit. Live broker
outage and physical RTU recovery acceptance remain separately scoped experiments.
