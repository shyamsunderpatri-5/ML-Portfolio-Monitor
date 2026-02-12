"""
🚀 PROFESSIONAL PORTFOLIO MONITOR v7.0 - TRADING TERMINAL EDITION
================================================================
Zerodha Kite + TradingView + Bloomberg Terminal Inspired Design
ALL Features from v6 + Professional UI + Zero Errors
"""

import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import time
import json
from typing import Tuple, Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try imports
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
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Portfolio Monitor Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# PROFESSIONAL STYLING - Zerodha Kite + Bloomberg Inspired
# ============================================================================

st.markdown("""
<style>
    /* Import Professional Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Remove Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }
    
    /* Professional Header */
    .pro-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .pro-header h1 {
        color: white;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .pro-header p {
        color: rgba(255,255,255,0.9);
        margin: 0.5rem 0 0 0;
        font-size: 0.95rem;
    }
    
    /* Market Status Banner - Zerodha Style */
    .market-banner {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .market-banner.closed {
        background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%);
    }
    
    .market-info {
        color: white;
        font-weight: 600;
    }
    
    /* Professional Cards - Kite Style */
    .position-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
    }
    
    .position-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    .position-card.critical {
        border-left-color: #dc3545;
        background: linear-gradient(to right, #fff 0%, #fff5f5 100%);
    }
    
    .position-card.warning {
        border-left-color: #ffc107;
        background: linear-gradient(to right, #fff 0%, #fffbf0 100%);
    }
    
    .position-card.success {
        border-left-color: #28a745;
        background: linear-gradient(to right, #fff 0%, #f0fff4 100%);
    }
    
    /* Metric Cards */
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 10px rgba(0,0,0,0.12);
    }
    
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        color: #666;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }
    
    .status-badge.critical {
        background: #dc3545;
        color: white;
    }
    
    .status-badge.warning {
        background: #ffc107;
        color: #000;
    }
    
    .status-badge.success {
        background: #28a745;
        color: white;
    }
    
    .status-badge.good {
        background: #20c997;
        color: white;
    }
    
    /* Profit/Loss Colors */
    .profit {
        color: #28a745;
        font-weight: 600;
    }
    
    .loss {
        color: #dc3545;
        font-weight: 600;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.75rem 1.5rem;
        border-radius: 8px 8px 0 0;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1.05rem;
        border-radius: 8px;
        background: #f8f9fa;
    }
    
    /* Data Tables */
    .dataframe {
        font-size: 0.9rem;
    }
    
    /* Progress Bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Alert Boxes */
    .alert-box {
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 0.75rem 0;
        font-weight: 500;
    }
    
    .alert-critical {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        color: #721c24;
    }
    
    .alert-warning {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        color: #856404;
    }
    
    .alert-success {
        background: #d4edda;
        border-left: 4px solid #28a745;
        color: #155724;
    }
    
    .alert-info {
        background: #d1ecf1;
        border-left: 4px solid #17a2b8;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# GOOGLE SHEETS & CREDENTIALS SETUP
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
    logger.error(f"Credentials error: {e}")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division"""
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
    """Round to NSE tick size"""
    if pd.isna(price) or price is None:
        return 0.0
    
    price = float(price)
    if price < 0:
        return 0.0
    
    if price < 1:
        return round(price / 0.01) * 0.01
    else:
        return round(price / 0.05) * 0.05

def get_ist_now():
    """Get IST time"""
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
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize session state"""
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
        'last_correlation_calc': None,
        'email_alerts_enabled': False
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
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
# MARKET HEALTH CHECK
# ============================================================================

@st.cache_data(ttl=300)
def get_market_health():
    """Get market health from NIFTY + VIX"""
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_df = nifty.history(period="1mo")
        
        if nifty_df.empty:
            return None
        
        nifty_price = float(nifty_df['Close'].iloc[-1])
        nifty_prev = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else nifty_price
        nifty_change = ((nifty_price - nifty_prev) / nifty_prev) * 100
        
        nifty_sma20 = nifty_df['Close'].rolling(20).mean().iloc[-1]
        nifty_sma50 = nifty_df['Close'].rolling(50).mean().iloc[-1] if len(nifty_df) >= 50 else nifty_sma20
        nifty_rsi = calculate_rsi(nifty_df['Close']).iloc[-1]
        
        if pd.isna(nifty_rsi):
            nifty_rsi = 50
        
        vix = yf.Ticker("^INDIAVIX")
        vix_df = vix.history(period="5d")
        vix_value = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 15
        
        # Health Score Calculation
        health_score = 50
        
        if nifty_price > nifty_sma20:
            health_score += 15
        else:
            health_score -= 15
        
        if nifty_price > nifty_sma50:
            health_score += 10
        else:
            health_score -= 10
        
        if nifty_rsi > 55:
            health_score += 15
        elif nifty_rsi > 45:
            health_score += 5
        elif nifty_rsi < 35:
            health_score -= 15
        elif nifty_rsi < 45:
            health_score -= 10
        
        if vix_value < 12:
            health_score += 20
        elif vix_value < 15:
            health_score += 10
        elif vix_value > 25:
            health_score -= 20
        elif vix_value > 18:
            health_score -= 10
        
        if nifty_sma20 > nifty_sma50:
            health_score += 10
        else:
            health_score -= 10
        
        health_score = max(0, min(100, health_score))
        
        if health_score >= 70:
            status = "BULLISH"
            color = "#28a745"
            icon = "🟢"
            action = "✅ Good environment for trading"
        elif health_score >= 50:
            status = "NEUTRAL"
            color = "#ffc107"
            icon = "🟡"
            action = "⚠️ Be selective with new positions"
        elif health_score >= 30:
            status = "WEAK"
            color = "#fd7e14"
            icon = "🟠"
            action = "⚠️ Tighten stop losses"
        else:
            status = "BEARISH"
            color = "#dc3545"
            icon = "🔴"
            action = "🚨 HIGH RISK - Reduce exposure"
        
        message = f"NIFTY: ₹{nifty_price:,.0f} ({nifty_change:+.2f}%) | RSI: {nifty_rsi:.0f} | VIX: {vix_value:.1f}"
        
        return {
            'status': status,
            'health_score': health_score,
            'message': message,
            'color': color,
            'icon': icon,
            'action': action,
            'nifty_price': nifty_price,
            'nifty_change': nifty_change,
            'nifty_rsi': nifty_rsi,
            'nifty_sma20': nifty_sma20,
            'nifty_sma50': nifty_sma50,
            'vix': vix_value
        }
    
    except Exception as e:
        logger.error(f"Market health error: {e}")
        return None

# ============================================================================
# STOCK DATA FETCHING
# ============================================================================

def rate_limited_api_call(ticker, min_interval=1.0):
    """Rate limit API calls"""
    current_time = time.time()
    
    if ticker in st.session_state.last_api_call:
        elapsed = current_time - st.session_state.last_api_call[ticker]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    
    st.session_state.last_api_call[ticker] = time.time()
    st.session_state.api_call_count += 1
    return True

@st.cache_data(ttl=60)
def get_stock_data(ticker, period="6mo"):
    """Fetch stock data with caching"""
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
                time.sleep(1 * (attempt + 1))
                continue
            logger.error(f"Stock data error for {ticker}: {e}")
    
    return None

# ============================================================================
# SUPPORT/RESISTANCE DETECTION
# ============================================================================

def find_support_resistance(df, lookback=60):
    """Find key support/resistance levels"""
    if len(df) < lookback:
        lookback = len(df)
    
    if lookback < 10:
        current_price = df['Close'].iloc[-1]
        return {
            'support': current_price * 0.95,
            'resistance': current_price * 1.05,
            'strength': 'WEAK'
        }
    
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    current_price = float(df['Close'].iloc[-1])
    
    pivot_highs = []
    pivot_lows = []
    
    for i in range(3, len(high) - 3):
        if (high.iloc[i] >= high.iloc[i-1] and high.iloc[i] >= high.iloc[i-2] and
            high.iloc[i] >= high.iloc[i-3] and high.iloc[i] >= high.iloc[i+1] and
            high.iloc[i] >= high.iloc[i+2] and high.iloc[i] >= high.iloc[i+3]):
            pivot_highs.append(float(high.iloc[i]))
        
        if (low.iloc[i] <= low.iloc[i-1] and low.iloc[i] <= low.iloc[i-2] and
            low.iloc[i] <= low.iloc[i-3] and low.iloc[i] <= low.iloc[i+1] and
            low.iloc[i] <= low.iloc[i+2] and low.iloc[i] <= low.iloc[i+3]):
            pivot_lows.append(float(low.iloc[i]))
    
    supports_below = [s for s in pivot_lows if s < current_price]
    resistances_above = [r for r in pivot_highs if r > current_price]
    
    nearest_support = max(supports_below) if supports_below else float(low.min()) * 0.99
    nearest_resistance = min(resistances_above) if resistances_above else float(high.max()) * 1.01
    
    return {
        'support': nearest_support,
        'resistance': nearest_resistance,
        'strength': 'STRONG' if len(supports_below) >= 2 else 'MODERATE' if len(supports_below) >= 1 else 'WEAK'
    }

# ============================================================================
# VOLUME ANALYSIS
# ============================================================================

def analyze_volume(df):
    """Analyze volume patterns"""
    if 'Volume' not in df.columns or len(df) < 20:
        return "NEUTRAL", 1.0, "No volume data"
    
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    if price_change > 0 and volume_ratio > 1.5:
        return "STRONG_BUYING", volume_ratio, f"Strong buying ({volume_ratio:.1f}x)"
    elif price_change > 0 and volume_ratio > 1.0:
        return "BUYING", volume_ratio, f"Buying with volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.5:
        return "STRONG_SELLING", volume_ratio, f"Strong selling ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.0:
        return "SELLING", volume_ratio, f"Selling with volume ({volume_ratio:.1f}x)"
    else:
        return "NEUTRAL", volume_ratio, f"Normal volume ({volume_ratio:.1f}x)"

# ============================================================================
# MOMENTUM SCORING
# ============================================================================

def calculate_momentum_score(df):
    """Calculate momentum score 0-100"""
    close = df['Close']
    score = 50
    
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if rsi > 70:
        score -= 10
    elif rsi > 60:
        score += 15
    elif rsi > 50:
        score += 10
    elif rsi > 40:
        score -= 5
    elif rsi > 30:
        score -= 15
    else:
        score += 10
    
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    
    if not pd.isna(hist_current):
        if hist_current > 0:
            score += 20
        else:
            score -= 20
    
    current_price = close.iloc[-1]
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    
    if current_price > sma_20:
        score += 10
    else:
        score -= 10
    
    score = max(0, min(100, score))
    
    if score >= 70:
        trend = "STRONG BULLISH"
    elif score >= 55:
        trend = "BULLISH"
    elif score >= 45:
        trend = "NEUTRAL"
    elif score >= 30:
        trend = "BEARISH"
    else:
        trend = "STRONG BEARISH"
    
    return score, trend

# ============================================================================
# SL RISK PREDICTION
# ============================================================================

def predict_sl_risk(df, current_price, stop_loss, position_type, threshold=50):
    """Predict SL hit probability"""
    risk_score = 0
    reasons = []
    
    # Distance to SL
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:
        risk_score = 100
        reasons.append("⚠️ SL already breached!")
    elif distance_pct < 1:
        risk_score += 40
        reasons.append(f"🔴 Very close to SL ({distance_pct:.1f}%)")
    elif distance_pct < 2:
        risk_score += 30
        reasons.append(f"🟠 Close to SL ({distance_pct:.1f}%)")
    elif distance_pct < 3:
        risk_score += 15
        reasons.append(f"🟡 Approaching SL ({distance_pct:.1f}%)")
    
    # RSI check
    rsi = calculate_rsi(df['Close']).iloc[-1]
    if not pd.isna(rsi):
        if position_type == "LONG" and rsi < 35:
            risk_score += 10
            reasons.append(f"📉 RSI weak ({rsi:.0f})")
        elif position_type == "SHORT" and rsi > 65:
            risk_score += 10
            reasons.append(f"📈 RSI strong ({rsi:.0f})")
    
    # MACD check
    macd, signal_line, histogram = calculate_macd(df['Close'])
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    
    if not pd.isna(hist_current):
        if position_type == "LONG" and hist_current < 0:
            risk_score += 8
            reasons.append("📊 MACD bearish")
        elif position_type == "SHORT" and hist_current > 0:
            risk_score += 8
            reasons.append("📊 MACD bullish")
    
    risk_score = min(100, risk_score)
    
    if risk_score >= 80:
        recommendation = "🚨 EXIT NOW - Very high risk"
        priority = "CRITICAL"
    elif risk_score >= threshold + 20:
        recommendation = "⚠️ CONSIDER EXIT - High risk"
        priority = "HIGH"
    elif risk_score >= threshold:
        recommendation = "👀 WATCH CLOSELY - Moderate risk"
        priority = "MEDIUM"
    else:
        recommendation = "✅ MONITOR - Low risk"
        priority = "LOW"
    
    return risk_score, reasons, recommendation, priority

# ============================================================================
# DYNAMIC LEVELS CALCULATION
# ============================================================================

def calculate_dynamic_levels(df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_trigger=2.0):
    """Calculate dynamic targets and trailing SL"""
    close = df['Close']
    high = df['High']
    low = df['Low']
    
    atr = calculate_atr(high, low, close).iloc[-1]
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02
    
    sr_levels = find_support_resistance(df)
    
    result = {
        'atr': atr,
        'support': sr_levels['support'],
        'resistance': sr_levels['resistance']
    }
    
    if position_type == "LONG":
        result['target1'] = round_to_tick_size(current_price + (atr * 1.5))
        result['target2'] = round_to_tick_size(current_price + (atr * 3))
        
        # Dynamic trail logic
        if pnl_percent >= trail_trigger * 5:
            atr_trail = current_price - (atr * 1.0)
            pct_trail = entry_price + (current_price - entry_price) * 0.70
            result['trail_stop'] = max(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 70%+ profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_MAJOR_PROFIT"
        elif pnl_percent >= trail_trigger * 3:
            atr_trail = current_price - (atr * 1.5)
            pct_trail = entry_price + (current_price - entry_price) * 0.50
            result['trail_stop'] = max(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 50% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        elif pnl_percent >= trail_trigger * 2:
            atr_trail = current_price - (atr * 2.0)
            pct_trail = entry_price + (current_price - entry_price) * 0.30
            result['trail_stop'] = max(atr_trail, pct_trail, entry_price * 1.005)
            result['trail_reason'] = f"Securing gains (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        elif pnl_percent >= trail_trigger:
            atr_trail = current_price - (atr * 2.5)
            result['trail_stop'] = max(atr_trail, entry_price)
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "BREAKEVEN"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL"
            result['trail_action'] = "HOLD"
        
        result['trail_stop'] = max(result['trail_stop'], stop_loss)
        result['should_trail'] = result['trail_stop'] > stop_loss
    
    else:  # SHORT
        result['target1'] = round_to_tick_size(current_price - (atr * 1.5))
        result['target2'] = round_to_tick_size(current_price - (atr * 3))
        
        if pnl_percent >= trail_trigger * 5:
            atr_trail = current_price + (atr * 1.0)
            pct_trail = entry_price - (entry_price - current_price) * 0.70
            result['trail_stop'] = min(atr_trail, pct_trail)
            result['trail_reason'] = f"Locking 70%+ profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_MAJOR_PROFIT"
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
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL"
            result['trail_action'] = "HOLD"
        
        result['trail_stop'] = min(result['trail_stop'], stop_loss)
        result['should_trail'] = result['trail_stop'] < stop_loss
    
    result['trail_stop'] = round_to_tick_size(result['trail_stop'])
    
    return result

# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

@st.cache_data(ttl=60)
def analyze_position(ticker, position_type, entry_price, quantity, stop_loss, 
                     target1, target2, trail_trigger=2.0, sl_threshold=50):
    """Complete position analysis"""
    df = get_stock_data(ticker)
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
    except:
        return None
    
    # P&L Calculation
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
    
    # Momentum & Volume
    momentum_score, momentum_trend = calculate_momentum_score(df)
    volume_signal, volume_ratio, volume_desc = analyze_volume(df)
    
    # S/R Levels
    sr_levels = find_support_resistance(df)
    
    # SL Risk
    sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_sl_risk(
        df, current_price, stop_loss, position_type, sl_threshold
    )
    
    # Dynamic Levels
    dynamic = calculate_dynamic_levels(
        df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_trigger
    )
    
    # Target Status
    if position_type == "LONG":
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
        sl_hit = current_price <= stop_loss
    else:
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
        sl_hit = current_price >= stop_loss
    
    # Overall Status
    if sl_hit:
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
    elif sl_risk >= 70:
        overall_status = 'CRITICAL'
        overall_action = 'EXIT_EARLY'
    elif sl_risk >= sl_threshold:
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    elif target2_hit:
        overall_status = 'SUCCESS'
        overall_action = 'BOOK_PROFITS'
    elif target1_hit:
        overall_status = 'SUCCESS'
        overall_action = 'PARTIAL_EXIT'
    elif dynamic['should_trail']:
        overall_status = 'GOOD'
        overall_action = 'TRAIL_SL'
    elif pnl_percent >= 0:
        overall_status = 'GOOD'
        overall_action = 'HOLD'
    else:
        overall_status = 'OK'
        overall_action = 'MONITOR'
    
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
        'rsi': rsi,
        'macd_hist': macd_hist,
        'momentum_score': momentum_score,
        'momentum_trend': momentum_trend,
        'volume_signal': volume_signal,
        'volume_ratio': volume_ratio,
        'volume_desc': volume_desc,
        'support': sr_levels['support'],
        'resistance': sr_levels['resistance'],
        'sl_risk': sl_risk,
        'sl_reasons': sl_reasons,
        'sl_recommendation': sl_recommendation,
        'trail_stop': dynamic['trail_stop'],
        'should_trail': dynamic['should_trail'],
        'trail_reason': dynamic.get('trail_reason', ''),
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'sl_hit': sl_hit,
        'overall_status': overall_status,
        'overall_action': overall_action,
        'df': df
    }

# ============================================================================
# EMAIL FUNCTIONS - Complete Implementation
# ============================================================================

def log_email(message):
    """Add to email log"""
    timestamp = get_ist_now().strftime("%H:%M:%S")
    st.session_state.email_log.append(f"[{timestamp}] {message}")
    if len(st.session_state.email_log) > 50:
        st.session_state.email_log = st.session_state.email_log[-50:]

def generate_alert_hash(ticker, alert_type, key_value=""):
    """Generate unique hash for alert"""
    alert_string = f"{ticker}_{alert_type}_{key_value}_{get_ist_now().strftime('%Y%m%d')}"
    return hashlib.md5(alert_string.encode()).hexdigest()[:12]

def can_send_email(alert_hash, cooldown_minutes=15):
    """Check cooldown"""
    if alert_hash not in st.session_state.last_email_time:
        return True
    
    last_sent = st.session_state.last_email_time[alert_hash]
    now = datetime.now()
    
    try:
        if isinstance(last_sent, datetime):
            if last_sent.tzinfo is not None:
                last_sent = last_sent.replace(tzinfo=None)
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
            
            time_diff = (now - last_sent).total_seconds() / 60.0
        else:
            return True
        
        return time_diff >= cooldown_minutes
    
    except Exception as e:
        logger.error(f"Email cooldown check failed: {e}")
        return True

def mark_email_sent(alert_hash):
    """Mark alert as sent"""
    st.session_state.last_email_time[alert_hash] = datetime.now()
    st.session_state.email_sent_alerts[alert_hash] = True

def send_email_alert(subject, html_content, sender, password, recipient):
    """Send email alert"""
    if not sender or not password or not recipient:
        log_email("❌ Missing email credentials")
        return False, "Missing credentials"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        
        log_email(f"✅ Email sent: {subject}")
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError:
        log_email("❌ SMTP Authentication failed")
        return False, "Authentication failed"
    except Exception as e:
        log_email(f"❌ Email failed: {str(e)}")
        return False, f"Email failed: {str(e)}"

def create_alert_email_html(result, alert_type, alert_message):
    """Create professional email HTML"""
    pnl_color = "#28a745" if result['pnl_percent'] >= 0 else "#dc3545"
    
    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                 background: #f5f7fa; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; 
                    border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 2rem; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 1.75rem; font-weight: 700;">
                    {alert_type}
                </h1>
                <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
                    {result['ticker']}
                </p>
            </div>
            
            <!-- Alert Message -->
            <div style="padding: 1.5rem; background: #f8f9fa; border-left: 4px solid #667eea;">
                <p style="margin: 0; font-size: 1.1rem; font-weight: 600; color: #333;">
                    {alert_message}
                </p>
            </div>
            
            <!-- Position Details -->
            <div style="padding: 2rem;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>Position Type</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">
                            {'📈 LONG' if result['position_type'] == 'LONG' else '📉 SHORT'}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>Entry Price</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">
                            ₹{result['entry_price']:,.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>Current Price</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">
                            ₹{result['current_price']:,.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>Stop Loss</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">
                            ₹{result['stop_loss']:,.2f}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>P&L</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right; 
                                   color: {pnl_color}; font-weight: bold; font-size: 1.1rem;">
                            {result['pnl_percent']:+.2f}% (₹{result['pnl_amount']:+,.0f})
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #eee;">
                            <strong>SL Risk Score</strong>
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">
                            {result['sl_risk']}%
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 1.5rem; text-align: center; 
                        font-size: 0.9rem; color: #666;">
                <p style="margin: 0;">Professional Portfolio Monitor v7.0</p>
                <p style="margin: 0.5rem 0 0 0;">{get_ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    
    return html

# ============================================================================
# GOOGLE SHEETS FUNCTIONS - Complete Implementation
# ============================================================================

def get_google_sheet_connection():
    """Connect to Google Sheets"""
    try:
        if credentials is None:
            return None, "Credentials not configured"
        gc = gspread.authorize(credentials)
        sh = gc.open("my_portfolio")
        return sh.sheet1, "success"
    except Exception as e:
        return None, str(e)

def load_portfolio():
    """Load portfolio from Google Sheets"""
    if not HAS_GSPREAD:
        st.warning("⚠️ gspread not installed")
        return get_demo_portfolio()
    
    try:
        sheet, status = get_google_sheet_connection()
        
        if sheet is None:
            st.warning(f"⚠️ Using demo data: {status}")
            return get_demo_portfolio()
        
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return get_demo_portfolio()
        
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        return df
    
    except Exception as e:
        logger.error(f"Portfolio load error: {e}")
        return get_demo_portfolio()

def get_demo_portfolio():
    """Demo portfolio data"""
    return pd.DataFrame({
        'Ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'],
        'Position': ['LONG', 'LONG', 'LONG', 'LONG', 'LONG'],
        'Entry_Price': [2450.00, 3580.00, 1520.00, 1650.00, 1050.00],
        'Quantity': [10, 5, 8, 12, 20],
        'Stop_Loss': [2380.00, 3480.00, 1450.00, 1600.00, 1010.00],
        'Target_1': [2550.00, 3720.00, 1620.00, 1750.00, 1120.00],
        'Target_2': [2650.00, 3850.00, 1720.00, 1850.00, 1180.00],
        'Status': ['ACTIVE'] * 5
    })

def update_sheet_stop_loss(ticker, new_sl, reason, email_settings=None, result=None):
    """Update SL in Google Sheets"""
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        logger.warning(f"Cannot update sheet: {status}")
        return False, status
    
    try:
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found"
        
        row = cell.row
        headers = sheet.row_values(1)
        
        try:
            sl_col = headers.index('Stop_Loss') + 1
        except ValueError:
            sl_col = 4
        
        old_sl = sheet.cell(row, sl_col).value
        new_sl = round_to_tick_size(new_sl)
        
        sheet.update_cell(row, sl_col, new_sl)
        
        log_message = f"🔄 AUTO-UPDATED {ticker} SL: ₹{old_sl} → ₹{new_sl:.2f} - {reason}"
        logger.info(log_message)
        log_email(log_message)
        
        # Send email
        if email_settings and email_settings.get('enabled') and result:
            sender = email_settings.get('sender_email')
            password = email_settings.get('sender_password')
            recipient = email_settings.get('recipient_email')
            
            if sender and password and recipient:
                alert_hash = generate_alert_hash(ticker, "SL_UPDATE", str(new_sl))
                
                if can_send_email(alert_hash, email_settings.get('cooldown', 15)):
                    subject = f"🔄 Stop Loss Updated - {ticker}"
                    html = create_alert_email_html(result, "🔄 Stop Loss Updated", 
                                                   f"New SL: ₹{new_sl:.2f} - {reason}")
                    
                    success, msg = send_email_alert(subject, html, sender, password, recipient)
                    if success:
                        mark_email_sent(alert_hash)
        
        return True, log_message
    
    except Exception as e:
        error_msg = f"Error updating {ticker}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def update_sheet_target(ticker, new_target, target_num, reason, email_settings=None, result=None):
    """Update target in Google Sheets"""
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        return False, status
    
    try:
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found"
        
        row = cell.row
        headers = sheet.row_values(1)
        target_col_name = f'Target_{target_num}'
        
        try:
            target_col = headers.index(target_col_name) + 1
        except ValueError:
            target_col = 6 if target_num == 1 else 7
        
        old_target = sheet.cell(row, target_col).value
        new_target = round_to_tick_size(new_target)
        
        sheet.update_cell(row, target_col, new_target)
        
        log_message = f"🎯 AUTO-UPDATED {ticker} Target {target_num}: ₹{old_target} → ₹{new_target:.2f}"
        logger.info(log_message)
        log_email(log_message)
        
        # Send email
        if email_settings and email_settings.get('enabled') and result:
            sender = email_settings.get('sender_email')
            password = email_settings.get('sender_password')
            recipient = email_settings.get('recipient_email')
            
            if sender and password and recipient:
                alert_hash = generate_alert_hash(ticker, "TARGET_UPDATE", str(new_target))
                
                if can_send_email(alert_hash, email_settings.get('cooldown', 15)):
                    subject = f"🎯 Target Extended - {ticker}"
                    html = create_alert_email_html(result, "🎯 Target Extended",
                                                   f"New Target {target_num}: ₹{new_target:.2f}")
                    
                    success, msg = send_email_alert(subject, html, sender, password, recipient)
                    if success:
                        mark_email_sent(alert_hash)
        
        return True, log_message
    
    except Exception as e:
        return False, str(e)

def mark_position_inactive(ticker, exit_price, pnl_amount, exit_reason, 
                          email_settings=None, result=None):
    """Mark position as closed"""
    sheet, status = get_google_sheet_connection()
    
    if sheet is None:
        return False, status
    
    try:
        cell = sheet.find(ticker)
        if not cell:
            return False, f"Ticker {ticker} not found"
        
        row = cell.row
        headers = sheet.row_values(1)
        
        try:
            status_col = headers.index('Status') + 1
        except ValueError:
            status_col = 9
        
        sheet.update_cell(row, status_col, 'INACTIVE')
        
        log_message = f"🚪 CLOSED: {ticker} | Exit: ₹{exit_price:.2f} | P&L: ₹{pnl_amount:+,.0f}"
        logger.info(log_message)
        log_email(log_message)
        
        # Send email
        if email_settings and email_settings.get('enabled') and result:
            sender = email_settings.get('sender_email')
            password = email_settings.get('sender_password')
            recipient = email_settings.get('recipient_email')
            
            if sender and password and recipient:
                subject = f"{'✅' if pnl_amount > 0 else '❌'} Position Closed - {ticker}"
                html = create_alert_email_html(result, "🚪 Position Closed",
                                               f"Exit: ₹{exit_price:.2f} | P&L: ₹{pnl_amount:+,.0f}")
                
                send_email_alert(subject, html, sender, password, recipient)
        
        return True, log_message
    
    except Exception as e:
        return False, str(e)

# ============================================================================
# PROFESSIONAL CHART CREATION - TradingView Style
# ============================================================================

def create_professional_chart(result):
    """Create TradingView-style 3-panel chart"""
    df = result['df']
    
    # Create subplots: Price + RSI + Volume
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('Price Chart', 'RSI (14)', 'Volume'),
        row_heights=[0.6, 0.2, 0.2]
    )
    
    # PANEL 1: CANDLESTICK + MOVING AVERAGES
    fig.add_trace(
        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )
    
    # Add Moving Averages
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    
    fig.add_trace(
        go.Scatter(x=df['Date'], y=df['SMA20'], mode='lines',
                  name='SMA 20', line=dict(color='#FF9800', width=1.5)),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['Date'], y=df['EMA9'], mode='lines',
                  name='EMA 9', line=dict(color='#9C27B0', width=1.5)),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(x=df['Date'], y=df['SMA50'], mode='lines',
                  name='SMA 50', line=dict(color='#2196F3', width=1.5, dash='dot')),
        row=1, col=1
    )
    
    # Add horizontal levels
    fig.add_hline(y=result['entry_price'], line_dash="dash",
                 line_color="#2196F3", annotation_text="Entry",
                 annotation_position="right", row=1, col=1)
    
    fig.add_hline(y=result['stop_loss'], line_dash="dash",
                 line_color="#F44336", annotation_text="Stop Loss",
                 annotation_position="right", row=1, col=1)
    
    fig.add_hline(y=result['target1'], line_dash="dash",
                 line_color="#4CAF50", annotation_text="Target 1",
                 annotation_position="right", row=1, col=1)
    
    fig.add_hline(y=result['target2'], line_dash="dot",
                 line_color="#388E3C", annotation_text="Target 2",
                 annotation_position="right", row=1, col=1)
    
    if result['should_trail']:
        fig.add_hline(y=result['trail_stop'], line_dash="solid",
                     line_color="#00BCD4", annotation_text="Trail SL",
                     annotation_position="right", line_width=2, row=1, col=1)
    
    # PANEL 2: RSI
    rsi_series = calculate_rsi(df['Close'])
    fig.add_trace(
        go.Scatter(x=df['Date'], y=rsi_series, mode='lines',
                  name='RSI', line=dict(color='#9C27B0', width=2)),
        row=2, col=1
    )
    
    fig.add_hline(y=70, line_dash="dash", line_color="#F44336",
                 annotation_text="Overbought", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#4CAF50",
                 annotation_text="Oversold", row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#9E9E9E", row=2, col=1)
    
    # PANEL 3: VOLUME
    colors = ['#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350'
              for i in range(len(df))]
    
    fig.add_trace(
        go.Bar(x=df['Date'], y=df['Volume'], name='Volume',
               marker_color=colors, showlegend=False),
        row=3, col=1
    )
    
    # Layout
    fig.update_layout(
        title=f"{result['ticker']} - Professional Chart Analysis",
        height=800,
        xaxis_rangeslider_visible=False,
        template='plotly_white',
        font=dict(family='Inter, sans-serif', size=12),
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    return fig

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

def render_sidebar():
    """Professional sidebar configuration"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Email Configuration
        st.markdown("### 📧 Email Alerts")
        
        YOUR_EMAIL = "pssundaar@gmail.com"
        YOUR_APP_PASSWORD = "ibpl ptdp oueh drjr"
        YOUR_RECIPIENT = "shyamsunderpatri@gmail.com"
        
        credentials_configured = bool(YOUR_EMAIL and YOUR_APP_PASSWORD and "@" in YOUR_EMAIL)
        
        if 'email_alerts_enabled' not in st.session_state:
            st.session_state.email_alerts_enabled = False
        
        email_enabled = st.checkbox(
            "Enable Email Alerts",
            value=st.session_state.email_alerts_enabled,
            key="email_checkbox"
        )
        
        if email_enabled != st.session_state.email_alerts_enabled:
            st.session_state.email_alerts_enabled = email_enabled
        
        email_settings = {
            'enabled': email_enabled and credentials_configured,
            'sender_email': YOUR_EMAIL if credentials_configured else '',
            'sender_password': YOUR_APP_PASSWORD if credentials_configured else '',
            'recipient_email': YOUR_RECIPIENT if credentials_configured else YOUR_EMAIL,
            'cooldown': 15
        }
        
        if email_enabled and credentials_configured:
            st.success("✅ Email configured!")
        
        st.divider()
        
        # Auto-refresh
        st.markdown("### 🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable Auto-Refresh", value=True)
        refresh_interval = st.slider("Interval (seconds)", 30, 300, 60)
        
        st.divider()
        
        # Alert Thresholds
        st.markdown("### 🎯 Alert Thresholds")
        trail_sl_trigger = st.slider("Trail SL after Profit %", 0.5, 10.0, 2.0, step=0.5)
        sl_risk_threshold = st.slider("SL Risk Alert Threshold", 30, 90, 50)
        
        st.divider()
        
        # Analysis Settings
        st.markdown("### 📊 Analysis")
        enable_charts = st.checkbox("Professional Charts", value=True)
        enable_technical = st.checkbox("Technical Indicators", value=True)
        
        return {
            'email_settings': email_settings,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval,
            'trail_sl_trigger': trail_sl_trigger,
            'sl_risk_threshold': sl_risk_threshold,
            'enable_charts': enable_charts,
            'enable_technical': enable_technical
        }

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application"""
    
    # Professional Header
    st.markdown("""
    <div class="pro-header">
        <h1>📊 Professional Portfolio Monitor v7.0</h1>
        <p>Real-time trading terminal with institutional-grade analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar settings
    settings = render_sidebar()
    
    # Market Status Banner
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    
    banner_class = "market-banner" if is_open else "market-banner closed"
    
    st.markdown(f"""
    <div class="{banner_class}">
        <div>
            <div style="font-size: 1.5rem; font-weight: 700;">{market_icon} {market_status}</div>
            <div style="font-size: 0.9rem; margin-top: 0.25rem;">{market_msg}</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 1.25rem; font-weight: 600;">{ist_now.strftime('%H:%M:%S')}</div>
            <div style="font-size: 0.85rem;">{ist_now.strftime('%a, %b %d, %Y')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Market Health
    market_health = get_market_health()
    if market_health:
        st.markdown(f"""
        <div style='background:{market_health['color']}20; padding:1.5rem; border-radius:10px; 
                    border-left:5px solid {market_health['color']}; margin:1rem 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <h2 style='margin:0; color:{market_health['color']};'>
                        {market_health['icon']} Market Health: {market_health['status']}
                    </h2>
                    <p style='margin:0.5rem 0; font-size:1.1rem;'>{market_health['message']}</p>
                    <p style='margin:0.5rem 0; font-weight:600;'>{market_health['action']}</p>
                </div>
                <div style='text-align:center; min-width:100px;'>
                    <div style='font-size:3rem; font-weight:700; color:{market_health['color']};'>
                        {market_health['health_score']}
                    </div>
                    <div style='font-size:0.9rem; color:#666;'>Health Score</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Load Portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.error("❌ No positions found")
        return
    
    # Analyze All Positions
    results = []
    progress_bar = st.progress(0, text="Analyzing positions...")
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {ticker}...")
        
        result = analyze_position(
            ticker,
            str(row['Position']).upper().strip(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            settings['trail_sl_trigger'],
            settings['sl_risk_threshold']
        )
        
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio), text=f"Completed {ticker}")
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch stock data")
        return
    
    # Portfolio Summary Metrics
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    pnl_percent_total = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    success_count = sum(1 for r in results if r['overall_status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['overall_status'] == 'GOOD')
    
    # Summary Cards
    st.markdown("### 📊 Portfolio Overview")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total P&L</div>
            <div class="metric-value {'profit' if total_pnl >= 0 else 'loss'}">
                ₹{total_pnl:+,.0f}
            </div>
            <div style="font-size:0.9rem; color:#666;">{pnl_percent_total:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Positions</div>
            <div class="metric-value">{len(results)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Critical</div>
            <div class="metric-value" style="color:#dc3545;">{critical_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Warning</div>
            <div class="metric-value" style="color:#ffc107;">{warning_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Good</div>
            <div class="metric-value" style="color:#28a745;">{good_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Success</div>
            <div class="metric-value" style="color:#20c997;">{success_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Charts", "📋 Details"])
    
    # TAB 1: DASHBOARD
    with tab1:
        # Sort by status priority
        status_order = {'CRITICAL': 0, 'WARNING': 1, 'SUCCESS': 2, 'GOOD': 3, 'OK': 4}
        sorted_results = sorted(results, key=lambda x: status_order.get(x['overall_status'], 5))
        
        for r in sorted_results:
            # Position Card
            card_class = "position-card"
            if r['overall_status'] == 'CRITICAL':
                card_class += " critical"
            elif r['overall_status'] == 'WARNING':
                card_class += " warning"
            elif r['overall_status'] in ['SUCCESS', 'GOOD']:
                card_class += " success"
            
            badge_class = f"status-badge {r['overall_status'].lower()}"
            
            with st.container():
                st.markdown(f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                        <div>
                            <h2 style="margin:0; font-size:1.5rem;">{r['ticker']}</h2>
                            <span class="{badge_class}">{r['overall_status']}</span>
                            <span style="margin-left:0.5rem; font-weight:600;">
                                {'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'}
                            </span>
                        </div>
                        <div style="text-align:right;">
                            <div class="{'profit' if r['pnl_percent'] >= 0 else 'loss'}" 
                                 style="font-size:1.75rem;">
                                {r['pnl_percent']:+.2f}%
                            </div>
                            <div style="font-size:1.1rem; font-weight:600;">
                                ₹{r['pnl_amount']:+,.0f}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Details in columns
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("**💰 Position**")
                    st.write(f"Entry: ₹{r['entry_price']:,.2f}")
                    st.write(f"Current: ₹{r['current_price']:,.2f}")
                    st.write(f"Quantity: {r['quantity']}")
                
                with col2:
                    st.markdown("**🎯 Levels**")
                    st.write(f"SL: ₹{r['stop_loss']:,.2f} {'🔴' if r['sl_hit'] else ''}")
                    st.write(f"T1: ₹{r['target1']:,.2f} {'✅' if r['target1_hit'] else ''}")
                    st.write(f"T2: ₹{r['target2']:,.2f} {'✅' if r['target2_hit'] else ''}")
                    if r['should_trail']:
                        st.success(f"Trail SL: ₹{r['trail_stop']:,.2f}")
                
                with col3:
                    st.markdown("**📊 Technical**")
                    st.write(f"RSI: {r['rsi']:.1f}")
                    st.write(f"Momentum: {r['momentum_score']:.0f}/100")
                    st.write(f"Volume: {r['volume_signal'].replace('_', ' ')}")
                
                with col4:
                    st.markdown("**⚠️ Risk**")
                    risk_color = "🔴" if r['sl_risk'] >= 70 else "🟡" if r['sl_risk'] >= 50 else "🟢"
                    st.write(f"SL Risk: {risk_color} {r['sl_risk']}%")
                    st.write(f"Support: ₹{r['support']:,.2f}")
                    st.write(f"Resistance: ₹{r['resistance']:,.2f}")
                
                # Alerts
                if r['sl_risk'] >= settings['sl_risk_threshold']:
                    alert_class = "alert-critical" if r['sl_risk'] >= 70 else "alert-warning"
                    st.markdown(f"""
                    <div class="alert-box {alert_class}">
                        <strong>⚠️ {r['sl_recommendation']}</strong><br>
                        {r['sl_reasons'][0] if r['sl_reasons'] else ''}
                    </div>
                    """, unsafe_allow_html=True)
                
                if r['should_trail']:
                    st.markdown(f"""
                    <div class="alert-box alert-success">
                        <strong>📈 Trail Stop Loss Recommended</strong><br>
                        {r['trail_reason']}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.divider()
    
    # TAB 2: CHARTS
    with tab2:
        if settings['enable_charts']:
            selected_stock = st.selectbox("Select Stock", [r['ticker'] for r in results])
            selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
            
            if selected_result:
                fig = create_professional_chart(selected_result)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Enable Professional Charts in sidebar")
    
    # TAB 3: DETAILS
    with tab3:
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
                'Status': r['overall_status'],
                'Action': r['overall_action'].replace('_', ' ')
            })
        
        df_details = pd.DataFrame(details_data)
        st.dataframe(df_details, use_container_width=True, hide_index=True)
        
        # Export
        csv_data = df_details.to_csv(index=False)
        st.download_button(
            "📥 Download Analysis",
            csv_data,
            file_name=f"portfolio_{ist_now.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    # Auto-refresh
    if settings['auto_refresh'] and is_open and HAS_AUTOREFRESH:
        count = st_autorefresh(
            interval=settings['refresh_interval'] * 1000,
            limit=None,
            key="autorefresh"
        )
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <p style='text-align:center; color:#666; font-size:0.85rem;'>
        Professional Portfolio Monitor v7.0 | {ist_now.strftime('%H:%M:%S')} IST | 
        Positions: {len(results)} | API Calls: {st.session_state.api_call_count}
    </p>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
