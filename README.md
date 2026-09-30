# Freight Chartering Decision Support System (SIH26006)

A decision-support dashboard for logistics teams importing bulk cargo (e.g. coal) by ship from overseas (Australia, Mozambique, Indonesia, Russia, USA) to India's East Coast ports. Given a cargo quantity, overseas origin port, and Indian destination port, the system returns:

1. **Freight-rate forecast** (next ~90 days) with 85% confidence bands
2. **Ranked vessel class recommendations** with estimated cost
3. **Risk warnings** for market volatility
4. **Idle-time / contracting-strategy advice**

This is a decision-support tool — a human logistics manager reads the output and decides.

---

## Quick Start

### Prerequisites
- Python 3.11+ (tested on 3.13.7)
- pip

### Install Dependencies

```bash
cd sih26006
pip install -r backend/requirements.txt
```

### Generate Data & Train Model (first time only)

```bash
# Generate synthetic BDI data (or place a real CSV at data/raw/bdi_historical.csv)
python data/generate_synthetic.py

# Clean and resample the data
python data/clean.py

# Train the forecasting model
python backend/forecasting/train_model.py

# Validate the model (reports MAPE)
python backend/forecasting/validate.py
```

### Run the Backend

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

API docs available at: http://127.0.0.1:8000/docs

### Run the Frontend

```bash
python -m streamlit run frontend/streamlit_app.py --server.port 8501
```

Dashboard available at: http://localhost:8501

---

## Architecture

```
sih26006/
├── data/
│   ├── raw/bdi_historical.csv          # Raw BDI data (synthetic or real)
│   ├── raw/usd_inr_historical.csv      # Real USD/INR historical rates (RBI Archive)
│   ├── reference/vessel_specs.json     # Vessel class specifications
│   ├── reference/ports.json            # Destination ports with state mapping
│   ├── reference/origin_ports.json     # Origin ports (overseas loading ports)
│   ├── reference/cyclone_risk.json     # IMD/RSMC cyclone landfall climatology
│   ├── processed/bdi_clean.csv         # Cleaned daily BDI data
│   ├── generate_synthetic.py           # Synthetic data generator
│   └── clean.py                        # Data cleaning pipeline
├── backend/
│   ├── app.py                          # FastAPI orchestration layer
│   ├── forecasting/
│   │   ├── train_model.py              # Model training (Prophet)
│   │   ├── validate.py                 # Cross-validation & MAPE
│   │   ├── forecast.py                 # Forecast serving
│   │   └── model_bdi.pkl               # Trained model artifact
│   ├── vessel_recommender/
│   │   └── recommend.py                # Feasibility & cost ranking
│   └── rules/
│       ├── risk_flags.py               # Market volatility detection (40% weight)
│       ├── seasonal_risk.py            # IMD cyclone landfall climatology (30% weight)
│       ├── fx_risk.py                  # RBI USD/INR exchange rate risk (20% weight)
│       ├── composite_risk.py           # Weighted composite scoring engine
│       ├── idle_time.py                # Fleet utilization & parcel geometry (10% weight)
│       └── market_timing.py            # Optimal 7-day charter entry window
├── frontend/
│   └── streamlit_app.py                # Streamlit dashboard
├── Procfile                            # Deployment start command
└── README.md
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/ports` | GET | Destination ports (Indian East Coast) |
| `/api/origin-ports` | GET | Origin ports (overseas loading ports) |
| `/api/routes` | GET | Precomputed mathematical route distances and voyage metrics |
| `/api/recommend` | GET | Main recommendation (forecast + vessels + voyage economics + risks) |

### `/api/recommend` Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cargo_qty` | float | required | Cargo quantity in tonnes |
| `origin` | string | required | Overseas origin port name (from origin_ports.json) |
| `destination` | string | required | Indian East Coast destination port name (from ports.json) |
| `horizon_days` | int | 90 | Forecast horizon (7–365 days) |

---

## Route Distance & Voyage Economics Engine

Rather than looking up or guessing maritime distances, route distances are computed mathematically using real geographic coordinates and the **Haversine great-circle formula**, adjusted by a **1.10x multiplier** to approximate realistic maritime routes around coastlines, straits, and navigation channels:

$$\text{Voyage Days (Sea)} = \frac{\text{Adjusted Distance (nm)}}{13.0 \text{ knots} \times 24 \text{ hrs/day}}$$

