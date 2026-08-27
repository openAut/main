# Official Siemens sources

Checked 2026-08-25. Siemens Industry Online Support pages require JavaScript in some clients; use
the document IDs below to locate the current downloadable revision before maintenance.

## Hardware and safety

- Siemens Industry Online Support, **SIMATIC IOT2050 Operating Instructions**, document ID
  `109963259`, edition 03/2024, manual number `A5E39456816-AF`:
  https://support.industry.siemens.com/cs/document/109963259/?lc=en-WW&dti=0
- Earlier indexed revision, document ID `109814142`, edition 10/2022, manual number
  `A5E39456816-AD`. Use only when the current revision is unavailable or when tracing a historical
  hardware requirement:
  https://support.industry.siemens.com/cs/document/109814142/?lc=en-WW&dti=0

The operating instructions are authoritative for product variants, connectors, installation,
wiring, environmental conditions, approvals, and safety notices.

## Debian image and firmware

- Siemens official Debian BSP repository and overview:
  https://github.com/siemens/meta-iot2050
- Documentation index:
  https://github.com/siemens/meta-iot2050/blob/master/doc/README.md
- Maintenance and firmware operations:
  https://github.com/siemens/meta-iot2050/blob/master/doc/maintenance.md
- First-boot onboarding and runtime topology:
  https://github.com/siemens/meta-iot2050/blob/master/doc/firstboot-onboarding.md
- SWUpdate A/B procedure:
  https://github.com/siemens/meta-iot2050/blob/master/doc/swupdate.md
- Siemens downloads for SIMATIC IOT20x0, document ID `109741799`:
  https://support.industry.siemens.com/cs/document/109741799/downloads-for-simatic-iot20x0?dti=0&lc=en-WW

The repository documents that installation to internal eMMC is available only on IOT2050 Advanced,
that the example image and base BSP have different network defaults, and that boot-firmware updates
use `iot2050-firmware-update`. Always match procedures to the installed image generation and exact
hardware variant.

## Verification rule

Before a state-changing operation, re-open the current Siemens source, confirm that its revision and
target variant match the device, and verify downloaded artifacts using checksums or signatures
published by Siemens. A URL in this reference is provenance, not standing approval to make a change.
