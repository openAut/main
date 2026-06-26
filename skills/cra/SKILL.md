---
name: cra
description: "EU Cyber Resilience Act (Regulation (EU) 2024/2847) – scope, obligations, timelines, vulnerability and incident reporting, connected hardware/IoT, open source, and economic-operator roles. Use for CRA compliance questions."
permissions:
  knowledge_only: true
  tools: none
  network: none
  exec: none
---

# EU Cyber Resilience Act (CRA)

Use this skill when answering questions about Regulation (EU) 2024/2847, the Cyber Resilience Act: scope, obligations, timelines, vulnerability/incident reporting, connected hardware/IoT products, product classes, open source, and economic-operator roles.

This is a knowledge aid, not legal advice. For compliance decisions, cite the Regulation and recommend qualified legal/compliance review.

## Primary sources

Prefer these over summaries:

- Regulation (EU) 2024/2847 of the European Parliament and of the Council on horizontal cybersecurity requirements for products with digital elements (Cyber Resilience Act), EUR-Lex ELI: `https://eur-lex.europa.eu/eli/reg/2024/2847/oj/eng`
- EUR-Lex CELEX: `32024R2847`
- Key CRA anchors to verify in the legal text before high-stakes answers:
  - Article 2: scope
  - Article 3: definitions
  - Article 4: free movement
  - Articles 7-8 and Annex III-IV: important and critical products with digital elements
  - Articles 13-14: manufacturer obligations and reporting obligations
  - Articles 16-20: authorised representatives, importers, distributors, and other cases where obligations apply
  - Articles 22-24: open-source software stewards and related administrative obligations
  - Article 27 and Annex I: essential cybersecurity requirements
  - Articles 28-31 and Annexes V-VIII: conformity assessment, EU declaration, CE marking, technical documentation
  - Articles 35-51: notification/conformity assessment bodies
  - Articles 52-54: market surveillance and safeguards
  - Articles 64-65: penalties and sanctions
  - Article 71: entry into force and application dates

## Legal nature

- CRA is an EU Regulation, not a directive: it is directly applicable in Member States without national transposition, though Member States designate authorities and set/implement penalties within the Regulation's framework.
- It creates horizontal cybersecurity requirements for placing products with digital elements on the EU market.
- It complements, and sometimes defers to, sector-specific EU rules where those rules already impose equivalent cybersecurity requirements.

## Scope

Core concept: a “product with digital elements” (PDE) is a software or hardware product and its remote data processing solutions, including software or hardware components placed on the market separately.

Usually in scope:

- Connected hardware and IoT devices: sensors, gateways, routers, cameras, PLC-like devices, smart home products, wearables, industrial connected equipment, connected building automation components.
- Embedded software/firmware supplied with hardware.
- Standalone software placed on the market, including apps and software components, where not exempt.
- Remote data processing solutions that are necessary for a product with digital elements to perform one of its functions.

Remember:

- “Placing on the market” and “making available on the market” are product-law concepts. The CRA follows the New Legislative Framework style.
- A product can be in scope even if the cybersecurity risk is low; risk affects obligations and assessment route, not basic scope.

## Exemptions and exclusions

Check Article 2 before answering definitively. Common exclusions/limitations include:

- Products already covered by certain sector-specific EU legislation with equivalent cybersecurity requirements, such as medical devices, in vitro diagnostic medical devices, motor vehicles/type approval, civil aviation, and marine equipment, to the extent specified.
- Products developed exclusively for national security or defence purposes, or products specifically designed to process classified information.
- Free and open-source software developed or supplied outside a commercial activity is generally not treated the same as commercial products placed on the market.
- SaaS/cloud services are not generally covered as standalone services, unless they are remote data processing solutions necessary for a product with digital elements to perform one of its functions. Do not overstate SaaS coverage.

## Open source steward regime

The CRA distinguishes commercial product manufacturers from open-source actors.

Key points:

- Free and open-source software not made available on the market in the course of a commercial activity is generally outside the ordinary manufacturer regime.
- Commercialisation indicators can include charging for the software, monetisation through support/hosting/technical services when linked to the software, or other commercial use patterns. Always check the definition and recitals for nuance.
- “Open-source software steward” is a dedicated role for certain legal persons, other than manufacturers, that systematically provide support for development of specific open-source products with digital elements intended for commercial activities, and ensure viability of those products.
- Open-source software stewards have lighter, administrative/security-process obligations than manufacturers. They are not simply treated as manufacturers solely because they support an open-source project.
- Do not tell community maintainers that they automatically have CRA manufacturer obligations. First ask: Is there a legal person? Is there commercial activity? Is software placed/made available on the EU market? Is the actor a manufacturer, steward, importer, distributor, or none?

