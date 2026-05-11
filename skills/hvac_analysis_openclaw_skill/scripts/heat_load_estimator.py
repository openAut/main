#!/usr/bin/env python3
"""
Heat Load Estimator — transmission and ventilation losses.

Functions:
- transmission_load(u_value, area_m2, delta_t) -> float   [W]
- ventilation_load(airflow_ls, delta_t, efficiency=0.0) -> float   [W]

Usage from bash_tool:
    python3 scripts/heat_load_estimator.py \\
        --u 0.3 --area 150 --dt 22 \\
        --airflow 25 --recovery 0.75

Formulas:
    Q_transmission = U × A × ΔT
    Q_ventilation  = ρ × c_p × V̇ × ΔT × (1 − η)
      where ρ = 1.2 kg/m³, c_p = 1000 J/(kg·K), η = heat recovery efficiency
"""

import argparse


def transmission_load(u_value: float, area_m2: float, delta_t: float) -> float:
    """
    Heat loss through building envelope.

    Parameters: U (W/m²·K), A (m²), ΔT (°C)
    Returns: heat loss in W
    Formula: Q = U × A × ΔT
    """
    return u_value * area_m2 * delta_t


def ventilation_load(airflow_ls: float, delta_t: float, efficiency: float = 0.0) -> float:
    """
    Heat loss due to ventilation (outdoor air heating).

    Parameters:
        airflow_ls  — outdoor airflow in l/s
        delta_t     — temperature difference indoor minus outdoor (°C)
        efficiency  — heat recovery efficiency (0–1), default 0 (no recovery)
    Returns: heat loss in W
    Formula: Q = ρ × c_p × V̇ × ΔT × (1 − η)
      ρ = 1.2 kg/m³, c_p = 1000 J/(kg·K)
    """
    airflow_m3s = airflow_ls / 1000.0
    rho = 1.2        # kg/m³
    cp = 1000.0      # J/(kg·K)
    return rho * cp * airflow_m3s * delta_t * (1.0 - efficiency)


def main():
    parser = argparse.ArgumentParser(
        description="Estimate building heat loss — transmission and ventilation."
    )
    parser.add_argument("--u", type=float, help="U-value of envelope (W/m²·K)")
    parser.add_argument("--area", type=float, help="Envelope area (m²)")
    parser.add_argument("--dt", type=float, required=True,
                        help="Indoor–outdoor temperature difference (°C)")
    parser.add_argument("--airflow", type=float,
                        help="Outdoor airflow (l/s)")
    parser.add_argument("--recovery", type=float, default=0.0,
                        help="Heat recovery efficiency 0–1 (default: 0)")
    args = parser.parse_args()

    print(f"\nHeat load estimate  (ΔT = {args.dt} °C)")
    print()

    total = 0.0

    if args.u is not None and args.area is not None:
        q_trans = transmission_load(args.u, args.area, args.dt)
        total += q_trans
        print(f"Transmission (Q = U × A × ΔT):")
        print(f"  U = {args.u} W/m²·K,  A = {args.area} m²")
        print(f"  Q_transmission = {q_trans:.0f} W  ({q_trans/1000:.2f} kW)")
        print()

    if args.airflow is not None:
        q_vent = ventilation_load(args.airflow, args.dt, args.recovery)
        total += q_vent
        eta_pct = args.recovery * 100
        print(f"Ventilation (Q = ρ·c_p·V̇·ΔT·(1−η)):")
        print(f"  Airflow = {args.airflow} l/s,  η = {eta_pct:.0f} %")
        print(f"  Q_ventilation = {q_vent:.0f} W  ({q_vent/1000:.2f} kW)")
        print()

    if args.u and args.airflow:
        print(f"Total estimated heat loss: {total:.0f} W  ({total/1000:.2f} kW)")


if __name__ == "__main__":
    main()
