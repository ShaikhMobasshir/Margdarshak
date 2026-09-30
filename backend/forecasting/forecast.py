"""
Forecast module: loads trained model and generates future predictions.

Works with either Prophet or SARIMAX models.
"""

import os
import pickle
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = SCRIPT_DIR


# Documented vessel-class freight rate multipliers relative to composite BDI.
# Based on standard dry bulk charter market relationships:
# Capesize (BCI): 1.25x (higher rate operating leverage and $/tonne proxy on heavy ore/coal voyages)
# Panamax (BPI): 1.05x (benchmark mid-size bulk carrier, closely tracking composite index)
# Supramax (BSI): 0.95x (geared bulkers with handy self-discharge flexibility)
# Handysize (BHSI): 0.85x (smaller coastal parcel trades)
VESSEL_CLASS_MULTIPLIERS = {
    "capesize": 1.25,
    "bci": 1.25,
    "panamax": 1.05,
    "bpi": 1.05,
    "supramax": 0.95,
    "bsi": 0.95,
    "handysize": 0.85,
    "bhsi": 0.85,
}


def get_forecast(vessel_class="bdi", horizon_days=90):
    """
    Load the trained model and generate forecast for the specified horizon.

    Args:
        vessel_class: Which index to forecast ("bdi", "bci", "bpi", "bsi", "bhsi",
                      or vessel class name). Maps to model_<vessel_class>.pkl or
                      derives from composite BDI using documented empirical multipliers.
        horizon_days: Number of days to forecast into the future.

    Returns:
        List of dicts: [{ds, yhat, yhat_lower, yhat_upper}, ...]
    """
    vessel_key = vessel_class.lower()
    model_path = os.path.join(MODEL_DIR, f"model_{vessel_key}.pkl")

    if not os.path.exists(model_path):
        if vessel_key in VESSEL_CLASS_MULTIPLIERS and vessel_key != "bdi":
            mult = VESSEL_CLASS_MULTIPLIERS[vessel_key]
            bdi_forecast = get_forecast("bdi", horizon_days)
            return [
                {
                    "ds": p["ds"],
                    "yhat": max(round(p["yhat"] * mult, 2), 0.0),
                    "yhat_lower": max(round(p["yhat_lower"] * mult, 2), 0.0),
                    "yhat_upper": max(round(p["yhat_upper"] * mult, 2), 0.0),
                }
                for p in bdi_forecast
            ]
        raise FileNotFoundError(
            f"Model not found at {model_path}. Run train_model.py first."
        )

    with open(model_path, "rb") as f:
        model_data = pickle.load(f)

    model_type = model_data["type"]

    if model_type == "prophet":
        return _forecast_prophet(model_data["model"], horizon_days)
    elif model_type == "sarimax":
        return _forecast_sarimax(model_data, horizon_days)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def _forecast_prophet(model, horizon_days):
    """Generate forecast using Prophet model."""
    future = model.make_future_dataframe(periods=horizon_days)
    forecast = model.predict(future)

    # Return only future dates (beyond training data)
    future_forecast = forecast.tail(horizon_days)

    results = []
    for _, row in future_forecast.iterrows():
        yhat = max(round(float(row["yhat"]), 2), 0)
        yhat_lower = max(round(float(row["yhat_lower"]), 2), 0)
        yhat_upper = max(round(float(row["yhat_upper"]), 2), 0)
        results.append({
            "ds": row["ds"].strftime("%Y-%m-%d"),
            "yhat": yhat,
            "yhat_lower": yhat_lower,
            "yhat_upper": yhat_upper,
        })

    return results


def _forecast_sarimax(model_data, horizon_days):
    """Generate forecast using SARIMAX model."""
    model = model_data["model"]
    last_date = model_data["last_date"]

    # Generate forecast
    forecast = model.get_forecast(steps=horizon_days)
    predicted = forecast.predicted_mean
    conf_int = forecast.conf_int(alpha=0.15)  # 85% interval to match Prophet's interval_width=0.85

    # Build future dates
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D"
    )

    results = []
    for i in range(horizon_days):
        yhat = float(predicted.iloc[i])
        # Ensure non-negative values (BDI can't be negative)
        yhat = max(yhat, 0)
        yhat_lower = max(float(conf_int.iloc[i, 0]), 0)
        yhat_upper = max(float(conf_int.iloc[i, 1]), 0)

        results.append({
            "ds": future_dates[i].strftime("%Y-%m-%d"),
            "yhat": round(yhat, 2),
            "yhat_lower": round(yhat_lower, 2),
            "yhat_upper": round(yhat_upper, 2),
        })

    return results


if __name__ == "__main__":
    # Quick test: get forecast and print first 5 results
    print("Testing get_forecast()...")
    try:
        results = get_forecast("bdi", 90)
        print(f"\nForecast generated: {len(results)} days")
        print("\nFirst 5 forecast points:")
        for r in results[:5]:
            print(f"   {r['ds']}: yhat={r['yhat']}, lower={r['yhat_lower']}, upper={r['yhat_upper']}")

        # Sanity checks
        all_numeric = all(
            isinstance(r["yhat"], (int, float)) and
            not np.isnan(r["yhat"])
            for r in results
        )
        all_positive = all(r["yhat"] > 0 for r in results)
        all_different = len(set(r["yhat"] for r in results)) > 1

        print(f"\nSanity checks:")
        print(f"   All numeric (no NaN): {all_numeric}")
        print(f"   All positive: {all_positive}")
        print(f"   Values vary (not all identical): {all_different}")

        if all_numeric and all_positive and all_different:
            print("\n[OK] Forecast module working correctly.")
        else:
            print("\n[WARNING] Some sanity checks failed -- review output.")
    except Exception as e:
        print(f"[ERROR] {e}")
