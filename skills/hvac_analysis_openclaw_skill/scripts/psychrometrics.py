#!/usr/bin/env python3
"""
Psychrometric calculations.

Functions:
- saturation_vapor_pressure(temperature_c) -> float   [Pa]
- humidity_ratio(relative_humidity, temperature_c, pressure_pa) -> float   [kg/kg]
- dew_point(temperature_c, relative_humidity) -> float   [°C]
- absolute_humidity(temperature_c, relative_humidity) -> float   [g/m³]

Usage from bash_tool:
    python3 scripts/psychrometrics.py --temp 21 --rh 0.30
    python3 scripts/psychrometrics.py --temp 21 --rh 0.30 --temp-outdoor 0 --rh-outdoor 0.85

The --temp-outdoor / --rh-outdoor flags calculate the absolute humidity
difference between indoor and outdoor air — useful for assessing ventilation
quality against the FoHMFS 2014:18 limit of 3 g/m³.

Note: Magnus formula, valid for 0–50 °C.
"""

import argparse
import math


def saturation_vapor_pressure(temperature_c: float) -> float:
    """Saturation vapour pressure [Pa] using Magnus formula."""
    a, b = 17.62, 243.12
    return 610.94 * math.exp((a * temperature_c) / (temperature_c + b))


def humidity_ratio(relative_humidity: float, temperature_c: float,
                   pressure_pa: float = 101325.0) -> float:
    """
    Humidity ratio [kg water / kg dry air].
    Formula: w = 0.62198 × (φ·P_ws) / (P − φ·P_ws)
    """
    p_ws = saturation_vapor_pressure(temperature_c)
    p_w = relative_humidity * p_ws
    return 0.62198 * p_w / (pressure_pa - p_w)


def dew_point(temperature_c: float, relative_humidity: float) -> float:
    """Dew point temperature [°C] using inverse Magnus formula."""
    p_ws = saturation_vapor_pressure(temperature_c)
    p_w = relative_humidity * p_ws
    a, b = 17.62, 243.12
    alpha = math.log(p_w / 610.94)
    return (b * alpha) / (a - alpha)


def absolute_humidity(temperature_c: float, relative_humidity: float) -> float:
    """
    Absolute humidity [g/m³].
    Formula: AH = (φ · P_ws · M_w) / (R · T)
      M_w = 18.015 g/mol, R = 8.314 J/(mol·K)
    """
    p_ws = saturation_vapor_pressure(temperature_c)
    p_w = relative_humidity * p_ws
    mw = 18.015  # g/mol
    r = 8.314    # J/(mol·K)
    t_k = temperature_c + 273.15
    return (p_w * mw) / (r * t_k)


def main():
    parser = argparse.ArgumentParser(
        description="Psychrometric calculations for HVAC analysis."
    )
    parser.add_argument("--temp", type=float, required=True,
                        help="Indoor dry-bulb temperature (°C)")
    parser.add_argument("--rh", type=float, required=True,
                        help="Indoor relative humidity (0–1)")
    parser.add_argument("--temp-outdoor", type=float, default=None,
                        help="Outdoor temperature (°C) — for humidity difference check")
    parser.add_argument("--rh-outdoor", type=float, default=None,
                        help="Outdoor relative humidity (0–1) — for humidity difference check")
    args = parser.parse_args()

    print(f"\nPsychrometric results")
    print(f"  Indoor: {args.temp} °C,  RH = {args.rh*100:.0f} %")
    print()
    print(f"  Saturation vapour pressure:  {saturation_vapor_pressure(args.temp):.1f} Pa")
    print(f"  Humidity ratio:              {humidity_ratio(args.rh, args.temp)*1000:.2f} g/kg")
    print(f"  Absolute humidity:           {absolute_humidity(args.temp, args.rh):.2f} g/m³")
    print(f"  Dew point:                   {dew_point(args.temp, args.rh):.1f} °C")

    if args.temp_outdoor is not None and args.rh_outdoor is not None:
        ah_in = absolute_humidity(args.temp, args.rh)
        ah_out = absolute_humidity(args.temp_outdoor, args.rh_outdoor)
        diff = ah_in - ah_out
        flag = " ⚠ exceeds FoHMFS 2014:18 limit of 3 g/m³" if diff > 3.0 else " ✓ within FoHMFS 2014:18 limit"
        print()
        print(f"  Outdoor: {args.temp_outdoor} °C,  RH = {args.rh_outdoor*100:.0f} %")
        print(f"  Outdoor absolute humidity:   {ah_out:.2f} g/m³")
        print(f"  Δ absolute humidity:         {diff:.2f} g/m³{flag}")


if __name__ == "__main__":
    main()
