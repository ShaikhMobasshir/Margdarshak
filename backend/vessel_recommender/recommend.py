"""
Vessel Recommender module.

Pure deterministic logic — no ML/training needed.
Checks vessel feasibility against port constraints (draft, LOA, beam)
and cargo capacity, then models voyage economics using calculated Haversine
route distances (with 1.10x real-route factor), port berth times (handling rates),
demonstration congestion estimates, and vessel daily charter rates.

Origin ports (overseas loading ports) and destination ports (Indian East
Coast discharge ports) are loaded from separate reference files so that
the system correctly models INTERNATIONAL voyages as specified in SIH26006.
"""

import os
import json
from math import radians, sin, cos, sqrt, atan2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
VESSEL_SPECS_PATH = os.path.join(PROJECT_ROOT, "data", "reference", "vessel_specs.json")
DEST_PORTS_PATH = os.path.join(PROJECT_ROOT, "data", "reference", "ports.json")
ORIGIN_PORTS_PATH = os.path.join(PROJECT_ROOT, "data", "reference", "origin_ports.json")
ROUTES_PATH = os.path.join(PROJECT_ROOT, "data", "reference", "routes.json")


def haversine_nm(lat1, lon1, lat2, lon2):
    """Compute great-circle distance between two coordinates in nautical miles."""
    R_km = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round((R_km * c) / 1.852)


def load_reference_data():
    """Load vessel specs and both port datasets from JSON files.

    Returns:
        Tuple of (vessel_specs, origin_ports, dest_ports)
    """
    with open(VESSEL_SPECS_PATH, "r", encoding="utf-8") as f:
        vessel_specs = json.load(f)
    with open(ORIGIN_PORTS_PATH, "r", encoding="utf-8") as f:
        origin_ports = json.load(f)
    with open(DEST_PORTS_PATH, "r", encoding="utf-8") as f:
        dest_ports = json.load(f)
    return vessel_specs, origin_ports, dest_ports


