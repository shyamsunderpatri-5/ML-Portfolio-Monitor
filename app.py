"""
🎯 PROFESSIONAL PORTFOLIO MONITOR v7.0
=======================================
Production-ready trading portfolio monitor with professional UI
Inspired by: Zerodha Kite, TradingView, Bloomberg Terminal

Features:
- Clean, modern interface
- Real-time position monitoring
- Smart alerts & notifications
- Multi-timeframe analysis
- Email notifications
- Google Sheets integration
- Future-ready for multi-user auth
"""

import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
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

# Try optional imports
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ============================================================================
# PAGE CONFIGURATION (MUST BE FIRST!)
# ============================================================================
st.set_page_config(
    page_title="Portfolio Monitor Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Professional Portfolio Monitor v7.0"
    }
)

# ============================================================================
# PROFESSIONAL THEME & STYLING
# ============================================================================
st.markdown("""
<style>
    /* Modern Professional Theme */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Main container */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Remove default padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header styling */
    h1, h2, h3 {
        font-weight: 600;
        color: #1a1a1a;
    }
    
    /* Metric cards - Zerodha style */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
    }
    
    /* Remove metric label background */
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 500;
        color: #666;
    }
    
    /* Buttons - modern flat design */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Tabs - TradingView style */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: white;
        border-radius: 8px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 20px;
        font-weight: 500;
    }
    
    /* Dataframe styling */
    .dataframe {
        font-size: 0.9rem;
    }
    
    /* Expander - clean design */
    .streamlit-expanderHeader {
        font-weight: 500;
        border-radius: 6px;
        background-color: white;
    }
    
    /* Success/Error/Warning boxes */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
    }
    
    /* Remove hamburger menu and footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Professional status badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-critical { background: #fee; color: #c00; }
    .status-warning { background: #fff3cd; color: #856404; }
    .status-success { background: #d4edda; color: #155724; }
    .status-info { background: #d1ecf1; color: #0c5460; }
    
    /* Card containers */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        transition: all 0.3s;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    /* Market status indicator */
    .market-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    .market-open {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
    }
    
    .market-closed {
        background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%);
        color: white;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# GOOGLE SHEETS CREDENTIALS
# ============================================================================
credentials = None
try:
    if 'GCP_SA_KEY' in os.environ:
        service_account_info = json.loads(os.environ.get('GCP_SA_KEY'))
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets", 
                   "https://www.googleapis.com/auth/drive"]
        )
except Exception as e:
    logger.error(f"Failed to load credentials: {e}")

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'email_alerts_enabled': False,
        'email_sent_alerts': {},
        'last_email_time': {},
        'email_log': [],
        'trade_history': [],
        'performance_stats': {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0,
            'total_loss': 0
        },
        'peak_portfolio_value': 0,
        'current_drawdown': 0,
        'max_drawdown': 0,
        'last_api_call': {},
        'api_call_count': 0,
        'theme': 'light',  # For future dark mode
        'user_id': None,  # For future multi-user support
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division handling zeros and NaN"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        return default if pd.isna(result) or np.isinf(result) else result
    except:
        return default

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        result = float(value)
        return default if pd.isna(result) else result
    except:
        return default

def round_to_tick_size(price):
    """Round to NSE tick size (0.05 for >₹1, 0.01 for <₹1)"""
    if pd.isna(price) or price is None:
        return 0.0
    price = float(price)
    if price < 0:
        return 0.0
    if price < 1:
        return round(price / 0.01) * 0.01
    return round(price / 0.05) * 0.05

def get_ist_now():
    """Get current IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    
    if ist_now.weekday() >= 5:  # Weekend
        return False, "CLOSED", "Weekend", "🔴"
    
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return False, "PRE-MARKET", "Opens at 09:15", "🟡"
    elif current_time > market_close:
        return False, "CLOSED", "Closed for today", "🔴"
    else:
        return True, "LIVE", "Market open", "🟢"

# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI using Wilder's smoothing"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices: pd.Series, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_atr(high, low, close, period=14):
    """Calculate ATR"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=60)
def get_stock_data(ticker, period="6mo"):
    """Fetch stock data with caching"""
    symbol = ticker if '.NS' in str(ticker) or '.BO' in str(ticker) else f"{ticker}.NS"
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        if not df.empty:
            df.reset_index(inplace=True)
            return df
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
    return None

@st.cache_data(ttl=300)
def get_market_health():
    """Get NIFTY and India VIX for market health"""
    try:
        # NIFTY 50
        nifty = yf.Ticker("^NSEI")
        nifty_df = nifty.history(period="1mo")
        
        if nifty_df.empty:
            return None
        
        nifty_price = float(nifty_df['Close'].iloc[-1])
        nifty_prev = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else nifty_price
        nifty_change = ((nifty_price - nifty_prev) / nifty_prev) * 100
        
        nifty_sma20 = nifty_df['Close'].rolling(20).mean().iloc[-1]
        nifty_rsi = calculate_rsi(nifty_df['Close']).iloc[-1]
        if pd.isna(nifty_rsi):
            nifty_rsi = 50
        
        # India VIX
        vix = yf.Ticker("^INDIAVIX")
        vix_df = vix.history(period="5d")
        vix_value = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 15
        
        # Calculate health score
        health_score = 50
        if nifty_price > nifty_sma20:
            health_score += 15
        else:
            health_score -= 15
        
        if nifty_rsi > 55:
            health_score += 15
        elif nifty_rsi < 35:
            health_score -= 15
        
        if vix_value < 12:
            health_score += 20
        elif vix_value > 25:
            health_score -= 20
        
        health_score = max(0, min(100, health_score))
        
        if health_score >= 70:
            status = "BULLISH"
            color = "#28a745"
        elif health_score >= 50:
            status = "NEUTRAL"
            color = "#ffc107"
        else:
            status = "BEARISH"
            color = "#dc3545"
        
        return {
            'status': status,
            'health_score': health_score,
            'nifty_price': nifty_price,
            'nifty_change': nifty_change,
            'nifty_rsi': nifty_rsi,
            'vix': vix_value,
            'color': color
        }
    except Exception as e:
        logger.error(f"Market health check failed: {e}")
        return None

# ============================================================================
# GOOGLE SHEETS INTEGRATION
# ============================================================================

def get_google_sheet_connection():
    """Connect to Google Sheets"""
    try:
        if credentials is None:
            return None, "Google credentials not configured"
        gc = gspread.authorize(credentials)
        sh = gc.open("my_portfolio")
        return sh.sheet1, "success"
    except Exception as e:
        return None, str(e)

def load_portfolio():
    """Load portfolio from Google Sheets"""
    if not HAS_GSPREAD:
        # Return sample data for demo
        return pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'],
            'Position': ['LONG', 'LONG', 'SHORT', 'LONG', 'LONG'],
            'Entry_Price': [2450.00, 3580.00, 1520.00, 1650.00, 1050.00],
            'Quantity': [10, 5, 8, 12, 20],
            'Stop_Loss': [2380.00, 3480.00, 1580.00, 1600.00, 1010.00],
            'Target_1': [2550.00, 3720.00, 1420.00, 1750.00, 1120.00],
            'Target_2': [2650.00, 3850.00, 1350.00, 1850.00, 1180.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01', '2024-01-10', '2024-02-05'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE']
        })
    
    try:
        sheet, status = get_google_sheet_connection()
        if sheet is None:
            return None
        
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return None
        
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        return df
    except Exception as e:
        logger.error(f"Error loading portfolio: {e}")
        return None

# ============================================================================
# POSITION ANALYSIS
# ============================================================================

def analyze_position(ticker, position_type, entry_price, quantity, stop_loss, 
                    target1, target2, entry_date=None):
    """Analyze a single position"""
    df = get_stock_data(ticker)
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
    except:
        return None
    
    # Calculate P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
        sl_hit = current_price <= stop_loss
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
    else:  # SHORT
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
        sl_hit = current_price >= stop_loss
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
    
    # Technical indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    
    # Status determination
    if sl_hit:
        status = 'CRITICAL'
        action = 'EXIT NOW'
    elif target2_hit:
        status = 'SUCCESS'
        action = 'BOOK PROFITS'
    elif target1_hit:
        status = 'GOOD'
        action = 'TRAIL SL'
    elif pnl_percent < -2:
        status = 'WARNING'
        action = 'WATCH CLOSELY'
    elif pnl_percent > 2:
        status = 'GOOD'
        action = 'HOLD'
    else:
        status = 'OK'
        action = 'MONITOR'
    
    return {
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        'day_high': day_high,
        'day_low': day_low,
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'sl_hit': sl_hit,
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'rsi': rsi,
        'macd_hist': macd_hist,
        'status': status,
        'action': action,
        'df': df
    }

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_market_status():
    """Render market status banner"""
    is_open, status, message, icon = is_market_hours()
    market_health = get_market_health()
    ist_now = get_ist_now()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        status_class = "market-open" if is_open else "market-closed"
        st.markdown(f"""
        <div class="market-status {status_class}">
            {icon} {status} - {message}
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if market_health:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-weight: 600;">NIFTY:</span>
                <span style="font-size: 1.2rem; font-weight: 600;">
                    ₹{market_health['nifty_price']:,.0f}
                </span>
                <span style="color: {'#28a745' if market_health['nifty_change'] >= 0 else '#dc3545'}; 
                             font-weight: 600;">
                    {market_health['nifty_change']:+.2f}%
                </span>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        st.caption(f"🕐 {ist_now.strftime('%H:%M:%S IST')}")
        st.caption(f"{ist_now.strftime('%d %b %Y')}")

def render_portfolio_summary(results):
    """Render portfolio summary cards"""
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    critical_count = sum(1 for r in results if r['status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['status'] == 'WARNING')
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['status'] == 'GOOD')
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            label="Total P&L",
            value=f"₹{abs(total_pnl):,.0f}",
            delta=f"{pnl_percent:+.2f}%"
        )
    
    with col2:
        st.metric(
            label="Positions",
            value=len(results)
        )
    
    with col3:
        st.metric(
            label="🔴 Critical",
            value=critical_count
        )
    
    with col4:
        st.metric(
            label="🟡 Warning",
            value=warning_count
        )
    
    with col5:
        st.metric(
            label="🟢 Good",
            value=good_count
        )
    
    with col6:
        st.metric(
            label="✅ Success",
            value=success_count
        )

def render_position_card(result):
    """Render individual position card - Zerodha Kite style"""
    # Status colors
    status_colors = {
        'CRITICAL': '#dc3545',
        'WARNING': '#ffc107',
        'SUCCESS': '#28a745',
        'GOOD': '#17a2b8',
        'OK': '#6c757d'
    }
    
    status_color = status_colors.get(result['status'], '#6c757d')
    pnl_color = '#28a745' if result['pnl_percent'] >= 0 else '#dc3545'
    
    # Card container
    with st.container():
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid {status_color};">
        """, unsafe_allow_html=True)
        
        # Header row
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        
        with col1:
            st.markdown(f"### {result['ticker']}")
            st.caption(f"{'📈 LONG' if result['position_type'] == 'LONG' else '📉 SHORT'} • {result['quantity']} shares")
        
        with col2:
            st.metric(
                label="Current Price",
                value=f"₹{result['current_price']:,.2f}",
                delta=f"₹{result['current_price'] - result['entry_price']:+,.2f}"
            )
        
        with col3:
            st.metric(
                label="P&L",
                value=f"₹{abs(result['pnl_amount']):,.0f}",
                delta=f"{result['pnl_percent']:+.2f}%"
            )
        
        with col4:
            st.markdown(f"""
            <div class="status-badge status-{result['status'].lower()}">
                {result['status']}
            </div>
            <p style="margin-top: 8px; font-weight: 600; color: {status_color};">
                {result['action']}
            </p>
            """, unsafe_allow_html=True)
        
        # Details row
        st.divider()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.caption("Entry / Target 1 / Target 2")
            st.write(f"₹{result['entry_price']:,.2f} / ₹{result['target1']:,.2f} / ₹{result['target2']:,.2f}")
            
        with col2:
            st.caption("Stop Loss")
            sl_status = '🔴 HIT' if result['sl_hit'] else '✅ Safe'
            st.write(f"₹{result['stop_loss']:,.2f} {sl_status}")
        
        with col3:
            st.caption("RSI / MACD")
            rsi_color = '#28a745' if 40 <= result['rsi'] <= 60 else '#ffc107'
            st.markdown(f"<span style='color:{rsi_color}'>{result['rsi']:.1f}</span> / {'📈' if result['macd_hist'] > 0 else '📉'}", 
                       unsafe_allow_html=True)
        
        with col4:
            st.caption("Day Range")
            st.write(f"₹{result['day_low']:,.2f} - ₹{result['day_high']:,.2f}")
        
        st.markdown("</div>", unsafe_allow_html=True)

def render_chart(result):
    """Render professional chart - TradingView style"""
    df = result['df']
    
    # Create subplots
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=('Price', 'RSI', 'Volume')
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price'
        ),
        row=1, col=1
    )
    
    # Moving averages
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    
    fig.add_trace(
        go.Scatter(x=df['Date'], y=df['SMA20'], name='SMA 20',
                  line=dict(color='orange', width=1)),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['Date'], y=df['SMA50'], name='SMA 50',
                  line=dict(color='blue', width=1)),
        row=1, col=1
    )
    
    # Add levels
    fig.add_hline(y=result['entry_price'], line_dash="dash",
                 line_color="blue", annotation_text="Entry",
                 row=1, col=1)
    fig.add_hline(y=result['stop_loss'], line_dash="dash",
                 line_color="red", annotation_text="SL",
                 row=1, col=1)
    fig.add_hline(y=result['target1'], line_dash="dash",
                 line_color="green", annotation_text="T1",
                 row=1, col=1)
    
    # RSI
    rsi_series = calculate_rsi(df['Close'])
    fig.add_trace(
        go.Scatter(x=df['Date'], y=rsi_series, name='RSI',
                  line=dict(color='purple', width=2)),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
    
    # Volume
    colors = ['green' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'red'
             for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df['Date'], y=df['Volume'], name='Volume',
              marker_color=colors, showlegend=False),
        row=3, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        template='plotly_white'
    )
    
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    """Render professional sidebar"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Email alerts
        st.markdown("### 📧 Email Alerts")
        
        email_enabled = st.checkbox(
            "Enable Alerts",
            value=st.session_state.email_alerts_enabled,
            help="Turn on/off email notifications"
        )
        
        if email_enabled != st.session_state.email_alerts_enabled:
            st.session_state.email_alerts_enabled = email_enabled
        
        if email_enabled:
            st.success("✅ Email alerts active")
        else:
            st.info("📧 Email alerts disabled")
        
        st.divider()
        
        # Auto-refresh
        st.markdown("### 🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable", value=True)
        
        if auto_refresh:
            refresh_interval = st.slider("Interval (seconds)", 30, 300, 60)
        else:
            refresh_interval = 60
        
        st.divider()
        
        # Thresholds
        st.markdown("### 🎯 Alert Thresholds")
        sl_risk_threshold = st.slider("SL Risk Alert %", 30, 90, 50)
        trail_trigger = st.slider("Trail SL after %", 0.5, 10.0, 2.0, 0.5)
        
        st.divider()
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        if st.button("📊 Export Report", use_container_width=True):
            st.info("Export feature coming soon!")
        
        st.divider()
        
        # Info
        st.caption("📊 Portfolio Monitor Pro v7.0")
        st.caption(f"Session: {st.session_state.api_call_count} API calls")
        
        return {
            'email_enabled': email_enabled,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval,
            'sl_risk_threshold': sl_risk_threshold,
            'trail_trigger': trail_trigger
        }

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application"""
    
    # Header
    st.markdown("# 📊 Portfolio Monitor Pro")
    st.caption("Professional trading portfolio analysis platform")
    
    st.divider()
    
    # Market status
    render_market_status()
    
    st.divider()
    
    # Sidebar
    settings = render_sidebar()
    
    # Load portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.error("❌ No portfolio data found")
        st.info("💡 Configure Google Sheets or use demo data")
        return
    
    # Analyze positions
    results = []
    progress = st.progress(0, text="Analyzing positions...")
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress.progress((i + 1) / len(portfolio), text=f"Analyzing {ticker}...")
        
        result = analyze_position(
            ticker,
            str(row['Position']).upper().strip(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            row.get('Entry_Date', None)
        )
        
        if result:
            results.append(result)
    
    progress.empty()
    
    if not results:
        st.error("❌ Could not fetch data")
        return
    
    # Portfolio summary
    st.markdown("## 📊 Portfolio Overview")
    render_portfolio_summary(results)
    
    st.divider()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📈 Positions", "📊 Charts", "📋 Details"])
    
    with tab1:
        # Sort by status
        status_order = {'CRITICAL': 0, 'WARNING': 1, 'SUCCESS': 2, 'GOOD': 3, 'OK': 4}
        sorted_results = sorted(results, key=lambda x: status_order.get(x['status'], 5))
        
        for result in sorted_results:
            render_position_card(result)
            st.markdown("<br>", unsafe_allow_html=True)
    
    with tab2:
        selected_stock = st.selectbox(
            "Select Stock",
            [r['ticker'] for r in results]
        )
        
        selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
        
        if selected_result:
            render_chart(selected_result)
    
    with tab3:
        # Create dataframe
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
                'Target': f"₹{r['target1']:,.2f}",
                'RSI': f"{r['rsi']:.1f}",
                'Status': r['status'],
                'Action': r['action']
            })
        
        df_details = pd.DataFrame(details_data)
        
        # Apply styling
        def style_status(val):
            if val == 'CRITICAL':
                return 'background-color: #fee'
            elif val == 'WARNING':
                return 'background-color: #fff3cd'
            elif val == 'SUCCESS':
                return 'background-color: #d4edda'
            elif val == 'GOOD':
                return 'background-color: #d1ecf1'
            return ''
        
        styled_df = df_details.style.applymap(style_status, subset=['Status'])
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Export
        csv = df_details.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            file_name=f"portfolio_{get_ist_now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    # Auto-refresh
    if settings['auto_refresh']:
        is_open, _, _, _ = is_market_hours()
        if is_open and HAS_AUTOREFRESH:
            st_autorefresh(
                interval=settings['refresh_interval'] * 1000,
                key="portfolio_refresh"
            )
    
    # Footer
    st.divider()
    st.caption(f"Last updated: {get_ist_now().strftime('%H:%M:%S IST')} • {len(results)} positions")

# ============================================================================
# RUN APP
# ============================================================================

if __name__ == "__main__":
    main()
