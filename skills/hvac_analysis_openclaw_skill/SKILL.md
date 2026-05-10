---
name: hvac_analysis
description: |
  Structured support for analyzing ventilation, heating, cooling, indoor climate, energy optimisation, hydronic balancing, and troubleshooting in Swedish buildings. The skill uses Swedish regulations and industry guidelines to diagnose HVAC issues, propose measurements and actions, and ensure compliance.
---
# Purpose
Provide a structured methodology to analyse and improve HVAC systems in residential, commercial, and industrial buildings. The skill helps identify ventilation, heating, cooling, indoor climate, and control problems; suggests measurements and corrective actions; emphasises energy efficiency; and references Swedish regulations (Boverket, Folkhälsomyndigheten, Arbetsmiljöverket) and the obligatory ventilation control (OVK).

# When to use
Use this skill whenever a user asks about:
- Ventilation problems: insufficient airflow, high CO₂, odours, humidity.
- Heating or cooling performance issues: uneven temperature, poor comfort, high energy use.
- Hydronic system imbalance or poor heat distribution.
- Control or automation questions: scheduling, setpoints, sensors, alarms.
- Energy optimisation or commissioning of HVAC systems.
- Compliance with Swedish ventilation rules or OVK.
- Design or assessment of S, F, FT, FTX, CAV, VAV systems, heat pumps, district heating, hydronic systems.

# Required inputs
Before analysis, collect or estimate:
- **Building information:** type (apartment, office, school, etc.), year of construction, floor area, number of occupants, operating schedule, climate zone, renovation history.
- **HVAC system information:** type of ventilation (S, F, FT, FTX, CAV, VAV), heating (district heating, heat pump, boiler, electric), cooling (DX, chiller, free cooling, split), hydronic details (pumps, valves, coils), heat recovery type, control system/BMS.
- **Symptoms:** when and where problems occur, affected rooms or zones, seasonal and diurnal patterns, noise, smell, humidity, temperature deviation, CO₂ measurements.

# Workflow
1. **Identify problem category**: Determine whether the issue relates to airflow, temperature, humidity, pressure, hydronics, controls, energy, occupancy, or envelope interaction.
2. **Check operating conditions**: Verify schedules, setpoints, fan and pump operation, valve positions, sensor values, alarm history, and trend logs.
3. **Evaluate ventilation**: Measure supply and extract airflows, pressure balance, filter pressure drop, heat recovery efficiency, damper operation, fan speed, and duct restrictions.
4. **Evaluate heating and cooling**: Check supply and return temperatures, delta‑T, flow rates, coil operation, compressor staging, heat pump behaviour, and hydronic balancing.
5. **Evaluate indoor climate**: Assess CO₂, relative humidity, operative temperature, draught risk, noise, and odours.
6. **Evaluate energy performance**: Look for simultaneous heating and cooling, excessive airflow, incorrect scheduling, bypassed heat recovery, short cycling, pump overcapacity, constant operation, or sensor drift.
7. **Check regulatory context**: For Swedish projects, verify compliance with Boverket’s ventilation rules (minimum outdoor airflow 0.35 l/s·m² and ≥4 l/s per person in residences【307965596929412†L6814-L6819】; 7 l/s per person + 0.35 l/s·m² in schools and offices【476562234464538†L690-L697】), Folkhälsomyndigheten’s guidelines on CO₂ (indicative limit 1 000 ppm【470547024757844†L410-L425】), relative humidity (20–40 % during heating season【470547024757844†L378-L399】), and absolute humidity difference (<3 g/m³ difference between indoor and outdoor【470547024757844†L378-L399】), and OVK inspection intervals (3 or 6 years depending on system【763264260481650†L40-L60】).
8. **Assess energy impact and recommend measures**: Start with no‑cost operational changes, then control optimisation, maintenance and balancing, component upgrades, and finally system redesign.
9. **Provide structured output** (see Output format).

