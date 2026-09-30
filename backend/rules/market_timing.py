"""
Market Timing Module -- Requirement (a): Optimal Market Entry Timing.

Analyzes freight forecast curves across rolling windows to identify the
optimal contracting entry window. Balances expected cost against forecast
confidence interval width (volatility uncertainty), and determines whether
the charterer should fix contracts immediately ("CHARTER NOW"), defer
commitment ("WAIT FOR WINDOW"), or track developments closely ("MONITOR").
"""

from typing import List, Dict, Any


def _confidence_descriptor(volatility_pct: float) -> str:
    """Return a human-readable confidence descriptor based on band width."""
    if volatility_pct < 20.0:
        return "high confidence"
    elif volatility_pct < 45.0:
        return "moderate confidence"
    elif volatility_pct < 90.0:
        return "moderate-to-wide uncertainty"
    else:
        return "elevated uncertainty"


def find_optimal_entry_window(
    forecast_data: List[Dict[str, Any]],
    window_days: int = 7
) -> Dict[str, Any]:
    """
    Identify the optimal chartering entry window across the forecast horizon.

    Algorithm:
    1. Aggregates rolling average yhat, yhat_lower, and yhat_upper across
       window_days-sized sliding windows (default 7 days).
    2. Identifies the window with the lowest expected rate (primary candidate).
    3. Examines all candidate windows within 5% of the minimum cost. Selects
       the candidate with the lowest confidence band width (volatility),
       favoring price certainty over negligible price savings.
    4. Evaluates the current/nearest-term window (Day 1 to window_days):
       - If the current window is already within 5% of the optimal future window,
         or if rates are upward-trending, recommends "CHARTER NOW" (since near-term
         windows carry the highest model accuracy and avoid operational deferral risk).
       - If future windows offer >5% savings with acceptable uncertainty,
         recommends "WAIT FOR WINDOW".
       - If potential savings are marginal or future uncertainty expands excessively,
         recommends "MONITOR".

    Args:
        forecast_data: List of dicts: [{"ds": "YYYY-MM-DD", "yhat": float,
                                       "yhat_lower": float, "yhat_upper": float}, ...]
        window_days: Size of rolling contracting window in calendar days (default 7).

    Returns:
        Structured dict with keys:
        - recommended_window_start: ISO date string
        - recommended_window_end: ISO date string
        - expected_avg_rate: float (mean yhat across recommended window)
        - expected_confidence: float (volatility % across recommended window)
        - pct_below_horizon_avg: float (% savings vs full horizon average)
        - verdict: "CHARTER NOW" | "WAIT FOR WINDOW" | "MONITOR"
        - reasoning: str (explainable, data-tied operational rationale)
    """
    if not forecast_data:
        return {
            "recommended_window_start": None,
            "recommended_window_end": None,
            "expected_avg_rate": 0.0,
            "expected_confidence": 0.0,
            "pct_below_horizon_avg": 0.0,
            "verdict": "MONITOR",
            "reasoning": "No forecast data available to compute market entry timing.",
        }

    n = len(forecast_data)
    # Adjust window size if horizon is shorter than requested window
    effective_window = min(window_days, n)
    if effective_window < 1:
        effective_window = 1

    # Full horizon benchmark metrics
    horizon_avg = sum(p["yhat"] for p in forecast_data) / n

    MIN_BDI_THRESHOLD = 100.0   # Operational baseline floor to prevent denominator blowout
    MAX_VOLATILITY_CAP = 100.0  # Cap percentage volatility to realistic 0-100% scale

    # Step 1: Compute rolling window metrics
    windows = []
    for i in range(n - effective_window + 1):
        w = forecast_data[i : i + effective_window]
        avg_y = sum(p["yhat"] for p in w) / effective_window
        avg_lo = sum(p["yhat_lower"] for p in w) / effective_window
        avg_hi = sum(p["yhat_upper"] for p in w) / effective_window
        band_width = max(avg_hi - avg_lo, 0.0)

        # Safety check: if expected rate is near zero or below operational floor,
        # normalize against threshold baseline to avoid inflated, meaningless ratios
        if avg_y < MIN_BDI_THRESHOLD:
            raw_vol = (band_width / MIN_BDI_THRESHOLD * 100.0) if MIN_BDI_THRESHOLD > 0 else 0.0
        else:
            raw_vol = (band_width / avg_y * 100.0)

        # Cap volatility percentage to realistic 0-100% scale
        vol_pct = min(round(raw_vol, 1), MAX_VOLATILITY_CAP)

        windows.append({
            "index": i,
            "start": w[0]["ds"],
            "end": w[-1]["ds"],
            "avg_rate": round(avg_y, 2),
            "avg_lower": round(avg_lo, 2),
            "avg_upper": round(avg_hi, 2),
            "volatility": vol_pct,
        })

    # Step 2: Primary candidate with lowest expected rate
    min_window = min(windows, key=lambda x: x["avg_rate"])

    # Step 3: Candidate pool within 5% of minimum expected cost
    cost_threshold = min_window["avg_rate"] * 1.05
    near_optimal_pool = [w for w in windows if w["avg_rate"] <= cost_threshold]

    # Find the candidate within 5% cost pool that offers the lowest volatility
    lowest_vol_candidate = min(near_optimal_pool, key=lambda x: x["volatility"])

    # If the candidate with lower volatility provides a meaningful uncertainty reduction
    # (at least 3 percentage points lower band width than min_window), prefer it;
    # otherwise stick with the cheaper min_window.
    if (min_window["volatility"] - lowest_vol_candidate["volatility"]) >= 3.0:
        best_future_window = lowest_vol_candidate
    else:
        best_future_window = min_window

    # Step 4: Evaluate the current nearest-term window (index 0)
    current_window = windows[0]
    curr_rate = current_window["avg_rate"]
    best_rate = best_future_window["avg_rate"]

    # Calculate savings of waiting for best future window vs chartering now
    savings_vs_now_pct = ((curr_rate - best_rate) / curr_rate * 100.0) if curr_rate > 0 else 0.0

    # Calculate savings of best future window vs full horizon average
    best_vs_horizon_pct = ((horizon_avg - best_rate) / horizon_avg * 100.0) if horizon_avg > 0 else 0.0

    # Confidence descriptors
    curr_conf = _confidence_descriptor(current_window["volatility"])
    best_conf = _confidence_descriptor(best_future_window["volatility"])

    # Decision Logic:
    # A. If current window is already the minimum, or within 5% of the minimum:
    if savings_vs_now_pct <= 5.0 or best_future_window["index"] == 0:
        verdict = "CHARTER NOW"
        recommended = current_window
        pct_below = ((horizon_avg - curr_rate) / horizon_avg * 100.0) if horizon_avg > 0 else 0.0

        if savings_vs_now_pct <= 0:
            comparison_phrase = "represent the lowest projected cost across the horizon"
        else:
            comparison_phrase = f"are within {savings_vs_now_pct:.1f}% of the projected horizon floor"

        reasoning = (
            f"Nearest-term rates (averaging {curr_rate:,.0f} BDI through {current_window['end']}) "
            f"{comparison_phrase}. Because near-term estimates carry {curr_conf} "
            f"({current_window['volatility']}% band width) and forward deferral introduces operational friction, "
            f"immediate contract execution is recommended."
        )

    # B. If future window offers savings, but confidence band is extremely wide (>75%) and savings are small (<10%):
    elif best_future_window["volatility"] > 75.0 and savings_vs_now_pct < 10.0:
        verdict = "MONITOR"
        recommended = best_future_window
        pct_below = best_vs_horizon_pct

        reasoning = (
            f"A potential rate softening is projected between {best_future_window['start']} and {best_future_window['end']} "
            f"(averaging {best_rate:,.0f} BDI, {best_vs_horizon_pct:.1f}% below the {n}-day average), but forward uncertainty "
            f"expands to {best_future_window['volatility']}% band width ({best_conf}). Recommend monitoring spot movements closely "
            f"before committing to delayed laycan windows."
        )

    # C. Clear future dip with meaningful savings (>5%):
    else:
        verdict = "WAIT FOR WINDOW"
        recommended = best_future_window
        pct_below = best_vs_horizon_pct

        reasoning = (
            f"Rates are forecasted to dip {best_vs_horizon_pct:.1f}% below the {n}-day average "
            f"(and {savings_vs_now_pct:.1f}% below current levels) between {best_future_window['start']} and {best_future_window['end']}, "
            f"averaging {best_rate:,.0f} BDI with {best_conf} ({best_future_window['volatility']}% band width). "
            f"Recommend delaying contract commitment until this window if operationally feasible."
        )

    return {
        "recommended_window_start": recommended["start"],
        "recommended_window_end": recommended["end"],
        "expected_avg_rate": recommended["avg_rate"],
        "expected_confidence": recommended["volatility"],
        "pct_below_horizon_avg": round(pct_below, 1),
        "verdict": verdict,
        "reasoning": reasoning,
        "current_window_avg_rate": curr_rate,
        "horizon_avg_rate": round(horizon_avg, 2),
        "savings_vs_now_pct": round(savings_vs_now_pct, 1),
    }


if __name__ == "__main__":
    import os
    import sys
    # Quick self-test with sample synthetic curves
    test_curve = [
        {"ds": f"2013-06-{i+1:02d}", "yhat": 1000 - i * 15 if i < 15 else 775 + (i - 15) * 20,
         "yhat_lower": 850 if i < 15 else 650, "yhat_upper": 1150 if i < 15 else 900}
        for i in range(30)
    ]
    res = find_optimal_entry_window(test_curve, 7)
    print("Test Result:", res)
