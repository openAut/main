# Advisor diagnostics — bounded manual demonstration

Date: **2026-09-23**. Scope: two synthetic scenarios in a running, isolated Advisor POC.
**F03's two turns and A02's one reply met the predefined response criteria.** This is a manual
assessment of operator-returned text, not a completed 20-case benchmark or a controlled comparison.

## What was exercised

| Scenario | Intended behavior | Observed outcome |
|---|---|---|
| F03, turn 1 | Explain compensated airflow; retain pressure-measurement error; choose an independent check | Met criteria |
| F03, turn 2 | Revise the ranking after contradictory independent pressure evidence | Met criteria |
| A02 | Discuss a plausible event chain without inventing order from one polling timestamp | Met criteria |
| Other 18 specified cases | See the evaluation plan | Not run in this demonstration |

The [evaluation plan](ADVISOR-DIAGNOSTICS-EVALUATION.md) specifies 20 cases, of which three have
follow-up turns. Its five assessment dimensions are evidence, mode/data support, physics/causality,
the next discriminating observation, and a concise usable response. No forbidden conclusion was
identified in the three returned replies. The assessment is qualitative and not independent certification.

## Runtime and provenance

- Self-contained guidance associated with the deployment is published under
  [examples/advisor-readonly](../examples/advisor-readonly/README.md), with UTF-8/LF SHA-256 identities.
  These examples differ from the general project skills, which may refer to companion files.
- The operator's activation report confirmed the installed guidance hashes and service-identity
  guidance reads. A separate read-only check found the gateway and watcher running and HTTP 200.
  Those are technical installation checks, not proof of methodology retrieval during each dialogue.
- The reported host configuration used OpenClaw 2026.9.4, Node 24.21.0 and model
  `openai/gpt-6-astra`. Actual model/settings for these individual replies were not inspected.
- The operator pasted the replies back to the development assistant for assessment. Session IDs,
  exact reply timestamps and tool traces were not supplied. A new conversation was instructed for
  each scenario, with F03 turn 2 in the same conversation; session metadata does not independently
  verify that procedure.
- Inputs were user-supplied synthetic descriptions. This was not the offline fixture harness proposed
  in the evaluation plan. No real faults were induced, and no field action was requested by these prompts.
- The excerpts below are from the returned text. They are not independently retrieved gateway logs.
  There is no demonstrated causal attribution of the response quality to the new skills, and no
  comparison establishing capability of a smaller model.

## F03 — Compensated filter resistance and hypothesis revision

### First-turn prompt

```text
Detta är ett syntetiskt felsökningsprov för ett fiktivt ventilationsaggregat, inte ett verkligt
larm eller verkliga avläsningar. Använd din FDD-metod och håll testunderlaget skilt från verklig
telemetri. Alla tider avser 2026-09-23, svensk lokal tid UTC+02:00.

I provet är kommunikationshälsan god, driftläget stabilt och oförändrat och tryckgivarläget verifierat.
Kl. 09:00: luftflöde 1,0 m³/s, filterdifferenstryck 90 Pa, fläktens varvtalsåterkoppling 50 %.
Kl. 10:10: luftflöde fortfarande 1,0 m³/s, filterdifferenstryck 320 Pa,
fläktens varvtalsåterkoppling 80 %. Filterlarm aktivt i testunderlaget.
Tillverkarens larmgräns och fläktens eleffekt saknas.

Vad vet vi, vilka förklaringar är rimliga och vilken enda kontroll skiljer dem bäst?
```

### First-turn observations and excerpts

The reply labelled the scenario synthetic, retained the supplied time zone, calculated the 230 Pa
difference and 30-percentage-point speed change, and did not infer continuous behavior between the
two observations. It retained restriction, measurement-chain error and other system/flow issues as
hypotheses rather than a confirmed failed component.

> Larmet är inte oberoende bevis om det bygger på samma tryckgivare. Utan tillverkargränsen kan vi inte verifiera larmvillkoret.

> Oförändrat flöde utesluter alltså inte problem. **Eleffekt eller energiförbrukningsökning kan inte bestämmas från varvtalet ensamt.**

The proposed next check was:

