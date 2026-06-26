---
name: nis2
description: "Svenskt stöd för NIS2-omfattning, artikel 20, 21 och 23-checklistor."
permissions:
  knowledge_only: true
  tools: none
  network: none
  exec: none
---

# NIS2

Använd denna skill när du vill förstå eller arbeta strukturerat med EU:s NIS2-direktiv, direktiv (EU) 2022/2555: omfattning, sektorer, entitetstyp, riskhantering, incidentrapportering eller ledningsansvar.

## Viktiga noggrannhetsregler

- Presentera aldrig svaret som bindande juridisk rådgivning. Säg tydligt att bedömningen är ett arbetsstöd och rekommendera kvalificerad jurist, regelefterlevnadsexpert eller cybersäkerhetsexpert vid skarpa beslut.
- Hänvisa konkret till relevanta artikelnummer och bilagor i direktiv (EU) 2022/2555.
- Nationell implementering skiljer sig per land. För Sverige: hänvisa till cybersäkerhetslagen, MSB och CERT-SE, men hårdkoda inte datum, trösklar, myndighetsroller eller exakt lagtext utan att först verifiera mot officiella källor.
- Nationell status kan ändras. Be användaren kontrollera aktuell status mot officiella källor, särskilt EUR-Lex, Europeiska kommissionen, ENISA, MSB och CERT-SE.
- Om frågan gäller skyldigheter, sanktioner eller rapporteringskrav i en specifik verksamhet: ange osäkerheter och vad som behöver verifieras.

## Grundförklaring

Förklara kort:

- NIS2 är EU:s direktiv om åtgärder för en hög gemensam cybersäkerhetsnivå i unionen.
- Det ersätter och utvidgar tidigare NIS-reglering med fler sektorer, tydligare riskhanteringskrav, incidentrapportering och ledningsansvar.
- Direktivet behöver genomföras i nationell rätt; därför avgör nationell lag och tillsyn hur kraven faktiskt gäller i ett land.

## Bedöm om verksamheten kan omfattas

Gör en strukturerad, icke-bindande screening.

1. **Identifiera land och juridisk enhet**
   - Vilket EU-land gäller verksamheten?
   - Är det en egen juridisk person, koncernbolag, leverantör eller offentlig aktör?
   - Finns verksamhet i flera EU-länder?

2. **Matcha sektor mot bilaga I eller II**
   - Bilaga I: sektorer med hög kritikalitet, bland annat energi, transport, bankverksamhet, finansmarknadsinfrastruktur, hälso- och sjukvård, dricksvatten, avloppsvatten, digital infrastruktur, IKT-tjänstehantering B2B, offentlig förvaltning och rymden.
   - Bilaga II: andra kritiska sektorer, bland annat post- och budtjänster, avfallshantering, tillverkning/produktion/distribution av kemikalier, livsmedel, viss tillverkning, digitala leverantörer och forskning.
   - Be om verksamhetsbeskrivning om sektorn är oklar.

3. **Kontrollera storlekskriterier**
   - NIS2 använder i huvudsak storlekskriterier kopplade till medelstora och stora företag, men undantag finns.
   - Kontrollera anställda, omsättning och balansomslutning mot aktuell EU-definition och nationell implementering innan slutsats.
   - Vissa typer av entiteter kan omfattas oavsett storlek enligt direktivet eller nationell rätt; verifiera alltid.

4. **Klassificera preliminärt: väsentlig eller viktig entitet**
   - Väsentliga entiteter: typiskt aktörer i bilaga I som uppfyller relevanta kriterier, samt vissa särskilt utpekade aktörer enligt direktivet/nationell rätt.
   - Viktiga entiteter: typiskt andra omfattade aktörer som inte klassas som väsentliga, inklusive många bilaga II-aktörer.
   - Var tydlig: klassificering kan bero på nationell implementering och särskilda beslut från behörig myndighet.

5. **Ge slutsats med osäkerhetsnivå**
   - Skriv: “Preliminär bedömning: sannolikt / möjligt / osannolikt omfattad”.
   - Lista vilka fakta som saknas.
   - Rekommendera officiell verifiering och rådgivning.

## Artikel 21: riskhanteringsåtgärder som checklista

Använd denna checklista för gap-analys. Hänvisa till artikel 21 i NIS2.

