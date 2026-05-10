#!/usr/bin/env python3
"""
Heat Load Estimator.

Provides simple functions to estimate heating load for buildings based
on envelope heat transfer and ventilation losses.

Functions:
- transmission_load(u_value: float, area_m2: float, delta_t: float) -> float
- ventilation_load(density: float, specific_heat: float, airflow_m3_s: float, delta_t: float) -> float

All loads are returned in watts (W).

Note: These calculations are simplified and intended for preliminary estimates.
"""

def transmission_load(u_value: float, area_m2: float, delta_t: float) -> float:
    """
    Estimate the heat loss through a building envelope (transmission).

    Parameters
    ----------
    u_value : float
        Thermal transmittance (W/m²·K) of the envelope.
    area_m2 : float
        Area of the envelope (m²).
    delta_t : float
        Temperature difference between indoors and outdoors (°C).

    Returns
    -------
    float
        Heat loss in watts (W) due to transmission.

    Formula:
        Q = U * A * ΔT
    """
    return u_value * area_m2 * delta_t

def ventilation_load(density: float, specific_heat: float, airflow_m3_s: float, delta_t: float) -> float:
    """
    Estimate the heat loss due to ventilation (outdoor air heating).

    Parameters
    ----------
    density : float
        Air density (kg/m³). Use 1.2 kg/m³ for dry air at ~20 °C.
    specific_heat : float
        Specific heat capacity of air (kJ/kg·K). Use 1.0 kJ/kg·K (approx. 1000 J/kg·K).
    airflow_m3_s : float
        Outdoor airflow rate (m³/s).
    delta_t : float
        Temperature difference between indoors and outdoors (°C).

    Returns
    -------
    float
        Heat loss in watts (W) due to ventilation.

    Formula:
        Q = ρ * c_p * V̇ * ΔT
    """
    # Convert specific heat to J/kg·K
    return density * (specific_heat * 1000.0) * airflow_m3_s * delta_t

if __name__ == "__main__":
    # Example usage
    u = 0.5  # W/m²·K
    area = 200.0  # m²
    delta_t = 20.0  # °C
    trans_loss = transmission_load(u, area, delta_t)
    print(f"Transmission heat loss: {trans_loss:.1f} W")

    density = 1.2  # kg/m³
    cp = 1.0  # kJ/kg·K
    airflow = 0.1  # m³/s
    vent_loss = ventilation_load(density, cp, airflow, delta_t)
    print(f"Ventilation heat loss: {vent_loss:.1f} W")