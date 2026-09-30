"""
Currency / FX Risk Module (USD/INR).

Models currency exchange rate risk between USD-denominated ocean freight fixtures
and domestic INR landed cost payment.

Data Source:
    Frankfurter API (https://api.frankfurter.dev)
    Open-source currency exchange rate API tracking central bank reference rates.
    Zero API key or signup required, updated daily.

Design Principles:
    1. Fresh Live Data at Request Time: BDI forecasts forward mathematically from a trained
       ML model, but a rolling 30-day volatility metric for FX requires genuinely current
       data on every run to avoid snapshot staleness.
    2. Zero Authentication / Open Access: Uses the free, open Frankfurter API endpoint:
       https://api.frankfurter.dev/v1/{start_date}..{end_date}?base=USD&symbols=INR
    3. Graceful Network Degradation: Live network calls can fail (network outage, API timeout).
       On failure (10s timeout), the system catches the exception and returns a structured
       'data_unavailable' status without crashing or silently fabricating fake numbers.
       Composite risk proportionally reallocates the 20% FX weight across active criteria.
    4. Rolling 30-Day Volatility: Standard deviation of daily percentage returns:
           pct_change_t = (Rate_t - Rate_{t-1}) / Rate_{t-1} * 100
           volatility_30d = std(pct_change_{t-29...t})
    5. Documented Historical Thresholds:
       - Low (< 0.30% daily std): Calm central bank market intervention regime; minimal currency risk.
       - Moderate (0.30% - 0.60% daily std): Macro headwind / oil shock pressure; rupee
         depreciation risk of 2-5% over standard voyage transit cycle.
       - High (>= 0.60% daily std): Severe forex volatility (annualized > 10%); currency hedging
         (FEC / forward contract) recommended to protect operating margins.
"""

import os
import sys
from datetime import date, timedelta
from typing import Dict, Any, Optional
import requests
import pandas as pd
import numpy as np


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_FX_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "usd_inr_historical.csv")

# Historical volatility thresholds (std of daily % change over rolling 30-day window)
THRESHOLD_LOW_MAX = 0.30      # < 0.30%
THRESHOLD_MODERATE_MAX = 0.60 # 0.30% - 0.60% (>= 0.60% is High)

SOURCE_CITATION = (
    "Frankfurter API (live, fetched at request time from central bank reference rates; "
    "https://api.frankfurter.dev)"
)

THRESHOLDS_DOC = {
    "low": "< 0.30% daily volatility std (orderly market conditions)",
    "moderate": "0.30% - 0.60% daily volatility std (macro/oil shock pressure)",
    "high": ">= 0.60% daily volatility std (severe forex turbulence, annualized > 10%)"
}


