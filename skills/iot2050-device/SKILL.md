---
name: iot2050-device
description: Inspect and operate Siemens SIMATIC IOT2050 hardware using model-aware, read-only-first workflows grounded in Siemens operating instructions and the official Siemens Debian BSP. Use when identifying an IOT2050 variant, checking its OS, storage, interfaces, services, serial adapters, health, boot media, or preparing a separately approved firmware or reimage procedure.
permissions:
  knowledge_only: false
  tools: "SSH and standard Linux inspection commands; Siemens utilities only after approval"
  exec: "read-only remote inspection by default; approved maintenance commands require explicit human confirmation"
  network: "SSH to the lab IOT2050 only"
  files: "read-only by default; approved maintenance may alter boot media or firmware"
  credentials: "existing node-local SSH identity; never read or print private keys or certificates"
  control_writes: "none"
---

# SIMATIC IOT2050 device operations

Use this skill for the device itself. Use [`edge-iot2050`](../edge-iot2050/SKILL.md) to install the
openAut MQTT edge publisher and a protocol skill such as [`modbus`](../modbus/SKILL.md) or
[`bacnet`](../bacnet/SKILL.md) to inspect field devices.

This is a lab workflow. Never connect the node to a live building, occupied space, or
safety-critical equipment. Default to read-only SSH through the machine-local alias. Do not copy
addresses, MAC addresses, serial numbers, credentials, certificates, or other node-specific values
into shared documentation.

## Source policy

Use Siemens sources in [`references/official-sources.md`](references/official-sources.md). Apply this
precedence when sources differ:

1. The current Siemens operating instructions for hardware, mounting, wiring, environmental limits,
   and product variants.
2. The official `siemens/meta-iot2050` documentation matching the installed image generation for
   image, boot, firmware, and Siemens utility behaviour.
3. Observations from the node for its current runtime state.

Do not infer a hardware capability from a Linux device node alone. Record the observed fact and the
manual-backed interpretation separately.

## Read-only inventory

Connect only through the approved lab alias. Do not probe other hosts from the IOT2050.

```bash
ssh openaut-iot2050
```

Identify the exact variant before recommending any operation:

```bash
cat /sys/firmware/devicetree/base/model
tr '\0' '\n' < /sys/firmware/devicetree/base/compatible
cat /etc/os-release
uname -a
lscpu
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
df -hT /
```

Inspect health and interfaces without printing link-layer identifiers:

```bash
systemctl is-system-running
systemctl --failed --no-pager
ip -brief link
ip -brief address
timedatectl
ss -lntup
```

For reports, redact IP addresses and process arguments that contain secrets. Report unexpected
listeners by interface and port, but do not attempt to disable them without approval. Run `ethtool`
only for Ethernet interface names observed in `ip -brief link`; do not assume `eno1`/`eno2` on every
image.

Inspect Siemens software and attached serial devices:

```bash
dpkg-query -W 'iot2050*' 'mraa*' 'node-red*' 2>/dev/null
find /usr/share/iot2050 -maxdepth 3 -type f -printf '%p\n' 2>/dev/null
ls -l /dev/serial/by-id /dev/serial/by-path 2>/dev/null
```

Prefer stable `/dev/serial/by-id/...` names over `/dev/ttyUSB*`. A USB adapter being present does not
identify its electrical mode, bus wiring, termination, baud rate, parity, or field protocol.

## Interpret the result

- Treat the device-tree `model` as the primary runtime variant identifier.
- Confirm storage against the variant. Siemens documents eMMC installation for IOT2050 Advanced
  only. On Basic, do not call an `mmcblk` device internal eMMC merely because of its Linux name.
- Treat `VARIANT="IOT2050 Debian Example Image"` as a development/example image, not by itself as a
  hardened production baseline.
- Distinguish boot firmware from the Debian root filesystem. `BUILD_ID` describes the image build;
  a bundled file under `/usr/share/iot2050/fwu/` is an available update package, not proof that it
  has been flashed.
- Note clock synchronization failures because bad time can invalidate TLS and telemetry timestamps.
- List active listeners and enabled services. An installed package does not prove its service is
  active, externally reachable, configured, or needed.

## Maintenance gate

The following are state-changing and are forbidden during inventory:

- `iot2050setup` or `switchserialmode`
- `iot2050-firmware-update`
- `fw_setenv`, U-Boot commands, or boot-target changes
- package installation, service enable/disable, firewall or network changes
- writing an image with `bmaptool`, `dd`, or SWUpdate
- creating `/etc/install-on-emmc`
- reboot, shutdown, or power removal

Before any such action, require an approved Systemdatabas case and explicit human confirmation of
the exact target, command, maintenance window, backup/rollback path, and expected outage. Keep field
writes and deployment in the Engineer trust domain. Read the matching Siemens procedure in full;
do not execute a command copied only from this summary.

## Model-aware maintenance rules

- Never propose the Advanced-only eMMC installation flow for Basic.
- Firmware and OS images are separate artifacts. Verify product variant, release, checksum/signature,
  power stability, and recovery access before either operation.
- Do not use force flags for firmware updates merely to bypass a compatibility check.
- Do not interrupt power while firmware or storage is being written.
- Treat serial-mode changes as electrical configuration changes. Verify the connector, transceiver,
  pinout, voltage/mode, termination, and isolation against the operating instructions and attached
  equipment before approval.
- A/B SWUpdate applies only when the installed image was built with that layout. Confirm partitions
  and the image documentation before using `swupdate` or `complete_update.sh`.

## Report format

Return a concise report with:

1. Variant and evidence from device tree.
2. OS/image build and kernel.
3. CPU architecture/core count and memory.
4. Storage layout, usage, and whether media type remains unconfirmed.
5. Ethernet link state/speed without MAC addresses or local addresses.
6. Attached serial adapters and stable device paths.
7. System health, clock synchronization, active relevant services, and exposed listeners.
8. Differences between observed state and Siemens guidance.
9. Recommended next read-only check, or the approval prerequisites for a change.

Label values as `observed`, `manual-backed`, or `inferred`. Never present an inference as an
observed hardware fact.
