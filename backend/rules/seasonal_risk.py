"""
Seasonal / Cyclone Risk Module for Indian East Coast Destination Ports.

Evaluates historical climatological cyclone landfall exposure for Indian East Coast
ports (Bay of Bengal basin) over a forward chartering horizon.

Data Source:
    India Meteorological Department (IMD) / Regional Specialized Meteorological
    Centre (RSMC) New Delhi - Tropical Cyclone Landfall Climatology
    Reference: https://rsmcnewdelhi.imd.gov.in/landfall.php

Climatological Background:
    Over 60% of Bay of Bengal tropical cyclones strike India's East Coast, with
    distinct historical landfall timing across two active seasons:
    - Primary Post-Monsoon Season (October-December):
        * Odisha / West Bengal coast peaks in October
        * Andhra Pradesh coast peaks in November
        * Tamil Nadu coast peaks in December
    - Secondary Pre-Monsoon Season (April-June):
        * Moderate activity across northern and central Bay of Bengal coastlines.

IMPORTANT DISCLAIMER:
    This evaluation reflects historical CLIMATOLOGICAL frequency patterns (i.e.
    what typically occurs in that region during those calendar months), NOT a
    live weather forecast, storm radar feed, or real-time cyclone tracking prediction.
"""

import os
import json
from datetime import datetime, timedelta, date


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
REF_DIR = os.path.join(PROJECT_ROOT, "data", "reference")

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def _load_reference_files():
    """Load ports.json and cyclone_risk.json reference data."""
    ports_path = os.path.join(REF_DIR, "ports.json")
    cyclone_path = os.path.join(REF_DIR, "cyclone_risk.json")

    with open(ports_path, "r", encoding="utf-8") as f:
        ports_data = json.load(f)

    with open(cyclone_path, "r", encoding="utf-8") as f:
        cyclone_data = json.load(f)

    return ports_data, cyclone_data


def get_spanned_months(start_date, horizon_days):
    """
    Calculate the unique list of calendar months (1-12) spanned by the horizon.

    Args:
        start_date: str (YYYY-MM-DD), date, or datetime
        horizon_days: int

    Returns:
        List of integer months in chronological order of occurrence.
    """
    if isinstance(start_date, str):
        # Support YYYY-MM-DD or ISO formats
        clean_date_str = start_date.split("T")[0].split(" ")[0]
        dt = datetime.strptime(clean_date_str, "%Y-%m-%d").date()
    elif isinstance(start_date, datetime):
        dt = start_date.date()
    elif isinstance(start_date, date):
        dt = start_date
    else:
        dt = datetime.now().date()

    end_dt = dt + timedelta(days=max(horizon_days, 1))

    months = []
    curr = dt
    while curr <= end_dt:
        if curr.month not in months:
            months.append(curr.month)
        # Advance by 1 day or jump to next month
        curr += timedelta(days=1)

    return months


