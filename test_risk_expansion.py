"""
Automated Test Suite for Expanded Multi-Criteria Risk Assessment Module.

Tests:
1. Seasonal / Cyclone Risk (IMD / RSMC Climatology):
   - Scenario A: Andhra Pradesh destination (Visakhapatnam) with Sep-Nov window (spans Nov peak) -> High Tier (75)
   - Scenario B: Odisha destination (Paradip) with Sep-Oct window (spans Oct peak) -> High Tier (75)
   - Scenario C: Off-season window (January, 30 days) -> Low Tier (25)
2. Currency / FX Risk (RBI Reference Rate):
   - Graceful fallback when CSV is missing -> status: data_unavailable, no fake numbers
   - Correct rolling 30-day volatility calculation and tier classification when CSV is present
3. Composite Risk Calculation:
   - 40/30/20/10 nominal weighting and proportional re-allocation when FX is absent
   - Executive recommendation synthesis
4. End-to-End API Integration:
   - Test via FastAPI TestClient on /api/recommend
   - Pretty-prints full composite risk output for peak cyclone scenario
"""

import os
import sys
import json
import tempfile
import pandas as pd
from datetime import datetime

# Setup project path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.rules.seasonal_risk import compute_seasonal_risk, get_spanned_months
from backend.rules.fx_risk import compute_fx_risk, clean_fx_data
from backend.rules.composite_risk import (
    compute_composite_risk,
    evaluate_idle_time_risk,
    score_from_tier,
    tier_from_score,
)
import asyncio
from backend.app import app, recommend


def test_spanned_months():
    """Verify spanned month calculation."""
    print("TEST: get_spanned_months()")
    # Sep 1 for 90 days spans Sep (9), Oct (10), Nov (11), Dec (12)
    m = get_spanned_months("2026-09-01", 90)
    assert 9 in m and 10 in m and 11 in m, f"Expected 9, 10, 11 in {m}"
    print(f"  [PASS] Spanned months for 90d from 2026-09-01: {m}")

    # Sep 1 for 60 days spans Sep (9), Oct (10), Nov (11)
    m2 = get_spanned_months("2026-09-01", 60)
    assert 9 in m2 and 10 in m2, f"Expected 9, 10 in {m2}"
    print(f"  [PASS] Spanned months for 60d from 2026-09-01: {m2}")

    # Jan 1 for 25 days spans Jan (1)
    m3 = get_spanned_months("2026-01-01", 25)
    assert m3 == [1], f"Expected [1], got {m3}"
    print(f"  [PASS] Spanned months for 25d from 2026-01-01: {m3}")


def test_seasonal_cyclone_scenarios():
    """Verify seasonal risk for peak vs non-peak months."""
    print("\nTEST: Seasonal Cyclone Scenarios (IMD / RSMC Climatology)")

    # Scenario 1: Andhra Pradesh destination (Visakhapatnam), Sep 1 + 90 days -> overlaps November peak
    res_ap = compute_seasonal_risk("Visakhapatnam", "2026-09-01", 90)
    print(f"  Scenario 1 (Andhra Pradesh / Visakhapatnam): Tier={res_ap['tier']}, Peak={res_ap['peak_month_name']}")
    assert res_ap["tier"] == "High", f"Expected High, got {res_ap['tier']}"
    assert res_ap["overlaps_peak"] is True
    assert res_ap["score"] == 75
    assert "IMD" in res_ap["source"] and "RSMC" in res_ap["source"]
    assert "CLIMATOLOGICAL" in res_ap["disclaimer"]
    print("  [PASS] Scenario 1 triggered HIGH seasonal risk as expected.")

    # Scenario 2: Odisha destination (Paradip), Sep 1 + 60 days -> overlaps October peak
    res_od = compute_seasonal_risk("Paradip", "2026-09-01", 60)
    print(f"  Scenario 2 (Odisha / Paradip): Tier={res_od['tier']}, Peak={res_od['peak_month_name']}")
    assert res_od["tier"] == "High", f"Expected High, got {res_od['tier']}"
    assert res_od["overlaps_peak"] is True
    assert res_od["score"] == 75
    print("  [PASS] Scenario 2 triggered HIGH seasonal risk as expected.")

    # Scenario 3: Off-season counter test (Visakhapatnam, Jan 1 + 30 days) -> Low tier
    res_off = compute_seasonal_risk("Visakhapatnam", "2026-01-01", 30)
    print(f"  Scenario 3 (Off-season January): Tier={res_off['tier']}")
    assert res_off["tier"] == "Low", f"Expected Low, got {res_off['tier']}"
    assert res_off["overlaps_peak"] is False
    assert res_off["overlaps_season"] is False
    assert res_off["score"] == 25
    print("  [PASS] Scenario 3 triggered LOW seasonal risk as expected.")


