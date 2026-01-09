"""
🧠 SMART PORTFOLIO MONITOR v7.0 - PERFORMANCE OPTIMIZED EDITION
================================================================
PERFORMANCE UPGRADES:
✅ Async parallel API fetching (5x faster)
✅ Adaptive smart caching
✅ Memory-optimized data storage
✅ Lazy loading for charts
✅ Batch API calls
✅ Connection pooling
✅ Rate limiting with backoff

ALL ORIGINAL FEATURES RETAINED:
✅ Alert when SL hits
✅ Alert when target hits  
✅ Warn BEFORE SL hits (Predictive)
✅ Hold recommendation after target
✅ Dynamic target calculation
✅ Momentum scoring (0-100)
✅ Volume confirmation
✅ Support/Resistance detection
✅ Trail stop suggestion
✅ Risk scoring (0-100)
✅ Auto-refresh during market hours
✅ Email alerts for critical events
✅ Multi-Timeframe Analysis
✅ Position Sizing Calculator
✅ Risk-Reward Ratio Calculator
✅ Portfolio Risk Dashboard
✅ Win Rate & Trade Statistics
✅ Drawdown Tracking
✅ Sector Exposure Analysis
✅ Correlation Analysis
✅ Breakeven Alerts
✅ Partial Profit Booking Tracker
✅ Holding Period Tracker
✅ Trade History Log
✅ Performance Dashboard
"""

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
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import lru_cache
import threading
import time
import warnings
warnings.filterwarnings('ignore')
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# ============================================================================
# IMPORT SHARED UTILITIES
# ============================================================================
try:
    from trading_utils import (
        calculate_rsi, calculate_macd, calculate_atr,
        calculate_bollinger_bands, calculate_stochastic,
        safe_divide, safe_float
    )
    UTILS_IMPORTED = True
    logger.info("✅ Loaded shared trading utilities")
except ImportError:
    UTILS_IMPORTED = False
    # Functions will be defined inline below as fallback




# Try to import streamlit-autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False



# ============================================================================
# PERFORMANCE CONFIGURATION
# ============================================================================
PERF_CONFIG = {
    'max_workers': 5,              # Parallel API threads
    'api_timeout': 10,             # Seconds per API call
    'cache_ttl_market_open': 30,   # Cache during market hours
    'cache_ttl_market_closed': 300, # Cache after hours
    'batch_size': 5,               # Stocks per batch
    'rate_limit_delay': 0.2,       # Seconds between batches
    'max_retries': 3,              # API retry attempts
    'retry_backoff': 1.5,          # Exponential backoff multiplier
}

# Thread-safe API call tracking
api_lock = threading.Lock()
_api_call_count = 0

def get_api_call_count():
    """Get current API call count (thread-safe)"""
    global _api_call_count
    return _api_call_count
# ============================================================================
# PERFORMANCE UTILITIES - NEW IN v7.0
# ============================================================================

class APIRateLimiter:
    """Thread-safe rate limiter for API calls"""
    
    def __init__(self, calls_per_second=2):
        self.calls_per_second = calls_per_second
        self.last_call_time = 0
        self.lock = threading.Lock()
    
    def wait(self):
        """Wait if needed to respect rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_call_time
            min_interval = 1.0 / self.calls_per_second
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_call_time = time.time()

# Global rate limiter
rate_limiter = APIRateLimiter(calls_per_second=2)


class DataCache:
    """Smart caching with adaptive TTL"""
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self._last_market_state = None
    
    def get_ttl(self):
        """Get TTL based on market hours"""
        is_open, current_state, _, _ = is_market_hours()  # ✅ Get current_state
        
        # Clear cache if market state changed
        if self._last_market_state and self._last_market_state != current_state:
            logger.info(f"Market state changed: {self._last_market_state} -> {current_state}")
            self.clear()
        
        self._last_market_state = current_state

        if is_open:
            return PERF_CONFIG['cache_ttl_market_open']
        return PERF_CONFIG['cache_ttl_market_closed']
    
    def get(self, key):
        """Get cached value if still valid"""
        if key not in self.cache:
            return None
        
        age = time.time() - self.timestamps.get(key, 0)
        if age > self.get_ttl():
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key, value):
        """Cache a value"""
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear all cache"""
        self.cache = {}
        self.timestamps = {}
    
    def clear_ticker(self, ticker):
        """Clear cache for specific ticker"""
        keys_to_remove = [k for k in self.cache if ticker in k]
        for key in keys_to_remove:
            del self.cache[key]
            if key in self.timestamps:
                del self.timestamps[key]

# Global data cache
data_cache = DataCache()


