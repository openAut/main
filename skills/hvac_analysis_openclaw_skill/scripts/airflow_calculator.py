#!/usr/bin/env python3
"""
Airflow Calculator for Swedish ventilation requirements.

This script provides utility functions to calculate minimum outdoor
airflow rates for different occupancy types based on Swedish regulations.

Functions:
- required_airflow_residential(area_m2: float, occupants: int) -> float
- required_airflow_school_or_office(area_m2: float, occupants: int) -> float

All flows are returned in litres per second (l/s).

References:
- Boverket requires at least 0.35 l/s·m² and 4 l/s per person in residences【307965596929412†L6814-L6819】.
- For schools and offices, a minimum of 7 l/s per person plus 0.35 l/s·m² is recommended【476562234464538†L690-L697】.
"""

def required_airflow_residential(area_m2: float, occupants: int) -> float:
    """
    Calculate the minimum outdoor airflow for a residential space.

    Parameters
    ----------
    area_m2 : float
        Floor area in square metres.
    occupants : int
        Number of occupants.

    Returns
    -------
    float
        Required outdoor airflow in litres per second (l/s).

    The calculation follows the formula:
        q = max(0.35 * area_m2, 4 * occupants)
    where 0.35 l/s·m² is the minimum ventilation per floor area and 4 l/s per person is the minimum per person【307965596929412†L6814-L6819】.
    """
    area_flow = 0.35 * area_m2
    person_flow = 4.0 * occupants
    return max(area_flow, person_flow)

def required_airflow_school_or_office(area_m2: float, occupants: int) -> float:
    """
    Calculate the minimum outdoor airflow for schools or offices during sedentary activities.

    Parameters
    ----------
    area_m2 : float
        Floor area in square metres.
    occupants : int
        Number of occupants.

    Returns
    -------
    float
        Required outdoor airflow in litres per second (l/s).

    The calculation follows the formula:
        q = 0.35 * area_m2 + 7 * occupants
    where 0.35 l/s·m² accounts for building emissions and 7 l/s per person accounts for occupant emissions【476562234464538†L690-L697】.
    """
    return 0.35 * area_m2 + 7.0 * occupants

if __name__ == "__main__":
    # Example usage
    area = 70.0  # m²
    occupants = 3
    q_res = required_airflow_residential(area, occupants)
    q_office = required_airflow_school_or_office(area, occupants)
    print(f"Minimum residential airflow: {q_res:.1f} l/s")
    print(f"Minimum office/school airflow: {q_office:.1f} l/s")