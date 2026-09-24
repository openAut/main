# Research: FDD och larmsamband för Advisor

Datum: **2026-09-23**. Omfattning: de två kunskaps-skillsen `fdd` och `anomaly-correlation`
samt självständiga läsanpassningar för Advisor. Fokus är ventilationsdemo, med metodstöd för
givare, återvinning och vattenbatterier. Detta dokument är ett metodunderlag, inte en driftsättning.

## Samlad slutsats

En användbar Advisor ska ge **nästa särskiljande kontroll**, inte bara en lång lista med möjliga fel.
Det kräver driftlägesberoende fysik, explicit datakvalitet, motbevis och en hypotes som kan omprövas.
Vid flera larm ska den visa vilka samband som är belagda och vilka som bara är möjliga, samtidigt som
varje relevant larm och dess angelägenhetsgrad förblir synliga.

Skillsen är instruktioner för analys och förklaring. De är varken körbara detektorer eller bevis för
att ett styrsystemsfel har fastställts. Driftsatta, deterministiska fynd behöver egna versionerade
regler och verifierade indata. Ett styrsystemslarm och dess fysiska orsak är olika saker.

## Källor och läsdjup

Nedanstående webbkällor hämtades 2026-09-23. R1 och R8 har granskats på respektive forskningsinstituts
publikationssida/abstract, **inte i fulltext**. R2–R7 har granskats i de angivna HTML-avsnitten.
Hänvisningarna stödjer principerna nedan; de är inte instruktioner för en viss installerad utrustning.

### R1 — NIST: APAR, driftläge och observerbarhet

Milesi-Ferretti, Schein, Park, Galler, Bushby och House (2003), *Results from Simulation and Laboratory
Testing of Air Handling Unit and Variable Air Volume Box Diagnostic Tools*, NISTIR 6964.

