"""
Composite Risk Scoring Module.

Combines multiple risk dimensions into a unified, weighted Composite Risk Score:
1. Market Volatility (40%) - Baltic Dry Index forecast confidence-band spread
2. Seasonal / Cyclone Risk (30%) - IMD/RSMC Bay of Bengal landfall climatology
3. Currency / FX Risk (20%) - Frankfurter API live USD/INR central bank exchange rate volatility
4. Idle-Time / Fleet Utilization (10%) - Cargo-to-vessel capacity utilization & rate momentum

Disclosure & Rationale:
    The 40 / 30 / 20 / 10 weighting scheme is disclosed as a reasonable starting judgment
    based on commercial maritime freight practice rather than a scientifically derived figure.
    - Market Volatility (40%): Direct determinant of freight charter cost variance.
    - Seasonal / Cyclone Risk (30%): Physical navigation risk causing port closures, demurrage,
      and vessel route diversions on India's East Coast.
    - Currency / FX Risk (20%): Freight is invoiced in USD; domestic buyers settle in INR,
      creating currency landed cost exposure.
    - Idle-Time / Utilization (10%): Operational efficiency and contract structure alignment.

Tier-to-Numeric Score Mapping:
    - Low: 25
    - Moderate: 50
    - High: 75
    - Severe: 100
    (Sub-tiers: Low-Moderate: 37.5, Moderate-High: 62.5, High-Severe: 87.5)

Composite Score-to-Tier Mapping:
    - Score < 40.0: Low Risk
    - 40.0 <= Score < 65.0: Moderate Risk
    - 65.0 <= Score < 85.0: High Risk
    - Score >= 85.0: Severe Risk
"""

import os
from typing import Dict, Any, List, Optional


DEFAULT_WEIGHTS = {
    "market_volatility": 0.40,
    "seasonal_cyclone": 0.30,
    "currency_fx": 0.20,
    "idle_utilization": 0.10,
}

TIER_TO_SCORE = {
    "low": 25.0,
    "low-moderate": 37.5,
    "moderate": 50.0,
    "moderate-high": 62.5,
    "high": 75.0,
    "high-severe": 87.5,
    "severe": 100.0,
}


def score_from_tier(tier: str, default: float = 25.0) -> float:
    """Convert a categorical tier string to its numeric score (25 to 100)."""
    if not tier:
        return default
    cleaned = str(tier).strip().lower()
    return TIER_TO_SCORE.get(cleaned, default)


def tier_from_score(score: float) -> str:
    """Map a numeric composite score back to a categorical tier label."""
    if score >= 85.0:
        return "Severe"
    elif score >= 65.0:
        return "High"
    elif score >= 40.0:
        return "Moderate"
    else:
        return "Low"


