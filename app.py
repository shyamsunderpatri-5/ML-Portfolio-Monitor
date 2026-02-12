"""
🧠 SMART PORTFOLIO MONITOR v6.0 - COMPLETE EDITION
==================================================
"""
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import time
import json
from typing import Tuple, Optional, Dict, List, Any
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import streamlit-autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False
# ============================================================================
# GOOGLE SHEETS API SETUP
# ============================================================================

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False
    st.warning("⚠️ Install gspread: pip install gspread google-auth")

# ✅ FIX: Get credentials from Streamlit Secrets/Environment
credentials = None  # ✅ Initialize to None so it always exists

try:
    if 'GCP_SA_KEY' in os.environ:
        service_account_info = json.loads(os.environ.get('GCP_SA_KEY'))
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
    else:
        st.error("❌ GCP_SA_KEY not found in Environment/Secrets")
except Exception as e:
    st.error(f"❌ Failed to load credentials: {e}")

# ============================================================================
# SAFE UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division that handles zero and NaN"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        return default if pd.isna(result) or np.isinf(result) else result
    except (TypeError, ValueError, ZeroDivisionError, FloatingPointError):
        return default

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        result = float(value)
        return default if pd.isna(result) else result
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logging.warning(f"Error in calculation: {e}")
        return default


def round_to_tick_size(price):
    """
    Round price according to NSE tick size rules:
    - Price >= 1000: Round to 0.05 (₹2500.00, ₹2500.05, ₹2500.10...)
    - Price >= 10: Round to 0.05 (₹500.00, ₹500.05, ₹500.10...)
    - Price >= 1: Round to 0.05 (₹5.00, ₹5.05, ₹5.10...)
    - Price < 1: Round to 0.01 (₹0.20, ₹0.21, ₹0.22... for penny stocks)
    
    Returns: Properly rounded price as float
    """
    if pd.isna(price) or price is None:
        return 0.0
    
    price = float(price)
    
    if price < 0:
        return 0.0
    
    # NSE Tick Size Rules
    if price < 1:
        # Penny stocks: Round to 0.01 (paise level)
        return round(price / 0.01) * 0.01
    else:
        # All other stocks: Round to 0.05
        return round(price / 0.05) * 0.05

