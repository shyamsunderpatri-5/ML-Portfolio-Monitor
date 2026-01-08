"""
🧠 AI TRADING BRAIN - Professional Position Manager
====================================================
This is the CORE AI that monitors and manages your positions.

Features:
- Continuous position monitoring
- Dynamic SL/Target adjustment
- News sentiment tracking
- Market regime awareness
- Multi-signal aggregation
- Automatic level updates

Author: Smart Portfolio Monitor
Version: 1.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
import os

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

TRADING_CONFIG = {
    # Position Management
    'max_position_risk_pct': 2.0,      # Max 2% risk per position
    'trail_start_pct': 2.0,            # Start trailing after 2% profit
    'trail_step_pct': 0.5,             # Trail in 0.5% steps
    
    # Target Extension
    'extend_target_momentum_threshold': 70,  # Momentum > 70 = can extend
    'extend_target_max_pct': 50,             # Max 50% target extension
    'target_extension_atr_multiplier': 2.0,  # Extend by 2x ATR
    
    # Stop Loss
    'min_sl_distance_pct': 1.0,        # Minimum 1% SL distance
    'max_sl_distance_pct': 5.0,        # Maximum 5% SL distance
    'breakeven_trigger_pct': 2.0,      # Move to breakeven at 2%
    
    # Market Regime Adjustments
    'bullish_target_boost': 1.3,       # 30% higher targets in bull
    'bearish_sl_tighten': 0.7,         # 30% tighter SL in bear
    
    # News Impact
    'positive_news_target_boost': 1.15,  # 15% boost on good news
    'negative_news_sl_tighten': 0.8,     # 20% tighter SL on bad news
    
    # Confidence Thresholds
    'min_confidence_to_extend': 60,    # Need 60% confidence to extend
    'min_signals_for_action': 2,       # Need 2+ signals to act
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def calculate_fibonacci_extensions(low: float, high: float, direction: str = 'LONG') -> Dict[str, float]:
    """
    Calculate Fibonacci extension levels for targets
    
    For LONG: Extensions above the high
    For SHORT: Extensions below the low
    """
    diff = high - low
    
    if direction == 'LONG':
        return {
            'fib_1.0': high,
            'fib_1.272': high + (diff * 0.272),
            'fib_1.414': high + (diff * 0.414),
            'fib_1.618': high + (diff * 0.618),
            'fib_2.0': high + (diff * 1.0),
            'fib_2.618': high + (diff * 1.618),
        }
    else:  # SHORT
        return {
            'fib_1.0': low,
            'fib_1.272': low - (diff * 0.272),
            'fib_1.414': low - (diff * 0.414),
            'fib_1.618': low - (diff * 0.618),
            'fib_2.0': low - (diff * 1.0),
            'fib_2.618': low - (diff * 1.618),
        }


def find_support_resistance_zones(df: pd.DataFrame, lookback: int = 60) -> Dict:
    """Find key support and resistance zones"""
    if len(df) < lookback:
        lookback = len(df)
    
    recent = df.tail(lookback)
    current_price = float(df['Close'].iloc[-1])
    
    # Find pivot highs and lows
    highs = []
    lows = []
    
    for i in range(2, len(recent) - 2):
        # Pivot high
        if (recent['High'].iloc[i] > recent['High'].iloc[i-1] and
            recent['High'].iloc[i] > recent['High'].iloc[i-2] and
            recent['High'].iloc[i] > recent['High'].iloc[i+1] and
            recent['High'].iloc[i] > recent['High'].iloc[i+2]):
            highs.append(float(recent['High'].iloc[i]))
        
        # Pivot low
        if (recent['Low'].iloc[i] < recent['Low'].iloc[i-1] and
            recent['Low'].iloc[i] < recent['Low'].iloc[i-2] and
            recent['Low'].iloc[i] < recent['Low'].iloc[i+1] and
            recent['Low'].iloc[i] < recent['Low'].iloc[i+2]):
            lows.append(float(recent['Low'].iloc[i]))
    
    # Find nearest levels
    resistances = sorted([h for h in highs if h > current_price])
    supports = sorted([l for l in lows if l < current_price], reverse=True)
    
    return {
        'supports': supports[:3] if supports else [current_price * 0.95],
        'resistances': resistances[:3] if resistances else [current_price * 1.05],
        'nearest_support': supports[0] if supports else current_price * 0.95,
        'nearest_resistance': resistances[0] if resistances else current_price * 1.05
    }


# ============================================================================
# AI TRADING BRAIN - MAIN CLASS
# ============================================================================

class AITradingBrain:
    """
    🧠 The AI Trading Brain - Makes intelligent trading decisions
    
    This class:
    1. Analyzes each position continuously
    2. Calculates optimal SL/Target levels
    3. Considers market conditions, news, technicals
    4. Recommends adjustments with confidence scores
    5. Tracks decision history for learning
    """
    
    def __init__(self):
        self.decision_history = []
        self.position_states = {}
        self.config = TRADING_CONFIG
        
        # Try to load AI features
        self.ai_features_available = self._check_ai_features()
    
    def _check_ai_features(self) -> Dict[str, bool]:
        """Check which AI features are available"""
        available = {
            'lstm': False,
            'sentiment': False,
            'regime': False,
            'rl_optimizer': False
        }
        
        try:
            from ai_features import predict_price_lstm
            available['lstm'] = True
        except:
            pass
        
        try:
            from ai_features import get_real_sentiment
            available['sentiment'] = True
        except:
            pass
        
        try:
            from ai_features import detect_market_regime
            available['regime'] = True
        except:
            pass
        
        try:
            from ai_features import get_rl_optimized_sl
            available['rl_optimizer'] = True
        except:
            pass
        
        return available
    
    def analyze_position(
        self,
        ticker: str,
        position_type: str,
        entry_price: float,
        current_price: float,
        original_sl: float,
        original_target1: float,
        original_target2: float,
        quantity: int,
        df: pd.DataFrame,
        market_health: Optional[Dict] = None
    ) -> Dict:
        """
        🧠 MAIN ANALYSIS FUNCTION
        
        Analyzes a position and returns:
        - New recommended SL
        - New recommended Target 1
        - New recommended Target 2
        - Confidence score
        - Reasoning
        - Action required
        """
        
        if df is None or df.empty or len(df) < 20:
            return self._create_no_change_result(
                ticker, original_sl, original_target1, original_target2,
                "Insufficient data for analysis"
            )
        
        # =====================================================================
        # STEP 1: GATHER ALL SIGNALS
        # =====================================================================
        signals = self._gather_all_signals(
            ticker, position_type, entry_price, current_price,
            df, market_health
        )
        
        # =====================================================================
        # STEP 2: CALCULATE OPTIMAL LEVELS
        # =====================================================================
        optimal_levels = self._calculate_optimal_levels(
            position_type, entry_price, current_price,
            original_sl, original_target1, original_target2,
            df, signals, market_health
        )
        
        # =====================================================================
        # STEP 3: DETERMINE IF CHANGES ARE NEEDED
        # =====================================================================
        changes = self._determine_changes(
            original_sl, original_target1, original_target2,
            optimal_levels, signals
        )
        
        # =====================================================================
        # STEP 4: GENERATE RECOMMENDATION
        # =====================================================================
        recommendation = self._generate_recommendation(
            ticker, position_type, entry_price, current_price,
            original_sl, original_target1, original_target2,
            optimal_levels, changes, signals
        )
        
        # =====================================================================
        # STEP 5: LOG DECISION
        # =====================================================================
        self._log_decision(ticker, recommendation)
        
        return recommendation
    
    def _gather_all_signals(
        self,
        ticker: str,
        position_type: str,
        entry_price: float,
        current_price: float,
        df: pd.DataFrame,
        market_health: Optional[Dict]
    ) -> Dict:
        """Gather all available signals for decision making"""
        
        signals = {
            'timestamp': datetime.now(),
            'ticker': ticker,
            'position_type': position_type,
            'current_price': current_price,
            'entry_price': entry_price,
            'pnl_pct': ((current_price - entry_price) / entry_price) * 100 if position_type == 'LONG' 
                       else ((entry_price - current_price) / entry_price) * 100,
            
            # Technical signals
            'technical': {},
            
            # Market signals
            'market': {},
            
            # AI signals
            'ai': {},
            
            # Sentiment signals
            'sentiment': {},
            
            # Aggregated
            'bullish_score': 0,
            'bearish_score': 0,
            'confidence': 0,
            'trend_strength': 'NEUTRAL'
        }
        
        # -----------------------------------------------------------------
        # TECHNICAL ANALYSIS
        # -----------------------------------------------------------------
        try:
            close = df['Close']
            high = df['High']
            low = df['Low']
            
            # RSI
            rsi = calculate_rsi(close).iloc[-1]
            signals['technical']['rsi'] = float(rsi) if not pd.isna(rsi) else 50
            
            # Moving Averages
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma20
            ema9 = close.ewm(span=9).mean().iloc[-1]
            ema21 = close.ewm(span=21).mean().iloc[-1]
            
            signals['technical']['sma20'] = float(sma20)
            signals['technical']['sma50'] = float(sma50)
            signals['technical']['ema9'] = float(ema9)
            signals['technical']['ema21'] = float(ema21)
            signals['technical']['above_sma20'] = current_price > sma20
            signals['technical']['above_sma50'] = current_price > sma50
            signals['technical']['ema_bullish'] = ema9 > ema21
            signals['technical']['golden_cross'] = sma20 > sma50
            
            # ATR
            atr = calculate_atr(high, low, close).iloc[-1]
            signals['technical']['atr'] = float(atr) if not pd.isna(atr) else current_price * 0.02
            signals['technical']['atr_pct'] = (signals['technical']['atr'] / current_price) * 100
            
            # Momentum (5-day returns)
            returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
            signals['technical']['momentum_5d'] = float(returns_5d)
            
            # Volatility
            volatility = close.pct_change().tail(20).std() * np.sqrt(252) * 100
            signals['technical']['volatility'] = float(volatility) if not pd.isna(volatility) else 20
            
            # Support/Resistance
            sr = find_support_resistance_zones(df)
            signals['technical']['nearest_support'] = sr['nearest_support']
            signals['technical']['nearest_resistance'] = sr['nearest_resistance']
            signals['technical']['supports'] = sr['supports']
            signals['technical']['resistances'] = sr['resistances']
            
            # Fibonacci levels
            recent_low = low.tail(60).min()
            recent_high = high.tail(60).max()
            fib_levels = calculate_fibonacci_extensions(recent_low, recent_high, position_type)
            signals['technical']['fib_levels'] = fib_levels
            
            # Price position in range
            price_range = recent_high - recent_low
            if price_range > 0:
                range_position = (current_price - recent_low) / price_range
                signals['technical']['range_position'] = float(range_position)
            else:
                signals['technical']['range_position'] = 0.5
            
        except Exception as e:
            logger.warning(f"Technical analysis error for {ticker}: {e}")
            signals['technical']['error'] = str(e)
        
        # -----------------------------------------------------------------
        # MARKET HEALTH
        # -----------------------------------------------------------------
        if market_health:
            signals['market']['status'] = market_health.get('status', 'NEUTRAL')
            signals['market']['health_score'] = market_health.get('health_score', 50)
            signals['market']['vix'] = market_health.get('vix', 15)
            signals['market']['nifty_change'] = market_health.get('nifty_change', 0)
            signals['market']['above_sma20'] = market_health.get('above_sma20', True)
            
            # Market regime adjustments
            if signals['market']['status'] == 'BULLISH':
                signals['market']['target_multiplier'] = self.config['bullish_target_boost']
                signals['market']['sl_multiplier'] = 1.0  # Normal SL in bull
            elif signals['market']['status'] == 'BEARISH':
                signals['market']['target_multiplier'] = 1.0  # Normal targets in bear
                signals['market']['sl_multiplier'] = self.config['bearish_sl_tighten']
            else:
                signals['market']['target_multiplier'] = 1.0
                signals['market']['sl_multiplier'] = 1.0
        else:
            signals['market']['target_multiplier'] = 1.0
            signals['market']['sl_multiplier'] = 1.0
        
        # -----------------------------------------------------------------
        # AI PREDICTIONS (if available)
        # -----------------------------------------------------------------
        if self.ai_features_available.get('lstm') and len(df) >= 100:
            try:
                from ai_features import predict_price_lstm
                lstm_result = predict_price_lstm(df, periods=5)
                
                if lstm_result and lstm_result.get('status') == 'success':
                    signals['ai']['lstm_prediction'] = lstm_result.get('predicted_price')
                    signals['ai']['lstm_change_pct'] = lstm_result.get('change_pct')
                    signals['ai']['lstm_trend'] = lstm_result.get('trend')
                    signals['ai']['lstm_confidence'] = lstm_result.get('confidence')
            except Exception as e:
                logger.warning(f"LSTM prediction error: {e}")
        
        if self.ai_features_available.get('regime'):
            try:
                from ai_features import detect_market_regime
                import yfinance as yf
                
                nifty = yf.Ticker("^NSEI")
                nifty_df = nifty.history(period="1y")
                
                if not nifty_df.empty:
                    regime_result = detect_market_regime(nifty_df)
                    if regime_result and regime_result.get('status') == 'success':
                        signals['ai']['regime'] = regime_result.get('regime')
                        signals['ai']['regime_confidence'] = regime_result.get('confidence')
            except Exception as e:
                logger.warning(f"Regime detection error: {e}")
        
        if self.ai_features_available.get('rl_optimizer'):
            try:
                from ai_features import get_rl_optimized_sl
                rl_result = get_rl_optimized_sl(df, entry_price, current_price, position_type)
                
                if rl_result:
                    signals['ai']['rl_optimal_sl'] = rl_result.get('optimal_sl')
                    signals['ai']['rl_multiplier'] = rl_result.get('multiplier')
            except Exception as e:
                logger.warning(f"RL optimizer error: {e}")
        
        # -----------------------------------------------------------------
        # SENTIMENT (if available)
        # -----------------------------------------------------------------
        if self.ai_features_available.get('sentiment'):
            try:
                from ai_features import get_real_sentiment
                sentiment_result = get_real_sentiment(ticker)
                
                if sentiment_result and sentiment_result.get('status') == 'success':
                    signals['sentiment']['score'] = sentiment_result.get('score', 0)
                    signals['sentiment']['type'] = sentiment_result.get('type', 'NEUTRAL')
                    signals['sentiment']['confidence'] = sentiment_result.get('confidence', 50)
            except Exception as e:
                logger.warning(f"Sentiment analysis error: {e}")
        
        # -----------------------------------------------------------------
        # CALCULATE AGGREGATE SCORES
        # -----------------------------------------------------------------
        signals = self._calculate_aggregate_scores(signals, position_type)
        
        return signals
    
    def _calculate_aggregate_scores(self, signals: Dict, position_type: str) -> Dict:
        """Calculate bullish/bearish aggregate scores"""
        
        bullish_score = 0
        bearish_score = 0
        confidence_factors = []
        
        tech = signals.get('technical', {})
        market = signals.get('market', {})
        ai = signals.get('ai', {})
        sentiment = signals.get('sentiment', {})
        
        # Technical factors (weight: 40%)
        if tech.get('rsi', 50) > 50:
            bullish_score += 10
        else:
            bearish_score += 10
        
        if tech.get('above_sma20'):
            bullish_score += 8
        else:
            bearish_score += 8
        
        if tech.get('above_sma50'):
            bullish_score += 7
        else:
            bearish_score += 7
        
        if tech.get('ema_bullish'):
            bullish_score += 8
        else:
            bearish_score += 8
        
        if tech.get('momentum_5d', 0) > 0:
            bullish_score += 7
        else:
            bearish_score += 7
        
        # Market factors (weight: 25%)
        if market.get('status') == 'BULLISH':
            bullish_score += 15
        elif market.get('status') == 'BEARISH':
            bearish_score += 15
        elif market.get('status') == 'WEAK':
            bearish_score += 10
        
        market_health = market.get('health_score', 50)
        if market_health >= 70:
            bullish_score += 10
        elif market_health <= 30:
            bearish_score += 10
        
        # AI factors (weight: 25%)
        lstm_trend = ai.get('lstm_trend', '')
        if lstm_trend == 'BULLISH':
            bullish_score += 15
            confidence_factors.append(ai.get('lstm_confidence', 50))
        elif lstm_trend == 'BEARISH':
            bearish_score += 15
            confidence_factors.append(ai.get('lstm_confidence', 50))
        
        regime = ai.get('regime', '')
        if 'BULL' in regime:
            bullish_score += 10
            confidence_factors.append(ai.get('regime_confidence', 50))
        elif 'BEAR' in regime:
            bearish_score += 10
            confidence_factors.append(ai.get('regime_confidence', 50))
        
        # Sentiment factors (weight: 10%)
        sent_type = sentiment.get('type', 'NEUTRAL')
        if sent_type in ['BULLISH', 'SLIGHTLY_BULLISH']:
            bullish_score += 10
            confidence_factors.append(sentiment.get('confidence', 50))
        elif sent_type in ['BEARISH', 'SLIGHTLY_BEARISH']:
            bearish_score += 10
            confidence_factors.append(sentiment.get('confidence', 50))
        
        # Calculate trend strength and confidence
        total_score = bullish_score + bearish_score
        if total_score > 0:
            bull_pct = (bullish_score / total_score) * 100
            bear_pct = (bearish_score / total_score) * 100
        else:
            bull_pct = bear_pct = 50
        
        if bull_pct > 70:
            trend_strength = 'STRONG_BULLISH'
        elif bull_pct > 55:
            trend_strength = 'BULLISH'
        elif bear_pct > 70:
            trend_strength = 'STRONG_BEARISH'
        elif bear_pct > 55:
            trend_strength = 'BEARISH'
        else:
            trend_strength = 'NEUTRAL'
        
        # Overall confidence
        if confidence_factors:
            confidence = int(np.mean(confidence_factors))
        else:
            confidence = int(min(bull_pct, bear_pct) + 20)  # Higher diff = higher confidence
        
        signals['bullish_score'] = bullish_score
        signals['bearish_score'] = bearish_score
        signals['bullish_pct'] = bull_pct
        signals['bearish_pct'] = bear_pct
        signals['trend_strength'] = trend_strength
        signals['confidence'] = min(100, confidence)
        
        return signals
    
    def _calculate_optimal_levels(
        self,
        position_type: str,
        entry_price: float,
        current_price: float,
        original_sl: float,
        original_target1: float,
        original_target2: float,
        df: pd.DataFrame,
        signals: Dict,
        market_health: Optional[Dict]
    ) -> Dict:
        """
        🎯 Calculate optimal SL and Target levels
        
        This is where the magic happens - dynamic level calculation
        """
        
        tech = signals.get('technical', {})
        market = signals.get('market', {})
        ai = signals.get('ai', {})
        
        atr = tech.get('atr', current_price * 0.02)
        pnl_pct = signals.get('pnl_pct', 0)
        
        # Initialize with original values
        optimal = {
            'sl': original_sl,
            'target1': original_target1,
            'target2': original_target2,
            'sl_reason': 'Original',
            'target1_reason': 'Original',
            'target2_reason': 'Original',
            'changes_made': False
        }
        
        # =====================================================================
        # STOP LOSS CALCULATION
        # =====================================================================
        
        if position_type == 'LONG':
            # Base SL from ATR
            atr_sl = current_price - (atr * 2.0)
            
            # Consider RL optimizer suggestion
            rl_sl = ai.get('rl_optimal_sl', atr_sl)
            
            # Support-based SL
            nearest_support = tech.get('nearest_support', entry_price * 0.95)
            support_sl = nearest_support - (atr * 0.5)  # Just below support
            
            # Trail SL based on profit
            trail_sl = original_sl
            if pnl_pct >= 10:  # 10%+ profit
                trail_sl = entry_price + (current_price - entry_price) * 0.7  # Lock 70%
                optimal['sl_reason'] = 'Trail: Locking 70% profit'
            elif pnl_pct >= 6:  # 6%+ profit
                trail_sl = entry_price + (current_price - entry_price) * 0.5  # Lock 50%
                optimal['sl_reason'] = 'Trail: Locking 50% profit'
            elif pnl_pct >= 4:  # 4%+ profit
                trail_sl = entry_price + (current_price - entry_price) * 0.3  # Lock 30%
                optimal['sl_reason'] = 'Trail: Locking 30% profit'
            elif pnl_pct >= self.config['breakeven_trigger_pct']:  # 2%+ profit
                trail_sl = entry_price * 1.002  # Move to breakeven + 0.2%
                optimal['sl_reason'] = 'Trail: Moved to breakeven'
            
            # Choose best SL (highest of all methods, but below current price)
            candidate_sls = [s for s in [atr_sl, rl_sl, support_sl, trail_sl] if s < current_price]
            
            if candidate_sls:
                best_sl = max(candidate_sls)
                
                # Never move SL down (only up for longs)
                if best_sl > original_sl:
                    optimal['sl'] = best_sl
                    optimal['changes_made'] = True
                    
                    if best_sl == trail_sl:
                        pass  # Reason already set
                    elif best_sl == rl_sl:
                        optimal['sl_reason'] = 'RL Optimizer suggestion'
                    elif best_sl == support_sl:
                        optimal['sl_reason'] = 'Just below support level'
                    else:
                        optimal['sl_reason'] = 'ATR-based stop'
            
            # Market regime adjustment
            sl_multiplier = market.get('sl_multiplier', 1.0)
            if sl_multiplier < 1.0:  # Bearish market - tighten
                tightened_sl = current_price - (current_price - optimal['sl']) * sl_multiplier
                if tightened_sl > optimal['sl']:
                    optimal['sl'] = tightened_sl
                    optimal['sl_reason'] += ' (Tightened for bearish market)'
                    optimal['changes_made'] = True
        
        else:  # SHORT position
            # Similar logic but inverted
            atr_sl = current_price + (atr * 2.0)
            rl_sl = ai.get('rl_optimal_sl', atr_sl)
            nearest_resistance = tech.get('nearest_resistance', entry_price * 1.05)
            resistance_sl = nearest_resistance + (atr * 0.5)
            
            trail_sl = original_sl
            if pnl_pct >= 10:
                trail_sl = entry_price - (entry_price - current_price) * 0.7
                optimal['sl_reason'] = 'Trail: Locking 70% profit'
            elif pnl_pct >= 6:
                trail_sl = entry_price - (entry_price - current_price) * 0.5
                optimal['sl_reason'] = 'Trail: Locking 50% profit'
            elif pnl_pct >= 4:
                trail_sl = entry_price - (entry_price - current_price) * 0.3
                optimal['sl_reason'] = 'Trail: Locking 30% profit'
            elif pnl_pct >= self.config['breakeven_trigger_pct']:
                trail_sl = entry_price * 0.998
                optimal['sl_reason'] = 'Trail: Moved to breakeven'
            
            candidate_sls = [s for s in [atr_sl, rl_sl, resistance_sl, trail_sl] if s > current_price]
            
            if candidate_sls:
                best_sl = min(candidate_sls)
                
                if best_sl < original_sl:  # Move SL down for shorts
                    optimal['sl'] = best_sl
                    optimal['changes_made'] = True
        
        # =====================================================================
        # TARGET CALCULATION
        # =====================================================================
        
        trend = signals.get('trend_strength', 'NEUTRAL')
        confidence = signals.get('confidence', 50)
        momentum = tech.get('momentum_5d', 0)
        
        # Fibonacci levels
        fib = tech.get('fib_levels', {})
        
        if position_type == 'LONG':
            # Check if we can extend targets
            can_extend = (
                trend in ['STRONG_BULLISH', 'BULLISH'] and
                confidence >= self.config['min_confidence_to_extend'] and
                momentum > 0 and
                pnl_pct > 0  # Only extend if already in profit
            )
            
            if can_extend:
                # Calculate extended targets
                nearest_resistance = tech.get('nearest_resistance', original_target1)
                
                # Target 1: Use higher of original, Fib 1.272, or resistance
                new_target1_candidates = [
                    original_target1,
                    fib.get('fib_1.272', original_target1),
                    nearest_resistance
                ]
                new_target1 = max([t for t in new_target1_candidates if t > current_price], 
                                  default=original_target1)
                
                # Apply market multiplier
                target_multiplier = market.get('target_multiplier', 1.0)
                if target_multiplier > 1.0:
                    extension = (new_target1 - entry_price) * (target_multiplier - 1)
                    new_target1 = new_target1 + extension
                
                # LSTM prediction can extend further
                lstm_pred = ai.get('lstm_prediction')
                if lstm_pred and lstm_pred > new_target1 and ai.get('lstm_confidence', 0) >= 60:
                    # Blend LSTM prediction (weight by confidence)
                    lstm_conf = ai.get('lstm_confidence', 50) / 100
                    new_target1 = new_target1 * (1 - lstm_conf * 0.3) + lstm_pred * (lstm_conf * 0.3)
                
                if new_target1 > original_target1:
                    optimal['target1'] = new_target1
                    optimal['target1_reason'] = f'Extended ({trend}, {confidence}% conf)'
                    optimal['changes_made'] = True
                
                # Target 2: Higher extension
                new_target2_candidates = [
                    original_target2,
                    fib.get('fib_1.618', original_target2),
                    fib.get('fib_2.0', original_target2),
                    tech.get('resistances', [original_target2])[1] if len(tech.get('resistances', [])) > 1 else original_target2
                ]
                new_target2 = max([t for t in new_target2_candidates if t > optimal['target1']], 
                                  default=original_target2)
                
                if new_target2 > original_target2:
                    optimal['target2'] = new_target2
                    optimal['target2_reason'] = f'Extended to Fib 1.618/2.0'
                    optimal['changes_made'] = True
            
            # Reduce targets in bearish conditions
            elif trend in ['STRONG_BEARISH', 'BEARISH'] and pnl_pct > 3:
                # Book profits sooner
                reduced_target1 = entry_price + (original_target1 - entry_price) * 0.7
                if reduced_target1 < original_target1 and reduced_target1 > current_price:
                    optimal['target1'] = reduced_target1
                    optimal['target1_reason'] = 'Reduced for bearish conditions'
                    optimal['changes_made'] = True
        
        else:  # SHORT
            can_extend = (
                trend in ['STRONG_BEARISH', 'BEARISH'] and
                confidence >= self.config['min_confidence_to_extend'] and
                momentum < 0 and
                pnl_pct > 0
            )
            
            if can_extend:
                nearest_support = tech.get('nearest_support', original_target1)
                
                new_target1_candidates = [
                    original_target1,
                    fib.get('fib_1.272', original_target1),
                    nearest_support
                ]
                new_target1 = min([t for t in new_target1_candidates if t < current_price], 
                                  default=original_target1)
                
                if new_target1 < original_target1:
                    optimal['target1'] = new_target1
                    optimal['target1_reason'] = f'Extended ({trend}, {confidence}% conf)'
                    optimal['changes_made'] = True
        
        return optimal
    
    def _determine_changes(
        self,
        original_sl: float,
        original_target1: float,
        original_target2: float,
        optimal: Dict,
        signals: Dict
    ) -> Dict:
        """Determine what changes are recommended"""
        
        changes = {
            'sl_changed': abs(optimal['sl'] - original_sl) / original_sl > 0.001,
            'target1_changed': abs(optimal['target1'] - original_target1) / original_target1 > 0.001,
            'target2_changed': abs(optimal['target2'] - original_target2) / original_target2 > 0.001,
            'sl_change_pct': ((optimal['sl'] - original_sl) / original_sl) * 100,
            'target1_change_pct': ((optimal['target1'] - original_target1) / original_target1) * 100,
            'target2_change_pct': ((optimal['target2'] - original_target2) / original_target2) * 100,
            'any_change': False,
            'change_count': 0
        }
        
        changes['any_change'] = changes['sl_changed'] or changes['target1_changed'] or changes['target2_changed']
        changes['change_count'] = sum([changes['sl_changed'], changes['target1_changed'], changes['target2_changed']])
        
        return changes
    
    def _generate_recommendation(
        self,
        ticker: str,
        position_type: str,
        entry_price: float,
        current_price: float,
        original_sl: float,
        original_target1: float,
        original_target2: float,
        optimal: Dict,
        changes: Dict,
        signals: Dict
    ) -> Dict:
        """Generate final recommendation with all details"""
        
        pnl_pct = signals.get('pnl_pct', 0)
        trend = signals.get('trend_strength', 'NEUTRAL')
        confidence = signals.get('confidence', 50)
        
        # Determine action priority
        if changes['any_change']:
            if changes['sl_changed'] and optimal['sl_reason'].startswith('Trail'):
                action = 'TRAIL_SL'
                priority = 'HIGH'
            elif changes['target1_changed'] and 'Extended' in optimal['target1_reason']:
                action = 'EXTEND_TARGET'
                priority = 'MEDIUM'
            elif changes['sl_changed']:
                action = 'UPDATE_SL'
                priority = 'HIGH'
            else:
                action = 'UPDATE_LEVELS'
                priority = 'MEDIUM'
        else:
            action = 'NO_CHANGE'
            priority = 'LOW'
        
        # Generate summary message
        messages = []
        if changes['sl_changed']:
            direction = "up" if optimal['sl'] > original_sl else "down"
            messages.append(f"SL moved {direction} to ₹{optimal['sl']:,.2f} ({changes['sl_change_pct']:+.1f}%)")
        if changes['target1_changed']:
            direction = "up" if optimal['target1'] > original_target1 else "down"
            messages.append(f"Target 1 {direction} to ₹{optimal['target1']:,.2f}")
        if changes['target2_changed']:
            direction = "up" if optimal['target2'] > original_target2 else "down"
            messages.append(f"Target 2 {direction} to ₹{optimal['target2']:,.2f}")
        
        summary = " | ".join(messages) if messages else "No changes needed"
        
        return {
            'ticker': ticker,
            'position_type': position_type,
            'timestamp': datetime.now().isoformat(),
            
            # Current state
            'entry_price': entry_price,
            'current_price': current_price,
            'pnl_pct': pnl_pct,
            
            # Original levels
            'original_sl': original_sl,
            'original_target1': original_target1,
            'original_target2': original_target2,
            
            # New recommended levels
            'new_sl': optimal['sl'],
            'new_target1': optimal['target1'],
            'new_target2': optimal['target2'],
            
            # Reasons
            'sl_reason': optimal['sl_reason'],
            'target1_reason': optimal['target1_reason'],
            'target2_reason': optimal['target2_reason'],
            
            # Changes
            'changes': changes,
            'any_change': changes['any_change'],
            
            # Action
            'action': action,
            'priority': priority,
            'summary': summary,
            
            # Signals used
            'trend': trend,
            'confidence': confidence,
            'bullish_score': signals.get('bullish_score', 0),
            'bearish_score': signals.get('bearish_score', 0),
            
            # Full signals for reference
            'signals': signals,
            
            # Alert flag
            'should_alert': changes['any_change'] and priority in ['HIGH', 'MEDIUM']
        }
    
    def _create_no_change_result(
        self,
        ticker: str,
        sl: float,
        target1: float,
        target2: float,
        reason: str
    ) -> Dict:
        """Create a no-change result"""
        return {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'new_sl': sl,
            'new_target1': target1,
            'new_target2': target2,
            'any_change': False,
            'action': 'NO_CHANGE',
            'priority': 'LOW',
            'summary': reason,
            'should_alert': False
        }
    
    def _log_decision(self, ticker: str, recommendation: Dict):
        """Log decision for learning"""
        self.decision_history.append({
            'ticker': ticker,
            'timestamp': recommendation['timestamp'],
            'action': recommendation['action'],
            'changes': recommendation.get('changes', {}),
            'confidence': recommendation.get('confidence', 0)
        })
        
        # Keep last 1000 decisions
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]


# ============================================================================
# POSITION MONITOR - Continuous Monitoring
# ============================================================================

class PositionMonitor:
    """
    📊 Continuous Position Monitor
    
    Monitors all positions and triggers AI analysis
    """
    
    def __init__(self):
        self.brain = AITradingBrain()
        self.last_analysis = {}
        self.alerts = []
    
    def monitor_all_positions(
        self,
        portfolio: pd.DataFrame,
        stock_data: Dict[str, pd.DataFrame],
        market_health: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Monitor all positions and return AI recommendations
        
        Args:
            portfolio: DataFrame with positions
            stock_data: Dict of {ticker: DataFrame} with price data
            market_health: Current market health
        
        Returns:
            List of recommendations for each position
        """
        
        recommendations = []
        
        for _, row in portfolio.iterrows():
            ticker = str(row['Ticker']).strip()
            
            # Get stock data
            df = stock_data.get(ticker) or stock_data.get(f"{ticker}.NS")
            
            if df is not None and not df.empty:
                continue
            
            try:
                current_price = float(df['Close'].iloc[-1])
                
                rec = self.brain.analyze_position(
                    ticker=ticker,
                    position_type=str(row['Position']).upper().strip(),
                    entry_price=float(row['Entry_Price']),
                    current_price=current_price,
                    original_sl=float(row['Stop_Loss']),
                    original_target1=float(row['Target_1']),
                    original_target2=float(row.get('Target_2', row['Target_1'] * 1.1)),
                    quantity=int(row.get('Quantity', 1)),
                    df=df,
                    market_health=market_health
                )
                
                recommendations.append(rec)
                
                # Store alert if needed
                if rec.get('should_alert'):
                    self.alerts.append(rec)
            
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
        
        return recommendations
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get pending alerts and clear them"""
        alerts = self.alerts.copy()
        self.alerts = []
        return alerts


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

trading_brain = AITradingBrain()
position_monitor = PositionMonitor()


# ============================================================================
# EASY-TO-USE FUNCTIONS
# ============================================================================

def analyze_single_position(
    ticker: str,
    position_type: str,
    entry_price: float,
    current_price: float,
    stop_loss: float,
    target1: float,
    target2: float,
    df: pd.DataFrame,
    market_health: Optional[Dict] = None
) -> Dict:
    """
    Analyze a single position and get AI recommendation
    
    Usage:
        result = analyze_single_position(
            ticker="RELIANCE",
            position_type="LONG",
            entry_price=2500,
            current_price=2650,
            stop_loss=2400,
            target1=2700,
            target2=2900,
            df=stock_df,
            market_health=market_health
        )
        
        if result['any_change']:
            print(f"New SL: {result['new_sl']}")
            print(f"New Target 1: {result['new_target1']}")
    """
    return trading_brain.analyze_position(
        ticker=ticker,
        position_type=position_type,
        entry_price=entry_price,
        current_price=current_price,
        original_sl=stop_loss,
        original_target1=target1,
        original_target2=target2,
        quantity=1,
        df=df,
        market_health=market_health
    )


def analyze_portfolio(
    portfolio: pd.DataFrame,
    stock_data: Dict[str, pd.DataFrame],
    market_health: Optional[Dict] = None
) -> List[Dict]:
    """
    Analyze entire portfolio and get AI recommendations
    """
    return position_monitor.monitor_all_positions(
        portfolio=portfolio,
        stock_data=stock_data,
        market_health=market_health
    )


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_trading_brain():
    """Test the trading brain with sample data"""
    
    print("=" * 60)
    print("🧠 TESTING AI TRADING BRAIN")
    print("=" * 60)
    
    # Create sample data
    import numpy as np
    
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    np.random.seed(42)
    
    # Simulate uptrending stock
    close = 1000 + np.cumsum(np.random.randn(100) * 20 + 1)  # Slight upward bias
    high = close + np.random.rand(100) * 20
    low = close - np.random.rand(100) * 20
    volume = np.random.randint(100000, 500000, 100)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': close - np.random.rand(100) * 5,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    })
    
    current_price = float(df['Close'].iloc[-1])
    entry_price = 1000
    
    print(f"\n📊 Test Position:")
    print(f"  Entry: ₹{entry_price}")
    print(f"  Current: ₹{current_price:.2f}")
    print(f"  P&L: {((current_price - entry_price) / entry_price) * 100:.1f}%")
    
    # Test analysis
    result = analyze_single_position(
        ticker="TEST",
        position_type="LONG",
        entry_price=entry_price,
        current_price=current_price,
        stop_loss=950,
        target1=1100,
        target2=1200,
        df=df,
        market_health={'status': 'BULLISH', 'health_score': 75}
    )
    
    print(f"\n🤖 AI Recommendation:")
    print(f"  Action: {result['action']}")
    print(f"  Priority: {result['priority']}")
    print(f"  Summary: {result['summary']}")
    print(f"\n📊 New Levels:")
    print(f"  SL: ₹{result['new_sl']:.2f} ({result['sl_reason']})")
    print(f"  Target 1: ₹{result['new_target1']:.2f} ({result['target1_reason']})")
    print(f"  Target 2: ₹{result['new_target2']:.2f} ({result['target2_reason']})")
    print(f"\n📈 Analysis:")
    print(f"  Trend: {result['trend']}")
    print(f"  Confidence: {result['confidence']}%")
    print(f"  Changes Made: {result['any_change']}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    
    return result


if __name__ == "__main__":
    test_trading_brain()