- [NIST publikationssida](https://www.nist.gov/publications/results-simulation-and-laboratory-testing-air-handling-unit-and-variable-air-volume-box)
- [DOI: 10.6028/NIST.IR.6964](https://doi.org/10.6028/NIST.IR.6964)
- Abstractet beskriver APAR som expertregler härledda ur mass-/energibalanser, med driftläge bestämt
  från styrsignaler och ett driftlägesspecifikt regelurval.
- Testresultaten anger också att vissa fel inte kan upptäckas i vissa driftfall: regleringen kan
  maskera felet eller nödvändiga givare saknas.
- **Tillämpning:** läge före regel; normal reglerad temperatur utesluter inte ett kompenserat fel;
  saknade mätpunkter begränsar slutsatsen.
- **Gräns:** inga exakta APAR-regelnummer, toleranser eller fördröjningar kopieras från abstractet.
  Resultat från APAR/VPACC etablerar inte förmågan hos en LLM eller en openAut-installation.

### R2 — EnergyPlus 24.2: Operational Faults

[Engineering Reference: Operational Faults](https://bigladdersoftware.com/epx/docs/24-2/engineering-reference/operational-faults.html),
särskilt *Heating and Cooling Coil Fouling*, *Air Filter Fouling*, *Sensor Faults with Air Economizers*
och *Coil Supply Air Temperature Sensor Offset*. EnergyPlus-dokumentation publicerad via Big Ladder.

- Filtermotstånd kan kompenseras av en varvtalsstyrd fläkt med bibehållet flöde. När kompensation inte
  räcker kan flödet falla; effekten behöver inte öka i samtliga driftfall.
- Minskad värmeöverföringsförmåga i vattenbatteri kan ge otillräcklig kapacitet och/eller större
  vattenflöde och låg vattensidig ΔT. Givaroffset påverkar både reglering och observerad prestanda.
- **Tillämpning:** jämför filtertryck vid jämförbart flöde; skilj kommando, återkoppling och process;
  använd inte låg ΔT som unik indikator på lågt flöde.
- **Gräns:** detta är simuleringsmodeller och deras antaganden, inte universella diagnostiska test eller
  en tillverkares servicegränser. Vi använder mekanismerna, inte modellernas parameterisering.

### R3 — EnergyPlus 24.2: Heat Exchangers

[Engineering Reference: Heat Exchangers](https://bigladdersoftware.com/epx/docs/24-2/engineering-reference/heat-exchangers.html),
avsnittet *Air System Air-To-Air Sensible and Latent Effectiveness Heat Exchanger*: Overview,
Model Description, Frost Control Methods, Economizer Operation och Supply Air Outlet Temperature Control.

- Återvinning beror på båda luftströmmarnas värmekapacitetsflöden. Bypass/rotorreglering kan avsiktligt
  begränsa återvinning för tilluftsbörvärde, frikyla eller frostskydd.
- Modellen skiljer sensibel/latent överföring och givarlägen vid växlarens in-/utlopp.
- **Tillämpning:** kontrollera sekvens och givarläge innan temperaturkvot beräknas; eftervärmd tilluft
  är inte samma temperatur som direkt efter återvinnaren. Kvot med nästan lika inlopp är instabil.
- **Gräns:** modellens nominella flödesområden/frosttemperaturer blir inte POC-larmgränser. En enkel
  temperaturkvot är inte certifierad totalverkningsgrad eller en besparingsberäkning.

### R4 — HSE: Alarm management

[HSE: Alarm management](https://www.hse.gov.uk/humanfactors/topics/alarm-management.htm),
*Key principles of alarm management*.

- Larm ska rikta operatörens uppmärksamhet mot förhållanden som behöver bedömning/åtgärd i tid.
  De ska vara relevanta, vägleda responsen och ta hänsyn till mänskliga begränsningar.
- **Tillämpning:** kort incidentbild, tydlig nästa kontroll och synlig angelägenhetsgrad.
- **Gräns:** sidan handlar om larmhantering i bredare processindustri. Den bevisar ingen viss
  korrelationsalgoritm och ger inga numeriska larmfrekvenskrav för openAut. ISA-18.2/IEC 62682/EEMUA 191
  har inte fulltextgranskats här och används inte som grund för ett påstående om efterlevnad.

### R5 — OPC Foundation: larmtillstånd och övergångstid

OPC UA Part 9, visad version 1.05.06:

- [§4.8 Alarms](https://reference.opcfoundation.org/Core/Part9/v105/docs/4.8)
- [§5.2 Two-state state machines](https://reference.opcfoundation.org/Core/Part9/v105/docs/5.2)

Modellen skiljer aktivt larm, kvitterbarhet, latch, shelving och suppression. TransitionTime och
EffectiveTransitionTime har olika betydelse när delstater ändras. Ett latchat larm kan kvarstå efter
att det utlösande värdet normaliserats.

**Tillämpning:** återgång, kvittering, reset, mänskligt rapporterad åtgärd och verifierad återhämtning
är olika saker. Återkommande tillstånd skiljs från upprepade meddelanden. Gruppering i Advisor är en
presentation, inte suppression i källsystemet. **Gräns:** OPC UA läggs inte till; dessa fält antas inte
finnas i Modbus-/COV-data. Aktuell källsemantik måste komma från integrationen.

### R6 — OPC Foundation: kvalitet och tidssemantik

OPC UA Part 4, visad version 1.05.07:
[§7.11 DataValue, särskilt §§7.11.3–7.11.5](https://reference.opcfoundation.org/Core/Part4/v105/docs/7.11).

Källans tid, serverns tid och värdets användbarhet/kvalitet är skilda begrepp. Vid händelsestyrd
överföring behöver oförändrat värde inte ge ny källtidsstämpel.

**Tillämpning:** skilj lästid, publicering/ändring och fysisk mättid; bevara klockosäkerhet. Ett gammalt
COV-värde är inte automatiskt en död givare. **Gräns:** openAut följer sitt eget verifierade
insamlingskontrakt; OPC UA-serverns specifika garantier överförs inte till POC:ns heartbeat.

### R7 — NIST: robust statistik och beroende observationer

NIST/SEMATECH e-Handbook of Statistical Methods:

- [§1.3.5.17 Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)
- [§1.3.3.1 Autocorrelation Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/autocopl.htm)

Den modifierade z-poängen är `0.6745 * (x - median) / MAD`. Gränsen 3,5 diskuteras för att märka
potentiella avvikare, inte för att fastställa fel. Källan skiljer märkning, robust hantering och
formell identifiering. Autokorrelation kan göra antaganden om oberoende observationer olämpliga.

**Tillämpning:** jämförbar baslinje, redovisad beräkning, noll-MAD-hantering, ingen påhittad säkerhet
eller automatisk driftsättning av 3,5 som larmgräns. COV-viktning, baslinjeläckage och flera samtidiga
jämförelser behandlas som explicita metodbegränsningar i openAut-syntesen.

### R8 — LBNL: utvärdera FDD med kända fall

Lin, Kramer och Granderson (2020), *Building fault detection and diagnostics: Achieved savings,
and methods to evaluate algorithm performance*, Building and Environment 168.

- [LBNL publikationssida](https://buildings.lbl.gov/publications/building-fault-detection-and)
- [DOI: 10.1016/j.buildenv.2019.106505](https://doi.org/10.1016/j.buildenv.2019.106505)

Abstractet beskriver en systematisk utvärderingsmetod, ett initialt AHU-feldataset och prov på tre
FDD-algoritmer. **Tillämpning:** separata normal-, fel- och otillräckliga-datafall samt upprepningsbar
jämförelse mellan skill-revisioner. **Gräns:** vår rubric och våra syntetiska fall är egna, inte en
reproduktion av studiens benchmark. Studiens besparingar överförs inte till POC:n.

## Konkreta ändringar och stöd

| Tidigare svaghet | Ny metod | Grund |
|---|---|---|
| För hög tilluft i värmedrift kopplades bl.a. till för liten värmare | Separata tecken-/driftlägesspår; oönskad värme och otillräcklig värme skiljs | R1/R2 + energibalans, egen teknisk syntes |
| Låg ΔT kopplades för direkt till lågt flöde | Last/flöde/bypass/givare; fast-last-resonemang märks med sitt villkor | R2 + värmebalans |
| Filterfel kunde förenklas till lågt flöde | Kompenserad drift och jämförbar flödespunkt | R1/R2 |
| Få explicita normalfall | Start/stopp, frikyla, frost/avfrostning, återvärmning, setpunktsbyte | R1/R3 + insamlingskontrakt |
| Samtidighet och första larm riskerade att bli rotorsak | Tidsintervall, fördröjning, klockfel, dokumenterad riktad relation och motbevis | R5/R6 + egen korrelationsmetod |
| Topologi kunde antas från topic-hierarki | Bevisad relation med typ, riktning och källa krävs | Behörighets-/datakontrakt |
| Parent/child suppression och severity × confidence | Synliga medlemslarm; prioritet hålls skild från kausal säkerhet | R4/R5 + Advisor-gränsen |
| Statistik utan beräknings-/baslinjekrav | Reproducerbar beräkning, jämförbart driftläge, otillräcklig-datautfall | R7 |
| Kunskapstext lät som installerad deterministisk logik | Observation → faktiskt regelfynd → hypotes → verifierad orsak | Runtime-kontrakt, R8 för utvärderingsprincip |

Hypotesrangordning, högst tre initiala hypoteser, en särskiljande fråga och stopp när nästa kontroll
är tydlig är **openAut-designval**, inte ordagranna standardkrav. De ska prövas med utvärderingsfallen.

## Runtime-anpassning och gränser

Den [publika läsverktygsadaptern](../deploy/advisor-discovery/openclaw/read-tool.mjs) tillåter endast
`fdd` och `anomaly-correlation` som guidance-namn och returnerar respektive SKILL.md från en
ägarprovisionerad katalog. Den hämtar inte referensfiler. Därför finns
[självständiga Advisor-exempel](../examples/advisor-readonly/README.md) med nödvändiga instruktioner
inuti varje fil. Skill-filerna skapar inte själva någon läsåtkomst eller behörighet.

Historikgränserna är 8 mätvärden, 7 dygn och 500 rader per anrop. Dessa är anropsgränser, inte löfte
om faktisk datatäckning eller tillräcklig baslinje. Dokument, fysisk punktmappning och installerad
programversion behöver verifieras för varje verklig utrustning.

Fullständiga NIST-/LBNL-PDF:er och HSE CHIS6 kunde inte textgranskas vid researchen; endast läsbara
avsnitt ovan används som belägg. ASHRAE:s addendakatalog kontrollerades, men ingen normativ
Guideline 36-text används som läst källa. Metoden gör inga anspråk på fullständig APAR-implementation
eller standardöverensstämmelse. Ingen automatisk fältdetektor införs genom kunskapstexterna.

Se [utvärderingsfallen](ADVISOR-DIAGNOSTICS-EVALUATION.md) för observerbara beteendekrav och
[demorapporten](ADVISOR-DIAGNOSTICS-DEMO-20260923.md) för det begränsade manuella utfallet.
