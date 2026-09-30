"""
Integration test script for the Freight Chartering Decision Support System.

Tests international voyage scenarios as specified in SIH26006:
1. Large cargo (150,000t), Newcastle (Australia) -> Gangavaram (both Capesize-capable)
2. Large cargo (150,000t), Newcastle (Australia) -> Gopalpur (shallow destination)
3. Small cargo (30,000t), Nacala (Mozambique) -> Dhamra (should recommend Handysize)
4. Large cargo via unverified origin, Tanjung Bara (Indonesia) -> Paradip (draft-limited)
"""

import requests
import json
import sys

API_BASE = "http://127.0.0.1:8000"

def test_scenario(name, cargo_qty, origin, destination, checks):
    """Run a test scenario and verify assertions."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {name}")
    print(f"  Cargo: {cargo_qty:,}t | Route: {origin} -> {destination}")
    print(f"{'='*60}")

    try:
        r = requests.get(
            f"{API_BASE}/api/recommend",
            params={
                "cargo_qty": cargo_qty,
                "origin": origin,
                "destination": destination,
                "horizon_days": 90,
            },
            timeout=60,
        )

        if r.status_code != 200:
            print(f"  [FAIL] API returned status {r.status_code}: {r.text}")
            return False

        data = r.json()

        # Basic structure checks
        assert "forecast" in data, "Missing 'forecast' key"
        assert "vessel_recommendations" in data, "Missing 'vessel_recommendations' key"
        assert "risk_flags" in data, "Missing 'risk_flags' key"
        assert "idle_time_flags" in data, "Missing 'idle_time_flags' key"
        assert "market_timing" in data, "Missing 'market_timing' key (Requirement a)"
        mt = data["market_timing"]
        assert "verdict" in mt and mt["verdict"] in ["CHARTER NOW", "WAIT FOR WINDOW", "MONITOR"]
        assert "recommended_window_start" in mt
        assert "recommended_window_end" in mt
        assert "expected_avg_rate" in mt
        assert "expected_confidence" in mt
        assert "pct_below_horizon_avg" in mt
        assert "reasoning" in mt
        assert len(data["forecast"]) == 90, f"Expected 90 forecast points, got {len(data['forecast'])}"

        # Print Requirement (a) Market Timing
        print("\n  Market Entry Timing (Requirement a):")
        print(f"    Verdict:              [{mt['verdict']}]")
        print(f"    Optimal Window:       {mt['recommended_window_start']} to {mt['recommended_window_end']}")
        print(f"    Expected Rate:        {mt['expected_avg_rate']:,.0f} BDI (~${mt['expected_avg_rate']/100:.2f}/t)")
        print(f"    Confidence Band:      {mt['expected_confidence']:.1f}% width")
        print(f"    Horizon Advantage:    {mt['pct_below_horizon_avg']:+.1f}% vs horizon mean")
        print(f"    Reasoning:            {mt['reasoning']}")

        # Print vessel recommendations
        print("\n  Vessel Recommendations:")
        for v in data["vessel_recommendations"]:
            status = "FEASIBLE" if v["feasible"] else "INFEASIBLE"
            cost = f"${v['total_cost']:,.0f}" if v["total_cost"] else "N/A"
            rate_info = f"${v.get('rate_per_tonne', '?')}/t ({v.get('rate_index', '?')})"
            print(f"    {v['vessel_class']:12s} [{status}] Rate: {rate_info:22s} Cost: {cost}")
            if v["reasons"]:
                for reason in v["reasons"]:
                    print(f"      - {reason}")

        print(f"\n  Risk flags: {len(data['risk_flags'])}")
        print(f"  Idle-time flags: {len(data['idle_time_flags'])}")
        for f in data["idle_time_flags"]:
            msg = f['message']
            print(f"    [{f['type']}] {msg[:80]}{'...' if len(msg) > 80 else ''}")

        # Print metadata
        meta = data.get("metadata", {})
        print(f"  Route type: {meta.get('route_type', 'N/A')}")
        print(f"  Origin country: {meta.get('origin_country', 'N/A')}")
        rate_lookup = meta.get("rate_lookup", {})
        if rate_lookup:
            print(f"  Per-class rates: {rate_lookup}")

        # Port warnings
        for pw in meta.get("port_warnings", []):
            print(f"  [PORT WARNING] {pw}")

        # Run specific checks
        all_passed = True
        for check_name, check_fn in checks.items():
            try:
                result = check_fn(data)
                if result:
                    print(f"  [PASS] {check_name}")
                else:
                    print(f"  [FAIL] {check_name}")
                    all_passed = False
            except AssertionError as e:
                print(f"  [FAIL] {check_name}: {e}")
                all_passed = False

        return all_passed

    except requests.exceptions.ConnectionError:
        print("  [FAIL] Cannot connect to backend API. Is it running?")
        return False
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")
        return False


def test_api_rejects_indian_origin():
    """Verify that the API rejects an Indian port used as origin."""
    print(f"\n{'='*60}")
    print("SCENARIO: API rejects Indian port as origin")
    print(f"{'='*60}")

    try:
        r = requests.get(
            f"{API_BASE}/api/recommend",
            params={
                "cargo_qty": 50000,
                "origin": "Paradip",  # Indian port — should be rejected as origin
                "destination": "Gangavaram",
                "horizon_days": 90,
            },
            timeout=10,
        )
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            print(f"  API correctly rejected: {detail}")
            print(f"  [PASS] Indian port rejected as origin")
            return True
        else:
            print(f"  [FAIL] API should return 400, got {r.status_code}")
            return False
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")
        return False


def test_separate_port_endpoints():
    """Verify that /api/ports and /api/origin-ports return different port sets."""
    print(f"\n{'='*60}")
    print("SCENARIO: Separate origin and destination port endpoints")
    print(f"{'='*60}")

    try:
        r_dest = requests.get(f"{API_BASE}/api/ports", timeout=5)
        r_origin = requests.get(f"{API_BASE}/api/origin-ports", timeout=5)

        if r_dest.status_code != 200 or r_origin.status_code != 200:
            print(f"  [FAIL] API endpoints returned errors")
            return False

        dest_ports = r_dest.json()
        origin_ports = r_origin.json()

        dest_names = set(dest_ports.keys())
        origin_names = set(origin_ports.keys())

        print(f"  Destination ports (Indian): {list(dest_names)}")
        print(f"  Origin ports (overseas):    {list(origin_names)}")

        overlap = dest_names & origin_names
        if overlap:
            print(f"  [FAIL] Overlap between origin and destination ports: {overlap}")
            return False
        else:
            print(f"  [PASS] No overlap — origin and destination ports are fully separate")
            return True

    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")
        return False


def main():
    print("=" * 60)
    print("INTEGRATION TEST SUITE (International Routes)")
    print("Freight Chartering Decision Support System (SIH26006)")
    print("=" * 60)

    # Check backend is running
    try:
        r = requests.get(f"{API_BASE}/api/health", timeout=5)
        print(f"\nBackend health: {r.json()}")
    except:
        print("\n[FATAL] Backend not reachable. Start it first.")
        sys.exit(1)

    results = []

    # Test 0: Verify port endpoints are separate
    result0 = test_separate_port_endpoints()
    results.append(("Port endpoints separation", result0))

    # Test 0b: Verify API rejects Indian port as origin
    result0b = test_api_rejects_indian_origin()
    results.append(("Indian port rejected as origin", result0b))

    # Test 0c: Verify per-class rates are differentiated
    result0c = test_scenario(
        "Rate differentiation: 50,000t, Hampton Roads -> Visakhapatnam",
        50000,
        "Hampton Roads (USA)",
        "Visakhapatnam",
        {
            "Vessels have different rates": lambda d: (
                len(set(
                    v.get("rate_per_tonne", 0)
                    for v in d["vessel_recommendations"]
                )) > 1  # At least 2 distinct rates, not all the same
            ),
            "Rate lookup has per-class entries": lambda d: (
                len(d.get("metadata", {}).get("rate_lookup", {})) >= 4
            ),
            "Capesize rate > Handysize rate": lambda d: (
                d.get("metadata", {}).get("rate_lookup", {}).get("capesize", 0) >
                d.get("metadata", {}).get("rate_lookup", {}).get("handysize", 0)
            ),
        }
    )
    results.append(("Rate differentiation", result0c))

    # Scenario 1: Large cargo (150,000t), overseas -> deep Indian port
    # Newcastle max_draft=16.2m, max_loa=300m (verified)
    # Gangavaram max_draft=20.2m, max_loa=300m (verified)
    # Capesize: draft=18.0m -> exceeds Newcastle 16.2m -> INFEASIBLE at origin
    # All other vessels: max DWT < 150,000t -> INFEASIBLE on capacity
    # Result: NO vessel is feasible for 150,000t out of Newcastle
    # (This is realistic — Newcastle is a Panamax-limited port for coal loading)
    result1 = test_scenario(
        "150,000t cargo, Newcastle -> Gangavaram (no feasible vessel)",
        150000,
        "Newcastle (Australia)",
        "Gangavaram",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Capesize infeasible (draft 18m > Newcastle 16.2m)": lambda d: any(
                v["vessel_class"] == "Capesize" and not v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "No vessel feasible for 150kt at Newcastle": lambda d: all(
                not v["feasible"] for v in d["vessel_recommendations"]
            ),
            "Route type is international": lambda d: (
                d.get("metadata", {}).get("route_type") == "international"
            ),
            "Origin country is Australia": lambda d: (
                d.get("metadata", {}).get("origin_country") == "Australia"
            ),
        }
    )
    results.append(("Scenario 1 (150kt, Newcastle -> Gangavaram)", result1))

    # Scenario 1b: Panamax-sized cargo from Newcastle
    # 80,000t fits Panamax DWT range (65,000-99,999t)
    # Panamax draft=14.0m < Newcastle 16.2m -> feasible at origin
    # Panamax draft=14.0m < Gangavaram 20.2m -> feasible at dest
    result1b = test_scenario(
        "80,000t cargo, Newcastle -> Gangavaram (Panamax feasible)",
        80000,
        "Newcastle (Australia)",
        "Gangavaram",
        {
            "Panamax is feasible": lambda d: any(
                v["vessel_class"] == "Panamax" and v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Panamax is top recommendation": lambda d: (
                d["vessel_recommendations"][0]["vessel_class"] == "Panamax"
                and d["vessel_recommendations"][0]["feasible"]
            ),
            "Capesize still infeasible (draft)": lambda d: any(
                v["vessel_class"] == "Capesize" and not v["feasible"]
                for v in d["vessel_recommendations"]
            ),
        }
    )
    results.append(("Scenario 1b (80kt, Newcastle -> Gangavaram)", result1b))

    # Scenario 1c: 50,000t sanity check, Newcastle -> Gangavaram
    # Tests Haversine distance (~3,772 nm), voyage days (~13.3), and Supramax allocation
    result1c = test_scenario(
        "50,000t sanity check, Newcastle -> Gangavaram (Supramax feasible)",
        50000,
        "Newcastle (Australia)",
        "Gangavaram",
        {
            "Supramax is feasible": lambda d: any(
                v["vessel_class"] == "Supramax" and v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Supramax is top recommendation": lambda d: (
                d["vessel_recommendations"][0]["vessel_class"] == "Supramax"
                and d["vessel_recommendations"][0]["feasible"]
            ),
            "Haversine route distance matches ~3,772 nm": lambda d: (
                abs(d["metadata"].get("route_distance_nm", 0) - 3772) <= 5
            ),
            "Adjusted route distance matches ~4,149 nm": lambda d: (
                abs(d["metadata"].get("route_adjusted_distance_nm", 0) - 4149) <= 10
            ),
            "Voyage sailing days matches ~13.3 days": lambda d: (
                abs(d["metadata"].get("route_sea_days", 0) - 13.3) <= 0.5
            ),
            "Disclosure banner text is present": lambda d: (
                "illustrative estimates" in d.get("metadata", {}).get("disclosure", "").lower()
            ),
        }
    )
    results.append(("Scenario 1c (50kt, Newcastle -> Gangavaram)", result1c))

    # Scenario 2: Large cargo, overseas -> Gopalpur (200k DWT verified, draft provisional)
    result2 = test_scenario(
        "Large cargo, Newcastle -> Gopalpur (200k DWT ceiling verified, draft provisional)",
        150000,
        "Newcastle (Australia)",
        "Gopalpur",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Capesize is infeasible on draft/LOA": lambda d: any(
                v["vessel_class"] == "Capesize" and not v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Capesize does NOT fail DWT ceiling": lambda d: any(
                v["vessel_class"] == "Capesize"
                and not any("max vessel DWT ceiling" in r for r in v.get("reasons", []))
                for v in d["vessel_recommendations"]
            ),
            "Nuanced Gopalpur disclosure present": lambda d: any(
                "200,000 DWT" in pw or "Gopalpur" in pw
                for pw in d.get("metadata", {}).get("port_warnings", [])
            ),
            "Destination max vessel DWT is 200,000": lambda d: (
                d.get("metadata", {}).get("destination_max_vessel_dwt") == 200000
            ),
        }
    )
    results.append(("Scenario 2 (Newcastle -> Gopalpur 150kt)", result2))

    # Scenario 2b: Medium cargo (50,000t), Newcastle -> Gopalpur (feasible Supramax)
    result2b = test_scenario(
        "Medium cargo (50,000t), Newcastle -> Gopalpur (Supramax feasible)",
        50000,
        "Newcastle (Australia)",
        "Gopalpur",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Supramax is feasible": lambda d: any(
                v["vessel_class"] == "Supramax" and v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Supramax is top recommendation": lambda d: (
                d["vessel_recommendations"][0]["vessel_class"] == "Supramax"
                and d["vessel_recommendations"][0]["feasible"]
            ),
        }
    )
    results.append(("Scenario 2b (Newcastle -> Gopalpur 50kt)", result2b))

    # Scenario 2c: Large cargo (150,000t), Newcastle -> Haldia (75k DWT ceiling enforced)
    result2c = test_scenario(
        "Large cargo (150,000t), Newcastle -> Haldia (75k DWT ceiling enforced)",
        150000,
        "Newcastle (Australia)",
        "Haldia",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Capesize fails Haldia 75k DWT ceiling": lambda d: any(
                v["vessel_class"] == "Capesize"
                and not v["feasible"]
                and any("75,000 DWT" in r for r in v.get("reasons", []))
                for v in d["vessel_recommendations"]
            ),
            "Nuanced Haldia disclosure present": lambda d: any(
                "75,000 DWT" in pw or "Haldia" in pw
                for pw in d.get("metadata", {}).get("port_warnings", [])
            ),
            "Destination max vessel DWT is 75,000": lambda d: (
                d.get("metadata", {}).get("destination_max_vessel_dwt") == 75000
            ),
        }
    )
    results.append(("Scenario 2c (Newcastle -> Haldia 150kt)", result2c))

    # Scenario 3: Small cargo, Mozambique -> India
    result3 = test_scenario(
        "Small cargo (30,000t), Nacala -> Dhamra",
        30000,
        "Nacala (Mozambique)",
        "Dhamra",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Handysize is feasible": lambda d: any(
                v["vessel_class"] == "Handysize" and v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Capesize is NOT recommended (capacity mismatch)": lambda d: any(
                v["vessel_class"] == "Capesize" and not v["feasible"]
                for v in d["vessel_recommendations"]
            ),
            "Handysize is the top recommendation": lambda d: (
                d["vessel_recommendations"][0]["vessel_class"] == "Handysize"
                and d["vessel_recommendations"][0]["feasible"]
            ),
        }
    )
    results.append(("Scenario 3 (Nacala -> Dhamra, small cargo)", result3))

    # Scenario 4: Unverified origin port, draft-limited destination with Paradip tension
    # Tanjung Bara: max_draft=16.0m (unverified), Paradip: max_draft=16.5m (official)
    # Capesize draft=18.0m > both -> infeasible
    result4 = test_scenario(
        "Large cargo, Tanjung Bara -> Paradip (unverified origin, draft-limited dest, tension disclosed)",
        150000,
        "Tanjung Bara (Indonesia)",
        "Paradip",
        {
            "Has forecast data": lambda d: len(d["forecast"]) == 90,
            "Capesize infeasible at both ports": lambda d: any(
                v["vessel_class"] == "Capesize"
                and not v["feasible"]
                and len(v["reasons"]) >= 2  # Should fail at BOTH ports
                for v in d["vessel_recommendations"]
            ),
            "Unverified origin port flagged": lambda d: any(
                "Tanjung Bara" in pw
                for pw in d.get("metadata", {}).get("port_warnings", [])
            ),
            "Paradip operational tension disclosed": lambda d: any(
                "Paradip" in pw and "tension" in pw.lower()
                for pw in d.get("metadata", {}).get("port_warnings", [])
            ),
            "Destination max vessel DWT is 155,000": lambda d: (
                d.get("metadata", {}).get("destination_max_vessel_dwt") == 155000
            ),
        }
    )
    results.append(("Scenario 4 (Tanjung Bara -> Paradip)", result4))

    # Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n[ALL TESTS PASSED]")
    else:
        print("\n[SOME TESTS FAILED] - Review output above")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
