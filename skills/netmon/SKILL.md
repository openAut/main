---
name: netmon
description: "Network device discovery and anomaly detection for home network (192.168.1.x). Lists known devices, triggers on-demand scans, shows topology. Results go only to owner DM, never group chat."
permissions:
  knowledge_only: false
  exec: "operator-provisioned wrappers (netmon-status.sh, netmon-scan.sh) on the node, allowlisted"
  network: "local-subnet-scan (192.168.1.x, nmap -sn/-sV)"
  files: "read-write (registry.sqlite for device registry)"
  data_sensitivity: "network topology - owner DM only, never group chat"
---

# Netmon – Nätverkskartläggning

Deterministisk nätverks-NDR för hemmet. **Ingen LLM i skannings- eller analysvägen.**

## Tillgängliga kommandon (ägarkommando, endast David i DM)

Wrapparna nedan är **operatörs-provisionerade och allowlistade på noden** (samma modell som meshcore) och ingår inte i repot; refereras med wrapper-namn:

- `netmon-status.sh` — visa aktuell inventering (rör inte nätet)
- `netmon-scan.sh [MAC]` — tvinga omskanning av alla eller en enhet

## Arkitektur

- **Poll** var 15:e min (systemd-timer `netmon-poll.timer`): `nmap -sn` + `ip neigh` → InfluxDB bucket `netmon`
- **Analys** 03:30 nattligen (`netmon-analyze.timer`): `-sV` granskning av nya enheter, baseline, avvikelse-digest → Davids DM
- **Dashboard**: http://192.168.1.172:3000/d/netmon/

## Säkerhet

Topologidata är ägarinfo — skickas **aldrig** till Signal-gruppen. Larm och digest går **enbart** till Davids DM.
