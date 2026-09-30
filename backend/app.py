"""
FastAPI backend for the Freight Chartering Decision Support System.

Orchestrates all modules: forecasting, vessel recommendation,
risk flags, and idle-time analysis.

Origin ports (overseas loading ports) and destination ports (Indian East
Coast discharge ports) are served from separate reference files.
"""

import os
import sys
import json

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path so modules can be imported
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from backend.forecasting.forecast import get_forecast
from backend.vessel_recommender.recommend import recommend_vessel, load_reference_data, load_routes_data
from backend.rules.risk_flags import compute_risk_flags
from backend.rules.seasonal_risk import compute_seasonal_risk
from backend.rules.fx_risk import compute_fx_risk
from backend.rules.composite_risk import compute_composite_risk, evaluate_idle_time_risk
from backend.rules.idle_time import check_idle_time_risk
from backend.rules.market_timing import find_optimal_entry_window

# Check if using synthetic data
DATA_RAW_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "bdi_historical.csv")
USING_SYNTHETIC = True  # Will be updated at startup

app = FastAPI(
    title="Freight Chartering Decision Support System",
    description="SIH26006 - Decision support dashboard for international bulk cargo shipping",
    version="1.1.0",
)

# CORS middleware — must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Print data source status on startup."""
    global USING_SYNTHETIC
    try:
        import pandas as pd
        candidate_paths = [
            os.path.join(PROJECT_ROOT, "data", "raw", "Baltic_Dry_Index_Historical_Data.csv"),
            os.path.join(PROJECT_ROOT, "data", "raw", "Baltic Dry Index Historical Data.csv"),
            os.path.join(PROJECT_ROOT, "data", "processed", "bdi_clean.csv"),
        ]
        found = any(os.path.exists(cp) for cp in candidate_paths)
        if found:
            USING_SYNTHETIC = False
            print("=" * 70)
            print("INFO: Using REAL Baltic Dry Index market data (2020-2026)")
            print("=" * 70)
        else:
            USING_SYNTHETIC = True
    except Exception:
        USING_SYNTHETIC = False


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "daersk-freight-api"}


@app.get("/api/ports")
async def get_ports():
    """Return destination ports (Indian East Coast) for the frontend dropdown."""
    _, _, dest_ports = load_reference_data()
    return dest_ports


@app.get("/api/origin-ports")
async def get_origin_ports():
    """Return origin ports (overseas loading ports) for the frontend dropdown."""
    _, origin_ports, _ = load_reference_data()
    return origin_ports


@app.get("/api/routes")
async def get_routes():
    """Return precomputed mathematical route distances and voyage metrics."""
    return load_routes_data()


