#!/usr/bin/env python3
"""
Airflow Calculator for Swedish ventilation requirements.

Calculates minimum outdoor airflow rates for different occupancy types
based on Swedish regulations.

Functions:
- required_airflow_residential(area_m2, occupants) -> float   [l/s]
- required_airflow_school_or_office(area_m2, occupants) -> float  [l/s]

Usage from bash_tool:
    python3 scripts/airflow_calculator.py --area 120 --occupants 4 --type residential
    python3 scripts/airflow_calculator.py --area 500 --occupants 40 --type office

Sources:
    BBR 9:2 — residential minimum 0.35 l/s·m² and 4 l/s/person.
    AFS 2020:1 §22 — offices/schools minimum 7 l/s/person + 0.35 l/s·m².
"""

import argparse


def required_airflow_residential(area_m2: float, occupants: int) -> float:
    """
    Minimum outdoor airflow for a residential space.

    Formula: q = max(0.35 * area_m2, 4 * occupants)   [l/s]
    Source: BBR 9:2
    """
    return max(0.35 * area_m2, 4.0 * occupants)


def required_airflow_school_or_office(area_m2: float, occupants: int) -> float:
    """
    Minimum outdoor airflow for schools or offices (sedentary activities).

    Formula: q = 0.35 * area_m2 + 7 * occupants   [l/s]
    Source: AFS 2020:1 §22
    """
    return 0.35 * area_m2 + 7.0 * occupants


def main():
    parser = argparse.ArgumentParser(
        description="Calculate minimum outdoor airflow per Swedish regulations."
    )
    parser.add_argument("--area", type=float, required=True, help="Floor area in m²")
    parser.add_argument("--occupants", type=int, required=True, help="Number of occupants")
    parser.add_argument(
        "--type",
        choices=["residential", "office", "school", "both"],
        default="both",
        help="Building type (default: both)",
    )
    args = parser.parse_args()

    print(f"\nAirflow calculation")
    print(f"  Area:      {args.area} m²")
    print(f"  Occupants: {args.occupants}")
    print()

    if args.type in ("residential", "both"):
        q = required_airflow_residential(args.area, args.occupants)
        area_flow = 0.35 * args.area
        person_flow = 4.0 * args.occupants
        binding = "area-based" if area_flow >= person_flow else "person-based"
        print(f"Residential (BBR 9:2):")
        print(f"  Area-based:   {area_flow:.1f} l/s  (0.35 × {args.area})")
        print(f"  Person-based: {person_flow:.1f} l/s  (4 × {args.occupants})")
        print(f"  Required:     {q:.1f} l/s  [{binding} governs]")
        print()

    if args.type in ("office", "school", "both"):
        q = required_airflow_school_or_office(args.area, args.occupants)
        print(f"Office/School (AFS 2020:1 §22):")
        print(f"  Area component:   {0.35 * args.area:.1f} l/s  (0.35 × {args.area})")
        print(f"  Person component: {7.0 * args.occupants:.1f} l/s  (7 × {args.occupants})")
        print(f"  Required:         {q:.1f} l/s  [sum of both components]")
        print()


if __name__ == "__main__":
    main()
