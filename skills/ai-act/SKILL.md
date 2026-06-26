---
name: ai-act
description: "Answer EU AI Act scope, risk classes, roles, obligations, and timeline as knowledge support."
permissions:
  knowledge_only: true
  tools: none
  network: none
  exec: none
---

# AI Act Skill

Use this skill when the user asks about the EU Artificial Intelligence Act, Regulation (EU) 2024/1689, including scope, exclusions, risk classes, provider/deployer/importer/distributor obligations, GPAI/foundation-model rules, prohibited practices, high-risk systems, transparency duties, conformity assessment, penalties, or the staged timeline.

## Purpose and boundaries

- Provide **knowledge support**, practical orientation, and structured checklists.
- Do **not** present the answer as legal advice. For binding interpretation, enforcement risk, contract wording, or compliance sign-off, recommend qualified legal/compliance counsel.
- Prefer the official regulation text and current EU Commission/AI Office guidance when available, because delegated acts, codes of practice, harmonised standards, guidance, and enforcement practice are moving.
- If current dates, guidance, standards, codes of practice, or national authorities matter, verify with web/official sources before answering.
- Be explicit about uncertainty: say what is in the Regulation, what is guidance/implementation, and what may still evolve.

## Fast answer pattern

For most AI Act questions, answer in this order:

1. **Short conclusion** — one or two sentences.
2. **Scope/role** — who is acting as provider, deployer, importer, distributor, product manufacturer, authorised representative, or GPAI provider.
3. **Risk class** — prohibited, high-risk, limited/transparency-risk, GPAI/systemic-risk GPAI, or minimal/no specific AI Act duties.
4. **Main obligations** — bullet list by role.
5. **Timeline** — when the relevant rules apply.
6. **Caveat** — “knowledge support, not legal advice”; mention official sources if the issue is high-stakes.

## Regulation identity

- Legal act: **Regulation (EU) 2024/1689** laying down harmonised rules on artificial intelligence, commonly called the **AI Act**.
- Publication: OJ L, 12 July 2024.
- Entry into force: **1 August 2024** (20 days after publication).
- General application: **2 August 2026**, with staged earlier/later dates.

## Scope checklist

The AI Act broadly covers AI systems placed on the EU market, put into service, or used in the EU, and can also apply extraterritorially when outputs are used in the EU.

Check:

- Is there an **AI system** as defined by the Act? In short: a machine-based system designed to operate with varying autonomy, that may exhibit adaptiveness after deployment, and that infers from input how to generate outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments.
- Is it placed on the market, put into service, or used in the EU?
- Is the actor a provider, deployer, importer, distributor, authorised representative, product manufacturer, or GPAI model provider?
- Does an exclusion apply?

Common exclusions/limits to mention:

- Areas outside EU law competence are outside scope.
- National security exemptions.
- Military, defence, or national security purposes.
- Certain research, testing, and development activities before market placement/putting into service.
- Purely personal, non-professional use by natural persons.
- Free and open-source components have special treatment, but open source is not a blanket exemption, especially for high-risk systems or GPAI obligations.

## Risk classes and how to classify

### 1. Prohibited / unacceptable risk

These are banned after the relevant application date. Typical categories include:

- Harmful manipulative or deceptive techniques.
- Exploitation of vulnerabilities due to age, disability, or socio-economic situation causing/significantly likely to cause harm.
- Social scoring by public authorities or private actors in prohibited ways.
- Certain predictive policing based solely/profiling-type risk assessments.
- Untargeted scraping of facial images to build facial recognition databases.
- Emotion recognition in workplaces and educational institutions, except narrow medical/safety exceptions.
- Biometric categorisation to infer sensitive characteristics.
- Certain real-time remote biometric identification in publicly accessible spaces for law enforcement, subject to narrow exceptions and safeguards.

### 2. High-risk AI systems

High-risk systems have the heaviest obligations. Two main routes:

- **Product safety route:** AI is a safety component of, or itself is, a product covered by listed EU harmonisation legislation in Annex I and requires third-party conformity assessment.
- **Use-case route:** AI falls under Annex III areas, such as biometrics, critical infrastructure, education/vocational training, employment/work management, access to essential private/public services and benefits, law enforcement, migration/asylum/border control, administration of justice, and democratic processes.