## Roles

Use the economic-operator role before listing obligations:

- Manufacturer: develops/manufactures a product with digital elements, or has it designed/developed/manufactured, and markets it under its name or trademark, whether for payment or free of charge. Main compliance burden.
- Authorised representative: EU-based mandated representative for specified manufacturer tasks.
- Importer: places a third-country product with digital elements on the EU market. Must verify manufacturer compliance and act where non-compliance/risk exists.
- Distributor: makes a product available on the market. Must act with due care and verify required markings/documents/instructions.
- Open-source software steward: dedicated CRA role with specific obligations, not the same as manufacturer.
- Other cases: a distributor/importer may take on manufacturer obligations if it markets under its own name/trademark or substantially modifies a product.

## Product classes

Default: products with digital elements are subject to baseline essential cybersecurity requirements.

Higher-risk classifications:

- Important products with digital elements: listed in Annex III, split into Class I and Class II. They trigger stricter conformity assessment routes.
- Critical products with digital elements: listed in Annex IV. They are the highest CRA category and may require European cybersecurity certification schemes where specified.

Examples to check against Annex III/IV rather than relying on memory:

- Identity/access management, privileged access management, password managers.
- Network management, security monitoring, SIEM/SOAR, vulnerability scanners.
- Firewalls, intrusion detection/prevention, routers/modems, switches, VPN products.
- Operating systems, hypervisors/container runtimes, microprocessors/microcontrollers with security functionality.
- Smart home products with security relevance, connected toys/baby monitors, wearable health-related products.
- Industrial automation/control products may fall into important classes depending on function.

Behavior rule: never classify a specific product as Class I/Class II/critical without checking Annex III/IV wording and the product's actual functions.

## Core obligations

For manufacturers, explain obligations in two bundles.

Product cybersecurity requirements (Annex I Part I):

- Design, develop, and produce products to ensure an appropriate level of cybersecurity based on risks.
- Supply products without known exploitable vulnerabilities, where feasible.
- Secure-by-default configuration, including possibility to reset to original state where appropriate.
- Protection against unauthorised access, appropriate authentication/identity/access controls.
- Data confidentiality, integrity, and availability protections.
- Minimise attack surfaces, limit incident impact, and provide security monitoring/logging where appropriate.
- Provide security updates and ensure vulnerabilities can be addressed.

Vulnerability handling requirements (Annex I Part II):

- Identify and document vulnerabilities/components, including a software bill of materials (SBOM) at least for internal/authority purposes as required by the Regulation.
- Address/remediate vulnerabilities without delay, including security updates.
- Have a coordinated vulnerability disclosure policy.
- Facilitate vulnerability reporting by users/third parties.
- Publicly disclose information about fixed vulnerabilities after security updates are available, where appropriate.

Manufacturer process/product-law obligations (mainly Article 13):

- Perform cybersecurity risk assessment and account for it during planning, design, development, production, delivery, and maintenance.
- Prepare technical documentation.
- Carry out the appropriate conformity assessment.
- Draw up EU declaration of conformity.
- Affix CE marking.
- Provide user instructions and security information.
- Keep documentation and declaration for the required period.
- Ensure vulnerability handling and security updates for the support period.
- State the support period; it must normally be at least five years unless the product is expected to be used for a shorter period.

## Reporting

Use this section carefully; reporting dates/details are high-risk facts. Verify Article 14 for exact wording.

Manufacturers must report through the CRA single reporting platform to the competent CSIRT and ENISA, as applicable, when they become aware of:

- An actively exploited vulnerability contained in the product with digital elements.
- A severe incident having an impact on the security of the product with digital elements.

Expected reporting sequence for actively exploited vulnerabilities:

- Early warning: without undue delay and in any event within 24 hours of becoming aware, indicating whether malicious exploitation is suspected.
- Vulnerability notification: without undue delay and in any event within 72 hours of becoming aware, with general information such as product, vulnerability, and corrective/mitigating measures.
- Final report: after a corrective or mitigating measure is available, including relevant details and, where appropriate, information enabling users to assess impact.