def compute_seasonal_risk(dest_port, forecast_start_date, horizon_days):
    """
    Compute seasonal cyclone risk for an Indian East Coast destination port.

    Args:
        dest_port: str, destination port name (e.g. 'Paradip', 'Visakhapatnam')
        forecast_start_date: str or date, starting date of forecast window
        horizon_days: int, duration of forecast horizon in days

    Returns:
        dict: Structured risk evaluation object including tier, score, and explanation.
    """
    ports_data, cyclone_data = _load_reference_files()

    port_info = ports_data.get(dest_port)
    if not port_info:
        # Fallback if port not recognized in destination reference
        return {
            "dest_port": dest_port,
            "state": "Unknown",
            "tier": "Low",
            "score": 25,
            "weight": 0.30,
            "peak_month": None,
            "peak_month_name": None,
            "season_months": [],
            "spanned_months": [],
            "spanned_month_names": [],
            "overlaps_peak": False,
            "overlaps_season": False,
            "message": f"Port '{dest_port}' not found in destination port database; defaulting seasonal risk to Low.",
            "disclaimer": "Historical climatological pattern based on IMD/RSMC New Delhi data; not live weather tracking.",
            "source": "India Meteorological Department (IMD) / RSMC New Delhi (https://rsmcnewdelhi.imd.gov.in/landfall.php)",
        }

    state = port_info.get("state", "Odisha")
    cyclone_profile = cyclone_data.get(state)

    if not cyclone_profile:
        # Fallback for unexpected state
        cyclone_profile = {
            "peak_month": 10,
            "peak_month_name": "October",
            "season_months": [4, 5, 6, 10, 11, 12],
            "peak_risk_label": "High",
        }

    peak_month = cyclone_profile.get("peak_month", 10)
    peak_month_name = cyclone_profile.get("peak_month_name", MONTH_NAMES[peak_month])
    season_months = cyclone_profile.get("season_months", [4, 5, 6, 10, 11, 12])

    spanned_months = get_spanned_months(forecast_start_date, horizon_days)
    spanned_month_names = [MONTH_NAMES[m] for m in spanned_months]

    overlaps_peak = peak_month in spanned_months
    overlaps_season = any(m in season_months for m in spanned_months)

    source_citation = (
        "India Meteorological Department (IMD) / RSMC New Delhi "
        "(https://rsmcnewdelhi.imd.gov.in/landfall.php)"
    )
    disclaimer = (
        "This evaluation reflects historical CLIMATOLOGICAL frequency patterns per "
        "IMD/RSMC records (i.e. statistical landfall probability by region/season), "
        "not a live weather forecast or real-time storm tracking prediction."
    )

    if overlaps_peak:
        tier = "High"
        score = 75
        message = (
            f"Forecast horizon overlaps peak cyclone season for {state} (typically {peak_month_name}) "
            f"-- per IMD/RSMC landfall climatology, over 60% of Bay of Bengal cyclones make landfall on "
            f"India's East Coast during Oct-Dec. Historical records show heightened probability of port "
            f"disruption, vessel draft delays, and berth closures during this window. "
            f"(Climatological baseline, not live weather tracking)."
        )
    elif overlaps_season:
        tier = "Moderate"
        score = 50
        # Identify whether overlapping pre-monsoon (Apr-Jun) or post-monsoon (Oct-Dec)
        active_in_span = [MONTH_NAMES[m] for m in spanned_months if m in season_months]
        active_str = ", ".join(active_in_span)
        message = (
            f"Forecast horizon overlaps the broader Bay of Bengal cyclone season for {state} "
            f"(active months in window: {active_str}), though it avoids the historical peak month "
            f"({peak_month_name}). Per IMD/RSMC landfall records, moderate storm activity is "
            f"statistically observed. Recommend building weather contingency days into laycan schedules. "
            f"(Climatological baseline, not live weather tracking)."
        )
    else:
        tier = "Low"
        score = 25
        spanned_str = ", ".join(spanned_month_names)
        message = (
            f"Forecast horizon ({spanned_str}) falls outside active Bay of Bengal tropical cyclone "
            f"seasons for {state} (primary: Oct-Dec, secondary: Apr-Jun). Minimal climatological "
            f"cyclone risk expected based on IMD/RSMC historical landfall records."
        )

    return {
        "dest_port": dest_port,
        "state": state,
        "tier": tier,
        "score": score,
        "weight": 0.30,
        "peak_month": peak_month,
        "peak_month_name": peak_month_name,
        "season_months": season_months,
        "spanned_months": spanned_months,
        "spanned_month_names": spanned_month_names,
        "overlaps_peak": overlaps_peak,
        "overlaps_season": overlaps_season,
        "message": message,
        "disclaimer": disclaimer,
        "source": source_citation,
    }


if __name__ == "__main__":
    # Quick self-test
    res1 = compute_seasonal_risk("Visakhapatnam", "2026-09-01", 90)
    print("Visakhapatnam (Andhra Pradesh, 90 days from Sep 1):")
    print(f"  Tier: {res1['tier']} (Score: {res1['score']})")
    print(f"  Overlaps Peak: {res1['overlaps_peak']} (Peak: {res1['peak_month_name']})")
    print(f"  Message: {res1['message']}")

    res2 = compute_seasonal_risk("Paradip", "2026-09-01", 60)
    print("\nParadip (Odisha, 60 days from Sep 1):")
    print(f"  Tier: {res2['tier']} (Score: {res2['score']})")
    print(f"  Overlaps Peak: {res2['overlaps_peak']} (Peak: {res2['peak_month_name']})")
    print(f"  Message: {res2['message']}")

    res3 = compute_seasonal_risk("Visakhapatnam", "2026-01-01", 30)
    print("\nVisakhapatnam (Andhra Pradesh, 30 days from Jan 1):")
    print(f"  Tier: {res3['tier']} (Score: {res3['score']})")
    print(f"  Overlaps Season: {res3['overlaps_season']}")
    print(f"  Message: {res3['message']}")