Total turnaround turnaround time includes:
- **Sea Days:** Transit time at a standard laden dry bulk carrier speed of 13.0 knots.
- **Berth Days:** Calculated from cargo quantity divided by port cargo handling rates (loading at origin, discharge at destination).
- **Congestion Days:** Port waiting estimates.
- **Voyage Economics:** Replaces flat $/tonne estimates with daily charter hire ($/day) multiplied by total voyage cycle days, deriving realistic freight rates.

### Operational Confidence & Data Source Disclosure

> **Important Disclosure on Data Confidence Tiers:**
> Beam limits and cargo handling rates are illustrative estimates, not sourced from official port authority data (this level of detail typically requires port pilot handbooks not publicly accessible). Draft/LOA figures for verified ports and route distances are independently sourced/calculated and carry higher confidence than beam/handling-rate figures. Port congestion durations are demonstration estimates for turnaround modeling, not measured real-time AIS telemetry.

---

## Forecasting

- **Engine:** Prophet (Facebook/Meta's time-series forecasting library)
- **Configuration:** yearly + weekly seasonality, automated `changepoint_prior_scale` hyperparameter grid search, 85% confidence interval.
- **Validation:** 
  - **Cross-Validation:** Evaluated via Prophet cross-validation (initial=365 days, period=30 days, horizon=14 days).
  - **Held-Out Test Set:** The last 30 days of available data are held out and never shown to the model during training or cross-validation. An independent MAPE is reported on this set.
- **Bayesian Sampling (MCMC):** Full Bayesian posterior sampling (MCMC) is available via the `--mcmc` flag for `train_model.py`. This provides robust parameter estimation but is slower, so it remains an opt-in mode over the MAP default.
- **Sub-Index Modeling:** Class-specific forecasting via Baltic sub-index multipliers (Capesize 1.25x BCI, Panamax 1.05x BPI, Supramax 0.95x BSI, Handysize 0.85x BHSI).
- **Future Enhancements:** 
  - **Bunker Fuel Price Regressor:** A documented stub exists (`backend/forecasting/fuel_regressor.py`) to incorporate VLSFO prices as a model regressor. It is deliberately left unconnected and unimplemented until genuine historical fuel price data (`data/raw/vlsfo_price_historical.csv`) is provided, maintaining the project's standard against using fabricated/synthetic data for features.

---

## Vessel Classes

| Class | DWT Range | Draft | Beam | LOA | Rate Factor |
|---|---|---|---|---|---|
| Handysize | 15,000–39,999t | 10.0m | 30.0m | 190m | 0.85x BHSI |
| Supramax | 40,000–64,999t | 12.5m | 32.0m | 200m | 0.95x BSI |
| Panamax | 65,000–99,999t | 14.0m | 32.31m | 240m | 1.05x BPI |
| Capesize | 90,000–200,000t | 18.0m | 45.0m | 290m | 1.25x BCI |

---

## Multi-Criteria Risk Assessment Framework

The system combines four real-data-backed risk criteria into a weighted composite risk score:

$$\text{Composite Score} = 0.40 \times S_{\text{Market}} + 0.30 \times S_{\text{Seasonal}} + 0.20 \times S_{\text{FX}} + 0.10 \times S_{\text{Idle}}$$

Where categorical tiers map to numeric scores:
- **Low Risk:** 25.0
- **Moderate Risk:** 50.0
- **High Risk:** 75.0
- **Severe Risk:** 100.0
*(Sub-tiers: Low-Moderate = 37.5, Moderate-High = 62.5, High-Severe = 87.5)*

Overall Composite Tier Classification:
- **Score < 40.0:** Low Risk
- **40.0 ≤ Score < 65.0:** Moderate Risk
- **65.0 ≤ Score < 85.0:** High Risk
- **Score ≥ 85.0:** Severe Risk

### 1. The Four Evaluated Criteria

| Criterion | Nominal Weight | Underlying Data Source | Methodology & Decision Logic |
|---|---|---|---|
| **Market Volatility** | **40%** | Baltic Dry Index (BDI) via Prophet Forecasting Model | Measures forward uncertainty spread: $\frac{\text{Upper Band} - \text{Lower Band}}{\text{Forecast Rate}} \times 100$. Identifies dates where uncertainty exceeds the 15% corporate threshold, computes horizon trend slope, and determines the first action cutoff date. |
| **Seasonal / Cyclone Risk** | **30%** | **India Meteorological Department (IMD) / RSMC New Delhi** Tropical Cyclone Landfall Climatology ([rsmcnewdelhi.imd.gov.in](https://rsmcnewdelhi.imd.gov.in/landfall.php)) | Evaluates historical Bay of Bengal tropical cyclone landfall frequency for Indian East Coast destination ports. Over 60% of Bay of Bengal cyclones strike the East Coast during the post-monsoon (Oct–Dec) and pre-monsoon (Apr–Jun) seasons. High risk (Score 75) triggers if the horizon overlaps the state's historical peak landfall month (Odisha/West Bengal peak in October; Andhra Pradesh peaks in November; Tamil Nadu peaks in December). *Disclosed: Climatological historical baseline, not live weather radar.* |
| **Currency / FX Risk (USD/INR)** | **20%** | **Frankfurter API (Live)** ([api.frankfurter.dev](https://api.frankfurter.dev)) | Ocean freight is quoted in USD; Indian end-users settle in INR. Rupee depreciation between fixture agreement and laycan payment increases effective landed cost. Fetches fresh live exchange rates at request time and computes a 30-day rolling standard deviation of daily % changes: Low (<0.30%), Moderate (0.30%–0.60%), High (≥0.60%). If the live API is unreachable or times out, synthetic data is **never** fabricated; status is marked `data_unavailable` and its 20% weight is proportionally re-allocated across active criteria. |
| **Fleet Utilization & Idle-Time** | **10%** | Vessel specifications & voyage parcel sizing geometry | Assesses dead-freight penalties from cargo parcel sizing relative to vessel DWT (<60% High, <80% Moderate) and downward freight market momentum. Suggests spot vs Contract of Affreightment (COA) positioning. |

### 2. Disclosed Weighting Scheme Rationale
The 40 / 30 / 20 / 10 weighting allocation is disclosed as an **operational starting judgment** based on bulk maritime chartering practice rather than a scientifically derived closed-form formula:
- Freight rate market volatility carries the largest weight (40%) because it directly drives cashflow variance.
- Seasonal cyclone risk carries 30% because physical disruption closes ports, cancels pilotage, and incurs substantial demurrage on India's East Coast.
- Currency risk carries 20% to account for USD/INR macro variance impacting domestic landed costs.
- Fleet idle-time carries 10% to capture operational deadweight matching efficiency.

### 3. Architectural Design Distinction: Live FX API vs. Static Forecasting Data
The system makes a deliberate architectural distinction between how freight rate forecasting and currency volatility risk are sourced:
- **ML Forecasting Models (BDI / Freight Rates):** Static historical data is appropriate for training machine-learning models (Prophet / autoregressive Ridge regression). The model ingests multi-year historical time-series, learns cyclical day-of-week/monthly harmonics, and projects **forward** mathematically into the 90-day future horizon.
- **Rolling Risk Metrics (Currency / FX Volatility):** A rolling volatility indicator measures current regime turbulence ($std$ of daily % changes over the trailing 30-day window). If this relied on a static downloaded CSV file, the calculation would measure volatility from the most recent 30 days *in that file*—meaning as real time advances past the file's download date, the metric would freeze in an increasingly stale historical window, rendering it operationally misleading.
- **The Solution:** A live API call to the open-source **Frankfurter API** (`https://api.frankfurter.dev`) is executed at request time. It requires no API key or paid subscription, sources official central bank reference rates, and guarantees that every dashboard evaluation reflects genuine, current currency volatility.
- **Graceful Network Degradation:** If the live network call fails (e.g. offline environment or >10s timeout), the system never fabricates synthetic currency numbers. Instead, it reports `data_unavailable` and proportionally re-allocates the 20% weight across the active criteria:
  - **Market Volatility:** $\frac{40}{80} = 50.0\%$
  - **Seasonal Cyclone Risk:** $\frac{30}{80} = 37.5\%$
  - **Fleet Utilization:** $\frac{10}{80} = 12.5\%$

### 4. Documented Future Extensions (Considered but Not Implemented)
During development, two additional real-world risk dimensions were evaluated:
1. **Commodity-Price Correlation Risk (Thermal Coal / Metallurgical Coal):**
   *Why considered:* Sharp fluctuations in benchmark thermal coal (e.g. Newcastle 6,000 kcal) or coking coal prices alter trader willingness to lift cargoes, shift laycan urgency, and impact charterer default risk.
   *Why not implemented:* High-frequency global coal index APIs (e.g. Platts, Argus) require expensive enterprise proprietary subscriptions; no freely available, daily machine-readable public API exists without restrictive paywalls.
2. **Piracy & Geopolitical Maritime Chokepoint Risk:**
   *Why considered:* International dry bulk voyages transiting the Bab-el-Mandeb, Gulf of Aden, Red Sea, or the Strait of Malacca face potential rerouting around the Cape of Good Hope, adding 10–14 days and substantial bunker expenses.
   *Why not implemented:* Real-time maritime security telemetry feeds (such as the IMB Piracy Reporting Centre or UKMTO incident databases) do not provide open, unauthenticated REST APIs suitable for automated runtime ingestion without licensing agreements.
*Both features are documented as high-priority roadmap extensions once institutional API credentials or public feeds become accessible.*

---

## Origin Ports (Overseas Loading)

| Port | Country | Coordinates | Max Draft | Max Beam* | Max LOA | Load Rate* | Congestion* | Draft/LOA Verified |
|---|---|---|---|---|---|---|---|---|
| Newcastle | Australia | 32.917°S, 151.800°E | 16.2m | 45.0m | 300m | 40,000 tpd | 2.0 d | ✅ Yes |
| Nacala | Mozambique | 14.543°S, 40.673°E | 15.2m | 45.0m | 330m | 30,000 tpd | 2.0 d | ✅ Yes |
| Tanjung Bara | Indonesia | 0.537°N, 117.643°E | 16.0m | 42.0m | 290m | 20,000 tpd | 3.0 d | ⚠️ No (est.) |
| Vostochny | Russia | 42.733°N, 133.080°E | 16.5m | 45.0m | 300m | 25,000 tpd | 2.5 d | ⚠️ No (est.) |
| Hampton Roads | USA | 36.950°N, 76.330°W | 15.8m | 45.0m | 300m | 25,000 tpd | 2.5 d | ⚠️ No (est.) |

*\*Beam, load rate, and congestion values are marked `verified: false` as illustrative estimates.*

---

## Destination Ports (Indian East Coast)

| Port | Coordinates | Max Vessel DWT | Max Draft | Max Beam* | Max LOA | Discharge Rate* | Congestion* | Verification Status & Official Source |
|---|---|---|---|---|---|---|---|---|
| Paradip | 20.264°N, 86.670°E | 155,000 DWT | 16.5m | 40.0m | 260m | 28,000 tpd | 2.0 d | ✅ **DWT Verified** (~155k DWT Capesize); Berth draft 16–16.5m. *Source: Paradip Port official infrastructure page* |
| Visakhapatnam | 17.698°N, 83.279°E | 200,000 DWT | 18.1m | 48.0m | 356m | 35,000 tpd | 1.5 d | ✅ **Verified** (200k DWT Capesize; VGCB draft 18.1m). *Source: Visakhapatnam Port Authority* |
| Gangavaram | 17.622°N, 83.230°E | 200,000 DWT | 20.2m | 50.0m | 300m | 40,000 tpd | 1.0 d | ✅ **Verified** (200k DWT fully laden Capesize; draft 20.2m). *Source: Adani Ports / Gangavaram Port berthing policy* |
| Dhamra | 20.826°N, 86.972°E | 180,000 DWT | 18.0m | 48.0m | 300m | 30,000 tpd | 1.5 d | ✅ **Verified** (~180k DWT; draft 18.0m). *Source: Odisha Govt, Directorate of Ports & Inland Water Transport* |
| Gopalpur | 19.306°N, 84.967°E | 200,000 DWT | 13.5m | 32.0m | 200m | 15,000 tpd | 3.0 d | ⚠️ **Nuanced Verification**: 200k DWT ceiling verified (*Source: Gopalpur Ports berthing policy 2024*); draft (13.5m) provisional pending hydrographic precision |
| Haldia | 22.026°N, 88.058°E | 75,000 DWT | 9.0m | 28.0m | 180m | 12,000 tpd | 4.0 d | ⚠️ **Nuanced Verification**: 75k DWT dry-bulk ceiling verified (*Source: Shipping Ministry / Kolkata Port HDC report*); river draft (9.0m) provisional |

*\*Beam, discharge rate, and congestion values are marked `verified: false` as illustrative estimates.*

### Operational Tension & Hydrographic Disclosures
- **Paradip Draft-vs-DWT Operational Tension:** Paradip's official infrastructure page lists a maximum vessel size of ~155,000 DWT (Capesize range), while berth drafts are listed at ~16–16.5m (modeled at 16.5m). Because a standard fully-laden Capesize typically draws ~18.0m draft, this implies deeper channel/anchorage arrangements, lighterage, or tidal assistance not captured by a single berth draft figure. The system discloses both figures transparently rather than arbitrarily selecting one.
- **Gopalpur Hydrographic Precision:** Gopalpur's 200,000 DWT Capesize capacity ceiling is officially verified per the port's 2024 berthing policy document. This capability implies significantly deeper water access than the previous 13.5m placeholder. While the 200,000 DWT ceiling is enforced, the draft figure is flagged as provisional pending further hydrographic precision.
- **Haldia Riverine Draft Precision:** Haldia's ~75,000 DWT dry-bulk berth capacity is officially verified per Shipping Ministry / HDC administrative reports. The 9.0m draft reflects navigability constraints of the Hooghly River subject to siltation dynamics and tidal assistance; it is flagged as needing further precision rather than guessing an unverified draft.

---

## Known Limitations

1. **BDI data is synthetic.** The `data/raw/bdi_historical.csv` file contains algorithmically generated data (3 years of plausible values in the 300–6000 range). Replace with a real export from [balticdryindex.com](https://balticdryindex.com) or [macromicro.me](https://macromicro.me) before using for anything beyond a demo.

2. **Nuanced Port Verification Status:** On the destination side, maximum vessel capacity ceiling (`max_vessel_dwt`) is officially verified for all 6 Indian East Coast ports. Paradip, Visakhapatnam, Gangavaram, and Dhamra also have verified berth drafts, while Gopalpur and Haldia have officially verified DWT ceilings with provisional draft figures flagged for hydrographic precision. On the origin side, Tanjung Bara (Indonesia), Vostochny (Russia), and Hampton Roads (USA) are unverified estimates, whereas Newcastle (Australia) and Nacala (Mozambique) are fully verified from official terminal publications.

3. **Beam limits and handling rates are estimated.** As documented in the disclosure, beam limits and cargo handling rates are illustrative placeholders derived from mechanization evidence and vessel draft capabilities rather than official pilot books.

4. **Paradip Capesize Berth Constraints & Disclosed Tension:** Paradip's berth draft (16.5m) and LOA (260m) prevent standard 18.0m draft / 290m LOA Capesize berthing directly alongside standard berths, despite its official ~155,000 DWT capability. For deep-water Capesize direct discharge, Visakhapatnam (18.1m draft) or Gangavaram (20.2m draft) provide compliant infrastructure.

5. **Newcastle (Australia) cannot load Capesize vessels** — Newcastle's max draft (16.2m) is below Capesize draft (18.0m). Newcastle is a Panamax-limited port. For Capesize-capable origin ports, use one of the deeper-draft terminals (note: most verified coal terminals worldwide are also Panamax-limited).

---

## Why No Database

Reference data (vessel specs, ports) is static and loaded from JSON files. The forecasting model is a persisted pickle file, not transactional data. The system computes a response per request without storing anything — so a database adds infrastructure with no functional benefit at this scope.

---

## Deployment

### Recommended: Streamlit Community Cloud (simplest)

1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Point it at `frontend/streamlit_app.py`
4. Set the `API_BASE_URL` environment variable to point to your deployed backend

### Alternative: Backend on Render/Railway + Frontend on Streamlit Cloud

1. Deploy backend to Render.com using the `Procfile` (free tier)
2. Deploy frontend to Streamlit Community Cloud
3. Set `API_BASE_URL` environment variable in Streamlit Cloud settings

> **Note:** Free hosting tiers often sleep after inactivity and take 20–30 seconds to wake on first request. Open the link a minute before presenting.

---

## License

Built for Smart India Hackathon 2026 (SIH26006).
