---
name: hvac_analysis
description: |
  Use this skill for any question about HVAC systems, ventilation, heating, cooling, or indoor climate in Swedish buildings. Trigger on: ventilation problems (dålig ventilation, högt CO₂, drag, lukt, fukt), heating/cooling issues (ojämn temperatur, värmeläckage, kyla), hydronic systems and balancing (injustering, radiatorer, fjärrvärme), heat pumps (värmepump, luftvärmepump, bergvärme), energy optimisation of HVAC (besparingar, driftsoptimering, VFD, VAV, CAV), BMS/automation questions (styrning, DUC, setpoints, sensorer), OVK and Swedish regulatory compliance (Boverket BBR, Folkhälsomyndigheten, Arbetsmiljöverket, OVK), and commissioning or troubleshooting of FTX/FT/F/S systems, AHU, chillers, district heating, hydronic loops, or any building services question. Always use this skill even when the user asks briefly — e.g. "varför är det kallt på övre plan?" or "hur sparar man energi på ventilation?" — because the structured workflow, Swedish regulations, and calculation tools it provides are always relevant.
---

# Purpose
Provide a structured methodology to analyse and improve HVAC systems in residential, commercial, and industrial Swedish buildings. The skill diagnoses ventilation, heating, cooling, indoor climate, and control problems; suggests measurements and corrective actions; emphasises energy efficiency; and references Swedish regulations (Boverket, Folkhälsomyndigheten, Arbetsmiljöverket) and OVK.

# Reference files — when to read them
Load reference files on demand using the `view` tool. Read only what is relevant to the current question.

| Topic | File |
|---|---|
| Swedish regulations, airflow limits, CO₂, OVK intervals | `references/swedish_regulations.md` |
| OVK details (procedure, intervals, responsibilities) | `references/ovk.md` |
| Ventilation system types S/F/FT/FTX/CAV/VAV | `references/ventilation_systems.md` |
| Heating systems: district heating, heat pumps, boilers | `references/heating_systems.md` |
| Cooling: DX, chilled water, free cooling, splits | `references/cooling_systems.md` |
| Hydronic systems and balancing | `references/hydronic_systems.md` |
| BMS and control strategies | `references/controls_and_bms.md` |
| Indoor climate parameters (temp, humidity, CO₂, noise) | `references/indoor_climate.md` |
| Energy optimisation strategies | `references/energy_optimization.md` |
| Troubleshooting guide | `references/troubleshooting.md` |
| Commissioning and start-up | `references/commissioning.md` |

For novel or complex issues, also read the most relevant example file in `examples/`.

# Calculation tools — when to run them
Use `bash_tool` to run scripts for numerical calculations. Always show inputs, formula, and result.

| Calculation | Script | When to run |
|---|---|---|
| Minimum outdoor airflow (BBR/AFS) | `scripts/airflow_calculator.py` | Any airflow requirement check |
| Heat loss through envelope or ventilation | `scripts/heat_load_estimator.py` | Heating load estimates |
| Humidity ratio, dew point, saturation pressure | `scripts/psychrometrics.py` | Moisture/condensation analysis |