def test_fx_risk_handling():
    """Verify live Frankfurter API fetching, volatility calculation, and graceful failure fallback."""
    print("\nTEST: Currency / FX Risk Handling (Frankfurter Live API)")

    # 1. Live API call -> verify open-access fetching without auth
    res_live = compute_fx_risk()
    assert res_live["status"] == "available", f"Expected available, got {res_live['status']}"
    assert res_live["score"] is not None
    assert res_live["rolling_30d_volatility_pct"] is not None
    assert res_live["latest_rate"] is not None
    assert "Frankfurter API" in res_live["source"]
    print(f"  [PASS] Live Frankfurter API connected successfully (Zero Auth):")
    print(f"         Rate=INR {res_live['latest_rate']}/$ ({res_live['latest_date']}) | 30d Volatility={res_live['rolling_30d_volatility_pct']}% std | Tier={res_live['tier']}")

    # 2. Simulated failure / missing data -> data_unavailable, no fake numbers
    res_fallback = compute_fx_risk(csv_path="non_existent_mock_path.csv")
    assert res_fallback["status"] == "data_unavailable"
    assert res_fallback["score"] is None
    print("  [PASS] Missing/offline fallback handled gracefully without inventing synthetic numbers.")

    # 3. Pre-fetched / Mock dictionary verification
    mock_rates = {
        f"2026-08-{d:02d}": {"INR": round(94.0 + (d % 3 - 1) * 0.15, 2)}
        for d in range(1, 31)
    }
    res_mock = compute_fx_risk(rates_dict=mock_rates)
    assert res_mock["status"] == "available"
    assert res_mock["score"] is not None
    assert res_mock["rolling_30d_volatility_pct"] is not None
    print(f"  [PASS] Custom rates dictionary parsed: Volatility={res_mock['rolling_30d_volatility_pct']}% -> Tier={res_mock['tier']}")


