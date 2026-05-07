# openAut

> Öppen AI-plattform för fastighetsautomation med lokal inferens, Python edge-reglering och ingen leverantörsinlåsning.

openAut är ett **öppet tillägg till ditt befintliga BMS** — inte en ersättare. Plattformen samlar in driftsdata, analyserar den lokalt med kraftfull AI-hårdvara, och kan driftsätta Python-baserad reglering direkt på edge-noder. Designat för offentlig upphandling, IEC 62443-säkerhet och långsiktig förvaltning.

**Hemsida:** https://openaut.io · **Licens:** MIT · **Status:** v0.1 — aktiv utveckling

---

## Vad openAut gör

- **Feldetektering (FDD):** Korrelerar signaler över tid och identifierar rotorsak med konfidensgrad — levererat i Teams eller Slack, inte i BMS-klienten.
- **Energioptimering:** Prediktion, lastprognos och avvikelseanalys mot historisk trenddata.
- **Guidad integration:** Läs in en fabrikants manual, ange edge-nod — openAut guidar teknikern steg för steg och dokumenterar automatiskt.
- **Python edge-reglering:** Driftsätt Python-baserade reglerloopar direkt på edge-noden mot lokal I/O. Utan rundtur till AI-servern. Versionshanterat, loggat och återkallelsebart centralt via NemoClaw.
- **Automatisk dokumentation:** I/O-listor, driftsättningsprotokoll och FAT/SAT genereras som sidoeffekt av normal drift.

---

## Arkitektur — fyra lager

```
LAGER 04 — GRÄNSSNITT   Teams · Slack · Webb-HMI · REST API
LAGER 03 — AI           NemoClaw · DGX Spark · LLM-inferens · FDD · Energioptimering
LAGER 02 — EDGE         Linux-noder · SSH · Protokolldrivrutiner · Python edge-reglering
LAGER 01 — FÄLT         BACnet · Modbus RTU/TCP · M-Bus · OPC UA · LoRaWAN · KNX · DALI
```

**LAGER 01 — FÄLT:** Befintlig fältutrustning ansluts utan modifiering. PLC:er, DDC-regulatorer och mätare kommunicerar via sina befintliga protokoll. openAut läser — fältets reglering behåller prioritet.

**LAGER 02 — EDGE:** Moxa AIG-noder eller Siemens SIMATIC IOT2050 kör standard Linux och nås av NemoClaw via krypterad SSH. Protokolldrivrutiner körs direkt på noden. NemoClaw kan via SSH även driftsätta Python-regleringsskript mot lokal I/O — slutna reglerloopar utan molnrundtur. Data transporteras krypterat via OPC UA (Basic256Sha256) eller MQTT over TLS.

**LAGER 03 — AI:** NVIDIA DGX Spark (GB10 Grace Blackwell, 128 GB unified memory, 1 PFLOP FP4) kör NemoClaw och OpenClaw lokalt. MQTT-broker, LLM-inferens och FDD-modeller på samma hårdvara. All data stannar i fastigheten.

**LAGER 04 — GRÄNSSNITT:** Insikter når de som behöver dem i de verktyg de redan använder. Drifttekniker i Teams. Energisamordnare i dashboard. Integrationsteam via REST API.

---

## Teknisk stack

| Lager | Komponenter |
|---|---|
| **openAut** (domänramverk) | BACnet-skill · Modbus-skill · M-Bus-skill · LoRa-skill · OPC UA-skill · FDD-skill · Energianalys-skill · SSH edge-access · Python I/O-skill · Edge-reglerings-skill |
| **NemoClaw** (agent) | Anthropic Claude Agent SDK · MCP · lokalt körd · ARM64 |
| **OpenClaw** (LLM) | Öppen källkod · ≤200B parametrar · lokal inferens |
| **AI-hårdvara** | NVIDIA DGX Spark · ASUS Ascent GX10 (alternativ) |
| **Edge-hårdvara** | Siemens SIMATIC IOT2050 · Moxa AIG-serien |
| **I/O-modul** | Siemens EM1.8U (8× universell I/O · Modbus RTU · RS485) |
| **Transport** | OPC UA Basic256Sha256 · MQTT over TLS · WireGuard VPN |
| **Databas** | PostgreSQL · TimescaleDB · Haystack · Brick Schema |