def fetch_recent_usd_inr(days: int = 45, timeout: int = 10) -> Dict[str, Dict[str, float]]:
    """
    Fetch a rolling window of recent USD/INR rates directly from the Frankfurter API.

    Args:
        days: int, number of calendar days to look back (default 45 to ensure >= 30 trading days).
        timeout: int, network request timeout in seconds (default 10s).

    Returns:
        dict: rates mapping, e.g. {"2026-08-01": {"INR": 95.12}, ...}
    """
    end = date.today()
    start = end - timedelta(days=days)
    url = f"https://api.frankfurter.dev/v1/{start.isoformat()}..{end.isoformat()}"
    resp = requests.get(url, params={"base": "USD", "symbols": "INR"}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("rates", {})


def rates_to_dataframe(rates: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert Frankfurter rates dict into a sorted, daily-resampled DataFrame.

    Args:
        rates: dict of format {date_str: {"INR": rate_float}} or {date_str: rate_float}

    Returns:
        pd.DataFrame with 'date' and 'rate' columns.
    """
    rows = []
    for dt_str, r_val in rates.items():
        if isinstance(r_val, dict) and "INR" in r_val:
            try:
                rows.append({"date": dt_str, "rate": float(r_val["INR"])})
            except (ValueError, TypeError):
                continue
        elif isinstance(r_val, (int, float)):
            rows.append({"date": dt_str, "rate": float(r_val)})

    if not rows:
        return pd.DataFrame(columns=["date", "rate"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Resample daily to forward-fill weekends and bank holidays
    df = df.set_index("date")
    df = df.resample("D").ffill()
    df = df.dropna(subset=["rate"]).reset_index()
    return df


def clean_fx_data(csv_path: str) -> pd.DataFrame:
    """
    Load and clean USD/INR historical CSV data (backward compatibility / offline fallback).

    Args:
        csv_path: str, path to the raw CSV file.

    Returns:
        pd.DataFrame with 'date' and 'rate' columns, daily resampled, ffilled.
    """
    df = pd.read_csv(csv_path)

    # Normalize column names
    col_map = {c: str(c).strip().lower() for c in df.columns}
    df = df.rename(columns=col_map)

    # Detect date column
    date_col = None
    for cand in ["date", "ds", "trade date", "observation_date", "timestamp"]:
        if cand in df.columns:
            date_col = cand
            break
    if date_col is None:
        date_col = df.columns[0]

    # Detect rate / price column
    rate_col = None
    for cand in ["rate", "price", "usd_inr", "usdinr", "close", "last", "value"]:
        if cand in df.columns:
            rate_col = cand
            break
    if rate_col is None:
        rate_col = df.columns[1]

    # Robust date parsing
    try:
        df["date"] = pd.to_datetime(df[date_col], format="mixed", dayfirst=True)
    except TypeError:
        try:
            df["date"] = pd.to_datetime(df[date_col], dayfirst=True)
        except Exception:
            df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    except Exception:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")

    # Clean numeric rate
    cleaned_rate = (
        df[rate_col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace('"', "", regex=False)
        .str.replace("'", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.strip()
    )
    df["rate"] = pd.to_numeric(cleaned_rate, errors="coerce")

    # Filter, drop NaNs, sort chronologically
    df = df[["date", "rate"]].dropna(subset=["date", "rate"])
    df = df.sort_values("date").reset_index(drop=True)

    # Resample daily to handle weekends and bank holidays
    df = df.set_index("date")
    df = df.resample("D").ffill()
    df = df.dropna(subset=["rate"]).reset_index()

    return df


def _data_unavailable_result(reason: str = "") -> Dict[str, Any]:
    """Return structured fallback response when live data is unavailable."""
    msg_suffix = f" ({reason})" if reason else ""
    return {
        "status": "data_unavailable",
        "tier": "Low",               # Default baseline tier for compatibility
        "tier_label": "Data Unavailable",
        "score": None,
        "weight": 0.20,
        "rolling_30d_volatility_pct": None,
        "latest_rate": None,
        "latest_date": None,
        "message": (
            "USD/INR currency volatility data is currently unavailable from the live Frankfurter API"
            f"{msg_suffix}. Freight rates are conventionally priced in USD, exposing INR buyers to currency risk. "
            "Sourced live from central bank reference rates via Frankfurter API when connected. "
            "Weight is reallocated across active criteria."
        ),
        "source": SOURCE_CITATION,
        "thresholds": THRESHOLDS_DOC,
    }


def compute_fx_risk(
    csv_path: Optional[str] = None,
    rates_dict: Optional[Dict[str, Any]] = None,
    days: int = 45,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Compute USD/INR exchange rate risk over the most recent 30-day window.

    By default, fetches fresh live rates directly from Frankfurter API at request time.
    If the network request fails or times out, gracefully falls back to 'data_unavailable'
    without crashing or silently fabricating synthetic numbers.

    Args:
        csv_path: str (optional), override path to USD/INR historical CSV for offline testing.
        rates_dict: dict (optional), pre-fetched rates dictionary for testing/mocking.
        days: int, calendar days to fetch from live API (default 45).
        timeout: int, network timeout in seconds (default 10).

    Returns:
        dict: Structured risk evaluation object.
    """
    try:
        # 1. Acquire DataFrame based on provided inputs or live API
        if rates_dict is not None:
            df = rates_to_dataframe(rates_dict)
        elif csv_path is not None:
            if not os.path.exists(csv_path):
                print(
                    f"WARNING: Specified USD/INR CSV file not found at '{csv_path}'. "
                    "Skipping FX risk computation gracefully (status: data_unavailable). "
                    "Per policy, synthetic currency data will NOT be fabricated."
                )
                return _data_unavailable_result(f"Specified CSV path '{csv_path}' not found")
            df = clean_fx_data(csv_path)
        else:
            # Live Frankfurter API call
            try:
                rates = fetch_recent_usd_inr(days=days, timeout=timeout)
                if not rates:
                    print("WARNING: Frankfurter API returned empty rates. Falling back to data_unavailable.")
                    return _data_unavailable_result("API returned empty rates")
                df = rates_to_dataframe(rates)
            except Exception as net_exc:
                print(
                    f"WARNING: Frankfurter live FX API request failed: {net_exc}. "
                    "Skipping FX risk computation gracefully (status: data_unavailable). "
                    "Per policy, synthetic currency data will NOT be fabricated."
                )
                return _data_unavailable_result(f"Network error or timeout: {net_exc}")

        # 2. Check sufficient data
        if len(df) < 5:
            print("WARNING: USD/INR dataset contains fewer than 5 rows; insufficient data for volatility calculation.")
            return {
                "status": "insufficient_data",
                "tier": "Low",
                "tier_label": "Insufficient Data",
                "score": None,
                "weight": 0.20,
                "rolling_30d_volatility_pct": None,
                "latest_rate": float(df["rate"].iloc[-1]) if not df.empty else None,
                "latest_date": df["date"].iloc[-1].strftime("%Y-%m-%d") if not df.empty else None,
                "message": "USD/INR series contains insufficient history to calculate rolling 30-day volatility.",
                "source": SOURCE_CITATION,
                "thresholds": THRESHOLDS_DOC,
            }

        # 3. Daily percentage change
        df["pct_change"] = df["rate"].pct_change() * 100.0

        # Window size up to 30 days
        window_size = min(len(df.dropna(subset=["pct_change"])), 30)
        recent_changes = df["pct_change"].dropna().tail(window_size)
        rolling_std = float(recent_changes.std()) if len(recent_changes) > 1 else 0.0
        rolling_std = round(rolling_std, 3)

        latest_rate = round(float(df["rate"].iloc[-1]), 2)
        latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")

        # 4. Classify into tiers
        if rolling_std >= THRESHOLD_MODERATE_MAX:
            tier = "High"
            score = 75
            message = (
                f"Elevated USD/INR volatility ({rolling_std:.2f}% daily std over 30d; latest: ₹{latest_rate}/$ on {latest_date}). "
                f"Freight is quoted in USD but settled in INR; sharp rupee depreciation between fixture and discharge can "
                f"substantially expand effective landed cost (typically 3-6% cost variance). Recommend locking in Forward "
                f"Exchange Contracts (FEC) or currency hedging."
            )
        elif rolling_std >= THRESHOLD_LOW_MAX:
            tier = "Moderate"
            score = 50
            message = (
                f"Moderate USD/INR currency volatility ({rolling_std:.2f}% daily std over 30d; latest: ₹{latest_rate}/$ on {latest_date}). "
                f"Moderate exchange rate fluctuations observed; consider factoring a 2-3% currency fluctuation contingency into "
                f"INR landed cost estimates."
            )
        else:
            tier = "Low"
            score = 25
            message = (
                f"Stable USD/INR exchange rate ({rolling_std:.2f}% daily std over 30d; latest: ₹{latest_rate}/$ on {latest_date}). "
                f"Currency fluctuations are within calm historical bounds (<0.30% std); minimal rupee depreciation risk expected "
                f"for short-to-medium transit fixtures."
            )

        return {
            "status": "available",
            "tier": tier,
            "tier_label": f"{tier} FX Risk",
            "score": score,
            "weight": 0.20,
            "rolling_30d_volatility_pct": rolling_std,
            "latest_rate": latest_rate,
            "latest_date": latest_date,
            "message": message,
            "source": SOURCE_CITATION,
            "thresholds": THRESHOLDS_DOC,
        }

    except Exception as exc:
        print(f"ERROR: Failed to process USD/INR data: {exc}")
        return {
            "status": "error",
            "tier": "Low",
            "tier_label": "Error Processing Data",
            "score": None,
            "weight": 0.20,
            "rolling_30d_volatility_pct": None,
            "latest_rate": None,
            "latest_date": None,
            "message": f"Error parsing USD/INR series: {exc}. Gracefully excluded from composite risk.",
            "source": SOURCE_CITATION,
            "thresholds": THRESHOLDS_DOC,
        }


if __name__ == "__main__":
    print("Testing live Frankfurter API call:")
    res_live = compute_fx_risk()
    print(f"  Status: {res_live['status']}")
    print(f"  Tier: {res_live['tier']}")
    print(f"  Score: {res_live['score']}")
    print(f"  Latest Rate: INR {res_live['latest_rate']}/$ ({res_live['latest_date']})")
    print(f"  30d Volatility: {res_live['rolling_30d_volatility_pct']}% std")
    print(f"  Source: {res_live['source']}")