Important nuance:

- Some Annex III systems may be exempt from high-risk classification when they do not pose a significant risk of harm to health, safety, or fundamental rights and meet the Act’s conditions, but providers must document the assessment before placing on the market/putting into service.

### 3. Limited risk / transparency obligations

Certain systems are allowed but must satisfy transparency duties, for example:

- AI systems intended to interact directly with natural persons: disclose that the person is interacting with AI unless obvious.
- AI-generated or manipulated image, audio, or video content: label/disclose artificial generation/manipulation where required.
- Emotion recognition or biometric categorisation systems: inform exposed natural persons, unless lawfully used for law enforcement under conditions.
- Deepfakes: disclose artificial generation/manipulation, subject to exceptions.

### 4. GPAI models and systemic risk GPAI

General-purpose AI (GPAI) model providers have separate duties. GPAI models are models that display significant generality and can competently perform a wide range of distinct tasks and be integrated into many downstream systems.

Typical GPAI provider obligations:

- Maintain technical documentation.
- Provide information/instructions to downstream AI system providers.
- Comply with EU copyright law and publish a sufficiently detailed summary of training content.
- Put in place a policy to comply with copyright/TDM reservations.

Additional obligations for GPAI models with systemic risk:

- Model evaluation, including adversarial testing where appropriate.
- Assess and mitigate systemic risks.
- Track, document, and report serious incidents.
- Ensure adequate cybersecurity protection.

### 5. Minimal/no specific AI Act duties

Many AI systems have no specific AI Act obligations beyond general laws and voluntary codes, if they are not prohibited, high-risk, transparency-risk, or GPAI-covered. Still mention other law may apply: GDPR, product safety, consumer protection, labour law, sector rules, public procurement, IP/copyright, discrimination law.

## Role-specific obligations

### Providers of high-risk AI systems

Core duties include:

- Establish and maintain a risk management system.
- Data governance for training/validation/testing data where used.
- Technical documentation.
- Logging/record-keeping capabilities.
- Transparency and instructions for use.
- Human oversight design.
- Accuracy, robustness, and cybersecurity.
- Quality management system.
- Conformity assessment before placing on the market/putting into service.
- CE marking and EU declaration of conformity where applicable.
- Registration in the EU database for certain high-risk systems.
- Post-market monitoring.
- Serious incident reporting and corrective actions.

### Deployers of high-risk AI systems

Core duties include:

- Use the system according to instructions.
- Ensure appropriate human oversight by competent, trained persons.
- Monitor operation and keep logs where under their control.
- Ensure input data is relevant and sufficiently representative for the intended purpose where the deployer controls input data.
- Inform provider/distributor and authorities where serious incidents or risks arise.
- Conduct a fundamental rights impact assessment when required, notably for certain public bodies and listed uses.
- Inform workers/representatives when high-risk AI is used in the workplace where required.

### Importers

Check that the non-EU provider has completed required conformity steps, documentation, CE marking, instructions, and authorised representative where required. Do not place non-compliant high-risk AI on the EU market; cooperate with authorities.

### Distributors

Verify CE marking, EU declaration/instructions, and provider/importer compliance indicators before making high-risk AI available. Act with due care, avoid making non-compliant systems available, and cooperate with authorities.

### Authorised representatives

Hold provider mandate, keep documentation available, cooperate with competent authorities, and perform tasks specified in the mandate.

### Product manufacturers

When a high-risk AI system is placed on the market/put into service together with a product under the manufacturer’s name/trademark, product manufacturers may have provider-like responsibilities.

### Deployers vs providers: common trap

A deployer can become a provider if they:

- Put their name/trademark on a high-risk AI system already on the market or in service.
- Make a substantial modification to a high-risk AI system.
- Modify the intended purpose so an AI system becomes high-risk.

## Timeline quick reference

Always verify if exact current application date matters, but use this baseline:

- **1 Aug 2024:** AI Act enters into force.
- **2 Feb 2025:** Prohibited AI practices rules apply; AI literacy obligation begins.
- **2 Aug 2025:** GPAI model obligations generally start applying; governance/AI Office and many penalty provisions begin applying. Some GPAI transitional rules apply for models already on the market.
- **2 Aug 2026:** Most of the AI Act applies, including most high-risk obligations and transparency obligations.
- **2 Aug 2027:** Certain high-risk AI obligations connected to products covered by Annex I apply; some obligations for GPAI models already placed on the market before 2 Aug 2025 also have later transitional application.

When answering about implementation, mention moving parts:

- Commission/AI Office guidance.
- Codes of practice for GPAI.
- Harmonised standards.
- National competent authorities and market surveillance.
- Delegated/implementing acts.
- Sector-specific interactions.

## Penalties — high-level only

Do not over-focus on fines unless asked. High-level:

- Prohibited practices can attract the highest administrative fines.
- Other non-compliance and supplying incorrect/incomplete information can attract lower but still significant fines.
- Exact caps depend on infringement type and undertaking size/turnover. Verify current text and national implementation context before giving numbers.

If giving numbers, state carefully:

- Up to EUR 35 million or 7% worldwide annual turnover for prohibited practices.
- Up to EUR 15 million or 3% for many other obligations.
- Up to EUR 7.5 million or 1% for supplying incorrect, incomplete, or misleading information.
- SMEs/startups may be subject to the lower of the percentages/amounts in certain cases; verify exact provision.

## Common answer templates

### “Is X allowed?”

Answer:

- “Likely allowed / likely prohibited / depends.”
- Classify: prohibited, high-risk, limited-risk, GPAI, minimal.
- Identify role and sector.
- List obligations and timeline.
- Caveat: not legal advice; verify official text/guidance for deployment decisions.

### “Are we provider or deployer?”

Ask or infer:

- Who develops or has the system developed?
- Who places it on the market or puts it into service under their name/trademark?
- Who determines intended purpose?
- Is anyone substantially modifying the system or changing intended purpose?
- Is it internal use only, customer-facing, or supplied to others?

Then map roles and warn that one organisation can hold multiple roles.

### “What do we need to do?”

Produce a checklist by risk class and role. For high-risk, split into:

- Classification and intended purpose.
- Governance/risk management.
- Data and technical documentation.
- Human oversight and transparency.
- Conformity assessment/CE/registration.
- Post-market monitoring and incident handling.
- Deployer controls and FRIA if relevant.
- Timeline and owners.

### “When does it apply?”

Give the staged timeline and then say: “If your case involves GPAI, prohibited practices, or Annex I product safety, the date may differ; I’d verify the latest guidance before you rely on it.”

## Questions to ask when facts are missing

Ask only the minimum needed:

- What does the system do and what outputs does it produce?
- Who built it and under whose name is it supplied/used?
- Who uses it, in what country, and for what intended purpose?
- Is it used for employment, education, essential services, law enforcement, biometrics, critical infrastructure, healthcare/product safety, migration, justice, or democratic processes?
- Does it interact with people, generate content/deepfakes, perform biometric categorisation, emotion recognition, or make/recommend decisions about individuals?
- Is it a GPAI model, a downstream AI system using GPAI, or both?

## Style rules

- Be concise first, then structured.
- Use bullets and checklists.
- Distinguish “Act says” from “best practice” from “still evolving”.
- In Swedish chats, answer in Swedish unless the user asks otherwise. Use terms like “leverantör (provider)”, “användare/införare (deployer)”, “högrisk”, “förbjuden AI-praktik”, and “transparenskrav”.
- Never claim certainty on borderline classification without enough facts.
- Never say “compliant” as a final legal conclusion; say “this looks aligned with the main AI Act requirements, subject to legal review.”

## Source hints

Preferred sources when verification is needed:

- EUR-Lex text for Regulation (EU) 2024/1689.
- European Commission AI Act pages.
- EU AI Office guidance, codes of practice, and model/systemic-risk materials.
- National competent authority pages once designated.
- Harmonised standards references once published in the Official Journal.