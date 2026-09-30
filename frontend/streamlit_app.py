"""
Streamlit frontend for the Freight Chartering Decision Support System.

A professional, maritime-grade decision-support dashboard for bulk cargo
chartering teams importing commodities from overseas loading ports
to Indian East Coast discharge ports (SIH26006).

Consolidated Design System:
- Sharp, square geometry (0px border-radius) per industrial maritime aesthetic
- Consistent deep navy, slate, and teal palette
- Structured 3-tab decision narrative: Feasibility -> Cost & Timing -> Risk Analysis
- Zero emoji characters anywhere in the interface
- Comprehensive visual hierarchy: prominent decision verdicts followed by technical detail
- Integrated Draft/Beam schematic and interactive Navigational Route Map
"""

import os
import json
import requests
import pandas as pd
import altair as alt
import pydeck as pdk
import streamlit as st

# Backend API URL
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

# Page configuration - strictly zero emoji
st.set_page_config(
    page_title="Maritime Freight Decision Support | SIH26006",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Unified Maritime Design System (Sharp / Industrial / Navy / Teal Palette)
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* Base typography and container tweaks */
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--text-color, #1E293B);
}

/* Medium-style Body text */
.stMarkdown p, .stMarkdown li, div[data-testid="stMarkdownContainer"] > p, div[data-testid="stMarkdownContainer"] > ul {
    font-family: 'Lora', Georgia, serif !important;
    font-size: 20px !important;
    font-weight: 400 !important;
    line-height: 1.6 !important;
    margin-bottom: 1.4rem !important;
}

/* Headings */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6,
div[data-testid="stMarkdownContainer"] > h1, div[data-testid="stMarkdownContainer"] > h2, div[data-testid="stMarkdownContainer"] > h3 {
    font-family: 'Lora', Georgia, serif !important;
    font-weight: 700 !important;
}
div[data-testid="stMarkdownContainer"] > h1 { font-size: 34px !important; }
div[data-testid="stMarkdownContainer"] > h2 { font-size: 30px !important; }
div[data-testid="stMarkdownContainer"] > h3 { font-size: 26px !important; }

/* Links */
.stMarkdown a, div[data-testid="stMarkdownContainer"] a {
    color: inherit;
    text-decoration: underline !important;
    text-decoration-color: rgba(13, 148, 136, 0.5) !important;
    text-decoration-thickness: 1px !important;
    text-underline-offset: 2px !important;
}
.stMarkdown a:hover, div[data-testid="stMarkdownContainer"] a:hover {
    text-decoration-color: #0D9488 !important;
}

/* Italics */
.stMarkdown em, .stMarkdown i, div[data-testid="stMarkdownContainer"] em, div[data-testid="stMarkdownContainer"] i {
    font-family: 'Lora', Georgia, serif !important;
    font-style: italic !important;
}


/* Allow Streamlit theme to control base background canvas */
.stApp {
    background-color: var(--background-color, transparent);
}

/* Enforce sharp / square borders globally across UI components except buttons */
div, input, select, textarea, .stTabs, [data-baseweb="tab"] {
    border-radius: 0px !important;
}

/* Medium-style pill buttons */
.stButton > button, div[data-testid="stButton"] button {
    border-radius: 999px !important;
    font-weight: 600 !important;
    padding-top: 0.35rem !important;
    padding-bottom: 0.35rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
    box-shadow: none !important;
    min-height: 2.2rem !important; 
    line-height: 1.4 !important;
}

/* Clear contrast flat primary button */
.stButton > button[kind="primary"], div[data-testid="stButton"] button[kind="primary"] {
    background: #0D9488 !important;
    color: #FFFFFF !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover, div[data-testid="stButton"] button[kind="primary"]:hover {
    background: #0F766E !important;
}

/* Clear contrast flat secondary button */
.stButton > button[kind="secondary"], div[data-testid="stButton"] button[kind="secondary"] {
    background: transparent !important;
    color: var(--text-color, #FAFAFA) !important;
    border: 1px solid rgba(250, 250, 250, 0.4) !important;
}
.stButton > button[kind="secondary"]:hover, div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(250, 250, 250, 0.05) !important;
    border-color: var(--text-color, #FAFAFA) !important;
}

/* Header styling */
.header-container {
    padding-top: 3.5rem;
    padding-bottom: 1.5rem;
    margin-bottom: 3rem;
    color: var(--text-color, #FAFAFA);
}

.header-title {
    font-family: 'Lora', Georgia, serif;
    font-size: 44px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-color, #FAFAFA);
    margin: 0 0 1rem 0;
    display: flex;
    align-items: center;
    gap: 12px;
}

.header-tag {
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    background: #0D9488;
    color: #FFFFFF;
    padding: 4px 10px;
    border-radius: 999px;
}

.header-subtitle {
    font-family: 'Lora', Georgia, serif;
    font-size: 22px;
    color: #94A3B8;
    margin-top: 1rem;
    font-weight: 400;
    letter-spacing: 0.01em;
}

/* Input Form Container (Outside Tabs) */
.input-form-container {
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left: 4px solid #0D9488;
    border-radius: 0px;
    padding: 10px 18px;
    margin-bottom: 8px;
}

.form-header {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-color, inherit);
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Single Global Benchmark / Disclosure Banners (Outside Tabs) */
.benchmark-card {
    background: var(--secondary-background-color, rgba(13, 148, 136, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left: 4px solid #0D9488;
    border-radius: 0px;
    padding: 8px 14px;
    margin-bottom: 6px;
    font-size: 0.80rem;
    color: var(--text-color, inherit);
    line-height: 1.4;
}

.disclosure-card {
    background: rgba(217, 119, 6, 0.08);
    border: 1px solid rgba(217, 119, 6, 0.3);
    border-left: 4px solid #D97706;
    border-radius: 0px;
    padding: 8px 14px;
    margin-bottom: 8px;
    font-size: 0.78rem;
    color: var(--text-color, inherit);
    line-height: 1.4;
}

.assessment-strip {
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left: 4px solid #0D9488;
    border-radius: 0px;
    padding: 8px 16px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}

/* Industrial Streamlit Tabs Overrides - HIGH CONTRAST LIGHT/DARK COMPATIBLE */
.stTabs [data-baseweb="tab-list"] {
    position: sticky;
    top: 0px;
    z-index: 99;
    gap: 8px !important;
    background-color: transparent !important;
    padding: 6px 0px 4px 0px !important;
    border-bottom: 2px solid rgba(148, 163, 184, 0.3) !important;
    margin-bottom: 16px !important;
}

.stTabs [data-baseweb="tab"] {
    height: 44px !important;
    background-color: rgba(148, 163, 184, 0.12) !important;
    border-radius: 4px 4px 0px 0px !important;
    padding: 8px 22px !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    border-bottom: none !important;
    margin-right: 4px !important;
    cursor: pointer !important;
}

/* Force readable text on all unselected tabs in light and dark */
.stTabs [data-baseweb="tab"],
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] div,
.stTabs [data-baseweb="tab"] span {
    color: var(--text-color, currentColor) !important;
    font-weight: 700 !important;
    font-size: 0.94rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    opacity: 0.85 !important;
}

.stTabs [data-baseweb="tab"]:hover {
    background-color: rgba(13, 148, 136, 0.15) !important;
    border-color: #0D9488 !important;
}

.stTabs [data-baseweb="tab"]:hover p,
.stTabs [data-baseweb="tab"]:hover div,
.stTabs [data-baseweb="tab"]:hover span {
    color: var(--text-color, currentColor) !important;
    opacity: 1 !important;
}

/* Selected Tab: Vibrant Teal Card with Crisp White Text */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background-color: #0D9488 !important;
    border: 1px solid #0D9488 !important;
    border-bottom: none !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] p,
.stTabs [data-baseweb="tab"][aria-selected="true"] div,
.stTabs [data-baseweb="tab"][aria-selected="true"] span {
    color: #FFFFFF !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    background-color: #0D9488 !important;
}

/* Custom Card Container */
.custom-card {
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 0px;
    padding: 20px;
    margin-bottom: 20px;
}

/* Industrial Section Titles */
.section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-color, inherit);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-top: 14px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid rgba(148, 163, 184, 0.25);
    padding-bottom: 8px;
}

.section-subtitle {
    font-size: 0.82rem;
    font-weight: 400;
    color: var(--text-color, #94A3B8);
    opacity: 0.75;
    text-transform: none;
    letter-spacing: normal;
}

/* Metric Display Cards */
.metric-box {
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 0px;
    padding: 14px 16px;
    text-align: left;
    height: 100%;
}

.metric-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-color, #94A3B8);
    opacity: 0.8;
    margin-bottom: 4px;
}

.metric-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--text-color, inherit);
    letter-spacing: -0.02em;
    line-height: 1.2;
}

