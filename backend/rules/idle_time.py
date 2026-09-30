"""
Idle time / contracting strategy warnings module.

Analyzes vessel utilization and forecast trends to recommend
contracting strategies.
"""


def check_idle_time_risk(recommended_vessel_spec, cargo_qty_tonnes, forecast_data):
    """
    Check for idle-time risk and recommend contracting strategies.

    Flags:
    1. Under-utilization: if cargo / dwt_max < 80%, suggests a smaller vessel
       or splitting cargo.
    2. Declining market: if the average forecast in the first half of the horizon
       is more than 5% higher than the second half, recommends a multiple-voyage
       contract instead of repeated spot fixtures.

    Args:
        recommended_vessel_spec: Dict with vessel specs (must have 'dwt_max')
        cargo_qty_tonnes: Amount of cargo in tonnes
        forecast_data: List of dicts with keys: ds, yhat, yhat_lower, yhat_upper

    Returns:
        List of idle-time warning dicts with: type, message
    """
    flags = []

    # Check 1: Under-utilization
    dwt_max = recommended_vessel_spec["dwt_max"]
    utilization = cargo_qty_tonnes / dwt_max

    if utilization < 0.80:
        flags.append({
            "type": "under_utilization",
            "utilization_pct": round(utilization * 100, 1),
            "message": (
                f"Vessel capacity under-utilized at {utilization:.0%} "
                f"({cargo_qty_tonnes:,.0f}t cargo vs {dwt_max:,}t max capacity). "
                f"Consider a smaller vessel class or splitting cargo across voyages."
            ),
        })

    # Check 2: Declining market trend
    if len(forecast_data) >= 2:
        mid = len(forecast_data) // 2
        first_half = forecast_data[:mid]
        second_half = forecast_data[mid:]

        avg_first = sum(p["yhat"] for p in first_half) / len(first_half)
        avg_second = sum(p["yhat"] for p in second_half) / len(second_half)

        if avg_first > 0:
            decline_pct = (avg_first - avg_second) / avg_first * 100

            if decline_pct > 5:
                flags.append({
                    "type": "declining_market",
                    "decline_pct": round(decline_pct, 2),
                    "message": (
                        f"Market rates are trending down ({decline_pct:.1f}% decline "
                        f"from first to second half of forecast horizon). "
                        f"Consider a multiple-voyage contract (COA) instead of "
                        f"repeated spot fixtures to lock in current rates."
                    ),
                })
            elif decline_pct < -5:
                # Market is rising — opposite advice
                flags.append({
                    "type": "rising_market",
                    "rise_pct": round(abs(decline_pct), 2),
                    "message": (
                        f"Market rates are trending up ({abs(decline_pct):.1f}% increase "
                        f"from first to second half of forecast horizon). "
                        f"Spot fixtures may offer better rates than locking in a "
                        f"long-term contract now."
                    ),
                })

    return flags


if __name__ == "__main__":
    # Quick test
    test_vessel = {"dwt_max": 200000}

    # Test under-utilization
    flags = check_idle_time_risk(test_vessel, 100000, [
        {"ds": "2026-09-01", "yhat": 2000, "yhat_lower": 1800, "yhat_upper": 2200},
        {"ds": "2026-09-02", "yhat": 1800, "yhat_lower": 1600, "yhat_upper": 2000},
    ])
    print("Under-utilization test:")
    for f in flags:
        print(f"   [{f['type']}] {f['message']}")

    # Test declining market
    declining_forecast = [
        {"ds": f"2026-09-{i+1:02d}", "yhat": 2000 - i * 20, "yhat_lower": 1800, "yhat_upper": 2200}
        for i in range(90)
    ]
    flags = check_idle_time_risk({"dwt_max": 100000}, 95000, declining_forecast)
    print("\nDeclining market test:")
    for f in flags:
        print(f"   [{f['type']}] {f['message']}")
