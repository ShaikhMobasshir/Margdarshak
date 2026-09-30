"""
Data cleaning script for Baltic Dry Index historical data.

Loads raw CSV export (2020-2026), parses dates explicitly as day-first (%d-%m-%Y),
cleans numeric Price values (strips commas/quotes), sorts chronologically (oldest first),
resamples to daily frequency with forward-fill for gaps, and saves cleaned result
to data/processed/bdi_clean.csv.
"""

import os
import sys
import shutil
import pandas as pd
import numpy as np


def clean_bdi_data(raw_path, output_path):
    """Clean raw BDI data and save to processed directory."""
    print(f"Reading raw data from: {raw_path}")
    df = pd.read_csv(raw_path)

    # Normalize column names to lowercase
    col_map = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=col_map)

    # Check date column name
    date_col = "date" if "date" in df.columns else df.columns[0]
    
    # Check price / bdi column name
    price_col = None
    for candidate in ["bdi", "price", "close", "last"]:
        if candidate in df.columns:
            price_col = candidate
            break
    if price_col is None:
        price_col = df.columns[1]

    # Explicit day-first parsing for DD-MM-YYYY format (e.g. 01-09-2026 -> 1 Sep 2026)
    try:
        df["date"] = pd.to_datetime(df[date_col], format="%d-%m-%Y")
    except Exception:
        # Fallback to dayfirst=True if some dates differ slightly
        df["date"] = pd.to_datetime(df[date_col], dayfirst=True)

    # Clean Price/BDI: strip commas and quotes, convert to numeric float
    cleaned_series = (
        df[price_col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace('"', "", regex=False)
        .str.replace("'", "", regex=False)
        .str.strip()
    )
    df["bdi"] = pd.to_numeric(cleaned_series, errors="coerce")

    # Filter only required columns
    df = df[["date", "bdi"]].dropna(subset=["date", "bdi"])

    # Sort chronologically (oldest to newest)
    df = df.sort_values("date").reset_index(drop=True)

    # Set date as index for daily resampling
    df = df.set_index("date")

    # Resample to daily frequency and forward-fill weekend/holiday gaps
    df = df.resample("D").ffill()

    # Drop any leading NaNs before first recorded date
    df = df.dropna(subset=["bdi"])

    # Reset index so date is a column
    df = df.reset_index()

    # Sanity checks
    assert (df["bdi"] > 0).all(), "ERROR: Negative or zero BDI values found after cleaning!"
    assert not df["bdi"].isna().any(), "ERROR: NaN BDI values remain after cleaning!"

    # Save to processed directory
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    return df


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Search candidates for the new raw file
    candidate_raw_paths = [
        os.path.join(project_root, "data", "raw", "Baltic_Dry_Index_Historical_Data.csv"),
        os.path.join(project_root, "data", "raw", "Baltic Dry Index Historical Data.csv"),
        os.path.join(project_root, "data", "raw", "bdi_historical.csv"),
    ]

    raw_path = None
    for p in candidate_raw_paths:
        if os.path.exists(p):
            raw_path = p
            break

    if not raw_path:
        print(f"[ERROR] Raw data not found in data/raw/")
        print("   Expected: Baltic_Dry_Index_Historical_Data.csv or Baltic Dry Index Historical Data.csv")
        sys.exit(1)

    output_path = os.path.join(project_root, "data", "processed", "bdi_clean.csv")

    # Archive existing processed file if present and not already archived
    archive_path = os.path.join(project_root, "data", "processed", "bdi_clean_1985_2013_archive.csv")
    if os.path.exists(output_path) and not os.path.exists(archive_path):
        shutil.copyfile(output_path, archive_path)
        print(f"[ARCHIVE] Saved previous dataset to {archive_path}")

    cleaned_df = clean_bdi_data(raw_path, output_path)
    print(f"\n[OK] Cleaned data saved successfully to {output_path}")
    print(f"   Total rows (daily resampled): {len(cleaned_df):,}")
    print(f"   Date range: {cleaned_df['date'].min().strftime('%d-%b-%Y')} to {cleaned_df['date'].max().strftime('%d-%b-%Y')}")
    print(f"   BDI value range: {cleaned_df['bdi'].min():,.0f} to {cleaned_df['bdi'].max():,.0f} BDI (latest: {cleaned_df['bdi'].iloc[-1]:,.0f} BDI)")
    print(f"   Columns: {list(cleaned_df.columns)}")