# ============================================================================
# PAGE CONFIG (MUST BE FIRST STREAMLIT COMMAND!)
# ============================================================================
st.set_page_config(
    page_title="Smart Portfolio Monitor v6.0",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
<style>
    /* ================================================================
       PROFESSIONAL TRADING TERMINAL THEME
       ================================================================ */
        /* ================================================================
       THEME VARIABLES - Controls Light/Dark mode
       ================================================================ */
    
    /* Dark mode (default) */
    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #0f1419;
        --bg-card: #141c27;
        --border-color: #1e2a3a;
        --text-primary: #e2e8f0;
        --text-secondary: #a0aec0;
        --text-muted: #4a5568;
        --green: #00d4aa;
        --red: #ff4757;
        --yellow: #ffa502;
        --blue: #00b4d8;
        --purple: #7b68ee;
    }
    
    /* Light mode override - activates when Streamlit is in light mode */
    @media (prefers-color-scheme: light) {
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-card: #ffffff;
            --border-color: #e2e8f0;
            --text-primary: #1a202c;
            --text-secondary: #4a5568;
            --text-muted: #718096;
            --green: #22c55e;
            --red: #ef4444;
            --yellow: #f59e0b;
            --blue: #3b82f6;
            --purple: #8b5cf6;
        }
    }
    
    /* Also detect Streamlit's own light theme class */
    [data-testid="stAppViewContainer"][data-theme="light"],
    .stApp[data-theme="light"] {
        --bg-primary: #ffffff;
        --bg-secondary: #f8f9fa;
        --bg-card: #ffffff;
        --border-color: #e2e8f0;
        --text-primary: #1a202c;
        --text-secondary: #4a5568;
        --text-muted: #718096;
    }
    /* ---------- Global Background & Font ---------- */
    .stApp {
        background-color: var(--bg-primary, #0a0e17);
    }
    
    section[data-testid="stSidebar"] {
        background-color: var(--bg-secondary, #0f1419);
        border-right: 1px solid var(--border-color, #1e2a3a);
    }
            
    section[data-testid="stSidebar"] * {
        color: var(--text-secondary, #c8d6e5) !important;
    }
    
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #00d4aa !important;
    }
    
    /* ---------- Typography ---------- */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', 'SF Pro Display', -apple-system, sans-serif !important;
        letter-spacing: -0.02em;
    }
    
    p, span, div, label, td, th {
        font-family: 'Inter', 'SF Pro Text', -apple-system, sans-serif !important;
    }
    
    /* ---------- Main Header ---------- */
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00d4aa 0%, #00b4d8 50%, #7b68ee 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 0.5rem 0;
        letter-spacing: -0.03em;
        margin-bottom: 0;
    }
    
    .sub-header {
        text-align: center;
        color: #4a5568;
        font-size: 0.8rem;
        margin-top: -5px;
        letter-spacing: 0.15em;
        text-transform: uppercase;
    }
    
    /* ---------- Market Status Bar ---------- */
    .market-bar {
        background: linear-gradient(90deg, #0f1419 0%, #141c27 100%);
        border: 1px solid #1e2a3a;
        border-radius: 12px;
        padding: 12px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 10px 0;
    }
    
    .market-bar-item {
        text-align: center;
        padding: 0 15px;
        border-right: 1px solid #1e2a3a;
    }
    
    .market-bar-item:last-child {
        border-right: none;
    }
    
    .market-bar-label {
        font-size: 0.65rem;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 2px;
    }
    
    .market-bar-value {
        font-size: 1rem;
        font-weight: 600;
        color: #e2e8f0;
    }
    
    /* ---------- Health Score Ring ---------- */
    .health-ring {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        font-weight: 800;
        color: white;
        margin: 0 auto;
        position: relative;
    }
    
    /* ---------- Portfolio Summary Cards ---------- */
    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 10px;
        margin: 15px 0;
    }
    
    .summary-card {
        background: linear-gradient(145deg, var(--bg-card, #141c27), var(--bg-secondary, #0f1419));
        border: 1px solid var(--border-color, #1e2a3a);
    .summary-card:hover {
        border-color: #00d4aa;
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 212, 170, 0.1);
    }
    
    .summary-card-label {
        font-size: 0.65rem;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 6px;
    }
    
    .summary-card-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #e2e8f0;
    }
    
    .summary-card-delta {
        font-size: 0.75rem;
        margin-top: 4px;
    }
    
    /* ---------- Position Cards ---------- */
    .position-card {
        background: linear-gradient(145deg, var(--bg-card, #141c27), var(--bg-secondary, #0f1419));
        border: 1px solid var(--border-color, #1e2a3a);
    
    .position-card:hover {
        border-color: #2d3a4a;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    
    .position-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 18px;
        border-bottom: 1px solid #1e2a3a;
    }
    
    .position-ticker {
        font-size: 1.1rem;
        font-weight: 700;
        color: #e2e8f0;
        letter-spacing: 0.02em;
    }
    
    .position-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    
    .badge-long {
        background: rgba(0, 212, 170, 0.15);
        color: #00d4aa;
        border: 1px solid rgba(0, 212, 170, 0.3);
    }
    
    .badge-short {
        background: rgba(255, 107, 107, 0.15);
        color: #ff6b6b;
        border: 1px solid rgba(255, 107, 107, 0.3);
    }
    
    .position-body {
        padding: 14px 18px;
    }
    
    .position-metrics {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
    }
    
    .position-metric {
        text-align: center;
    }
    
    .position-metric-label {
        font-size: 0.6rem;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    
    .position-metric-value {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-top: 2px;
    }
    
    /* ---------- Status Badges ---------- */
    .status-critical {
        background: linear-gradient(135deg, #ff4757, #ff3838);
        color: white;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
        animation: pulse-critical 2s infinite;
    }
    
    @keyframes pulse-critical {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.4); }
        50% { opacity: 0.9; box-shadow: 0 0 0 8px rgba(255, 71, 87, 0); }
    }
    
    .status-warning {
        background: linear-gradient(135deg, #ffa502, #ff9f43);
        color: #1a1a2e;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
    }
    
    .status-success {
        background: linear-gradient(135deg, #00d4aa, #00b894);
        color: #1a1a2e;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
    }
    
    .status-info {
        background: linear-gradient(135deg, #00b4d8, #0096c7);
        color: white;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
    }
    
    .status-neutral {
        background: linear-gradient(135deg, #2d3a4a, #1e2a3a);
        color: #a0aec0;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        display: inline-block;
    }
    
    /* ---------- Alert Boxes ---------- */
    .alert-critical {
        background: linear-gradient(135deg, rgba(255, 71, 87, 0.12), rgba(255, 56, 56, 0.08));
        border: 1px solid rgba(255, 71, 87, 0.3);
        border-left: 4px solid #ff4757;
        color: #ff6b6b;
        padding: 14px 18px;
        border-radius: 8px;
        margin: 8px 0;
        font-size: 0.9rem;
    }
    
    .alert-warning {
        background: linear-gradient(135deg, rgba(255, 165, 2, 0.12), rgba(255, 159, 67, 0.08));
        border: 1px solid rgba(255, 165, 2, 0.3);
        border-left: 4px solid #ffa502;
        color: #ffc048;
        padding: 14px 18px;
        border-radius: 8px;
        margin: 8px 0;
        font-size: 0.9rem;
    }
    
    .alert-success {
        background: linear-gradient(135deg, rgba(0, 212, 170, 0.12), rgba(0, 184, 148, 0.08));
        border: 1px solid rgba(0, 212, 170, 0.3);
        border-left: 4px solid #00d4aa;
        color: #00d4aa;
        padding: 14px 18px;
        border-radius: 8px;
        margin: 8px 0;
        font-size: 0.9rem;
    }
    
    .alert-info {
        background: linear-gradient(135deg, rgba(0, 180, 216, 0.12), rgba(0, 150, 199, 0.08));
        border: 1px solid rgba(0, 180, 216, 0.3);
        border-left: 4px solid #00b4d8;
        color: #48dbfb;
        padding: 14px 18px;
        border-radius: 8px;
        margin: 8px 0;
        font-size: 0.9rem;
    }
    
    /* ---------- Score Gauges ---------- */
    .score-gauge {
        background: var(--bg-secondary, #0f1419);
        border: 1px solid var(--border-color, #1e2a3a);
    
    .score-value {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 4px;
    }
    
    .score-label {
        font-size: 0.65rem;
        color: #4a5568;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    .score-bar {
        height: 4px;
        background: #1e2a3a;
        border-radius: 2px;
        margin-top: 8px;
        overflow: hidden;
    }
    
    .score-bar-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.5s ease;
    }
    
    /* ---------- Level Indicators ---------- */
    .level-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid #1e2a3a;
    }
    
    .level-label {
        font-size: 0.75rem;
        color: #4a5568;
    }
    
    .level-value {
        font-size: 0.85rem;
        font-weight: 600;
        color: #e2e8f0;
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    }
    
    .level-tag {
        font-size: 0.6rem;
        padding: 2px 6px;
        border-radius: 3px;
        font-weight: 600;
    }
    
    /* ---------- P&L Colors ---------- */
    .pnl-positive {
        color: #00d4aa !important;
    }
    
    .pnl-negative {
        color: #ff4757 !important;
    }
    
    .pnl-neutral {
        color: #a0aec0 !important;
    }
    
    /* ---------- Action Buttons ---------- */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.2s ease;
        border: 1px solid #1e2a3a;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00d4aa, #00b894) !important;
        color: #0a0e17 !important;
        border: none !important;
    }
    
    .stButton > button[kind="secondary"] {
        background: #141c27 !important;
        color: #e2e8f0 !important;
        border: 1px solid #2d3a4a !important;
    }
    
    /* ---------- Recommendation Boxes ---------- */
    .rec-exit {
        background: linear-gradient(135deg, rgba(255, 71, 87, 0.2), rgba(255, 56, 56, 0.1));
        border: 1px solid rgba(255, 71, 87, 0.4);
        color: #ff6b6b;
        padding: 12px 18px;
        border-radius: 8px;
        text-align: center;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        margin: 10px 0;
    }
    
    .rec-hold {
        background: linear-gradient(135deg, rgba(0, 180, 216, 0.2), rgba(0, 150, 199, 0.1));
        border: 1px solid rgba(0, 180, 216, 0.4);
        color: #48dbfb;
        padding: 12px 18px;
        border-radius: 8px;
        text-align: center;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        margin: 10px 0;
    }
    
    .rec-profit {
        background: linear-gradient(135deg, rgba(0, 212, 170, 0.2), rgba(0, 184, 148, 0.1));
        border: 1px solid rgba(0, 212, 170, 0.4);
        color: #00d4aa;
        padding: 12px 18px;
        border-radius: 8px;
        text-align: center;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        margin: 10px 0;
    }
    
    .rec-trail {
        background: linear-gradient(135deg, rgba(123, 104, 238, 0.2), rgba(99, 80, 214, 0.1));
        border: 1px solid rgba(123, 104, 238, 0.4);
        color: #9c88ff;
        padding: 12px 18px;
        border-radius: 8px;
        text-align: center;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        margin: 10px 0;
    }
    
    .rec-watch {
        background: linear-gradient(135deg, rgba(255, 165, 2, 0.2), rgba(255, 159, 67, 0.1));
        border: 1px solid rgba(255, 165, 2, 0.4);
        color: #ffc048;
        padding: 12px 18px;
        border-radius: 8px;
        text-align: center;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.05em;
        margin: 10px 0;
    }
    
    /* ---------- Pattern Cards ---------- */
    .pattern-card {
        background: #0f1419;
        border: 1px solid #1e2a3a;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 5px 0;
    }
    
    .pattern-bullish {
        border-left: 3px solid #00d4aa;
    }
    
    .pattern-bearish {
        border-left: 3px solid #ff4757;
    }
    
    /* ---------- Metric Overrides (Streamlit defaults) ---------- */
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: var(--text-primary, #e2e8f0) !important;
    
    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        color: var(--text-muted, #4a5568) !important;
    
    [data-testid="stMetricDelta"] > div {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
    }
    
    /* Positive delta */
    [data-testid="stMetricDelta"] > div[data-testid="stMetricDeltaIcon-Up"] ~ div,
    [data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Up"] {
        color: #00d4aa !important;
        fill: #00d4aa !important;
    }
    
    /* Negative delta */
    [data-testid="stMetricDelta"] > div[data-testid="stMetricDeltaIcon-Down"] ~ div,
    [data-testid="stMetricDelta"] svg[data-testid="stMetricDeltaIcon-Down"] {
        color: #ff4757 !important;
        fill: #ff4757 !important;
    }
    
    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background: var(--bg-secondary, #0f1419);
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: var(--text-muted, #4a5568);
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #00d4aa, #00b894) !important;
        color: #0a0e17 !important;
    }
    
    /* ---------- Expander ---------- */
    .streamlit-expanderHeader {
        background: #0f1419 !important;
        border: 1px solid #1e2a3a !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    
    .streamlit-expanderContent {
        background: #0f1419 !important;
        border: 1px solid #1e2a3a !important;
        border-top: none !important;
    }
    
    /* ---------- Progress Bar ---------- */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #00d4aa, #00b4d8) !important;
    }
    
    /* ---------- Divider ---------- */
    hr {
        border-color: #1e2a3a !important;
        opacity: 0.5;
    }
    
    /* ---------- Data Tables ---------- */
    .stDataFrame {
        border: 1px solid #1e2a3a;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* ---------- Emergency Blink ---------- */
    .emergency-banner {
        background: linear-gradient(135deg, #ff4757, #ff3838);
        color: white;
        padding: 14px 20px;
        border-radius: 10px;
        text-align: center;
        font-weight: 700;
        font-size: 1.1rem;
        letter-spacing: 0.05em;
        animation: emergency-pulse 1.5s infinite;
        margin: 10px 0;
    }
    
    @keyframes emergency-pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.5); }
        50% { opacity: 0.92; box-shadow: 0 0 0 12px rgba(255, 71, 87, 0); }
    }
    
    /* ---------- Scrollbar ---------- */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: #0a0e17;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #2d3a4a;
        border-radius: 3px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #3d4a5a;
    }
    
    /* ---------- Footer ---------- */
    .terminal-footer {
        text-align: center;
        color: #2d3a4a;
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        padding: 20px 0 10px 0;
        border-top: 1px solid #1e2a3a;
        margin-top: 30px;
    }
    
    /* ---------- Responsive ---------- */
    @media (max-width: 768px) {
        .position-metrics {
            grid-template-columns: repeat(2, 1fr);
        }
        .summary-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
            
    /* Light mode overrides for inline-styled HTML elements */
    @media (prefers-color-scheme: light) {
        .position-header, .position-body, .level-row {
            border-color: #e2e8f0 !important;
        }
        
        .position-ticker {
            color: #1a202c !important;
        }
        
        .position-metric-value {
            color: #1a202c !important;
        }
        
        .level-label {
            color: #718096 !important;
        }
        
        .level-value {
            color: #1a202c !important;
        }
        
        .score-label {
            color: #718096 !important;
        }
        
        .summary-card-value {
            color: #1a202c !important;
        }
        
        .summary-card-label {
            color: #718096 !important;
        }
        
        .terminal-footer {
            color: #a0aec0 !important;
            border-color: #e2e8f0 !important;
        }
        
        .pattern-card {
            background: #f8f9fa !important;
            border-color: #e2e8f0 !important;
        }
        
        .position-metric-label {
            color: #718096 !important;
        }
        
        .market-bar-label, .summary-card-delta {
            color: #718096 !important;
        }
    }
</style>
""", unsafe_allow_html=True)
# ============================================================================
# INITIALIZE SESSION STATE
# ============================================================================
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'email_sent_alerts': {},
        'last_email_time': {},
        'email_log': [],
        'trade_history': [],
        'portfolio_values': [],
        'performance_stats': {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0,
            'total_loss': 0
        },
        'drawdown_history': [],
        'peak_portfolio_value': 0,
        'current_drawdown': 0,
        'max_drawdown': 0,
        'partial_exits': {},
        'holding_periods': {},
        'last_api_call': {},
        'api_call_count': 0,
        'correlation_matrix': None,
        'last_correlation_calc': None
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_ist_now():
    """Get current IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    
    if ist_now.weekday() >= 5:
        return False, "WEEKEND", "Markets closed for weekend", "🔴"
    
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return False, "PRE-MARKET", f"Opens at 09:15 IST", "🟡"
    elif current_time > market_close:
        return False, "CLOSED", "Market closed for today", "🔴"
    else:
        return True, "OPEN", f"Closes at 15:30 IST", "🟢"

# ============================================================================
# GAP 1: MARKET HEALTH CHECK (NIFTY + VIX)
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_market_health():
    """
    Analyze NIFTY 50 and India VIX to determine overall market health
    Returns: dict with status, message, color, action, metrics
    """
    try:
        # Get NIFTY 50 data
        nifty = yf.Ticker("^NSEI")
        nifty_df = nifty.history(period="1mo")
        
        if nifty_df.empty:
            return None
        
        nifty_price = float(nifty_df['Close'].iloc[-1])
        nifty_prev = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else nifty_price
        nifty_change = ((nifty_price - nifty_prev) / nifty_prev) * 100
        
        # Calculate NIFTY indicators
        nifty_sma20 = nifty_df['Close'].rolling(20).mean().iloc[-1]
        nifty_sma50 = nifty_df['Close'].rolling(50).mean().iloc[-1] if len(nifty_df) >= 50 else nifty_sma20
        nifty_rsi = calculate_rsi(nifty_df['Close']).iloc[-1]
        
        if pd.isna(nifty_rsi):
            nifty_rsi = 50
        
        # Get India VIX (Volatility Index)
        vix = yf.Ticker("^INDIAVIX")
        vix_df = vix.history(period="5d")
        vix_value = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 15
        
        # Calculate Market Health Score (0-100)
        health_score = 50  # Start neutral
        
        # NIFTY Price vs SMA20 (0-20 points)
        if nifty_price > nifty_sma20:
            health_score += 15
        else:
            health_score -= 15
        
        # NIFTY Price vs SMA50 (0-15 points)
        if nifty_price > nifty_sma50:
            health_score += 10
        else:
            health_score -= 10
        
        # NIFTY RSI (0-20 points)
        if nifty_rsi > 55:
            health_score += 15
        elif nifty_rsi > 45:
            health_score += 5
        elif nifty_rsi < 35:
            health_score -= 15
        elif nifty_rsi < 45:
            health_score -= 10
        
        # VIX Level (0-25 points)
        if vix_value < 12:
            health_score += 20  # Very low volatility = good
        elif vix_value < 15:
            health_score += 10
        elif vix_value > 25:
            health_score -= 20  # High volatility = bad
        elif vix_value > 18:
            health_score -= 10
        
        # NIFTY Trend (SMA20 vs SMA50) (0-20 points)
        if nifty_sma20 > nifty_sma50:
            health_score += 10  # Golden cross
        else:
            health_score -= 10  # Death cross
        
        # Cap between 0-100
        health_score = max(0, min(100, health_score))
        
        # Determine Status
        if health_score >= 70:
            status = "BULLISH"
            color = "#28a745"
            icon = "🟢"
            action = "✅ Good environment for trading"
            sl_adjustment = "NORMAL"
        elif health_score >= 50:
            status = "NEUTRAL"
            color = "#ffc107"
            icon = "🟡"
            action = "⚠️ Be selective with new positions"
            sl_adjustment = "NORMAL"
        elif health_score >= 30:
            status = "WEAK"
            color = "#fd7e14"
            icon = "🟠"
            action = "⚠️ Tighten stop losses, avoid new longs"
            sl_adjustment = "TIGHTEN"
        else:
            status = "BEARISH"
            color = "#dc3545"
            icon = "🔴"
            action = "🚨 HIGH RISK - Consider reducing exposure"
            sl_adjustment = "AGGRESSIVE"
        
        # Build message
        message = f"NIFTY: ₹{nifty_price:,.0f} ({nifty_change:+.2f}%) | RSI: {nifty_rsi:.0f} | VIX: {vix_value:.1f}"
        
        return {
            'status': status,
            'health_score': health_score,
            'message': message,
            'color': color,
            'icon': icon,
            'action': action,
            'sl_adjustment': sl_adjustment,
            'nifty_price': nifty_price,
            'nifty_change': nifty_change,
            'nifty_rsi': nifty_rsi,
            'nifty_sma20': nifty_sma20,
            'nifty_sma50': nifty_sma50,
            'vix': vix_value,
            'above_sma20': nifty_price > nifty_sma20,
            'above_sma50': nifty_price > nifty_sma50
        }
    
    except Exception as e:
        logger.error(f"Market health check failed: {e}")
        return None
# ============================================================================
# GAP 2: EMERGENCY EXIT DETECTOR
# ============================================================================

def detect_emergency_exit(result, market_health):
    """
    Detect critical exit conditions that override normal analysis
    Returns: (is_emergency, reasons, urgency_level)
    """
    emergency = False
    reasons = []
    urgency = "NORMAL"
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 1: Market Crash + Losing Position
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if market_health and market_health['status'] in ['BEARISH', 'WEAK']:
        if result['pnl_percent'] < -2:
            emergency = True
            urgency = "CRITICAL"
            reasons.append(f"🚨 Market {market_health['status']} + Position down {result['pnl_percent']:.1f}%")
        elif result['pnl_percent'] < 0:
            urgency = "HIGH"
            reasons.append(f"⚠️ Weak market + Position negative ({result['pnl_percent']:.1f}%)")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 2: Gap Down Below SL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if result['position_type'] == 'LONG':
        if result['day_low'] < result['stop_loss'] * 0.98:
            emergency = True
            urgency = "CRITICAL"
            reasons.append(f"🚨 Gap down: Day low ₹{result['day_low']:.2f} below SL ₹{result['stop_loss']:.2f}")
    else:  # SHORT
        if result['day_high'] > result['stop_loss'] * 1.02:
            emergency = True
            urgency = "CRITICAL"
            reasons.append(f"🚨 Gap up: Day high ₹{result['day_high']:.2f} above SL ₹{result['stop_loss']:.2f}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 3: VIX Spike + High SL Risk
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if market_health and market_health['vix'] > 25:
        if result['sl_risk'] > 60:
            emergency = True
            urgency = "CRITICAL"
            reasons.append(f"🚨 VIX spike ({market_health['vix']:.1f}) + SL Risk {result['sl_risk']}%")
        elif result['sl_risk'] > 50:
            urgency = "HIGH"
            reasons.append(f"⚠️ High VIX ({market_health['vix']:.1f}) + SL Risk {result['sl_risk']}%")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 4: Heavy Selling Volume + Negative
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if result['position_type'] == 'LONG':
        if result['volume_signal'] in ['STRONG_SELLING', 'SELLING']:
            if result['volume_ratio'] > 2.5 and result['pnl_percent'] < -1:
                emergency = True
                urgency = "HIGH"
                reasons.append(f"⚠️ Heavy selling volume ({result['volume_ratio']:.1f}x) + Position down")
    else:  # SHORT
        if result['volume_signal'] in ['STRONG_BUYING', 'BUYING']:
            if result['volume_ratio'] > 2.5 and result['pnl_percent'] < -1:
                emergency = True
                urgency = "HIGH"
                reasons.append(f"⚠️ Heavy buying volume ({result['volume_ratio']:.1f}x) + Position down")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 5: All Timeframes Against Position
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if result['mtf_alignment'] < 20 and result['sl_risk'] > 50:
        emergency = True
        urgency = "HIGH"
        reasons.append(f"⚠️ All timeframes against position (MTF: {result['mtf_alignment']}%)")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EMERGENCY CONDITION 6: Breakdown Below Support with Volume
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if result['position_type'] == 'LONG':
        if result['current_price'] < result['support'] * 0.99:
            if result['volume_ratio'] > 1.5:
                emergency = True
                urgency = "HIGH"
                reasons.append(f"⚠️ Breakdown below support ₹{result['support']:.2f} with volume")
    else:  # SHORT
        if result['current_price'] > result['resistance'] * 1.01:
            if result['volume_ratio'] > 1.5:
                emergency = True
                urgency = "HIGH"
                reasons.append(f"⚠️ Breakout above resistance ₹{result['resistance']:.2f} with volume")
    
    return emergency, reasons, urgency    

# ============================================================================
# GAP 3: STOCK-SPECIFIC WIN RATE ANALYSIS
# ============================================================================

def get_stock_performance_history(ticker):
    """
    Analyze historical performance for specific stock
    Returns: dict with win_rate, trade_count, avg_win, avg_loss, recommendation
    """
    # Get trades for this ticker
    stock_trades = [t for t in st.session_state.trade_history if t['ticker'] == ticker]
    
    if len(stock_trades) < 3:
        return {
            'has_history': False,
            'trade_count': len(stock_trades),
            'message': f"Only {len(stock_trades)} trade(s) logged - need 3+ for analysis"
        }
    
    # Calculate statistics
    total_trades = len(stock_trades)
    wins = sum(1 for t in stock_trades if t['win'])
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100
    
    winning_trades = [t for t in stock_trades if t['win']]
    losing_trades = [t for t in stock_trades if not t['win']]
    
    avg_win = sum(t['pnl'] for t in winning_trades) / max(wins, 1)
    avg_loss = sum(abs(t['pnl']) for t in losing_trades) / max(losses, 1)
    
    # Calculate expectancy
    expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
    
    # Profit factor
    total_profit = sum(t['pnl'] for t in winning_trades)
    total_loss = sum(abs(t['pnl']) for t in losing_trades)
    profit_factor = total_profit / max(total_loss, 1)
    
    # Determine recommendation
    if win_rate < 30:
        quality = "POOR"
        color = "#dc3545"
        icon = "🔴"
        recommendation = "⚠️ AVOID - Very low win rate"
    elif win_rate < 40:
        quality = "WEAK"
        color = "#fd7e14"
        icon = "🟠"
        recommendation = "⚠️ CAUTION - Below average performance"
    elif win_rate < 50:
        quality = "AVERAGE"
        color = "#ffc107"
        icon = "🟡"
        recommendation = "ℹ️ Acceptable - Monitor closely"
    elif win_rate < 60:
        quality = "GOOD"
        color = "#28a745"
        icon = "🟢"
        recommendation = "✅ Good track record"
    else:
        quality = "EXCELLENT"
        color = "#20c997"
        icon = "💚"
        recommendation = "✅ Excellent performance!"
    
    # Check expectancy
    if expectancy < 0:
        recommendation = "🚨 NEGATIVE EXPECTANCY - Stop trading this stock!"
        quality = "LOSING"
        color = "#dc3545"
    
    return {
        'has_history': True,
        'trade_count': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'expectancy': expectancy,
        'profit_factor': profit_factor,
        'quality': quality,
        'color': color,
        'icon': icon,
        'recommendation': recommendation
    }

# ============================================================================
# GAP 4: CHART PATTERN DETECTION
# ============================================================================

def detect_chart_patterns(df, current_price):
    """
    Detect common chart patterns
    Returns: list of detected patterns with signals
    """
    patterns = []
    
    if len(df) < 30:
        return patterns
    
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 1: DOUBLE TOP (Bearish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    last_30 = df.tail(30)
    highs_30 = last_30['High']
    
    # Find two highest peaks
    sorted_highs = highs_30.nlargest(5)
    if len(sorted_highs) >= 2:
        peak1 = sorted_highs.iloc[0]
        peak2 = sorted_highs.iloc[1]
        
        # Check if peaks are similar (within 2%)
        if abs(peak1 - peak2) / peak1 < 0.02:
            # Check if current price is below peaks
            if current_price < peak1 * 0.98:
                patterns.append({
                    'name': 'DOUBLE TOP',
                    'signal': 'BEARISH',
                    'strength': 'HIGH',
                    'icon': '📉',
                    'description': f'Resistance at ₹{peak1:.2f} tested twice',
                    'action': 'Watch for breakdown - potential reversal'
                })
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 2: DOUBLE BOTTOM (Bullish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    lows_30 = last_30['Low']
    sorted_lows = lows_30.nsmallest(5)
    
    if len(sorted_lows) >= 2:
        bottom1 = sorted_lows.iloc[0]
        bottom2 = sorted_lows.iloc[1]
        
        if abs(bottom1 - bottom2) / bottom1 < 0.02:
            if current_price > bottom1 * 1.02:
                patterns.append({
                    'name': 'DOUBLE BOTTOM',
                    'signal': 'BULLISH',
                    'strength': 'HIGH',
                    'icon': '📈',
                    'description': f'Support at ₹{bottom1:.2f} held twice',
                    'action': 'Watch for breakout - potential reversal'
                })
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 3: BULLISH ENGULFING (Bullish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if len(df) >= 2:
        prev_candle = df.iloc[-2]
        curr_candle = df.iloc[-1]
        
        # Previous red, current green, and current engulfs previous
        if (prev_candle['Close'] < prev_candle['Open'] and
            curr_candle['Close'] > curr_candle['Open'] and
            curr_candle['Open'] < prev_candle['Close'] and
            curr_candle['Close'] > prev_candle['Open']):
            
            patterns.append({
                'name': 'BULLISH ENGULFING',
                'signal': 'BULLISH',
                'strength': 'MEDIUM',
                'icon': '🟢',
                'description': 'Strong reversal candle pattern',
                'action': 'Potential upward momentum'
            })
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 4: BEARISH ENGULFING (Bearish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if len(df) >= 2:
        prev_candle = df.iloc[-2]
        curr_candle = df.iloc[-1]
        
        if (prev_candle['Close'] > prev_candle['Open'] and
            curr_candle['Close'] < curr_candle['Open'] and
            curr_candle['Open'] > prev_candle['Close'] and
            curr_candle['Close'] < prev_candle['Open']):
            
            patterns.append({
                'name': 'BEARISH ENGULFING',
                'signal': 'BEARISH',
                'strength': 'MEDIUM',
                'icon': '🔴',
                'description': 'Strong reversal candle pattern',
                'action': 'Potential downward momentum'
            })
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 5: ASCENDING TRIANGLE (Bullish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if len(df) >= 20:
        last_20 = df.tail(20)
        
        # Check if highs are flat (resistance)
        highs_20 = last_20['High']
        high_max = highs_20.max()
        high_std = highs_20.std()
        
        # Check if lows are rising
        lows_20 = last_20['Low']
        low_trend = lows_20.iloc[-5:].mean() > lows_20.iloc[:5].mean()
        
        if high_std / high_max < 0.015 and low_trend:  # Flat top + rising lows
            patterns.append({
                'name': 'ASCENDING TRIANGLE',
                'signal': 'BULLISH',
                'strength': 'HIGH',
                'icon': '📐',
                'description': f'Breakout potential above ₹{high_max:.2f}',
                'action': 'Watch for volume spike on breakout'
            })
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PATTERN 6: DESCENDING TRIANGLE (Bearish)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if len(df) >= 20:
        last_20 = df.tail(20)
        
        # Check if lows are flat (support)
        lows_20 = last_20['Low']
        low_min = lows_20.min()
        low_std = lows_20.std()
        
        # Check if highs are falling
        highs_20 = last_20['High']
        high_trend = highs_20.iloc[-5:].mean() < highs_20.iloc[:5].mean()
        
        if low_std / low_min < 0.015 and high_trend:  # Flat bottom + falling highs
            patterns.append({
                'name': 'DESCENDING TRIANGLE',
                'signal': 'BEARISH',
                'strength': 'HIGH',
                'icon': '📐',
                'description': f'Breakdown potential below ₹{low_min:.2f}',
                'action': 'Watch for volume spike on breakdown'
            })
    
    return patterns

def send_email_alert(subject, html_content, sender, password, recipient):
    """
    Send email alert - Returns (success, message)
    """
    if not sender or not password or not recipient:
        log_email("❌ Missing email credentials")
        return False, "Missing email credentials"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)  # ✅ Add timeout
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        
        log_email(f"✅ Email sent: {subject}")  # ✅ Add logging
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError:
        log_email("❌ SMTP Authentication failed")
        return False, "Authentication failed - check App Password"
    except smtplib.SMTPRecipientsRefused:
        log_email("❌ Invalid recipient email")
        return False, "Invalid recipient email address"
    except smtplib.SMTPException as e:
        log_email(f"❌ SMTP error: {str(e)}")
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        log_email(f"❌ Email failed: {str(e)}")
        return False, f"Email failed: {str(e)}"
    

def log_email(message):
    """Add to email log"""
    timestamp = get_ist_now().strftime("%H:%M:%S")
    st.session_state.email_log.append(f"[{timestamp}] {message}")
    if len(st.session_state.email_log) > 50:
        st.session_state.email_log = st.session_state.email_log[-50:]

def generate_alert_hash(ticker, alert_type, key_value=""):
    """Generate unique hash for an alert"""
    alert_string = f"{ticker}_{alert_type}_{key_value}_{get_ist_now().strftime('%Y%m%d')}"
    return hashlib.md5(alert_string.encode()).hexdigest()[:12]


def can_send_email(alert_hash, cooldown_minutes=15):
    """
    Check if enough time has passed since last email
    """
    if alert_hash not in st.session_state.last_email_time:
        return True
    
    last_sent = st.session_state.last_email_time[alert_hash]
    now = datetime.now()  # ✅ Use simple datetime
    
    try:
        # ✅ Handle timezone issues properly
        if isinstance(last_sent, datetime):
            # Remove timezone info for comparison
            if last_sent.tzinfo is not None:
                last_sent = last_sent.replace(tzinfo=None)
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
            
            time_diff = (now - last_sent).total_seconds() / 60.0
        else:
            # Invalid last_sent, allow email
            return True
        
        # ✅ Debug log
        if time_diff < cooldown_minutes:
            logger.info(f"Email cooldown: {time_diff:.1f}/{cooldown_minutes} min for {alert_hash}")
        
        return time_diff >= cooldown_minutes
    
    except Exception as e:
        logger.error(f"Email cooldown check failed: {e}")
        return True  # Allow email on error
    

def mark_email_sent(alert_hash):
    """Mark an alert as sent"""
    st.session_state.last_email_time[alert_hash] = datetime.now()  # ✅ Use datetime.now()
    st.session_state.email_sent_alerts[alert_hash] = True
    logger.info(f"Email marked sent: {alert_hash} at {datetime.now().strftime('%H:%M:%S')}")

MAX_TRADE_HISTORY = 500
def log_trade(ticker, entry_price, exit_price, quantity, position_type, exit_reason):
    """Log completed trade"""
    if position_type == "LONG":
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        pnl = (entry_price - exit_price) * quantity
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
    
    trade = {
        'timestamp': get_ist_now(),
        'ticker': ticker,
        'type': position_type,
        'entry': entry_price,
        'exit': exit_price,
        'quantity': quantity,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'reason': exit_reason,
        'win': pnl > 0
    }
    
    st.session_state.trade_history.append(trade)
    if len(st.session_state.trade_history) > MAX_TRADE_HISTORY:
        st.session_state.trade_history = st.session_state.trade_history[-MAX_TRADE_HISTORY:]
    
    # Update stats
    stats = st.session_state.performance_stats
    stats['total_trades'] += 1
    
    if pnl > 0:
        stats['wins'] += 1
        stats['total_profit'] += pnl
    else:
        stats['losses'] += 1
        stats['total_loss'] += abs(pnl)

def get_performance_stats():
    """Calculate performance statistics"""
    stats = st.session_state.performance_stats
    history = st.session_state.trade_history
    
    if stats['total_trades'] == 0:
        return None
    
    win_rate = (stats['wins'] / stats['total_trades'] * 100)
    avg_win = stats['total_profit'] / stats['wins'] if stats['wins'] > 0 else 0
    avg_loss = stats['total_loss'] / stats['losses'] if stats['losses'] > 0 else 0
    
    expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
    profit_factor = stats['total_profit'] / stats['total_loss'] if stats['total_loss'] > 0 else float('inf')
    
    return {
        'total_trades': stats['total_trades'],
        'wins': stats['wins'],
        'losses': stats['losses'],
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'expectancy': expectancy,
        'profit_factor': profit_factor,
        'net_profit': stats['total_profit'] - stats['total_loss']
    }

def update_drawdown(current_portfolio_value):
    """Update drawdown tracking"""
    if current_portfolio_value > st.session_state.peak_portfolio_value:
        st.session_state.peak_portfolio_value = current_portfolio_value
    
    if st.session_state.peak_portfolio_value > 0:
        drawdown = ((st.session_state.peak_portfolio_value - current_portfolio_value) / 
                   st.session_state.peak_portfolio_value) * 100
        st.session_state.current_drawdown = drawdown
        
        if drawdown > st.session_state.max_drawdown:
            st.session_state.max_drawdown = drawdown
        
        # Store history
        st.session_state.drawdown_history.append({
            'timestamp': get_ist_now(),
            'value': current_portfolio_value,
            'drawdown': drawdown
        })
        
        # Keep last 1000 records
        if len(st.session_state.drawdown_history) > 1000:
            st.session_state.drawdown_history = st.session_state.drawdown_history[-1000:]

def rate_limited_api_call(ticker, min_interval=1.0):
    """Ensure minimum interval between API calls"""
    current_time = time.time()
    
    if ticker in st.session_state.last_api_call:
        elapsed = current_time - st.session_state.last_api_call[ticker]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    
    st.session_state.last_api_call[ticker] = time.time()
    st.session_state.api_call_count += 1
    return True

def get_stock_data_safe(ticker, period="6mo"):
    """Safely fetch stock data with rate limiting"""
    symbol = ticker if '.NS' in str(ticker) or '.BO' in str(ticker) else f"{ticker}.NS"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            rate_limited_api_call(symbol)
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            if not df.empty:
                df.reset_index(inplace=True)
                return df
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            logger.error(f"API Error for {ticker}: {str(e)}")
            log_email(f"API Error for {ticker}: {str(e)}")
    
    return None

def calculate_holding_period(entry_date):
    """Calculate holding period in days with multiple format support"""
    if entry_date is None or entry_date == '' or (isinstance(entry_date, float) and pd.isna(entry_date)):
        return 0
    
    if isinstance(entry_date, str):
        entry_date = entry_date.strip()
        
        # Try multiple date formats
        formats_to_try = [
            "%Y-%m-%d",
            "%d-%m-%Y", 
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d %b %Y",
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
        ]
        
        parsed = None
        for fmt in formats_to_try:
            try:
                parsed = datetime.strptime(entry_date, fmt)
                break
            except ValueError:
                continue
        
        if parsed is None:
            log_email(f"Could not parse entry date: {entry_date}")
            return 0
        
        entry_date = parsed
    
    # Handle pandas Timestamp
    if hasattr(entry_date, 'to_pydatetime'):
        entry_date = entry_date.to_pydatetime()
    
    if isinstance(entry_date, datetime):
        now = get_ist_now()
        try:
            # Handle timezone-aware and naive datetime
            if entry_date.tzinfo is not None:
                delta = now - entry_date
            else:
                delta = now.replace(tzinfo=None) - entry_date
            return max(0, delta.days)
        except (TypeError, ValueError, AttributeError):
             return 0
    
    return 0

def get_tax_implication(holding_days, pnl):
    """Get tax implication based on holding period"""
    if pnl <= 0:
        return "Loss - Can be set off", "🟢"
    
    if holding_days >= 365:
        # LTCG - 10% above 1 lakh
        return "LTCG (10% above ₹1L)", "🟢"
    else:
        # STCG - 15%
        return "STCG (15%)", "🟡"

# ============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing method"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Use Wilder's smoothing (EWM with alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # Handle division by zero
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(
    prices: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD (Moving Average Convergence Divergence)"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_atr(high, low, close, period=14):
    """Calculate ATR using Wilder's smoothing"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Use Wilder's smoothing
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_sma(prices, period):
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean()

def calculate_adx(high, low, close, period=14):
    """Calculate ADX correctly"""
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high - high.shift()
    down_move = low.shift() - low  # ✅ FIXED
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Wilder's smoothing
    alpha = 1/period
    atr = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean() / atr
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    return adx

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    EPSILON = np.finfo(float).eps
    k = 100 * (close - lowest_low) / (highest_high - lowest_low + EPSILON)
    d = k.rolling(window=d_period).mean()
    
    return k, d

# ============================================================================
# VOLUME ANALYSIS
# ============================================================================

def analyze_volume(df):
    """
    Analyze volume to confirm price movements
    Returns: volume_signal, volume_ratio, description, volume_trend
    """
    if 'Volume' not in df.columns or len(df) < 20:
        return "NEUTRAL", 1.0, "Volume data not available", "NEUTRAL"
    
    if df['Volume'].iloc[-1] == 0:
        return "NEUTRAL", 1.0, "No volume data", "NEUTRAL"
    
    # Calculate average volume (20-day)
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    # Get price direction
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    # Volume trend (is volume increasing?)
    vol_5d = df['Volume'].tail(5).mean()
    vol_20d = df['Volume'].tail(20).mean()
    volume_trend = "INCREASING" if vol_5d > vol_20d else "DECREASING"
    
    # Determine signal
    if price_change > 0 and volume_ratio > 1.5:
        signal = "STRONG_BUYING"
        desc = f"Strong buying pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change > 0 and volume_ratio > 1.0:
        signal = "BUYING"
        desc = f"Buying with good volume ({volume_ratio:.1f}x)"
    elif price_change > 0 and volume_ratio < 0.7:
        signal = "WEAK_BUYING"
        desc = f"Weak rally, low volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.5:
        signal = "STRONG_SELLING"
        desc = f"Strong selling pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change < 0 and volume_ratio > 1.0:
        signal = "SELLING"
        desc = f"Selling with volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio < 0.7:
        signal = "WEAK_SELLING"
        desc = f"Weak decline, low volume ({volume_ratio:.1f}x)"
    else:
        signal = "NEUTRAL"
        desc = f"Normal volume ({volume_ratio:.1f}x)"
    
    return signal, volume_ratio, desc, volume_trend

# ============================================================================
# SUPPORT/RESISTANCE DETECTION
# ============================================================================

def find_support_resistance(df, lookback=60):
    """
    Find key support and resistance levels using multiple methods.
    Uses pivot points, volume profile, and clustering.
    """
    if len(df) < lookback:
        lookback = len(df)
    
    if lookback < 10:
        current_price = df['Close'].iloc[-1]
        return {
            'support_levels': [],
            'resistance_levels': [],
            'nearest_support': current_price * 0.95,
            'nearest_resistance': current_price * 1.05,
            'distance_to_support': 5.0,
            'distance_to_resistance': 5.0,
            'support_strength': 'WEAK',
            'resistance_strength': 'WEAK',
            'support_touches': 0,
            'resistance_touches': 0,
            'psychological_levels': []
        }
    
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    close = df['Close'].tail(lookback)
    volume = df['Volume'].tail(lookback) if 'Volume' in df.columns else None
    current_price = float(close.iloc[-1])
    
    # METHOD 1: PIVOT POINTS
    pivot_highs = []
    pivot_lows = []
    
    for i in range(3, len(high) - 3):
        # Pivot high
        if (high.iloc[i] >= high.iloc[i-1] and high.iloc[i] >= high.iloc[i-2] and
            high.iloc[i] >= high.iloc[i-3] and high.iloc[i] >= high.iloc[i+1] and
            high.iloc[i] >= high.iloc[i+2] and high.iloc[i] >= high.iloc[i+3]):
            
            vol_weight = 1.0
            if volume is not None and volume.iloc[i] > volume.mean():
                vol_weight = 1.5
            
            pivot_highs.append({
                'price': float(high.iloc[i]),
                'index': i,
                'weight': vol_weight
            })
        
        # Pivot low
        if (low.iloc[i] <= low.iloc[i-1] and low.iloc[i] <= low.iloc[i-2] and
            low.iloc[i] <= low.iloc[i-3] and low.iloc[i] <= low.iloc[i+1] and
            low.iloc[i] <= low.iloc[i+2] and low.iloc[i] <= low.iloc[i+3]):
            
            vol_weight = 1.0
            if volume is not None and volume.iloc[i] > volume.mean():
                vol_weight = 1.5
            
            pivot_lows.append({
                'price': float(low.iloc[i]),
                'index': i,
                'weight': vol_weight
            })
    
    # METHOD 2: CLUSTER NEARBY LEVELS
    def cluster_levels(pivots, threshold_pct=1.5):
        """Cluster nearby pivot points and calculate strength."""
        if not pivots:
            return []
        
        sorted_pivots = sorted(pivots, key=lambda x: x['price'])
        clusters = []
        current_cluster = [sorted_pivots[0]]
        
        for pivot in sorted_pivots[1:]:
            cluster_center = sum(p['price'] for p in current_cluster) / len(current_cluster)
            if (pivot['price'] - cluster_center) / cluster_center * 100 < threshold_pct:
                current_cluster.append(pivot)
            else:
                avg_price = sum(p['price'] * p['weight'] for p in current_cluster) / sum(p['weight'] for p in current_cluster)
                total_weight = sum(p['weight'] for p in current_cluster)
                touch_count = len(current_cluster)
                
                clusters.append({
                    'price': avg_price,
                    'touches': touch_count,
                    'weight': total_weight,
                    'strength': 'STRONG' if touch_count >= 3 else 'MODERATE' if touch_count >= 2 else 'WEAK'
                })
                
                current_cluster = [pivot]
        
        # Last cluster
        if current_cluster:
            avg_price = sum(p['price'] * p['weight'] for p in current_cluster) / sum(p['weight'] for p in current_cluster)
            total_weight = sum(p['weight'] for p in current_cluster)
            touch_count = len(current_cluster)
            
            clusters.append({
                'price': avg_price,
                'touches': touch_count,
                'weight': total_weight,
                'strength': 'STRONG' if touch_count >= 3 else 'MODERATE' if touch_count >= 2 else 'WEAK'
            })
        
        return clusters
    
    support_clusters = cluster_levels(pivot_lows)
    resistance_clusters = cluster_levels(pivot_highs)
    
    # Find nearest support
    supports_below = [s for s in support_clusters if s['price'] < current_price]
    if supports_below:
        nearest_support_data = max(supports_below, key=lambda x: x['price'])
        nearest_support = nearest_support_data['price']
        support_strength = nearest_support_data['strength']
        support_touches = nearest_support_data['touches']
    else:
        nearest_support = float(low.min()) * 0.99
        support_strength = 'WEAK'
        support_touches = 0
    
    # Find nearest resistance
    resistances_above = [r for r in resistance_clusters if r['price'] > current_price]
    if resistances_above:
        nearest_resistance_data = min(resistances_above, key=lambda x: x['price'])
        nearest_resistance = nearest_resistance_data['price']
        resistance_strength = nearest_resistance_data['strength']
        resistance_touches = nearest_resistance_data['touches']
    else:
        nearest_resistance = float(high.max()) * 1.01
        resistance_strength = 'WEAK'
        resistance_touches = 0
    
    # METHOD 3: PSYCHOLOGICAL LEVELS (Round Numbers)
    def find_round_numbers(price, range_pct=5):
        levels = []
        magnitude = 10 ** (len(str(int(price))) - 2)
        base = int(price / magnitude) * magnitude
        
        for offset in range(-3, 4):
            level = base + (offset * magnitude)
            if abs(level - price) / price * 100 < range_pct:
                levels.append(level)
        
        half_magnitude = magnitude / 2
        for offset in range(-5, 6):
            level = base + (offset * half_magnitude)
            if abs(level - price) / price * 100 < range_pct:
                if level not in levels:
                    levels.append(level)
        
        return sorted(levels)
    
    psychological_levels = find_round_numbers(current_price)
    
    # Calculate distances
    distance_to_support = ((current_price - nearest_support) / current_price) * 100
    distance_to_resistance = ((nearest_resistance - current_price) / current_price) * 100
    
    return {
        'support_levels': [s['price'] for s in support_clusters[-5:]],
        'resistance_levels': [r['price'] for r in resistance_clusters[-5:]],
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'distance_to_support': distance_to_support,
        'distance_to_resistance': distance_to_resistance,
        'support_strength': support_strength,
        'resistance_strength': resistance_strength,
        'support_touches': support_touches,
        'resistance_touches': resistance_touches,
        'psychological_levels': psychological_levels
    }

# ============================================================================
# MOMENTUM SCORING (0-100)
# ============================================================================

def calculate_momentum_score(df):
    """
    Calculate comprehensive momentum score (0-100)
    Higher = More bullish, Lower = More bearish
    """
    close = df['Close']
    score = 50  # Start neutral
    components = {}
    
    # RSI Component (0-20 points)
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if rsi > 70:
        rsi_score = -10  # Overbought
    elif rsi > 60:
        rsi_score = 15
    elif rsi > 50:
        rsi_score = 10
    elif rsi > 40:
        rsi_score = -5
    elif rsi > 30:
        rsi_score = -15
    else:
        rsi_score = 10  # Oversold bounce
    
    score += rsi_score
    components['RSI'] = rsi_score
    
    # MACD Component (0-20 points)
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if hist_current > 0:
        if hist_current > hist_prev:
            macd_score = 20
        else:
            macd_score = 10
    else:
        if hist_current < hist_prev:
            macd_score = -20
        else:
            macd_score = -10
    
    score += macd_score
    components['MACD'] = macd_score
    
    # Moving Average Component (0-20 points)
    current_price = close.iloc[-1]
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    ma_score = 0
    if current_price > ema_9:
        ma_score += 5
    if current_price > sma_20:
        ma_score += 5
    if current_price > sma_50:
        ma_score += 5
    if sma_20 > sma_50:
        ma_score += 5
    
    if current_price < ema_9:
        ma_score -= 5
    if current_price < sma_20:
        ma_score -= 5
    if current_price < sma_50:
        ma_score -= 5
    if sma_20 < sma_50:
        ma_score -= 5
    
    score += ma_score
    components['MA'] = ma_score
    
    # Price Momentum (0-15 points)
    returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
    momentum_score = min(15, max(-15, returns_5d * 3))
    score += momentum_score
    components['Momentum'] = momentum_score
    
    # Trend Strength (0-10 points)
    if sma_50 != 0:
        adx_approx = safe_divide(abs(sma_20 - sma_50), sma_50, 0) * 100
    else:
        adx_approx = 0
    
    if current_price > sma_20:
        trend_score = min(10, adx_approx * 2)
    else:
        trend_score = -min(10, adx_approx * 2)
    
    score += trend_score
    components['Trend'] = trend_score
    
    # Cap between 0-100
    final_score = max(0, min(100, score))
    
    # Determine trend direction
    if final_score >= 70:
        trend = "STRONG BULLISH"
    elif final_score >= 55:
        trend = "BULLISH"
    elif final_score >= 45:
        trend = "NEUTRAL"
    elif final_score >= 30:
        trend = "BEARISH"
    else:
        trend = "STRONG BEARISH"
    
    return final_score, trend, components

# ============================================================================
# MULTI-TIMEFRAME ANALYSIS
# ============================================================================

def multi_timeframe_analysis(ticker, position_type):
    """Analyze multiple timeframes with rate limiting."""
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    
    try:
        rate_limited_api_call(symbol)
        stock = yf.Ticker(symbol)
        
        timeframes = {}
        
        # Daily
        try:
            daily_df = stock.history(period="3mo", interval="1d")
            if len(daily_df) >= 20:
                timeframes['Daily'] = daily_df
        except:
            pass
        
        time.sleep(0.3)
        
        # Weekly
        try:
            weekly_df = stock.history(period="1y", interval="1wk")
            if len(weekly_df) >= 10:
                timeframes['Weekly'] = weekly_df
        except:
            pass
        
        # Hourly (only during market hours)
        is_open, _, _, _ = is_market_hours()
        if is_open:
            time.sleep(0.3)
            try:
                hourly_df = stock.history(period="5d", interval="1h")
                if len(hourly_df) >= 10:
                    timeframes['Hourly'] = hourly_df
            except:
                pass
        
        if not timeframes:
            return {
                'signals': {},
                'details': {},
                'alignment_score': 50,
                'recommendation': "Unable to fetch data",
                'aligned_count': 0,
                'against_count': 0,
                'total_timeframes': 0,
                'trend_strength': 'UNKNOWN'
            }
        
        signals = {}
        details = {}
        
        for tf_name, tf_df in timeframes.items():
            if len(tf_df) >= 14:
                close = tf_df['Close']
                current = float(close.iloc[-1])
                
                rsi = calculate_rsi(close).iloc[-1]
                if pd.isna(rsi):
                    rsi = 50
                
                sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
                ema_9 = close.ewm(span=9).mean().iloc[-1]
                ema_21 = close.ewm(span=21).mean().iloc[-1] if len(close) >= 21 else close.mean()
                
                macd, signal_line, histogram = calculate_macd(close)
                macd_hist = histogram.iloc[-1] if len(histogram) > 0 else 0
                if pd.isna(macd_hist):
                    macd_hist = 0
                
                bullish_points = 0
                total_points = 8
                
                if rsi > 50:
                    bullish_points += 2
                if current > sma_20:
                    bullish_points += 2
                if ema_9 > ema_21:
                    bullish_points += 2
                if macd_hist > 0:
                    bullish_points += 2
                
                bullish_pct = (bullish_points / total_points) * 100
                
                if bullish_pct >= 75:
                    signal = "BULLISH"
                    strength = "Strong"
                elif bullish_pct >= 50:
                    signal = "BULLISH"
                    strength = "Moderate"
                elif bullish_pct <= 25:
                    signal = "BEARISH"
                    strength = "Strong"
                elif bullish_pct < 50:
                    signal = "BEARISH"
                    strength = "Moderate"
                else:
                    signal = "NEUTRAL"
                    strength = "Weak"
                
                signals[tf_name] = signal
                details[tf_name] = {
                    'signal': signal,
                    'strength': strength,
                    'rsi': rsi,
                    'above_sma20': current > sma_20,
                    'ema_bullish': ema_9 > ema_21,
                    'macd_bullish': macd_hist > 0,
                    'bullish_score': bullish_pct
                }
        
        # Calculate alignment
        if position_type == "LONG":
            aligned = sum(1 for s in signals.values() if s == "BULLISH")
            against = sum(1 for s in signals.values() if s == "BEARISH")
        else:
            aligned = sum(1 for s in signals.values() if s == "BEARISH")
            against = sum(1 for s in signals.values() if s == "BULLISH")
        
        total = len(signals)
        alignment_score = int((aligned / total) * 100) if total > 0 else 50
        
        if alignment_score >= 80:
            recommendation = f"✅ Strong alignment with {position_type}"
        elif alignment_score >= 60:
            recommendation = f"👍 Good alignment with {position_type}"
        elif alignment_score >= 40:
            recommendation = f"⚠️ Mixed signals"
        else:
            recommendation = f"🚨 Against {position_type}"
        
        return {
            'signals': signals,
            'details': details,
            'alignment_score': alignment_score,
            'recommendation': recommendation,
            'aligned_count': aligned,
            'against_count': against,
            'total_timeframes': total,
            'trend_strength': 'STRONG' if alignment_score >= 70 else 'MODERATE' if alignment_score >= 50 else 'WEAK'
        }
    
    except Exception as e:
        return {
            'signals': {},
            'details': {},
            'alignment_score': 50,
            'recommendation': f"Error: {str(e)}",
            'aligned_count': 0,
            'against_count': 0,
            'total_timeframes': 0,
            'trend_strength': 'UNKNOWN'
        }

# ============================================================================
# CORRELATION ANALYSIS
# ============================================================================

def calculate_correlation_matrix(tickers, period="3mo"):
    """Calculate correlation matrix between stocks"""
    price_data = {}
    
    for ticker in tickers:
        df = get_stock_data_safe(ticker, period=period)
        if df is not None and len(df) > 20:
            price_data[ticker] = df['Close'].pct_change().dropna()
        time.sleep(0.2)
    
    if len(price_data) < 2:
        return None, "Not enough data"
    
    # Align all series
    combined = pd.DataFrame(price_data)
    combined = combined.dropna()
    
    if len(combined) < 20:
        return None, "Insufficient overlapping data"
    
    correlation_matrix = combined.corr()
    
    return correlation_matrix, "Success"

def analyze_correlation_risk(correlation_matrix, threshold=0.7):
    """Analyze correlation risk in portfolio"""
    if correlation_matrix is None:
        return [], 0, "No correlation data"
    
    high_correlations = []
    tickers = correlation_matrix.columns.tolist()
    
    for i, ticker1 in enumerate(tickers):
        for j, ticker2 in enumerate(tickers):
            if i < j:
                corr = correlation_matrix.loc[ticker1, ticker2]
                if abs(corr) >= threshold:
                    high_correlations.append({
                        'pair': f"{ticker1} - {ticker2}",
                        'correlation': corr,
                        'risk': 'HIGH' if abs(corr) >= 0.85 else 'MEDIUM'
                    })
    
    avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
    
    if avg_correlation > 0.6:
        status = "🔴 High portfolio correlation - diversification needed"
    elif avg_correlation > 0.4:
        status = "🟡 Moderate correlation - acceptable"
    else:
        status = "🟢 Low correlation - well diversified"
    
    return high_correlations, avg_correlation, status
	
# ============================================================================
# STOP LOSS RISK PREDICTION (0-100)
# ============================================================================

def predict_sl_risk(df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold=50):
    """
    Predict likelihood of hitting stop loss
    Returns: risk_score (0-100), reasons, recommendation, priority
    """
    risk_score = 0
    reasons = []
    close = df['Close']
    
    # Distance to Stop Loss (0-40 points)
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:  # Already hit SL
        risk_score = 100
        reasons.append("⚠️ SL already breached!")
    elif distance_pct < 1:
        risk_score += 40
        reasons.append(f"🔴 Very close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 2:
        risk_score += 30
        reasons.append(f"🟠 Close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 3:
        risk_score += 15
        reasons.append(f"🟡 Approaching SL ({distance_pct:.1f}% away)")
    elif distance_pct < 5:
        risk_score += 5
    
    # Trend Against Position (0-25 points)
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    if position_type == "LONG":
        if current_price < ema_9:
            risk_score += 8
            reasons.append("📉 Below EMA 9")
        if current_price < sma_20:
            risk_score += 10
            reasons.append("📉 Below SMA 20")
        if current_price < sma_50:
            risk_score += 7
            reasons.append("📉 Below SMA 50")
        if sma_20 < sma_50:
            risk_score += 5
            reasons.append("📉 Death cross forming")
    else:  # SHORT
        if current_price > ema_9:
            risk_score += 8
            reasons.append("📈 Above EMA 9")
        if current_price > sma_20:
            risk_score += 10
            reasons.append("📈 Above SMA 20")
        if current_price > sma_50:
            risk_score += 7
            reasons.append("📈 Above SMA 50")
        if sma_20 > sma_50:
            risk_score += 5
            reasons.append("📈 Golden cross forming")
    
    # MACD Against Position (0-15 points)
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if position_type == "LONG":
        if hist_current < 0:
            risk_score += 8
            reasons.append("📊 MACD bearish")
        if hist_current < hist_prev:
            risk_score += 7
            reasons.append("📊 MACD declining")
    else:
        if hist_current > 0:
            risk_score += 8
            reasons.append("📊 MACD bullish")
        if hist_current > hist_prev:
            risk_score += 7
            reasons.append("📊 MACD rising")
    
    # RSI Extreme (0-10 points)
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG" and rsi < 35:
        risk_score += 10
        reasons.append(f"📉 RSI weak ({rsi:.0f})")
    elif position_type == "SHORT" and rsi > 65:
        risk_score += 10
        reasons.append(f"📈 RSI strong ({rsi:.0f})")
    
    # Consecutive Candles Against Position (0-10 points)
    if len(close) >= 4:
        last_3 = close.tail(4).diff().dropna()
        if position_type == "LONG" and all(last_3 < 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive red candles")
        elif position_type == "SHORT" and all(last_3 > 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive green candles")
    
    # Volume Confirmation (0-10 points)
    volume_signal, volume_ratio, _, _ = analyze_volume(df)
    
    if position_type == "LONG" and volume_signal in ["STRONG_SELLING", "SELLING"]:
        risk_score += 10
        reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_signal in ["STRONG_BUYING", "BUYING"]:
        risk_score += 10
        reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    
    # Cap at 100
    risk_score = min(100, risk_score)
    
    # Generate recommendation based on threshold
    if risk_score >= 80:
        recommendation = "🚨 EXIT NOW - Very high risk"
        priority = "CRITICAL"
    elif risk_score >= sl_alert_threshold + 20:
        recommendation = "⚠️ CONSIDER EXIT - High risk"
        priority = "HIGH"
    elif risk_score >= sl_alert_threshold:
        recommendation = "👀 WATCH CLOSELY - Moderate risk"
        priority = "MEDIUM"
    elif risk_score >= 20:
        recommendation = "✅ MONITOR - Low risk"
        priority = "LOW"
    else:
        recommendation = "✅ SAFE - Very low risk"
        priority = "SAFE"
    
    return risk_score, reasons, recommendation, priority

# ============================================================================
# UPSIDE POTENTIAL PREDICTION
# ============================================================================

def predict_upside_potential(df, current_price, target1, target2, position_type):
    """
    Predict if stock can continue after hitting target
    Returns: upside_score (0-100), new_target, reasons, recommendation, action
    """
    score = 50  # Start neutral
    reasons = []
    close = df['Close']
    
    # Momentum still strong?
    momentum_score, trend, _ = calculate_momentum_score(df)
    
    if position_type == "LONG":
        if momentum_score >= 70:
            score += 25
            reasons.append(f"🚀 Strong momentum ({momentum_score:.0f})")
        elif momentum_score >= 55:
            score += 15
            reasons.append(f"📈 Good momentum ({momentum_score:.0f})")
        elif momentum_score <= 40:
            score -= 20
            reasons.append(f"📉 Weak momentum ({momentum_score:.0f})")
    else:  # SHORT
        if momentum_score <= 30:
            score += 25
            reasons.append(f"🚀 Strong bearish momentum ({momentum_score:.0f})")
        elif momentum_score <= 45:
            score += 15
            reasons.append(f"📉 Good bearish momentum ({momentum_score:.0f})")
        elif momentum_score >= 60:
            score -= 20
            reasons.append(f"📈 Bullish reversal ({momentum_score:.0f})")
    
    # RSI not extreme?
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG":
        if rsi < 60:
            score += 15
            reasons.append(f"✅ RSI has room ({rsi:.0f})")
        elif rsi > 75:
            score -= 25
            reasons.append(f"⚠️ RSI overbought ({rsi:.0f})")
        elif rsi > 65:
            score -= 10
            reasons.append(f"🟡 RSI getting high ({rsi:.0f})")
    else:
        if rsi > 40:
            score += 15
            reasons.append(f"✅ RSI has room ({rsi:.0f})")
        elif rsi < 25:
            score -= 25
            reasons.append(f"⚠️ RSI oversold ({rsi:.0f})")
    
    # Volume confirming?
    volume_signal, volume_ratio, _, volume_trend = analyze_volume(df)
    
    if position_type == "LONG" and volume_signal in ["STRONG_BUYING", "BUYING"]:
        score += 15
        reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_signal in ["STRONG_SELLING", "SELLING"]:
        score += 15
        reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    elif volume_ratio < 0.7:
        score -= 10
        reasons.append("📊 Low volume")
    
    # Bollinger Band position
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(close)
    if len(upper_bb) > 0 and len(lower_bb) > 0:
        bb_upper = upper_bb.iloc[-1]
        bb_lower = lower_bb.iloc[-1]
        bb_range = bb_upper - bb_lower
        
        if bb_range > 0:
            if position_type == "LONG":
                bb_position = (current_price - bb_lower) / bb_range
                if bb_position < 0.7:
                    score += 10
                    reasons.append("📈 Room to upper BB")
                elif bb_position > 0.95:
                    score -= 15
                    reasons.append("⚠️ At upper BB")
            else:
                bb_position = (current_price - bb_lower) / bb_range
                if bb_position > 0.3:
                    score += 10
                    reasons.append("📉 Room to lower BB")
                elif bb_position < 0.05:
                    score -= 15
                    reasons.append("⚠️ At lower BB")
    
    # Calculate new target based on ATR and S/R
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    if pd.isna(atr):
        atr = current_price * 0.02
    
    sr_levels = find_support_resistance(df)
    
    if position_type == "LONG":
        atr_target = current_price + (atr * 3)
        sr_target = sr_levels['nearest_resistance']
        new_target = min(atr_target, sr_target) if sr_target > current_price else atr_target
        potential_gain = ((new_target - current_price) / current_price) * 100
    else:
        atr_target = current_price - (atr * 3)
        sr_target = sr_levels['nearest_support']
        new_target = max(atr_target, sr_target) if sr_target < current_price else atr_target
        potential_gain = ((current_price - new_target) / current_price) * 100
    
    # ✅ Round new_target to NSE tick size
    new_target = round_to_tick_size(new_target)
    
    if potential_gain > 5:
        score += 10
        reasons.append(f"🎯 {potential_gain:.1f}% more potential")
    
    # Cap score
    score = max(0, min(100, score))
    
    # Generate recommendation
    if score >= 70:
        recommendation = "HOLD"
        action = f"Strong upside - New target: ₹{new_target:.2f}"
    elif score >= 50:
        recommendation = "PARTIAL_EXIT"
        action = f"Book 50%, hold rest for ₹{new_target:.2f}"
    else:
        recommendation = "EXIT"
        action = "Book full profits now"
    
    return score, new_target, reasons, recommendation, action

# ============================================================================
# DYNAMIC TARGET & TRAIL STOP CALCULATION
# ============================================================================

def calculate_dynamic_levels(df, entry_price, current_price, stop_loss, position_type,
                            pnl_percent, trail_trigger=2.0):
    """
    Calculate dynamic targets and trailing stop loss.
    Uses ATR-based dynamic trailing instead of fixed percentages.
    """
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    # Calculate ATR
    atr = calculate_atr(high, low, close).iloc[-1]
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02
    
    atr_pct = (atr / current_price) * 100
    
    # Get support/resistance
    sr_levels = find_support_resistance(df)
    
    result = {
        'atr': atr,
        'atr_pct': atr_pct,
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance'],
        'support_strength': sr_levels.get('support_strength', 'UNKNOWN'),
        'resistance_strength': sr_levels.get('resistance_strength', 'UNKNOWN')
    }
    
    # DYNAMIC TRAIL STOP CALCULATION
    if position_type == "LONG":
        # Calculate dynamic targets
        result['target1'] = current_price + (atr * 1.5)
        result['target2'] = current_price + (atr * 3)
        result['target3'] = min(current_price + (atr * 5), sr_levels['nearest_resistance'])
        # ✅ Round targets to NSE tick size AFTER all are defined
        result["target1"] = round_to_tick_size(result["target1"])
        result["target2"] = round_to_tick_size(result["target2"])
        result["target3"] = round_to_tick_size(result["target3"])
        
        # Dynamic trail based on profit level AND volatility (ATR)
        if pnl_percent >= trail_trigger * 5:  # e.g., 10% profit
            atr_trail = current_price - (atr * 1.0)
            pct_trail = entry_price + (current_price - entry_price) * 0.70
            result['trail_stop'] = max(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 70%+ profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_MAJOR_PROFIT"
        
        elif pnl_percent >= trail_trigger * 4:  # e.g., 8%
            atr_trail = current_price - (atr * 1.2)
            pct_trail = entry_price + (current_price - entry_price) * 0.60
            result['trail_stop'] = max(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 60% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        
        elif pnl_percent >= trail_trigger * 3:  # e.g., 6%
            atr_trail = current_price - (atr * 1.5)
            pct_trail = entry_price + (current_price - entry_price) * 0.50
            result['trail_stop'] = max(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 50% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        
        elif pnl_percent >= trail_trigger * 2:  # e.g., 4%
            atr_trail = current_price - (atr * 2.0)
            pct_trail = entry_price + (current_price - entry_price) * 0.30
            result['trail_stop'] = max(atr_trail, pct_trail, entry_price * 1.005)
            result['trail_reason'] = f"Securing gains (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        
        elif pnl_percent >= trail_trigger:  # e.g., 2%
            atr_trail = current_price - (atr * 2.5)
            result['trail_stop'] = max(atr_trail, entry_price)
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "BREAKEVEN"
        
        elif pnl_percent >= trail_trigger * 0.5:  # e.g., 1%
            atr_trail = current_price - (atr * 3.0)
            result['trail_stop'] = max(atr_trail, stop_loss)
            if result['trail_stop'] > stop_loss:
                result['trail_reason'] = f"Tightening SL (P&L: {pnl_percent:.1f}%)"
                result['trail_action'] = "TIGHTEN"
            else:
                result['trail_reason'] = "Keep original SL"
                result['trail_action'] = "HOLD"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL - profit not enough to trail"
            result['trail_action'] = "HOLD"
        
        # Ensure trail stop is not below original SL
        result['trail_stop'] = max(result['trail_stop'], stop_loss)
        result['should_trail'] = result['trail_stop'] > stop_loss
        result['trail_improvement'] = result['trail_stop'] - stop_loss if result['should_trail'] else 0
        result['trail_improvement_pct'] = (result['trail_improvement'] / entry_price * 100) if result['should_trail'] else 0
        
        # ✅ Round trail_stop to NSE tick size
        result["trail_stop"] = round_to_tick_size(result["trail_stop"])
    
    else:  # SHORT position
        result['target1'] = current_price - (atr * 1.5)
        result['target2'] = current_price - (atr * 3)
        result['target3'] = max(current_price - (atr * 5), sr_levels['nearest_support'])
        # ✅ Round targets to NSE tick size
        result["target1"] = round_to_tick_size(result["target1"])
        result["target2"] = round_to_tick_size(result["target2"])
        result["target3"] = round_to_tick_size(result["target3"])
        
        if pnl_percent >= trail_trigger * 5:
            atr_trail = current_price + (atr * 1.0)
            pct_trail = entry_price - (entry_price - current_price) * 0.70
            result['trail_stop'] = min(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 70%+ profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_MAJOR_PROFIT"
        
        elif pnl_percent >= trail_trigger * 4:
            atr_trail = current_price + (atr * 1.2)
            pct_trail = entry_price - (entry_price - current_price) * 0.60
            result['trail_stop'] = min(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 60% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        
        elif pnl_percent >= trail_trigger * 3:
            atr_trail = current_price + (atr * 1.5)
            pct_trail = entry_price - (entry_price - current_price) * 0.50
            result['trail_stop'] = min(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 50% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        
        elif pnl_percent >= trail_trigger * 2:
            atr_trail = current_price + (atr * 2.0)
            pct_trail = entry_price - (entry_price - current_price) * 0.30
            result['trail_stop'] = min(atr_trail, pct_trail, entry_price * 0.995)
            result['trail_reason'] = f"Securing gains (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        
        elif pnl_percent >= trail_trigger:
            atr_trail = current_price + (atr * 2.5)
            result['trail_stop'] = min(atr_trail, entry_price)
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "BREAKEVEN"
        
        elif pnl_percent >= trail_trigger * 0.5:
            atr_trail = current_price + (atr * 3.0)
            result['trail_stop'] = min(atr_trail, stop_loss)
            if result['trail_stop'] < stop_loss:
                result['trail_reason'] = f"Tightening SL (P&L: {pnl_percent:.1f}%)"
                result['trail_action'] = "TIGHTEN"
            else:
                result['trail_reason'] = "Keep original SL"
                result['trail_action'] = "HOLD"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL - profit not enough to trail"
            result['trail_action'] = "HOLD"
        
        result['trail_stop'] = min(result['trail_stop'], stop_loss)
        result['should_trail'] = result['trail_stop'] < stop_loss
        result['trail_improvement'] = stop_loss - result['trail_stop'] if result['should_trail'] else 0
        result['trail_improvement_pct'] = (result['trail_improvement'] / entry_price * 100) if result['should_trail'] else 0
        
        # ✅ Round trail_stop to NSE tick size
        result["trail_stop"] = round_to_tick_size(result["trail_stop"])
    
    return result

# ============================================================================
# SECTOR EXPOSURE ANALYSIS
# ============================================================================

# Stock to Sector Mapping (NSE Top 100+)
SECTOR_MAP = {
    # IT
    'TCS': 'IT', 'INFY': 'IT', 'WIPRO': 'IT', 'HCLTECH': 'IT', 'TECHM': 'IT',
    'LTIM': 'IT', 'MPHASIS': 'IT', 'COFORGE': 'IT', 'PERSISTENT': 'IT', 'LTTS': 'IT',
    
    # Banking
    'HDFCBANK': 'Banking', 'ICICIBANK': 'Banking', 'SBIN': 'Banking', 'KOTAKBANK': 'Banking',
    'AXISBANK': 'Banking', 'INDUSINDBK': 'Banking', 'BANDHANBNK': 'Banking', 'FEDERALBNK': 'Banking',
    'IDFCFIRSTB': 'Banking', 'PNB': 'Banking', 'BANKBARODA': 'Banking', 'CANBK': 'Banking',
    
    # NBFC/Finance
    'HDFC': 'Finance', 'BAJFINANCE': 'Finance', 'BAJAJFINSV': 'Finance', 'SBICARD': 'Finance',
    'CHOLAFIN': 'Finance', 'M&MFIN': 'Finance', 'MUTHOOTFIN': 'Finance', 'LICHSGFIN': 'Finance',
    
    # Energy/Oil & Gas
    'RELIANCE': 'Energy', 'ONGC': 'Energy', 'IOC': 'Energy', 'BPCL': 'Energy',
    'GAIL': 'Energy', 'PETRONET': 'Energy', 'HINDPETRO': 'Energy', 'ADANIGREEN': 'Energy',
    'ADANIPOWER': 'Energy', 'TATAPOWER': 'Energy', 'POWERGRID': 'Energy', 'NTPC': 'Energy',
    
    # Auto
    'MARUTI': 'Auto', 'TATAMOTORS': 'Auto', 'M&M': 'Auto', 'BAJAJ-AUTO': 'Auto',
    'HEROMOTOCO': 'Auto', 'EICHERMOT': 'Auto', 'ASHOKLEY': 'Auto', 'TVSMOTOR': 'Auto',
    'MOTHERSON': 'Auto', 'BHARATFORG': 'Auto', 'BALKRISIND': 'Auto', 'MRF': 'Auto',
    
    # FMCG
    'HINDUNILVR': 'FMCG', 'ITC': 'FMCG', 'NESTLEIND': 'FMCG', 'BRITANNIA': 'FMCG',
    'DABUR': 'FMCG', 'MARICO': 'FMCG', 'GODREJCP': 'FMCG', 'COLPAL': 'FMCG',
    'TATACONSUM': 'FMCG', 'VBL': 'FMCG', 'MCDOWELL-N': 'FMCG', 'UBL': 'FMCG',
    
    # Pharma
    'SUNPHARMA': 'Pharma', 'DRREDDY': 'Pharma', 'CIPLA': 'Pharma', 'DIVISLAB': 'Pharma',
    'APOLLOHOSP': 'Pharma', 'LUPIN': 'Pharma', 'AUROPHARMA': 'Pharma', 'BIOCON': 'Pharma',
    'TORNTPHARM': 'Pharma', 'ALKEM': 'Pharma', 'GLENMARK': 'Pharma', 'LAURUSLABS': 'Pharma',
    
    # Telecom
    'BHARTIARTL': 'Telecom', 'IDEA': 'Telecom', 'INDUSTOWER': 'Telecom',
    
    # Infrastructure/Construction
    'LT': 'Infrastructure', 'ADANIENT': 'Infrastructure', 'ADANIPORTS': 'Infrastructure',
    'ULTRACEMCO': 'Infrastructure', 'GRASIM': 'Infrastructure', 'SHREECEM': 'Infrastructure',
    'AMBUJACEM': 'Infrastructure', 'ACC': 'Infrastructure', 'DALBHARAT': 'Infrastructure',
    
    # Metals
    'TATASTEEL': 'Metals', 'JSWSTEEL': 'Metals', 'HINDALCO': 'Metals', 'VEDL': 'Metals',
    'COALINDIA': 'Metals', 'NMDC': 'Metals', 'SAIL': 'Metals', 'JINDALSTEL': 'Metals',
    
    # Retail
    'TITAN': 'Retail', 'TRENT': 'Retail', 'DMART': 'Retail', 'PAGEIND': 'Retail',
    'ABFRL': 'Retail', 'RELAXO': 'Retail',
    
    # Insurance
    'SBILIFE': 'Insurance', 'HDFCLIFE': 'Insurance', 'ICICIPRULI': 'Insurance',
    'ICICIGI': 'Insurance', 'BAJAJHLDNG': 'Insurance', 'NIACL': 'Insurance',
    
    # Real Estate
    'DLF': 'Real Estate', 'GODREJPROP': 'Real Estate', 'OBEROIRLTY': 'Real Estate',
    'PHOENIXLTD': 'Real Estate', 'PRESTIGE': 'Real Estate', 'BRIGADE': 'Real Estate',
    
    # Chemicals
    'PIDILITIND': 'Chemicals', 'SRF': 'Chemicals', 'ATUL': 'Chemicals',
    'NAVINFLUOR': 'Chemicals', 'DEEPAKNI': 'Chemicals', 'CLEAN': 'Chemicals',
}

def analyze_sector_exposure(results):
    """
    Analyze sector exposure across portfolio
    Returns sector breakdown and warnings
    """
    sector_exposure = {}
    total_value = 0
    
    for r in results:
        ticker = r['ticker'].replace('.NS', '').replace('.BO', '').upper()
        sector = SECTOR_MAP.get(ticker, 'Other')
        position_value = r['entry_price'] * r['quantity']
        
        if sector not in sector_exposure:
            sector_exposure[sector] = {
                'value': 0,
                'count': 0,
                'stocks': [],
                'pnl': 0
            }
        
        sector_exposure[sector]['value'] += position_value
        sector_exposure[sector]['count'] += 1
        sector_exposure[sector]['stocks'].append(ticker)
        sector_exposure[sector]['pnl'] += r['pnl_amount']
        total_value += position_value
    
    # Calculate percentages
    sector_pct = {}
    for sector, data in sector_exposure.items():
        sector_pct[sector] = {
            'percentage': (data['value'] / total_value * 100) if total_value > 0 else 0,
            'count': data['count'],
            'stocks': data['stocks'],
            'value': data['value'],
            'pnl': data['pnl']
        }
    
    # Sort by percentage
    sector_pct_sorted = dict(sorted(sector_pct.items(),
                                    key=lambda x: x[1]['percentage'],
                                    reverse=True))
    
    # Warnings
    warnings = []
    for sector, data in sector_pct_sorted.items():
        if data['percentage'] > 40:
            warnings.append(f"🚨 {sector}: {data['percentage']:.1f}% - Highly over-exposed!")
        elif data['percentage'] > 30:
            warnings.append(f"⚠️ {sector}: {data['percentage']:.1f}% - Over-concentrated")
    
    # Diversification score
    num_sectors = len([s for s in sector_pct if sector_pct[s]['percentage'] > 5])
    if num_sectors >= 6:
        diversification_score = 90
    elif num_sectors >= 4:
        diversification_score = 70
    elif num_sectors >= 2:
        diversification_score = 50
    else:
        diversification_score = 30
    
    # Adjust for concentration
    max_concentration = max([d['percentage'] for d in sector_pct.values()]) if sector_pct else 0
    if max_concentration > 50:
        diversification_score -= 30
    elif max_concentration > 35:
        diversification_score -= 15
    
    diversification_score = max(0, min(100, diversification_score))
    
    return {
        'sectors': sector_pct_sorted,
        'warnings': warnings,
        'total_sectors': len(sector_pct),
        'diversification_score': diversification_score,
        'max_concentration': max_concentration,
        'total_value': total_value
    }

# ============================================================================
# PORTFOLIO RISK CALCULATION
# ============================================================================

def calculate_portfolio_risk(results):
    """
    Calculate overall portfolio risk metrics
    """
    if not results:
        return None
    
    total_capital = sum(r['entry_price'] * r['quantity'] for r in results)
    total_current_value = sum(r['current_price'] * r['quantity'] for r in results)
    total_pnl = sum(r['pnl_amount'] for r in results)
    
    # Calculate total risk amount (if all SL hit)
    total_risk_amount = 0
    for r in results:
        if r['position_type'] == 'LONG':
            loss_if_sl = (r['entry_price'] - r['stop_loss']) * r['quantity']
        else:
            loss_if_sl = (r['stop_loss'] - r['entry_price']) * r['quantity']
        total_risk_amount += max(loss_if_sl, 0)
    
    portfolio_risk_pct = (total_risk_amount / total_capital * 100) if total_capital > 0 else 0
    
    # Risk status
    if portfolio_risk_pct <= 5:
        risk_status = "SAFE"
        risk_color = "#28a745"
        risk_icon = "✅"
    elif portfolio_risk_pct <= 10:
        risk_status = "MEDIUM"
        risk_color = "#ffc107"
        risk_icon = "⚠️"
    else:
        risk_status = "HIGH"
        risk_color = "#dc3545"
        risk_icon = "🚨"
    
    # Count risky positions
    risky_positions = sum(1 for r in results if r['sl_risk'] >= 50)
    critical_positions = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    
    # Average SL risk
    avg_sl_risk = sum(r['sl_risk'] for r in results) / len(results) if results else 0
    
    return {
        'total_capital': total_capital,
        'current_value': total_current_value,
        'total_pnl': total_pnl,
        'total_pnl_pct': (total_pnl / total_capital * 100) if total_capital > 0 else 0,
        'total_risk_amount': total_risk_amount,
        'portfolio_risk_pct': portfolio_risk_pct,
        'risk_status': risk_status,
        'risk_color': risk_color,
        'risk_icon': risk_icon,
        'risky_positions': risky_positions,
        'critical_positions': critical_positions,
        'avg_sl_risk': avg_sl_risk,
        'total_positions': len(results)
    }

# ============================================================================
# PARTIAL PROFIT BOOKING TRACKER
# ============================================================================

def calculate_partial_exit_levels(entry_price, target1, target2, position_type):
    """
    Calculate recommended partial exit levels
    """
    if position_type == "LONG":
        move = target1 - entry_price
        levels = [
            {'level': entry_price + move * 0.5, 'exit_pct': 25, 'reason': '50% to T1'},
            {'level': target1, 'exit_pct': 25, 'reason': 'Target 1'},
            {'level': entry_price + (target2 - entry_price) * 0.75, 'exit_pct': 25, 'reason': '75% to T2'},
            {'level': target2, 'exit_pct': 25, 'reason': 'Target 2'},
        ]
    else:
        move = entry_price - target1
        levels = [
            {'level': entry_price - move * 0.5, 'exit_pct': 25, 'reason': '50% to T1'},
            {'level': target1, 'exit_pct': 25, 'reason': 'Target 1'},
            {'level': entry_price - (entry_price - target2) * 0.75, 'exit_pct': 25, 'reason': '75% to T2'},
            {'level': target2, 'exit_pct': 25, 'reason': 'Target 2'},
        ]
    
    return levels

def track_partial_exit(ticker, current_price, entry_price, quantity, position_type, target1, target2):
    """
    Track partial exit recommendations based on current price
    """
    levels = calculate_partial_exit_levels(entry_price, target1, target2, position_type)
    
    recommendations = []
    remaining_qty = quantity
    
    for level in levels:
        if position_type == "LONG":
            if current_price >= level['level']:
                exit_qty = int(quantity * level['exit_pct'] / 100)
                if exit_qty > 0:
                    recommendations.append({
                        'level': level['level'],
                        'exit_pct': level['exit_pct'],
                        'exit_qty': exit_qty,
                        'reason': level['reason'],
                        'status': 'TRIGGERED',
                        'pnl': (level['level'] - entry_price) * exit_qty
                    })
                    remaining_qty -= exit_qty
        else:
            if current_price <= level['level']:
                exit_qty = int(quantity * level['exit_pct'] / 100)
                if exit_qty > 0:
                    recommendations.append({
                        'level': level['level'],
                        'exit_pct': level['exit_pct'],
                        'exit_qty': exit_qty,
                        'reason': level['reason'],
                        'status': 'TRIGGERED',
                        'pnl': (entry_price - level['level']) * exit_qty
                    })
                    remaining_qty -= exit_qty
    
    # Add pending levels
    for level in levels:
        already_added = any(r['level'] == level['level'] for r in recommendations)
        if not already_added:
            exit_qty = int(quantity * level['exit_pct'] / 100)
            recommendations.append({
                'level': level['level'],
                'exit_pct': level['exit_pct'],
                'exit_qty': exit_qty,
                'reason': level['reason'],
                'status': 'PENDING',
                'pnl': 0
            })
    
    return {
        'recommendations': recommendations,
        'remaining_qty': max(0, remaining_qty),
        'triggered_count': sum(1 for r in recommendations if r['status'] == 'TRIGGERED'),
        'total_booked_pnl': sum(r['pnl'] for r in recommendations if r['status'] == 'TRIGGERED')
    }

# ============================================================================
# COMPLETE SMART ANALYSIS FUNCTION
# ============================================================================

@st.cache_data(ttl=15)  # 15 second cache
def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss,
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                          sl_approach_threshold=2.0, enable_mtf=True, entry_date=None):
    """
    Complete smart analysis with all features
    Accepts sidebar parameters for dynamic thresholds
    """
    df = get_stock_data_safe(ticker, period="6mo")
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
    except Exception as e:
        return None
    
    # Basic P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    # Technical Indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    if pd.isna(macd_hist):
        macd_hist = 0
    macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
    
    # Stochastic
    stoch_k, stoch_d = calculate_stochastic(df['High'], df['Low'], df['Close'])
    stoch_k_val = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else 50
    stoch_d_val = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else 50
    
    # Momentum Score
    momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
    
    # Volume Analysis
    volume_signal, volume_ratio, volume_desc, volume_trend = analyze_volume(df)
    
    # Support/Resistance
    sr_levels = find_support_resistance(df)
    
    # SL Risk Prediction
    sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_sl_risk(
        df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold
    )
    
    # Multi-Timeframe Analysis
    if enable_mtf:
        mtf_result = multi_timeframe_analysis(ticker, position_type)
    else:
        mtf_result = {
            'signals': {},
            'details': {},
            'alignment_score': 50,
            'recommendation': "MTF disabled",
            'aligned_count': 0,
            'against_count': 0,
            'total_timeframes': 0,
            'trend_strength': 'UNKNOWN'
        }
    
    # Check if target hit
    if position_type == "LONG":
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
        sl_hit = current_price <= stop_loss
    else:
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
        sl_hit = current_price >= stop_loss
    
    # Upside prediction (if target hit)
    if target1_hit and not sl_hit:
        upside_score, new_target, upside_reasons, upside_rec, upside_action = predict_upside_potential(
            df, current_price, target1, target2, position_type
        )
    else:
        upside_score = 0
        new_target = target2
        upside_reasons = []
        upside_rec = ""
        upside_action = ""
    
    # Dynamic Levels
    dynamic_levels = calculate_dynamic_levels(
        df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_threshold
    )
    
    # Partial Exit Tracking
    partial_exits = track_partial_exit(
        ticker, current_price, entry_price, quantity, position_type, target1, target2
    )
    
    # Holding Period & Tax
    if entry_date:
        holding_days = calculate_holding_period(entry_date)
        tax_implication, tax_color = get_tax_implication(holding_days, pnl_amount)
    else:
        holding_days = 0
        tax_implication = "Entry date not provided"
        tax_color = "⚪"
    
    # Breakeven check
    breakeven_distance = abs(pnl_percent)
    at_breakeven = breakeven_distance < 0.5 and pnl_percent >= 0
    
    # Distance to SL (for approach warning)
    if position_type == "LONG":
        distance_to_sl = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_to_sl = ((stop_loss - current_price) / current_price) * 100
    
    approaching_sl = distance_to_sl > 0 and distance_to_sl <= sl_approach_threshold
    
    # =========================================================================
    # GENERATE ALERTS AND DETERMINE OVERALL STATUS
    # =========================================================================
    alerts = []
    overall_status = 'OK'
    overall_action = 'HOLD'
    
    # Priority 1: SL Hit
    if sl_hit:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 STOP LOSS HIT',
            'message': f'Price ₹{current_price:.2f} breached SL ₹{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY',
            'email_type': 'critical'
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
    
    # Priority 2: High SL Risk (Early Exit Warning)
    elif sl_risk >= sl_alert_threshold + 20:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '⚠️ HIGH SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation,
            'email_type': 'critical'
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT_EARLY'
    
    # Priority 3: Approaching SL
    elif approaching_sl:
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ APPROACHING SL',
            'message': f'Only {distance_to_sl:.1f}% away from Stop Loss!',
            'action': 'Review position - consider early exit',
            'email_type': 'sl_approach'
        })
        if overall_status == 'OK':
            overall_status = 'WARNING'
            overall_action = 'WATCH'
    
    # Priority 4: Moderate SL Risk
    elif sl_risk >= sl_alert_threshold:
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ MODERATE SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation,
            'email_type': 'important'
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    # Priority 5: Target 2 Hit
    elif target2_hit:
        alerts.append({
            'priority': 'HIGH',
            'type': '🎯 TARGET 2 HIT',
            'message': f'Both targets achieved! P&L: {pnl_percent:+.2f}%',
            'action': 'BOOK FULL PROFITS',
            'email_type': 'target'
        })
        overall_status = 'SUCCESS'
        overall_action = 'BOOK_PROFITS'
    
    # Priority 6: Target 1 Hit with Upside Analysis
    elif target1_hit:
        if upside_score >= 60:
            alerts.append({
                'priority': 'INFO',
                'type': '🎯 TARGET HIT - HOLD',
                'message': f'Upside Score: {upside_score}% - {", ".join(upside_reasons[:2])}',
                'action': f'{upside_action}',
                'email_type': 'target'
            })
            overall_status = 'OPPORTUNITY'
            overall_action = 'HOLD_EXTEND'
        else:
            alerts.append({
                'priority': 'HIGH',
                'type': '🎯 TARGET HIT - EXIT',
                'message': f'Limited upside ({upside_score}%). Book profits.',
                'action': 'BOOK PROFITS',
                'email_type': 'target'
            })
            overall_status = 'SUCCESS'
            overall_action = 'BOOK_PROFITS'
    
    # Priority 7: Trail Stop Recommendation
    elif dynamic_levels['should_trail'] and pnl_percent >= trail_threshold:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📈 TRAIL STOP LOSS',
            'message': f'{dynamic_levels.get("trail_reason", "Lock profits!")} Move SL from ₹{stop_loss:.2f} to ₹{dynamic_levels["trail_stop"]:.2f}',
            'action': f'New SL: ₹{dynamic_levels["trail_stop"]:.2f}',
            'email_type': 'sl_change'
        })
        overall_status = 'GOOD'
        overall_action = 'TRAIL_SL'
    
    # Priority 8: MTF Warning
    elif enable_mtf and mtf_result['alignment_score'] < 40 and pnl_percent < 0:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📊 MTF WARNING',
            'message': f'Timeframes against position ({mtf_result["alignment_score"]}% aligned)',
            'action': mtf_result['recommendation'],
            'email_type': 'important'
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    # Priority 9: Breakeven Alert
    elif at_breakeven:
        alerts.append({
            'priority': 'LOW',
            'type': '🔔 BREAKEVEN REACHED',
            'message': f'Position at breakeven. Consider moving SL to entry (₹{entry_price:.2f})',
            'action': f'Move SL to ₹{entry_price:.2f} (breakeven)',
            'email_type': 'important'
        })
        if overall_status == 'OK':
            overall_status = 'GOOD'
            overall_action = 'MOVE_SL_BREAKEVEN'
    
    # Priority 10: Partial Exit Alert
    if partial_exits['triggered_count'] > 0 and not target2_hit:
        triggered = [r for r in partial_exits['recommendations'] if r['status'] == 'TRIGGERED']
        if triggered:
            latest = triggered[-1]
            alerts.append({
                'priority': 'LOW',
                'type': '📊 PARTIAL EXIT',
                'message': f'Level ₹{latest["level"]:.2f} triggered - Book {latest["exit_pct"]}% ({latest["exit_qty"]} shares)',
                'action': f'Exit {latest["exit_qty"]} shares at ₹{current_price:.2f}',
                'email_type': 'important'
            })
    
    # Volume Warning
    if position_type == "LONG" and volume_signal == "STRONG_SELLING" and sl_risk < sl_alert_threshold:
        alerts.append({
            'priority': 'LOW',
            'type': '📊 VOLUME WARNING',
            'message': volume_desc,
            'action': 'Monitor closely',
            'email_type': 'important'
        })
    elif position_type == "SHORT" and volume_signal == "STRONG_BUYING" and sl_risk < sl_alert_threshold:
        alerts.append({
            'priority': 'LOW',
            'type': '📊 VOLUME WARNING',
            'message': volume_desc,
            'action': 'Monitor closely',
            'email_type': 'important'
        })
    
    # Calculate Risk-Reward Ratio
    if position_type == "LONG":
        risk = entry_price - stop_loss
        reward = target1 - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - target1
    
    risk_reward_ratio = safe_divide(reward, risk, default=0.0)
    
    return {
        # Basic Info
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        'day_change': day_change,
        'day_high': day_high,
        'day_low': day_low,
        
        # Original Levels
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        
        # Technical Indicators
        'rsi': rsi,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        'stoch_k': stoch_k_val,
        'stoch_d': stoch_d_val,
        
        # Momentum
        'momentum_score': momentum_score,
        'momentum_trend': momentum_trend,
        'momentum_components': momentum_components,
        
        # Volume
        'volume_signal': volume_signal,
        'volume_ratio': volume_ratio,
        'volume_desc': volume_desc,
        'volume_trend': volume_trend,
        
        # Support/Resistance
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance'],
        'distance_to_support': sr_levels['distance_to_support'],
        'distance_to_resistance': sr_levels['distance_to_resistance'],
        'support_strength': sr_levels['support_strength'],
        'resistance_strength': sr_levels['resistance_strength'],
        
        # SL Risk
        'sl_risk': sl_risk,
        'sl_reasons': sl_reasons,
        'sl_recommendation': sl_recommendation,
        'sl_priority': sl_priority,
        'distance_to_sl': distance_to_sl,
        'approaching_sl': approaching_sl,
        
        # Upside
        'upside_score': upside_score,
        'upside_reasons': upside_reasons,
        'new_target': new_target,
        
        # Dynamic Levels
        'trail_stop': dynamic_levels['trail_stop'],
        'should_trail': dynamic_levels['should_trail'],
        'trail_reason': dynamic_levels.get('trail_reason', ''),
        'trail_action': dynamic_levels.get('trail_action', ''),
        'dynamic_target1': dynamic_levels['target1'],
        'dynamic_target2': dynamic_levels['target2'],
        'atr': dynamic_levels['atr'],
        
        # Targets Status
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'sl_hit': sl_hit,
        'at_breakeven': at_breakeven,
        
        # Multi-Timeframe
        'mtf_signals': mtf_result['signals'],
        'mtf_details': mtf_result.get('details', {}),
        'mtf_alignment': mtf_result['alignment_score'],
        'mtf_recommendation': mtf_result['recommendation'],
        'mtf_trend_strength': mtf_result.get('trend_strength', 'UNKNOWN'),
        
        # Partial Exits
        'partial_exits': partial_exits,
        
        # Holding Period
        'holding_days': holding_days,
        'tax_implication': tax_implication,
        'tax_color': tax_color,
        
        # Risk-Reward
        'risk_reward_ratio': risk_reward_ratio,
        
        # Alerts & Status
        'alerts': alerts,
        'overall_status': overall_status,
        'overall_action': overall_action,
        
        # Chart Data
        'df': df
    }

# ============================================================================
# LOAD PORTFOLIO FROM GOOGLE SHEETS
# ============================================================================

def load_portfolio():
    """Load portfolio from Google Sheets using gspread"""
    
    if not HAS_GSPREAD:
        st.error("❌ gspread not installed. Run: pip install gspread oauth2client")
        return None
    
    try:
        # Use the service account connection (already defined in your code)
        sheet, status = get_google_sheet_connection()
        
        if sheet is None:
            st.error(f"❌ Connection failed: {status}")
            return None
        
        # Get all records from the sheet
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            st.warning("⚠️ No data found in sheet")
            return None
        
        # Filter active positions
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Validate required columns
        required_cols = ['Ticker', 'Position', 'Entry_Price', 'Stop_Loss', 'Target_1']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.warning(f"⚠️ Missing columns: {missing_cols}")
            # Try alternative column names
            alt_names = {
                'Ticker': ['Symbol', 'Stock', 'Name'],
                'Position': ['Type', 'Side', 'Direction'],
                'Entry_Price': ['Entry', 'Buy_Price', 'Price'],
                'Stop_Loss': ['SL', 'Stoploss'],
                'Target_1': ['Target', 'T1', 'Target1']
            }
            for col, alts in alt_names.items():
                if col not in df.columns:
                    for alt in alts:
                        if alt in df.columns:
                            df[col] = df[alt]
                            break
        
        # Set defaults for optional columns
        if 'Quantity' not in df.columns:
            df['Quantity'] = 1
        if 'Target_2' not in df.columns:
            df['Target_2'] = df['Target_1'] * 1.1
        if 'Entry_Date' not in df.columns:
            df['Entry_Date'] = None
        
        # ✅ NEW: Ensure Realized_PnL column exists
        if 'Realized_PnL' not in df.columns:
            df['Realized_PnL'] = 0.0
        
        st.success(f"✅ Loaded {len(df)} active positions from Google Sheets")
        
        return df
    
    except Exception as e:
        st.error(f"❌ Error loading from Google Sheets: {e}")
        st.info("💡 Make sure the Google Sheet is set to 'Anyone with the link can view'")
        
        # Return sample data as fallback
        st.warning("⚠️ Using sample data as fallback")
        return pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'],
            'Position': ['LONG', 'LONG', 'SHORT', 'LONG', 'LONG'],
            'Entry_Price': [2450.00, 3580.00, 1520.00, 1650.00, 1050.00],
            'Quantity': [10, 5, 8, 12, 20],
            'Stop_Loss': [2380.00, 3480.00, 1580.00, 1600.00, 1010.00],
            'Target_1': [2550.00, 3720.00, 1420.00, 1750.00, 1120.00],
            'Target_2': [2650.00, 3850.00, 1350.00, 1850.00, 1180.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01', '2024-01-10', '2024-02-05'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE'],
            'Realized_PnL': [0.0, 0.0, 0.0, 0.0, 0.0]
        })
# ============================================================================
# PORTFOLIO VALIDATION
# ============================================================================

def validate_portfolio(df):
    """
    Validate portfolio data and return errors
    Returns: (is_valid, errors_list)
    """
    errors = []
    warnings = []
    
    # Check required columns
    required_cols = ['Ticker', 'Position', 'Entry_Price', 'Stop_Loss', 'Target_1']
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"❌ Missing required column: {col}")
    
    if errors:
        return False, errors, warnings
    
    # Validate each row
    for idx, row in df.iterrows():
        ticker = str(row.get('Ticker', f'Row {idx}')).strip()
        
        try:
            entry = float(row['Entry_Price'])
            sl = float(row['Stop_Loss'])
            target = float(row['Target_1'])
            position = str(row['Position']).upper().strip()
            status = str(row['Status']).upper().strip()
        except (ValueError, TypeError) as e:
            errors.append(f"❌ {ticker}: Invalid number format - {e}")
            continue
        
        # Check positive values
        if entry <= 0:
            errors.append(f"❌ {ticker}: Entry price must be positive")
        if sl <= 0:
            errors.append(f"❌ {ticker}: Stop loss must be positive")
        if target <= 0:
            errors.append(f"❌ {ticker}: Target must be positive")
        
        # Check position type
        if position not in ['LONG', 'SHORT']:
            errors.append(f"❌ {ticker}: Position must be 'LONG' or 'SHORT', got '{position}'")
            continue
        
        # Validate levels based on position type
        if status == 'PENDING':
            if position == 'LONG':
                if entry <= sl: 
                    errors.append(f"❌ {ticker} (LONG): Entry (₹{entry}) must be > Stop Loss (₹{sl})")
                if target <= entry:
                    warnings.append(f"⚠️ {ticker} (LONG): Target (₹{target}) should be > Entry (₹{entry})")
            else:  # SHORT
                if entry >= sl:
                    errors.append(f"❌ {ticker} (SHORT): Entry (₹{entry}) must be < Stop Loss (₹{sl})")
                if target >= entry:
                    warnings.append(f"⚠️ {ticker} (SHORT): Target (₹{target}) should be < Entry (₹{entry})")
        
        # Check quantity if present
        if 'Quantity' in df.columns:
            try:
                qty = int(row['Quantity'])
                if qty <= 0:
                    errors.append(f"❌ {ticker}: Quantity must be positive")
            except:
                warnings.append(f"⚠️ {ticker}: Invalid quantity, using default (1)")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings

# ============================================================================
# GOOGLE SHEETS UPDATE FUNCTIONS
# ============================================================================

def get_google_sheet_connection():
    try:
        if credentials is None:
            return None, "Google credentials not configured"
        gc = gspread.authorize(credentials)
        sh = gc.open("my_portfolio")
        return sh.sheet1, "success"
    except Exception as e:
        return None, str(e)


def update_sheet_stop_loss(ticker, new_sl, reason, should_send_email=True, email_settings=None, result=None):
    """
    Update Stop Loss in Google Sheet and send email notification
    Returns: (success, message)
    """
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        logger.warning(f"Cannot update sheet: {status}")
        return False, status
    
    try:
        # Find the row with this ticker
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found in sheet"
        
        row = cell.row
        
        # Find Stop_Loss column
        headers = sheet.row_values(1)
        
        try:
            sl_col = headers.index('Stop_Loss') + 1  # +1 because gspread is 1-indexed
        except ValueError:
            sl_col = 4  # Default to column D if not found
        
        # Get old SL value before updating
        old_sl = sheet.cell(row, sl_col).value
        
        
        # ✅ Round to NSE tick size before updating
        new_sl = round_to_tick_size(new_sl)
        # Update the cell
        sheet.update_cell(row, sl_col, new_sl)
        
        # Log the update
        log_message = f"🔄 AUTO-UPDATED {ticker} SL: ₹{old_sl} → ₹{new_sl:.2f} - {reason}"
        logger.info(log_message)
        log_email(log_message)
        
        # 🆕 SEND EMAIL NOTIFICATION
        if should_send_email and email_settings and result:
            if email_settings.get('email_on_sl_change', True):
                sender = email_settings.get('sender_email')
                password = email_settings.get('sender_password')
                recipient = email_settings.get('recipient_email')
                
                if sender and password and recipient:
                    subject = f"🔄 Stop Loss Updated - {ticker}"
                    
                    html_content = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
                        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                            <div style="background: #17a2b8; color: white; padding: 20px; text-align: center;">
                                <h1 style="margin: 0;">🔄 Stop Loss Updated</h1>
                                <p style="margin: 10px 0 0 0; font-size: 1.2em;">{ticker}</p>
                            </div>
                            <div style="padding: 20px;">
                                <div style="background: #e7f3ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #17a2b8;">
                                    <p style="margin: 0; font-size: 1.1em;"><strong>Old Stop Loss:</strong> ₹{old_sl}</p>
                                    <p style="margin: 10px 0 0 0; font-size: 1.2em; color: #17a2b8;"><strong>New Stop Loss:</strong> ₹{new_sl:.2f}</p>
                                    <p style="margin: 10px 0 0 0;"><strong>Reason:</strong> {reason}</p>
                                </div>
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Current Price</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['current_price']:,.2f}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Entry Price</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['entry_price']:,.2f}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Current P&L</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; color: {'#28a745' if result['pnl_percent'] >= 0 else '#dc3545'};">
                                            {result['pnl_percent']:+.2f}% (₹{result['pnl_amount']:+,.0f})
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Trail Action</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result.get('trail_action', 'N/A')}</td>
                                    </tr>
                                </table>
                            </div>
                            <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
                                <p style="margin: 0;">Smart Portfolio Monitor - Auto Update</p>
                                <p style="margin: 5px 0 0 0;">{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    send_email_alert(subject, html_content, sender, password, recipient)
                    log_email(f"📧 Email sent for SL update: {ticker}")
        
        return True, log_message
    
    except Exception as e:
        error_msg = f"Error updating {ticker}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def update_sheet_target(ticker, new_target, target_num, reason, should_send_email=True, email_settings=None, result=None):
    """
    Update Target in Google Sheet and send email notification
    target_num: 1 or 2
    Returns: (success, message)
    """
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        logger.warning(f"Cannot update sheet: {status}")
        return False, status
    
    try:
        # Find the row
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found in sheet"
        
        row = cell.row
        
        # Find Target column
        headers = sheet.row_values(1)
        target_col_name = f'Target_{target_num}'
        
        try:
            target_col = headers.index(target_col_name) + 1
        except ValueError:
            target_col = 6 if target_num == 1 else 7  # Default columns
        
        # Get old target value before updating
        old_target = sheet.cell(row, target_col).value
        
        
        # ✅ Round to NSE tick size before updating
        new_target = round_to_tick_size(new_target)
        # Update the cell
        sheet.update_cell(row, target_col, new_target)
        
        log_message = f"🎯 AUTO-UPDATED {ticker} Target {target_num}: ₹{old_target} → ₹{new_target:.2f} - {reason}"
        logger.info(log_message)
        log_email(log_message)
        
        # 🆕 SEND EMAIL NOTIFICATION
        if should_send_email and email_settings and result:
            if email_settings.get('email_on_target_change', True):
                sender = email_settings.get('sender_email')
                password = email_settings.get('sender_password')
                recipient = email_settings.get('recipient_email')
                
                if sender and password and recipient:
                    subject = f"🎯 Target Extended - {ticker}"
                    
                    html_content = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
                        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                            <div style="background: #28a745; color: white; padding: 20px; text-align: center;">
                                <h1 style="margin: 0;">🎯 Target Extended</h1>
                                <p style="margin: 10px 0 0 0; font-size: 1.2em;">{ticker}</p>
                            </div>
                            <div style="padding: 20px;">
                                <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #28a745;">
                                    <p style="margin: 0; font-size: 1.1em;"><strong>Old Target {target_num}:</strong> ₹{old_target}</p>
                                    <p style="margin: 10px 0 0 0; font-size: 1.2em; color: #28a745;"><strong>New Target {target_num}:</strong> ₹{new_target:.2f}</p>
                                    <p style="margin: 10px 0 0 0;"><strong>Reason:</strong> {reason}</p>
                                </div>
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Current Price</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['current_price']:,.2f}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Upside Score</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result.get('upside_score', 0):.0f}/100</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Potential Gain</strong></td>
                                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">
                                            {((new_target - result['current_price']) / result['current_price'] * 100):+.2f}%
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
                                <p style="margin: 0;">Smart Portfolio Monitor - Auto Update</p>
                                <p style="margin: 5px 0 0 0;">{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    send_email_alert(subject, html_content, sender, password, recipient)
                    log_email(f"📧 Email sent for Target update: {ticker}")
        
        return True, log_message
    
    except Exception as e:
        error_msg = f"Error updating {ticker}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def mark_position_inactive(ticker, exit_price, pnl_amount, exit_reason, should_send_email=True, email_settings=None, result=None):
    """
    Mark position as INACTIVE and record realized P&L
    Sends email notification on exit
    Returns: (success, message)
    """
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        logger.warning(f"Cannot update sheet: {status}")
        return False, status
    
    try:
        # Find the row
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found in sheet"
        
        row = cell.row
        headers = sheet.row_values(1)
        
        # Find Status column
        try:
            status_col = headers.index('Status') + 1
        except ValueError:
            status_col = 9  # Default column
        
        # Find Realized_PnL column
        try:
            pnl_col = headers.index('Realized_PnL') + 1
        except ValueError:
            # If column doesn't exist, we need to add it
            pnl_col = len(headers) + 1
            sheet.update_cell(1, pnl_col, 'Realized_PnL')  # Add header
        
        # Find Exit_Date column (add if doesn't exist)
        try:
            exit_date_col = headers.index('Exit_Date') + 1
        except ValueError:
            exit_date_col = len(headers) + 2
            sheet.update_cell(1, exit_date_col, 'Exit_Date')
        
        # Find Exit_Reason column (add if doesn't exist)
        try:
            exit_reason_col = headers.index('Exit_Reason') + 1
        except ValueError:
            exit_reason_col = len(headers) + 3
            sheet.update_cell(1, exit_reason_col, 'Exit_Reason')
        
        # Update Status to INACTIVE
        sheet.update_cell(row, status_col, 'INACTIVE')
        
        # Update Realized P&L
        sheet.update_cell(row, pnl_col, pnl_amount)
        
        # Update Exit Date
        exit_date = get_ist_now().strftime('%Y-%m-%d')
        sheet.update_cell(row, exit_date_col, exit_date)
        
        # Update Exit Reason
        sheet.update_cell(row, exit_reason_col, exit_reason)
        
        log_message = f"🚪 POSITION CLOSED: {ticker} | Exit: ₹{exit_price:.2f} | P&L: ₹{pnl_amount:+,.0f} | Reason: {exit_reason}"
        logger.info(log_message)
        log_email(log_message)
        
        # 🆕 SEND EMAIL NOTIFICATION
        if should_send_email and email_settings and result:
            sender = email_settings.get('sender_email')
            password = email_settings.get('sender_password')
            recipient = email_settings.get('recipient_email')
            
            if sender and password and recipient:
                # Determine email color based on exit reason
                if pnl_amount > 0:
                    header_color = "#28a745"  # Green for profit
                    status_emoji = "✅"
                else:
                    header_color = "#dc3545"  # Red for loss
                    status_emoji = "❌"
                
                subject = f"{status_emoji} Position Closed - {ticker} | P&L: ₹{pnl_amount:+,.0f}"
                
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <div style="background: {header_color}; color: white; padding: 20px; text-align: center;">
                            <h1 style="margin: 0;">{status_emoji} Position Closed</h1>
                            <p style="margin: 10px 0 0 0; font-size: 1.2em;">{ticker}</p>
                        </div>
                        <div style="padding: 20px;">
                            <div style="background: {'#d4edda' if pnl_amount > 0 else '#f8d7da'}; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid {header_color};">
                                <p style="margin: 0; font-size: 1.3em; color: {header_color};"><strong>Realized P&L: ₹{pnl_amount:+,.0f}</strong></p>
                                <p style="margin: 10px 0 0 0;"><strong>Exit Reason:</strong> {exit_reason}</p>
                            </div>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Position Type</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{'📈 LONG' if result['position_type'] == 'LONG' else '📉 SHORT'}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Entry Price</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['entry_price']:,.2f}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Exit Price</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{exit_price:,.2f}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Quantity</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result['quantity']} shares</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>P&L %</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; color: {header_color}; font-weight: bold;">
                                        {result['pnl_percent']:+.2f}%
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Holding Period</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result.get('holding_days', 0)} days</td>
                                </tr>
                                <tr>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Exit Date</strong></td>
                                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{exit_date}</td>
                                </tr>
                            </table>
                        </div>
                        <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
                            <p style="margin: 0;">Smart Portfolio Monitor - Position Closed</p>
                            <p style="margin: 5px 0 0 0;">{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                send_email_alert(subject, html_content, sender, password, recipient)
                log_email(f"📧 Email sent for position closure: {ticker}")
        
        return True, log_message
    
    except Exception as e:
        error_msg = f"Error marking {ticker} inactive: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

# ============================================================================
# EMAIL ALERT FUNCTIONS
# ============================================================================

def should_send_email(alert, email_settings, result):
    """
    Determine if email should be sent for this alert
    """
    email_type = alert.get('email_type', 'important')
    
    if email_type == 'critical' and email_settings.get('email_on_critical', True):
        return True
    elif email_type == 'target' and email_settings.get('email_on_target', True):
        return True
    elif email_type == 'sl_approach' and email_settings.get('email_on_sl_approach', True):
        return True
    elif email_type == 'sl_change' and email_settings.get('email_on_sl_change', True):
        return True
    elif email_type == 'target_change' and email_settings.get('email_on_target_change', True):
        return True
    elif email_type == 'important' and email_settings.get('email_on_important', True):
        return True
    
    return False

def create_alert_email_html(result, alert):
    """
    Create HTML content for alert email
    """
    status_colors = {
        'CRITICAL': '#dc3545',
        'HIGH': '#ffc107',
        'MEDIUM': '#17a2b8',
        'LOW': '#28a745'
    }
    
    priority_color = status_colors.get(alert['priority'], '#6c757d')
    pnl_color = '#28a745' if result['pnl_percent'] >= 0 else '#dc3545'
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <div style="background: {priority_color}; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">{alert['type']}</h1>
                <p style="margin: 10px 0 0 0; font-size: 1.2em;">{result['ticker']}</p>
            </div>
            
            <!-- Content -->
            <div style="padding: 20px;">
                
                <!-- Alert Message -->
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <p style="margin: 0; font-size: 1.1em;"><strong>Message:</strong> {alert['message']}</p>
                    <p style="margin: 10px 0 0 0; font-size: 1.2em; color: {priority_color};"><strong>Action:</strong> {alert['action']}</p>
                </div>
                
                <!-- Position Details -->
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Position Type</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{'📈 LONG' if result['position_type'] == 'LONG' else '📉 SHORT'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Entry Price</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['entry_price']:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Current Price</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['current_price']:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Stop Loss</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">₹{result['stop_loss']:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>P&L</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; color: {pnl_color}; font-weight: bold;">
                            {result['pnl_percent']:+.2f}% (₹{result['pnl_amount']:+,.0f})
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>SL Risk Score</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result['sl_risk']}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Quantity</strong></td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{result['quantity']} shares</td>
                    </tr>
                </table>
                
                <!-- Technical Summary -->
                <div style="margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 8px;">
                    <h3 style="margin: 0 0 10px 0;">Technical Summary</h3>
                    <p style="margin: 5px 0;">RSI: {result['rsi']:.1f} | MACD: {result['macd_signal']} | Momentum: {result['momentum_score']:.0f}/100</p>
                    <p style="margin: 5px 0;">Volume: {result['volume_signal'].replace('_', ' ')} ({result['volume_ratio']:.1f}x)</p>
                    <p style="margin: 5px 0;">Support: ₹{result['support']:,.2f} | Resistance: ₹{result['resistance']:,.2f}</p>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
                <p style="margin: 0;">Smart Portfolio Monitor v6.0</p>
                <p style="margin: 5px 0 0 0;">{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return html

def create_summary_email_html(results, critical_count, warning_count, portfolio_risk):
    """
    Create HTML content for summary email
    """
    ist_now = get_ist_now()
    
    # Build critical alerts section
    critical_html = ""
    for r in results:
        if r['overall_status'] == 'CRITICAL':
            critical_html += f"""
            <div style="background:#f8d7da; padding:15px; margin:10px 0; border-radius:8px; border-left:4px solid #dc3545;">
                <h3 style="margin:0; color:#721c24;">{r['ticker']} - {r['overall_action'].replace('_', ' ')}</h3>
                <p style="margin:5px 0;">Position: {r['position_type']} | P&L: {r['pnl_percent']:+.2f}%</p>
                <p style="margin:5px 0;">SL Risk: {r['sl_risk']}% | Current: ₹{r['current_price']:,.2f}</p>
                <p style="margin:5px 0; font-weight:bold;">⚡ {r['alerts'][0]['action'] if r['alerts'] else 'Review immediately'}</p>
            </div>
            """
    
    # Build warning alerts section
    warning_html = ""
    for r in results:
        if r['overall_status'] == 'WARNING':
            warning_html += f"""
            <div style="background:#fff3cd; padding:15px; margin:10px 0; border-radius:8px; border-left:4px solid #ffc107;">
                <h3 style="margin:0; color:#856404;">{r['ticker']} - {r['overall_action'].replace('_', ' ')}</h3>
                <p style="margin:5px 0;">Position: {r['position_type']} | P&L: {r['pnl_percent']:+.2f}%</p>
                <p style="margin:5px 0;">SL Risk: {r['sl_risk']}%</p>
            </div>
            """
    
    total_pnl = sum(r['pnl_amount'] for r in results)
    pnl_color = '#28a745' if total_pnl >= 0 else '#dc3545'
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">📊 Portfolio Alert Summary</h1>
                <p style="margin: 10px 0 0 0;">{ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
            </div>
            
            <!-- Summary Stats -->
            <div style="padding: 20px; display: flex; justify-content: space-around; background: #f8f9fa;">
                <div style="text-align: center;">
                    <h2 style="margin: 0; color: #dc3545;">{critical_count}</h2>
                    <p style="margin: 5px 0;">Critical</p>
                </div>
                <div style="text-align: center;">
                    <h2 style="margin: 0; color: #ffc107;">{warning_count}</h2>
                    <p style="margin: 5px 0;">Warning</p>
                </div>
                <div style="text-align: center;">
                    <h2 style="margin: 0; color: {pnl_color};">₹{total_pnl:+,.0f}</h2>
                    <p style="margin: 5px 0;">Total P&L</p>
                </div>
            </div>
            
            <!-- Portfolio Risk -->
            <div style="padding: 15px 20px; background: {portfolio_risk['risk_color']}20; border-left: 4px solid {portfolio_risk['risk_color']};">
                <p style="margin: 0;"><strong>Portfolio Risk:</strong> {portfolio_risk['risk_icon']} {portfolio_risk['risk_status']} ({portfolio_risk['portfolio_risk_pct']:.1f}%)</p>
            </div>
            
            <!-- Critical Alerts -->
            {f'<div style="padding: 20px;"><h2 style="color: #dc3545;">🚨 Critical Alerts</h2>{critical_html}</div>' if critical_html else ''}
            
            <!-- Warning Alerts -->
            {f'<div style="padding: 20px;"><h2 style="color: #ffc107;">⚠️ Warnings</h2>{warning_html}</div>' if warning_html else ''}
            
            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
                <p style="margin: 0;">Smart Portfolio Monitor v6.0</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return html

def send_portfolio_alerts(results, email_settings, portfolio_risk):
    """
    Send email alerts for portfolio positions
    """
    if not email_settings.get('enabled', False):
        return
    
    sender = email_settings.get('sender_email', '')
    password = email_settings.get('sender_password', '')
    recipient = email_settings.get('recipient_email', '')
    cooldown = email_settings.get('cooldown', 15)
    
    if not sender or not password or not recipient:
        return
    
    # Count alerts
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    
    # Send summary email for critical alerts
    if critical_count > 0:
        alert_hash = generate_alert_hash("PORTFOLIO", "SUMMARY_CRITICAL", str(critical_count))
        
        if can_send_email(alert_hash, cooldown):
            subject = f"🚨 CRITICAL: {critical_count} positions need attention!"
            html = create_summary_email_html(results, critical_count, warning_count, portfolio_risk)
            
            success, msg = send_email_alert(subject, html, sender, password, recipient)
            if success:
                mark_email_sent(alert_hash)
                log_email(f"Summary email sent: {critical_count} critical, {warning_count} warning")
            else:
                log_email(f"Summary email failed: {msg}")
    
    # Send individual alerts for specific conditions
    for result in results:
        for alert in result['alerts']:
            if should_send_email(alert, email_settings, result):
                alert_hash = generate_alert_hash(result['ticker'], alert['type'], str(result['current_price']))
                
                if can_send_email(alert_hash, cooldown):
                    subject = f"{alert['type']} - {result['ticker']}"
                    html = create_alert_email_html(result, alert)
                    
                    success, msg = send_email_alert(subject, html, sender, password, recipient)
                    if success:
                        mark_email_sent(alert_hash)
                        log_email(f"Alert sent: {result['ticker']} - {alert['type']}")
                    else:
                        log_email(f"Alert failed for {result['ticker']}: {msg}")
# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

def render_sidebar():
    """
    Render the sidebar with all settings and calculators
    Returns: dictionary with all settings
    """
    
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # =====================================================================
        # EMAIL CONFIGURATION
        # =====================================================================
        st.markdown("### 📧 Email Alerts")
        
        # ╔═══════════════════════════════════════════════════════════════════╗
        # ║  YOUR CREDENTIALS - EDIT THESE                                     ║
        # ╚═══════════════════════════════════════════════════════════════════╝
        YOUR_EMAIL = "pssundaar@gmail.com"
        YOUR_APP_PASSWORD = "ibpl ptdp oueh drjr"  # Your Gmail App Password
        YOUR_RECIPIENT = "shyamsunderpatri@gmail.com"
        
        # Check if credentials are configured
        credentials_configured = bool(
            YOUR_EMAIL and
            YOUR_APP_PASSWORD and
            "@" in YOUR_EMAIL and
            YOUR_EMAIL != "your-email@gmail.com" and
            YOUR_APP_PASSWORD != "xxxx xxxx xxxx xxxx"
        )
        
        # ✅ Initialize email state ONCE (stays OFF until you enable it)
        if 'email_alerts_enabled' not in st.session_state:
            st.session_state.email_alerts_enabled = False  # ✅ Default OFF

        email_enabled = st.checkbox(
            "Enable Email Alerts",
            value=st.session_state.email_alerts_enabled,  # ✅ Remember user's choice
            key="email_enabled_checkbox",
            help="Enable/disable all email notifications"
        )

        # ✅ Update session state when checkbox changes
        if email_enabled != st.session_state.email_alerts_enabled:
            st.session_state.email_alerts_enabled = email_enabled
            if email_enabled:
                st.success("✅ Email alerts ENABLED")
                log_email("Email alerts enabled by user")
            else:
                st.info("📧 Email alerts DISABLED")
                log_email("Email alerts disabled by user")
        
        # Email settings dictionary
        email_settings = {
            'enabled': False,
            'sender_email': '',
            'sender_password': '',
            'recipient_email': '',
            'email_on_critical': True,
            'email_on_target': True,
            'email_on_sl_approach': True,
            'email_on_sl_change': True,
            'email_on_target_change': True,
            'email_on_important': True,
            'cooldown': 15
        }
        
        if email_enabled:
            if credentials_configured:
                email_settings['enabled'] = True
                email_settings['sender_email'] = YOUR_EMAIL
                email_settings['sender_password'] = YOUR_APP_PASSWORD
                email_settings['recipient_email'] = YOUR_RECIPIENT if YOUR_RECIPIENT else YOUR_EMAIL
                
                st.success("✅ Email auto-configured!")
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"📤 From: {YOUR_EMAIL[:3]}***@gmail.com")
                with col2:
                    st.caption(f"📥 To: {email_settings['recipient_email'][:3]}***@gmail.com")
                
                # Test email button
                if st.button("📧 Send Test Email", type="secondary", use_container_width=True):
                    test_subject = "🧪 Test Email - Smart Portfolio Monitor"
                    test_html = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    color: white; padding: 20px; border-radius: 10px; text-align: center;">
                            <h1>✅ Test Email Successful!</h1>
                            <p>Your email configuration is working correctly.</p>
                            <p>Time: {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa; margin-top: 15px; border-radius: 10px;">
                            <p>You will receive alerts for:</p>
                            <ul>
                                <li>🔴 Critical alerts (SL hit, high risk)</li>
                                <li>🎯 Target achieved</li>
                                <li>⚠️ Approaching stop loss</li>
                                <li>🔄 Trail SL recommendations</li>
                                <li>📈 New target suggestions</li>
                            </ul>
                        </div>
                    </body>
                    </html>
                    """
                    success, msg = send_email_alert(
                        test_subject, test_html,
                        email_settings['sender_email'],
                        email_settings['sender_password'],
                        email_settings['recipient_email']
                    )
                    if success:
                        st.success("✅ Test email sent! Check your inbox.")
                        log_email(f"Test email sent to {email_settings['recipient_email']}")
                    else:
                        st.error(f"❌ Failed: {msg}")
                        log_email(f"Test email FAILED: {msg}")
            else:
                st.warning("⚠️ Configure credentials in code OR enter manually:")
                email_settings['sender_email'] = st.text_input("Your Gmail", placeholder="you@gmail.com")
                email_settings['sender_password'] = st.text_input(
                    "App Password", type="password",
                    help="16-character Gmail App Password"
                )
                email_settings['recipient_email'] = st.text_input(
                    "Send Alerts To", placeholder="recipient@gmail.com"
                )
                
                if email_settings['sender_email'] and email_settings['sender_password']:
                    email_settings['enabled'] = True
                    if not email_settings['recipient_email']:
                        email_settings['recipient_email'] = email_settings['sender_email']
                
                st.info("""
                **To auto-enable emails:**
                1. Open this Python file
                2. Find `YOUR_APP_PASSWORD = "xxxx xxxx xxxx xxxx"`
                3. Replace with your actual App Password
                4. Save and restart the app
                """)
            
            st.divider()
            
            # Alert Types
            st.markdown("#### 📬 Alert Types")
            col1, col2 = st.columns(2)
            with col1:
                email_settings['email_on_critical'] = st.checkbox("🔴 Critical", value=True)
                email_settings['email_on_target'] = st.checkbox("🎯 Target Hit", value=True)
                email_settings['email_on_sl_approach'] = st.checkbox("⚠️ Near SL", value=True)
            with col2:
                email_settings['email_on_sl_change'] = st.checkbox("🔄 Trail SL", value=True)
                email_settings['email_on_target_change'] = st.checkbox("📈 New Target", value=True)
                email_settings['email_on_important'] = st.checkbox("📋 Important", value=True)
            
            email_settings['cooldown'] = st.slider("⏱️ Cooldown (min)", 5, 60, 15)
            
            # Status display
            if email_settings['enabled']:
                enabled_count = sum([
                    email_settings['email_on_critical'],
                    email_settings['email_on_target'],
                    email_settings['email_on_sl_approach'],
                    email_settings['email_on_sl_change'],
                    email_settings['email_on_target_change'],
                    email_settings['email_on_important']
                ])
                st.markdown(f"""
                <div style='background:linear-gradient(135deg, #28a745, #218838); 
                            color:white; padding:10px; border-radius:8px; text-align:center; margin-top:10px;'>
                    📧 <strong>ACTIVE</strong> | {enabled_count}/6 alerts ON
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("☑️ Check 'Enable Email Alerts' above to activate")
        
        st.divider()
        
        # =====================================================================
        # AUTO-REFRESH
        # =====================================================================
        st.markdown("### 🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable Auto-Refresh", value=True)
        refresh_interval = st.slider("Refresh Interval (seconds)", 30, 300, 60)
        
        if not HAS_AUTOREFRESH:
            st.warning("⚠️ Install streamlit-autorefresh:\n`pip install streamlit-autorefresh`")
        
        st.divider()
        
        # =====================================================================
        # ALERT THRESHOLDS
        # =====================================================================
        st.markdown("### 🎯 Alert Thresholds")
        loss_threshold = st.slider("Alert on Loss %", -10.0, 0.0, -2.0, step=0.5)
        profit_threshold = st.slider("Alert on Profit %", 0.0, 20.0, 5.0, step=0.5)
        trail_sl_trigger = st.slider("Trail SL after Profit %", 0.5, 10.0, 2.0, step=0.5)
        sl_risk_threshold = st.slider("SL Risk Alert Threshold", 30, 90, 50)
        sl_approach_threshold = st.slider("SL Approach Warning %", 1.0, 5.0, 2.0, step=0.5)
        
        st.divider()
        
        # =====================================================================
        # ANALYSIS SETTINGS
        # =====================================================================
        st.markdown("### 📊 Analysis Settings")
        enable_volume_analysis = st.checkbox("Volume Confirmation", value=True)
        enable_sr_detection = st.checkbox("Support/Resistance", value=True)
        enable_multi_timeframe = st.checkbox("Multi-Timeframe Analysis", value=True)
        enable_correlation = st.checkbox("Correlation Analysis", value=False,
                                        help="May slow down loading")
        
        st.divider()
        
        # =====================================================================
        # POSITION SIZING CALCULATOR
        # =====================================================================
        st.markdown("### 💰 Position Sizing Calculator")
        
        with st.expander("Calculate Optimal Position Size", expanded=False):
            st.markdown("**Based on Risk Percentage**")
            
            calc_capital = st.number_input(
                "Total Capital (₹)",
                min_value=10000.0,
                value=100000.0,
                step=10000.0,
                key="pos_calc_capital"
            )
            
            calc_risk_pct = st.slider(
                "Risk per Trade (%)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
                key="pos_calc_risk"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                calc_entry = st.number_input(
                    "Entry Price (₹)",
                    min_value=1.0,
                    value=1500.0,
                    step=10.0,
                    key="pos_calc_entry"
                )
            with col2:
                calc_sl = st.number_input(
                    "Stop Loss (₹)",
                    min_value=1.0,
                    value=1450.0,
                    step=10.0,
                    key="pos_calc_sl"
                )
            
            if calc_entry > calc_sl:
                risk_amount = calc_capital * (calc_risk_pct / 100)
                risk_per_share = abs(calc_entry - calc_sl)
                position_size = int(risk_amount / risk_per_share)
                investment = position_size * calc_entry
                investment_pct = (investment / calc_capital) * 100
                
                st.success(f"**Buy {position_size} shares**")
                st.info(f"Investment: ₹{investment:,.0f} ({investment_pct:.1f}% of capital)")
                st.caption(f"Risk Amount: ₹{risk_amount:,.0f} | Risk/Share: ₹{risk_per_share:.2f}")
                
                # Additional info
                if investment_pct > 30:
                    st.warning("⚠️ Position is > 30% of capital. Consider reducing.")
            elif calc_entry < calc_sl:
                st.error("For LONG: Entry must be > Stop Loss")
                st.info("For SHORT: Use Entry < SL calculator below")
            else:
                st.info("Enter different Entry and Stop Loss prices")
        
        st.divider()
        
        # =====================================================================
        # RISK-REWARD CALCULATOR
        # =====================================================================
        st.markdown("### ⚖️ Risk-Reward Calculator")
        
        with st.expander("Check Trade Quality", expanded=False):
            rr_col1, rr_col2 = st.columns(2)
            
            with rr_col1:
                rr_entry = st.number_input("Entry (₹)", min_value=1.0, value=1500.0, step=10.0, key="rr_entry")
                rr_sl = st.number_input("SL (₹)", min_value=1.0, value=1450.0, step=10.0, key="rr_sl")
            
            with rr_col2:
                rr_target = st.number_input("Target (₹)", min_value=1.0, value=1600.0, step=10.0, key="rr_target")
                rr_type = st.selectbox("Type", ["LONG", "SHORT"], key="rr_type")
            
            if rr_type == "LONG":
                risk = rr_entry - rr_sl
                reward = rr_target - rr_entry
            else:
                risk = rr_sl - rr_entry
                reward = rr_entry - rr_target
            
            if risk > 0 and reward > 0:
                ratio = reward / risk
                
                if ratio >= 3:
                    quality = "🟢 EXCELLENT"
                    color = "green"
                elif ratio >= 2:
                    quality = "🟢 GOOD"
                    color = "green"
                elif ratio >= 1.5:
                    quality = "🟡 ACCEPTABLE"
                    color = "orange"
                else:
                    quality = "🔴 POOR"
                    color = "red"
                
                st.markdown(f"**Risk-Reward Ratio:** <span style='color:{color};font-size:1.5em;'>1:{ratio:.2f}</span>",
                           unsafe_allow_html=True)
                st.markdown(f"**Quality:** {quality}")
                st.caption(f"Risk: ₹{risk:.2f} | Reward: ₹{reward:.2f}")
                
                if ratio < 2:
                    st.warning("⚠️ Minimum recommended: 1:2")
                
                # Win rate needed to be profitable
                breakeven_winrate = (1 / (1 + ratio)) * 100
                st.caption(f"Breakeven Win Rate: {breakeven_winrate:.1f}%")
            elif risk <= 0:
                st.error("Invalid: Risk must be positive!")
            else:
                st.error("Invalid: Reward must be positive!")
        
        st.divider()
        
        # =====================================================================
        # QUICK TRADE LOGGER
        # =====================================================================
        st.markdown("### 📝 Log Closed Trade")
        
        with st.expander("Record Trade Result", expanded=False):
            log_ticker = st.text_input("Ticker", placeholder="RELIANCE", key="log_ticker")
            log_type = st.selectbox("Position", ["LONG", "SHORT"], key="log_type")
            
            log_col1, log_col2 = st.columns(2)
            with log_col1:
                log_entry = st.number_input("Entry ₹", min_value=1.0, value=100.0, step=1.0, key="log_entry")
                log_qty = st.number_input("Quantity", min_value=1, value=10, step=1, key="log_qty")
            with log_col2:
                log_exit = st.number_input("Exit ₹", min_value=1.0, value=110.0, step=1.0, key="log_exit")
                log_reason = st.selectbox("Exit Reason", [
                    "Target Hit", "Stop Loss", "Trail SL", "Manual Exit", "Partial Exit"
                ], key="log_reason")
            
            if st.button("📊 Log Trade", use_container_width=True, key="log_trade_btn"):
                if log_ticker:
                    log_trade(log_ticker.upper(), log_entry, log_exit, log_qty, log_type, log_reason)
                    st.success(f"✅ Trade logged: {log_ticker.upper()}")
                    
                    # Show result
                    if log_type == "LONG":
                        pnl = (log_exit - log_entry) * log_qty
                    else:
                        pnl = (log_entry - log_exit) * log_qty
                    
                    if pnl >= 0:
                        st.success(f"Profit: ₹{pnl:+,.0f}")
                    else:
                        st.error(f"Loss: ₹{pnl:+,.0f}")
                else:
                    st.error("Enter ticker symbol")
        
        st.divider()
        
        # =====================================================================
        # RESET STATS
        # =====================================================================
        st.markdown("### 🔄 Reset Data")
        
        with st.expander("Reset Options", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Reset Stats", use_container_width=True, key="reset_stats"):
                    st.session_state.performance_stats = {
                        'total_trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'total_profit': 0,
                        'total_loss': 0
                    }
                    st.session_state.trade_history = []
                    st.session_state.max_drawdown = 0
                    st.session_state.current_drawdown = 0
                    st.session_state.peak_portfolio_value = 0
                    st.success("✅ Stats reset!")
                    time.sleep(1)
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Clear Cache", use_container_width=True, key="clear_cache"):
                    st.cache_data.clear()
                    st.success("✅ Cache cleared!")
                    time.sleep(1)
                    st.rerun()
            
            if st.button("🗑️ Reset Email Log", use_container_width=True, key="reset_email"):
                st.session_state.email_log = []
                st.session_state.email_sent_alerts = {}
                st.session_state.last_email_time = {}
                st.success("✅ Email log reset!")
        # =====================================================================
        # DEBUG INFO
        # =====================================================================
        with st.expander("🔧 Debug Info"):
            st.write(f"Email configured: {'✅ Yes' if credentials_configured else '❌ No'}")
            st.write(f"Email enabled: {'✅ Yes' if email_settings['enabled'] else '❌ No'}")
            st.write(f"Auto-refresh: {'✅ Installed' if HAS_AUTOREFRESH else '❌ Not installed'}")
            st.write(f"Refresh interval: {refresh_interval}s")
            st.write(f"Trail SL trigger: {trail_sl_trigger}%")
            st.write(f"SL Risk threshold: {sl_risk_threshold}%")
            st.write(f"SL Approach threshold: {sl_approach_threshold}%")
            st.write(f"API calls this session: {st.session_state.api_call_count}")
            
            if email_settings['enabled']:
                st.write(f"Email cooldown: {email_settings['cooldown']} min")
            
            # Email log
                        # Email log
            if st.session_state.email_log:
                st.markdown("**Recent Email Log:**")
                for log_entry in st.session_state.email_log[-5:]:
                    st.caption(log_entry)
                
                # Download button for full log
                full_log = "\n".join(st.session_state.email_log)
                st.download_button(
                    "📥 Download Full Log",
                    full_log,
                    file_name=f"email_log_{get_ist_now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain",
                    key="download_email_log"
                )
        
        # Return all settings
        return {
            'email_settings': email_settings,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval,
            'loss_threshold': loss_threshold,
            'profit_threshold': profit_threshold,
            'trail_sl_trigger': trail_sl_trigger,
            'sl_risk_threshold': sl_risk_threshold,
            'sl_approach_threshold': sl_approach_threshold,
            'enable_volume_analysis': enable_volume_analysis,
            'enable_sr_detection': enable_sr_detection,
            'enable_multi_timeframe': enable_multi_timeframe,
            'enable_correlation': enable_correlation
        }

# ============================================================================
# DISPLAY COMPONENTS
# ============================================================================

def display_portfolio_risk_dashboard(portfolio_risk, sector_analysis):
    """
    Display the portfolio risk dashboard
    """
    st.markdown("### 🛡️ Portfolio Risk Analysis")
    
    # Main metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "💰 Total Capital",
            f"₹{portfolio_risk['total_capital']:,.0f}"
        )
    
    with col2:
        st.metric(
            "📈 Current Value",
            f"₹{portfolio_risk['current_value']:,.0f}",
            f"{portfolio_risk['total_pnl_pct']:+.2f}%"
        )
    
    with col3:
        st.metric(
            "🛡️ Total Risk",
            f"₹{portfolio_risk['total_risk_amount']:,.0f}",
            f"{portfolio_risk['portfolio_risk_pct']:.1f}%"
        )
    
    with col4:
        st.markdown(f"""
        <div style='text-align:center; padding:10px; background:linear-gradient(135deg, {portfolio_risk['risk_color']}, {portfolio_risk['risk_color']}90); 
                    border-radius:10px; color:white;'>
            <h3 style='margin:0;'>{portfolio_risk['risk_icon']} {portfolio_risk['risk_status']}</h3>
            <p style='margin:5px 0; font-size:0.8em;'>Risk Status</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.metric(
            "⚠️ Risky Positions",
            portfolio_risk['risky_positions'],
            f"of {portfolio_risk['total_positions']}"
        )
    
    # Risk recommendation
    if portfolio_risk['portfolio_risk_pct'] > 10:
        st.error(f"🚨 Portfolio risk is HIGH ({portfolio_risk['portfolio_risk_pct']:.1f}%). Consider reducing exposure!")
    elif portfolio_risk['portfolio_risk_pct'] > 5:
        st.warning(f"⚠️ Portfolio risk is MEDIUM ({portfolio_risk['portfolio_risk_pct']:.1f}%). Monitor closely.")
    else:
        st.success(f"✅ Portfolio risk is SAFE ({portfolio_risk['portfolio_risk_pct']:.1f}%).")
    
    # Drawdown info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📉 Current Drawdown", f"{st.session_state.current_drawdown:.2f}%")
    with col2:
        st.metric("📊 Max Drawdown", f"{st.session_state.max_drawdown:.2f}%")
    with col3:
        st.metric("🎯 Avg SL Risk", f"{portfolio_risk['avg_sl_risk']:.1f}%")
    
    # Sector exposure warnings
    if sector_analysis['warnings']:
        st.markdown("#### ⚠️ Concentration Warnings")
        for warning in sector_analysis['warnings']:
            st.warning(warning)

def display_performance_dashboard():
    """
    Display performance statistics dashboard
    """
    st.markdown("### 📈 Performance Dashboard")
    
    perf_stats = get_performance_stats()
    
    if perf_stats:
        # Main stats row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📊 Total Trades", perf_stats['total_trades'])
        
        with col2:
            win_color = "normal" if perf_stats['win_rate'] >= 50 else "inverse"
            st.metric("🎯 Win Rate", f"{perf_stats['win_rate']:.1f}%")
        
        with col3:
            st.metric("✅ Wins / ❌ Losses", f"{perf_stats['wins']} / {perf_stats['losses']}")
        
        with col4:
            exp_color = "normal" if perf_stats['expectancy'] >= 0 else "inverse"
            st.metric("📈 Expectancy", f"₹{perf_stats['expectancy']:,.0f}")
        
        with col5:
            pf_color = "normal" if perf_stats['profit_factor'] >= 1 else "inverse"
            pf_display = f"{perf_stats['profit_factor']:.2f}" if perf_stats['profit_factor'] < 100 else "∞"
            st.metric("⚖️ Profit Factor", pf_display)
        
        # Second row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Net Profit", f"₹{perf_stats['net_profit']:+,.0f}")
        
        with col2:
            st.metric("📈 Avg Win", f"₹{perf_stats['avg_win']:,.0f}")
        
        with col3:
            st.metric("📉 Avg Loss", f"₹{perf_stats['avg_loss']:,.0f}")
        
        with col4:
            if perf_stats['avg_loss'] > 0:
                rr_actual = perf_stats['avg_win'] / perf_stats['avg_loss']
                st.metric("⚖️ Actual R:R", f"1:{rr_actual:.2f}")
            else:
                st.metric("⚖️ Actual R:R", "N/A")
        
        # Performance assessment
        if perf_stats['win_rate'] >= 60 and perf_stats['profit_factor'] >= 1.5:
            st.success("🌟 Excellent performance! Keep up the good work.")
        elif perf_stats['win_rate'] >= 50 and perf_stats['profit_factor'] >= 1.2:
            st.info("👍 Good performance. Room for improvement.")
        elif perf_stats['win_rate'] >= 40 and perf_stats['profit_factor'] >= 1.0:
            st.warning("⚠️ Marginal performance. Review your strategy.")
        else:
            st.error("🚨 Poor performance. Strategy review needed.")
        
        # Trade history
        if st.session_state.trade_history:
            st.markdown("#### 📋 Recent Trades")
            
            history_data = []
            for trade in reversed(st.session_state.trade_history[-10:]):
                history_data.append({
                    'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Ticker': trade['ticker'],
                    'Type': trade['type'],
                    'Entry': f"₹{trade['entry']:.2f}",
                    'Exit': f"₹{trade['exit']:.2f}",
                    'Qty': trade['quantity'],
                    'P&L': f"₹{trade['pnl']:+,.0f}",
                    'P&L %': f"{trade['pnl_pct']:+.2f}%",
                    'Result': '✅' if trade['win'] else '❌',
                    'Reason': trade['reason']
                })
            
            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history, use_container_width=True, hide_index=True)
            
            # Export button
            csv = df_history.to_csv(index=False)
            st.download_button(
                "📥 Download Trade History",
                csv,
                file_name=f"trade_history_{get_ist_now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    else:
        st.info("📊 No trades logged yet. Use the 'Log Closed Trade' feature in the sidebar to record trades.")
        
        # Sample explanation
        st.markdown("""
        **How to track performance:**
        1. When you close a trade, go to sidebar → 'Log Closed Trade'
        2. Enter the trade details (entry, exit, quantity)
        3. Click 'Log Trade'
        4. View your statistics here!
        """)

def display_sector_analysis(sector_analysis):
    """
    Display sector exposure analysis
    """
    st.markdown("### 🏢 Sector Exposure")
    
    if not sector_analysis['sectors']:
        st.info("No sector data available")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Pie chart
        sector_data = []
        for sector, data in sector_analysis['sectors'].items():
            sector_data.append({
                'Sector': sector,
                'Percentage': data['percentage'],
                'Value': data['value']
            })
        
        df_sector = pd.DataFrame(sector_data)
        
        fig = px.pie(
            df_sector,
            values='Percentage',
            names='Sector',
            title='Sector Distribution',
            color_discrete_sequence=px.colors.qualitative.Set3,
            hole=0.3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### Sector Breakdown")
        
        for sector, data in list(sector_analysis['sectors'].items())[:8]:
            pnl_color = "green" if data['pnl'] >= 0 else "red"
            st.markdown(f"""
            **{sector}** ({data['percentage']:.1f}%)
            - Stocks: {data['count']}
            - Value: ₹{data['value']:,.0f}
            - P&L: <span style='color:{pnl_color}'>₹{data['pnl']:+,.0f}</span>
            """, unsafe_allow_html=True)
            st.divider()
        
        # Diversification score
        score = sector_analysis['diversification_score']
        if score >= 70:
            score_color = "#28a745"
            score_text = "Well Diversified"
        elif score >= 50:
            score_color = "#ffc107"
            score_text = "Moderately Diversified"
        else:
            score_color = "#dc3545"
            score_text = "Poorly Diversified"
        
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:{score_color}20; border-radius:10px; border-left:4px solid {score_color};'>
            <h2 style='margin:0; color:{score_color};'>{score}/100</h2>
            <p style='margin:5px 0;'>{score_text}</p>
        </div>
        """, unsafe_allow_html=True)

def display_correlation_analysis(results, enable_correlation):
    """
    Display correlation analysis
    """
    st.markdown("### 🔗 Correlation Analysis")
    
    if not enable_correlation:
        st.info("Correlation analysis is disabled. Enable it in sidebar settings.")
        return
    
    tickers = [r['ticker'] for r in results]
    
    if len(tickers) < 2:
        st.warning("Need at least 2 positions for correlation analysis")
        return
    
    # Check cache
    cache_valid = (
        st.session_state.correlation_matrix is not None and
        st.session_state.last_correlation_calc is not None and
        (datetime.now() - st.session_state.last_correlation_calc).seconds < 300
    )
    
    if not cache_valid:
        with st.spinner("Calculating correlations..."):
            corr_matrix, status = calculate_correlation_matrix(tickers)
            if corr_matrix is not None:
                st.session_state.correlation_matrix = corr_matrix
                st.session_state.last_correlation_calc = datetime.now()
    else:
        corr_matrix = st.session_state.correlation_matrix
        status = "Cached"
    
    if corr_matrix is not None:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Heatmap
            fig = px.imshow(
                corr_matrix,
                labels=dict(x="Stock", y="Stock", color="Correlation"),
                x=corr_matrix.columns,
                y=corr_matrix.index,
                color_continuous_scale="RdYlGn",
                zmin=-1, zmax=1
            )
            fig.update_layout(title="Correlation Matrix", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            high_corr, avg_corr, corr_status = analyze_correlation_risk(corr_matrix)
            
            st.markdown(f"**Average Correlation:** {avg_corr:.2f}")
            st.markdown(f"**Status:** {corr_status}")
            
            if high_corr:
                st.markdown("#### ⚠️ High Correlations")
                for hc in high_corr[:5]:
                    risk_color = "red" if hc['risk'] == 'HIGH' else "orange"
                    st.markdown(f"""
                    <div style='background:{risk_color}20; padding:8px; margin:5px 0; border-radius:5px;'>
                        <strong>{hc['pair']}</strong>: {hc['correlation']:.2f}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No highly correlated pairs found")
    else:
        st.error(f"Could not calculate correlations: {status}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """
    Main application entry point
    """
    
    # Header
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v6.0</h1>', unsafe_allow_html=True)
    
    # Render sidebar and get settings
    settings = render_sidebar()
    
    # Market Status
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    
    # =========================================================================
    # PROFESSIONAL HEADER BAR
    # =========================================================================
    
    # Status color mapping
    status_color_map = {
        'OPEN': '#00d4aa',
        'CLOSED': '#ff4757',
        'PRE-MARKET': '#ffa502',
        'WEEKEND': '#4a5568'
    }
    status_color = status_color_map.get(market_status, '#4a5568')
    
    st.markdown(f"""
    <div style='display:flex; justify-content:space-between; align-items:center; 
                background:#0f1419; border:1px solid #1e2a3a; border-radius:12px; 
                padding:12px 24px; margin-bottom:15px;'>
        <div style='display:flex; align-items:center; gap:20px;'>
            <div>
                <span style='font-size:1.4rem; font-weight:800; 
                      background:linear-gradient(135deg, #00d4aa, #00b4d8);
                      -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>
                    SPM
                </span>
                <span style='color:#4a5568; font-size:0.65rem; margin-left:5px; 
                      letter-spacing:0.1em;'>v6.0</span>
            </div>
            <div style='height:24px; width:1px; background:#1e2a3a;'></div>
            <div>
                <span style='display:inline-block; width:8px; height:8px; 
                      border-radius:50%; background:{status_color}; 
                      margin-right:6px; animation: {"blink-dot 1.5s infinite" if is_open else "none"};'></span>
                <span style='color:{status_color}; font-weight:600; font-size:0.85rem;'>{market_status}</span>
                <span style='color:#4a5568; font-size:0.7rem; margin-left:8px;'>{market_msg}</span>
            </div>
        </div>
        <div style='display:flex; align-items:center; gap:20px;'>
            <div style='text-align:right;'>
                <div style='color:#e2e8f0; font-size:1.1rem; font-weight:700; 
                     font-family:"JetBrains Mono","Fira Code",monospace;'>
                    {ist_now.strftime('%H:%M:%S')}
                </div>
                <div style='color:#4a5568; font-size:0.65rem; letter-spacing:0.05em;'>
                    {ist_now.strftime('%a, %d %b %Y')} IST
                </div>
            </div>
        </div>
    </div>
    <style>
        @keyframes blink-dot {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}
    </style>
    """, unsafe_allow_html=True)
    
    # Refresh button row
    col_spacer, col_refresh = st.columns([5, 1])
    with col_refresh:
        if st.button("⟳ REFRESH", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # =========================================================================
    # ✅ GAP 1: MARKET HEALTH DISPLAY (OUTSIDE COLUMNS - FULL WIDTH!)
    # =========================================================================
    st.divider()
    
    market_health = get_market_health()
    
    if market_health:
        # Color mapping for health
        health_color = market_health['color']
        if market_health['health_score'] >= 70:
            health_gradient = 'linear-gradient(135deg, #00d4aa, #00b894)'
            ring_shadow = 'rgba(0, 212, 170, 0.3)'
        elif market_health['health_score'] >= 50:
            health_gradient = 'linear-gradient(135deg, #ffa502, #ff9f43)'
            ring_shadow = 'rgba(255, 165, 2, 0.3)'
        elif market_health['health_score'] >= 30:
            health_gradient = 'linear-gradient(135deg, #ff9f43, #ee5a24)'
            ring_shadow = 'rgba(238, 90, 36, 0.3)'
        else:
            health_gradient = 'linear-gradient(135deg, #ff4757, #ff3838)'
            ring_shadow = 'rgba(255, 71, 87, 0.3)'
        
        nifty_change_color = '#00d4aa' if market_health['nifty_change'] >= 0 else '#ff4757'
        nifty_arrow = '▲' if market_health['nifty_change'] >= 0 else '▼'
        
        st.markdown(f"""
        <div style='background:#0f1419; border:1px solid #1e2a3a; border-radius:12px; 
                    padding:20px 24px; margin:10px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:15px;'>
                
                <!-- Health Score Ring -->
                <div style='text-align:center; min-width:100px;'>
                    <div style='width:72px; height:72px; border-radius:50%; 
                                background:{health_gradient};
                                display:flex; align-items:center; justify-content:center;
                                box-shadow: 0 0 20px {ring_shadow};
                                margin:0 auto;'>
                        <span style='font-size:1.6rem; font-weight:800; color:#0a0e17;'>
                            {market_health['health_score']}
                        </span>
                    </div>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-top:6px;'>HEALTH</div>
                </div>
                
                <!-- Status -->
                <div style='min-width:120px;'>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:4px;'>MARKET</div>
                    <div style='color:{health_color}; font-size:1.1rem; font-weight:700;'>
                        {market_health['icon']} {market_health['status']}
                    </div>
                    <div style='color:#4a5568; font-size:0.75rem; margin-top:4px;'>
                        {market_health['action']}
                    </div>
                </div>
                
                <!-- NIFTY -->
                <div style='min-width:130px; text-align:center; padding:0 15px; 
                            border-left:1px solid #1e2a3a; border-right:1px solid #1e2a3a;'>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:4px;'>NIFTY 50</div>
                    <div style='color:#e2e8f0; font-size:1.2rem; font-weight:700; 
                                font-family:"JetBrains Mono",monospace;'>
                        {market_health['nifty_price']:,.0f}
                    </div>
                    <div style='color:{nifty_change_color}; font-size:0.8rem; font-weight:600;'>
                        {nifty_arrow} {market_health['nifty_change']:+.2f}%
                    </div>
                </div>
                
                <!-- RSI -->
                <div style='text-align:center; min-width:60px;'>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:4px;'>RSI</div>
                    <div style='color:#e2e8f0; font-size:1.2rem; font-weight:700;'>
                        {market_health['nifty_rsi']:.0f}
                    </div>
                </div>
                
                <!-- VIX -->
                <div style='text-align:center; min-width:60px;'>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:4px;'>VIX</div>
                    <div style='color:{"#ff4757" if market_health["vix"] > 20 else "#ffa502" if market_health["vix"] > 15 else "#00d4aa"}; 
                                font-size:1.2rem; font-weight:700;'>
                        {market_health['vix']:.1f}
                    </div>
                </div>
                
                <!-- Trend -->
                <div style='text-align:center; min-width:80px;'>
                    <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:4px;'>TREND</div>
                    <div style='color:{"#00d4aa" if market_health["above_sma20"] else "#ff4757"}; 
                                font-size:0.85rem; font-weight:600;'>
                        {"▲ ABOVE" if market_health["above_sma20"] else "▼ BELOW"} SMA20
                    </div>
                    <div style='color:{"#00d4aa" if market_health["above_sma50"] else "#ff4757"}; 
                                font-size:0.75rem;'>
                        {"▲ ABOVE" if market_health["above_sma50"] else "▼ BELOW"} SMA50
                    </div>
                </div>
                
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Auto-adjust SL thresholds
        if market_health['sl_adjustment'] == 'AGGRESSIVE':
            settings['sl_risk_threshold'] = max(30, settings['sl_risk_threshold'] - 20)
            st.markdown(f"""
            <div class='alert-critical'>
                ⚠️ SL Risk threshold auto-adjusted to <strong>{settings['sl_risk_threshold']}%</strong> — Weak market detected
            </div>
            """, unsafe_allow_html=True)
        elif market_health['sl_adjustment'] == 'TIGHTEN':
            settings['sl_risk_threshold'] = max(35, settings['sl_risk_threshold'] - 10)
            st.markdown(f"""
            <div class='alert-warning'>
                ℹ️ SL Risk threshold adjusted to <strong>{settings['sl_risk_threshold']}%</strong> — Cautious mode
            </div>
            """, unsafe_allow_html=True)
    
    else:
        market_health = None
        st.markdown("""
        <div class='alert-warning'>⚠️ Unable to fetch market health data</div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # =========================================================================
    # SETTINGS SUMMARY
    # =========================================================================
    with st.expander("⚙️ Current Settings", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Trail SL Trigger", f"{settings['trail_sl_trigger']}%")
        with col2:
            st.metric("SL Risk Alert", f"{settings['sl_risk_threshold']}%")
        with col3:
            st.metric("Refresh Interval", f"{settings['refresh_interval']}s")
        with col4:
            st.metric("MTF Analysis", "✅ On" if settings['enable_multi_timeframe'] else "❌ Off")
        with col5:
            st.metric("Email Alerts", "✅ On" if settings['email_settings']['enabled'] else "❌ Off")
    
    st.divider()
    
    # Load Portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No positions found!")
        
        # Show sample format
        st.markdown("### 📋 Expected Google Sheets Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY'],
            'Position': ['LONG', 'LONG', 'SHORT'],
            'Entry_Price': [2450.00, 3580.00, 1520.00],
            'Quantity': [10, 5, 8],
            'Stop_Loss': [2380.00, 3480.00, 1580.00],
            'Target_1': [2550.00, 3720.00, 1420.00],
            'Target_2': [2650.00, 3850.00, 1350.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    
    # Validate Portfolio Data
    is_valid, errors, warnings = validate_portfolio(portfolio)
    
    if errors:
        st.error("❌ Portfolio Validation Failed!")
        for error in errors:
            st.error(error)
        st.stop()
    
    if warnings:
        with st.expander("⚠️ Validation Warnings", expanded=False):
            for warning in warnings:
                st.warning(warning)
        
        # Show sample format
        st.markdown("### 📋 Expected Google Sheets Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY'],
            'Position': ['LONG', 'LONG', 'SHORT'],
            'Entry_Price': [2450.00, 3580.00, 1520.00],
            'Quantity': [10, 5, 8],
            'Stop_Loss': [2380.00, 3480.00, 1580.00],
            'Target_1': [2550.00, 3720.00, 1420.00],
            'Target_2': [2650.00, 3850.00, 1350.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    
    # =========================================================================
    # ANALYZE ALL POSITIONS
    # =========================================================================
    results = []
    progress_bar = st.progress(0, text="Analyzing positions...")
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {ticker}...")
        
        # Get entry date if available
        entry_date = row.get('Entry_Date', None)
        
        result = smart_analyze_position(
            ticker,
            str(row['Position']).upper().strip(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            settings['trail_sl_trigger'],
            settings['sl_risk_threshold'],
            settings['sl_approach_threshold'],
            settings['enable_multi_timeframe'],
            entry_date
        )
        
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio), text=f"Completed {ticker}")
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch stock data. Check internet connection and try again.")
        return
    
    # =========================================================================
    # CALCULATE PORTFOLIO METRICS
    # =========================================================================
    
    # Portfolio risk
    portfolio_risk = calculate_portfolio_risk(results)
    
    # Sector analysis
    sector_analysis = analyze_sector_exposure(results)
    
    # Update drawdown
    update_drawdown(portfolio_risk['current_value'])
    
    # Summary counts
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    pnl_percent_total = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    opportunity_count = sum(1 for r in results if r['overall_status'] == 'OPPORTUNITY')
    success_count = sum(1 for r in results if r['overall_status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['overall_status'] == 'GOOD')
    
    # =========================================================================
    # SEND EMAIL ALERTS
    # =========================================================================
    if settings['email_settings']['enabled']:
        send_portfolio_alerts(results, settings['email_settings'], portfolio_risk)
    
    # =========================================================================
    # DISPLAY SUMMARY CARDS
    # =========================================================================
        # Portfolio summary values
    total_current_value = sum(r['current_price'] * r['quantity'] for r in results)
    pnl_color_class = 'pnl-positive' if total_pnl >= 0 else 'pnl-negative'
    pnl_sign = '+' if total_pnl >= 0 else ''
    
    st.markdown(f"""
    <div class='summary-grid'>
        <div class='summary-card' style='border-top:3px solid {"#00d4aa" if total_pnl >= 0 else "#ff4757"};'>
            <div class='summary-card-label'>Total P&L</div>
            <div class='summary-card-value {pnl_color_class}'>₹{total_pnl:+,.0f}</div>
            <div class='summary-card-delta {pnl_color_class}'>{pnl_percent_total:+.2f}%</div>
        </div>
        <div class='summary-card'>
            <div class='summary-card-label'>Portfolio Value</div>
            <div class='summary-card-value'>₹{total_current_value:,.0f}</div>
            <div class='summary-card-delta' style='color:#4a5568;'>{len(results)} positions</div>
        </div>
        <div class='summary-card' style='border-top:3px solid #ff4757;'>
            <div class='summary-card-label'>Critical</div>
            <div class='summary-card-value' style='color:#ff4757;'>{critical_count}</div>
            <div class='summary-card-delta' style='color:#ff4757;'>{"⚠ ACTION NEEDED" if critical_count > 0 else "✓ Clear"}</div>
        </div>
        <div class='summary-card' style='border-top:3px solid #ffa502;'>
            <div class='summary-card-label'>Warning</div>
            <div class='summary-card-value' style='color:#ffa502;'>{warning_count}</div>
            <div class='summary-card-delta' style='color:#ffa502;'>{"Monitor" if warning_count > 0 else "✓ Clear"}</div>
        </div>
        <div class='summary-card' style='border-top:3px solid #00d4aa;'>
            <div class='summary-card-label'>Good</div>
            <div class='summary-card-value' style='color:#00d4aa;'>{good_count}</div>
            <div class='summary-card-delta' style='color:#00d4aa;'>On track</div>
        </div>
        <div class='summary-card' style='border-top:3px solid #00b4d8;'>
            <div class='summary-card-label'>Opportunity</div>
            <div class='summary-card-value' style='color:#00b4d8;'>{opportunity_count}</div>
            <div class='summary-card-delta' style='color:#00b4d8;'>Extended</div>
        </div>
        <div class='summary-card' style='border-top:3px solid #7b68ee;'>
            <div class='summary-card-label'>Target Hit</div>
            <div class='summary-card-value' style='color:#7b68ee;'>{success_count}</div>
            <div class='summary-card-delta' style='color:#7b68ee;'>Book profits</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # =========================================================================
    # MAIN TABS
    # =========================================================================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7= st.tabs([
        "📊 Dashboard",
        "📈 Charts", 
        "🔔 Alerts",
        "📉 MTF Analysis",
        "🛡️ Portfolio Risk",
        "📈 Performance",
        "📋 Details"
    ])
    
    # =========================================================================
    # TAB 1: DASHBOARD
    # =========================================================================
    with tab1:
        # Sort by status priority
        status_order = {'CRITICAL': 0, 'WARNING': 1, 'OPPORTUNITY': 2, 'SUCCESS': 3, 'GOOD': 4, 'OK': 5}
        sorted_results = sorted(results, key=lambda x: status_order.get(x['overall_status'], 5))
        
        for r in sorted_results:
            # Status styling
            status_config = {
                'CRITICAL': {'class': 'status-critical', 'border': '#ff4757', 'icon': '🔴'},
                'WARNING': {'class': 'status-warning', 'border': '#ffa502', 'icon': '🟡'},
                'OPPORTUNITY': {'class': 'status-info', 'border': '#00b4d8', 'icon': '🔵'},
                'SUCCESS': {'class': 'status-success', 'border': '#00d4aa', 'icon': '✅'},
                'GOOD': {'class': 'status-success', 'border': '#00d4aa', 'icon': '🟢'},
                'OK': {'class': 'status-neutral', 'border': '#2d3a4a', 'icon': '⚪'}
            }
            cfg = status_config.get(r['overall_status'], status_config['OK'])
            
            pnl_class = 'pnl-positive' if r['pnl_percent'] >= 0 else 'pnl-negative'
            pnl_arrow = '▲' if r['pnl_percent'] >= 0 else '▼'
            badge_class = 'badge-long' if r['position_type'] == 'LONG' else 'badge-short'
            
            # Build expander label
            expander_label = (
                f"{cfg['icon']} **{r['ticker']}** │ "
                f"{'LONG' if r['position_type'] == 'LONG' else 'SHORT'} │ "
                f"{pnl_arrow} {r['pnl_percent']:+.2f}% (₹{r['pnl_amount']:+,.0f}) │ "
                f"Risk: {r['sl_risk']}% │ "
                f"{r['overall_action'].replace('_', ' ')}"
            )
            
            with st.expander(
                expander_label,
                expanded=(r['overall_status'] in ['CRITICAL', 'WARNING', 'OPPORTUNITY', 'SUCCESS'])
            ):
                # ── EMERGENCY EXIT CHECK ──
                is_emergency, emergency_reasons, urgency_level = detect_emergency_exit(r, market_health)
                
                if is_emergency:
                    if urgency_level == "CRITICAL":
                        st.markdown("""
                        <div class='emergency-banner'>
                            🚨 EMERGENCY EXIT REQUIRED — ACT NOW 🚨
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class='alert-critical'>
                            <strong>⚠️ HIGH URGENCY</strong> — Consider immediate exit
                        </div>
                        """, unsafe_allow_html=True)
                    
                    for reason in emergency_reasons:
                        st.markdown(f"""
                        <div class='alert-critical' style='padding:8px 14px; margin:4px 0;'>
                            {reason}
                        </div>
                        """, unsafe_allow_html=True)
                
                # ── STOCK HISTORY WARNING ──
                stock_history = get_stock_performance_history(r['ticker'])
                
                if stock_history['has_history'] and (stock_history['win_rate'] < 45 or stock_history.get('expectancy', 0) < 0):
                    st.markdown(f"""
                    <div class='alert-warning' style='padding:10px 14px;'>
                        <strong>{stock_history['icon']} Historical: {stock_history['quality']}</strong> — 
                        Win Rate: {stock_history['win_rate']:.0f}% | 
                        Expectancy: ₹{stock_history.get('expectancy', 0):+,.0f} | 
                        {stock_history['recommendation']}
                    </div>
                    """, unsafe_allow_html=True)
                
                # ── POSITION HEADER CARD ──
                pnl_color_hex = '#00d4aa' if r['pnl_percent'] >= 0 else '#ff4757'
                day_color = '#00d4aa' if r['day_change'] >= 0 else '#ff4757'
                
                st.markdown(f"""
                <div class='position-card'>
                    <div class='position-header'>
                        <div>
                            <span class='position-ticker'>{r['ticker']}</span>
                            <span class='position-badge {badge_class}' style='margin-left:10px;'>
                                {"▲ LONG" if r['position_type'] == 'LONG' else "▼ SHORT"}
                            </span>
                            <span class='{cfg["class"]}' style='margin-left:8px;'>
                                {r['overall_action'].replace('_', ' ')}
                            </span>
                        </div>
                        <div style='text-align:right;'>
                            <div style='font-size:1.2rem; font-weight:700; color:{pnl_color_hex};
                                        font-family:"JetBrains Mono",monospace;'>
                                {pnl_arrow} ₹{r['pnl_amount']:+,.0f}
                            </div>
                            <div style='font-size:0.8rem; color:{pnl_color_hex};'>{r['pnl_percent']:+.2f}%</div>
                        </div>
                    </div>
                    <div class='position-body'>
                        <div class='position-metrics'>
                            <div class='position-metric'>
                                <div class='position-metric-label'>ENTRY</div>
                                <div class='position-metric-value'>₹{r['entry_price']:,.2f}</div>
                            </div>
                            <div class='position-metric'>
                                <div class='position-metric-label'>CURRENT</div>
                                <div class='position-metric-value' style='color:{pnl_color_hex};'>₹{r['current_price']:,.2f}</div>
                            </div>
                            <div class='position-metric'>
                                <div class='position-metric-label'>DAY CHG</div>
                                <div class='position-metric-value' style='color:{day_color};'>{r['day_change']:+.2f}%</div>
                            </div>
                            <div class='position-metric'>
                                <div class='position-metric-label'>QTY</div>
                                <div class='position-metric-value'>{r['quantity']}</div>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # ── LEVELS ROW ──
                st.markdown(f"""
                <div style='background:#0f1419; border:1px solid #1e2a3a; border-radius:10px; 
                            padding:14px 18px; margin:8px 0;'>
                    <div style='color:#4a5568; font-size:0.65rem; text-transform:uppercase; 
                                letter-spacing:0.1em; margin-bottom:10px;'>KEY LEVELS</div>
                    <div class='level-row'>
                        <span class='level-label'>Stop Loss</span>
                        <span>
                            <span class='level-value' style='color:#ff4757;'>₹{r['stop_loss']:,.2f}</span>
                            {'<span class="level-tag" style="background:rgba(255,71,87,0.2); color:#ff4757; margin-left:6px;">HIT!</span>' if r['sl_hit'] else ''}
                            {'<span class="level-tag" style="background:rgba(255,165,2,0.2); color:#ffa502; margin-left:6px;">NEAR</span>' if r['approaching_sl'] and not r['sl_hit'] else ''}
                        </span>
                    </div>
                    <div class='level-row'>
                        <span class='level-label'>Target 1</span>
                        <span>
                            <span class='level-value' style='color:#00d4aa;'>₹{r['target1']:,.2f}</span>
                            {'<span class="level-tag" style="background:rgba(0,212,170,0.2); color:#00d4aa; margin-left:6px;">✓ HIT</span>' if r['target1_hit'] else ''}
                        </span>
                    </div>
                    <div class='level-row'>
                        <span class='level-label'>Target 2</span>
                        <span>
                            <span class='level-value' style='color:#00b894;'>₹{r['target2']:,.2f}</span>
                            {'<span class="level-tag" style="background:rgba(0,184,148,0.2); color:#00b894; margin-left:6px;">✓ HIT</span>' if r['target2_hit'] else ''}
                        </span>
                    </div>
                    {'<div class="level-row"><span class="level-label">Trail SL</span><span><span class="level-value" style="color:#7b68ee;">₹' + f"{r['trail_stop']:,.2f}" + '</span><span class="level-tag" style="background:rgba(123,104,238,0.2); color:#9c88ff; margin-left:6px;">MOVE ↑</span></span></div>' if r['should_trail'] else ''}
                    <div class='level-row'>
                        <span class='level-label'>Support</span>
                        <span class='level-value'>₹{r['support']:,.2f} <span style='color:#4a5568; font-size:0.65rem;'>({r['support_strength']})</span></span>
                    </div>
                    <div class='level-row' style='border-bottom:none;'>
                        <span class='level-label'>Resistance</span>
                        <span class='level-value'>₹{r['resistance']:,.2f} <span style='color:#4a5568; font-size:0.65rem;'>({r['resistance_strength']})</span></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # ── SMART SCORES ──
                sl_color = '#ff4757' if r['sl_risk'] >= 70 else '#ffa502' if r['sl_risk'] >= 50 else '#00d4aa'
                mom_color = '#00d4aa' if r['momentum_score'] >= 60 else '#ffa502' if r['momentum_score'] >= 40 else '#ff4757'
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f"""
                    <div class='score-gauge'>
                        <div class='score-value' style='color:{sl_color};'>{r['sl_risk']}%</div>
                        <div class='score-label'>SL RISK</div>
                        <div class='score-bar'>
                            <div class='score-bar-fill' style='width:{r["sl_risk"]}%; background:{sl_color};'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if r['sl_reasons']:
                        for reason in r['sl_reasons'][:2]:
                            st.caption(reason)
                
                with col2:
                    st.markdown(f"""
                    <div class='score-gauge'>
                        <div class='score-value' style='color:{mom_color};'>{r['momentum_score']:.0f}</div>
                        <div class='score-label'>MOMENTUM</div>
                        <div class='score-bar'>
                            <div class='score-bar-fill' style='width:{r["momentum_score"]}%; background:{mom_color};'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(r['momentum_trend'])
                
                with col3:
                    if r['target1_hit']:
                        up_color = '#00d4aa' if r['upside_score'] >= 60 else '#ffa502' if r['upside_score'] >= 40 else '#ff4757'
                        st.markdown(f"""
                        <div class='score-gauge'>
                            <div class='score-value' style='color:{up_color};'>{r['upside_score']}%</div>
                            <div class='score-label'>UPSIDE</div>
                            <div class='score-bar'>
                                <div class='score-bar-fill' style='width:{r["upside_score"]}%; background:{up_color};'></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        if r['upside_score'] >= 60:
                            st.caption(f"New Target: ₹{r['new_target']:,.2f}")
                    else:
                        st.markdown("""
                        <div class='score-gauge'>
                            <div class='score-value' style='color:#2d3a4a;'>—</div>
                            <div class='score-label'>UPSIDE</div>
                            <div class='score-bar'><div class='score-bar-fill' style='width:0%;'></div></div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("Target not hit yet")
                
                with col4:
                    if r['mtf_signals']:
                        mtf_color = '#00d4aa' if r['mtf_alignment'] >= 60 else '#ffa502' if r['mtf_alignment'] >= 40 else '#ff4757'
                        st.markdown(f"""
                        <div class='score-gauge'>
                            <div class='score-value' style='color:{mtf_color};'>{r['mtf_alignment']}%</div>
                            <div class='score-label'>MTF ALIGN</div>
                            <div class='score-bar'>
                                <div class='score-bar-fill' style='width:{r["mtf_alignment"]}%; background:{mtf_color};'></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        for tf, signal in r['mtf_signals'].items():
                            sig_icon = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                            st.caption(f"{tf}: {sig_icon} {signal}")
                    else:
                        st.markdown("""
                        <div class='score-gauge'>
                            <div class='score-value' style='color:#2d3a4a;'>—</div>
                            <div class='score-label'>MTF ALIGN</div>
                            <div class='score-bar'><div class='score-bar-fill' style='width:0%;'></div></div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # ── TECHNICAL INDICATORS ROW ──
                rsi_color = '#00d4aa' if 40 <= r['rsi'] <= 60 else '#ffa502' if 30 <= r['rsi'] <= 70 else '#ff4757'
                macd_color = '#00d4aa' if r['macd_signal'] == 'BULLISH' else '#ff4757'
                
                st.markdown(f"""
                <div style='background:#0f1419; border:1px solid #1e2a3a; border-radius:10px; 
                            padding:12px 18px; margin:8px 0;'>
                    <div style='display:flex; justify-content:space-around; flex-wrap:wrap; gap:8px;'>
                        <div style='text-align:center; min-width:70px;'>
                            <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>RSI</div>
                            <div style='color:{rsi_color}; font-size:1rem; font-weight:700;'>{r['rsi']:.1f}</div>
                        </div>
                        <div style='width:1px; background:#1e2a3a;'></div>
                        <div style='text-align:center; min-width:70px;'>
                            <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>MACD</div>
                            <div style='color:{macd_color}; font-size:0.85rem; font-weight:700;'>{r['macd_signal']}</div>
                        </div>
                        <div style='width:1px; background:#1e2a3a;'></div>
                        <div style='text-align:center; min-width:80px;'>
                            <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>VOLUME</div>
                            <div style='color:#e2e8f0; font-size:0.8rem; font-weight:600;'>{r['volume_signal'].replace("_"," ")}</div>
                            <div style='color:#4a5568; font-size:0.65rem;'>{r['volume_ratio']:.1f}x avg</div>
                        </div>
                        <div style='width:1px; background:#1e2a3a;'></div>
                        <div style='text-align:center; min-width:70px;'>
                            <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>ATR</div>
                            <div style='color:#e2e8f0; font-size:0.85rem; font-weight:600;'>₹{r['atr']:,.2f}</div>
                        </div>
                        <div style='width:1px; background:#1e2a3a;'></div>
                        <div style='text-align:center; min-width:70px;'>
                            <div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>R:R</div>
                            <div style='color:#e2e8f0; font-size:0.85rem; font-weight:600;'>1:{r['risk_reward_ratio']:.2f}</div>
                        </div>
                        {"<div style='width:1px; background:#1e2a3a;'></div><div style='text-align:center; min-width:80px;'><div style='color:#4a5568; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.08em;'>HOLDING</div><div style='color:#e2e8f0; font-size:0.85rem;'>" + str(r['holding_days']) + "d</div><div style='color:#4a5568; font-size:0.6rem;'>" + r['tax_implication'][:15] + "</div></div>" if r['holding_days'] > 0 else ""}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # ── CHART PATTERNS ──
                if 'df' in r:
                    detected_patterns = detect_chart_patterns(r['df'], r['current_price'])
                    if detected_patterns:
                        st.markdown("<div style='color:#4a5568; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; margin:12px 0 6px 0;'>DETECTED PATTERNS</div>", unsafe_allow_html=True)
                        for pattern in detected_patterns:
                            p_class = 'pattern-bullish' if pattern['signal'] == 'BULLISH' else 'pattern-bearish'
                            p_color = '#00d4aa' if pattern['signal'] == 'BULLISH' else '#ff4757'
                            st.markdown(f"""
                            <div class='pattern-card {p_class}'>
                                <strong style='color:{p_color};'>{pattern['icon']} {pattern['name']}</strong>
                                <span style='color:#4a5568; font-size:0.75rem;'> — {pattern['signal']} ({pattern['strength']})</span><br>
                                <span style='color:#a0aec0; font-size:0.8rem;'>{pattern['description']}</span><br>
                                <span style='color:#e2e8f0; font-size:0.8rem;'>→ {pattern['action']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                
                # ── PARTIAL EXITS ──
                if r['partial_exits']['triggered_count'] > 0:
                    st.markdown("<div style='color:#4a5568; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; margin:12px 0 6px 0;'>PARTIAL EXIT LEVELS</div>", unsafe_allow_html=True)
                    pe_cols = st.columns(4)
                    for idx, pe in enumerate(r['partial_exits']['recommendations'][:4]):
                        with pe_cols[idx]:
                            pe_color = '#00d4aa' if pe['status'] == 'TRIGGERED' else '#2d3a4a'
                            st.markdown(f"""
                            <div style='background:#0f1419; border:1px solid {pe_color}; border-radius:8px; 
                                        padding:10px; text-align:center;'>
                                <div style='color:#e2e8f0; font-weight:700; font-family:monospace;'>₹{pe['level']:,.2f}</div>
                                <div style='color:#4a5568; font-size:0.7rem;'>{pe['reason']}</div>
                                <div style='color:{pe_color}; font-size:0.7rem; font-weight:600; margin-top:4px;'>{pe['status']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                
                # ── ALERTS ──
                if r['alerts']:
                    st.markdown("<div style='color:#4a5568; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; margin:12px 0 6px 0;'>ALERTS & ACTIONS</div>", unsafe_allow_html=True)
                    for alert in r['alerts']:
                        alert_class_map = {
                            'CRITICAL': 'alert-critical',
                            'HIGH': 'alert-warning',
                            'MEDIUM': 'alert-info',
                            'LOW': 'alert-success'
                        }
                        alert_css = alert_class_map.get(alert['priority'], 'alert-info')
                        st.markdown(f"""
                        <div class='{alert_css}'>
                            <strong>{alert['type']}</strong>: {alert['message']}<br>
                            <span style='font-size:0.85rem;'>⚡ {alert['action']}</span>
                        </div>
                        """, unsafe_allow_html=True)
                
                # ── RECOMMENDATION BOX ──
                rec_class_map = {
                    'EXIT': 'rec-exit', 'EXIT_EARLY': 'rec-exit',
                    'WATCH': 'rec-watch', 'BOOK_PROFITS': 'rec-profit',
                    'HOLD_EXTEND': 'rec-hold', 'TRAIL_SL': 'rec-trail',
                    'HOLD': 'rec-hold', 'MOVE_SL_BREAKEVEN': 'rec-trail'
                }
                rec_css = rec_class_map.get(r['overall_action'], 'rec-hold')
                
                st.markdown(f"""
                <div class='{rec_css}'>
                    📌 {r['overall_action'].replace('_', ' ')}
                </div>
                """, unsafe_allow_html=True)
                
                # ── AUTO UPDATE & MANUAL EXIT ──
                st.markdown("<div style='color:#4a5568; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; margin:12px 0 6px 0;'>ACTIONS</div>", unsafe_allow_html=True)
                
                auto_update_col1, auto_update_col2 = st.columns(2)
                
                with auto_update_col1:
                    # AUTO-UPDATE STOP LOSS
                    if r['should_trail'] and r['trail_stop'] != r['stop_loss']:
                        update_key = f"sl_updated_{r['ticker']}_{get_ist_now().strftime('%Y%m%d')}"
                        if update_key not in st.session_state:
                            with st.spinner(f"Updating SL..."):
                                success, msg = update_sheet_stop_loss(
                                    r['ticker'], r['trail_stop'],
                                    r.get('trail_reason', 'Trail stop recommended'),
                                    should_send_email=True,
                                    email_settings=settings["email_settings"], result=r
                                )
                                if success:
                                    st.success(f"✅ SL → ₹{r['trail_stop']:.2f}")
                                    st.session_state[update_key] = True
                                    r['stop_loss'] = r['trail_stop']
                                else:
                                    st.warning(f"⚠️ {msg}")
                        else:
                            st.markdown(f"<div class='alert-success' style='padding:8px 12px; font-size:0.8rem;'>✓ SL updated to ₹{r['trail_stop']:.2f}</div>", unsafe_allow_html=True)
                    
                    # AUTO-UPDATE TARGET
                    if r['target1_hit'] and r['upside_score'] >= 60 and r['new_target'] != r['target2']:
                        update_key = f"target_updated_{r['ticker']}_{get_ist_now().strftime('%Y%m%d')}"
                        if update_key not in st.session_state:
                            with st.spinner(f"Updating Target..."):
                                success, msg = update_sheet_target(
                                    r['ticker'], r['new_target'], 2,
                                    f"Extended (upside {r['upside_score']}%)",
                                    should_send_email=True,
                                    email_settings=settings["email_settings"], result=r
                                )
                                if success:
                                    st.success(f"✅ T2 → ₹{r['new_target']:.2f}")
                                    st.session_state[update_key] = True
                                    r['target2'] = r['new_target']
                                else:
                                    st.warning(f"⚠️ {msg}")
                        else:
                            st.markdown(f"<div class='alert-success' style='padding:8px 12px; font-size:0.8rem;'>✓ Target updated to ₹{r['new_target']:.2f}</div>", unsafe_allow_html=True)
                
                with auto_update_col2:
                    # SUGGESTED EXIT
                    exit_conditions = (
                        r['overall_action'] in ['EXIT', 'EXIT_EARLY', 'BOOK_PROFITS'] or 
                        r['sl_hit'] or r['target2_hit']
                    )
                    
                    if exit_conditions:
                        exit_reason = ""
                        if r['sl_hit']:
                            exit_reason = "Stop Loss Hit"
                        elif r['target2_hit']:
                            exit_reason = "Target 2 Achieved"
                        elif r['overall_action'] == 'EXIT_EARLY':
                            exit_reason = f"Early Exit - SL Risk {r['sl_risk']}%"
                        elif r['overall_action'] == 'EXIT':
                            exit_reason = "Exit Recommended"
                        else:
                            exit_reason = "Book Profits"
                        
                        if st.button(
                            f"🚪 Exit ({r['pnl_amount']:+,.0f})",
                            key=f"suggested_exit_{r['ticker']}",
                            use_container_width=True, type="primary"
                        ):
                            with st.spinner(f"Closing {r['ticker']}..."):
                                success, msg = mark_position_inactive(
                                    r['ticker'], r['current_price'], r['pnl_amount'], exit_reason,
                                    should_send_email=True,
                                    email_settings=settings["email_settings"], result=r
                                )
                                if success:
                                    st.success(f"✅ {msg}")
                                    log_trade(r['ticker'], r['entry_price'], r['current_price'],
                                             r['quantity'], r['position_type'], exit_reason)
                                    if r['pnl_amount'] > 0:
                                        st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                    
                    # MANUAL EXIT (always available)
                                        # MANUAL EXIT (always available - works with all Streamlit versions)
                    with st.expander(f"✋ Manual Exit {r['ticker']}", expanded=False):
                        manual_exit_price = st.number_input(
                            "Exit Price", min_value=0.01,
                            value=float(round_to_tick_size(r['current_price'])),
                            step=0.05, key=f"manual_price_{r['ticker']}"
                        )
                        manual_reason = st.selectbox("Reason", [
                            "Manual - Strategy Change", "Manual - Risk Management",
                            "Manual - Capital Reallocation", "Manual - News/Event",
                            "Manual - Partial Booking", "Manual - Market Conditions"
                        ], key=f"manual_reason_{r['ticker']}")
                        
                        if r['position_type'] == 'LONG':
                            m_pnl = (manual_exit_price - r['entry_price']) * r['quantity']
                        else:
                            m_pnl = (r['entry_price'] - manual_exit_price) * r['quantity']
                        
                        m_pnl_color = '#00d4aa' if m_pnl >= 0 else '#ff4757'
                        st.markdown(f"<div style='color:{m_pnl_color}; font-weight:700; font-size:1.1rem; text-align:center; margin:10px 0;'>P&L: ₹{m_pnl:+,.2f}</div>", unsafe_allow_html=True)
                        
                        confirm = st.checkbox(f"Confirm exit {r['ticker']}", key=f"confirm_{r['ticker']}")
                        
                        if st.button("Execute Exit", key=f"exec_exit_{r['ticker']}",
                                    use_container_width=True, type="primary", disabled=not confirm):
                            manual_result = r.copy()
                            manual_result['current_price'] = manual_exit_price
                            manual_result['pnl_amount'] = m_pnl
                            
                            success, msg = mark_position_inactive(
                                r['ticker'], manual_exit_price, m_pnl, manual_reason,
                                should_send_email=True,
                                email_settings=settings["email_settings"], result=manual_result
                            )
                            if success:
                                st.success(f"✅ {msg}")
                                log_trade(r['ticker'], r['entry_price'], manual_exit_price,
                                         r['quantity'], r['position_type'], manual_reason)
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")     
    
    # =========================================================================
    # TAB 2: CHARTS
    # =========================================================================
    with tab2:
        selected_stock = st.selectbox("Select Stock for Chart", [r['ticker'] for r in results])
        selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
        
        if selected_result and 'df' in selected_result:
            df = selected_result['df']
            
            # Candlestick Chart
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(
                x=df['Date'], open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Price'
            ))
            
            # Add moving averages
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['EMA9'] = df['Close'].ewm(span=9).mean()
            df['SMA50'] = df['Close'].rolling(50).mean()
            
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA20'], mode='lines',
                                    name='SMA 20', line=dict(color='orange', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA9'], mode='lines',
                                    name='EMA 9', line=dict(color='purple', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA50'], mode='lines',
                                    name='SMA 50', line=dict(color='blue', width=1, dash='dot')))
            
            # Add levels
            fig.add_hline(y=selected_result['entry_price'], line_dash="dash",
                         line_color="blue", annotation_text="Entry")
            fig.add_hline(y=selected_result['stop_loss'], line_dash="dash",
                         line_color="red", annotation_text="Stop Loss")
            fig.add_hline(y=selected_result['target1'], line_dash="dash",
                         line_color="green", annotation_text="Target 1")
            fig.add_hline(y=selected_result['target2'], line_dash="dot",
                         line_color="darkgreen", annotation_text="Target 2")
            fig.add_hline(y=selected_result['support'], line_dash="dot",
                         line_color="orange", annotation_text="Support")
            fig.add_hline(y=selected_result['resistance'], line_dash="dot",
                         line_color="purple", annotation_text="Resistance")
            
            if selected_result['should_trail']:
                fig.add_hline(y=selected_result['trail_stop'], line_dash="dash",
                             line_color="cyan", annotation_text="Trail SL", line_width=2)
            
            fig.update_layout(
                title=f"{selected_stock} - Price Chart with Levels",
                height=500,
                xaxis_rangeslider_visible=False,
                xaxis_title="Date",
                yaxis_title="Price (₹)",
                template="plotly_dark",
                plot_bgcolor='#0a0e17',
                paper_bgcolor='#0a0e17',
                font=dict(color='#a0aec0', family='Inter, sans-serif'),
                xaxis=dict(gridcolor='#1e2a3a', zerolinecolor='#1e2a3a'),
                yaxis=dict(gridcolor='#1e2a3a', zerolinecolor='#1e2a3a'),
                legend=dict(bgcolor='rgba(15,20,25,0.8)', bordercolor='#1e2a3a')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # RSI and MACD Charts
            col1, col2 = st.columns(2)
            
            with col1:
                rsi_series = calculate_rsi(df['Close'])
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df['Date'], y=rsi_series, mode='lines',
                                            name='RSI', line=dict(color='purple')))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
                fig_rsi.update_layout(
                    title="RSI (14)", height=250, yaxis_range=[0, 100],
                    template="plotly_dark", plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
                    font=dict(color='#a0aec0'), xaxis=dict(gridcolor='#1e2a3a'),
                    yaxis=dict(gridcolor='#1e2a3a')
                )
                st.plotly_chart(fig_rsi, use_container_width=True)
            
            with col2:
                macd, signal, histogram = calculate_macd(df['Close'])
                colors = ['green' if h >= 0 else 'red' for h in histogram]
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Bar(x=df['Date'], y=histogram, name='Histogram',
                                         marker_color=colors))
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=macd, mode='lines',
                                             name='MACD', line=dict(color='blue', width=1)))
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=signal, mode='lines',
                                             name='Signal', line=dict(color='orange', width=1)))
                fig_macd.update_layout(
                    title="MACD", height=250,
                    template="plotly_dark", plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
                    font=dict(color='#a0aec0'), xaxis=dict(gridcolor='#1e2a3a'),
                    yaxis=dict(gridcolor='#1e2a3a')
                )
                st.plotly_chart(fig_macd, use_container_width=True)
            
            # Volume Chart
            fig_vol = go.Figure()
            vol_colors = ['green' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'red'
                         for i in range(len(df))]
            fig_vol.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name='Volume',
                                    marker_color=vol_colors))
            fig_vol.update_layout(
                title="Volume", height=200,
                template="plotly_dark", plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
                font=dict(color='#a0aec0'), xaxis=dict(gridcolor='#1e2a3a'),
                yaxis=dict(gridcolor='#1e2a3a')
            )
            st.plotly_chart(fig_vol, use_container_width=True)
    
    # =========================================================================
    # TAB 3: ALERTS
    # =========================================================================
    with tab3:
        st.subheader("🔔 All Alerts")
        
        all_alerts = []
        for r in results:
            for alert in r['alerts']:
                all_alerts.append({
                    'Ticker': r['ticker'],
                    'Priority': alert['priority'],
                    'Type': alert['type'],
                    'Message': alert['message'],
                    'Action': alert['action'],
                    'P&L': f"{r['pnl_percent']:+.2f}%",
                    'SL Risk': f"{r['sl_risk']}%"
                })
        
        if all_alerts:
            # Sort by priority
            priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            all_alerts_sorted = sorted(all_alerts, key=lambda x: priority_order.get(x['Priority'], 4))
            
            df_alerts = pd.DataFrame(all_alerts_sorted)
            
            # Color code by priority
            def highlight_priority(row):
                if row['Priority'] == 'CRITICAL':
                    return ['background-color: #f8d7da'] * len(row)
                elif row['Priority'] == 'HIGH':
                    return ['background-color: #fff3cd'] * len(row)
                elif row['Priority'] == 'MEDIUM':
                    return ['background-color: #d1ecf1'] * len(row)
                return [''] * len(row)
            
            st.dataframe(df_alerts.style.apply(highlight_priority, axis=1),
                        use_container_width=True, hide_index=True)
            
            # Summary by priority
            st.markdown("### Alert Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                critical = sum(1 for a in all_alerts if a['Priority'] == 'CRITICAL')
                st.metric("🔴 Critical", critical)
            with col2:
                high = sum(1 for a in all_alerts if a['Priority'] == 'HIGH')
                st.metric("🟠 High", high)
            with col3:
                medium = sum(1 for a in all_alerts if a['Priority'] == 'MEDIUM')
                st.metric("🟡 Medium", medium)
            with col4:
                low = sum(1 for a in all_alerts if a['Priority'] == 'LOW')
                st.metric("🟢 Low", low)
        else:
            st.success("✅ No alerts! All positions are healthy.")
            st.balloons()
    
    # =========================================================================
    # TAB 4: MTF ANALYSIS
    # =========================================================================
    with tab4:
        st.subheader("📉 Multi-Timeframe Analysis")
        
        if not settings['enable_multi_timeframe']:
            st.warning("⚠️ Multi-Timeframe Analysis is disabled. Enable it in the sidebar settings.")
        else:
            for r in results:
                with st.expander(f"{r['ticker']} - MTF Alignment: {r['mtf_alignment']}%",
                                expanded=(r['mtf_alignment'] < 50)):
                    
                    if r['mtf_signals']:
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            alignment_color = "#28a745" if r['mtf_alignment'] >= 60 else "#ffc107" if r['mtf_alignment'] >= 40 else "#dc3545"
                            st.markdown(f"""
                            <div style='text-align:center;padding:20px;background:#f8f9fa;border-radius:10px;'>
                                <h1 style='color:{alignment_color};margin:0;'>{r['mtf_alignment']}%</h1>
                                <p style='margin:5px 0;'>Timeframe Alignment</p>
                                <p style='font-size:0.8em;color:#666;'>{r['mtf_recommendation']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            for tf, signal in r['mtf_signals'].items():
                                details = r['mtf_details'].get(tf, {})
                                sig_color = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                                
                                strength = details.get('strength', 'Unknown')
                                rsi_tf = details.get('rsi', 0)
                                
                                st.markdown(f"""
                                **{tf}:** {sig_color} {signal} ({strength})
                                - RSI: {rsi_tf:.1f} | Above SMA20: {'✅' if details.get('above_sma20') else '❌'} | 
                                EMA Bullish: {'✅' if details.get('ema_bullish') else '❌'} |
                                MACD: {'📈' if details.get('macd_bullish') else '📉'}
                                """)
                    else:
                        st.warning("MTF data not available for this stock")
    
    # =========================================================================
    # TAB 5: PORTFOLIO RISK
    # =========================================================================
    with tab5:
        display_portfolio_risk_dashboard(portfolio_risk, sector_analysis)
        
        st.divider()
        
        # Sector Analysis
        display_sector_analysis(sector_analysis)
        
        st.divider()
        
        # Correlation Analysis
        display_correlation_analysis(results, settings['enable_correlation'])
    
    # =========================================================================
    # TAB 6: PERFORMANCE
    # =========================================================================
    with tab6:
        display_performance_dashboard()
    
    # =========================================================================
    # TAB 7: DETAILS
    # =========================================================================
    with tab7:
        st.subheader("📋 Complete Analysis Data")
        
        details_data = []
        for r in results:
            details_data.append({
                'Ticker': r['ticker'],
                'Type': r['position_type'],
                'Entry': f"₹{r['entry_price']:,.2f}",
                'Current': f"₹{r['current_price']:,.2f}",
                'P&L %': f"{r['pnl_percent']:+.2f}%",
                'P&L ₹': f"₹{r['pnl_amount']:+,.0f}",
                'SL': f"₹{r['stop_loss']:,.2f}",
                'SL Risk': f"{r['sl_risk']}%",
                'Momentum': f"{r['momentum_score']:.0f}",
                'RSI': f"{r['rsi']:.1f}",
                'MACD': r['macd_signal'],
                'Volume': r['volume_signal'].replace('_', ' '),
                'Support': f"₹{r['support']:,.2f}",
                'Resistance': f"₹{r['resistance']:,.2f}",
                'Trail SL': f"₹{r['trail_stop']:,.2f}" if r['should_trail'] else '-',
                'MTF Align': f"{r['mtf_alignment']}%" if r['mtf_signals'] else 'N/A',
                'R:R': f"1:{r['risk_reward_ratio']:.2f}",
                'Holding': f"{r['holding_days']}d" if r['holding_days'] > 0 else '-',
                'Status': r['overall_status'],
                'Action': r['overall_action'].replace('_', ' ')
            })
        
        df_details = pd.DataFrame(details_data)
        
        # Color code by status
        def highlight_status(row):
            status = row['Status']
            if status == 'CRITICAL':
                return ['background-color: #f8d7da'] * len(row)
            elif status == 'WARNING':
                return ['background-color: #fff3cd'] * len(row)
            elif status in ['SUCCESS', 'GOOD']:
                return ['background-color: #d4edda'] * len(row)
            elif status == 'OPPORTUNITY':
                return ['background-color: #d1ecf1'] * len(row)
            return [''] * len(row)
        
        st.dataframe(df_details.style.apply(highlight_status, axis=1),
                    use_container_width=True, hide_index=True)
        
        # Export option
        csv_data = df_details.to_csv(index=False)
        st.download_button(
            "📥 Download Analysis as CSV",
            csv_data,
            file_name=f"portfolio_analysis_{ist_now.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    # =========================================================================
    # AUTO REFRESH
    # =========================================================================
    st.divider()
    
    if settings['auto_refresh']:
        if is_open:
            if HAS_AUTOREFRESH:
                count = st_autorefresh(
                    interval=settings['refresh_interval'] * 1000,
                    limit=None,
                    key="portfolio_autorefresh"
                )
                st.caption(f"🔄 Auto-refresh active | Interval: {settings['refresh_interval']}s | Count: {count}")
            else:
                st.caption(f"⏱️ Auto-refresh requires streamlit-autorefresh package")
                st.caption("💡 Install: `pip install streamlit-autorefresh`")
                
                # Manual refresh button as fallback
                if st.button("🔄 Refresh Now", key="manual_refresh"):
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption(f"⏸️ Auto-refresh paused - {market_status}: {market_msg}")
    else:
        st.caption("🔄 Auto-refresh disabled. Click 'Refresh' button to update.")
    
    # Footer
    # Footer
    st.markdown(f"""
    <div class='terminal-footer'>
        SMART PORTFOLIO MONITOR v6.0 &nbsp;│&nbsp; 
        {ist_now.strftime('%H:%M:%S')} IST &nbsp;│&nbsp; 
        {len(results)} POSITIONS &nbsp;│&nbsp; 
        {st.session_state.api_call_count} API CALLS &nbsp;│&nbsp;
        {"📧 EMAIL ON" if settings['email_settings']['enabled'] else "📧 OFF"}
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()
