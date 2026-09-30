"""
Generate synthetic BDI (Baltic Dry Index) historical data with sub-indices.

WARNING: THIS GENERATES SYNTHETIC DATA — NOT REAL MARKET DATA.
Replace data/raw/bdi_historical.csv with a real export from
balticdryindex.com or macromicro.me before using this for anything
beyond a demo.

The synthetic data mimics plausible BDI behavior:
- ~3 years of daily data
- Slow trend component
- Weekly and yearly seasonality
- Occasional volatility spikes
- Values in the historically plausible 500–5000 range

Sub-indices have genuinely different volatility and baseline levels:
- BCI (Capesize): highest volatility, highest baseline, largest swings
- BPI (Panamax): moderate-high volatility
- BSI (Supramax): moderate volatility
- BHSI (Handysize): calmest, lowest baseline

BDI composite formula (since 1 March 2018, Baltic Exchange):
  BDI = (0.40 * BCI + 0.30 * BPI + 0.30 * BSI) * 0.1
Note: BHSI is NOT included in the official BDI composite since the
2018 re-weighting. BHSI is still tracked as its own index for
Handysize pricing, it just doesn't feed into the composite BDI.
"""

import numpy as np
import pandas as pd
import os
import sys


def _make_sub_index(t, n, base_trend, yearly, weekly, rng,
                     baseline_offset, vol_mult, noise_std, spike_std,
                     walk_std, clamp_lo, clamp_hi):
    """Generate one sub-index series with its own distinct noise profile."""
    # Offset the shared trend
    trend = base_trend + baseline_offset

    # Scale seasonality by the volatility multiplier
    seas = (yearly + weekly) * vol_mult

    # Independent random walk (each sub-index gets its own)
    walk = np.cumsum(rng.normal(0, walk_std, n))
    walk = walk - np.linspace(walk[0], walk[-1], n)  # detrend

    # Independent daily noise
    noise = rng.normal(0, noise_std, n)

    # Independent spike events
    spike_mask = rng.random(n) < 0.05
    spikes = np.zeros(n)
    if spike_mask.sum() > 0:
        spikes[spike_mask] = rng.normal(0, spike_std, spike_mask.sum())

    series = trend + seas + walk + noise + spikes
    series = np.clip(series, clamp_lo, clamp_hi)
    return np.round(series).astype(int)


def generate_synthetic_bdi():
    np.random.seed(42)

    # ~3 years of daily data ending near "today"
    end_date = pd.Timestamp("2026-08-31")
    start_date = end_date - pd.DateOffset(years=3)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n = len(dates)

    t = np.arange(n)

    # Shared underlying trend shape (all indices follow similar macro cycles)
    base_trend = 2000 + 800 * np.sin(2 * np.pi * t / (365 * 2))
    yearly     = 300 * np.sin(2 * np.pi * (t + 90) / 365)
    weekly     = 50  * np.sin(2 * np.pi * t / 7)

    # ---- BCI (Capesize) — highest volatility, highest baseline ----
    rng_bci = np.random.RandomState(101)
    bci = _make_sub_index(
        t, n, base_trend, yearly, weekly, rng_bci,
        baseline_offset=800, vol_mult=1.6,
        noise_std=90, spike_std=600, walk_std=30,
        clamp_lo=200, clamp_hi=12000,
    )

    # ---- BPI (Panamax) — moderate-high volatility ----
    rng_bpi = np.random.RandomState(202)
    bpi = _make_sub_index(
        t, n, base_trend, yearly, weekly, rng_bpi,
        baseline_offset=200, vol_mult=1.2,
        noise_std=55, spike_std=400, walk_std=20,
        clamp_lo=300, clamp_hi=8000,
    )

    # ---- BSI (Supramax) — moderate volatility ----
    rng_bsi = np.random.RandomState(303)
    bsi = _make_sub_index(
        t, n, base_trend, yearly, weekly, rng_bsi,
        baseline_offset=-100, vol_mult=0.9,
        noise_std=35, spike_std=250, walk_std=12,
        clamp_lo=300, clamp_hi=5000,
    )

    # ---- BHSI (Handysize) — lowest volatility, lowest baseline ----
    # Note: BHSI is NOT part of the official BDI composite since March 2018,
    # but is still tracked as a separate index for Handysize vessel pricing.
    rng_bhsi = np.random.RandomState(404)
    bhsi = _make_sub_index(
        t, n, base_trend, yearly, weekly, rng_bhsi,
        baseline_offset=-500, vol_mult=0.6,
        noise_std=20, spike_std=150, walk_std=8,
        clamp_lo=200, clamp_hi=4000,
    )

    # ---- Composite BDI ----
    # Official Baltic Exchange formula since 1 March 2018:
    #   BDI = (0.40 * BCI + 0.30 * BPI + 0.30 * BSI) * 0.1
    # BHSI is deliberately excluded from this calculation per the 2018
    # re-weighting — research showed its contribution was statistically
    # negligible to the composite.
    bdi = np.round((0.40 * bci + 0.30 * bpi + 0.30 * bsi) * 0.1).astype(int)
    # Clamp composite to plausible range
    bdi = np.clip(bdi, 100, 6000)

    df = pd.DataFrame({
        "date": dates,
        "bdi": bdi,
        "bci": bci,
        "bpi": bpi,
        "bsi": bsi,
        "bhsi": bhsi,
    })

    return df

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    raw_path = os.path.join(project_root, "data", "raw", "bdi_historical.csv")

    # Always regenerate when run directly (to pick up sub-index changes)
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    df = generate_synthetic_bdi()
    df.to_csv(raw_path, index=False)
    print(f"[WARNING] SYNTHETIC BDI data generated: {len(df)} rows, {df['date'].min()} to {df['date'].max()}")
    print(f"   Saved to: {raw_path}")
    print(f"   Columns: {list(df.columns)}")
    print(f"\n   BDI composite formula: BDI = (0.40*BCI + 0.30*BPI + 0.30*BSI) * 0.1")
    print(f"   (BHSI excluded from composite per Baltic Exchange 2018 re-weighting)\n")
    for col in ["bdi", "bci", "bpi", "bsi", "bhsi"]:
        print(f"   {col.upper():5s} range: {df[col].min():>6} - {df[col].max():<6}  mean: {df[col].mean():>7.0f}  std: {df[col].std():>6.0f}")

    # Print last 5 rows side by side to visually confirm different series
    print(f"\n   === Last 5 rows (side-by-side comparison) ===")
    print(f"   {'Date':>12s}  {'BDI':>6s}  {'BCI':>6s}  {'BPI':>6s}  {'BSI':>6s}  {'BHSI':>6s}")
    print(f"   {'-'*12}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}")
    for _, row in df.tail(5).iterrows():
        print(f"   {str(row['date'])[:10]:>12s}  {row['bdi']:6d}  {row['bci']:6d}  {row['bpi']:6d}  {row['bsi']:6d}  {row['bhsi']:6d}")

    print("\n   Replace with real data from balticdryindex.com or macromicro.me before production use.")
