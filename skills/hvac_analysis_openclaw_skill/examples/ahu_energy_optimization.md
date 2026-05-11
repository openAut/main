# Example: AHU Energy Optimisation

## Situation
An air handling unit (AHU) serving a commercial building operates continuously at full speed. Energy audits show that the AHU consumes a large share of the building’s electricity. The building has variable occupancy and uses an FTX system with a rotary heat exchanger. Filters are changed annually.

## Likely causes
1. **Continuous operation regardless of occupancy** – fans run at full speed even when spaces are unoccupied.
2. **No variable speed control** – fixed-speed fans do not adjust to lower demand.
3. **Poor control of heat recovery bypass** – heat exchanger may be bypassed unnecessarily, reducing efficiency.
4. **Dirty filters or fouled heat exchanger** – increased pressure drop leads to higher fan power.
5. **Leaks in ductwork** – supply air leaks before reaching spaces, causing fans to work harder.

## Controls and measurements
- **Measure fan power and airflow** at various times; identify periods of low occupancy.
- **Check control strategy**: Review BMS schedules and setpoints; verify if demand-controlled ventilation is enabled.
- **Inspect variable frequency drives (VFDs)**: Determine if fans can operate at reduced speed; measure static pressure at different speeds.
- **Examine heat exchanger operation**: Ensure rotary wheel operates and control valve/bypass damper modulates correctly.
- **Check filters and ducts**: Measure pressure drop across filters; inspect ducts for leaks and insulation quality.
- **Review occupancy patterns** and adjust schedules accordingly.

## Recommended actions
1. Implement schedule control: reduce fan speed or shut down the AHU during unoccupied periods(Energimyndigheten ET 2016:02).
2. Install or commission VFDs on supply and exhaust fans; program them to maintain required airflow and pressure(Energimyndigheten ET 2016:02).
3. Enable demand-controlled ventilation using CO₂ sensors(Energimyndigheten ET 2016:02).
4. Check and clean filters and heat exchanger to reduce pressure drop(Energimyndigheten ET 2016:02).
5. Seal duct leaks and improve insulation(Energimyndigheten ET 2016:02).
6. Optimise heat recovery control: avoid bypassing the heat exchanger when heat recovery is beneficial.

## Energy impact
High: Continuous full-speed operation wastes significant energy. Implementing VFDs, demand control, and improved scheduling can reduce fan energy consumption by 20–50 %. Heat recovery optimisation can further reduce heating/cooling energy.

## Regulation and compliance notes
- Ensure minimum ventilation flows are maintained during occupancy (see Swedish regulations).
- Adjustments must not compromise indoor air quality or occupant comfort.
- Document energy savings for future energy declarations.

## Risks and assumptions
- Installation of VFDs requires electrical work and may need upgrades to motor control centres.
- Incorrectly configured demand control may underventilate spaces.
- Balancing supply and exhaust flows at variable speeds requires careful commissioning.

## Questions for precision
- Are there existing VFDs on the fans?
- What is the building’s occupancy schedule?
- Are CO₂ or occupancy sensors installed?
- What is the current heat recovery efficiency?