def evaluate_idle_time_risk(idle_flags: List[Dict[str, Any]], cargo_qty: float, vessel_spec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate idle-time & fleet utilization into a structured risk criterion.
    """
    utilization_pct = None
    if vessel_spec and "dwt_max" in vessel_spec and vessel_spec["dwt_max"] > 0:
        utilization_pct = round((cargo_qty / vessel_spec["dwt_max"]) * 100.0, 1)

    has_under_util = any(f.get("type") == "under_utilization" for f in idle_flags)
    has_declining = any(f.get("type") == "declining_market" for f in idle_flags)

    # Classify tier
    if utilization_pct is not None and utilization_pct < 60.0:
        tier = "High"
        score = 75.0
        message = (
            f"Significant capacity under-utilization ({utilization_pct:.1f}% load factor). "
            f"Chartering dead-freight penalty is severe -- recommend downsizing vessel class."
        )
    elif has_under_util or (has_declining and utilization_pct is not None and utilization_pct < 85.0):
        tier = "Moderate"
        score = 50.0
        util_str = f"{utilization_pct:.1f}%" if utilization_pct is not None else "< 80%"
        message = (
            f"Moderate utilization exposure ({util_str} load factor or downward market trend). "
            f"Review parcel sizing or consider multiple-voyage contracting (COA)."
        )
    else:
        tier = "Low"
        score = 25.0
        util_str = f"{utilization_pct:.1f}%" if utilization_pct is not None else ">= 80%"
        message = (
            f"Optimal capacity utilization ({util_str} load factor). "
            f"No structural idle-time or dead-freight penalties identified."
        )

    return {
        "tier": tier,
        "score": score,
        "weight": DEFAULT_WEIGHTS["idle_utilization"],
        "utilization_pct": utilization_pct,
        "flags_count": len(idle_flags),
        "message": message,
        "source": "Vessel specifications & voyage cargo utilization geometry",
    }


def compute_composite_risk(
    market_risk: Dict[str, Any],
    seasonal_risk: Dict[str, Any],
    fx_risk: Dict[str, Any],
    idle_risk: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute the weighted composite risk score across all four criteria.

    Handles missing FX data gracefully by proportionally re-allocating its 20%
    weight across the remaining three active criteria.
    """
    # 1. Extract scores
    market_verdict = market_risk.get("overall_verdict", "Low")
    market_score = score_from_tier(market_verdict)

    seasonal_tier = seasonal_risk.get("tier", "Low")
    seasonal_score = float(seasonal_risk.get("score") or score_from_tier(seasonal_tier))

    idle_tier = idle_risk.get("tier", "Low")
    idle_score = float(idle_risk.get("score") or score_from_tier(idle_tier))

    # Check FX availability
    fx_available = fx_risk.get("status") == "available" and fx_risk.get("score") is not None

    if fx_available:
        fx_tier = fx_risk.get("tier", "Low")
        fx_score = float(fx_risk.get("score") or score_from_tier(fx_tier))
        active_weights = dict(DEFAULT_WEIGHTS)
        weight_reallocated = False
    else:
        fx_tier = "Unavailable"
        fx_score = 0.0
        # Proportional re-allocation across active 80% (Market=40%, Seasonal=30%, Idle=10%)
        active_weights = {
            "market_volatility": round(0.40 / 0.80, 4),  # 0.5000 (50.0%)
            "seasonal_cyclone": round(0.30 / 0.80, 4),   # 0.3750 (37.5%)
            "currency_fx": 0.0,                           # 0.0%
            "idle_utilization": round(0.10 / 0.80, 4),   # 0.1250 (12.5%)
        }
        weight_reallocated = True

    # 2. Compute weighted average
    if fx_available:
        composite_score = (
            market_score * active_weights["market_volatility"]
            + seasonal_score * active_weights["seasonal_cyclone"]
            + fx_score * active_weights["currency_fx"]
            + idle_score * active_weights["idle_utilization"]
        )
    else:
        composite_score = (
            market_score * active_weights["market_volatility"]
            + seasonal_score * active_weights["seasonal_cyclone"]
            + idle_score * active_weights["idle_utilization"]
        )

    composite_score = round(composite_score, 1)
    composite_tier = tier_from_score(composite_score)

    # 3. Formulate synthesized executive recommendation
    elevated_drivers = []
    if score_from_tier(market_verdict) >= 50:
        elevated_drivers.append(f"market forecast volatility ({market_verdict})")
    if seasonal_score >= 50:
        elevated_drivers.append(f"seasonal cyclone climatology ({seasonal_tier})")
    if fx_available and fx_score >= 50:
        elevated_drivers.append(f"USD/INR exchange rate turbulence ({fx_tier})")
    if idle_score >= 50:
        elevated_drivers.append(f"vessel capacity utilization ({idle_tier})")

    if composite_tier in ["High", "Severe"]:
        if elevated_drivers:
            drivers_str = " and ".join(elevated_drivers)
            rec = (
                f"Elevated composite risk ({composite_score}/100) driven by {drivers_str}. "
                f"Strongly recommend tightening contract terms, locking laycan buffers, and hedging currency/rate exposures."
            )
        else:
            rec = f"Elevated composite risk ({composite_score}/100). Implement conservative contracting strategies."
    elif composite_tier == "Moderate":
        if elevated_drivers:
            drivers_str = " and ".join(elevated_drivers)
            rec = (
                f"Moderate composite risk ({composite_score}/100), with notable exposure in {drivers_str}. "
                f"Standard contracting terms acceptable with targeted contingency buffers."
            )
        else:
            rec = f"Moderate composite risk ({composite_score}/100). Maintain standard commercial vigilance."
    else:
        rec = (
            f"Low composite risk ({composite_score}/100) across all evaluated dimensions. "
            f"Market volatility, cyclone climatology, and operational utilization align favourably for standard fixture contracting."
        )

    # 4. Detailed breakdown per criterion for UI presentation
    criteria_summary = {
        "market_volatility": {
            "name": "Market Rate Volatility",
            "tier": market_verdict,
            "score": market_score,
            "nominal_weight": DEFAULT_WEIGHTS["market_volatility"],
            "effective_weight": active_weights["market_volatility"],
            "contribution": round(market_score * active_weights["market_volatility"], 1),
            "source": "Baltic Dry Index (Prophet Forecasting Engine)",
            "summary": f"{market_verdict} volatility spread ({market_risk.get('pct_days_flagged', 0):.0f}% of days flagged)",
        },
        "seasonal_cyclone": {
            "name": "Seasonal Cyclone Risk",
            "tier": seasonal_tier,
            "score": seasonal_score,
            "nominal_weight": DEFAULT_WEIGHTS["seasonal_cyclone"],
            "effective_weight": active_weights["seasonal_cyclone"],
            "contribution": round(seasonal_score * active_weights["seasonal_cyclone"], 1),
            "source": "India Meteorological Department (IMD) / RSMC New Delhi Climatology",
            "summary": seasonal_risk.get("message", "Climatological risk evaluation"),
        },
        "currency_fx": {
            "name": "Currency FX Risk (USD/INR)",
            "tier": fx_tier,
            "score": fx_score if fx_available else None,
            "status": fx_risk.get("status", "available"),
            "nominal_weight": DEFAULT_WEIGHTS["currency_fx"],
            "effective_weight": active_weights["currency_fx"],
            "contribution": round(fx_score * active_weights["currency_fx"], 1) if fx_available else 0.0,
            "source": "Frankfurter API (live, fetched at request time from central bank reference rates)",
            "summary": fx_risk.get("message", "USD/INR exchange rate risk"),
        },
        "idle_utilization": {
            "name": "Idle-Time & Fleet Utilization",
            "tier": idle_tier,
            "score": idle_score,
            "nominal_weight": DEFAULT_WEIGHTS["idle_utilization"],
            "effective_weight": active_weights["idle_utilization"],
            "contribution": round(idle_score * active_weights["idle_utilization"], 1),
            "source": "Vessel specifications & voyage parcel scheduling",
            "summary": idle_risk.get("message", "Capacity utilization evaluation"),
        },
    }

    disclosure_note = (
        "Weighting Scheme Rationale: Market Volatility (40%), Seasonal/Cyclone Risk (30%), "
        "Currency/FX Risk (20%), Idle-Time/Utilization (10%). Disclosed as an operational starting "
        "judgment rather than a scientifically derived figure. Data sources: Baltic Dry Index (freight), "
        "IMD/RSMC New Delhi (cyclone landfall climatology), and Frankfurter API (live central bank reference rates). "
        "Seasonal risk reflects historical climatological frequency, not live storm tracking."
    )
    if weight_reallocated:
        disclosure_note += (
            " Note: Live FX API unreachable; FX weight (20%) was proportionally re-allocated "
            "across active criteria: Market Volatility (50.0%), Seasonal Risk (37.5%), Idle/Utilization (12.5%)."
        )

    return {
        "composite_score": composite_score,
        "composite_tier": composite_tier,
        "headline_verdict": f"{composite_tier} Risk",
        "recommendation": rec,
        "nominal_weights": DEFAULT_WEIGHTS,
        "effective_weights": active_weights,
        "weight_reallocated": weight_reallocated,
        "criteria": criteria_summary,
        "disclosure": disclosure_note,
    }


if __name__ == "__main__":
    # Test composite scoring
    sample_market = {"overall_verdict": "Moderate", "pct_days_flagged": 25.0}
    sample_seasonal = {"tier": "High", "score": 75, "message": "Peak cyclone month overlap"}
    sample_fx_unavail = {"status": "data_unavailable", "score": None}
    sample_idle = {"tier": "Low", "score": 25, "message": "Optimal 95% utilization"}

    comp = compute_composite_risk(sample_market, sample_seasonal, sample_fx_unavail, sample_idle)
    print("Composite Risk (FX Unavailable):")
    print(f"  Score: {comp['composite_score']}/100 -> Tier: {comp['composite_tier']}")
    print(f"  Effective Weights: {comp['effective_weights']}")
    print(f"  Recommendation: {comp['recommendation']}")