Example — call a function from the airflow calculator:
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from airflow_calculator import required_airflow_residential, required_airflow_school_or_office
area, occupants = 120, 4
print(f'Residential: {required_airflow_residential(area, occupants):.1f} l/s')
print(f'Office: {required_airflow_school_or_office(area, occupants):.1f} l/s')
"
```

# Required inputs
Before analysis, collect or estimate:
- **Building:** type, year of construction, floor area, number of occupants, operating schedule, climate zone, renovation history.
- **HVAC:** ventilation type (S, F, FT, FTX, CAV, VAV), heating (district heating, heat pump, boiler, electric), cooling (DX, chiller, free cooling, split), hydronic details (pumps, valves, coils), heat recovery type, BMS.
- **Symptoms:** when and where problems occur, affected rooms/zones, seasonal and diurnal patterns, noise, smell, humidity, temperature deviation, CO₂ readings.

# Workflow
1. **Identify problem category:** Determine whether the issue relates to airflow, temperature, humidity, pressure, hydronics, controls, energy, occupancy, or building envelope.
2. **Load relevant reference files** using the `view` tool (see table above).
3. **Check operating conditions:** Verify schedules, setpoints, fan/pump operation, valve positions, sensor values, alarm history, trend logs.
4. **Evaluate ventilation:** Supply/extract flows, pressure balance, filter pressure drop, heat recovery efficiency, damper operation, fan speed, duct restrictions.
5. **Evaluate heating and cooling:** Supply/return temperatures, ΔT, flow rates, coil operation, compressor staging, heat pump behaviour, hydronic balancing.
6. **Evaluate indoor climate:** CO₂, relative humidity, operative temperature, draught risk, noise, odours.
7. **Evaluate energy performance:** Look for simultaneous heating/cooling, excessive airflow, incorrect scheduling, bypassed heat recovery, short cycling, pump overcapacity, sensor drift.
8. **Check regulatory compliance:** Verify minimum airflow (BBR 9:2 for residences; AFS 2020:1 §22 for offices/schools), CO₂ limits (FoHMFS 2014:18), OVK intervals (PBF 2011:338). Read `references/swedish_regulations.md` for details.
9. **Run calculations** via bash_tool when numerical verification is needed.
10. **Recommend measures:** No-cost operational changes → control optimisation → maintenance and balancing → component upgrades → system redesign.
11. **Provide structured output** (see Output format).

# HVAC principles
- **Measure before acting:** Verify flow rates, pressures, temperatures, and CO₂ before recommending replacement.
- **Separate symptoms from root causes:** Cold rooms may be due to airflow imbalance, not a faulty heater.
- **System thinking:** Evaluate entire airflow paths, pressure relations, occupancy patterns, control sequences, heat recovery, and building envelope interactions.
- **Prefer optimisation before replacement:** Adjust schedules, setpoints, balancing, and cleaning before replacing equipment.
- **Use SI units and show formulas** when calculating.
- **Radon awareness:** Negative building pressure (common in F-systems and poorly balanced FT-systems) can draw radon-laden air from the ground. Flag this risk when relevant.

# Diagnostic principles
- **Document assumptions** and uncertainties clearly.
- **Recommend qualified personnel** for safety-critical work: refrigerant systems, combustion, electrical faults, mould, legionella, smoke/fire dampers, pressure vessels, gas systems.
- **Prioritise occupant health and safety** in all recommendations.

# Calculation rules
Always show formulas and units. Key formulas:

**Minimum outdoor airflow — residences (BBR 9:2):**
$$q = \max(0.35\,\mathrm{l/s \cdot m^2} \times A,\ 4\,\mathrm{l/s/person} \times N)$$

**Minimum outdoor airflow — schools/offices at sedentary work (AFS 2020:1 §22):**
$$q = 0.35\,\mathrm{l/s \cdot m^2} \times A + 7\,\mathrm{l/s/person} \times N$$

**Ventilation heat loss:**
$$Q_{\text{vent}} = \rho \, c_p \, \dot{V} \, (T_{\text{in}} - T_{\text{out}})$$

**Transmission heat loss:**
$$Q = U \times A \times \Delta T$$

Run scripts via bash_tool for numerical results (see Calculation tools above).

# Swedish regulatory summary
| Topic | Value | Source |
|---|---|---|
| Min. airflow, residences (area-based) | 0.35 l/s·m² | BBR 9:2 |
| Min. airflow, residences (person-based) | 4 l/s/person | BBR 9:2 |
| Min. airflow, offices/schools (sedentary) | 7 l/s/person + 0.35 l/s·m² | AFS 2020:1 §22 |
| CO₂ — insufficient ventilation | > 1 000 ppm | FoHMFS 2014:18 |
| CO₂ — well-ventilated buildings | 600–800 ppm | FoHMFS 2014:18 |
| Indoor RH, heating season | 20–40 % (avg ~30 %) | FoHMFS 2014:18 |
| Absolute humidity difference (poor ventilation) | > 3 g/m³ indoor vs outdoor | FoHMFS 2014:18 |
| OVK — FT/FTX and public buildings | Every 3 years | PBF 2011:338 |
| OVK — exhaust-only (F) | Every 6 years | PBF 2011:338 |
| OVK — single-family FT/FTX | Initial inspection only | PBF 2011:338 |

Read `references/swedish_regulations.md` and `references/ovk.md` for complete details.

# Output format
Structure every response with these sections:

- **Situation:** Building, system, and observed issue.
- **Likely causes:** Most likely → possible → less likely, with brief reasoning.
- **Controls and measurements:** What to inspect or measure, where, why, and expected values.
- **Recommended actions:** Prioritised from no-cost → maintenance → controls → component replacement → system redesign.
- **Energy impact:** Low / Moderate / High — with explanation.
- **Regulation and compliance notes:** OVK implications, IAQ concerns, workplace regulations.
- **Risks and assumptions:** Uncertainties, assumptions, safety and health risks.
- **Questions for precision:** Additional data needed to refine the analysis.

See `examples/` for complete worked analyses following this format.