@app.get("/api/recommend")
async def recommend(
    cargo_qty: float = Query(..., description="Cargo quantity in tonnes", gt=0),
    origin: str = Query(..., description="Origin port name (overseas loading port)"),
    destination: str = Query(..., description="Destination port name (Indian East Coast)"),
    horizon_days: int = Query(90, description="Forecast horizon in days", ge=7, le=365),
):
    """
    Main recommendation endpoint.

    Orchestrates: forecast -> vessel recommendation -> risk flags -> idle-time flags.

    Origin port must be an overseas loading port (from origin_ports.json).
    Destination port must be an Indian East Coast port (from ports.json).

    Returns combined JSON with keys:
    - forecast: list of {ds, yhat, yhat_lower, yhat_upper}
    - vessel_recommendations: list of vessel class assessments
    - risk_flags: list of high-volatility warnings
    - idle_time_flags: list of contracting strategy recommendations
    - metadata: data source info, route metrics, warnings, and disclosures
    """
    # Load reference data
    _, origin_ports, dest_ports = load_reference_data()

    # Validate origin port (overseas)
    if origin not in origin_ports:
        raise HTTPException(
            status_code=400,
            detail=f"Origin port '{origin}' not found. Available overseas ports: {list(origin_ports.keys())}"
        )
    # Validate destination port (Indian East Coast)
    if destination not in dest_ports:
        raise HTTPException(
            status_code=400,
            detail=f"Destination port '{destination}' not found. Available Indian ports: {list(dest_ports.keys())}"
        )

    # Step 1: Get composite BDI forecast (used for the chart and as fallback)
    try:
        forecast_data = get_forecast("bdi", horizon_days)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Forecasting model not found. Run train_model.py first."
        )

    # Step 2: Build per-vessel-class rate lookup
    # Each vessel class is priced using its own sub-index forecast,
    # not the single composite BDI rate.
    # Mapping: Capesize->BCI, Panamax->BPI, Supramax->BSI, Handysize->BHSI
    sub_index_map = {
        "capesize":  "bci",
        "panamax":   "bpi",
        "supramax":  "bsi",
        "handysize": "bhsi",
    }

    avg_bdi = sum(p["yhat"] for p in forecast_data) / len(forecast_data)
    bdi_rate = avg_bdi / 100  # $/tonne proxy from composite BDI

    rate_lookup = {"bdi": round(bdi_rate, 2)}
    sub_index_rates = {}  # For metadata reporting

    for vessel_class, index_name in sub_index_map.items():
        try:
            sub_forecast = get_forecast(index_name, horizon_days)
            avg_sub = sum(p["yhat"] for p in sub_forecast) / len(sub_forecast)
            rate = avg_sub / 100  # $/tonne proxy
            rate_lookup[vessel_class] = round(rate, 2)
            sub_index_rates[index_name.upper()] = round(avg_sub, 2)
        except FileNotFoundError:
            # Sub-index model not trained — fall back to composite BDI
            rate_lookup[vessel_class] = bdi_rate
            sub_index_rates[index_name.upper()] = None

    # Step 3: Vessel recommendation (with per-class rates & voyage economics)
    vessel_recommendations = recommend_vessel(
        cargo_qty, origin, destination, rate_lookup
    )

    # Step 4: Idle-time flags (for the top feasible vessel, if any)
    idle_time_flags = []
    top_spec = None
    feasible_vessels = [v for v in vessel_recommendations if v["feasible"]]

    if feasible_vessels:
        top_vessel = feasible_vessels[0]
        # Load vessel specs for idle time check
        with open(os.path.join(PROJECT_ROOT, "data", "reference", "vessel_specs.json")) as f:
            all_specs = json.load(f)
        top_spec = all_specs.get(top_vessel["vessel_class"])
        if top_spec:
            idle_time_flags = check_idle_time_risk(top_spec, cargo_qty, forecast_data)

    # Step 5: Expanded Multi-Criteria Risk Assessment & Composite Score
    # Criterion 1: Market Rate Volatility (40% nominal weight)
    market_risk = compute_risk_flags(forecast_data)

    # Criterion 2: Seasonal / Cyclone Risk (30% nominal weight)
    forecast_start_date = forecast_data[0]["ds"] if forecast_data else None
    seasonal_risk = compute_seasonal_risk(destination, forecast_start_date, horizon_days)

    # Criterion 3: Currency / FX Risk (20% nominal weight)
    fx_risk = compute_fx_risk()

    # Criterion 4: Fleet Utilization & Idle-Time Risk (10% nominal weight)
    idle_risk = evaluate_idle_time_risk(idle_time_flags, cargo_qty, top_spec)

    # Synthesize all 4 criteria into Weighted Composite Risk
    composite_risk = compute_composite_risk(market_risk, seasonal_risk, fx_risk, idle_risk)

    # Build comprehensive risk_analysis object preserving all market-volatility fields
    # for strict backward compatibility while supplying the new criteria & composite score
    risk_analysis = {
        # Preserved market-volatility fields
        "overall_verdict": composite_risk["composite_tier"],
        "market_verdict": market_risk["overall_verdict"],
        "pct_days_flagged": market_risk["pct_days_flagged"],
        "peak_volatility": market_risk["peak_volatility"],
        "first_moderate_date": market_risk["first_moderate_date"],
        "volatility_trend": market_risk["volatility_trend"],
        "volatility_trend_slope": market_risk["volatility_trend_slope"],
        "recommendation": composite_risk["recommendation"],
        "market_recommendation": market_risk["recommendation"],
        "daily_volatility": market_risk["daily_volatility"],
        "daily_flags": market_risk["daily_flags"],

        # New Composite Risk Score & Criteria Breakdown
        "composite_score": composite_risk["composite_score"],
        "composite_tier": composite_risk["composite_tier"],
        "headline_verdict": composite_risk["headline_verdict"],
        "nominal_weights": composite_risk["nominal_weights"],
        "effective_weights": composite_risk["effective_weights"],
        "weight_reallocated": composite_risk["weight_reallocated"],
        "disclosure": composite_risk["disclosure"],
        "criteria": composite_risk["criteria"],

        # Dedicated criteria sub-objects
        "market_risk": market_risk,
        "seasonal_risk": seasonal_risk,
        "fx_risk": fx_risk,
        "idle_risk": idle_risk,
    }

    first_vessel = vessel_recommendations[0] if vessel_recommendations else {}

    # Build metadata
    metadata = {
        "data_source": "synthetic" if USING_SYNTHETIC else "real",
        "forecast_engine": "Prophet",
        "horizon_days": horizon_days,
        "avg_bdi_forecast": round(avg_bdi, 2),
        "rate_lookup": rate_lookup,
        "sub_index_averages": sub_index_rates,
        "route_type": "international",
        "origin_country": origin_ports[origin].get("country", "Unknown"),
        "route_distance_nm": first_vessel.get("distance_nm"),
        "route_adjusted_distance_nm": first_vessel.get("adjusted_distance_nm"),
        "route_adjustment_factor": first_vessel.get("adjustment_factor", 1.10),
        "route_speed_knots": first_vessel.get("speed_knots", 13.0),
        "route_sea_days": first_vessel.get("sea_days"),
        "berth_days": first_vessel.get("berth_days"),
        "congestion_days": first_vessel.get("congestion_days"),
        "total_voyage_days": first_vessel.get("total_voyage_days"),
        "destination_max_vessel_dwt": dest_ports[destination].get("max_vessel_dwt"),
        "destination_dwt_verified": dest_ports[destination].get("dwt_verified", True),
        "destination_draft_verified": dest_ports[destination].get("draft_verified", True),
        "destination_dwt_source": dest_ports[destination].get("dwt_source"),
        "disclosure": (
            "Max vessel DWT capacity is officially verified for all 6 Indian destination ports. "
            "Beam limits and cargo handling rates are illustrative estimates, not sourced from official port authority data "
            "(this level of detail typically requires port pilot handbooks not publicly accessible). Draft/LOA figures for verified "
            "ports and route distances are independently sourced/calculated and carry higher confidence than beam/handling-rate figures."
        ),
        "congestion_disclosure": "Port congestion estimates (days) are demonstration figures for modeling turnaround time, not measured real-time telemetry."
    }

    # Add port verification warnings and nuanced disclosures
    port_warnings = []
    if not origin_ports[origin].get("verified", True):
        port_warnings.append(
            f"Port draft/LOA data for {origin} is illustrative and pending verification. "
            f"({origin_ports[origin].get('notes', '')})"
        )

    # Destination-specific disclosures
    if destination == "Paradip":
        port_warnings.append(
            "Paradip Port capacity disclosure: Max vessel size ~155,000 DWT Capesize is officially verified "
            "(Paradip Port infrastructure page); berth draft is ~16-16.5m. Disclosed operational tension: "
            "Official max_vessel_dwt (155,000 DWT, Capesize-range) implies deeper effective access than cited berth "
            "draft alone would suggest (Capesize typically requires ~18m draft), reflecting additional channel/anchorage "
            "arrangements not captured by a single berth-draft figure."
        )
    elif destination == "Gopalpur":
        port_warnings.append(
            "Gopalpur Port capacity disclosure: Max vessel size 200,000 DWT Capesize ceiling is officially verified "
            "(Gopalpur Ports berthing policy 2024). Note: The draft figure (13.5m placeholder) is provisional and "
            "flagged as needing further hydrographic precision given the verified 200,000 DWT capability."
        )
    elif destination == "Haldia":
        port_warnings.append(
            "Haldia Port capacity disclosure: Max vessel size ~75,000 DWT dry-bulk berth ceiling is officially verified "
            "(Shipping Ministry / HDC administrative report). Note: Navigable river draft (9.0m placeholder) reflects "
            "Hooghly river constraints and is flagged as needing further precision rather than guessing an unverified draft."
        )
    elif not dest_ports[destination].get("verified", True):
        port_warnings.append(
            f"Port draft/LOA data for {destination} is illustrative and pending verification."
        )

    if port_warnings:
        metadata["port_warnings"] = port_warnings

    if USING_SYNTHETIC:
        metadata["data_warning"] = (
            "Using SYNTHETIC freight data -- replace data/raw/bdi_historical.csv "
            "with a real export from balticdryindex.com or macromicro.me before "
            "using this for anything beyond a demo."
        )

    # Step 6: Optimal market entry timing (Requirement a)
    market_timing = find_optimal_entry_window(forecast_data, window_days=7)

    return {
        "forecast": forecast_data,
        "vessel_recommendations": vessel_recommendations,
        "risk_analysis": risk_analysis,
        "risk_flags": risk_analysis["daily_flags"],
        "idle_time_flags": idle_time_flags,
        "market_timing": market_timing,
        "metadata": metadata,
    }