def fetch_stock_data_optimized(ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    """
    Optimized stock data fetching with caching and retry logic
    Returns None if fetch fails, DataFrame otherwise
    """
    if not ticker:
        return None
    
    symbol = ticker if '.NS' in str(ticker) or '.BO' in str(ticker) else f"{ticker}.NS"
    cache_key = f"stock_{symbol}_{period}"
    
    # Check cache first
    cached = data_cache.get(cache_key)
    if cached is not None and isinstance(cached, pd.DataFrame) and not cached.empty:
        return cached
    
    # Rate limit
    rate_limiter.wait()
    
    # Fetch with retry
    for attempt in range(PERF_CONFIG.get('max_retries', 3)):
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            # Validate the result
            if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                df = df.reset_index()
                data_cache.set(cache_key, df)
                
                try:
                    with api_lock:
                        # Use a module-level counter instead of session_state for thread safety
                        global _api_call_count
                        if '_api_call_count' not in globals():
                            _api_call_count = 0
                        _api_call_count += 1
                except Exception:
                    pass  # Don't fail on counting errors
                
                return df
            else:
                logger.warning(f"Empty response for {symbol} on attempt {attempt + 1}")
        
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            if attempt < PERF_CONFIG.get('max_retries', 3) - 1:
                sleep_time = PERF_CONFIG.get('retry_backoff', 1.5) ** attempt
                time.sleep(sleep_time)
    
    logger.error(f"Failed to fetch {ticker} after all retries")
    return None

def fetch_multiple_stocks_parallel(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    Fetch multiple stocks in parallel using ThreadPoolExecutor
    
    This is the KEY performance improvement - fetches 5 stocks at once
    instead of 1 at a time!
    """
    results = {}
    
    # Clean tickers
    clean_tickers = [str(t).strip() for t in tickers if t]
    
    # Split into batches
    batch_size = PERF_CONFIG.get('batch_size', 5)
    batches = [clean_tickers[i:i + batch_size] 
               for i in range(0, len(clean_tickers), batch_size)]
    
    for batch in batches:
        with ThreadPoolExecutor(max_workers=PERF_CONFIG.get('max_workers', 5)) as executor:
            future_to_ticker = {
                executor.submit(fetch_stock_data_optimized, ticker, period): ticker
                for ticker in batch
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    df = future.result()
                    # Explicitly check if df is a valid non-empty DataFrame
                    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                        results[ticker] = df
                    else:
                        logger.warning(f"No valid data returned for {ticker}")
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
        
        # Small delay between batches to avoid rate limiting
        if len(batches) > 1:
            time.sleep(PERF_CONFIG.get('rate_limit_delay', 0.2))
    
    return results

def create_minimal_result(full_result: Dict) -> Dict:
    """
    Create a memory-optimized version of analysis result
    Removes the heavy DataFrame, keeps only essential data
    """
    if full_result is None:
        return None
    
    # Keep everything EXCEPT the raw DataFrame
    minimal = {k: v for k, v in full_result.items() if k != 'df'}
    
    # Store only essential chart data (last 60 days)
    if 'df' in full_result and full_result['df'] is not None:
        df = full_result['df'].tail(60)
        minimal['chart_data'] = {
            'Date': df['Date'].tolist() if 'Date' in df.columns else df.index.tolist(),
            'Open': df['Open'].tolist(),
            'High': df['High'].tolist(),
            'Low': df['Low'].tolist(),
            'Close': df['Close'].tolist(),
            'Volume': df['Volume'].tolist() if 'Volume' in df.columns else []
        }
    
    return minimal


def reconstruct_dataframe(chart_data: Dict) -> pd.DataFrame:
    """
    Safely reconstruct DataFrame from minimal chart data
    Handles various data formats and edge cases
    """
    if not chart_data or not isinstance(chart_data, dict):
        logger.warning("reconstruct_dataframe: Invalid or empty chart_data")
        return pd.DataFrame()

    try:
        # Check if chart_data has the expected structure
        if not chart_data:
            return pd.DataFrame()
        
        # Handle case where values might be single values instead of lists
        processed_data = {}
        expected_length = None
        
        for key, value in chart_data.items():
            if value is None:
                continue
            
            # Convert to list if not already
            if isinstance(value, (list, tuple)):
                processed_data[key] = list(value)
            elif isinstance(value, pd.Series):
                processed_data[key] = value.tolist()
            elif isinstance(value, np.ndarray):
                processed_data[key] = value.tolist()
            else:
                # Single value - skip or wrap in list
                continue
            
            # Track expected length
            if expected_length is None:
                expected_length = len(processed_data[key])
            elif len(processed_data[key]) != expected_length:
                logger.warning(f"Length mismatch for {key}: {len(processed_data[key])} vs {expected_length}")
        
        if not processed_data or expected_length is None or expected_length == 0:
            logger.warning("No valid data to reconstruct DataFrame")
            return pd.DataFrame()
        
        # Create DataFrame
        df = pd.DataFrame(processed_data)
        
        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.warning(f"Missing required columns: {missing_cols}")
            # Try to fill with Close if available
            if 'Close' in df.columns:
                for col in missing_cols:
                    df[col] = df['Close']
            else:
                return pd.DataFrame()
        
        # Handle Date column conversion
        if 'Date' in df.columns:
            try:
                # Try multiple date formats
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                
                # Check for NaT values
                nat_count = df['Date'].isna().sum()
                if nat_count > len(df) * 0.5:
                    # More than 50% NaT, create synthetic dates
                    logger.warning(f"Too many invalid dates ({nat_count}), creating synthetic")
                    df['Date'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D')
                elif nat_count > 0:
                    # Fill NaT with forward/backward fill
                    df['Date'] = df['Date'].fillna(method='ffill').fillna(method='bfill')
            except Exception as e:
                logger.warning(f"Date conversion failed: {e}, creating synthetic dates")
                df['Date'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D')
        else:
            # No Date column - create one
            df['Date'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D')
        
        # Ensure numeric types for price columns
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Handle Volume (might be missing or have NaN)
        if 'Volume' not in df.columns:
            df['Volume'] = 0
        else:
            df['Volume'] = df['Volume'].fillna(0).astype(int)
        
        # Drop rows with NaN in critical columns
        df = df.dropna(subset=['Close'])
        
        # Sort by date
        df = df.sort_values('Date').reset_index(drop=True)
        
        if df.empty:
            logger.warning("DataFrame is empty after processing")
            return pd.DataFrame()
        
        logger.info(f"Successfully reconstructed DataFrame with {len(df)} rows")
        return df

    except Exception as e:
        logger.error(f"DataFrame reconstruction failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

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
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .critical-box {
        background: linear-gradient(135deg, #dc3545, #c82333);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .success-box {
        background: linear-gradient(135deg, #28a745, #218838);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #ffc107, #e0a800);
        color: black;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .info-box {
        background: linear-gradient(135deg, #17a2b8, #138496);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 5px 0;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
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

@st.cache_data(ttl=600)  # Cache for 5 minutes
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
        

        # Calculate Market Health Score (0-100) - Enhanced Version
        health_score = 50  # Start neutral
        scoring_breakdown = {}
        
        # ================================================================
        # FACTOR 1: NIFTY Price vs Moving Averages (0-25 points)
        # ================================================================
        ma_score = 0
        
        # Above SMA20 (+10)
        if nifty_price > nifty_sma20:
            ma_score += 10
            scoring_breakdown['above_sma20'] = '+10'
        else:
            ma_score -= 10
            scoring_breakdown['above_sma20'] = '-10'
        
        # Above SMA50 (+8)
        if nifty_price > nifty_sma50:
            ma_score += 8
            scoring_breakdown['above_sma50'] = '+8'
        else:
            ma_score -= 8
            scoring_breakdown['above_sma50'] = '-8'
        
        # SMA20 > SMA50 (Golden Cross) (+7)
        if nifty_sma20 > nifty_sma50:
            ma_score += 7
            scoring_breakdown['golden_cross'] = '+7'
        else:
            ma_score -= 5
            scoring_breakdown['golden_cross'] = '-5 (Death Cross)'
        
        health_score += ma_score
        
        # ================================================================
        # FACTOR 2: RSI Momentum (0-20 points)
        # ================================================================
        rsi_score = 0
        
        if 55 <= nifty_rsi <= 70:
            rsi_score = 15  # Healthy bullish
        elif 45 <= nifty_rsi < 55:
            rsi_score = 5   # Neutral
        elif 30 <= nifty_rsi < 45:
            rsi_score = -10  # Weak
        elif nifty_rsi < 30:
            rsi_score = 5   # Oversold bounce potential
        elif nifty_rsi > 70:
            rsi_score = -5  # Overbought risk
        
        health_score += rsi_score
        scoring_breakdown['rsi'] = f'{rsi_score:+d} (RSI={nifty_rsi:.0f})'
        
        # ================================================================
        # FACTOR 3: VIX Level - Volatility Risk (0-25 points)
        # ================================================================
        vix_score = 0
        
        if vix_value < 12:
            vix_score = 20    # Very low volatility = complacency risk
        elif vix_value < 15:
            vix_score = 15    # Low volatility = good
        elif vix_value < 18:
            vix_score = 5     # Normal
        elif vix_value < 22:
            vix_score = -5    # Elevated
        elif vix_value < 28:
            vix_score = -15   # High volatility
        else:
            vix_score = -25   # Extreme fear
        
        health_score += vix_score
        scoring_breakdown['vix'] = f'{vix_score:+d} (VIX={vix_value:.1f})'
        
        # ================================================================
        # FACTOR 4: Price Momentum (0-15 points)
        # ================================================================
        momentum_score = 0
        
        if nifty_change > 1:
            momentum_score = 10
        elif nifty_change > 0.3:
            momentum_score = 5
        elif nifty_change > -0.3:
            momentum_score = 0
        elif nifty_change > -1:
            momentum_score = -5
        else:
            momentum_score = -10
        
        health_score += momentum_score
        scoring_breakdown['momentum'] = f'{momentum_score:+d} ({nifty_change:+.2f}%)'
        
        # ================================================================
        # FACTOR 5: Trend Strength (0-15 points)
        # ================================================================
        # Distance from SMA20 as % (trend strength indicator)
        sma20_distance = ((nifty_price - nifty_sma20) / nifty_sma20) * 100
        
        trend_score = 0
        if sma20_distance > 3:
            trend_score = 10  # Strong uptrend
        elif sma20_distance > 1:
            trend_score = 5   # Moderate uptrend
        elif sma20_distance > -1:
            trend_score = 0   # Neutral
        elif sma20_distance > -3:
            trend_score = -5  # Moderate downtrend
        else:
            trend_score = -10 # Strong downtrend
        
        health_score += trend_score
        scoring_breakdown['trend_strength'] = f'{trend_score:+d} ({sma20_distance:+.1f}% from SMA20)'
        
        # ================================================================
        # Cap between 0-100
        # ================================================================
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
            'scoring_breakdown': scoring_breakdown,
            'above_sma20': nifty_price > nifty_sma20,
            'above_sma50': nifty_price > nifty_sma50,
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

def log_trade_with_rl_learning(ticker, entry_price, exit_price, quantity, 
                                position_type, exit_reason, stock_df, sl_used, hit_sl):
    """Enhanced trade logging with RL learning"""
    
    # Original trade logging
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
        'win': pnl > 0,
        'sl_used': sl_used,
        'hit_sl': hit_sl
    }
    
    st.session_state.trade_history.append(trade)
    
    # Update stats
    stats = st.session_state.performance_stats
    stats['total_trades'] += 1
    if pnl > 0:
        stats['wins'] += 1
        stats['total_profit'] += pnl
    else:
        stats['losses'] += 1
        stats['total_loss'] += abs(pnl)
    
    # ✅ FIX: Connect to RL Optimizer
    try:
        from ai_features import rl_optimizer
        
        if stock_df is not None and not stock_df.empty:
            rl_optimizer.learn_from_trade(
                df=stock_df,
                entry_price=entry_price,
                exit_price=exit_price,
                position_type=position_type,
                sl_used=sl_used,
                hit_sl=hit_sl
            )
            logger.info(f"✅ RL Optimizer learned from {ticker} trade")
    except ImportError:
        logger.warning("RL Optimizer not available")
    except Exception as e:
        logger.error(f"RL learning failed: {e}")

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
    """
    Safely fetch stock data - NOW USES OPTIMIZED FETCHER
    Kept for backward compatibility
    """
    return fetch_stock_data_optimized(ticker, period)


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

def find_volume_weighted_sr(df: pd.DataFrame, lookback: int = 60, num_levels: int = 5) -> Dict:
    """
    Find support/resistance levels weighted by volume (Volume Profile)
    
    High volume price levels are stronger S/R than low volume levels.
    """
    if df is None or len(df) < lookback:
        return {
            'volume_supports': [],
            'volume_resistances': [],
            'poc': None,  # Point of Control
            'value_area_high': None,
            'value_area_low': None
        }
    
    recent = df.tail(lookback).copy()
    current_price = float(df['Close'].iloc[-1])
    
    if 'Volume' not in recent.columns or recent['Volume'].sum() == 0:
        return {
            'volume_supports': [],
            'volume_resistances': [],
            'poc': None,
            'value_area_high': None,
            'value_area_low': None
        }
    
    try:
        # Create price bins
        price_min = recent['Low'].min()
        price_max = recent['High'].max()
        
        if price_max <= price_min:
            return {
                'volume_supports': [],
                'volume_resistances': [],
                'poc': current_price,
                'value_area_high': current_price * 1.02,
                'value_area_low': current_price * 0.98
            }
        
        # Create 50 price bins
        num_bins = 50
        bin_size = (price_max - price_min) / num_bins
        
        volume_profile = {}
        
        for _, row in recent.iterrows():
            # Distribute volume across the price range of this candle
            candle_low = row['Low']
            candle_high = row['High']
            candle_volume = row['Volume']
            
            # Find which bins this candle spans
            start_bin = int((candle_low - price_min) / bin_size)
            end_bin = int((candle_high - price_min) / bin_size)
            
            # Distribute volume evenly across bins
            bins_spanned = max(1, end_bin - start_bin + 1)
            volume_per_bin = candle_volume / bins_spanned
            
            for bin_idx in range(start_bin, end_bin + 1):
                if 0 <= bin_idx < num_bins:
                    bin_price = price_min + (bin_idx + 0.5) * bin_size
                    volume_profile[bin_price] = volume_profile.get(bin_price, 0) + volume_per_bin
        
        if not volume_profile:
            return {
                'volume_supports': [],
                'volume_resistances': [],
                'poc': current_price,
                'value_area_high': current_price * 1.02,
                'value_area_low': current_price * 0.98
            }
        
        # Sort by volume to find high-volume nodes
        sorted_levels = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        
        # Point of Control (highest volume price)
        poc = sorted_levels[0][0]
        
        # Value Area (70% of volume)
        total_volume = sum(v for _, v in sorted_levels)
        value_area_volume = 0
        value_area_prices = []
        
        for price, vol in sorted_levels:
            value_area_prices.append(price)
            value_area_volume += vol
            if value_area_volume >= total_volume * 0.7:
                break
        
        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)
        
        # Get high volume nodes as S/R
        high_volume_nodes = sorted_levels[:num_levels * 2]
        
        # Separate into supports (below current) and resistances (above current)
        volume_supports = sorted(
            [p for p, v in high_volume_nodes if p < current_price],
            reverse=True
        )[:num_levels]
        
        volume_resistances = sorted(
            [p for p, v in high_volume_nodes if p > current_price]
        )[:num_levels]
        
        return {
            'volume_supports': volume_supports,
            'volume_resistances': volume_resistances,
            'poc': round(poc, 2),
            'value_area_high': round(value_area_high, 2),
            'value_area_low': round(value_area_low, 2),
            'total_volume_analyzed': int(total_volume)
        }
    
    except Exception as e:
        logger.error(f"Volume profile calculation failed: {e}")
        return {
            'volume_supports': [],
            'volume_resistances': [],
            'poc': None,
            'value_area_high': None,
            'value_area_low': None
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
	
def get_correlation_based_sizing(results: List[Dict], correlation_matrix, new_ticker: str) -> Dict:
    """
    Suggest position size adjustment based on correlation with existing positions
    
    If new position is highly correlated with existing holdings,
    suggest reducing size to manage concentration risk.
    """
    if correlation_matrix is None or new_ticker not in correlation_matrix.columns:
        return {
            'adjustment_factor': 1.0,
            'reason': 'No correlation data available',
            'correlated_positions': []
        }
    
    # Find existing positions
    existing_tickers = [r['ticker'] for r in results if r['ticker'] != new_ticker]
    
    # Calculate correlations with existing positions
    high_correlations = []
    
    for ticker in existing_tickers:
        if ticker in correlation_matrix.columns:
            corr = correlation_matrix.loc[new_ticker, ticker]
            if abs(corr) >= 0.5:
                high_correlations.append({
                    'ticker': ticker,
                    'correlation': corr,
                    'position_value': next((r['entry_price'] * r['quantity'] 
                                           for r in results if r['ticker'] == ticker), 0)
                })
    
    if not high_correlations:
        return {
            'adjustment_factor': 1.0,
            'reason': 'No highly correlated positions',
            'correlated_positions': []
        }
    
    # Calculate adjustment factor
    # More correlated positions = smaller suggested size
    avg_correlation = np.mean([abs(c['correlation']) for c in high_correlations])
    total_correlated_value = sum(c['position_value'] for c in high_correlations)
    
    # Adjustment: reduce by correlation level
    if avg_correlation >= 0.8:
        adjustment = 0.5  # Reduce by 50%
        reason = "Very high correlation with existing positions"
    elif avg_correlation >= 0.7:
        adjustment = 0.7  # Reduce by 30%
        reason = "High correlation with existing positions"
    elif avg_correlation >= 0.5:
        adjustment = 0.85  # Reduce by 15%
        reason = "Moderate correlation with existing positions"
    else:
        adjustment = 1.0
        reason = "Low correlation"
    
    return {
        'adjustment_factor': adjustment,
        'reason': reason,
        'avg_correlation': round(avg_correlation, 2),
        'correlated_positions': high_correlations,
        'correlated_value': total_correlated_value,
        'recommendation': f"Consider sizing at {adjustment*100:.0f}% of normal due to {reason.lower()}"
    }
    
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
    
    # Support/Resistance (Price-based)
    sr_levels = find_support_resistance(df)
    
    # Volume-weighted S/R (more reliable)
    volume_sr = find_volume_weighted_sr(df)
    
    # Merge volume S/R into main S/R if available
    if volume_sr.get('poc'):
        sr_levels['poc'] = volume_sr['poc']
        sr_levels['value_area_high'] = volume_sr['value_area_high']
        sr_levels['value_area_low'] = volume_sr['value_area_low']
        
        # Use volume S/R as primary if available
        if volume_sr.get('volume_supports'):
            sr_levels['volume_supports'] = volume_sr['volume_supports']
        if volume_sr.get('volume_resistances'):
            sr_levels['volume_resistances'] = volume_sr['volume_resistances']  
    
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
    
    else:  # SHORT position
        result['target1'] = current_price - (atr * 1.5)
        result['target2'] = current_price - (atr * 3)
        result['target3'] = max(current_price - (atr * 5), sr_levels['nearest_support'])
        
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
# KELLY CRITERION POSITION SIZING
# ============================================================================

def calculate_kelly_position_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    capital: float,
    max_position_pct: float = 25.0,
    kelly_fraction: float = 0.5  # Half-Kelly for safety
) -> Dict:
    """
    Calculate optimal position size using Kelly Criterion
    
    Args:
        win_rate: Historical win rate (0-100)
        avg_win: Average winning trade amount
        avg_loss: Average losing trade amount
        capital: Total available capital
        max_position_pct: Maximum position as % of capital
        kelly_fraction: Fraction of Kelly to use (0.5 = half-Kelly)
    
    Returns:
        Dict with position sizing recommendations
    """
    if avg_loss <= 0 or avg_win <= 0:
        return {
            'status': 'error',
            'message': 'Invalid win/loss data',
            'recommended_pct': 5.0,
            'recommended_amount': capital * 0.05
        }
    
    # Convert win rate to decimal
    p = win_rate / 100  # Probability of winning
    q = 1 - p           # Probability of losing
    
    # Calculate win/loss ratio (b in Kelly formula)
    b = avg_win / avg_loss
    
    # Kelly Formula: f* = (p * b - q) / b
    kelly_pct = ((p * b) - q) / b
    
    # Apply Kelly fraction (half-Kelly is safer)
    adjusted_kelly = kelly_pct * kelly_fraction * 100
    
    # Cap at maximum position size
    final_pct = min(max(0, adjusted_kelly), max_position_pct)
    
    # Calculate amount
    position_amount = capital * (final_pct / 100)
    
    # Determine recommendation quality
    if kelly_pct < 0:
        quality = "NEGATIVE"
        advice = "🔴 Negative expectancy - don't trade this strategy"
    elif final_pct < 5:
        quality = "CONSERVATIVE"
        advice = "🟡 Small edge - use minimal position size"
    elif final_pct < 15:
        quality = "MODERATE"
        advice = "🟢 Good edge - reasonable position size"
    else:
        quality = "AGGRESSIVE"
        advice = "🔵 Strong edge - but consider reducing for safety"
    
    return {
        'status': 'success',
        'full_kelly_pct': round(kelly_pct * 100, 2),
        'adjusted_kelly_pct': round(adjusted_kelly, 2),
        'recommended_pct': round(final_pct, 2),
        'recommended_amount': round(position_amount, 0),
        'max_allowed_pct': max_position_pct,
        'kelly_fraction_used': kelly_fraction,
        'quality': quality,
        'advice': advice,
        'inputs': {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_loss_ratio': round(b, 2)
        }
    }


def get_position_size_recommendation(ticker: str, capital: float) -> Dict:
    """
    Get position size recommendation for a specific ticker based on historical performance
    """
    # Get stock-specific history
    stock_history = get_stock_performance_history(ticker)
    
    if not stock_history.get('has_history'):
        # Use default conservative sizing
        return {
            'status': 'no_history',
            'message': f"No trade history for {ticker}. Using default 5%.",
            'recommended_pct': 5.0,
            'recommended_amount': capital * 0.05
        }
    
    return calculate_kelly_position_size(
        win_rate=stock_history['win_rate'],
        avg_win=stock_history['avg_win'],
        avg_loss=stock_history['avg_loss'],
        capital=capital
    )
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
# PARALLEL PORTFOLIO ANALYSIS - NEW IN v7.0
# ============================================================================

def analyze_portfolio_parallel(portfolio: pd.DataFrame, settings: Dict) -> List[Dict]:
    """
    Analyze entire portfolio in parallel - MAJOR PERFORMANCE BOOST
    
    Instead of analyzing stocks one-by-one (30+ seconds for 10 stocks),
    this fetches all data in parallel, then analyzes (5-8 seconds total)
    """
    
    # Extract tickers
    tickers = portfolio['Ticker'].tolist()
    
    # Step 1: Fetch all stock data in parallel
    logger.info(f"Fetching {len(tickers)} stocks in parallel...")
    stock_data = fetch_multiple_stocks_parallel(tickers, period="6mo")
    logger.info(f"Fetched {len(stock_data)} stocks successfully")
    
    # Step 2: Analyze each stock (CPU-bound, but fast)
    results = []
    
    for _, row in portfolio.iterrows():
        ticker = str(row['Ticker']).strip()
        
        # Get the DataFrame - handle both ticker formats
        df = None
        
        # Try exact ticker first
        if ticker in stock_data:
            df = stock_data[ticker]
        # Try with .NS suffix
        elif f"{ticker}.NS" in stock_data:
            df = stock_data[f"{ticker}.NS"]
        # Try without .NS suffix (if ticker already has it)
        elif ticker.replace('.NS', '').replace('.BO', '') in stock_data:
            df = stock_data[ticker.replace('.NS', '').replace('.BO', '')]
        
        # Skip if no data found
        if df is None:
            logger.warning(f"No data for {ticker}, skipping...")
            continue
        
        # Skip if DataFrame is empty
        if isinstance(df, pd.DataFrame) and df.empty:
            logger.warning(f"Empty data for {ticker}, skipping...")
            continue
        
        # Analyze with pre-fetched data
        result = smart_analyze_position_with_data(
            df=df,
            ticker=ticker,
            position_type=str(row['Position']).upper().strip(),
            entry_price=float(row['Entry_Price']),
            quantity=int(row.get('Quantity', 1)),
            stop_loss=float(row['Stop_Loss']),
            target1=float(row['Target_1']),
            target2=float(row.get('Target_2', row['Target_1'] * 1.1)),
            trail_threshold=settings['trail_sl_trigger'],
            sl_alert_threshold=settings['sl_risk_threshold'],
            sl_approach_threshold=settings['sl_approach_threshold'],
            enable_mtf=settings['enable_multi_timeframe'],
            entry_date=row.get('Entry_Date', None)
        )
        
        if result:
            # Create memory-optimized version
            minimal_result = create_minimal_result(result)
            results.append(minimal_result)
    
    return results


def smart_analyze_position_with_data(df, ticker, position_type, entry_price, quantity,
                                      stop_loss, target1, target2, trail_threshold=2.0,
                                      sl_alert_threshold=50, sl_approach_threshold=2.0,
                                      enable_mtf=True, entry_date=None):
    """
    Smart analysis using PRE-FETCHED data (no API calls inside)
    This is called by the parallel analyzer
    """
    
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
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
    
    # Multi-Timeframe Analysis (OPTIMIZED - cached separately)
    if enable_mtf:
        mtf_result = get_cached_mtf_analysis(ticker, position_type)
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
    
    # Priority 2: High SL Risk
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
    
    # Priority 6: Target 1 Hit
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
            'message': f'{dynamic_levels.get("trail_reason", "Lock profits!")}',
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
            'message': f'Position at breakeven.',
            'action': f'Move SL to ₹{entry_price:.2f}',
            'email_type': 'important'
        })
        if overall_status == 'OK':
            overall_status = 'GOOD'
            overall_action = 'MOVE_SL_BREAKEVEN'
    
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
        
        # Chart Data (stored separately, not full DataFrame)
        'df': df  # This will be converted to minimal by create_minimal_result
    }


def get_cached_mtf_analysis(ticker: str, position_type: str) -> Dict:
    """
    Get MTF analysis with caching to avoid repeated API calls
    """
    cache_key = f"mtf_{ticker}_{position_type}"
    
    # Check cache
    cached = data_cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Fetch fresh (this still makes API calls, but cached)
    result = multi_timeframe_analysis(ticker, position_type)
    
    # Cache the result
    data_cache.set(cache_key, result)
    
    return result
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
    """Load portfolio from Google Sheets"""
    
    # Your Google Sheets URL
    GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/155htPsyom2e-dR5BZJx_cFzGxjQQjePJt3H2sRLSr6w/edit?usp=sharing"
    
    try:
        # Convert to export URL
        sheet_id = GOOGLE_SHEETS_URL.split('/d/')[1].split('/')[0]
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
        
        # Read from Google Sheets
        df = pd.read_csv(export_url)
        
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
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE']
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
# EMAIL ALERT FUNCTIONS
# ============================================================================

def should_send_email(alert, email_settings, result, ai_enhanced=None):
    """
    Determine if email should be sent for this alert
    """
    email_type = alert.get('email_type', 'important')
    
    if email_type == 'critical' and email_settings.get('email_on_critical', True):
        return True
    # NEW: AI-triggered email
    if ai_enhanced and ai_enhanced.get('ai_score', 0) <= -50:
        if email_settings.get('email_on_critical', True):
            return True  # AI says EXIT NOW = critical email
        
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
    # Send to Telegram/Discord if configured
    try:
        from ai_features import send_telegram_alert, send_discord_alert, AI_CONFIG
        
        # Only for critical alerts
        if critical_count > 0:
            # Build message
            msg_lines = [
                f"🚨 <b>PORTFOLIO ALERT</b> 🚨",
                f"",
                f"Critical: {critical_count} | Warnings: {warning_count}",
                f"Total P&L: ₹{sum(r['pnl_amount'] for r in results):+,.0f}",
                f"",
            ]
            
            for r in results:
                if r['overall_status'] == 'CRITICAL':
                    msg_lines.append(
                        f"🔴 <b>{r['ticker']}</b>: {r['pnl_percent']:+.1f}% | "
                        f"{r['overall_action'].replace('_', ' ')}"
                    )
            
            message = "\n".join(msg_lines)
            
            # Send to Telegram if configured
            if AI_CONFIG.get('telegram_bot_token'):
                send_telegram_alert(message, parse_mode='HTML')
            
            # Send to Discord if configured
            if AI_CONFIG.get('discord_webhook_url'):
                # Convert to plain text for Discord
                plain_message = message.replace('<b>', '**').replace('</b>', '**')
                send_discord_alert(plain_message, title="Portfolio Alert", color=0xFF0000)
    
    except ImportError:
        pass  # ai_features not available
    except Exception as e:
        logger.warning(f"Failed to send Telegram/Discord alerts: {e}")
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
                # Additional validations
                if calc_entry <= 0:
                    st.error("❌ Entry price must be positive")
                elif calc_sl <= 0:
                    st.error("❌ Stop loss must be positive")
                elif calc_capital < calc_entry:
                    st.error("❌ Capital must be greater than entry price")
                elif calc_risk_pct > 5:
                    st.warning("⚠️ Risk > 5% per trade is very aggressive")
                              
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

            with st.expander("📊 AI Position Size (Based on History)", expanded=False):
                st.markdown("**Uses your trade history to calculate optimal size**")
                
                ps_ticker = st.text_input(
                    "Ticker for sizing", 
                    placeholder="RELIANCE",
                    key="ps_ai_ticker"
                )
                ps_capital = st.number_input(
                    "Available Capital (₹)",
                    min_value=10000.0,
                    value=100000.0,
                    step=10000.0,
                    key="ps_ai_capital"
                )
                
                if st.button("Calculate AI Position Size", key="calc_ai_ps"):
                    if ps_ticker:
                        result = get_position_size_recommendation(ps_ticker.upper(), ps_capital)
                        
                        if result.get('status') == 'success':
                            st.success(f"**Recommended: {result['recommended_pct']:.1f}% = ₹{result['recommended_amount']:,.0f}**")
                            st.info(result['advice'])
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Full Kelly", f"{result['full_kelly_pct']:.1f}%")
                                st.metric("Win Rate", f"{result['inputs']['win_rate']:.1f}%")
                            with col2:
                                st.metric("Quality", result['quality'])
                                st.metric("Win/Loss Ratio", f"{result['inputs']['win_loss_ratio']:.2f}")
                        else:
                            st.warning(result.get('message', 'No history available'))
                            st.info("Using default 5% position size")
                    else:
                        st.error("Enter a ticker symbol")
        
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
        # RESET DATA - ENHANCED
        # =====================================================================
        st.markdown("### 🔄 Reset & Cache")
        
        with st.expander("Reset Options", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Reset Stats", use_container_width=True, key="reset_stats"):
                    st.session_state.performance_stats = {
                        'total_trades': 0, 'wins': 0, 'losses': 0,
                        'total_profit': 0, 'total_loss': 0
                    }
                    st.session_state.trade_history = []
                    st.session_state.max_drawdown = 0
                    st.session_state.current_drawdown = 0
                    st.session_state.peak_portfolio_value = 0
                    st.success("✅ Stats reset!")
                    time.sleep(0.5)
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Clear All Cache", use_container_width=True, key="clear_cache"):
                    # Clear Streamlit cache
                    st.cache_data.clear()
                    # Clear custom cache
                    data_cache.clear()
                    st.success("✅ All cache cleared!")
                    time.sleep(0.5)
                    st.rerun()
            
            if st.button("🗑️ Reset Email Log", use_container_width=True, key="reset_email"):
                st.session_state.email_log = []
                st.session_state.email_sent_alerts = {}
                st.session_state.last_email_time = {}
                st.success("✅ Email log reset!")
            
            # Show cache stats
            st.caption(f"📊 Cached items: {len(data_cache.cache)}")
            st.caption(f"🔄 API calls: {st.session_state.get('api_call_count', 0)}")
        
        # =====================================================================
        # AI FEATURES (OPTIONAL) - FIXED VERSION
        # =====================================================================
        st.markdown("### 🤖 AI Features")

        with st.expander("AI Analysis & Backtesting", expanded=False):
            st.info("🔧 AI features require additional setup")
            
            # Check if AI module is available - FIXED IMPORTS
            try:
                from ai_features import (
                    run_simple_backtest,
                    get_available_features,  # ✅ Changed from optimize_portfolio_weights
                    AVAILABLE_FEATURES       # ✅ Changed from AI_CONFIG
                )
                ai_available = True
                ai_error = None
            except ImportError as e:
                ai_available = False
                ai_error = str(e)
            
            if ai_available:
                st.success("✅ AI module loaded")
                
                # Backtesting
                st.markdown("#### 📊 Quick Backtest")
                bt_ticker = st.text_input("Ticker for Backtest", value="RELIANCE", key="bt_ticker")
                bt_col1, bt_col2 = st.columns(2)
                with bt_col1:
                    bt_sl = st.number_input("SL %", value=3.0, step=0.5, key="bt_sl")
                with bt_col2:
                    bt_target = st.number_input("Target %", value=6.0, step=0.5, key="bt_target")
                
                if st.button("🔬 Run Backtest", use_container_width=True, key="run_backtest"):
                    with st.spinner("Running backtest..."):
                        results = run_simple_backtest(bt_ticker, "1y", bt_sl, bt_target)
                    
                    if results.get('status') == 'success':
                        summary = results.get('summary', {})
                        st.success(f"✅ Backtest Complete: {summary.get('total_trades', 0)} trades")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Win Rate", f"{summary.get('win_rate', 0):.1f}%")
                        with col2:
                            pf = summary.get('profit_factor', 0)
                            st.metric("Profit Factor", f"{pf:.2f}" if isinstance(pf, (int, float)) else pf)
                        with col3:
                            st.metric("Net P&L", f"₹{summary.get('net_pnl', 0):+,.0f}")
                    else:
                        st.error(f"❌ {results.get('message', 'Unknown error')}")
            else:
                st.warning(f"⚠️ AI module error: {ai_error}")
                st.caption("Check the import in ai_features.py")

        # =====================================================================
        # DEBUG INFO
        # =====================================================================
        with st.expander("🔧 Debug & Developer Options"):
            debug_mode = st.checkbox(
                "Enable Debug Mode",
                value=st.session_state.get('debug_mode', False),
                key="debug_mode_toggle",
                help="Shows additional technical information"
            )
            st.session_state['debug_mode'] = debug_mode
            
            if debug_mode:
                st.warning("⚠️ Debug mode enabled - additional logging active")
                
                # Show memory usage
                import sys
                
                st.markdown("**Memory Usage:**")
                cache_size = len(data_cache.cache)
                st.caption(f"Cache entries: {cache_size}")
                st.caption(f"Trade history: {len(st.session_state.get('trade_history', []))} trades")
                st.caption(f"Email log: {len(st.session_state.get('email_log', []))} entries")
                
                # Clear individual caches
                st.markdown("**Clear Specific Caches:**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Clear Data Cache", key="clear_data_cache"):
                        data_cache.clear()
                        st.success("Data cache cleared")
                with col2:
                    if st.button("Clear ST Cache", key="clear_st_cache"):
                        st.cache_data.clear()
                        st.success("Streamlit cache cleared")
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
        
        # =====================================================================
        # AI/ML FEATURES TAB
        # =====================================================================
        st.markdown("### 🤖 AI/ML Features")
        
        # Check if AI module is available
        try:
            from ai_features import (
                get_available_features,
                run_simple_backtest,
                get_rl_optimized_sl,
                monte_carlo_portfolio_optimization,
                predict_price_lstm,
                detect_market_regime,
                get_real_sentiment,
                rl_optimizer
            )
            ai_available = True
        except ImportError as e:
            ai_available = False
            ai_error = str(e)
        
        if ai_available:
            features = get_available_features()
            available_count = sum(1 for f in features.values() if f['available'])
            
            st.success(f"✅ AI Module Loaded ({available_count}/{len(features)} features)")
            
            with st.expander("🧪 AI Features", expanded=False):
                # Show available features
                st.markdown("**Available Features:**")
                for name, info in features.items():
                    status = "✅" if info['available'] else "❌"
                    st.caption(f"{status} {name.replace('_', ' ').title()}")
                
                st.divider()
                
                # Quick Backtest
                st.markdown("#### 📊 Quick Backtest")
                bt_ticker = st.text_input("Ticker", value="RELIANCE", key="ai_bt_ticker")
                bt_col1, bt_col2 = st.columns(2)
                with bt_col1:
                    bt_sl = st.number_input("SL %", value=3.0, step=0.5, key="ai_bt_sl")
                with bt_col2:
                    bt_target = st.number_input("Target %", value=6.0, step=0.5, key="ai_bt_target")
                
                if st.button("🔬 Run Backtest", use_container_width=True, key="ai_run_bt"):
                    with st.spinner("Running backtest..."):
                        result = run_simple_backtest(bt_ticker, "1y", bt_sl, bt_target)
                    
                    if result.get('status') == 'success':
                        summary = result['summary']
                        st.success(f"✅ {summary['total_trades']} trades analyzed")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Win Rate", f"{summary['win_rate']:.1f}%")
                        with col2:
                            pf = summary['profit_factor']
                            st.metric("Profit Factor", f"{pf}" if isinstance(pf, str) else f"{pf:.2f}")
                        with col3:
                            st.metric("Net P&L", f"₹{summary['net_pnl']:+,.0f}")
                        
                        # Risk metrics
                        risk = result['risk_metrics']
                        st.caption(f"Max DD: {risk['max_drawdown']:.1f}% | Avg Win: ₹{risk['avg_win']:.0f} | Avg Loss: ₹{risk['avg_loss']:.0f}")
                    else:
                        st.error(f"❌ {result.get('message', 'Unknown error')}")
                
                st.divider()
                
                # RL Stop Loss Stats
                st.markdown("#### 🎯 RL Stop Loss Optimizer")
                rl_stats = rl_optimizer.get_stats()
                st.caption(f"States learned: {rl_stats['states_learned']} | Trades: {rl_stats['trades_processed']}")
                st.caption(f"Avg multiplier: {rl_stats['avg_multiplier']:.2f}x ATR")
        else:
            st.warning("⚠️ AI module not loaded")
            with st.expander("Setup Instructions"):
                st.markdown(f"**Error:** `{ai_error}`")
                st.markdown("""
                **To enable AI features:**
                1. Create `ai_features.py` in the same folder
                2. Install dependencies:
                ```bash
                pip install scikit-learn scipy hmmlearn
                pip install tensorflow  # For LSTM
                pip install transformers torch  # For sentiment
                ```
                3. Restart the app
                """)
        
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

         # Trade Journal Export
        if st.session_state.trade_history:
            st.divider()
            st.markdown("### 📔 Trade Journal Export")
            
            col1, col2 = st.columns(2)
            
            with col1:
                export_format = st.selectbox(
                    "Export Format",
                    ["CSV", "JSON", "Excel-ready CSV"],
                    key="journal_export_format"
                )
            
            with col2:
                include_analysis = st.checkbox(
                    "Include detailed analysis", 
                    value=True,
                    key="include_analysis"
                )
            
            # Prepare export data
            journal_data = []
            
            for trade in st.session_state.trade_history:
                entry = {
                    'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                    'Ticker': trade['ticker'],
                    'Type': trade['type'],
                    'Entry_Price': trade['entry'],
                    'Exit_Price': trade['exit'],
                    'Quantity': trade['quantity'],
                    'P&L_Amount': round(trade['pnl'], 2),
                    'P&L_Percent': round(trade['pnl_pct'], 2),
                    'Result': 'WIN' if trade['win'] else 'LOSS',
                    'Exit_Reason': trade['reason']
                }
                
                if include_analysis:
                    # Add computed fields
                    entry['Risk_Amount'] = round(abs(trade['pnl']) if not trade['win'] else 0, 2)
                    entry['Reward_Amount'] = round(trade['pnl'] if trade['win'] else 0, 2)
                    
                    # Add holding period if available
                    if 'holding_days' in trade:
                        entry['Holding_Days'] = trade['holding_days']
                
                journal_data.append(entry)
            
            df_journal = pd.DataFrame(journal_data)
            
            if export_format == "CSV":
                csv_data = df_journal.to_csv(index=False)
                st.download_button(
                    "📥 Download Trade Journal (CSV)",
                    csv_data,
                    file_name=f"trade_journal_{get_ist_now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="download_journal_csv"
                )
            
            elif export_format == "JSON":
                json_data = df_journal.to_json(orient='records', indent=2, date_format='iso')
                st.download_button(
                    "📥 Download Trade Journal (JSON)",
                    json_data,
                    file_name=f"trade_journal_{get_ist_now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    key="download_journal_json"
                )
            
            else:  # Excel-ready CSV
                # Add summary row
                summary_row = {
                    'Date': 'SUMMARY',
                    'Ticker': f"{len(journal_data)} trades",
                    'Type': '',
                    'Entry_Price': '',
                    'Exit_Price': '',
                    'Quantity': '',
                    'P&L_Amount': round(sum(t['P&L_Amount'] for t in journal_data), 2),
                    'P&L_Percent': round(np.mean([t['P&L_Percent'] for t in journal_data]), 2),
                    'Result': f"{sum(1 for t in journal_data if t['Result']=='WIN')}/{len(journal_data)} wins",
                    'Exit_Reason': ''
                }
                
                journal_data.append(summary_row)
                df_excel = pd.DataFrame(journal_data)
                
                csv_data = df_excel.to_csv(index=False)
                st.download_button(
                    "📥 Download Trade Journal (Excel-ready)",
                    csv_data,
                    file_name=f"trade_journal_excel_{get_ist_now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="download_journal_excel"
                )           
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
# AI-ENHANCED DECISION MAKING - INTEGRATES AI SIGNALS INTO ALERTS
# ============================================================================

def get_ai_enhanced_recommendation(result: Dict, market_health: Dict) -> Dict:
    """
    Enhance the standard recommendation with AI signals
    This actually changes the exit/stay decision based on AI
    
    Returns:
        Dict with enhanced recommendation and AI factors
    """
    
    # Start with the standard recommendation
    original_status = result.get('overall_status', 'OK')
    original_action = result.get('overall_action', 'HOLD')
    
    ai_factors = []
    ai_score = 0  # -100 (strong exit) to +100 (strong hold)
    
    # Try to load AI features
    try:
        from ai_features import (
            detect_market_regime,
            get_rl_optimized_sl,
            predict_price_lstm,
            get_real_sentiment,
            AVAILABLE_FEATURES
        )
        ai_available = True
    except ImportError:
        ai_available = False
        return {
            'status': original_status,
            'action': original_action,
            'ai_enhanced': False,
            'ai_factors': [],
            'ai_score': 0
        }
    
    # =========================================================================
    # FACTOR 1: MARKET REGIME (Weight: 30%)
    # =========================================================================
    if market_health:
        regime = market_health.get('status', 'NEUTRAL')
        
        if regime == 'BEARISH':
            ai_score -= 30
            ai_factors.append({
                'factor': 'Market Regime',
                'signal': 'BEARISH',
                'impact': -30,
                'action': '🔴 Market bearish - reduce exposure'
            })
        elif regime == 'WEAK':
            ai_score -= 15
            ai_factors.append({
                'factor': 'Market Regime',
                'signal': 'WEAK',
                'impact': -15,
                'action': '🟠 Weak market - be cautious'
            })
        elif regime == 'BULLISH':
            ai_score += 20
            ai_factors.append({
                'factor': 'Market Regime',
                'signal': 'BULLISH',
                'impact': +20,
                'action': '🟢 Bullish market - can hold'
            })
    
    # =========================================================================
    # FACTOR 2: POSITION ANALYSIS (Weight: 25%)
    # =========================================================================
    pnl_pct = result.get('pnl_percent', 0)
    sl_risk = result.get('sl_risk', 0)
    position_type = result.get('position_type', 'LONG')
    
    # Losing position in weak market = EXIT
    if pnl_pct < -3 and market_health and market_health.get('status') in ['BEARISH', 'WEAK']:
        ai_score -= 25
        ai_factors.append({
            'factor': 'Loss + Weak Market',
            'signal': 'DANGER',
            'impact': -25,
            'action': f'🚨 Losing {pnl_pct:.1f}% in weak market - EXIT'
        })
    
    # High SL risk = EXIT warning
    if sl_risk >= 70:
        ai_score -= 20
        ai_factors.append({
            'factor': 'High SL Risk',
            'signal': 'CRITICAL',
            'impact': -20,
            'action': f'⚠️ SL Risk {sl_risk}% - very likely to hit SL'
        })
    elif sl_risk >= 50:
        ai_score -= 10
        ai_factors.append({
            'factor': 'Moderate SL Risk',
            'signal': 'WARNING',
            'impact': -10,
            'action': f'🟡 SL Risk {sl_risk}% - monitor closely'
        })
    
    # =========================================================================
    # FACTOR 3: RL STOP LOSS SUGGESTION (Weight: 15%)
    # =========================================================================
    if 'chart_data' in result:
        try:
            import pandas as pd
            df = pd.DataFrame(result['chart_data'])
            
            if not df.empty and len(df) >= 20:
                rl_result = get_rl_optimized_sl(
                    df, 
                    result['entry_price'], 
                    result['current_price'], 
                    position_type
                )
                
                current_sl = result.get('stop_loss', 0)
                rl_sl = rl_result.get('optimal_sl', current_sl)
                
                # If RL suggests tighter SL than current
                if position_type == "LONG" and rl_sl > current_sl:
                    improvement = ((rl_sl - current_sl) / current_sl) * 100
                    ai_factors.append({
                        'factor': 'RL Stop Loss',
                        'signal': 'TIGHTEN',
                        'impact': 0,
                        'action': f'🎯 RL suggests tighter SL: ₹{rl_sl:.2f} (+{improvement:.1f}%)'
                    })
                elif position_type == "SHORT" and rl_sl < current_sl:
                    improvement = ((current_sl - rl_sl) / current_sl) * 100
                    ai_factors.append({
                        'factor': 'RL Stop Loss',
                        'signal': 'TIGHTEN',
                        'impact': 0,
                        'action': f'🎯 RL suggests tighter SL: ₹{rl_sl:.2f} (-{improvement:.1f}%)'
                    })
        except Exception as e:
            pass  # RL analysis failed, continue without it
    
    # =========================================================================
    # FACTOR 4: MOMENTUM & TREND (Weight: 20%)
    # =========================================================================
    momentum = result.get('momentum_score', 50)
    mtf_alignment = result.get('mtf_alignment', 50)
    
    # Against position
    if position_type == "LONG":
        if momentum < 35:
            ai_score -= 15
            ai_factors.append({
                'factor': 'Weak Momentum',
                'signal': 'BEARISH',
                'impact': -15,
                'action': f'📉 Momentum only {momentum}/100 - against LONG'
            })
        elif momentum > 65:
            ai_score += 15
            ai_factors.append({
                'factor': 'Strong Momentum',
                'signal': 'BULLISH',
                'impact': +15,
                'action': f'📈 Momentum {momentum}/100 - supports LONG'
            })
        
        if mtf_alignment < 40:
            ai_score -= 10
            ai_factors.append({
                'factor': 'MTF Against',
                'signal': 'WARNING',
                'impact': -10,
                'action': f'📊 Only {mtf_alignment}% timeframes aligned'
            })
    else:  # SHORT
        if momentum > 65:
            ai_score -= 15
            ai_factors.append({
                'factor': 'Against Momentum',
                'signal': 'BULLISH',
                'impact': -15,
                'action': f'📈 Momentum {momentum}/100 - against SHORT'
            })
        elif momentum < 35:
            ai_score += 15
            ai_factors.append({
                'factor': 'Supports Position',
                'signal': 'BEARISH',
                'impact': +15,
                'action': f'📉 Momentum {momentum}/100 - supports SHORT'
            })
    
    # =========================================================================
    # FACTOR 5: PROFIT PROTECTION (Weight: 10%)
    # =========================================================================
    if pnl_pct >= 5:
        # In profit - be more defensive
        if momentum < 50 or (market_health and market_health.get('status') in ['BEARISH', 'WEAK']):
            ai_factors.append({
                'factor': 'Profit Protection',
                'signal': 'BOOK',
                'impact': -10,
                'action': f'💰 {pnl_pct:.1f}% profit + weak signals - BOOK PROFITS'
            })
            ai_score -= 10
    
    # =========================================================================
    # CALCULATE FINAL AI-ENHANCED RECOMMENDATION
    # =========================================================================
    
    # Determine AI recommendation based on score
    if ai_score <= -50:
        ai_recommendation = 'EXIT_NOW'
        ai_status = 'CRITICAL'
        ai_message = '🚨 AI: Strong EXIT signal - multiple factors against position'
    elif ai_score <= -30:
        ai_recommendation = 'EXIT_EARLY'
        ai_status = 'WARNING'
        ai_message = '⚠️ AI: Consider exiting - unfavorable conditions'
    elif ai_score <= -10:
        ai_recommendation = 'REDUCE'
        ai_status = 'CAUTION'
        ai_message = '🟡 AI: Reduce exposure or tighten stops'
    elif ai_score >= 30:
        ai_recommendation = 'HOLD_STRONG'
        ai_status = 'GOOD'
        ai_message = '🟢 AI: Strong hold - favorable conditions'
    elif ai_score >= 10:
        ai_recommendation = 'HOLD'
        ai_status = 'OK'
        ai_message = '✅ AI: Can hold - conditions acceptable'
    else:
        ai_recommendation = 'WATCH'
        ai_status = 'NEUTRAL'
        ai_message = '👀 AI: Neutral - monitor for changes'
    
    # Override original if AI signal is stronger
    final_status = original_status
    final_action = original_action
    
    # AI can escalate but not de-escalate critical situations
    if original_status == 'CRITICAL':
        final_status = 'CRITICAL'
        final_action = original_action
    elif ai_status == 'CRITICAL' and ai_score <= -50:
        final_status = 'CRITICAL'
        final_action = 'EXIT_NOW'
    elif ai_status == 'WARNING' and ai_score <= -30:
        final_status = 'WARNING'
        final_action = ai_recommendation
    
    return {
        'original_status': original_status,
        'original_action': original_action,
        'ai_status': ai_status,
        'ai_action': ai_recommendation,
        'ai_score': ai_score,
        'ai_message': ai_message,
        'ai_factors': ai_factors,
        'final_status': final_status,
        'final_action': final_action,
        'ai_enhanced': True
    }
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
    # HEADER ROW (Market Status + Time + Refresh Button)
    # =========================================================================
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown(f"### {market_icon} {market_status}")
        st.caption(market_msg)
    
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
        st.caption(ist_now.strftime('%A, %B %d, %Y'))
    
    with col3:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # =========================================================================
    # ✅ GAP 1: MARKET HEALTH DISPLAY (OUTSIDE COLUMNS - FULL WIDTH!)
    # =========================================================================
    st.divider()
    
    market_health = get_market_health()
    
    if market_health:
        st.markdown(f"""
        <div style='background:{market_health['color']}20; padding:20px; border-radius:12px; 
                    border-left:5px solid {market_health['color']}; margin:15px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <h2 style='margin:0; color:{market_health['color']};'>
                        {market_health['icon']} Market Health: {market_health['status']}
                    </h2>
                    <p style='margin:8px 0; font-size:1.1em;'>{market_health['message']}</p>
                    <p style='margin:8px 0; font-weight:bold; font-size:1.05em;'>{market_health['action']}</p>
                </div>
                <div style='text-align:center; min-width:100px;'>
                    <h1 style='margin:0; color:{market_health['color']};'>{market_health['health_score']}</h1>
                    <p style='margin:0; font-size:0.9em;'>Health Score</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Show detailed metrics in expander
        with st.expander("📊 Market Details", expanded=False):
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            
            with m_col1:
                st.metric("NIFTY 50", f"₹{market_health['nifty_price']:,.0f}", 
                         f"{market_health['nifty_change']:+.2f}%")
            
            with m_col2:
                st.metric("RSI", f"{market_health['nifty_rsi']:.1f}")
            
            with m_col3:
                st.metric("India VIX", f"{market_health['vix']:.1f}")
            
            with m_col4:
                st.metric("Trend", "Bullish" if market_health['above_sma20'] else "Bearish")
            
            # Technical levels
            st.caption(f"NIFTY SMA20: ₹{market_health['nifty_sma20']:,.0f} | SMA50: ₹{market_health['nifty_sma50']:,.0f}")
        
        # ✅ AUTO-ADJUST SL THRESHOLDS BASED ON MARKET
        if market_health['sl_adjustment'] == 'AGGRESSIVE':
            settings['sl_risk_threshold'] = max(30, settings['sl_risk_threshold'] - 20)
            st.warning(f"⚠️ SL Risk threshold auto-adjusted to {settings['sl_risk_threshold']}% due to weak market")
        elif market_health['sl_adjustment'] == 'TIGHTEN':
            settings['sl_risk_threshold'] = max(35, settings['sl_risk_threshold'] - 10)
            st.info(f"ℹ️ SL Risk threshold adjusted to {settings['sl_risk_threshold']}% (cautious mode)")
    
    else:
        market_health = None  # Set to None if fetch failed
        st.warning("⚠️ Unable to fetch market health data")
    
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
    # ANALYZE ALL POSITIONS - PARALLEL OPTIMIZED (v7.0)
    # =========================================================================
    
    with st.spinner("🚀 Analyzing portfolio in parallel..."):
        start_time = time.time()
        
        # Use parallel analysis
        results = analyze_portfolio_parallel(portfolio, settings)
        # =========================================================================
        # AI TRADING BRAIN - DYNAMIC LEVEL ADJUSTMENT
        # =========================================================================
        
        ai_recommendations = []
        ai_updates_available = False
        
        try:
            from ai_trading_brain import analyze_portfolio, trading_brain
            from google_sheets_manager import sheets_manager, update_portfolio_from_ai
            
            # Convert results to stock_data dict for AI brain
            stock_data_for_ai = {}
            for r in results:
                if 'chart_data' in r:
                    stock_data_for_ai[r['ticker']] = pd.DataFrame(r['chart_data'])
            
            # Run AI analysis on all positions
            with st.spinner("🧠 AI analyzing positions for dynamic adjustments..."):
                ai_recommendations = analyze_portfolio(
                    portfolio=portfolio,
                    stock_data=stock_data_for_ai,
                    market_health=market_health
                )
            
            # Check for updates
            updates_with_changes = [r for r in ai_recommendations if r.get('any_change')]
            ai_updates_available = len(updates_with_changes) > 0
            
            if ai_updates_available:
                st.info(f"🤖 AI suggests updates for {len(updates_with_changes)} position(s)")
        
        except ImportError:
            st.caption("💡 AI Trading Brain not available. Create `ai_trading_brain.py` for dynamic adjustments.")
        except Exception as e:
            logger.warning(f"AI analysis error: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Portfolio analysis completed in {elapsed:.2f}s")
    
    # Show performance stats
    st.caption(f"✅ Analyzed {len(results)} positions in {elapsed:.1f}s")
    
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
    st.markdown("### 📊 Portfolio Summary")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        pnl_delta = f"{pnl_percent_total:+.2f}%"
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}", pnl_delta)
    with col2:
        st.metric("📊 Positions", len(results))
    with col3:
        st.metric("🔴 Critical", critical_count)
    with col4:
        st.metric("🟡 Warning", warning_count)
    with col5:
        st.metric("🟢 Good", good_count)
    with col6:
        st.metric("🔵 Opportunity", opportunity_count)
    with col7:
        st.metric("✅ Success", success_count)
    
    st.divider()
    # =========================================================================
    # AI LEVEL RECOMMENDATIONS (FIXED VERSION)
    # =========================================================================
    if 'apply_ai_recommendations' not in st.session_state:
         st.session_state.apply_ai_recommendations = False
    if ai_updates_available and ai_recommendations:
        st.divider()
        st.markdown("### 🤖 AI Dynamic Level Recommendations")
        
        updates_with_changes = [r for r in ai_recommendations if r.get('any_change')]
        
        col1, col2, col3 = st.columns([2, 1, 1])
            
        with col1:
            st.markdown(f"**{len(updates_with_changes)} position(s)** have suggested updates")
            
        with col2:
            auto_update = st.checkbox("Auto-update Sheet", value=False, key="auto_update_sheet")
            
        with col3:
            apply_all = st.form_submit_button("📝 Apply All to Sheet", type="primary")
        
        # ✅ FIXED: Only run when button is clicked
        if st.session_state.apply_ai_recommendations:
            try:
                from google_sheets_manager import update_portfolio_from_ai
                result = update_portfolio_from_ai(ai_recommendations)
                
                if result.get('updates_successful', 0) > 0:
                    st.success(f"✅ Updated {result['updates_successful']} position(s) in Google Sheet!")
                    st.balloons()
                    st.session_state.apply_ai_recommendations = False  
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⚠️ No updates applied. Check if Sheet API is configured.")
                    st.session_state.apply_ai_recommendations = False  
            except Exception as e:
                st.error(f"❌ Update failed: {e}")
                st.session_state.apply_ai_recommendations = False
        
        # Show each recommendation
        for idx, rec in enumerate(updates_with_changes):
            changes = rec.get('changes', {})
            priority_color = "#dc3545" if rec.get('priority') == 'HIGH' else "#ffc107"
            
            with st.expander(
                f"{'🔴' if rec.get('priority') == 'HIGH' else '🟡'} **{rec['ticker']}** - {rec['action'].replace('_', ' ')} | "
                f"Confidence: {rec.get('confidence', 0)}%",
                expanded=(rec.get('priority') == 'HIGH')
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### Current Levels")
                    st.write(f"**Entry:** ₹{rec['entry_price']:,.2f}")
                    st.write(f"**Current:** ₹{rec['current_price']:,.2f}")
                    st.write(f"**P&L:** {rec['pnl_pct']:+.2f}%")
                    st.divider()
                    st.write(f"**Original SL:** ₹{rec['original_sl']:,.2f}")
                    st.write(f"**Original T1:** ₹{rec['original_target1']:,.2f}")
                    st.write(f"**Original T2:** ₹{rec['original_target2']:,.2f}")
                
                with col2:
                    st.markdown("##### 🆕 AI Recommended Levels")
                    
                    # SL
                    sl_change = changes.get('sl_change_pct', 0)
                    sl_color = "green" if sl_change > 0 else "red" if sl_change < 0 else "gray"
                    st.markdown(f"**New SL:** <span style='color:{sl_color}; font-weight:bold;'>₹{rec['new_sl']:,.2f}</span> ({sl_change:+.1f}%)", 
                               unsafe_allow_html=True)
                    st.caption(f"Reason: {rec.get('sl_reason', 'N/A')}")
                    
                    # Target 1
                    t1_change = changes.get('target1_change_pct', 0)
                    t1_color = "green" if t1_change > 0 else "red" if t1_change < 0 else "gray"
                    st.markdown(f"**New T1:** <span style='color:{t1_color}; font-weight:bold;'>₹{rec['new_target1']:,.2f}</span> ({t1_change:+.1f}%)", 
                               unsafe_allow_html=True)
                    st.caption(f"Reason: {rec.get('target1_reason', 'N/A')}")
                    
                    # Target 2
                    t2_change = changes.get('target2_change_pct', 0)
                    t2_color = "green" if t2_change > 0 else "red" if t2_change < 0 else "gray"
                    st.markdown(f"**New T2:** <span style='color:{t2_color}; font-weight:bold;'>₹{rec['new_target2']:,.2f}</span> ({t2_change:+.1f}%)", 
                               unsafe_allow_html=True)
                    st.caption(f"Reason: {rec.get('target2_reason', 'N/A')}")
                
                # Analysis summary
                st.divider()
                st.markdown(f"**Trend:** {rec.get('trend', 'N/A')} | **Confidence:** {rec.get('confidence', 0)}%")
                st.markdown(f"📊 Bullish Score: {rec.get('bullish_score', 0)} | Bearish Score: {rec.get('bearish_score', 0)}")
                
                # ✅ FIXED: Individual update button with proper form structure
                with st.form(key=f"apply_form_{rec['ticker']}_{idx}", clear_on_submit=False):
                    form_col1, form_col2 = st.columns([1, 1])
                    
                    with form_col1:
                        apply_single = st.form_submit_button(f"✅ Apply to {rec['ticker']}", use_container_width=True)
                    
                    with form_col2:
                        ignore_btn = st.form_submit_button("❌ Ignore", use_container_width=True)
                
                # Handle button clicks (outside form, but checking the variable)
                if apply_single:
                    try:
                        from google_sheets_manager import sheets_manager
                        success = sheets_manager.update_position_levels(
                            ticker=rec['ticker'],
                            new_sl=rec['new_sl'],
                            new_target1=rec['new_target1'],
                            new_target2=rec['new_target2'],
                            reason=rec.get('summary', 'AI recommendation')
                        )
                        if success:
                            st.success(f"✅ {rec['ticker']} updated!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ Could not update. Sheet API may not be configured.")
                    except ImportError:
                        st.error("❌ Google Sheets manager not available")
                    except Exception as e:
                        st.error(f"❌ {e}")
                
                if ignore_btn:
                    st.info(f"Ignored {rec['ticker']} recommendation")
        
        st.divider()

    # =========================================================================
    # TAB STATE MANAGEMENT - FIXES PAGE RELOAD ISSUE
    # =========================================================================
    
    # Define tab names
    TAB_NAMES = [
        "📊 Dashboard",
        "📈 Charts", 
        "🔔 Alerts",
        "📉 MTF Analysis",
        "🛡️ Portfolio Risk",
        "📈 Performance",
        "📋 Details",
        "🤖 AI Insights"
    ]
    
    # Initialize tab state if not exists
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0
    
    # Create tabs
    tabs = st.tabs(TAB_NAMES)
    
    # Unpack tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = tabs
    # =========================================================================
    # TAB 1: DASHBOARD
    # =========================================================================
    with tab1:
        # Sort by status priority
        status_order = {'CRITICAL': 0, 'WARNING': 1, 'OPPORTUNITY': 2, 'SUCCESS': 3, 'GOOD': 4, 'OK': 5}
        sorted_results = sorted(results, key=lambda x: status_order.get(x['overall_status'], 5))
        
        for r in sorted_results:
            ai_enhanced = None
            try:
                ai_enhanced = get_ai_enhanced_recommendation(r, market_health)
            except Exception as e:
                pass  # AI enhancement failed, use original
            
            # Use AI-enhanced status if available
            if ai_enhanced and ai_enhanced.get('ai_enhanced'):
                display_status = ai_enhanced.get('final_status', r['overall_status'])
                display_action = ai_enhanced.get('final_action', r['overall_action'])
            else:
                display_status = r['overall_status']
                display_action = r['overall_action']
            # ===== END AI ENHANCEMENT =====
            status_icons = {
                'CRITICAL': '🔴', 'WARNING': '🟡', 'OPPORTUNITY': '🔵',
                'SUCCESS': '🟢', 'GOOD': '🟢', 'OK': '⚪'
            }
            status_icon = status_icons.get(r['overall_status'], '⚪')
            pnl_emoji = "📈" if r['pnl_percent'] >= 0 else "📉"
            
            # Use AI-enhanced status for icon
            status_icons_display = {
                'CRITICAL': '🔴', 'WARNING': '🟡', 'OPPORTUNITY': '🔵',
                'SUCCESS': '🟢', 'GOOD': '🟢', 'OK': '⚪', 'CAUTION': '🟠'
            }
            status_icon = status_icons_display.get(display_status, '⚪')
            
            # AI indicator
            ai_indicator = "🤖" if ai_enhanced and ai_enhanced.get('ai_enhanced') else ""
            
            with st.expander(
                f"{status_icon} **{r['ticker']}** {ai_indicator} | "
                f"{'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'} | "
                f"{pnl_emoji} P&L: **{r['pnl_percent']:+.2f}%** (₹{r['pnl_amount']:+,.0f}) | "
                f"SL Risk: **{r['sl_risk']}%** | "
                f"Action: **{display_action.replace('_', ' ')}**",
                expanded=(r['overall_status'] in ['CRITICAL', 'WARNING', 'OPPORTUNITY', 'SUCCESS'])
            ):
                # ✅ GAP 2: CHECK FOR EMERGENCY EXIT
                is_emergency, emergency_reasons, urgency_level = detect_emergency_exit(r, market_health)
                
                if is_emergency:
                    if urgency_level == "CRITICAL":
                        st.markdown("""
                        <div style='background:#dc3545; color:white; padding:15px; border-radius:10px; 
                                    text-align:center; font-size:1.2em; font-weight:bold; margin-bottom:15px;
                                    animation: blink 1s infinite;'>
                            🚨 EMERGENCY EXIT REQUIRED 🚨
                        </div>
                        <style>
                        @keyframes blink {
                            0%, 50%, 100% { opacity: 1; }
                            25%, 75% { opacity: 0.5; }
                        }
                        </style>
                        """, unsafe_allow_html=True)
                    else:
                        st.error("⚠️ HIGH URGENCY - Consider immediate exit")
                    
                    st.markdown("**Emergency Conditions:**")
                    for reason in emergency_reasons:
                        st.error(f"• {reason}")
                    
                    st.divider()
                # ===== AI-ENHANCED SIGNALS =====
                if ai_enhanced and ai_enhanced.get('ai_enhanced') and ai_enhanced.get('ai_factors'):
                    st.divider()
                    
                    # AI Score bar
                    ai_score = ai_enhanced.get('ai_score', 0)
                    
                    if ai_score <= -30:
                        score_color = "#dc3545"
                        score_text = "EXIT SIGNAL"
                    elif ai_score <= -10:
                        score_color = "#ffc107"
                        score_text = "CAUTION"
                    elif ai_score >= 20:
                        score_color = "#28a745"
                        score_text = "HOLD SIGNAL"
                    else:
                        score_color = "#6c757d"
                        score_text = "NEUTRAL"
                    
                    st.markdown(f"""
                    <div style='background:linear-gradient(90deg, {score_color}40, transparent); 
                                padding:15px; border-radius:10px; border-left:4px solid {score_color};
                                margin-bottom:15px;'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div>
                                <strong>🤖 AI Analysis: {score_text}</strong><br>
                                <small>{ai_enhanced.get('ai_message', '')}</small>
                            </div>
                            <div style='text-align:center;'>
                                <span style='font-size:1.5em; font-weight:bold; color:{score_color};'>
                                    {ai_score:+d}
                                </span><br>
                                <small>AI Score</small>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # AI Factors
                    st.markdown("##### 🧠 AI Decision Factors:")
                    for factor in ai_enhanced.get('ai_factors', []):
                        impact = factor.get('impact', 0)
                        if impact < 0:
                            factor_color = "#dc3545"
                            impact_text = f"📉 {impact}"
                        elif impact > 0:
                            factor_color = "#28a745"
                            impact_text = f"📈 +{impact}"
                        else:
                            factor_color = "#6c757d"
                            impact_text = "ℹ️ Info"
                        
                        st.markdown(f"""
                        <div style='background:{factor_color}15; padding:8px 12px; 
                                    border-radius:6px; margin:5px 0; border-left:3px solid {factor_color};'>
                            <strong>{factor.get('factor', '')}</strong>: {factor.get('action', '')}
                            <span style='float:right; color:{factor_color};'>{impact_text}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.divider()
                # ===== END AI-ENHANCED SIGNALS =====
                # ✅ GAP 3: STOCK WIN RATE WARNING
                stock_history = get_stock_performance_history(r['ticker'])
                
                if stock_history['has_history']:
                    if stock_history['win_rate'] < 45 or stock_history['expectancy'] < 0:
                        st.markdown(f"""
                        <div style='background:{stock_history['color']}20; padding:12px; border-radius:8px; 
                                    border-left:4px solid {stock_history['color']}; margin-bottom:15px;'>
                            <strong>{stock_history['icon']} Historical Performance: {stock_history['quality']}</strong><br>
                            Win Rate: {stock_history['win_rate']:.1f}% ({stock_history['wins']}/{stock_history['trade_count']}) | 
                            Expectancy: ₹{stock_history['expectancy']:+,.0f}<br>
                            <strong>{stock_history['recommendation']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        with st.expander(f"{stock_history['icon']} Historical: {stock_history['quality']} ({stock_history['win_rate']:.0f}% win rate)", expanded=False):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Win Rate", f"{stock_history['win_rate']:.1f}%")
                            with col2:
                                st.metric("Trades", f"{stock_history['wins']}/{stock_history['trade_count']}")
                            with col3:
                                st.metric("Expectancy", f"₹{stock_history['expectancy']:+,.0f}")
                
                st.divider()
                # Row 1: Basic Info
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("##### 💰 Position")
                    st.write(f"**Entry:** ₹{r['entry_price']:,.2f}")
                    st.write(f"**Current:** ₹{r['current_price']:,.2f}")
                    st.write(f"**Qty:** {r['quantity']}")
                    pnl_color = "green" if r['pnl_percent'] >= 0 else "red"
                    st.markdown(f"**P&L:** <span style='color:{pnl_color};font-weight:bold;'>"
                               f"₹{r['pnl_amount']:+,.2f} ({r['pnl_percent']:+.2f}%)</span>",
                               unsafe_allow_html=True)
                    if r['holding_days'] > 0:
                        st.caption(f"Holding: {r['holding_days']} days | {r['tax_color']} {r['tax_implication']}")
                
                with col2:
                    st.markdown("##### 🎯 Levels")
                    sl_status = '🔴 HIT!' if r['sl_hit'] else ''
                    t1_status = '✅' if r['target1_hit'] else ''
                    t2_status = '✅' if r['target2_hit'] else ''
                    
                    st.write(f"**Stop Loss:** ₹{r['stop_loss']:,.2f} {sl_status}")
                    st.write(f"**Target 1:** ₹{r['target1']:,.2f} {t1_status}")
                    st.write(f"**Target 2:** ₹{r['target2']:,.2f} {t2_status}")
                    
                    if r['should_trail']:
                        st.success(f"**Trail SL:** ₹{r['trail_stop']:,.2f}")
                        st.caption(r.get('trail_reason', ''))
                    
                    if r['at_breakeven']:
                        st.info("🔔 At Breakeven")
                
                with col3:
                    st.markdown("##### 📊 Indicators")
                    rsi_color = "green" if 40 <= r['rsi'] <= 60 else "orange" if 30 <= r['rsi'] <= 70 else "red"
                    st.markdown(f"**RSI:** <span style='color:{rsi_color};'>{r['rsi']:.1f}</span>", 
                               unsafe_allow_html=True)
                    macd_color = "green" if r['macd_signal'] == "BULLISH" else "red"
                    st.markdown(f"**MACD:** <span style='color:{macd_color};'>{r['macd_signal']}</span>", 
                               unsafe_allow_html=True)
                    st.write(f"**Volume:** {r['volume_signal'].replace('_', ' ')}")
                    st.write(f"**Trend:** {r['momentum_trend']}")
                    st.write(f"**R:R Ratio:** 1:{r['risk_reward_ratio']:.2f}")
                
                with col4:
                    st.markdown("##### 🛡️ Support/Resistance")
                    st.write(f"**Support:** ₹{r['support']:,.2f} ({r['support_strength']})")
                    st.write(f"**Resistance:** ₹{r['resistance']:,.2f} ({r['resistance_strength']})")
                    st.write(f"**ATR:** ₹{r['atr']:,.2f}")
                    st.write(f"**Dist to S:** {r['distance_to_support']:.1f}%")
                    st.write(f"**Dist to R:** {r['distance_to_resistance']:.1f}%")
                
                st.divider()

                                # Check entry trigger status
                
                # Row 2: Smart Scores
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("##### ⚠️ SL Risk Score")
                    risk_color = "#dc3545" if r['sl_risk'] >= 70 else "#ffc107" if r['sl_risk'] >= 50 else "#28a745"
                    st.markdown(f"<h2 style='color:{risk_color};text-align:center;'>{r['sl_risk']}%</h2>",
                               unsafe_allow_html=True)
                    st.progress(r['sl_risk'] / 100)
                    if r['sl_reasons']:
                        for reason in r['sl_reasons'][:3]:
                            st.caption(reason)
                
                with col2:
                    st.markdown("##### 📈 Momentum Score")
                    mom_color = "#28a745" if r['momentum_score'] >= 60 else "#ffc107" if r['momentum_score'] >= 40 else "#dc3545"
                    st.markdown(f"<h2 style='color:{mom_color};text-align:center;'>{r['momentum_score']:.0f}/100</h2>",
                               unsafe_allow_html=True)
                    st.progress(r['momentum_score'] / 100)
                    st.caption(r['momentum_trend'])
                
                with col3:
                    st.markdown("##### 🚀 Upside Score")
                    if r['target1_hit']:
                        up_color = "#28a745" if r['upside_score'] >= 60 else "#ffc107" if r['upside_score'] >= 40 else "#dc3545"
                        st.markdown(f"<h2 style='color:{up_color};text-align:center;'>{r['upside_score']}%</h2>",
                                   unsafe_allow_html=True)
                        st.progress(r['upside_score'] / 100)
                        if r['upside_score'] >= 60:
                            st.success(f"New Target: ₹{r['new_target']:,.2f}")
                    else:
                        st.markdown("<h2 style='color:#6c757d;text-align:center;'>N/A</h2>",
                                   unsafe_allow_html=True)
                        st.caption("Target not yet hit")
                
                with col4:
                    st.markdown("##### 📊 MTF Alignment")
                    if r['mtf_signals']:
                        mtf_color = "#28a745" if r['mtf_alignment'] >= 60 else "#ffc107" if r['mtf_alignment'] >= 40 else "#dc3545"
                        st.markdown(f"<h2 style='color:{mtf_color};text-align:center;'>{r['mtf_alignment']}%</h2>",
                                   unsafe_allow_html=True)
                        st.progress(r['mtf_alignment'] / 100)
                        for tf, signal in r['mtf_signals'].items():
                            sig_emoji = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                            st.caption(f"{tf}: {sig_emoji} {signal}")
                    else:
                        st.markdown("<h2 style='color:#6c757d;text-align:center;'>N/A</h2>",
                                   unsafe_allow_html=True)
                        st.caption("MTF data unavailable")
                                    # ✅ GAP 4: CHART PATTERN DETECTION
                if 'df' in r:
                    detected_patterns = detect_chart_patterns(r['df'], r['current_price'])
                    
                    if detected_patterns:
                        st.divider()
                        st.markdown("##### 📐 Detected Patterns")
                        
                        for pattern in detected_patterns:
                            signal_color = "#28a745" if pattern['signal'] == 'BULLISH' else "#dc3545"
                            
                            st.markdown(f"""
                            <div style='background:{signal_color}20; padding:10px; border-radius:8px; 
                                        border-left:3px solid {signal_color}; margin:5px 0;'>
                                <strong>{pattern['icon']} {pattern['name']}</strong> ({pattern['signal']} - {pattern['strength']})<br>
                                <small>{pattern['description']}</small><br>
                                <em>→ {pattern['action']}</em>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Row 3: Partial Exits
                if r['partial_exits']['triggered_count'] > 0:
                    st.divider()
                    st.markdown("##### 📊 Partial Exit Levels")
                    
                    pe_cols = st.columns(4)
                    for idx, pe in enumerate(r['partial_exits']['recommendations'][:4]):
                        with pe_cols[idx]:
                            status_color = "#28a745" if pe['status'] == 'TRIGGERED' else "#6c757d"
                            st.markdown(f"""
                            <div style='padding:10px;background:{status_color}20;border-radius:8px;text-align:center;border-left:3px solid {status_color};'>
                                <strong>₹{pe['level']:,.2f}</strong><br>
                                <small>{pe['reason']}</small><br>
                                <span style='color:{status_color};'>{pe['status']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                 # Row 3.5: Options Hedge Suggestion (for risky positions)
                if r['sl_risk'] >= 60 or r['overall_status'] == 'CRITICAL':
                    st.divider()
                    st.markdown("##### 🛡️ Hedge Suggestion")
                    
                    hedge = suggest_options_hedge(
                        ticker=r['ticker'],
                        position_type=r['position_type'],
                        current_price=r['current_price'],
                        position_value=r['current_price'] * r['quantity'],
                        market_health=market_health
                    )
                    
                    urgency_colors = {'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#28a745'}
                    
                    st.markdown(f"""
                    <div style='background:{urgency_colors.get(hedge['urgency'], '#6c757d')}20; 
                                padding:10px; border-radius:8px; border-left:3px solid {urgency_colors.get(hedge['urgency'], '#6c757d')}'>
                        <strong>{hedge['hedge_type']}</strong> (Urgency: {hedge['urgency']})<br>
                        {hedge['recommendation']}<br>
                        <small>Budget: ~₹{hedge['estimated_premium_budget']:,.0f}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if hedge.get('suggestions'):
                        for sug in hedge['suggestions']:
                            st.caption(sug)
                    
                    st.caption(hedge['note'])
                # Row 4: Alerts
                if r['alerts']:
                    st.divider()
                    st.markdown("##### ⚠️ Alerts & Recommendations")
                    for alert in r['alerts']:
                        if alert['priority'] == 'CRITICAL':
                            st.error(f"**{alert['type']}**: {alert['message']}\n\n**⚡ Action: {alert['action']}**")
                        elif alert['priority'] == 'HIGH':
                            st.warning(f"**{alert['type']}**: {alert['message']}\n\n**⚡ Action: {alert['action']}**")
                        elif alert['priority'] == 'MEDIUM':
                            st.info(f"**{alert['type']}**: {alert['message']}\n\n**Action: {alert['action']}**")
                        else:
                            st.caption(f"ℹ️ {alert['type']}: {alert['message']}")
                
                # Recommendation Box
                rec_colors = {
                    'EXIT': 'critical-box', 'EXIT_EARLY': 'critical-box',
                    'WATCH': 'warning-box', 'BOOK_PROFITS': 'success-box',
                    'HOLD_EXTEND': 'info-box', 'TRAIL_SL': 'success-box',
                    'HOLD': 'info-box', 'MOVE_SL_BREAKEVEN': 'info-box'
                }
                rec_class = rec_colors.get(r['overall_action'], 'info-box')
                
                st.markdown(f"""
                <div class="{rec_class}">
                    📌 RECOMMENDATION: {r['overall_action'].replace('_', ' ')}
                </div>
                """, unsafe_allow_html=True)
    
    # =========================================================================
    # TAB 2: CHARTS - OPTIMIZED FOR MINIMAL DATA
    # =========================================================================
    with tab2:
        selected_stock = st.selectbox("Select Stock for Chart", [r['ticker'] for r in results])
        selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
        
        if selected_result:
            # Reconstruct DataFrame from minimal chart data
            if 'chart_data' in selected_result:
                df = reconstruct_dataframe(selected_result['chart_data'])
            elif 'df' in selected_result:
                df = selected_result['df']
            else:
                # Fetch fresh if no cached data
                df = fetch_stock_data_optimized(selected_stock)
            
            if df is not None and not df.empty:
                # Candlestick Chart
                fig = go.Figure()
                
                # Handle both Date column and index
                x_axis = df['Date'] if 'Date' in df.columns else df.index
                
                fig.add_trace(go.Candlestick(
                    x=x_axis, 
                    open=df['Open'], 
                    high=df['High'],
                    low=df['Low'], 
                    close=df['Close'], 
                    name='Price'
                ))
                
                # Add moving averages
                if len(df) >= 20:
                    df['SMA20'] = pd.Series(df['Close']).rolling(20).mean()
                    fig.add_trace(go.Scatter(
                        x=x_axis, y=df['SMA20'], 
                        mode='lines', name='SMA 20', 
                        line=dict(color='orange', width=1)
                    ))
                
                if len(df) >= 9:
                    df['EMA9'] = pd.Series(df['Close']).ewm(span=9).mean()
                    fig.add_trace(go.Scatter(
                        x=x_axis, y=df['EMA9'], 
                        mode='lines', name='EMA 9', 
                        line=dict(color='purple', width=1)
                    ))
                
                # Add levels
                fig.add_hline(y=selected_result['entry_price'], line_dash="dash",
                             line_color="blue", annotation_text="Entry")
                fig.add_hline(y=selected_result['stop_loss'], line_dash="dash",
                             line_color="red", annotation_text="Stop Loss")
                fig.add_hline(y=selected_result['target1'], line_dash="dash",
                             line_color="green", annotation_text="Target 1")
                fig.add_hline(y=selected_result['target2'], line_dash="dot",
                             line_color="darkgreen", annotation_text="Target 2")
                
                if selected_result['should_trail']:
                    fig.add_hline(y=selected_result['trail_stop'], line_dash="dash",
                                 line_color="cyan", annotation_text="Trail SL", line_width=2)
                
                fig.update_layout(
                    title=f"{selected_stock} - Price Chart with Levels",
                    height=500,
                    xaxis_rangeslider_visible=False,
                    xaxis_title="Date",
                    yaxis_title="Price (₹)"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # RSI Chart
                col1, col2 = st.columns(2)
                
                with col1:
                    if len(df) >= 14:
                        rsi_series = calculate_rsi(pd.Series(df['Close']))
                        fig_rsi = go.Figure()
                        fig_rsi.add_trace(go.Scatter(
                            x=x_axis, y=rsi_series, 
                            mode='lines', name='RSI', 
                            line=dict(color='purple')
                        ))
                        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                        fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
                        fig_rsi.update_layout(title="RSI (14)", height=250, yaxis_range=[0, 100])
                        st.plotly_chart(fig_rsi, use_container_width=True)
                
                with col2:
                    if len(df) >= 26:
                        macd, signal, histogram = calculate_macd(pd.Series(df['Close']))
                        colors = ['green' if h >= 0 else 'red' for h in histogram]
                        fig_macd = go.Figure()
                        fig_macd.add_trace(go.Bar(
                            x=x_axis, y=histogram, 
                            name='Histogram', marker_color=colors
                        ))
                        fig_macd.add_trace(go.Scatter(
                            x=x_axis, y=macd, 
                            mode='lines', name='MACD', 
                            line=dict(color='blue', width=1)
                        ))
                        fig_macd.add_trace(go.Scatter(
                            x=x_axis, y=signal, 
                            mode='lines', name='Signal', 
                            line=dict(color='orange', width=1)
                        ))
                        fig_macd.update_layout(title="MACD", height=250)
                        st.plotly_chart(fig_macd, use_container_width=True)
            else:
                st.warning(f"No chart data available for {selected_stock}")
    
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
                # Correlation-based Position Sizing
        if settings['enable_correlation'] and st.session_state.correlation_matrix is not None:
            st.divider()
            st.markdown("### 📐 Correlation-Based Position Sizing")
            
            with st.expander("Check new position sizing", expanded=False):
                new_ticker = st.text_input(
                    "Ticker to add",
                    placeholder="INFY",
                    key="corr_sizing_ticker"
                )
                
                if new_ticker and st.button("Check Correlation Impact", key="check_corr_impact"):
                    sizing_result = get_correlation_based_sizing(
                        results, 
                        st.session_state.correlation_matrix,
                        new_ticker.upper()
                    )
                    
                    if sizing_result['adjustment_factor'] < 1.0:
                        st.warning(f"⚠️ {sizing_result['reason']}")
                        st.info(sizing_result['recommendation'])
                        
                        if sizing_result.get('correlated_positions'):
                            st.markdown("**Correlated with:**")
                            for cp in sizing_result['correlated_positions']:
                                st.caption(f"- {cp['ticker']}: {cp['correlation']:.2f} correlation")
                    else:
                        st.success("✅ No high correlation with existing positions")
    
    # =========================================================================
    # TAB 6: PERFORMANCE
    # =========================================================================
    with tab6:
        display_performance_dashboard()
        # =========================================================================
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
    # TAB 8: AI INSIGHTS - WITH PROPER STATE MANAGEMENT
    # =========================================================================
    with tab8:
        st.subheader("🤖 AI-Powered Insights")
        
        # Initialize all AI-related session states
        if 'ai_states' not in st.session_state:
            st.session_state.ai_states = {
                'sentiment_result': None,
                'sentiment_ticker': None,
                'lstm_result': None,
                'lstm_ticker': None,
                'backtest_result': None,
                'backtest_ticker': None,
                'regime_result': None,
            }
        
        try:
            from ai_features import (
                get_available_features,
                predict_price_lstm,
                detect_market_regime,
                get_real_sentiment,
                get_rl_optimized_sl,
                monte_carlo_portfolio_optimization,
                run_simple_backtest,
                rl_optimizer,
                sentiment_analyzer,  # âœ… ADDED THIS LINE
                AVAILABLE_FEATURES
            )
            ai_loaded = True
        except ImportError as e:
            ai_loaded = False
            st.warning(f"⚠️ AI module not available: {e}")
            st.code("pip install scikit-learn scipy hmmlearn", language="bash")
        
        if ai_loaded:
            features = get_available_features()
            
            # Feature availability
            with st.expander("📋 Available AI Features", expanded=False):
                cols = st.columns(3)
                for i, (name, info) in enumerate(features.items()):
                    with cols[i % 3]:
                        status = "✅" if info['available'] else "❌"
                        st.markdown(f"{status} **{name.replace('_', ' ').title()}**")
                        if not info['available'] and info.get('install'):
                            st.caption(f"Install: `{info['install']}`")
            
            st.divider()
            
            # =================================================================
            # MARKET REGIME DETECTION
            # =================================================================
            st.markdown("### 📊 Market Regime Detection")
            
            with st.form(key="regime_form", clear_on_submit=False):
                col1, col2 = st.columns([3, 1])
                with col2:
                 run_regime = st.form_submit_button("🔄 Detect Regime",  use_container_width=True)
            
            if run_regime or st.session_state.ai_states.get('regime_result'):
                if run_regime:
                    # Run fresh analysis
                    if features['regime_detection']['available']:
                        try:
                            import yfinance as yf
                            with st.spinner("Detecting market regime..."):
                                nifty = yf.Ticker("^NSEI")
                                nifty_df = nifty.history(period="1y")
                                
                                if not nifty_df.empty:
                                    regime_result = detect_market_regime(nifty_df)
                                    st.session_state.ai_states['regime_result'] = regime_result
                        except Exception as e:
                            st.error(f"Regime detection failed: {e}")
                    else:
                        st.info("Install `hmmlearn` for regime detection: `pip install hmmlearn`")
                
                # Display result
                regime_result = st.session_state.ai_states.get('regime_result')
                if regime_result and regime_result.get('status') == 'success':
                    rec = regime_result.get('recommendation', {})
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"""
                        <div style='background:{rec.get('color', '#6c757d')}20; 
                                    padding:20px; border-radius:10px;
                                    border-left:5px solid {rec.get('color', '#6c757d')}'>
                            <h3 style='margin:0;'>{regime_result['regime']}</h3>
                            <p style='margin:10px 0;'><strong>{rec.get('action', 'N/A')}</strong></p>
                            <small>{rec.get('strategy', 'N/A')}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.metric("Confidence", f"{regime_result.get('confidence', 0)}%")
                    
                    with col3:
                        st.metric("Duration", f"{regime_result.get('duration_days', 0)} days")
            
            st.divider()
            
            # =================================================================
            # RL STOP LOSS OPTIMIZER
            # =================================================================
            st.markdown("### 🎯 RL-Optimized Stop Loss")
            
            rl_stats = rl_optimizer.get_stats()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("States Learned", rl_stats['states_learned'])
            with col2:
                st.metric("Trades Processed", rl_stats['trades_processed'])
            with col3:
                st.metric("Avg Multiplier", f"{rl_stats['avg_multiplier']:.2f}x ATR")
            with col4:
                st.metric("Learning Rate", f"{rl_stats['learning_rate']}")
            
            if results:
                with st.expander("🎯 RL Suggestions for Current Positions", expanded=False):
                    rl_suggestions = []
                    for r in results[:5]:
                        if 'chart_data' in r:
                            try:
                                df = pd.DataFrame(r['chart_data'])
                                if not df.empty and len(df) >= 20:
                                    rl_result = get_rl_optimized_sl(
                                        df, r['entry_price'], r['current_price'], r['position_type']
                                    )
                                    rl_suggestions.append({
                                        'Ticker': r['ticker'],
                                        'Current SL': f"₹{r['stop_loss']:,.2f}",
                                        'RL Optimal SL': f"₹{rl_result['optimal_sl']:,.2f}",
                                        'Multiplier': f"{rl_result['multiplier']:.2f}x ATR",
                                    })
                            except:
                                pass
                    
                    if rl_suggestions:
                        st.dataframe(pd.DataFrame(rl_suggestions), use_container_width=True, hide_index=True)
            
            st.divider()
            
            # =================================================================
            # LSTM PREDICTION - WITH STATE MANAGEMENT
            # =================================================================
            st.markdown("### 🔮 Price Predictions (LSTM)")
            
            if features['lstm_prediction']['available']:
                with st.form(key="lstm_form", clear_on_submit=False):
                    lstm_col1, lstm_col2 = st.columns([3, 1])
                
                with lstm_col1:
                    lstm_ticker = st.selectbox(
                        "Select Stock for Prediction", 
                        [r['ticker'] for r in results] if results else ["RELIANCE"],
                        key="lstm_ticker_select"
                    )
                
                with lstm_col2:
                    run_lstm = st.form_submit_button("🔮 Predict",  use_container_width=True)
                
                # Run prediction
                if run_lstm:
                    selected = next((r for r in results if r['ticker'] == lstm_ticker), None)
                    if selected and 'chart_data' in selected:
                        df = pd.DataFrame(selected['chart_data'])
                        if len(df) >= 100:
                            with st.spinner("Training LSTM model (30-60 seconds)..."):
                                pred_result = predict_price_lstm(df, periods=5)
                                st.session_state.ai_states['lstm_result'] = pred_result
                                st.session_state.ai_states['lstm_ticker'] = lstm_ticker
                        else:
                            st.warning("Need at least 100 data points for LSTM")
                    else:
                        st.warning("No data available for prediction")
                
                # Display cached result
                if (st.session_state.ai_states.get('lstm_result') and 
                    st.session_state.ai_states.get('lstm_ticker') == lstm_ticker):
                    
                    pred_result = st.session_state.ai_states['lstm_result']
                    
                    if pred_result.get('status') == 'success':
                        st.success(f"✅ Prediction generated with {pred_result['confidence']}% confidence")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Current Price", f"₹{pred_result['current_price']:,.2f}")
                        with col2:
                            st.metric(
                                "5-Day Prediction", 
                                f"₹{pred_result['predicted_price']:,.2f}",
                                f"{pred_result['change_pct']:+.2f}%"
                            )
                        with col3:
                            trend_color = "green" if pred_result['trend'] == "BULLISH" else "red"
                            st.markdown(
                                f"**Trend:** <span style='color:{trend_color}'>{pred_result['trend']}</span>", 
                                unsafe_allow_html=True
                            )
                        
                        # Day-by-day predictions
                        st.caption("**Day-by-Day Predictions:**")
                        pred_df = pd.DataFrame({
                            'Day': [f'Day {i+1}' for i in range(5)],
                            'Predicted Price': [f"₹{p:,.2f}" for p in pred_result['predictions']]
                        })
                        st.dataframe(pred_df, use_container_width=True, hide_index=True)
                    else:
                        st.error(f"❌ {pred_result.get('message', 'Prediction failed')}")
            else:
                st.info("Install `tensorflow` for LSTM predictions: `pip install tensorflow`")
            
            st.divider()
            
            # =================================================================
            # SENTIMENT ANALYSIS - WITH STATE MANAGEMENT
            # =================================================================
            st.markdown("### 📰 News Sentiment Analysis")
            
            if features['sentiment_analysis']['available']:
                with st.form(key="sentiment_form", clear_on_submit=False):
                     sent_col1, sent_col2 = st.columns([3, 1])
                
                with sent_col1:
                    sent_ticker = st.selectbox(
                        "Select Stock for Sentiment", 
                        [r['ticker'] for r in results] if results else ["RELIANCE"],
                        key="sentiment_ticker_select"
                    )
                
                with sent_col2:
                    run_sentiment = st.form_submit_button("📰 Analyze", use_container_width=True)
                
                # Run sentiment analysis
                if run_sentiment:
                    with st.spinner("Analyzing news sentiment (loading FinBERT model)..."):
                        sent_result = get_real_sentiment(sent_ticker)
                        st.session_state.ai_states['sentiment_result'] = sent_result
                        st.session_state.ai_states['sentiment_ticker'] = sent_ticker
                
                # Display cached result
                if (st.session_state.ai_states.get('sentiment_result') and 
                    st.session_state.ai_states.get('sentiment_ticker') == sent_ticker):
                    
                    sent_result = st.session_state.ai_states['sentiment_result']
                    
                    if sent_result.get('status') == 'success':
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Sentiment Score", f"{sent_result['score']:+.1f}")
                        with col2:
                            st.markdown(
                                f"**Type:** <span style='color:{sent_result['color']}'>{sent_result['type']}</span>",
                                unsafe_allow_html=True
                            )
                        with col3:
                            st.metric("Confidence", f"{sent_result['confidence']}%")
                        
                        st.caption(f"Analyzed {sent_result['articles_analyzed']} articles")
                        
                        # Show top headlines
                        if sent_result.get('headlines'):
                            st.markdown("**Recent Headlines:**")
                            for h in sent_result['headlines'][:3]:
                                score_color = "green" if h['score'] > 0 else "red" if h['score'] < 0 else "gray"
                                st.markdown(
                                    f"- [{h['source']}] {h['headline']} "
                                    f"<small style='color:{score_color}'>({h['score']:+.0f})</small>",
                                    unsafe_allow_html=True
                                )
                    elif sent_result.get('status') == 'warning':
                        st.warning(sent_result.get('message', 'No news found'))
                    else:
                        st.error(f"❌ {sent_result.get('message', 'Sentiment analysis failed')}")
            else:
                st.info("Install `transformers` and `torch` for sentiment analysis")
                st.code("pip install transformers torch", language="bash")
            
            st.divider()
            
            # =================================================================
            # BACKTESTING - WITH STATE MANAGEMENT
            # =================================================================
            st.markdown("### 🔬 Strategy Backtester")
            
            with st.form(key="backtest_form", clear_on_submit=False):
                bt_col1, bt_col2, bt_col3, bt_col4, bt_col5 = st.columns([2, 1, 1, 1, 1])
            
            with bt_col1:
                bt_ticker = st.text_input("Ticker", value="RELIANCE", key="bt_ticker_input")
            with bt_col2:
                bt_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="bt_period_select")
            with bt_col3:
                bt_sl = st.number_input("SL %", value=3.0, step=0.5, key="bt_sl_input")
            with bt_col4:
                bt_target = st.number_input("Target %", value=6.0, step=0.5, key="bt_target_input")
            with bt_col5:
                run_backtest = st.form_submit_button("🔬 Run",  use_container_width=True)
            
            # Run backtest
            if run_backtest:
                with st.spinner("Running comprehensive backtest..."):
                    bt_result = run_simple_backtest(bt_ticker, bt_period, bt_sl, bt_target)
                    st.session_state.ai_states['backtest_result'] = bt_result
                    st.session_state.ai_states['backtest_ticker'] = bt_ticker
            
            # Display cached result
            if st.session_state.ai_states.get('backtest_result'):
                bt_result = st.session_state.ai_states['backtest_result']
                
                if bt_result.get('status') == 'success':
                    summary = bt_result['summary']
                    risk = bt_result['risk_metrics']
                    
                    # Summary metrics
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Trades", summary['total_trades'])
                    with col2:
                        st.metric("Win Rate", f"{summary['win_rate']:.1f}%")
                    with col3:
                        pf = summary['profit_factor']
                        st.metric("Profit Factor", f"{pf}" if isinstance(pf, str) else f"{pf:.2f}")
                    with col4:
                        st.metric("Net P&L", f"₹{summary['net_pnl']:+,.0f}")
                    with col5:
                        st.metric("Max Drawdown", f"{risk['max_drawdown']:.1f}%")
                    
                    # Detailed metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Wins/Losses", f"{summary['wins']}/{summary['losses']}")
                    with col2:
                        st.metric("Avg Win", f"₹{risk['avg_win']:,.0f}")
                    with col3:
                        st.metric("Avg Loss", f"₹{risk['avg_loss']:,.0f}")
                    with col4:
                        st.metric("Avg Holding", f"{risk['avg_holding_days']:.1f} days")
                    
                    # Equity curve
                    if 'equity_curve' in bt_result and len(bt_result['equity_curve']) > 1:
                        try:
                            fig_equity = go.Figure()
                            fig_equity.add_trace(go.Scatter(
                                y=bt_result['equity_curve'],
                                mode='lines',
                                name='Equity',
                                line=dict(color='#667eea', width=2)
                            ))
                            fig_equity.add_hline(
                                y=100000, 
                                line_dash="dash", 
                                line_color="gray", 
                                annotation_text="Initial Capital"
                            )
                            fig_equity.update_layout(
                                title="Equity Curve", 
                                height=300, 
                                xaxis_title="Trades", 
                                yaxis_title="Capital (₹)"
                            )
                            st.plotly_chart(fig_equity, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not render equity curve: {e}")
                    
                    # Exit analysis
                    if 'exit_analysis' in bt_result:
                        with st.expander("📊 Exit Reason Analysis"):
                            exit_data = []
                            for reason, data in bt_result['exit_analysis'].items():
                                exit_data.append({
                                    'Reason': reason,
                                    'Count': data['count'],
                                    'Total P&L': f"₹{data['pnl']:+,.0f}"
                                })
                            st.dataframe(pd.DataFrame(exit_data), use_container_width=True, hide_index=True)
                else:
                    st.error(f"❌ {bt_result.get('message', 'Backtest failed')}")
            
            # Clear results button
            st.divider()
            if st.button("🗑️ Clear All AI Results", key="clear_ai_results"):
                st.session_state.ai_states = {
                    'sentiment_result': None,
                    'sentiment_ticker': None,
                    'lstm_result': None,
                    'lstm_ticker': None,
                    'backtest_result': None,
                    'backtest_ticker': None,
                    'regime_result': None,
                }
                st.success("✅ AI results cleared!")
                st.rerun()    
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
    st.markdown("---")
    st.markdown(
        f"<p style='text-align:center;color:#666;font-size:0.8em;'>"
        f"Smart Portfolio Monitor v6.0 | Last updated: {ist_now.strftime('%H:%M:%S')} IST | "
        f"Positions: {len(results)} | API Calls: {get_api_call_count()}"
        f"</p>",
        unsafe_allow_html=True
    )


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()