# HVAC principles
- **Measure before acting:** Always verify flow rates, pressures, temperatures, and CO₂ before recommending replacement.
- **Separate symptoms from root causes:** For example, cold rooms may be due to airflow imbalance, not a faulty heater.
- **Distinguish problem types:** Comfort, health, energy, capacity, or compliance issues may require different actions.
- **System thinking:** Evaluate entire airflow paths, pressure relations, occupancy patterns, control sequences, heat recovery, and building envelope interactions rather than isolating components.
- **Prefer optimisation before replacement:** Prioritise adjusting schedules, setpoints, balancing, and cleaning over replacing equipment.
- **Use SI units and show formulas** when performing calculations.

# Diagnostic principles
- **Document assumptions** and uncertainties clearly.
- **Recommend further investigation by qualified personnel** for safety‑critical issues such as refrigerant leaks, combustion systems, electrical faults, mould, legionella, smoke/fire dampers, pressure vessels, gas systems.
- **Prioritise occupant health and safety** in all recommendations.

# Calculation rules
Always provide formulas and units. Examples:
- Required outdoor airflow (residences): $$q = \max(0.35\,\mathrm{l/s·m²} \times A,\ 4\,\mathrm{l/s/person} \times N)$$ where \(A\) is floor area and \(N\) the number of occupants【307965596929412†L6814-L6819】.
- Required outdoor airflow (schools/offices): $$q = 0.35\,\mathrm{l/s·m²} \times A + 7\,\mathrm{l/s/person} \times N$$【476562234464538†L690-L697】.
- Heat load estimate: \(Q = \dot{m}\,c_p\,(T_{\text{in}}-T_{\text{out}})\) (see scripts).
- Ventilation heat loss: \(Q_{\text{vent}} = \rho\,c_p\,\dot{V}\,(T_{\text{in}}-T_{\text{out}})\).

# Swedish regulation context
The following points summarise key Swedish rules and guidelines:
- **Minimum airflow in residences:** Outdoor air supply must be at least 0.35 l/s per m² of floor area and not less than 4 l/s per person【307965596929412†L6814-L6819】. 
- **Minimum airflow in schools/offices:** At sedentary work, supply at least 7 l/s per person plus 0.35 l/s per m²【476562234464538†L690-L697】. 
- **CO₂ indicator:** Indoor CO₂ levels above 1 000 ppm signal insufficient ventilation; well‑ventilated buildings typically have 600–800 ppm【470547024757844†L410-L425】. Humans exhale ~15–20 l/h CO₂, raising indoor levels if ventilation is inadequate【470547024757844†L410-L425】.
- **Humidity guidelines:** Typical indoor relative humidity during heating season is 20–40 % (average around 30 %), and an absolute humidity difference >3 g/m³ between indoor and outdoor indicates poor ventilation【470547024757844†L378-L399】.
- **OVK intervals:** Functional ventilation checks must be performed every 3 years for buildings with supply and extract ventilation (FT, FTX) and certain public buildings, and every 6 years for exhaust‑only systems【763264260481650†L40-L60】.

See `references/swedish_regulations.md` for more details.

# Output format
When responding to a user, structure your answer using the following sections:

- **Situation:** Describe the building, system, and observed issue.
- **Likely causes:** List the most likely, possible, and less likely causes, with brief reasoning.
- **Controls and measurements:** Specify what to inspect or measure (airflow, temperatures, pressures, CO₂, humidity, sensors, etc.), where, why, and expected values.
- **Recommended actions:** Prioritise actions from no-cost operational adjustments to maintenance, balancing, controls optimisation, component replacement, and system redesign.
- **Energy impact:** Estimate whether the problem has low, moderate, or high energy impact and explain why.
- **Regulation and compliance notes:** Mention potential OVK implications, IAQ concerns, workplace regulations, and other compliance issues.
- **Risks and assumptions:** Highlight uncertainties, assumptions, and any safety or health risks.
- **Questions for precision:** List additional questions or data needed to refine analysis.

Refer to example files in `examples/` for sample analyses.

# Referencing
Whenever applicable, cite content from the reference files in the skill. Use the heading names (e.g. “Swedish regulations”, “Energy optimisation”) to refer the user to detailed documentation in the `references/` folder.