.metric-subtext {
    font-size: 0.76rem;
    color: var(--text-color, #94A3B8);
    opacity: 0.85;
    margin-top: 4px;
}

/* Executive Verdict Banners */
.verdict-banner {
    border-radius: 0px;
    padding: 20px 24px;
    margin-bottom: 20px;
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left: 6px solid #0D9488;
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
}

.verdict-banner.severe {
    border-left: 6px solid #DC2626;
    background: rgba(220, 38, 38, 0.08);
    border-color: rgba(220, 38, 38, 0.3);
}

.verdict-banner.high {
    border-left: 6px solid #EA580C;
    background: rgba(234, 88, 12, 0.08);
    border-color: rgba(234, 88, 12, 0.3);
}

.verdict-banner.moderate {
    border-left: 6px solid #D97706;
    background: rgba(217, 119, 6, 0.08);
    border-color: rgba(217, 119, 6, 0.3);
}

.verdict-banner.low {
    border-left: 6px solid #0D9488;
    background: rgba(13, 148, 136, 0.08);
    border-color: rgba(13, 148, 136, 0.3);
}

.verdict-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 0px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.verdict-badge.severe {
    background: rgba(220, 38, 38, 0.18);
    color: #EF4444;
    border: 1px solid #DC2626;
}

.verdict-badge.high {
    background: rgba(234, 88, 12, 0.18);
    color: #F97316;
    border: 1px solid #EA580C;
}

.verdict-badge.moderate {
    background: rgba(217, 119, 6, 0.18);
    color: #F59E0B;
    border: 1px solid #D97706;
}

.verdict-badge.low {
    background: rgba(13, 148, 136, 0.18);
    color: #14B8A6;
    border: 1px solid #0D9488;
}

.verdict-rec {
    font-size: 0.94rem;
    font-weight: 500;
    color: var(--text-color, inherit);
    line-height: 1.55;
}

/* Callout Box */
.custom-callout {
    padding: 14px 18px;
    border-radius: 0px;
    margin-bottom: 14px;
    font-size: 0.88rem;
    line-height: 1.5;
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left: 4px solid #64748B;
}

.custom-callout.info {
    background: rgba(13, 148, 136, 0.08);
    border-color: rgba(13, 148, 136, 0.3);
    color: var(--text-color, inherit);
    border-left: 4px solid #0D9488;
}

.custom-callout.warning {
    background: rgba(217, 119, 6, 0.08);
    border-color: rgba(217, 119, 6, 0.3);
    color: var(--text-color, inherit);
    border-left: 4px solid #D97706;
}

.custom-callout.severe {
    background: rgba(220, 38, 38, 0.08);
    border-color: rgba(220, 38, 38, 0.3);
    color: var(--text-color, inherit);
    border-left: 4px solid #DC2626;
}

.custom-callout.neutral {
    background: rgba(148, 163, 184, 0.08);
    border-color: rgba(148, 163, 184, 0.25);
    color: var(--text-color, inherit);
    border-left: 4px solid #64748B;
}

/* Market Timing Executive Card */
.timing-card {
    border-radius: 0px;
    padding: 22px 26px;
    margin-bottom: 22px;
    border: 1px solid rgba(148, 163, 184, 0.25);
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
}

.timing-card.charter-now {
    border-left: 6px solid #0D9488;
    background: rgba(13, 148, 136, 0.08);
    border-color: rgba(13, 148, 136, 0.3);
}

.timing-card.wait-window {
    border-left: 6px solid #D97706;
    background: rgba(217, 119, 6, 0.08);
    border-color: rgba(217, 119, 6, 0.3);
}

.timing-card.monitor {
    border-left: 6px solid #64748B;
    background: rgba(100, 116, 139, 0.08);
    border-color: rgba(100, 116, 139, 0.3);
}

.timing-verdict-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 0px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.timing-verdict-badge.charter-now {
    background: rgba(13, 148, 136, 0.18);
    color: #0D9488;
    border: 1px solid #0D9488;
}

.timing-verdict-badge.wait-window {
    background: rgba(217, 119, 6, 0.18);
    color: #D97706;
    border: 1px solid #D97706;
}

.timing-verdict-badge.monitor {
    background: rgba(100, 116, 139, 0.18);
    color: #94A3B8;
    border: 1px solid #64748B;
}

.timing-reasoning {
    font-size: 0.98rem;
    font-weight: 500;
    color: var(--text-color, inherit);
    line-height: 1.6;
    margin-top: 10px;
    margin-bottom: 14px;
}

.timing-metric {
    display: flex;
    flex-direction: column;
    min-width: 140px;
}

.timing-metric-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-color, #94A3B8);
    opacity: 0.8;
    margin-bottom: 2px;
}

.timing-metric-val {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-color, inherit);
    line-height: 1.2;
}

