"""
📊 TRADING UTILITIES - Shared Technical Analysis Functions
==========================================================
Centralized technical indicators used across all modules.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI using Wilder's smoothing method
    
    Args:
        prices: Series of closing prices
        period: RSI period (default 14)
    
    Returns:
        Series of RSI values (0-100)
    """
    if prices is None or len(prices) < period:
        return pd.Series([50.0] * len(prices) if prices is not None else [50.0])
    
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Use Wilder's smoothing (EWM with alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    Args:
        prices: Series of closing prices
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
    
    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    if prices is None or len(prices) < slow:
        empty = pd.Series([0.0] * len(prices) if prices is not None else [0.0])
        return empty, empty, empty
    
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    
    return macd, signal_line, histogram


def calculate_atr(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """
    Calculate ATR using Wilder's smoothing
    
    Args:
        high: Series of high prices
        low: Series of low prices
        close: Series of closing prices
        period: ATR period (default 14)
    
    Returns:
        Series of ATR values
    """
    if high is None or low is None or close is None:
        return pd.Series([0.0])
    
    if len(high) < period:
        # Return simple range if not enough data
        return (high - low).fillna(0)
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Use Wilder's smoothing
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    return atr


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    if prices is None or len(prices) < period:
        return prices if prices is not None else pd.Series([0.0])
    return prices.ewm(span=period, adjust=False).mean()


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    if prices is None or len(prices) < period:
        return prices if prices is not None else pd.Series([0.0])
    return prices.rolling(window=period).mean()


def calculate_bollinger_bands(
    prices: pd.Series, 
    period: int = 20, 
    std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands
    
    Returns:
        Tuple of (Upper Band, Middle Band, Lower Band)
    """
    if prices is None or len(prices) < period:
        if prices is not None:
            return prices, prices, prices
        empty = pd.Series([0.0])
        return empty, empty, empty
    
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower


def calculate_stochastic(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    k_period: int = 14, 
    d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator
    
    Returns:
        Tuple of (%K, %D)
    """
    if high is None or low is None or close is None:
        empty = pd.Series([50.0])
        return empty, empty
    
    if len(high) < k_period:
        empty = pd.Series([50.0] * len(high))
        return empty, empty
    
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    # Avoid division by zero
    range_diff = highest_high - lowest_low
    range_diff = range_diff.replace(0, np.finfo(float).eps)
    
    k = 100 * (close - lowest_low) / range_diff
    d = k.rolling(window=d_period).mean()
    
    return k, d


def calculate_adx(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """Calculate Average Directional Index (ADX)"""
    if high is None or low is None or close is None:
        return pd.Series([25.0])
    
    if len(high) < period:
        return pd.Series([25.0] * len(high))
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high - high.shift()
    down_move = low.shift() - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Wilder's smoothing
    alpha = 1/period
    atr = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean() / atr
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    return adx


# ============================================================================
# SAFE UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division that handles zero and NaN"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        if pd.isna(result) or np.isinf(result):
            return default
        return result
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        if value is None:
            return default
        result = float(value)
        if pd.isna(result) or np.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default

def normalize_ticker(ticker: str, add_suffix: bool = True, suffix: str = '.NS') -> str:
    """
    Normalize ticker symbol for consistent matching
    
    Args:
        ticker: Raw ticker symbol
        add_suffix: Whether to add exchange suffix
        suffix: Exchange suffix to add (default .NS for NSE)
    
    Returns:
        Normalized ticker string
    """
    if not ticker:
        return ""
    
    # Clean the ticker
    clean = str(ticker).strip().upper()
    
    # Remove common suffixes for comparison
    for suf in ['.NS', '.BO', '.NSE', '.BSE', '.L', '.N']:
        if clean.endswith(suf):
            clean = clean[:-len(suf)]
    
    # Add suffix if requested
    if add_suffix and suffix:
        return f"{clean}{suffix}"
    
    return clean


def tickers_match(ticker1: str, ticker2: str) -> bool:
    """
    Check if two tickers refer to the same stock
    
    Args:
        ticker1: First ticker
        ticker2: Second ticker
    
    Returns:
        True if they match
    """
    return normalize_ticker(ticker1, add_suffix=False) == normalize_ticker(ticker2, add_suffix=False)


def safe_get_last(series: pd.Series, default=0.0):
    """Safely get last value from a series"""
    if series is None or len(series) == 0:
        return default
    try:
        value = series.iloc[-1]
        if pd.isna(value):
            return default
        return float(value)
    except (IndexError, TypeError):
        return default
