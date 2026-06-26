---
name: nmap
description: >
  Nätverksskanning med nmap. Använd denna skill när David (eller någon i gruppen
  med Davids godkännande) vill skanna nätverket, hitta enheter, kontrollera öppna
  portar, identifiera tjänster, eller undersöka en specifik host. Trigga också
  vid frågor som "vad finns på nätverket", "vilka portar är öppna", "är X uppe",
  "skanna 192.168.1.x" eller liknande.

permissions:
  knowledge_only: false
  exec: "operator-provisioned wrapper (nmap-scan.sh) on the node, allowlisted"
  network: "local-subnet-scan (192.168.1.x)"
  files: "read-only"
  external_services: "Signal/message notifications via operator wrapper"
---

# Nmap-skanning

## ⚠️ KRITISK REGEL: Kör ALLTID via bakgrundsscriptet

Kör ALDRIG nmap direkt med exec. nmap tar för lång tid — exec kommer att ta timeout.

Det enda tillåtna sättet att köra en skanning är:

> **Operator-provisioned wrapper:** `nmap-scan.sh` är ett allowlistat wrapper-skript som provisioneras på noden (samma modell som meshcore). Exemplen använder wrapper-namnet; den absoluta nodsökvägen är medvetet utelämnad eftersom den inte är portabel.

```
exec: nohup bash nmap-scan.sh TARGET LEVEL LABEL > /tmp/nmap-scan.log 2>&1 &
```

Scriptet kör nmap i bakgrunden och skickar resultatet till Signal-gruppen automatiskt när det är klart. Du behöver inte vänta eller följa upp — scriptet sköter det.

## Direkt efter att du startat scriptet

Bekräfta till David med message-verktyget:
"🔍 Skanningen är igång! Jag hör av mig när den är klar."

Fortsätt sedan konversationen normalt. Du behöver inte göra något mer.

## Välj target och level

| Level | Tid | Vad |
|-------|-----|-----|
| 1 | ~5s | Ping sweep — vilka hostar är uppe (standard för "vad finns på nätet") |
| 2 | ~15s | 100 vanligaste portar, bara öppna (standard för enskild host) |
| 3 | ~45s | Topp 1000 portar + service-versioner |
| 4 | ~3min | Topp 1000 portar + versioner + NSE-scripts |
| 5 | ~20min | Alla 65535 portar — fråga alltid om bekräftelse innan |

Börja alltid på lägsta lämpliga level. Fråga om David vill eskalera efter att resultatet kommit in.

## Exempel

**Hela nätverket (ping sweep):**
```
exec: nohup bash nmap-scan.sh 192.168.1.0/24 1 "hemmanätet" > /tmp/nmap-scan.log 2>&1 &
```

**Enskild host, snabb:**
```
exec: nohup bash nmap-scan.sh 192.168.1.43 2 "GX10" > /tmp/nmap-scan.log 2>&1 &
```

**Enskild host, med service-versioner:**
```
exec: nohup bash nmap-scan.sh 192.168.1.172 3 "claw" > /tmp/nmap-scan.log 2>&1 &
```

## Kända hostar

| Host | IP |
|------|----|
| claw | 192.168.1.172 |
| GX10 | 192.168.1.43 |
| Subnät | 192.168.1.0/24 |

## Kontrollera pågående skanning

```
exec: cat /tmp/nmap-scan.log
```

## Säkerhetsregler

- Skanna aldrig utanför 192.168.1.0/24 utan Davids godkännande
- Level 5 kräver alltid bekräftelse i förväg
- Kör inte --script vuln utan godkännande