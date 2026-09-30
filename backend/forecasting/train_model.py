"""
Train forecasting model on cleaned BDI data.

Tries Prophet first; falls back to SARIMAX if Prophet is unavailable.
Saves trained model as a pickle file for serving.
"""

import os
import sys
import time
import pickle
import argparse
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# Determine project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "bdi_clean.csv")
MODEL_DIR = SCRIPT_DIR  # Save models alongside the scripts

USE_PROPHET = False

# Try to import Prophet
try:
    from prophet import Prophet
    USE_PROPHET = True
    print("[OK] Prophet imported successfully.")
except ImportError:
    print("[INFO] Prophet not available. Using SARIMAX fallback.")

if not USE_PROPHET:
    from statsmodels.tsa.statespace.sarimax import SARIMAX


def train_prophet(df, col_name, model_path, mcmc=False, cps=0.1):
    """Train a Prophet model on the given column."""
    # Prophet requires columns named 'ds' and 'y'
    prophet_df = df[["date", col_name]].rename(columns={"date": "ds", col_name: "y"})
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

    kwargs = {
        "yearly_seasonality": True,
        "weekly_seasonality": True,
        "daily_seasonality": False,
        "changepoint_prior_scale": cps,
        "interval_width": 0.85
    }
    
    if mcmc:
        kwargs["mcmc_samples"] = 300
        print("   [INFO] Using full Bayesian (MCMC) posterior sampling (mcmc_samples=300). This will take longer.")

    model = Prophet(**kwargs)
    
    start_time = time.time()
    model.fit(prophet_df)
    elapsed = time.time() - start_time
    
    if mcmc:
        print(f"   [INFO] MCMC training completed in {elapsed:.2f} seconds.")

    with open(model_path, "wb") as f:
        pickle.dump({"type": "prophet", "model": model}, f)

    print(f"   [OK] Prophet model saved to {model_path}")
    return model


def train_sarimax(df, col_name, model_path):
    """Train a SARIMAX model as fallback."""
    series = df.set_index("date")[col_name].astype(float)
    series.index = pd.DatetimeIndex(series.index, freq="D")

    print(f"   Training SARIMAX on {len(series)} data points (this may take a minute)...")

    model = SARIMAX(
        series,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 0, 7),
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    results = model.fit(disp=False, maxiter=200)

    with open(model_path, "wb") as f:
        pickle.dump({
            "type": "sarimax",
            "model": results,
            "last_date": series.index[-1],
            "last_values": series.tail(30).tolist()
        }, f)

    print(f"   [OK] SARIMAX model saved to {model_path}")
    return results


def tune_prophet(df, col_name):
    """Run automated hyperparameter search for changepoint_prior_scale."""
    from prophet.diagnostics import cross_validation, performance_metrics
    import logging
    logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

    prophet_df = df[["date", col_name]].rename(columns={"date": "ds", col_name: "y"})
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

    candidates = [0.01, 0.05, 0.1, 0.5, 1.0]
    best_mape = float('inf')
    best_cps = 0.1

    print("\n   Starting hyperparameter search for changepoint_prior_scale...")
    print(f"   {'-'*25}")
    print(f"   {'CPS':<10} | {'MAPE (%)':<10}")
    print(f"   {'-'*25}")

    for cps in candidates:
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=cps,
            interval_width=0.85
        )
        model.fit(prophet_df)
        
        # We suppress the internal Prophet output to keep the table clean
        import contextlib
        with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
            df_cv = cross_validation(model, initial="365 days", period="30 days", horizon="14 days")
        
        df_p = performance_metrics(df_cv)
        mape = df_p["mape"].mean() * 100
        
        print(f"   {cps:<10} | {mape:.2f}")

        if mape < best_mape:
            best_mape = mape
            best_cps = cps

    print(f"   {'-'*25}")
    print(f"   Selected best changepoint_prior_scale = {best_cps} (MAPE = {best_mape:.2f}%)")
    return best_cps


def train(col_name="bdi", mcmc=False, tune=False):
    """Train a model on the specified column."""
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if col_name not in df.columns:
        print(f"   [SKIP] Column '{col_name}' not found in data.")
        return None

    # For datasets with long histories, train on the recent ~3 years (1095 days)
    # up to the end of the historical training data to capture the prevailing market regime
    # and avoid negative trend extrapolation from distant macro shocks
    if len(df) > 1095:
        df = df.tail(1095).reset_index(drop=True)

    # Set aside the last 30 days as a held-out test set
    train_df = df.iloc[:-30].reset_index(drop=True)

    model_path = os.path.join(MODEL_DIR, f"model_{col_name}.pkl")

    if USE_PROPHET:
        cps = 0.1
        if tune:
            cps = tune_prophet(train_df, col_name)
        return train_prophet(train_df, col_name, model_path, mcmc=mcmc, cps=cps)
    else:
        return train_sarimax(train_df, col_name, model_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train forecasting model")
    parser.add_argument("--mcmc", action="store_true", help="Enable full Bayesian (MCMC) posterior sampling (slower)")
    parser.add_argument("--tune", action="store_true", help="Run automated hyperparameter search for changepoint_prior_scale")
    args = parser.parse_args()

    print(f"Loading data from {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    print(f"   {len(df)} rows, columns: {list(df.columns)}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")

    # Always train on BDI
    print("\nTraining BDI model...")
    train("bdi", mcmc=args.mcmc, tune=args.tune)

    # Clean up stale sub-index models if columns are absent in the real composite dataset
    sub_indices = ["bci", "bpi", "bsi", "bhsi"]
    for idx in sub_indices:
        if idx in df.columns:
            print(f"\nTraining {idx.upper()} model...")
            train(idx, mcmc=args.mcmc, tune=args.tune)
        else:
            stale_pkl = os.path.join(MODEL_DIR, f"model_{idx}.pkl")
            if os.path.exists(stale_pkl):
                try:
                    os.remove(stale_pkl)
                    print(f"   [CLEANUP] Removed stale model: model_{idx}.pkl")
                except Exception:
                    pass
            print(f"   [INFO] Sub-index '{idx}' derived via documented multipliers from composite BDI.")

    print("\n[DONE] Model training complete.")
    print(f"   Engine used: {'Prophet' if USE_PROPHET else 'SARIMAX'}")
