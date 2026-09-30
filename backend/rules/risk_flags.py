"""
Risk flags module.

Analyzes forecast data to identify periods of market volatility
using severity tiers (Low / Moderate / High / Severe) and produces
a structured risk analysis object with summary statistics, trend
analysis, and actionable recommendations.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Severity tier thresholds (confidence-band width as % of yhat)
# ---------------------------------------------------------------------------
TIER_MODERATE = 15   # 15-20%
TIER_HIGH = 20       # 20-25%
TIER_SEVERE = 25     # 25%+


def _classify_tier(volatility_pct):
    """Return the severity tier label for a given volatility percentage."""
    if volatility_pct >= TIER_SEVERE:
        return "severe"
    elif volatility_pct >= TIER_HIGH:
        return "high"
    elif volatility_pct >= TIER_MODERATE:
        return "moderate"
    else:
        return "low"


def _compute_trend(values):
    """
    Fit a simple OLS line to the values and classify the slope.

    Returns one of: "increasing", "decreasing", "stable"
    along with the raw slope value (pct-points per day).
    """
    n = len(values)
    if n < 3:
        return "stable", 0.0

    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)

    # OLS slope = Cov(x,y) / Var(x)
    x_mean = x.mean()
    y_mean = y.mean()
    slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)

    # Total change over the window (slope * n days)
    total_change = slope * n

    # Classify: "increasing" if volatility grows by > 2 pct-points across
    # the window, "decreasing" if it drops by more than 2, else "stable".
    if total_change > 2.0:
        return "increasing", round(float(slope), 4)
    elif total_change < -2.0:
        return "decreasing", round(float(slope), 4)
    else:
        return "stable", round(float(slope), 4)


def _derive_overall_verdict(highest_tier, pct_moderate_plus):
    """
    Derive an overall risk verdict from the highest tier observed
    and the fraction of days at Moderate or above.
    """
    if highest_tier == "severe":
        if pct_moderate_plus > 60:
            return "Severe"
        return "High-Severe"
    elif highest_tier == "high":
        if pct_moderate_plus > 50:
            return "High"
        return "Moderate-High"
    elif highest_tier == "moderate":
        if pct_moderate_plus > 40:
            return "Moderate"
        return "Low-Moderate"
    else:
        return "Low"


def _build_recommendation(verdict, pct_flagged, peak_vol, peak_date,
                          first_moderate_date, trend_direction, horizon_days):
    """
    Build a specific, data-driven recommendation sentence
    (not generic boilerplate).
    """
    parts = []

    if verdict in ("Severe", "High-Severe", "High"):
        parts.append(
            f"Market uncertainty is elevated -- {pct_flagged:.0f}% of the "
            f"{horizon_days}-day window shows confidence-band width >=15%, "
            f"peaking at {peak_vol:.1f}% on {peak_date}."
        )
        if trend_direction == "increasing":
            parts.append(
                "Volatility is widening over the horizon, so delaying "
                "commitment increases exposure."
            )
        parts.append(
            "Prefer shorter contract durations or index-linked fixtures "
            "to cap downside."
        )
    elif verdict in ("Moderate-High", "Moderate"):
        parts.append(
            f"Moderate uncertainty: {pct_flagged:.0f}% of forecast days "
            f"exceed the 15% band-width threshold."
        )
        if first_moderate_date:
            parts.append(
                f"Volatility first crosses into the Moderate tier on "
                f"{first_moderate_date} -- fixing terms before that date "
                f"captures the lower-uncertainty window."
            )
        if trend_direction == "decreasing":
            parts.append(
                "Volatility is narrowing over the horizon, which favours "
                "waiting for better visibility before locking rates."
            )
    elif verdict == "Low-Moderate":
        parts.append(
            f"Mostly stable outlook with only {pct_flagged:.0f}% of days "
            f"flagged."
        )
        if first_moderate_date:
            parts.append(
                f"First Moderate-tier day is {first_moderate_date}; "
                f"contracting before then carries minimal rate uncertainty."
            )
    else:
        parts.append(
            "Confidence bands remain narrow across the entire forecast "
            "window -- low rate uncertainty. Standard contracting terms "
            "are appropriate."
        )

    return " ".join(parts)


def compute_risk_flags(forecast_data):
    """
    Compute a structured risk analysis from forecast confidence bands.

    For each forecast point, computes:
        volatility_pct = (yhat_upper - yhat_lower) / yhat * 100

    Returns a dict:
    {
        "overall_verdict": str,
        "pct_days_flagged": float,          # % of days at Moderate+
        "peak_volatility": {"value": float, "date": str},
        "first_moderate_date": str | None,
        "volatility_trend": str,            # "increasing" / "decreasing" / "stable"
        "volatility_trend_slope": float,    # pct-points per day
        "recommendation": str,
        "daily_volatility": [{"date": str, "volatility_pct": float}, ...],
        "daily_flags": [                    # only days at Moderate+
            {"date": str, "volatility_pct": float, "tier": str, "message": str},
            ...
        ],
    }
    """
    if not forecast_data:
        return {
            "overall_verdict": "Low",
            "pct_days_flagged": 0,
            "peak_volatility": {"value": 0, "date": None},
            "first_moderate_date": None,
            "volatility_trend": "stable",
            "volatility_trend_slope": 0.0,
            "recommendation": "No forecast data available for risk analysis.",
            "daily_volatility": [],
            "daily_flags": [],
        }

    # ------------------------------------------------------------------
    # Per-day volatility computation
    # ------------------------------------------------------------------
    daily_volatility = []
    daily_flags = []
    vol_values = []         # raw volatility_pct series for trend analysis
    peak_vol = 0.0
    peak_date = None
    first_moderate_date = None
    highest_tier = "low"
    tier_rank = {"low": 0, "moderate": 1, "high": 2, "severe": 3}

    MIN_BDI_THRESHOLD = 100.0   # Operational floor threshold to avoid denominator explosion
    MAX_VOLATILITY_CAP = 100.0  # Cap percentage volatility to sane 0-100% scale

    for point in forecast_data:
        yhat = point["yhat"]
        band_width = max(point["yhat_upper"] - point["yhat_lower"], 0.0)

        if yhat < MIN_BDI_THRESHOLD:
            # Low absolute rate: normalize against operational baseline to prevent runaway ratio
            raw_vol = (band_width / MIN_BDI_THRESHOLD) * 100.0 if MIN_BDI_THRESHOLD > 0 else 0.0
        else:
            raw_vol = (band_width / yhat) * 100.0

        vol_pct = min(raw_vol, MAX_VOLATILITY_CAP)
        vol_pct_rounded = round(vol_pct, 2)
        tier = _classify_tier(vol_pct)
        date_str = point["ds"]

        daily_volatility.append({
            "date": date_str,
            "volatility_pct": vol_pct_rounded,
        })
        vol_values.append(vol_pct)

        # Track peak
        if vol_pct > peak_vol:
            peak_vol = vol_pct
            peak_date = date_str

        # Track highest tier
        if tier_rank[tier] > tier_rank[highest_tier]:
            highest_tier = tier

        # Track first moderate+ date
        if first_moderate_date is None and tier != "low":
            first_moderate_date = date_str

        # Flagged days (Moderate+)
        if tier != "low":
            tier_labels = {
                "moderate": "Moderate",
                "high": "High",
                "severe": "Severe",
            }
            daily_flags.append({
                "date": date_str,
                "volatility_pct": vol_pct_rounded,
                "tier": tier,
                "message": (
                    f"{tier_labels[tier]} volatility on {date_str}: "
                    f"{vol_pct:.1f}% confidence-band width."
                ),
            })

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------
    total_days = len(forecast_data)
    flagged_count = len(daily_flags)
    pct_flagged = (flagged_count / total_days * 100) if total_days > 0 else 0

    trend_direction, trend_slope = _compute_trend(vol_values)
    verdict = _derive_overall_verdict(highest_tier, pct_flagged)
    recommendation = _build_recommendation(
        verdict, pct_flagged, peak_vol, peak_date,
        first_moderate_date, trend_direction, total_days,
    )

    return {
        "overall_verdict": verdict,
        "pct_days_flagged": round(pct_flagged, 1),
        "peak_volatility": {
            "value": round(peak_vol, 2),
            "date": peak_date,
        },
        "first_moderate_date": first_moderate_date,
        "volatility_trend": trend_direction,
        "volatility_trend_slope": trend_slope,
        "recommendation": recommendation,
        "daily_volatility": daily_volatility,
        "daily_flags": daily_flags,
    }


if __name__ == "__main__":
    # Quick test with synthetic forecast data spanning a range of tiers
    test_data = [
        {"ds": "2026-09-01", "yhat": 2000, "yhat_lower": 1900, "yhat_upper": 2100},  # 10% → Low
        {"ds": "2026-09-02", "yhat": 2000, "yhat_lower": 1850, "yhat_upper": 2150},  # 15% → Low (boundary)
        {"ds": "2026-09-03", "yhat": 2000, "yhat_lower": 1820, "yhat_upper": 2180},  # 18% → Moderate
        {"ds": "2026-09-04", "yhat": 2000, "yhat_lower": 1780, "yhat_upper": 2220},  # 22% → High
        {"ds": "2026-09-05", "yhat": 2000, "yhat_lower": 1700, "yhat_upper": 2300},  # 30% → Severe
        {"ds": "2026-09-06", "yhat": 2000, "yhat_lower": 1750, "yhat_upper": 2250},  # 25% → Severe
        {"ds": "2026-09-07", "yhat": 2000, "yhat_lower": 1800, "yhat_upper": 2200},  # 20% → High (boundary)
        {"ds": "2026-09-08", "yhat": 2000, "yhat_lower": 1850, "yhat_upper": 2150},  # 15% → Low (boundary)
        {"ds": "2026-09-09", "yhat": 2000, "yhat_lower": 1900, "yhat_upper": 2100},  # 10% → Low
        {"ds": "2026-09-10", "yhat": 2000, "yhat_lower": 1920, "yhat_upper": 2080},  #  8% → Low
    ]

    result = compute_risk_flags(test_data)

    print(f"Overall verdict:       {result['overall_verdict']}")
    print(f"% days flagged:        {result['pct_days_flagged']}%")
    print(f"Peak volatility:       {result['peak_volatility']['value']}% on {result['peak_volatility']['date']}")
    print(f"First moderate date:   {result['first_moderate_date']}")
    print(f"Volatility trend:      {result['volatility_trend']} (slope={result['volatility_trend_slope']})")
    print(f"Recommendation:        {result['recommendation']}")
    print(f"Daily flags count:     {len(result['daily_flags'])}")
    print(f"Daily volatility count: {len(result['daily_volatility'])}")

    print("\nFlagged days:")
    for f in result["daily_flags"]:
        print(f"   {f['date']}: {f['volatility_pct']}% [{f['tier']}] — {f['message']}")