Expected reporting sequence for severe security incidents:

- Early warning: without undue delay and in any event within 24 hours of becoming aware.
- Incident notification: without undue delay and in any event within 72 hours of becoming aware.
- Final report: normally within one month after the incident notification, unless Article 14 provides a different case-specific deadline.

Also mention:

- Manufacturers may need to inform users without undue delay when the vulnerability/incident could adversely affect product security.
- CRA reporting overlaps with NIS2/GDPR/sectoral reporting in some cases. Do not assume one report satisfies all regimes; check applicable law and guidance.

## Harmonized standards and certification

- CRA uses EU product conformity architecture. Compliance may be demonstrated through harmonised standards, common specifications, or European cybersecurity certification schemes where available/applicable.
- Harmonised standards can create a presumption of conformity for covered requirements when cited in the Official Journal.
- If no harmonised standard exists, manufacturers still must meet essential requirements and choose the applicable conformity assessment path.
- For important/critical products, conformity assessment may require a notified body or certification route depending on class and available standards/schemes.
- Always separate “standard helps prove conformity” from “standard is the law”. The Regulation is binding; harmonised standards are a route to presumption of conformity.

## Sanctions

- Member States set rules on penalties and enforcement, but CRA sets maximum administrative fine bands.
- Highest tier: infringements of essential cybersecurity requirements and key manufacturer obligations can reach up to EUR 15 million or 2.5% of total worldwide annual turnover, whichever is higher.
- Other obligation infringements can reach up to EUR 10 million or 2% of worldwide annual turnover.
- Supplying incorrect, incomplete, or misleading information to authorities/notified bodies can reach up to EUR 5 million or 1% of worldwide annual turnover.
- Enforcement can also involve market surveillance measures: corrective actions, withdrawal, recall, prohibition/restriction of market availability.

## Timeline

Anchor dates from Article 71:

- 20 November 2024: publication in the Official Journal (verify if needed for citation).
- 10 December 2024: entry into force, 20 days after publication.
- 11 June 2026: provisions on conformity assessment bodies/notification infrastructure start applying (18 months after entry into force; verify exact article set in Article 71).
- 11 September 2026: Article 14 reporting obligations start applying (21 months after entry into force).
- 11 December 2027: most CRA obligations apply (36 months after entry into force).

Practical answer framing:

- “In force” does not mean “all obligations apply today.” Distinguish entry into force from application dates.
- For products already being designed now, advise preparing early because secure development, documentation, SBOM/vulnerability processes, support-period commitments, and conformity assessment take time.

## Connected hardware / IoT checklist

When asked about a connected hardware/IoT product, ask or infer:

1. What is the product and what digital elements does it include: device, firmware, app, cloud/remote processing?
2. Is it placed/made available on the EU market, and by whom?
3. Is the actor manufacturer, importer, distributor, authorised representative, or open-source steward?
4. Is it excluded by sector-specific legislation?
5. Does Annex III or IV classify it as important or critical?
6. What is the intended use and foreseeable misuse?
7. What support period/security update period is declared?
8. What vulnerability disclosure, SBOM, update, logging, access-control, and secure-default measures exist?
9. What conformity assessment route and standards/certification are planned?
10. What reporting process exists for actively exploited vulnerabilities and severe security incidents?

## Behavior rules

- Be precise and humble. Say when a point requires checking the Regulation, Annexes, Commission guidance, or national authority guidance.
- Do not present this as legal advice.
- Cite article/annex numbers for obligations, reporting, classifications, exemptions, and penalties whenever possible.
- For product classification, prefer: “likely / needs confirmation against Annex III/IV” rather than definitive claims from vague facts.
- For open source, avoid chilling overstatements. Distinguish community FOSS, commercial open-source distribution, manufacturer use of OSS in products, and open-source software stewards.
- For SaaS/cloud, do not say CRA broadly regulates all SaaS. Explain the remote-data-processing link to products with digital elements and mention other regimes may apply.
- For reporting deadlines, state the 24h/72h/final-report structure but advise verifying Article 14 and any ENISA/single-platform guidance for operational reporting.
- If asked “does CRA apply to us?”, answer with a short issue-spotting analysis and the missing facts needed, not a final legal conclusion.
- If current Commission guidance, harmonised standards, or implementing acts matter, use web search/fetch current official sources before answering.