.timing-metric-sub {
    font-size: 0.74rem;
    color: var(--text-color, #94A3B8);
    opacity: 0.8;
    margin-top: 2px;
}

/* Empty State Box */
.empty-state-box {
    text-align: center;
    padding: 60px 24px;
    color: var(--text-color, #94A3B8);
    background: var(--secondary-background-color, rgba(148, 163, 184, 0.06));
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 0px;
}

.empty-state-tag {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #0D9488;
    background: rgba(13, 148, 136, 0.12);
    padding: 4px 10px;
    border: 1px solid #0D9488;
    display: inline-block;
    margin-bottom: 12px;
}

/* Tighten Streamlit default container padding */
.block-container {
    padding-top: 1.8rem;
    padding-bottom: 3rem;
    max-width: 1320px;
}
</style>
"""

# Helper function to generate an inline SVG sparkline
def make_sparkline_svg(values, width=120, height=24, color="#0D9488"):
    """Generate a clean, lightweight inline SVG polyline sparkline."""
    if not values or len(values) < 2:
        return ""
    min_v = min(values)
    max_v = max(values)
    rng = max_v - min_v if max_v != min_v else 1.0

    pts = []
    for i, v in enumerate(values):
        x = round(i / (len(values) - 1) * (width - 4) + 2, 1)
        y = round(height - 4 - ((v - min_v) / rng) * (height - 8), 1)
        pts.append(f"{x},{y}")
    polyline = " ".join(pts)

    return (
        f'<svg width="{width}" height="{height}" style="vertical-align: middle; overflow: visible;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter" points="{polyline}" />'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Reference Data Loaders
# ---------------------------------------------------------------------------
def load_origin_ports():
    """Load overseas origin port names and metadata."""
    try:
        r = requests.get(f"{API_BASE}/api/origin-ports", timeout=5)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.ConnectionError:
        pass

    ports_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "data", "reference", "origin_ports.json"
    )
    if os.path.exists(ports_path):
        with open(ports_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_dest_ports():
    """Load Indian East Coast destination port names and metadata."""
    try:
        r = requests.get(f"{API_BASE}/api/ports", timeout=5)
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.ConnectionError:
        pass

    ports_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "data", "reference", "ports.json"
    )
    if os.path.exists(ports_path):
        with open(ports_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Maritime Routing & Navigation Corridors (Bypasses Landmasses)
# ---------------------------------------------------------------------------
def get_maritime_route_data(origin_name, dest_name, origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Constructs realistic maritime shipping corridors with sea-lane waypoints,
    chokepoints, and maritime straits avoiding continental landmasses.
    Returns:
        waypoints: List of [lon, lat] coordinate pairs for pydeck PathLayer
        chokepoints: List of dicts with name, lon, lat for navigational markers
        corridor_name: Human-readable name of the established maritime corridor
    """
    orig_pt = [origin_lon, origin_lat]
    dest_pt = [dest_lon, dest_lat]

    dondra_head = [80.80, 5.70]     # South of Sri Lanka deepwater TSS
    east_sri_lanka = [82.20, 8.50]  # East of Sri Lanka into Bay of Bengal
    south_bob = [83.50, 13.00]       # South-Central Bay of Bengal corridor

    six_degree = [94.50, 6.00]       # Six Degree Channel / Great Channel north of Aceh
    central_bob = [88.00, 12.50]     # Central Bay of Bengal fairway

    chokepoints = []

    if "Newcastle" in origin_name:
        corridor_name = "Cape Leeuwin & Southern Ocean Bulk Route"
        waypoints = [
            orig_pt,
            [151.60, -34.50],   # Off Wollongong
            [150.20, -37.80],   # Cape Howe
            [148.00, -39.30],   # Bass Strait East
            [145.00, -39.80],   # Bass Strait Central
            [142.50, -39.80],   # Bass Strait West
            [135.00, -37.50],   # Great Australian Bight East
            [125.00, -36.00],   # Great Australian Bight West
            [115.00, -35.20],   # Cape Leeuwin South
            [112.00, -33.00],   # SW Australia oceanic turn
            [105.00, -25.00],   # Indian Ocean SE
            [98.00, -15.00],    # Indian Ocean Central
            [90.00, -3.00],     # Equator crossing
            [84.00, 4.00],      # Approaching Sri Lanka
            dondra_head,        # Dondra Head
            east_sri_lanka,
            south_bob,
            dest_pt
        ]
        chokepoints = [
            {"name": "Maritime Chokepoint: Bass Strait", "lon": 145.00, "lat": -39.80},
            {"name": "Strategic Turning Point: Cape Leeuwin", "lon": 115.00, "lat": -35.20},
            {"name": "Navigational Waypoint: Dondra Head (Sri Lanka)", "lon": 80.80, "lat": 5.70},
        ]

    elif "Nacala" in origin_name:
        corridor_name = "Mozambique Channel & Equatorial Indian Ocean Transit"
        waypoints = [
            orig_pt,
            [42.00, -13.00],    # Mozambique Channel North
            [44.00, -11.00],    # Clear of Comoros
            [49.00, -8.00],     # North of Madagascar
            [55.00, -4.50],     # Seychelles South Basin
            [65.00, 0.00],      # Equatorial Indian Ocean
            [73.50, 2.50],      # South of Maldives
            dondra_head,        # Dondra Head
            east_sri_lanka,
            south_bob,
            dest_pt
        ]
        chokepoints = [
            {"name": "Transit Channel: Mozambique Channel", "lon": 44.00, "lat": -11.00},
            {"name": "Equatorial Crossing: Central Indian Ocean", "lon": 65.00, "lat": 0.00},
            {"name": "Navigational Waypoint: Dondra Head (Sri Lanka)", "lon": 80.80, "lat": 5.70},
        ]

    elif "Tanjung Bara" in origin_name:
        corridor_name = "Makassar Strait, Sunda Strait & Six Degree Channel"
        waypoints = [
            orig_pt,
            [118.20, -1.50],    # Makassar Strait Central
            [117.50, -4.20],    # Makassar Strait South
            [114.50, -5.50],    # Java Sea East
            [110.00, -5.80],    # Java Sea Central
            [106.50, -5.90],    # Java Sea West
            [105.70, -6.05],    # Sunda Strait Channel
            [104.50, -6.60],    # Sunda Strait Indian Ocean Exit
            [99.50, -3.50],     # SW of Sumatra
            [95.50, 0.50],      # West Sumatra Offshore
            [93.80, 4.50],      # North Sumatra Offshore
            six_degree,         # Six Degree Channel
            central_bob,        # Central Bay of Bengal
            dest_pt
        ]
        chokepoints = [
            {"name": "Strategic Strait: Makassar Strait", "lon": 118.20, "lat": -1.50},
            {"name": "Strategic Strait: Sunda Strait", "lon": 105.70, "lat": -6.05},
            {"name": "Strategic Chokepoint: Six Degree Channel", "lon": 94.50, "lat": 6.00},
        ]

    elif "Vostochny" in origin_name:
        corridor_name = "Tsushima, Singapore & Malacca Straits Shipping Lane"
        waypoints = [
            orig_pt,
            [131.50, 39.00],    # Sea of Japan South
            [130.00, 36.00],    # Sea of Japan SW
            [129.20, 34.20],    # Tsushima Strait
            [125.00, 30.50],    # East China Sea
            [122.50, 25.50],    # North of Taiwan
            [118.50, 22.00],    # Taiwan Strait South
            [114.00, 16.00],    # South China Sea
            [110.00, 10.00],    # Off Vietnam Coast
            [106.00, 3.50],     # Approaching Singapore
            [104.20, 1.30],     # Singapore Strait East
            [103.80, 1.20],     # Singapore Strait TSS
            [101.50, 2.70],     # Malacca Strait Mid
            [98.50, 4.50],      # Malacca Strait North
            six_degree,         # Six Degree Channel / Andaman Sea
            central_bob,        # Central Bay of Bengal
            dest_pt
        ]
        chokepoints = [
            {"name": "Strategic Strait: Tsushima Strait", "lon": 129.20, "lat": 34.20},
            {"name": "Major Chokepoint: Singapore Strait", "lon": 103.80, "lat": 1.20},
            {"name": "Strategic Chokepoint: Malacca Strait", "lon": 101.50, "lat": 2.70},
            {"name": "Exit Chokepoint: Six Degree Channel", "lon": 94.50, "lat": 6.00},
        ]

    elif "Hampton Roads" in origin_name:
        corridor_name = "Gibraltar, Suez Canal & Red Sea Maritime Route"
        waypoints = [
            orig_pt,
            [-75.50, 36.80],    # Cape Henry / Chesapeake Exit
            [-60.00, 36.50],    # North Atlantic
            [-40.00, 36.00],    # Mid-Atlantic
            [-20.00, 36.00],    # East Atlantic
            [-9.00, 36.00],     # Approaching Gibraltar
            [-5.50, 35.95],     # Strait of Gibraltar
            [3.00, 37.00],      # West Mediterranean
            [15.00, 36.00],     # Central Mediterranean (South of Sicily)
            [26.00, 34.00],     # East Mediterranean (South of Crete)
            [32.35, 31.30],     # Port Said (Suez North)
            [32.55, 29.95],     # Suez South Exit
            [33.50, 27.50],     # Gulf of Suez Exit
            [38.00, 20.00],     # Red Sea Central
            [43.30, 12.60],     # Bab-el-Mandeb Strait
            [48.00, 12.50],     # Gulf of Aden
            [60.00, 11.00],     # Arabian Sea Central
            [73.00, 7.50],      # Lakshadweep Sea
            dondra_head,        # Dondra Head
            east_sri_lanka,
            south_bob,
            dest_pt
        ]
        chokepoints = [
            {"name": "Strategic Strait: Gibraltar", "lon": -5.50, "lat": 35.95},
            {"name": "Canal Chokepoint: Suez Canal", "lon": 32.55, "lat": 29.95},
            {"name": "Strategic Strait: Bab-el-Mandeb", "lon": 43.30, "lat": 12.60},
            {"name": "Navigational Waypoint: Dondra Head (Sri Lanka)", "lon": 80.80, "lat": 5.70},
        ]

    else:
        corridor_name = "Oceanic Transit Arc"
        mid_lon = (origin_lon + dest_lon) / 2
        mid_lat = min(origin_lat, dest_lat) - 8.0
        waypoints = [orig_pt, [mid_lon, mid_lat], dest_pt]
        chokepoints = []

    return waypoints, chokepoints, corridor_name


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
def main():
    # Inject Custom Design System CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Top Executive Header (Industrial Maritime Command Cockpit, Zero Emoji)
    st.markdown("""
    <div class="header-container">
        <div class="header-title">
            <span class="header-tag">DECISION COCKPIT</span>
            <span>Maritime Freight Decision Support System</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Load port reference data
    origin_ports = load_origin_ports()
    dest_ports = load_dest_ports()

    if not origin_ports or not dest_ports:
        st.markdown("""
        <div class="custom-callout severe">
            <strong>SYSTEM ALERT: Backend Service Offline</strong><br>
            Could not connect to the decision engine at <code>http://127.0.0.1:8000</code>.<br>
            Please start the backend API: <code>python -m uvicorn backend.app:app --port 8000</code>
        </div>
        """, unsafe_allow_html=True)
        return

    origin_port_names = list(origin_ports.keys())
    dest_port_names = list(dest_ports.keys())

    # -----------------------------------------------------------------------
    # Primary Voyage Configuration in Sidebar (Clean Main Deck)
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.markdown("### VOYAGE CONFIGURATION")
        cargo_qty = st.number_input(
            "Cargo Quantity (MT)",
            min_value=1000,
            max_value=500000,
            value=st.session_state.get("cargo_qty", 50000),
            step=5000,
            help="Total bulk cargo parcel size in metric tonnes",
            key="sb_cargo_qty"
        )
        origin = st.selectbox(
            "Origin (Loading Port)",
            origin_port_names,
            index=origin_port_names.index(st.session_state.get("origin", origin_port_names[0])) if st.session_state.get("origin") in origin_port_names else 0,
            help="Overseas bulk loading port",
            key="sb_origin"
        )
        destination = st.selectbox(
            "Destination (Discharge Port)",
            dest_port_names,
            index=dest_port_names.index(st.session_state.get("destination", "Gangavaram")) if st.session_state.get("destination") in dest_port_names else 2,
            help="Indian East Coast discharge port",
            key="sb_destination"
        )
        horizon_days = st.slider(
            "Forecast Horizon (Days)",
            min_value=7,
            max_value=365,
            value=st.session_state.get("horizon_days", 90),
            step=7,
            help="Forward projection window in calendar days",
            key="sb_horizon"
        )
        run_query = st.button("RUN DECISION ENGINE", type="primary", use_container_width=True, key="sb_run_btn")

        st.markdown("---")
        st.markdown("### ROUTE CONSTRAINTS")
        origin_draft = origin_ports[origin].get("max_draft_m", "N/A")
        dest_draft = dest_ports[destination].get("max_draft_m", "N/A")
        dest_dwt = dest_ports[destination].get("max_vessel_dwt", "N/A")
        dest_dwt_str = f"{dest_dwt:,} DWT" if isinstance(dest_dwt, (int, float)) else str(dest_dwt)
        st.caption(f"**Origin ({origin})**: Max Draft {origin_draft}m")
        st.caption(f"**Destination ({destination})**: Max Draft {dest_draft}m | Ceiling {dest_dwt_str}")

    # -----------------------------------------------------------------------
    # Decision Engine Execution & State Management
    # -----------------------------------------------------------------------
    # Auto-execute default scenario on initial page load so tabs are immediately populated
    if run_query or "recommendation_data" not in st.session_state:
        with st.spinner("Computing freight forecasts, port feasibility evaluations, and volatility risk profiles..."):
            try:
                r = requests.get(
                    f"{API_BASE}/api/recommend",
                    params={
                        "cargo_qty": cargo_qty,
                        "origin": origin,
                        "destination": destination,
                        "horizon_days": horizon_days,
                    },
                    timeout=60,
                )

                if r.status_code == 200:
                    data = r.json()
                    st.session_state["recommendation_data"] = data
                    st.session_state["active_params"] = {
                        "cargo_qty": cargo_qty,
                        "origin": origin,
                        "destination": destination,
                        "horizon_days": horizon_days
                    }
                else:
                    detail = r.json().get("detail", r.text) if r.headers.get("content-type") == "application/json" else r.text
                    st.error(f"API Error ({r.status_code}): {detail}")
                    return

            except requests.exceptions.ConnectionError:
                st.markdown("""
                <div class="custom-callout severe">
                    <strong>CONNECTION FAILURE:</strong> Cannot reach backend decision engine at <code>http://127.0.0.1:8000</code>.
                </div>
                """, unsafe_allow_html=True)
                return
            except Exception as e:
                st.error(f"Execution Error: {e}")
                return

    # Render results if active in session state
    if "recommendation_data" in st.session_state:
        data = st.session_state["recommendation_data"]
        params = st.session_state.get("active_params", {
            "cargo_qty": cargo_qty,
            "origin": origin,
            "destination": destination,
            "horizon_days": horizon_days
        })
        display_consolidated_dashboard(
            data,
            params["cargo_qty"],
            params["origin"],
            params["destination"],
            params["horizon_days"],
            origin_ports,
            dest_ports
        )


# ---------------------------------------------------------------------------
# Consolidated Dashboard with Strict 3-Tab Narrative Structure
# ---------------------------------------------------------------------------
def display_consolidated_dashboard(data, cargo_qty, origin, destination, horizon_days, origin_ports, dest_ports):
    """
    Renders the decision support results strictly organized into Streamlit tabs:
    Tab 1: Feasibility
    Tab 2: Cost & Timing
    Tab 3: Risk Analysis
    """
    forecast = data.get("forecast", [])
    vessels = data.get("vessel_recommendations", [])
    risk_analysis = data.get("risk_analysis", {})
    idle_flags = data.get("idle_time_flags", [])
    meta = data.get("metadata", {})
    market_timing = data.get("market_timing", {})

    start_date = forecast[0]["ds"] if forecast else "N/A"
    end_date = forecast[-1]["ds"] if forecast else "N/A"

    # Per-class rates bar
    rate_lookup = meta.get("rate_lookup", {})
    rate_chips = []
    for k in ["capesize", "panamax", "supramax", "handysize"]:
        if k in rate_lookup:
            rate_chips.append(f"<strong>{k.upper()}</strong>: ${rate_lookup[k]:.2f}/t")
    rate_summary_html = " &nbsp;|&nbsp; ".join(rate_chips) if rate_chips else ""

    # Clean Scenario Summary (Directly above tabs) - Theme Neutral
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--secondary-background-color, rgba(148, 163, 184, 0.08)); border: 1px solid rgba(148, 163, 184, 0.25); border-left: 4px solid #0D9488; margin-bottom: 14px;">
        <span style="font-size: 1.05rem; font-weight: 700; color: var(--text-color, inherit);">
            VOYAGE EVALUATION: <span style="color: #0D9488;">{cargo_qty:,.0f} MT</span> ({origin} → {destination})
        </span>
        <span style="font-size: 0.82rem; font-weight: 600; color: var(--text-color, inherit); background: rgba(148, 163, 184, 0.15); padding: 4px 10px; border: 1px solid rgba(148, 163, 184, 0.3);">
            HORIZON: {start_date} to {end_date} ({len(forecast)}d)
        </span>
    </div>
    """, unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # RESTRUCTURED INTO EXPLICIT STREAMLIT TABS (Problem Statement Priority)
    # Tab 1: Cost & Timing (Requirement a: Optimal Market Entry Timing)
    # Tab 2: Feasibility (Requirement b: Vessel Type Optimization)
    # Tab 3: Risk Analysis
    # -----------------------------------------------------------------------
    tab_cost_timing, tab_feasibility, tab_risk = st.tabs([
        "Tab 1: Cost & Timing",
        "Tab 2: Feasibility",
        "Tab 3: Risk Analysis"
    ])

    # =======================================================================
    # TAB 1: COST & TIMING (Problem Statement Priority: Requirement a)
    # =======================================================================
    with tab_cost_timing:
        if rate_summary_html:
            st.markdown(f"""
            <div style="background: var(--secondary-background-color, rgba(13, 148, 136, 0.08)); border: 1px solid rgba(148, 163, 184, 0.25); border-left: 4px solid #0D9488; padding: 8px 14px; margin-bottom: 14px; font-size: 0.82rem; color: var(--text-color, inherit);">
                <strong>CURRENT MARKET BENCHMARK RATES:</strong> &nbsp;{rate_summary_html}
            </div>
            """, unsafe_allow_html=True)

        # 1. PRIMARY DECISION-CRITICAL ELEMENT: Optimal Market Entry Timing Card (TOP OF TAB)
        if market_timing and market_timing.get("verdict"):
            mt_verdict = market_timing.get("verdict", "MONITOR")
            mt_start = market_timing.get("recommended_window_start", "N/A")
            mt_end = market_timing.get("recommended_window_end", "N/A")
            mt_rate = market_timing.get("expected_avg_rate", 0.0)
            mt_conf = market_timing.get("expected_confidence", 0.0)
            mt_pct_below = market_timing.get("pct_below_horizon_avg", 0.0)
            mt_reasoning = market_timing.get("reasoning", "")
            mt_curr_rate = market_timing.get("current_window_avg_rate")
            mt_horizon_avg = market_timing.get("horizon_avg_rate")

            if mt_verdict == "CHARTER NOW":
                timing_cls = "charter-now"
                badge_text = "CHARTER NOW"
                accent_color = "#0D9488"
                adv_color = "#0D9488"
                adv_text = f"At horizon floor ({mt_pct_below:+.1f}%)" if mt_pct_below <= 0 else f"{mt_pct_below:.1f}% below avg"
            elif mt_verdict == "WAIT FOR WINDOW":
                timing_cls = "wait-window"
                badge_text = "WAIT FOR WINDOW"
                accent_color = "#D97706"
                adv_color = "#D97706"
                adv_text = f"{mt_pct_below:.1f}% below avg"
            else:  # MONITOR
                timing_cls = "monitor"
                badge_text = "MONITOR MARKET"
                accent_color = "#94A3B8"
                adv_color = "#94A3B8"
                adv_text = f"{mt_pct_below:.1f}% below avg"

            if mt_conf < 25.0:
                conf_tier = "High confidence"
            elif mt_conf < 50.0:
                conf_tier = "Moderate confidence"
            elif mt_conf < 100.0:
                conf_tier = "Moderate-to-wide band"
            else:
                conf_tier = "Elevated uncertainty"

            if mt_curr_rate is not None and mt_curr_rate > 0:
                diff_pct = ((mt_curr_rate - mt_rate) / mt_curr_rate) * 100.0
                if diff_pct > 0:
                    diff_text = f"-{diff_pct:.1f}% cheaper"
                    diff_color = "#0D9488"
                elif diff_pct < 0:
                    diff_text = f"+{abs(diff_pct):.1f}% higher"
                    diff_color = "#DC2626"
                else:
                    diff_text = "Parity with Day 1"
                    diff_color = "#94A3B8"
            else:
                diff_text = "N/A"
                diff_color = "#94A3B8"

            horizon_label = f"{mt_horizon_avg:,.0f} BDI" if mt_horizon_avg else "horizon avg"

            timing_html = (
                f'<div class="timing-card {timing_cls}">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 8px;">'
                f'<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">'
                f'<span class="timing-verdict-badge {timing_cls}">{badge_text}</span>'
                f'<span style="font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-color, #94A3B8); opacity: 0.85;">'
                f'OPTIMAL MARKET ENTRY TIMING'
                f'</span>'
                f'</div>'
                f'<div style="font-size: 0.90rem; font-weight: 600; color: var(--text-color, inherit);">'
                f'RECOMMENDED CONTRACTING WINDOW: <strong style="color: {accent_color}; font-size: 1.05rem;">{mt_start}</strong> TO <strong style="color: {accent_color}; font-size: 1.05rem;">{mt_end}</strong>'
                f'</div>'
                f'</div>'
                f'<div class="timing-reasoning">{mt_reasoning}</div>'
                f'<div style="display: flex; gap: 24px; flex-wrap: wrap; margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(148, 163, 184, 0.2);">'
                f'<div class="timing-metric">'
                f'<span class="timing-metric-label">Expected Window Rate</span>'
                f'<span class="timing-metric-val">{mt_rate:,.0f} <span style="font-size: 0.8rem; color: var(--text-color, #94A3B8); opacity: 0.8; font-weight: 500;">BDI</span></span>'
                f'<span class="timing-metric-sub">~${mt_rate/100:.2f}/t proxy</span>'
                f'</div>'
                f'<div class="timing-metric">'
                f'<span class="timing-metric-label">Horizon Cost Advantage</span>'
                f'<span class="timing-metric-val" style="color: {adv_color};">{adv_text}</span>'
                f'<span class="timing-metric-sub">vs {horizon_days}d mean ({horizon_label})</span>'
                f'</div>'
                f'<div class="timing-metric">'
                f'<span class="timing-metric-label">Confidence Band Width</span>'
                f'<span class="timing-metric-val">{mt_conf:.1f}%</span>'
                f'<span class="timing-metric-sub">{conf_tier}</span>'
                f'</div>'
                f'<div class="timing-metric">'
                f'<span class="timing-metric-label">Spot Differential</span>'
                f'<span class="timing-metric-val" style="color: {diff_color};">{diff_text}</span>'
                f'<span class="timing-metric-sub">vs Day 1 forward baseline</span>'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(timing_html, unsafe_allow_html=True)

        # 2. Freight Rate Forecast & Entry Window (Altair Chart + Metrics)
        st.markdown('<div class="section-title"><span>Freight Rate Forecast & Entry Window</span><span class="section-subtitle">Composite BDI forecast curve with 85% confidence band and highlighted entry window</span></div>', unsafe_allow_html=True)

        forecast_df = pd.DataFrame(forecast) if forecast else pd.DataFrame(columns=["ds", "yhat", "yhat_lower", "yhat_upper"])
        if not forecast_df.empty and "ds" in forecast_df.columns:
            forecast_df["date"] = pd.to_datetime(forecast_df["ds"])
        else:
            forecast_df["date"] = pd.Series(dtype="datetime64[ns]")

        chart_rendered = False
        try:
            f_df = forecast_df.copy()

            # Confidence interval band (85%)
            band = alt.Chart(f_df).mark_area(opacity=0.20, color="#94A3B8").encode(
                x=alt.X("date:T", title="Timeline", axis=alt.Axis(format="%b %d", labelAngle=-30)),
                y=alt.Y("yhat_lower:Q", title="Baltic Dry Index (BDI)"),
                y2="yhat_upper:Q"
            )

            # Main forecast curve
            line = alt.Chart(f_df).mark_line(color="#0D9488", strokeWidth=2.6).encode(
                x="date:T",
                y=alt.Y("yhat:Q"),
                tooltip=[
                    alt.Tooltip("ds:N", title="Date"),
                    alt.Tooltip("yhat:Q", title="Forecast (BDI)", format=",.0f"),
                    alt.Tooltip("yhat_lower:Q", title="Lower (85%)", format=",.0f"),
                    alt.Tooltip("yhat_upper:Q", title="Upper (85%)", format=",.0f"),
                ]
            )

            chart_layers = [band]

            if market_timing and market_timing.get("recommended_window_start"):
                w_start = market_timing["recommended_window_start"]
                w_end = market_timing["recommended_window_end"]
                w_verdict = market_timing.get("verdict", "CHARTER NOW")
                w_color = "#0D9488" if w_verdict == "CHARTER NOW" else ("#D97706" if w_verdict == "WAIT FOR WINDOW" else "#64748B")

                w_df = pd.DataFrame([{
                    "start": pd.to_datetime(w_start),
                    "end": pd.to_datetime(w_end),
                    "label": f"Optimal Entry Window: {w_start} to {w_end} ({w_verdict})"
                }])

                rect = alt.Chart(w_df).mark_rect(opacity=0.20, color=w_color).encode(
                    x="start:T",
                    x2="end:T",
                    tooltip=[alt.Tooltip("label:N", title="Optimal Window")]
                )
                r1 = alt.Chart(w_df).mark_rule(color=w_color, strokeDash=[4, 4], strokeWidth=1.5).encode(x="start:T")
                r2 = alt.Chart(w_df).mark_rule(color=w_color, strokeDash=[4, 4], strokeWidth=1.5).encode(x="end:T")
                chart_layers.extend([rect, r1, r2])

            chart_layers.append(line)

            forecast_chart = alt.layer(*chart_layers).properties(
                height=340
            ).configure_view(
                strokeWidth=0
            ).configure_axis(
                labelFontSize=11,
                titleFontSize=12,
                gridColor="rgba(148, 163, 184, 0.15)"
            )

            st.altair_chart(forecast_chart, use_container_width=True)
            chart_rendered = True

        except Exception:
            chart_rendered = False

        if not chart_rendered and not forecast_df.empty:
            fallback_df = forecast_df.set_index("date").rename(columns={
                "yhat": "Forecast",
                "yhat_lower": "Lower (85%)",
                "yhat_upper": "Upper (85%)",
            })
            st.line_chart(fallback_df[["Forecast", "Lower (85%)", "Upper (85%)"]], color=["#0D9488", "#94A3B8", "#94A3B8"], use_container_width=True)

        # Forecast Summary Metrics
        mcol1, mcol2, mcol3 = st.columns(3)
        if not forecast_df.empty and "yhat" in forecast_df.columns:
            c_val = float(forecast_df['yhat'].iloc[0])
            m_val = float(forecast_df['yhat'].iloc[:30].mean())
            e_val = float(forecast_df['yhat'].iloc[-1])
            delta_val = e_val - c_val
        else:
            c_val = m_val = e_val = delta_val = 0.0

        with mcol1:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Current Forecast Baseline</div>
                <div class="metric-value">{c_val:,.0f} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">BDI</span></div>
                <div class="metric-subtext">Day 1 forward estimate</div>
            </div>
            """, unsafe_allow_html=True)

        with mcol2:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">30-Day Mean Expectation</div>
                <div class="metric-value">{m_val:,.0f} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">BDI</span></div>
                <div class="metric-subtext">Near-term operational benchmark</div>
            </div>
            """, unsafe_allow_html=True)

        with mcol3:
            delta_color = "#0D9488" if delta_val >= 0 else "#DC2626"
            delta_sign = "+" if delta_val >= 0 else ""
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Horizon Terminal Value</div>
                <div class="metric-value">{e_val:,.0f} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">BDI</span></div>
                <div class="metric-subtext" style="color: {delta_color}; font-weight: 600;">{delta_sign}{delta_val:,.0f} BDI over {horizon_days}d</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # 3. Per-Vessel-Class Rate Table (With note for infeasible classes pointing to Tab 2)
        st.markdown('<div class="section-title"><span>Per-Vessel-Class Freight Rate Breakdown</span><span class="section-subtitle">Mapped Baltic sub-index rates & voyage cost allocations</span></div>', unsafe_allow_html=True)

        rate_rows = []
        for v in vessels:
            v_class = v.get("vessel_class", "")
            sub_idx = v.get("rate_index", "BDI")
            r_per_t = v.get("rate_per_tonne", 0.0)
            day_rate = v.get("daily_charter_rate", 0)
            tot_cost = v.get("total_cost", 0)
            is_feas = v.get("feasible", False)

            rate_rows.append({
                "Vessel Class": v_class,
                "Capacity Range": f"{v.get('dwt_min', 0):,} – {v.get('dwt_max', 0):,} DWT",
                "Baltic Sub-Index": sub_idx,
                "Freight Rate ($/t)": f"${r_per_t:.2f}/t",
                "Daily Charter Rate": f"${day_rate:,}/day" if day_rate else "N/A",
                "Est. Voyage Cost": f"${tot_cost:,.0f}" if tot_cost else "N/A",
                "Feasibility": "FEASIBLE" if is_feas else "INFEASIBLE (See Tab 2)",
            })
        st.dataframe(pd.DataFrame(rate_rows), use_container_width=True, hide_index=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # 4. Voyage Cost & Turnaround Breakdown
        st.markdown('<div class="section-title"><span>Voyage Operational Breakdown</span><span class="section-subtitle">Transit durations, berth handling, and turnaround modeling</span></div>', unsafe_allow_html=True)

        route_dist = meta.get("route_distance_nm")
        adj_dist = meta.get("route_adjusted_distance_nm")
        sea_days = meta.get("route_sea_days")
        berth_days = meta.get("berth_days")
        cong_days = meta.get("congestion_days")
        total_days = meta.get("total_voyage_days")

        if route_dist:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Route Distance</div>
                    <div class="metric-value">{adj_dist:,} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">nm</span></div>
                    <div class="metric-subtext">Haversine base: {route_dist:,} nm (1.10x factor)</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Sailing Duration</div>
                    <div class="metric-value">{sea_days} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">days</span></div>
                    <div class="metric-subtext">Laden transit @ 13.0 knots</div>
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Berth Handling</div>
                    <div class="metric-value">{berth_days} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">days</span></div>
                    <div class="metric-subtext">Load + discharge handling</div>
                </div>
                """, unsafe_allow_html=True)
            with c4:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Total Turnaround</div>
                    <div class="metric-value">{total_days} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-color, #94A3B8); opacity: 0.8;">days</span></div>
                    <div class="metric-subtext">Includes {cong_days}d congestion estimate</div>
                </div>
                """, unsafe_allow_html=True)

    # =======================================================================
    # TAB 2: FEASIBILITY (Problem Statement Priority: Requirement b)
    # =======================================================================
    with tab_feasibility:
        feasible = [v for v in vessels if v["feasible"]]
        infeasible = [v for v in vessels if not v["feasible"]]

        origin_spec = origin_ports.get(origin, {})
        dest_spec = dest_ports.get(destination, {})
        origin_max_draft = float(origin_spec.get("max_draft_m", 16.0))
        dest_max_draft = float(dest_spec.get("max_draft_m", 18.0))

        # 1. PRIMARY DECISION-CRITICAL ELEMENT: Feasibility Verdict (Largest/Most Prominent)
        if feasible:
            top_v = feasible[0]
            st.markdown(f"""
            <div class="verdict-banner low" style="padding: 22px 26px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                    <span class="verdict-badge low">FEASIBILITY STATUS: COMPLIANT ALLOCATION AVAILABLE</span>
                    <span style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #10B981;">
                        PORT & VESSEL BOUNDARIES VERIFIED
                    </span>
                </div>
                <div style="font-size: 1.35rem; font-weight: 700; color: var(--text-color, inherit); margin-bottom: 6px;">
                    Primary Recommended Class: <span style="color: #0D9488;">{top_v['vessel_class'].upper()}</span> ({top_v['dwt_min']:,} – {top_v['dwt_max']:,} DWT)
                </div>
                <div class="verdict-rec">
                    Vessel operational draft ({top_v['draft_m']}m) and LOA ({top_v['loa_m']}m) satisfy physical terminal constraints at both <strong>{origin}</strong> (max {origin_max_draft}m draft) and <strong>{destination}</strong> (max {dest_max_draft}m draft{f", max {dest_spec.get('max_vessel_dwt'):,} DWT ceiling" if dest_spec.get('max_vessel_dwt') else ""}). {len(feasible)} of {len(vessels)} evaluated vessel classes are technically viable.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="verdict-banner severe" style="padding: 22px 26px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                    <span class="verdict-badge severe">FEASIBILITY RESTRICTION: NO COMPLIANT SINGLE-VESSEL ALLOCATION</span>
                    <span style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #EF4444;">
                        BERTH CONSTRAINT BREACH
                    </span>
                </div>
                <div style="font-size: 1.30rem; font-weight: 700; color: #EF4444; margin-bottom: 6px;">
                    Cargo Parcel ({cargo_qty:,.0f} MT) Exceeds Port Physical Clearances
                </div>
                <div class="verdict-rec" style="color: #EF4444;">
                    Neither origin loading berths nor destination discharge berths can safely accommodate a single vessel with capacity for {cargo_qty:,.0f} MT within permissible draft, LOA, or beam limits. Recommended mitigation: parcel the shipment across multiple smaller voyages or reassign to an alternative deep-water discharge terminal.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 2. Vessel Class Recommendations Table
        st.markdown('<div class="section-title"><span>Vessel Class Allocation & Port Fit</span><span class="section-subtitle">Ranked by deadweight capacity and physical compliance</span></div>', unsafe_allow_html=True)

        if feasible:
            rows = []
            for v in feasible:
                rows.append({
                    "Vessel Class": v["vessel_class"],
                    "Capacity (DWT)": f"{v['dwt_min']:,} – {v['dwt_max']:,} MT",
                    "Draft / Beam / LOA": f"{v['draft_m']}m / {v.get('beam_m', '-')}m / {v['loa_m']}m",
                    "Sea Days": f"{v.get('sea_days', v.get('voyage_days', '-'))} d",
                    "Berth Days": f"{v.get('berth_days', '-')} d",
                    "Charter Day Rate": f"${v.get('daily_charter_rate', 0):,}/day" if v.get('daily_charter_rate') else "N/A",
                    "Total Voyage Cost": f"${v['total_cost']:,.0f}" if v.get("total_cost") else "N/A",
                    "Freight Rate ($/t)": f"${v.get('rate_per_tonne', 0):.2f}/t ({v.get('rate_index', '')})",
                    "Allocation Status": "FEASIBLE",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # 3. Feasibility Reasons & Infeasible Vessels Expander
        if infeasible:
            with st.expander(f"Review Non-Compliant Vessel Classes ({len(infeasible)})", expanded=(not feasible)):
                for v in infeasible:
                    reasons_str = "; ".join(v.get("reasons", ["Exceeds port constraints"]))
                    st.markdown(f"""
                    <div style="border-left: 3px solid #DC2626; padding: 6px 12px; margin-bottom: 6px; background: rgba(220, 38, 38, 0.08); border: 1px solid rgba(220, 38, 38, 0.25); border-left: 3px solid #DC2626; font-size: 0.85rem; color: var(--text-color, inherit);">
                        <strong>{v['vessel_class']}</strong>: {reasons_str}
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # 4. Navigational Route Map Visual (Pydeck Interactive Maritime Transit Track)
        st.markdown('<div class="section-title"><span>Navigational Route & Maritime Sea Lane</span><span class="section-subtitle">Real maritime corridors bypassing landmasses via international straits & chokepoints</span></div>', unsafe_allow_html=True)

        route_dist = meta.get("route_distance_nm") or 0
        adj_dist = meta.get("route_adjusted_distance_nm") or int(route_dist * 1.10)
        sea_days = meta.get("route_sea_days") or round(adj_dist / (13.0 * 24), 1)

        origin_lat = float(origin_spec.get("lat", 0.0))
        origin_lon = float(origin_spec.get("lon", 0.0))
        dest_lat = float(dest_spec.get("lat", 0.0))
        dest_lon = float(dest_spec.get("lon", 0.0))

        if origin_lat != 0.0 and dest_lat != 0.0:
            try:
                # Build maritime shipping lane waypoints that avoid landmasses
                route_path, chokepoints, corridor_name = get_maritime_route_data(
                    origin, destination, origin_lat, origin_lon, dest_lat, dest_lon
                )

                df_route_path = pd.DataFrame([{
                    "path": route_path,
                    "name": f"{origin} → {destination}",
                    "corridor": corridor_name,
                    "distance": f"{adj_dist:,} nm ({sea_days} Sea Days)",
                }])

                # Terminal ports layer
                df_terminals = pd.DataFrame([
                    {
                        "name": f"Loading Terminal: {origin}",
                        "lat": origin_lat,
                        "lon": origin_lon,
                        "color": [13, 148, 136, 240],
                        "radius": 110000,
                    },
                    {
                        "name": f"Discharge Terminal: {destination}",
                        "lat": dest_lat,
                        "lon": dest_lon,
                        "color": [220, 38, 38, 240],
                        "radius": 110000,
                    }
                ])

                path_layer = pdk.Layer(
                    "PathLayer",
                    data=df_route_path,
                    get_path="path",
                    get_color=[13, 148, 136, 230],
                    width_scale=1,
                    width_min_pixels=3,
                    get_width=5,
                    pickable=True,
                    auto_highlight=True
                )

                terminals_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_terminals,
                    get_position=["lon", "lat"],
                    get_color="color",
                    get_radius="radius",
                    pickable=True,
                    auto_highlight=True
                )

                map_layers = [path_layer, terminals_layer]

                # If navigational chokepoints exist on this route, add waypoint markers
                if chokepoints:
                    df_cp = pd.DataFrame([
                        {
                            "name": cp["name"],
                            "lat": cp["lat"],
                            "lon": cp["lon"],
                            "color": [217, 119, 6, 230],
                            "radius": 65000,
                        }
                        for cp in chokepoints
                    ])
                    cp_layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=df_cp,
                        get_position=["lon", "lat"],
                        get_color="color",
                        get_radius="radius",
                        pickable=True,
                        auto_highlight=True
                    )
                    map_layers.append(cp_layer)

                # Center of map
                center_lat = (origin_lat + dest_lat) / 2
                center_lon = (origin_lon + dest_lon) / 2
                if abs(origin_lon - dest_lon) > 180:
                    center_lon = ((origin_lon + dest_lon + 360) / 2) % 360

                deck = pdk.Deck(
                    layers=map_layers,
                    initial_view_state=pdk.ViewState(
                        latitude=center_lat,
                        longitude=center_lon,
                        zoom=1.7,
                        min_zoom=1,
                        max_zoom=10,
                        pitch=0
                    ),
                    tooltip={"html": "<strong>{name}</strong><br>{distance}"},
                    map_style=None
                )
                st.pydeck_chart(deck, use_container_width=True)

            except Exception as e:
                st.info(f"Route: {origin} ({origin_lat:.2f}N, {origin_lon:.2f}E) → {destination} ({dest_lat:.2f}N, {dest_lon:.2f}E)")

            # Navigational stat strip below map
            n1, n2, n3, n4 = st.columns(4)
            with n1:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Loading Origin</div>
                    <div class="metric-value" style="font-size: 1.10rem;">{origin}</div>
                    <div class="metric-subtext">{origin_lat:.2f}°, {origin_lon:.2f}°</div>
                </div>
                """, unsafe_allow_html=True)
            with n2:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Discharge Port</div>
                    <div class="metric-value" style="font-size: 1.10rem;">{destination}</div>
                    <div class="metric-subtext">{dest_lat:.2f}°, {dest_lon:.2f}°</div>
                </div>
                """, unsafe_allow_html=True)
            with n3:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Route Distance</div>
                    <div class="metric-value" style="font-size: 1.30rem;">{adj_dist:,} nm</div>
                    <div class="metric-subtext">Haversine base: {route_dist:,} nm (1.10x factor)</div>
                </div>
                """, unsafe_allow_html=True)
            with n4:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-label">Laden Sea Transit</div>
                    <div class="metric-value" style="font-size: 1.30rem;">{sea_days} days</div>
                    <div class="metric-subtext">Service speed: 13.0 knots</div>
                </div>
                """, unsafe_allow_html=True)

    # =======================================================================
    # TAB 3: RISK ANALYSIS
    # =======================================================================
    with tab_risk:
        verdict = risk_analysis.get("overall_verdict", "Low")
        verdict_lower = verdict.lower().replace("-", "")
        pct_flagged = risk_analysis.get("pct_days_flagged", 0.0)
        peak_info = risk_analysis.get("peak_volatility", {})
        peak_val = peak_info.get("value", 0.0)
        peak_dt = peak_info.get("date", "N/A")
        first_mod = risk_analysis.get("first_moderate_date") or "None in window"
        trend = risk_analysis.get("volatility_trend", "stable")
        recommendation = risk_analysis.get("recommendation", "Standard contracting terms are appropriate.")
        daily_vol = risk_analysis.get("daily_volatility", [])
        daily_flags = risk_analysis.get("daily_flags", [])

        # Determine composite score and styling
        composite_score = risk_analysis.get("composite_score")
        composite_tier = risk_analysis.get("composite_tier", verdict)
        display_tier = composite_tier if composite_score is not None else verdict
        verdict_lower = display_tier.lower().replace("-", "")

        # Map verdict to CSS style category
        if "severe" in verdict_lower:
            card_cls = "severe"
            spark_color = "#DC2626"
        elif "high" in verdict_lower:
            card_cls = "high"
            spark_color = "#EA580C"
        elif "moderate" in verdict_lower:
            card_cls = "moderate"
            spark_color = "#D97706"
        else:
            card_cls = "low"
            spark_color = "#0D9488"

        vol_spark_vals = [d["volatility_pct"] for d in daily_vol]
        spark_svg = make_sparkline_svg(vol_spark_vals, width=120, height=24, color=spark_color)

        # 1. PRIMARY DECISION-CRITICAL ELEMENT: Risk Verdict Executive Banner
        headline_title = (
            f"COMPOSITE RISK VERDICT: {display_tier.upper()} RISK ({composite_score:.1f}/100)"
            if composite_score is not None
            else f"OVERALL VERDICT: {verdict.upper()} RISK"
        )

        st.markdown(f"""
        <div class="verdict-banner {card_cls}" style="padding: 22px 26px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                <span class="verdict-badge {card_cls}">{headline_title}</span>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 0.74rem; color: var(--text-color, #94A3B8); opacity: 0.85; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;">
                        RATE TRAJECTORY:
                    </span>
                    {spark_svg}
                </div>
            </div>
            <div class="verdict-rec" style="font-size: 1.02rem; font-weight: 500;">{recommendation}</div>
        </div>
        """, unsafe_allow_html=True)

        # 2. Four-Criterion Multi-Dimensional Scorecard Grid
        st.markdown(
            '<div class="section-title"><span>Multi-Criteria Risk Scorecard</span>'
            '<span class="section-subtitle">Weighted composite evaluation across market, seasonal, currency & fleet dimensions</span></div>',
            unsafe_allow_html=True
        )

        crit = risk_analysis.get("criteria", {})
        crit_market = crit.get("market_volatility", {})
        crit_seasonal = crit.get("seasonal_cyclone", {})
        crit_fx = crit.get("currency_fx", {})
        crit_idle = crit.get("idle_utilization", {})

        seasonal_info = risk_analysis.get("seasonal_risk", {})
        fx_info = risk_analysis.get("fx_risk", {})
        idle_info = risk_analysis.get("idle_risk", {})

        def _badge_html(t_label):
            t_str = str(t_label).strip()
            tl = t_str.lower()
            if "severe" in tl:
                return f'<span style="background: rgba(220, 38, 38, 0.15); color: #EF4444; border: 1px solid #DC2626; padding: 2px 8px; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;">{t_str}</span>'
            elif "high" in tl:
                return f'<span style="background: rgba(234, 88, 12, 0.15); color: #F97316; border: 1px solid #EA580C; padding: 2px 8px; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;">{t_str}</span>'
            elif "moderate" in tl:
                return f'<span style="background: rgba(217, 119, 6, 0.15); color: #F59E0B; border: 1px solid #D97706; padding: 2px 8px; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;">{t_str}</span>'
            elif "unavail" in tl or "error" in tl:
                return f'<span style="background: rgba(148, 163, 184, 0.15); color: var(--text-color, #94A3B8); border: 1px solid #64748B; padding: 2px 8px; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;">{t_str}</span>'
            else:
                return f'<span style="background: rgba(13, 148, 136, 0.15); color: #14B8A6; border: 1px solid #0D9488; padding: 2px 8px; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;">{t_str}</span>'

        mc1, mc2, mc3, mc4 = st.columns(4)

        with mc1:
            m_tier = crit_market.get("tier", "Low")
            m_score = crit_market.get("score", 25.0)
            m_weight_eff = crit_market.get("effective_weight", 0.40) * 100.0
            st.markdown(f"""
            <div class="metric-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div class="metric-label" style="margin-bottom: 0;">1. Market Volatility</div>
                    {_badge_html(m_tier)}
                </div>
                <div class="metric-value" style="font-size: 1.35rem;">{m_score:.0f}<span style="font-size: 0.82rem; color: var(--text-color, #94A3B8); opacity: 0.8; font-weight: 500;">/100</span></div>
                <div class="metric-subtext">
                    Weight: <strong>40%</strong> (Active: {m_weight_eff:.1f}%)<br>
                    Peak Volatility: <strong>{peak_val:.1f}%</strong> ({peak_dt})<br>
                    Flagged Days: <strong>{pct_flagged:.0f}%</strong> ({trend.upper()})<br>
                    <span style="font-size: 0.70rem; color: var(--text-color, #94A3B8); opacity: 0.7;">Source: Baltic Dry Index (Prophet)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with mc2:
            s_tier = seasonal_info.get("tier", "Low")
            s_score = seasonal_info.get("score", 25)
            s_weight_eff = crit_seasonal.get("effective_weight", 0.30) * 100.0
            s_state = seasonal_info.get("state", "Odisha")
            s_peak = seasonal_info.get("peak_month_name", "October")
            s_overlap = "Peak Month Overlap" if seasonal_info.get("overlaps_peak") else ("Season Overlap" if seasonal_info.get("overlaps_season") else "Off-Season Window")
            st.markdown(f"""
            <div class="metric-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div class="metric-label" style="margin-bottom: 0;">2. Seasonal / Cyclone</div>
                    {_badge_html(s_tier)}
                </div>
                <div class="metric-value" style="font-size: 1.35rem;">{s_score:.0f}<span style="font-size: 0.82rem; color: var(--text-color, #94A3B8); opacity: 0.8; font-weight: 500;">/100</span></div>
                <div class="metric-subtext">
                    Weight: <strong>30%</strong> (Active: {s_weight_eff:.1f}%)<br>
                    Port State: <strong>{s_state}</strong><br>
                    Peak Landfall: <strong>{s_peak}</strong> ({s_overlap})<br>
                    <span style="font-size: 0.70rem; color: var(--text-color, #94A3B8); opacity: 0.7;">Source: IMD / RSMC New Delhi Climatology</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with mc3:
            fx_status = fx_info.get("status", "available")
            fx_tier = fx_info.get("tier", "Low")
            fx_score = fx_info.get("score")
            fx_weight_eff = crit_fx.get("effective_weight", 0.20) * 100.0
            fx_vol = fx_info.get("rolling_30d_volatility_pct")
            fx_rate = fx_info.get("latest_rate")

            if fx_status == "available" and fx_score is not None:
                fx_badge_str = _badge_html(fx_tier)
                fx_score_str = f"{fx_score:.0f}<span style='font-size: 0.82rem; color: var(--text-color, #94A3B8); opacity: 0.8; font-weight: 500;'>/100</span>"
                fx_vol_str = f"{fx_vol:.2f}% std" if fx_vol is not None else "N/A"
                fx_rate_str = f"₹{fx_rate:.2f}/$" if fx_rate is not None else "N/A"
                fx_sub_str = (
                    f"Weight: <strong>20%</strong> (Active: {fx_weight_eff:.1f}%)<br>"
                    f"30d Daily Vol: <strong>{fx_vol_str}</strong><br>"
                    f"Latest Rate: <strong>{fx_rate_str}</strong><br>"
                    "<span style='font-size: 0.70rem; color: var(--text-color, #94A3B8); opacity: 0.7;'>Source: Frankfurter API (live, central bank rates)</span>"
                )
            else:
                fx_badge_str = _badge_html("DATA UNAVAILABLE")
                fx_score_str = "<span style='font-size: 1.05rem; color: var(--text-color, #94A3B8); opacity: 0.7;'>N/A</span>"
                fx_sub_str = (
                    "Weight: <strong>20% (Reallocated)</strong><br>"
                    "Status: <strong>Live API Unavailable</strong><br>"
                    "Central bank rates unreachable / timed out<br>"
                    "<span style='font-size: 0.70rem; color: var(--text-color, #94A3B8); opacity: 0.7;'>Source: Frankfurter API (live)</span>"
                )

            st.markdown(f"""
            <div class="metric-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div class="metric-label" style="margin-bottom: 0;">3. Currency / FX (USD/INR)</div>
                    {fx_badge_str}
                </div>
                <div class="metric-value" style="font-size: 1.35rem;">{fx_score_str}</div>
                <div class="metric-subtext">{fx_sub_str}</div>
            </div>
            """, unsafe_allow_html=True)

        with mc4:
            i_tier = idle_info.get("tier", "Low")
            i_score = idle_info.get("score", 25.0)
            i_weight_eff = crit_idle.get("effective_weight", 0.10) * 100.0
            i_util = idle_info.get("utilization_pct")
            i_util_str = f"{i_util:.1f}%" if i_util is not None else "N/A"
            st.markdown(f"""
            <div class="metric-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div class="metric-label" style="margin-bottom: 0;">4. Fleet Utilization</div>
                    {_badge_html(i_tier)}
                </div>
                <div class="metric-value" style="font-size: 1.35rem;">{i_score:.0f}<span style="font-size: 0.82rem; color: var(--text-color, #94A3B8); opacity: 0.8; font-weight: 500;'>/100</span></div>
                <div class="metric-subtext">
                    Weight: <strong>10%</strong> (Active: {i_weight_eff:.1f}%)<br>
                    Load Factor: <strong>{i_util_str}</strong> capacity<br>
                    Flags: <strong>{len(idle_flags)}</strong> contract advisory flag(s)<br>
                    <span style="font-size: 0.70rem; color: var(--text-color, #94A3B8); opacity: 0.7;'>Source: Vessel specs & voyage geometry</span>
                </div>
            </div>
            """, unsafe_allow_html=True)



        # 2. Key Actionable Volatility Metrics
        st.markdown('<div class="section-title"><span>Actionable Volatility Metrics</span><span class="section-subtitle">Forward market exposure thresholds and cutoff dates</span></div>', unsafe_allow_html=True)

        rk1, rk2, rk3, rk4 = st.columns(4)
        with rk1:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Peak Volatility</div>
                <div class="metric-value">{peak_val:.1f}%</div>
                <div class="metric-subtext">Peak Date: <strong>{peak_dt}</strong></div>
            </div>
            """, unsafe_allow_html=True)
        with rk2:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Action Cutoff Date</div>
                <div class="metric-value" style="font-size: 1.25rem;">{first_mod}</div>
                <div class="metric-subtext">First day crossing Moderate tier (≥15%)</div>
            </div>
            """, unsafe_allow_html=True)
        with rk3:
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Elevated Volatility Days</div>
                <div class="metric-value">{pct_flagged:.0f}%</div>
                <div class="metric-subtext">{len(daily_flags)} of {len(forecast)} horizon days flagged</div>
            </div>
            """, unsafe_allow_html=True)
        with rk4:
            trend_label = "INCREASING" if trend == "increasing" else ("DECREASING" if trend == "decreasing" else "STABLE")
            st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">Volatility Trend</div>
                <div class="metric-value" style="font-size: 1.25rem;">{trend_label}</div>
                <div class="metric-subtext">Confidence-band width slope</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # 3. Volatility Profile Horizon Chart (Dedicated Curve with 15% Threshold)
        if daily_vol:
            st.markdown('<div class="section-title"><span>Volatility Profile Across Forecast Horizon</span><span class="section-subtitle">Confidence band width as percentage of expected freight rate</span></div>', unsafe_allow_html=True)



            vol_df = pd.DataFrame(daily_vol)
            vol_df["date"] = pd.to_datetime(vol_df["date"])

            try:
                # Volatility curve
                max_vol = float(vol_df["volatility_pct"].max()) if not vol_df.empty else 25.0
                y_max = max(28.0, max_vol + 4.0)

                vol_line = alt.Chart(vol_df).mark_line(color="#0D9488", strokeWidth=2.6).encode(
                    x=alt.X("date:T", title="Forecast Date", axis=alt.Axis(format="%b %d", labelAngle=-30)),
                    y=alt.Y("volatility_pct:Q", title="Uncertainty Spread (% of Freight Rate)", scale=alt.Scale(domain=[0, y_max])),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date", format="%Y-%m-%d"),
                        alt.Tooltip("volatility_pct:Q", title="Volatility Spread (%)", format=".1f"),
                    ]
                )

                # Moderate Risk Threshold (15% benchmark rule)
                thresh_df = pd.DataFrame([{"threshold": 15.0, "label": "Moderate Risk Threshold (15.0%)"}])
                thresh_rule = alt.Chart(thresh_df).mark_rule(
                    color="#D97706", strokeDash=[6, 4], strokeWidth=2.0
                ).encode(
                    y="threshold:Q"
                )

                thresh_text = alt.Chart(thresh_df).mark_text(
                    align="right", baseline="bottom", dx=-10, dy=-6, color="#D97706", fontSize=11, fontWeight="bold"
                ).encode(
                    x=alt.value(720),
                    y="threshold:Q",
                    text="label:N"
                )

                vol_chart = alt.layer(vol_line, thresh_rule, thresh_text).properties(
                    height=280
                ).configure_view(
                    strokeWidth=0
                ).configure_axis(
                    labelFontSize=11, titleFontSize=12, gridColor="rgba(148, 163, 184, 0.15)"
                )

                st.altair_chart(vol_chart, use_container_width=True)

            except Exception:
                fallback_chart_df = vol_df.set_index("date")
                fallback_chart_df["Moderate Threshold (15%)"] = 15.0
                st.line_chart(fallback_chart_df[["volatility_pct", "Moderate Threshold (15%)"]], color=["#0D9488", "#D97706"], use_container_width=True)

        # 4. Contracting Strategy & Fleet Utilization Guidance
        if idle_flags:
            st.markdown('<div class="section-title"><span>Contracting Strategy & Fleet Guidance</span><span class="section-subtitle">Operational chartering terms based on rate momentum & parcel size</span></div>', unsafe_allow_html=True)
            for f in idle_flags:
                f_type = f.get("type", "")
                f_msg = f.get("message", "")
                if f_type == "under_utilization":
                    st.markdown(f"""
                    <div class="custom-callout warning">
                        <strong>CAPACITY UNDER-UTILIZATION:</strong> {f_msg}
                    </div>
                    """, unsafe_allow_html=True)
                elif f_type == "declining_market":
                    st.markdown(f"""
                    <div class="custom-callout info">
                        <strong>DOWNWARD RATE MOMENTUM (COA ADVISORY):</strong> {f_msg}
                    </div>
                    """, unsafe_allow_html=True)
                elif f_type == "rising_market":
                    st.markdown(f"""
                    <div class="custom-callout info">
                        <strong>UPWARD RATE MOMENTUM (SPOT ADVISORY):</strong> {f_msg}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="custom-callout neutral">
                        <strong>STRATEGY ADVISORY:</strong> {f_msg}
                    </div>
                    """, unsafe_allow_html=True)

        # 5. Supplementary Expander: Detailed Day-by-Day Volatility Log
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        with st.expander(f"View Detailed Day-by-Day Volatility Log ({len(daily_flags)} flagged days)", expanded=False):
            if daily_flags:
                flag_rows = []
                for df_item in daily_flags:
                    flag_rows.append({
                        "Date": df_item["date"],
                        "Band Width": f"{df_item['volatility_pct']:.1f}%",
                        "Severity Tier": df_item["tier"].upper(),
                        "Advisory": df_item["message"],
                    })
                st.dataframe(pd.DataFrame(flag_rows), use_container_width=True, hide_index=True)
            else:
                st.write("All forecast dates remain below the 15% volatility threshold.")



if __name__ == "__main__":
    main()