def load_routes_data():
    """Load programmatic route distance cache from routes.json."""
    if os.path.exists(ROUTES_PATH):
        with open(ROUTES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def check_feasibility(vessel_name, vessel_spec, origin_port, dest_port,
                      origin_ports_data, dest_ports_data, cargo_qty_tonnes=None):
    """
    Check if a vessel is feasible for a given route based on port constraints.

    Validates the vessel's draft, LOA, beam, and max_vessel_dwt capacity ceiling against:
    - The ORIGIN port (overseas loading port) from origin_ports.json
    - The DESTINATION port (Indian East Coast port) from ports.json

    A vessel is marked infeasible if it fails physical dimension checks (draft/LOA/beam)
    OR exceeds the port's stated max_vessel_dwt ceiling.

    Args:
        vessel_name: Name of vessel class (e.g. "Capesize")
        vessel_spec: Dict with vessel specifications (draft_m, loa_m, beam_m, dwt_min, dwt_max)
        origin_port: Name of origin port (overseas)
        dest_port: Name of destination port (India East Coast)
        origin_ports_data: Dict of origin port specifications
        dest_ports_data: Dict of destination port specifications
        cargo_qty_tonnes: Optional cargo quantity in tonnes

    Returns:
        Tuple of (bool feasible, list of reason strings if not feasible)
    """
    reasons = []

    # Check origin port constraints (overseas loading port)
    if origin_port in origin_ports_data:
        origin = origin_ports_data[origin_port]
        if vessel_spec["draft_m"] > origin["max_draft_m"]:
            reasons.append(
                f"Vessel draft ({vessel_spec['draft_m']}m) exceeds "
                f"{origin_port} max draft ({origin['max_draft_m']}m)"
            )
        if vessel_spec["loa_m"] > origin["max_loa_m"]:
            reasons.append(
                f"Vessel LOA ({vessel_spec['loa_m']}m) exceeds "
                f"{origin_port} max LOA ({origin['max_loa_m']}m)"
            )
        # Check beam constraint if present
        if "max_beam_m" in origin and vessel_spec.get("beam_m", 0) > origin["max_beam_m"]:
            reasons.append(
                f"Vessel beam ({vessel_spec.get('beam_m')}m) exceeds "
                f"{origin_port} max beam ({origin['max_beam_m']}m) [Illustrative limit]"
            )
        # Check max_vessel_dwt constraint if present
        if "max_vessel_dwt" in origin:
            max_dwt = origin["max_vessel_dwt"]
            if vessel_spec.get("dwt_min", 0) > max_dwt:
                reasons.append(
                    f"Vessel class minimum DWT ({vessel_spec['dwt_min']:,}t) exceeds "
                    f"{origin_port} max vessel DWT ceiling ({max_dwt:,} DWT)"
                )
            elif cargo_qty_tonnes is not None and cargo_qty_tonnes > max_dwt:
                reasons.append(
                    f"Cargo ({cargo_qty_tonnes:,.0f}t) exceeds "
                    f"{origin_port} max vessel DWT ceiling ({max_dwt:,} DWT)"
                )
    else:
        reasons.append(f"Origin port '{origin_port}' not found in overseas port database")

    # Check destination port constraints (Indian East Coast port)
    if dest_port in dest_ports_data:
        dest = dest_ports_data[dest_port]
        if vessel_spec["draft_m"] > dest["max_draft_m"]:
            reasons.append(
                f"Vessel draft ({vessel_spec['draft_m']}m) exceeds "
                f"{dest_port} max draft ({dest['max_draft_m']}m)"
            )
        if vessel_spec["loa_m"] > dest["max_loa_m"]:
            reasons.append(
                f"Vessel LOA ({vessel_spec['loa_m']}m) exceeds "
                f"{dest_port} max LOA ({dest['max_loa_m']}m)"
            )
        # Check beam constraint if present
        if "max_beam_m" in dest and vessel_spec.get("beam_m", 0) > dest["max_beam_m"]:
            reasons.append(
                f"Vessel beam ({vessel_spec.get('beam_m')}m) exceeds "
                f"{dest_port} max beam ({dest['max_beam_m']}m) [Illustrative limit]"
            )
        # Check max_vessel_dwt constraint if present
        if "max_vessel_dwt" in dest:
            max_dwt = dest["max_vessel_dwt"]
            if vessel_spec.get("dwt_min", 0) > max_dwt:
                reasons.append(
                    f"Vessel class minimum DWT ({vessel_spec['dwt_min']:,}t) exceeds "
                    f"{dest_port} max vessel DWT ceiling ({max_dwt:,} DWT)"
                )
            elif cargo_qty_tonnes is not None and cargo_qty_tonnes > max_dwt:
                reasons.append(
                    f"Cargo ({cargo_qty_tonnes:,.0f}t) exceeds "
                    f"{dest_port} max vessel DWT ceiling ({max_dwt:,} DWT)"
                )
    else:
        reasons.append(f"Destination port '{dest_port}' not found in Indian port database")

    feasible = len(reasons) == 0
    return feasible, reasons


# Mapping from vessel class name -> sub-index column name
VESSEL_CLASS_TO_INDEX = {
    "Capesize":  "bci",
    "Panamax":   "bpi",
    "Supramax":  "bsi",
    "Handysize": "bhsi",
}


def recommend_vessel(cargo_qty_tonnes, origin_port, dest_port, rate_lookup):
    """
    Recommend vessels for a given international cargo route using voyage economics.

    Args:
        cargo_qty_tonnes: Amount of cargo in tonnes
        origin_port: Name of overseas origin port (from origin_ports.json)
        dest_port: Name of Indian East Coast destination port (from ports.json)
        rate_lookup: Dict mapping vessel class (lowercase) to $/tonne rate or charter rate proxy,
                     e.g. {"capesize": 39.83, "panamax": 33.46, "supramax": 30.27,
                           "handysize": 27.08, "bdi": 31.86}

    Returns:
        List of dicts, feasible vessels sorted by ascending cost first,
        then infeasible vessels.
    """
    vessel_specs, origin_ports_data, dest_ports_data = load_reference_data()
    routes_data = load_routes_data()

    # Determine route distances and voyage parameters
    speed_knots = 13.0
    adjustment_factor = 1.10

    if origin_port in routes_data and dest_port in routes_data[origin_port]:
        route_info = routes_data[origin_port][dest_port]
        distance_nm = route_info.get("distance_nm", 0)
        adjusted_distance_nm = route_info.get("adjusted_distance_nm", round(distance_nm * adjustment_factor))
        speed_knots = route_info.get("speed_knots", 13.0)
    else:
        # Compute on the fly via Haversine if route entry is absent
        orig = origin_ports_data.get(origin_port, {})
        dest = dest_ports_data.get(dest_port, {})
        if "lat" in orig and "lat" in dest:
            lat1 = orig.get("lat_ref", orig["lat"])
            distance_nm = haversine_nm(lat1, orig["lon"], dest["lat"], dest["lon"])
            adjusted_distance_nm = round(distance_nm * adjustment_factor)
        else:
            distance_nm = 4000
            adjusted_distance_nm = round(distance_nm * adjustment_factor)

    # Compute sea days (sailing time)
    sea_days = round(adjusted_distance_nm / (speed_knots * 24), 1)
    voyage_days = sea_days  # Standard user terminology

    # Handling rates & berth days (illustrative typical estimates)
    # Origin: load rate (e.g. 40k tpd Newcastle, 25k tpd default)
    # Destination: discharge rate (e.g. 40k tpd Gangavaram, 35k tpd Vizag)
    origin_load_rate = origin_ports_data.get(origin_port, {}).get("load_rate_tpd", 25000)
    dest_discharge_rate = dest_ports_data.get(dest_port, {}).get("discharge_rate_tpd", 25000)

    load_days = round(cargo_qty_tonnes / origin_load_rate, 2)
    discharge_days = round(cargo_qty_tonnes / dest_discharge_rate, 2)
    berth_days = round(load_days + discharge_days, 1)

    # Congestion estimates (illustrative demonstration estimates)
    origin_congestion = origin_ports_data.get(origin_port, {}).get("congestion_days", 2.0)
    dest_congestion = dest_ports_data.get(dest_port, {}).get("congestion_days", 1.5)
    congestion_days = round(origin_congestion + dest_congestion, 1)

    # Total voyage cycle days
    total_voyage_days = round(sea_days + berth_days + congestion_days, 1)

    results = []

    for vessel_name, spec in vessel_specs.items():
        # Check port feasibility (origin = overseas, destination = India)
        port_feasible, port_reasons = check_feasibility(
            vessel_name, spec, origin_port, dest_port,
            origin_ports_data, dest_ports_data,
            cargo_qty_tonnes=cargo_qty_tonnes
        )

        # Check capacity match
        capacity_reasons = []
        capacity_match = spec["dwt_min"] <= cargo_qty_tonnes <= spec["dwt_max"]
        if cargo_qty_tonnes < spec["dwt_min"]:
            capacity_reasons.append(
                f"Cargo ({cargo_qty_tonnes:,.0f}t) is below vessel minimum capacity "
                f"({spec['dwt_min']:,}t)"
            )
        elif cargo_qty_tonnes > spec["dwt_max"]:
            capacity_reasons.append(
                f"Cargo ({cargo_qty_tonnes:,.0f}t) exceeds vessel maximum capacity "
                f"({spec['dwt_max']:,}t)"
            )

        # Overall feasibility
        all_reasons = port_reasons + capacity_reasons
        feasible = port_feasible and capacity_match

        # Look up the per-vessel-class rate multiplier
        vessel_key = vessel_name.lower()  # e.g. "capesize", "panamax"
        if vessel_key in rate_lookup:
            rate_input = rate_lookup[vessel_key]
            rate_index = VESSEL_CLASS_TO_INDEX.get(vessel_name, "bdi")
        else:
            rate_input = rate_lookup.get("bdi", 0)
            rate_index = "bdi"

        # Daily charter rate ($/day)
        # If rate_input is in $/tonne proxy format (e.g. 14.0 - 45.0),
        # convert to standard daily charter hire ($/day, e.g. $14,000 - $45,000/day)
        if rate_input < 1000:
            daily_charter_rate = round(rate_input * 1000)
        else:
            daily_charter_rate = round(rate_input)

        # Voyage economics cost calculation:
        # Total voyage cost = daily charter rate * total turnaround days (sea + berth + congestion)
        if feasible:
            total_cost = round(daily_charter_rate * total_voyage_days)
            rate_per_tonne = round(total_cost / cargo_qty_tonnes, 2)
        else:
            total_cost = None
            rate_per_tonne = round(rate_input, 2)

        # Check port verification status
        unverified_ports = []
        if origin_port in origin_ports_data and not origin_ports_data[origin_port].get("verified", True):
            unverified_ports.append(origin_port)
        if dest_port in dest_ports_data and not dest_ports_data[dest_port].get("verified", True):
            unverified_ports.append(dest_port)

        result = {
            "vessel_class": vessel_name,
            "dwt_min": spec["dwt_min"],
            "dwt_max": spec["dwt_max"],
            "draft_m": spec["draft_m"],
            "loa_m": spec["loa_m"],
            "beam_m": spec.get("beam_m", 0),
            "feasible": feasible,
            "capacity_match": capacity_match,
            "reasons": all_reasons,
            "distance_nm": distance_nm,
            "adjusted_distance_nm": adjusted_distance_nm,
            "adjustment_factor": adjustment_factor,
            "speed_knots": speed_knots,
            "voyage_days": voyage_days,
            "sea_days": sea_days,
            "berth_days": berth_days,
            "load_days": load_days,
            "discharge_days": discharge_days,
            "congestion_days": congestion_days,
            "total_voyage_days": total_voyage_days,
            "daily_charter_rate": daily_charter_rate,
            "total_cost": total_cost,
            "rate_per_tonne": rate_per_tonne,
            "rate_index": rate_index.upper(),
            "unverified_ports": unverified_ports,
        }
        results.append(result)

    # Sort: feasible vessels first (by ascending cost), then infeasible
    feasible_vessels = sorted(
        [r for r in results if r["feasible"]],
        key=lambda x: x["total_cost"] or float("inf")
    )
    infeasible_vessels = [r for r in results if not r["feasible"]]

    return feasible_vessels + infeasible_vessels


if __name__ == "__main__":
    print("=== Vessel Recommender Test Scenarios (Voyage Economics) ===\n")

    test_cases = [
        ("Newcastle -> Gangavaram (50,000t sanity check)",
         50000, "Newcastle (Australia)", "Gangavaram"),
        ("Scenario 1: Large cargo, Newcastle -> Gangavaram (deep ports)",
         150000, "Newcastle (Australia)", "Gangavaram"),
        ("Scenario 2: Large cargo, Newcastle -> Gopalpur (200k DWT ceiling verified)",
         150000, "Newcastle (Australia)", "Gopalpur"),
        ("Scenario 2b: Medium cargo, Newcastle -> Gopalpur (50,000t Supramax)",
         50000, "Newcastle (Australia)", "Gopalpur"),
        ("Scenario 3: Small cargo, Nacala -> Dhamra",
         30000, "Nacala (Mozambique)", "Dhamra"),
        ("Scenario 4: Large cargo, Tanjung Bara -> Paradip (draft-limited)",
         150000, "Tanjung Bara (Indonesia)", "Paradip"),
        ("Scenario 5: Medium cargo, Hampton Roads -> Visakhapatnam",
         50000, "Hampton Roads (USA)", "Visakhapatnam"),
        ("Scenario 6: Large cargo, Newcastle -> Haldia (exceeds 75k DWT ceiling)",
         150000, "Newcastle (Australia)", "Haldia"),
        ("Scenario 7: Medium cargo, Nacala -> Haldia (within 75k DWT ceiling)",
         50000, "Nacala (Mozambique)", "Haldia"),
    ]

    mock_rates = {
        "capesize":  28.50,  # BCI-based
        "panamax":   22.10,  # BPI-based
        "supramax":  18.70,  # BSI-based
        "handysize": 14.20,  # BHSI-based
        "bdi":       21.80,  # Composite fallback
    }

    for title, cargo, origin, dest in test_cases:
        print(f"--- {title} ---")
        print(f"    Cargo: {cargo:,}t | Route: {origin} -> {dest}")
        results = recommend_vessel(cargo, origin, dest, mock_rates)

        first = results[0]
        print(f"    Route: {first['distance_nm']} nm (Adjusted: {first['adjusted_distance_nm']} nm, {first['voyage_days']} sea days)")
        print(f"    Port Logistics: {first['berth_days']} berth days + {first['congestion_days']} congestion days = {first['total_voyage_days']} total days")

        for r in results:
            status = "FEASIBLE" if r["feasible"] else "INFEASIBLE"
            cost_str = f"${r['total_cost']:,.0f}" if r["total_cost"] else "N/A"
            rate_str = f"${r['rate_per_tonne']}/t (${r['daily_charter_rate']:,}/day)"
            print(f"    {r['vessel_class']:12s} [{status}] Rate: {rate_str:30s} Total Cost: {cost_str}")
            if r["reasons"]:
                for reason in r["reasons"]:
                    print(f"        - {reason}")
        print()