- Policyer för riskanalys och informationssystemens säkerhet.
- Incidenthantering: processer för detektion, respons, eskalering, kommunikation och lärdomar.
- Kontinuitet: backup, krishantering och återställning efter katastrof.
- Säkerhet i leveranskedjan, inklusive säkerhetsrelaterade aspekter i relationer med direkta leverantörer och tjänsteleverantörer.
- Säkerhet vid anskaffning, utveckling och underhåll av nätverks- och informationssystem, inklusive sårbarhetshantering och sårbarhetsrapportering.
- Policyer och rutiner för att bedöma effektiviteten i cybersäkerhetsåtgärder.
- Grundläggande cyberhygien och cybersäkerhetsutbildning.
- Policyer och rutiner för kryptografi och, där relevant, kryptering.
- Personalsäkerhet, åtkomstkontroll och tillgångshantering.
- Användning av flerfaktorsautentisering eller kontinuerlig autentisering, säkrade röst-, video- och textkommunikationer samt säkrade nödkommunikationssystem där det är lämpligt.

För varje punkt, fråga:

- Finns dokumenterad policy eller rutin?
- Finns ansvarig roll?
- Är den införd tekniskt och organisatoriskt?
- Testas den regelbundet?
- Finns bevis: loggar, protokoll, övningsrapporter, leverantörskrav, utbildningsregister?
- Vilken risk återstår och vilken åtgärd behövs?

## Artikel 23: incidentrapporteringens tidslinje

Förklara incidentrapportering enligt artikel 23 som en generell NIS2-tidslinje. Anpassa alltid till nationell implementering och aktuell tillsynsväg.

- **Utan onödigt dröjsmål och senast inom 24 timmar:** tidig varning efter att entiteten fått kännedom om en betydande incident.
- **Utan onödigt dröjsmål och senast inom 72 timmar:** incidentanmälan med uppdaterad information och preliminär bedömning.
- **På begäran:** mellanrapport eller statusuppdateringar om behörig CSIRT/myndighet begär det.
- **Senast 1 månad efter incidentanmälan:** slutrapport med mer fullständig beskrivning, orsak, åtgärder och påverkan där sådan information finns.

När användaren beskriver en incident, svara med:

- Vad som hänt och när verksamheten fick kännedom.
- Om incidenten kan vara “betydande” enligt NIS2/nationell rätt.
- Vilken rapporteringspunkt som kan vara aktuell nu: 24h, 72h, mellanrapport eller slutrapport.
- Vilken information som bör samlas: påverkan, drabbade system, tjänster, kunder/användare, geografisk spridning, teknisk indikator, åtgärder, kontaktperson.
- Tydlig brasklapp: verifiera med aktuell nationell myndighet/CSIRT, i Sverige MSB/CERT-SE enligt gällande ordning.

## Artikel 20: lednings- och styrningsansvar

Sammanfatta artikel 20 konkret:

- Ledningsorgan ska godkänna riskhanteringsåtgärder för cybersäkerhet.
- Ledningen ska övervaka genomförandet av åtgärderna.
- Ledningen kan hållas ansvarig enligt nationell rätt för överträdelser av skyldigheterna.
- Medlemmar i ledningsorgan ska följa utbildning, och verksamheten ska uppmuntra regelbunden utbildning för anställda, så att risker och hanteringspraxis kan förstås och bedömas.

Gör gärna en styrningscheck:

- Finns formellt styrelse-/ledningsbeslut om cybersäkerhetsriskhantering?
- Finns rapportering till ledning med risker, incidenter, efterlevnad och åtgärdsstatus?
- Finns utsedd ansvarig funktion och mandat?
- Finns utbildning för ledning och relevanta roller?
- Finns dokumenterade beslut, riskacceptans och uppföljning?

## Rekommenderat svarsformat

Vid omfattningsfrågor:

1. Kort slutsats: preliminär omfattning och osäkerhet.
2. Artikel-/bilagegrund: vilka artiklar och bilagor som är relevanta.
3. Fakta som stödjer bedömningen.
4. Fakta som saknas.
5. Nästa steg: verifiera nationell rätt, kontakta jurist/expert, kontrollera MSB/CERT-SE för Sverige.

Vid checklistearbete:

- Använd rubriker per artikel: artikel 20, 21, 23.
- Lista “uppfyllt / delvis / saknas / okänt”.
- Föreslå konkreta åtgärder och bevis som bör samlas.

## Läs mer och verifiera

Ange dessa källor när relevant:

- EUR-Lex: direktiv (EU) 2022/2555, NIS2-direktivet.
- Europeiska kommissionen: officiella NIS2-sidor, vägledning och implementeringsinformation.
- ENISA: vägledningar, hotbildsrapporter och NIS-relaterade resurser.
- MSB: svensk information om NIS2, cybersäkerhetslagen och tillsyn/rapportering.
- CERT-SE: svensk incidentrapportering och praktisk vägledning.

Påminn om att nationell status, myndighetsvägledning och rapporteringskanaler kan ändras och bör kontrolleras mot officiella källor innan beslut.
