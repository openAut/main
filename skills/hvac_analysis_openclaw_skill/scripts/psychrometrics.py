#!/usr/bin/env python3
"""
Psychrometric calculations.

Provides functions to compute saturation vapour pressure, humidity ratio,
and dew point temperature using approximate formulas.

Functions:
- saturation_vapor_pressure(temperature_c: float) -> float
- humidity_ratio(relative_humidity: float, temperature_c: float, pressure_pa: float = 101325.0) -> float
- dew_point(temperature_c: float, relative_humidity: float) -> float

All temperatures are in degrees Celsius and pressures in Pascals.

Note: These equations are approximations suitable for typical HVAC ranges.
"""

import math

def saturation_vapor_pressure(temperature_c: float) -> float:
    """
    Calculate saturation vapour pressure of water at a given temperature.

    Parameters
    ----------
    temperature_c : float
        Air temperature in degrees Celsius.

    Returns
    -------
    float
        Saturation vapour pressure in Pascals (Pa).

    Uses the Magnus formula (Tetens equation) for 0–50 °C.
    """
    # Constants for Magnus formula
    a = 17.62
    b = 243.12  # °C
    return 610.94 * math.exp((a * temperature_c) / (temperature_c + b))

def humidity_ratio(relative_humidity: float, temperature_c: float, pressure_pa: float = 101325.0) -> float:
    """
    Calculate humidity ratio (mass of water vapour per mass of dry air).

    Parameters
    ----------
    relative_humidity : float
        Relative humidity (0–1).
    temperature_c : float
        Dry-bulb temperature in °C.
    pressure_pa : float, optional
        Atmospheric pressure in Pa. Default is standard atmospheric pressure 101325 Pa.

    Returns
    -------
    float
        Humidity ratio (dimensionless, kg water/kg dry air).

    Formula:
        w = 0.62198 * (φ * P_ws) / (P - φ * P_ws)
    where P_ws is saturation vapour pressure at temperature T.
    """
    p_ws = saturation_vapor_pressure(temperature_c)
    p_w = relative_humidity * p_ws
    return 0.62198 * p_w / (pressure_pa - p_w)

def dew_point(temperature_c: float, relative_humidity: float) -> float:
    """
    Estimate the dew point temperature given dry-bulb temperature and relative humidity.

    Parameters
    ----------
    temperature_c : float
        Dry-bulb temperature in °C.
    relative_humidity : float
        Relative humidity (0–1).

    Returns
    -------
    float
        Dew point temperature in °C.

    Uses the Magnus formula.
    """
    # Saturation vapor pressure at dry-bulb temperature
    p_ws = saturation_vapor_pressure(temperature_c)
    # Actual vapor pressure
    p_w = relative_humidity * p_ws
    # Compute dew point using inverse of Magnus formula
    a = 17.62
    b = 243.12
    alpha = math.log(p_w / 610.94)
    dew_point_c = (b * alpha) / (a - alpha)
    return dew_point_c

if __name__ == "__main__":
    # Example usage
    T = 21.0  # °C
    RH = 0.3  # 30 %
    print(f"Saturation vapour pressure at {T} °C: {saturation_vapor_pressure(T):.1f} Pa")
    print(f"Humidity ratio: {humidity_ratio(RH, T):.6f} kg/kg")
    print(f"Dew point: {dew_point(T, RH):.2f} °C")