---

## Kärnprinciper

**P.01 — Reglering under kontroll, aldrig på autopilot**
openAut kan driftsätta Python-baserad reglering direkt på edge-noder via I/O, men bara när en applikationsprofil och ett explicit regleringsuppdrag konfigurerats av behörig användare. All skrivåtkomst loggas, versionshanteras och kan återkallas. Befintliga PLC:er och DDC-regulatorer behåller prioritet.

**P.02 — Skickar inte din data till molnet**
All inferens körs på den lokala AI-servern i fastigheten. Ingen driftdata lämnar byggnaden om du inte aktivt konfigurerar det.

**P.03 — Kräver inga proprietära beroenden**
Kärnstacken körs helt på öppen källkod: `pymodbus`, `opcua-asyncio`, `BAC0`, `open62541` med flera. Inga proprietära drivrutiner eller licenser.

**P.04 — Ersätter inte ditt befintliga BMS**
openAut samexisterar med Desigo CC, EcoStruxure, Trend, Regin, Niagara och alla andra plattformar. Det läser deras data — konkurrerar aldrig med dem.

**P.05 — Skapar inget nytt leverantörsberoende**
Arkitekturen är modulär, dokumenterad och kan tas vid av vilken kompetent integratör som helst. Varje designbeslut utvärderas mot frågan: skapar detta inlåsning?

---

## Referenshårdvara

### AI-lager
| Enhet | Chip | Minne | Prestanda | Roll |
|---|---|---|---|---|
| NVIDIA DGX Spark | GB10 Grace Blackwell | 128 GB unified | 1 PFLOP FP4 | Primär referenshårdvara |
| ASUS Ascent GX10 | GB10 Grace Blackwell | 128 GB LPDDR5x | 1 PFLOP FP4 | Alternativ, identisk chip |

### Edge-lager
| Enhet | CPU | Gränssnitt | Roll |
|---|---|---|---|
| Siemens SIMATIC IOT2050 | TI AM6548 · 4× A53 · 1 GHz | RS232/422/485 · 2× GbE · Arduino Shield | Python-regulator och datainsamlare via SSH |
| Siemens EM1.8U | — | 8× universell I/O · Modbus RTU · RS485 | Industriell I/O, upp till 31 moduler per buss |

Hela stacken är ARM64-nativ. `pymodbus`, `opcua-asyncio`, `BAC0` och `open62541` är verifierade på ARM64 utan proprietära beroenden.

---

## Säkerhet

Säkerhet är inbyggt från dag ett, inte tillagt i efterhand:

- **IEC 62443** och **NIS2** är baskrav
- VLAN-segmentering per lager
- OPC UA Basic256Sha256 för all datatransport
- WireGuard VPN för fjärråtkomst
- RBAC och auditloggning
- Regleringskod versionshanteras och granskas som konfiguration

---

## Offentlig sektor och LOU

openAut är MIT-licensierat — det finns ingen enskild leverantör att upphandla. Plattformen är gratis att använda. Vad din organisation upphandlar är **kompetensen** att implementera och förvalta den — tjänster som kan tilldelas valfri regional konsult eller befintlig ramavtalspartner.

En lösning som en kommun bygger kan återanvändas av alla andra. Bidrag tillbaka till projektet stärker plattformen för hela ekosystemet.

---

## Protokollstöd

`BACnet/IP` · `BACnet MS/TP` · `Modbus RTU` · `Modbus TCP` · `M-Bus` · `OPC UA` · `MQTT` · `LoRaWAN (EU868)` · `KNX` · `DALI`

---

## Kom igång

```bash
# Utforska projektet
https://github.com/openaut

# Hemsida och dokumentation
https://openaut.io

# Systemtopologi
https://openaut.io/topologi.html
```

Projektet är under aktiv utveckling och redo för pilotdriftsättningar. Bidra med en protokolldrivrutin, anpassa en applikationsprofil, eller testa edge-reglering mot din befintliga I/O-hårdvara.

---

MIT License · openAut · https://openaut.io
