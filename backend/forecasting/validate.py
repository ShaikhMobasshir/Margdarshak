"""
Validate the trained forecasting models.

For Prophet: uses built-in cross_validation and performance_metrics.
For SARIMAX: performs a manual train/test split validation.
Reports MAPE (Mean Absolute Percentage Error) for each model.
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "bdi_clean.csv")


def validate_prophet(model_data, col_name="bdi"):
    """Validate Prophet model using built-in cross-validation and held-out test set."""
    from prophet.diagnostics import cross_validation, performance_metrics
    import contextlib

    model = model_data["model"]

    print(f"   Running Prophet cross-validation...")
    print(f"   initial='365 days', period='30 days', horizon='14 days'")

    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
        df_cv = cross_validation(
            model,
            initial="365 days",
            period="30 days",
            horizon="14 days"
        )

    df_p = performance_metrics(df_cv)

    cv_mape = df_p["mape"].mean() * 100  # Convert to percentage
    print(f"   Cross-validation MAPE: {cv_mape:.2f}%")
    print(f"   MAE:  {df_p['mae'].mean():.2f}")
    print(f"   RMSE: {df_p['rmse'].mean():.2f}")
    print(f"   Cross-validation folds: {len(df_cv['cutoff'].unique())}")
    
    # Evaluate on held-out test set
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    
    last_train_date = model.history['ds'].max()
    holdout = df[df["date"] > last_train_date].copy()
    
    if len(holdout) > 0:
        print(f"   Evaluating on held-out test set ({len(holdout)} days)...")
        future = pd.DataFrame({"ds": holdout["date"]})
        forecast = model.predict(future)
        actual = holdout[col_name].values
        predicted = forecast["yhat"].values
        
        # Calculate MAPE handling zero actuals gracefully
        with np.errstate(divide='ignore', invalid='ignore'):
            mape_array = np.abs((actual - predicted) / actual)
            # if actual is 0, replace with 0 or exclude
            mape_array[~np.isfinite(mape_array)] = 0
            holdout_mape = np.mean(mape_array) * 100
            
        print(f"   Held-out Test MAPE: {holdout_mape:.2f}%")
        return cv_mape, holdout_mape
    else:
        print("   [INFO] No held-out test data found.")
        return cv_mape, None


def validate_sarimax(model_data, col_name="bdi"):
    """Validate SARIMAX model using manual train/test split."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if col_name not in df.columns:
        print(f"   [SKIP] Column '{col_name}' not found in data.")
        return None

    series = df.set_index("date")[col_name].astype(float)
    series.index = pd.DatetimeIndex(series.index, freq="D")

    # Use last 90 days as test set, rest as train
    train_size = len(series) - 90
    train = series.iloc[:train_size]
    test = series.iloc[train_size:]

    print(f"   Running SARIMAX validation (train/test split)...")
    print(f"   Train: {len(train)} days, Test: {len(test)} days")

    # Retrain on training portion only
    model = SARIMAX(
        train,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 0, 7),
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    results = model.fit(disp=False, maxiter=200)

    # Forecast the test period
    forecast = results.forecast(steps=len(test))

    # Calculate MAPE
    actual = test.values
    predicted = forecast.values
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100

    # Calculate MAE and RMSE
    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))

    print(f"   MAPE: {mape:.2f}%")
    print(f"   MAE:  {mae:.2f}")
    print(f"   RMSE: {rmse:.2f}")
    print(f"   Test period: {test.index[0].date()} to {test.index[-1].date()}")

    return mape


def validate_model(col_name):
    """Validate a single model by column name."""
    model_path = os.path.join(SCRIPT_DIR, f"model_{col_name}.pkl")

    if not os.path.exists(model_path):
        print(f"   [SKIP] Model file not found: model_{col_name}.pkl")
        return None

    with open(model_path, "rb") as f:
        model_data = pickle.load(f)

    model_type = model_data["type"]

    if model_type == "prophet":
        return validate_prophet(model_data, col_name)
    elif model_type == "sarimax":
        return validate_sarimax(model_data, col_name)
    else:
        print(f"   [ERROR] Unknown model type: {model_type}")
        return None


if __name__ == "__main__":
    # Validate all models: BDI composite + 4 sub-indices
    all_indices = ["bdi", "bci", "bpi", "bsi", "bhsi"]
    results = {}

    for idx in all_indices:
        model_path = os.path.join(SCRIPT_DIR, f"model_{idx}.pkl")
        if os.path.exists(model_path):
            print(f"\n{'='*50}")
            print(f"Validating {idx.upper()} model...")
            print(f"{'='*50}")
            mape = validate_model(idx)
            if mape is not None:
                results[idx] = mape
        else:
            print(f"\n[INFO] No model found for {idx.upper()} -- skipping.")

    # Summary table
    print(f"\n{'='*65}")
    print("VALIDATION SUMMARY")
    print(f"{'='*65}")
    print(f"  {'Index':>6s}  {'CV MAPE':>10s}  {'Test MAPE':>10s}")
    print(f"  {'-'*6}  {'-'*10}  {'-'*10}")
    for idx, res in results.items():
        if isinstance(res, tuple):
            cv_mape, test_mape = res
            test_str = f"{test_mape:>9.2f}%" if test_mape is not None else "       N/A"
            print(f"  {idx.upper():>6s}  {cv_mape:>9.2f}%  {test_str}")
        else:
            print(f"  {idx.upper():>6s}  {res:>9.2f}%  {'       N/A'}")

    print(f"\n[DONE] Validated {len(results)} model(s).")