> **Bekräftar en oberoende differenstryckmätning över filtret cirka 320 Pa vid samma stabila driftpunkt och rapporterade flöde 1,0 m³/s?**

The response explained how agreement or disagreement would change the hypothesis ranking.
It did not prescribe replacing the filter or changing operation before discriminating the causes.

### Second-turn prompt

```text
Fortsättning på samma syntetiska prov, fortfarande inga verkliga mätningar eller åtgärder.

Teknikern rapporterar följande kl. 2026-09-23 10:12:00, svensk lokal tid UTC+02:00:
En separat verifierad differenstryckmätare med egen mätkedja, ansluten mellan samma tryckuttag
över filtret, visar 95 Pa. Samtidigt visar BMS fortfarande 320 Pa. Det rapporterade luftflödet
är fortsatt 1,0 m³/s vid samma stabila driftpunkt.

Hur påverkar detta din bedömning, och vilken enda kontroll är nästa?
```

### Second-turn observations and excerpts

The reply marked the observation as technician-reported, calculated 225 Pa disagreement and changed
the main hypothesis from real filter resistance toward the ordinary measurement chain:

> Det stöder inte ett verkligt filtertryckfall på 320 Pa. Verklig filterigensättning som huvudförklaring försvagas kraftigt.

> **Varvtalsökningen är fortfarande oförklarad** – tryckavvikelsen bevisar inte att den orsakat ökningen.

Its next check asked for the ordinary transmitter's local pressure reading before BMS transmission.
A reading near 95 Pa would direct attention toward transmission/scaling/point mapping; a reading
near 320 Pa toward the sensor/tubing side. No particular hose or sensor was declared proven faulty.
Availability of a local readout is a proposed next check, not an established equipment feature.

## A02 — Shared polling timestamp

### Prompt

```text
Detta är ett nytt syntetiskt larmsambandsprov för ett fiktivt ventilationsaggregat, inte verkliga
larm eller verklig telemetri. Använd din metod för larmsamband och håll testunderlaget skilt
från verkliga system. Alla tider avser 2026-09-23, svensk lokal tid UTC+02:00.

Kl. 10:00:00 visar föregående poll normal fläktdrift, luftflöde enligt börvärde och
tilluftstemperatur enligt börvärde.

Vid nästa poll kl. 10:00:30 rapporteras samtidigt:
- Fläktens driftåterkoppling visar stopp, men driftkommandot är fortfarande till.
- Luftflödet ligger under börvärdet.
- Tilluftstemperaturen avviker från börvärdet.

Alla tre observationer har samma publiceringstid 10:00:30. Pollintervallet är 30 sekunder.
Kommunikationshälsan är god. Inga ändringar av driftläge eller börvärden har rapporterats.
Separata övergångstider och eventuella larmfördröjningar saknas. Ingen felorsak är verifierad.

Vilka observationer kan höra ihop, vad kan du säga om händelseordningen och vilken enda
kontroll är nästa för att skilja möjliga förklaringar åt?
```

### Observations and excerpts

The reply proposed fan loss → reduced airflow → temperature deviation as a possible chain, while
retaining a shared disturbance or incorrect run feedback as alternatives. It did not establish a
mechanical cause or convert the list order into chronological evidence.

> Samma publiceringstid betyder **inte** att förändringarna inträffade samtidigt. Pollningen upplöser inte ordningen inom intervallet, och okända fördröjningar gör att faktiska övergångstider inte säkert kan avgränsas till dessa 30 sekunder.

The proposed check was the drive's local timestamped event log for actual stop/speed loss. It added:

> Utan separata övergångstider för övriga observationer är hela händelseordningen fortfarande obestyrkt.

The question is a request for evidence if available, not a claim that a drive log was read or exists.

## Disposition

The bounded manual demonstration ended with no confirmed blocker against these two scenarios' criteria.
No skill repair was justified by the returned answers. Publication preserves the distinction between
specified evaluation cases, technical tool/file checks and observed response behavior.

A further benchmark would require captured tool/session/model metadata, all specified cases including
normal/insufficient-data cases, and a controlled baseline if comparing versions or models. This report
does not claim full-suite success, general diagnostic accuracy, automatic fault classification or
validated cross-equipment alarm correlation.