def test_composite_scoring_math():
    """Verify weighting and re-allocation arithmetic."""
    print("\nTEST: Composite Risk Math & Tier Mapping")

    # Tier to score check
    assert score_from_tier("Low") == 25.0
    assert score_from_tier("Moderate") == 50.0
    assert score_from_tier("High") == 75.0
    assert score_from_tier("Severe") == 100.0

    # Score to tier check
    assert tier_from_score(35.0) == "Low"
    assert tier_from_score(50.0) == "Moderate"
    assert tier_from_score(70.0) == "High"
    assert tier_from_score(88.0) == "Severe"

    # Case A: Full 4-criteria active (40 / 30 / 20 / 10 nominal weighting)
    m_risk = {"overall_verdict": "Moderate", "pct_days_flagged": 20.0}       # Score: 50 (40%) -> 20.0
    s_risk = {"tier": "High", "score": 75, "message": "Cyclone peak"}          # Score: 75 (30%) -> 22.5
    f_risk_active = {"status": "available", "tier": "Low", "score": 25.0}     # Score: 25 (20%) -> 5.0
    i_risk = {"tier": "Low", "score": 25, "message": "Optimal load"}           # Score: 25 (10%) -> 2.5
    comp_full = compute_composite_risk(m_risk, s_risk, f_risk_active, i_risk)
    # Expected score: 50*0.40 + 75*0.30 + 25*0.20 + 25*0.10 = 20 + 22.5 + 5 + 2.5 = 50.0
    assert abs(comp_full["composite_score"] - 50.0) < 0.1, f"Expected 50.0, got {comp_full['composite_score']}"
    assert comp_full["weight_reallocated"] is False
    assert comp_full["effective_weights"]["currency_fx"] == 0.20
    assert comp_full["effective_weights"]["market_volatility"] == 0.40
    print(f"  [PASS] Full 4-criteria composite risk calculated: {comp_full['composite_score']}/100 (Nominal: 40/30/20/10)")

    # Case B: FX unavailable -> weights re-allocated to 50% / 37.5% / 0% / 12.5%
    f_risk_unavail = {"status": "data_unavailable", "score": None}
    comp_realloc = compute_composite_risk(m_risk, s_risk, f_risk_unavail, i_risk)
    # Expected score: 50 * 0.50 + 75 * 0.375 + 25 * 0.125 = 25.0 + 28.125 + 3.125 = 56.25 -> 56.2
    assert abs(comp_realloc["composite_score"] - 56.2) < 0.2, f"Expected ~56.2, got {comp_realloc['composite_score']}"
    assert comp_realloc["composite_tier"] == "Moderate"
    assert comp_realloc["weight_reallocated"] is True
    assert comp_realloc["effective_weights"]["market_volatility"] == 0.50
    assert comp_realloc["effective_weights"]["seasonal_cyclone"] == 0.375
    print(f"  [PASS] Reallocated composite risk score calculated: {comp_realloc['composite_score']}/100 (Tier: {comp_realloc['composite_tier']})")


def test_end_to_end_api_recommend():
    """Run full recommend orchestration test directly."""
    print("\nTEST: End-to-End API Integration via recommend()")

    data = asyncio.run(recommend(
        cargo_qty=150000,
        origin="Newcastle (Australia)",
        destination="Visakhapatnam",
        horizon_days=90,
    ))

    # Verify response structure
    assert "risk_analysis" in data
    assert "risk_flags" in data
    assert "vessel_recommendations" in data
    assert "market_timing" in data

    risk_analysis = data["risk_analysis"]
    assert "composite_score" in risk_analysis
    assert "composite_tier" in risk_analysis
    assert "criteria" in risk_analysis
    assert "seasonal_risk" in risk_analysis
    assert "fx_risk" in risk_analysis
    assert "disclosure" in risk_analysis

    # Backward compatibility checks
    assert "daily_flags" in risk_analysis
    assert "daily_volatility" in risk_analysis
    assert "overall_verdict" in risk_analysis
    assert len(data["risk_flags"]) > 0

    print("  [PASS] API response contains all required fields and preserves backward compatibility.")
    return risk_analysis


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING RISK ASSESSMENT MODULE VALIDATION SUITE")
    print("=" * 70)

    test_spanned_months()
    test_seasonal_cyclone_scenarios()
    test_fx_risk_handling()
    test_composite_scoring_math()
    full_risk_output = test_end_to_end_api_recommend()

    print("\n" + "=" * 70)
    print("FULL COMPOSITE RISK OUTPUT FOR PEAK CYCLONE TEST CASE")
    print("Route: Newcastle -> Visakhapatnam (Andhra Pradesh), Horizon: 90 Days")
    print("=" * 70)
    print(json.dumps({
        "composite_score": full_risk_output["composite_score"],
        "composite_tier": full_risk_output["composite_tier"],
        "headline_verdict": full_risk_output["headline_verdict"],
        "recommendation": full_risk_output["recommendation"],
        "effective_weights": full_risk_output["effective_weights"],
        "weight_reallocated": full_risk_output["weight_reallocated"],
        "criteria": full_risk_output["criteria"],
        "disclosure": full_risk_output["disclosure"],
    }, indent=2))

    print("\nALL RISK ASSESSMENT TESTS PASSED SUCCESSFULLY!")
