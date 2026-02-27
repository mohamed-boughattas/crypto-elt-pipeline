"""Dashboard configuration and constants.

This module provides centralized configuration for the Streamlit dashboard,
including constants, theme styles, and settings.
"""

import streamlit as st

# --- DASHBOARD PARAMETERS ---
CACHE_TTL = 3600  # Cache data for 1 hour
DEFAULT_DAYS = 30  # Historical lookback period
MA_PERIOD = 7  # Moving Average window (days)
RSI_PERIOD = 14  # RSI calculation period


# --- PAGE SETTINGS ---
def init_page_config():
    """Initialize Streamlit page configuration."""
    st.set_page_config(
        page_title="Crypto Market Dashboard",
        page_icon="₿",
        layout="wide",
        initial_sidebar_state="expanded",
    )


# --- THEME MANAGEMENT ---
def get_theme_styles() -> str:
    """Generate CSS styles for dark theme."""
    return """
    <style>
    /* Dark Theme */
    [data-testid="collapsedControl"] { display: none; }

    .analysis-box {
        background-color: #1e1e2e;
        border: 1px solid #2d2d3d;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #F7931A;
        margin-bottom: 20px;
    }
    .analysis-box h4 { margin-top: 0; color: #e0e0e0; }
    .bullish { color: #22c55e; font-weight: bold; }
    .bearish { color: #ef4444; font-weight: bold; }

    div[data-testid="stMetric"] {
        background-color: #1e1e2e;
        border: 1px solid #2d2d3d;
        padding: 15px;
        border-radius: 8px;
    }

    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    .title-with-logo { display: flex; align-items: center; gap: 15px; }
    .bitcoin-logo {
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #F7931A 0%, #FFA726 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: bold;
        color: white;
        box-shadow: 0 4px 6px rgba(247, 147, 26, 0.3);
        flex-shrink: 0;
    }
    .dashboard-title { font-size: 2.5rem; font-weight: 600; margin: 0; color: #e0e0e0; }

    .rsi-overbought { color: #ef4444; }
    .rsi-oversold { color: #22c55e; }

    /* Custom metric styling */
    .metric-label { color: #888; font-size: 0.9em; }
    .metric-value { color: #e0e0e0; font-size: 1.5em; font-weight: bold; }
    </style>
    """
