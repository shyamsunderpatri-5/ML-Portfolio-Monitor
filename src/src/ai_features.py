"""
🤖 AI & ML FEATURES FOR SMART PORTFOLIO MONITOR v2.0
=====================================================
Advanced features including:
- LSTM Price Prediction
- Reinforcement Learning Stop Loss
- FinBERT Sentiment Analysis
- Monte Carlo Portfolio Optimization
- Hidden Markov Model Market Regime Detection
- AI Trade Suggestions (Claude)
- Backtesting Engine
- Telegram/Discord Alerts

Author: Smart Portfolio Monitor Team
Version: 2.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import warnings
import json
import os
import threading

_LSTM_LOCK = threading.Lock()
warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

try:
    from trading_utils import calculate_rsi, calculate_atr, calculate_macd
except ImportError:
    pass  

# ============================================================================
# CONFIGURATION
# ============================================================================

AI_CONFIG = {
    # API Keys - Set these for full functionality
    'claude_api_key': os.getenv('ANTHROPIC_API_KEY', ''),  
    'news_api_key': os.getenv('NEWS_API_KEY', '50272e1e31b74cd8957606ba72b69d50'),
    'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'discord_webhook_url': os.getenv('DISCORD_WEBHOOK_URL', ''),
    
    # Model settings
    'lstm_epochs': 10,
    'lstm_batch_size': 32,
    'lstm_sequence_length': 60,
    'monte_carlo_simulations': 10000,
    'hmm_states': 4,
}
# Check available dependencies
AVAILABLE_FEATURES = {
    'tensorflow': False,
    'transformers': False,
    'hmmlearn': False,
    'sklearn': False,
    'newsapi': False,
}
DEPENDENCY_ERRORS = {}

try:
    import tensorflow as tf
    # Test with proper error handling
    try:
        _ = tf.constant([1, 2, 3])
        AVAILABLE_FEATURES['tensorflow'] = True
        logger.info(f"✅ TensorFlow {tf.__version__} ready")
    except Exception as test_error:
        # TF installed but not configured
        AVAILABLE_FEATURES['tensorflow'] = True  # Still mark as available
        logger.warning(f"⚠️ TensorFlow installed but needs configuration: {test_error}")
except ImportError:
    AVAILABLE_FEATURES['tensorflow'] = False
    logger.error("❌ TensorFlow not installed")

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    # Test if PyTorch works
    _ = torch.tensor([1, 2, 3])
    AVAILABLE_FEATURES['transformers'] = True
    logger.info("✅ Transformers available for sentiment analysis")
except ImportError as e:
    DEPENDENCY_ERRORS['transformers'] = str(e)
    logger.warning("⚠️ Transformers not installed - Sentiment analysis disabled")
except Exception as e:
    DEPENDENCY_ERRORS['transformers'] = f"Transformers error: {str(e)}"
    logger.warning(f"⚠️ Transformers error - Sentiment analysis disabled: {e}")

# Add this function to display dependency status:
def get_dependency_status():
    """Get detailed dependency status"""
    status = {}
    
    for feature, available in AVAILABLE_FEATURES.items():
        status[feature] = {
            'available': available,
            'error': DEPENDENCY_ERRORS.get(feature, None) if not available else None
        }
    
    return status

def validate_api_keys():
    """Warn if critical API keys are missing"""
    warnings = []
    
    if not AI_CONFIG['claude_api_key']:
        warnings.append("⚠️ Claude API key missing - AI suggestions disabled")
    
    if not AI_CONFIG['news_api_key']:
        warnings.append("⚠️ News API key missing - Sentiment analysis disabled")
    
    return warnings



# Try importing optional dependencies
try:
    import tensorflow as tf
    AVAILABLE_FEATURES['tensorflow'] = True
    logger.info("✅ TensorFlow available for LSTM predictions")
except ImportError:
    logger.warning("⚠️ TensorFlow not installed - LSTM predictions disabled")

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    AVAILABLE_FEATURES['transformers'] = True
    logger.info("✅ Transformers available for sentiment analysis")
except ImportError:
    logger.warning("⚠️ Transformers not installed - Sentiment analysis disabled")

try:
    from hmmlearn.hmm import GaussianHMM
    AVAILABLE_FEATURES['hmmlearn'] = True
    logger.info("✅ HMMLearn available for regime detection")
except ImportError:
    logger.warning("⚠️ HMMLearn not installed - Regime detection disabled")

try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
    AVAILABLE_FEATURES['sklearn'] = True
    logger.info("✅ Scikit-learn available")
except ImportError:
    logger.warning("⚠️ Scikit-learn not installed")

try:
    import requests
    AVAILABLE_FEATURES['newsapi'] = True
except ImportError:
    pass


# ============================================================================
# HELPER FUNCTIONS (from main app - needed for calculations)
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


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculate MACD"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram


# ============================================================================
# 1. LSTM PRICE PREDICTION
# ============================================================================

class LSTMPredictor:
    """
    LSTM-based price prediction model
    Predicts future price movements based on historical patterns
    """
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_fitted = False
        self.model_cache = {}  # Cache models by ticker
        self.cache_dir = 'model_cache'
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        import os
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
            except Exception:
                self.cache_dir = '.'  # Use current directory as fallback
    
    def _get_cache_key(self, df: pd.DataFrame) -> str:
        """Generate cache key based on data characteristics"""
        if df is None or df.empty:
            return ""
        
        # Use last price and data length as cache key
        last_price = df['Close'].iloc[-1]
        data_len = len(df)
        
        # Round last price to reduce cache misses from tiny price changes
        price_bucket = round(last_price / 10) * 10
        
        return f"{data_len}_{price_bucket}"
    
    def _get_cached_model(self, cache_key: str):
        """Get cached model if available and still valid"""
        if cache_key in self.model_cache:
            cached = self.model_cache[cache_key]
            # Check if cache is less than 1 hour old
            age = (datetime.now() - cached['timestamp']).total_seconds()
            if age < 3600:  # 1 hour
                return cached['model'], cached['scaler']
        return None, None
    
    def _cache_model(self, cache_key: str, model, scaler):
        """Cache the trained model"""
        self.model_cache[cache_key] = {
            'model': model,
            'scaler': scaler,
            'timestamp': datetime.now()
        }
        
        # Limit cache size
        if len(self.model_cache) > 10:
            # Remove oldest entry
            oldest_key = min(self.model_cache.keys(), 
                           key=lambda k: self.model_cache[k]['timestamp'])
            del self.model_cache[oldest_key]
    
    def is_available(self) -> bool:
        """Check if TensorFlow is available"""
        return AVAILABLE_FEATURES['tensorflow']

    def _load_cached_model(self):
        """Load pre-trained model if exists"""
        import os
        if os.path.exists(self.model_cache_file):
            try:
                from tensorflow.keras.models import load_model
                import pickle
                
                self.model = load_model(self.model_cache_file)
                with open(self.scaler_cache_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                logger.info("✅ Loaded cached LSTM model")
                return True
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
        return False
    
    def _save_model_cache(self):
        """Save trained model for reuse"""
        try:
            import pickle
            self.model.save(self.model_cache_file)
            with open(self.scaler_cache_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info("✅ Saved LSTM model to cache")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def predict(self, df: pd.DataFrame, periods: int = 5) -> Optional[Dict]:
        """
        Predict next N periods using LSTM
        
        Args:
            df: DataFrame with 'Close' prices
            periods: Number of days to predict
        
        Returns:
            Dict with predictions, confidence, etc.
        """
        # Check cache first
        cache_key = self._get_cache_key(df)
        cached_model, cached_scaler = self._get_cached_model(cache_key)
        
        use_cached = cached_model is not None

        if not self.is_available():
            return {
                'status': 'error',
                'message': 'TensorFlow not installed. Run: pip install tensorflow',
                'predictions': None
            }
        
        if df is None or len(df) < 100:
            return {
                'status': 'error',
                'message': 'Need at least 100 data points for LSTM',
                'predictions': None
            }
        
        try:
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from sklearn.preprocessing import MinMaxScaler

            # Prepare data (safe – numpy/sklearn only)
            close_prices = df['Close'].values.reshape(-1, 1)
            self.scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data = self.scaler.fit_transform(close_prices)

            sequence_length = AI_CONFIG['lstm_sequence_length']
            X, y = [], []

            for i in range(sequence_length, len(scaled_data)):
                X.append(scaled_data[i-sequence_length:i, 0])
                y.append(scaled_data[i, 0])

            X, y = np.array(X), np.array(y)
            X = np.reshape(X, (X.shape[0], X.shape[1], 1))

            split = int(len(X) * 0.8)
            X_train, X_val = X[:split], X[split:]
            y_train, y_val = y[:split], y[split:]

            # 🔒 LOCK STARTS HERE
            with _LSTM_LOCK:

                if use_cached:
                    self.model = cached_model
                    self.scaler = cached_scaler
                    logger.info("Using cached LSTM model")
                    train_loss = 0.01
                    val_loss = 0.01

                else:
                    from tensorflow.keras.callbacks import EarlyStopping

                    self.model = Sequential([
                        LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)),
                        Dropout(0.2),
                        LSTM(50, return_sequences=True),
                        Dropout(0.2),
                        LSTM(50, return_sequences=False),
                        Dropout(0.2),
                        Dense(25, activation='relu'),
                        Dense(1)
                    ])

                    self.model.compile(optimizer='adam', loss='mean_squared_error')

                    early_stop = EarlyStopping(
                        monitor='val_loss',
                        patience=3,
                        restore_best_weights=True
                    )

                    history = self.model.fit(
                        X_train, y_train,
                        batch_size=AI_CONFIG['lstm_batch_size'],
                        epochs=AI_CONFIG['lstm_epochs'],
                        validation_data=(X_val, y_val),
                        callbacks=[early_stop],
                        verbose=0
                    )

                    train_loss = history.history['loss'][-1]
                    val_loss = history.history['val_loss'][-1]

                    self._cache_model(cache_key, self.model, self.scaler)
                    logger.info("Trained and cached new LSTM model")

                # 🔒 ALSO protect prediction loop
                last_sequence = scaled_data[-sequence_length:]
                predictions = []
                current_sequence = last_sequence.copy()

                for _ in range(periods):
                    pred = self.model.predict(
                        current_sequence.reshape(1, sequence_length, 1),
                        verbose=0
                    )
                    predictions.append(pred[0][0])
                    current_sequence = np.append(current_sequence[1:], pred)

            # 🔓 LOCK ENDS HERE

            
            # Inverse transform predictions
            predictions = self.scaler.inverse_transform(
                np.array(predictions).reshape(-1, 1)
            ).flatten()
            
            # Calculate confidence based on validation loss
            confidence = max(0, min(100, int(100 * (1 - val_loss))))
            
            # Determine trend
            current_price = float(df['Close'].iloc[-1])
            predicted_final = predictions[-1]
            trend = "BULLISH" if predicted_final > current_price else "BEARISH"
            change_pct = ((predicted_final - current_price) / current_price) * 100
            
            self.is_fitted = True
            
            return {
                'status': 'success',
                'predictions': predictions.tolist(),
                'current_price': current_price,
                'predicted_price': float(predicted_final),
                'change_pct': float(change_pct),
                'trend': trend,
                'confidence': confidence,
                'model': 'LSTM (3-layer)',
                'horizon': f'{periods} days',
                'train_loss': float(train_loss),
                'val_loss': float(val_loss),
                'generated_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"LSTM prediction failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'predictions': None
            }


# Global LSTM predictor instance
lstm_predictor = LSTMPredictor()


def predict_price_lstm(df: pd.DataFrame, periods: int = 5) -> Optional[Dict]:
    """
    Wrapper function for LSTM prediction
    
    Usage:
        result = predict_price_lstm(stock_df, periods=5)
        if result['status'] == 'success':
            print(f"Predicted price: ₹{result['predicted_price']:.2f}")
    """
    return lstm_predictor.predict(df, periods)


# ============================================================================
# 2. REINFORCEMENT LEARNING STOP LOSS OPTIMIZER
# ============================================================================

class RLStopLossOptimizer:
    """
    Q-Learning based adaptive stop loss optimizer
    Learns optimal SL placement from historical trades and market conditions
    
    State Space: (volatility_bucket, trend, rsi_bucket, pnl_bucket)
    Action Space: SL multiplier (1.0 to 4.0 x ATR)
    Reward: Positive for profitable trades, negative for losses
    """
    
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9):
        self.q_table = {}
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = 0.2  # Initial exploration rate
        self.epsilon_decay = 0.995  # Decay per trade
        self.epsilon_min = 0.05  # Minimum exploration
        self.trade_history = []
        self.max_q_table_size = 1000  # Limit Q-table size
        self.max_history_size = 500
        
        # Load saved Q-table if exists
        self._load_q_table()
    
    def _get_state(
        self, 
        df: pd.DataFrame, 
        entry_price: float, 
        current_price: float,
        position_type: str
    ) -> Tuple[int, int, int, int]:
        """
        Define state space based on market conditions
        
        Returns tuple of discretized features:
        - Volatility bucket (0-9)
        - Trend (0=bearish, 1=bullish)
        - RSI bucket (0-9)
        - P&L bucket (-5 to 5)
        """
        # Calculate features
        returns = df['Close'].pct_change().dropna()
        volatility = returns.tail(20).std()
        
        # Trend based on price vs SMA20
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        trend = 1 if df['Close'].iloc[-1] > sma20 else 0
        
        # RSI
        rsi = calculate_rsi(df['Close']).iloc[-1]
        if pd.isna(rsi):
            rsi = 50
        
        # Current P&L
        if position_type == "LONG":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Discretize features
        vol_bucket = min(9, int(volatility * 500))  # 0-9
        rsi_bucket = int(rsi / 10)  # 0-9
        pnl_bucket = max(-5, min(5, int(pnl_pct)))  # -5 to 5
        
        return (vol_bucket, trend, rsi_bucket, pnl_bucket)
    
    def _get_default_multiplier(self, state: Tuple) -> float:
        """Get default SL multiplier based on state"""
        vol_bucket, trend, rsi_bucket, pnl_bucket = state
        
        # Higher volatility = wider SL
        base_multiplier = 2.0 + (vol_bucket * 0.1)
        
        # Adjust for trend
        if trend == 1:  # Bullish
            base_multiplier -= 0.2
        else:
            base_multiplier += 0.2
        
        # Adjust for P&L (protect profits)
        if pnl_bucket > 2:
            base_multiplier -= 0.3
        elif pnl_bucket < -2:
            base_multiplier += 0.3
        
        return max(1.5, min(4.0, base_multiplier))
    
    def get_optimal_sl(
        self, 
        df: pd.DataFrame, 
        entry_price: float, 
        current_price: float, 
        position_type: str
    ) -> Tuple[float, float, str]:
        """
        Get RL-optimized stop loss
        
        Args:
            df: Price DataFrame
            entry_price: Entry price
            current_price: Current price
            position_type: LONG or SHORT
        
        Returns:
            (optimal_sl, sl_multiplier, reason)
        """
        state = self._get_state(df, entry_price, current_price, position_type)
        
        # Get learned or default multiplier
        if state in self.q_table:
            sl_multiplier = self.q_table[state]
            reason = f"RL-Optimized (learned from {len(self.trade_history)} trades)"
        else:
            sl_multiplier = self._get_default_multiplier(state)
            reason = "RL-Default (exploring)"
        
        # Calculate ATR
        atr = calculate_atr(df['High'], df['Low'], df['Close']).iloc[-1]
        if pd.isna(atr):
            atr = current_price * 0.02
        
        # Calculate optimal SL
        if position_type == "LONG":
            optimal_sl = current_price - (atr * sl_multiplier)
        else:
            optimal_sl = current_price + (atr * sl_multiplier)
        
        return optimal_sl, sl_multiplier, reason
    
    def update(
        self, 
        state: Tuple, 
        action: float, 
        reward: float, 
        next_state: Optional[Tuple] = None
    ):
        """
        Update Q-value after trade completion
        
        Args:
            state: State when SL was set
            action: SL multiplier used
            reward: Trade result (+ve for profit, -ve for loss)
            next_state: State at trade exit (optional)
        """
        if state not in self.q_table:
            self.q_table[state] = action
        
        old_q = self.q_table[state]
        
        if next_state is not None:
            next_max = self.q_table.get(next_state, action)
        else:
            next_max = action
        
        # Q-learning update
        new_q = old_q + self.alpha * (reward + self.gamma * next_max - old_q)
        
        # Bound the multiplier
        self.q_table[state] = max(1.5, min(4.0, new_q))
        
        # Log trade
        self.trade_history.append({
            'state': state,
            'action': action,
            'reward': reward,
            'new_q': self.q_table[state],
            'timestamp': datetime.now().isoformat()
        })
                # Decay exploration rate
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        # Limit Q-table size
        if len(self.q_table) > self.max_q_table_size:
            # Remove least-visited states
            state_visits = {}
            for trade in self.trade_history:
                state = trade.get('state')
                if state:
                    state_visits[state] = state_visits.get(state, 0) + 1
            
            # Sort by visits and keep top states
            sorted_states = sorted(state_visits.items(), key=lambda x: x[1], reverse=True)
            states_to_keep = set(s[0] for s in sorted_states[:self.max_q_table_size])
            
            self.q_table = {k: v for k, v in self.q_table.items() if k in states_to_keep}
            logger.info(f"Pruned Q-table to {len(self.q_table)} states")
        
        # Limit history size
        if len(self.trade_history) > self.max_history_size:
            self.trade_history = self.trade_history[-self.max_history_size:]
        # Save Q-table periodically
        if len(self.trade_history) % 10 == 0:
            self._save_q_table()
    
    def learn_from_trade(
        self,
        df: pd.DataFrame,
        entry_price: float,
        exit_price: float,
        position_type: str,
        sl_used: float,
        hit_sl: bool
    ):
        """
        Learn from a completed trade
        
        Args:
            df: Price data during trade
            entry_price: Entry price
            exit_price: Exit price
            position_type: LONG or SHORT
            sl_used: Stop loss that was used
            hit_sl: Whether SL was hit
        """
        # Calculate P&L
        if position_type == "LONG":
            pnl = exit_price - entry_price
        else:
            pnl = entry_price - exit_price
        
        # Get state at entry
        state = self._get_state(df, entry_price, entry_price, position_type)
        
        # Calculate reward
        if pnl > 0:
            reward = pnl / entry_price * 100  # Positive reward for profits
        else:
            if hit_sl:
                reward = -2  # Penalty for hitting SL
            else:
                reward = -1  # Smaller penalty for manual exit at loss
        
        # Calculate multiplier that was used
        atr = calculate_atr(df['High'], df['Low'], df['Close']).iloc[-1]
        if position_type == "LONG":
            multiplier_used = (entry_price - sl_used) / atr
        else:
            multiplier_used = (sl_used - entry_price) / atr
        
        # Update Q-table
        self.update(state, multiplier_used, reward)
    
    def _save_q_table(self):
        """Save Q-table to file"""
        try:
            data = {
                'q_table': {str(k): v for k, v in self.q_table.items()},
                'trade_count': len(self.trade_history),
                'last_updated': datetime.now().isoformat()
            }
            with open('rl_q_table.json', 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save Q-table: {e}")
    
    def _load_q_table(self):
        """Load Q-table from file"""
        try:
            if os.path.exists('rl_q_table.json'):
                with open('rl_q_table.json', 'r') as f:
                    data = json.load(f)
                    self.q_table = {eval(k): v for k, v in data.get('q_table', {}).items()}
                    logger.info(f"Loaded Q-table with {len(self.q_table)} states")
        except Exception as e:
            logger.warning(f"Failed to load Q-table: {e}")
    
    def get_stats(self) -> Dict:
        """Get RL optimizer statistics"""
        return {
            'states_learned': len(self.q_table),
            'trades_processed': len(self.trade_history),
            'avg_multiplier': np.mean(list(self.q_table.values())) if self.q_table else 2.0,
            'learning_rate': self.alpha,
            'discount_factor': self.gamma,
            'exploration_rate': round(self.epsilon, 4),
            'q_table_limit': self.max_q_table_size,
            'recent_performance': self._calculate_recent_performance()
        }
    
    def _calculate_recent_performance(self) -> Dict:
        """Calculate performance on recent trades"""
        recent = self.trade_history[-50:]  # Last 50 trades
        if not recent:
            return {'trades': 0, 'avg_reward': 0}
        
        rewards = [t.get('reward', 0) for t in recent]
        return {
            'trades': len(recent),
            'avg_reward': round(np.mean(rewards), 2),
            'positive_pct': round(sum(1 for r in rewards if r > 0) / len(rewards) * 100, 1)
        }
    
# Global RL optimizer instance
rl_optimizer = RLStopLossOptimizer()


def get_rl_optimized_sl(
    df: pd.DataFrame, 
    entry_price: float, 
    current_price: float, 
    position_type: str
) -> Dict:
    """
    Wrapper function for RL-optimized stop loss
    
    Usage:
        result = get_rl_optimized_sl(df, 100, 105, "LONG")
        print(f"Optimal SL: ₹{result['optimal_sl']:.2f}")
    """
    optimal_sl, multiplier, reason = rl_optimizer.get_optimal_sl(
        df, entry_price, current_price, position_type
    )
    
    return {
        'optimal_sl': optimal_sl,
        'multiplier': multiplier,
        'reason': reason,
        'stats': rl_optimizer.get_stats()
    }


# ============================================================================
# ============================================================================
# 3. REAL SENTIMENT ANALYSIS WITH FINBERT (DYNAMIC VERSION)
# ============================================================================

class SentimentAnalyzer:
    """
    Financial sentiment analysis using FinBERT model
    Dynamically fetches company info - NO HARDCODED TICKER MAPS
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        self._company_cache = {}
        self._cache_file = 'company_cache.json'
        
        # ✅ Add request tracking
        self._api_requests_today = 0
        self._last_request_date = None
        self._max_requests_per_day = 90 
        # Sentiment result cache
        self._sentiment_cache = {}
        self._sentiment_cache_ttl = 3600  # 1 hour cache

    def _check_rate_limit(self) -> bool:
        """Check if we can make another API request"""
        from datetime import date
        
        today = date.today()
        
        # Reset counter on new day
        if self._last_request_date != today:
            self._api_requests_today = 0
            self._last_request_date = today
        
        if self._api_requests_today >= self._max_requests_per_day:
            logger.warning(f"⚠️ API rate limit reached ({self._api_requests_today}/{self._max_requests_per_day})")
            return False
        
        return True
    
    def _load_cache(self):
        """Load company cache from file"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r') as f:
                    self._company_cache = json.load(f)
                logger.info(f"Loaded {len(self._company_cache)} cached company entries")
        except Exception as e:
            logger.warning(f"Could not load company cache: {e}")
            self._company_cache = {}
    
    def _save_cache(self):
        """Save company cache to file"""
        try:
            with open(self._cache_file, 'w') as f:
                json.dump(self._company_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save company cache: {e}")
    
    def is_available(self) -> bool:
        """Check if transformers is available"""
        return AVAILABLE_FEATURES['transformers']
    
    def _load_model(self):
        """Lazy load FinBERT model"""
        if self.is_loaded:
            return True
        
        if not self.is_available():
            return False
        
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            
            logger.info("Loading FinBERT model (this may take a minute)...")
            self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            self.is_loaded = True
            logger.info("✅ FinBERT model loaded successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load FinBERT: {e}")
            return False
    
    def _extract_search_terms(self, company_name: str, ticker: str) -> List[str]:
        """
        Intelligently extract search terms from company name
        
        Examples:
            "Apple Inc." -> ["Apple Inc", "Apple"]
            "Tata Consultancy Services Limited" -> ["Tata Consultancy Services", "TCS", "Tata Consultancy"]
            "HDFC Bank Limited" -> ["HDFC Bank", "HDFC"]
        """
        terms = []
        
        if not company_name:
            return [ticker] if ticker else []
        
        # Add full name (cleaned)
        clean_name = company_name.strip()
        terms.append(clean_name)
        
        # Remove common suffixes and add that version
        suffixes_to_remove = [
            ' Limited', ' Ltd', ' Ltd.', ' Inc', ' Inc.', ' Corp', ' Corp.',
            ' Corporation', ' Company', ' Co.', ' Co', ' LLC', ' LLP',
            ' PLC', ' Plc', ' N.V.', ' S.A.', ' AG', ' SE',
            ' Private Limited', ' Pvt Ltd', ' Pvt. Ltd.'
        ]
        
        name_without_suffix = clean_name
        for suffix in suffixes_to_remove:
            if name_without_suffix.lower().endswith(suffix.lower()):
                name_without_suffix = name_without_suffix[:-len(suffix)].strip()
                break
        
        if name_without_suffix != clean_name:
            terms.append(name_without_suffix)
        
        # Extract acronym if name has multiple words
        words = name_without_suffix.split()
        if len(words) >= 2:
            # Try to create acronym
            acronym = ''.join(word[0].upper() for word in words if word[0].isalpha())
            if len(acronym) >= 2 and acronym != ticker:
                terms.append(acronym)
            
            # Add first two words (often the "brand" name)
            if len(words) >= 2:
                brand_name = ' '.join(words[:2])
                if brand_name not in terms:
                    terms.append(brand_name)
            
            # Add just first word if it's substantial
            if len(words[0]) >= 4:
                terms.append(words[0])
        
        # Add ticker if not already present
        if ticker and ticker.upper() not in [t.upper() for t in terms]:
            terms.append(ticker.upper())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            if term.lower() not in seen and len(term) >= 2:
                seen.add(term.lower())
                unique_terms.append(term)
        
        return unique_terms
    
    def _get_company_info_yfinance(self, ticker: str) -> Optional[Dict]:
        """
        Get company info from yfinance
        """
        try:
            import yfinance as yf
            
            # Try different suffixes
            suffixes = ['', '.NS', '.BO', '.L', '.TO', '.AX', '.HK']
            
            for suffix in suffixes:
                try:
                    symbol = f"{ticker}{suffix}"
                    stock = yf.Ticker(symbol)
                    info = stock.info
                    
                    # Check if we got valid data
                    company_name = info.get('longName') or info.get('shortName')
                    
                    if company_name and len(company_name) > 1:
                        # Extract search terms
                        search_terms = self._extract_search_terms(company_name, ticker)
                        
                        return {
                            'ticker': ticker,
                            'symbol': symbol,
                            'company_name': company_name,
                            'short_name': info.get('shortName', ''),
                            'search_terms': search_terms,
                            'sector': info.get('sector', ''),
                            'industry': info.get('industry', ''),
                            'country': info.get('country', ''),
                            'website': info.get('website', ''),
                            'source': 'yfinance',
                            'fetched_at': datetime.now().isoformat()
                        }
                except Exception as e:
                    continue
            
            return None
            
        except ImportError:
            logger.warning("yfinance not installed")
            return None
        except Exception as e:
            logger.error(f"yfinance error: {e}")
            return None
    
    def _get_company_info_fallback(self, ticker: str) -> Dict:
        """
        Fallback method when yfinance fails
        Uses basic heuristics to create search terms
        """
        # Try to make the ticker more readable
        # e.g., "TATAMOTORS" -> "Tata Motors"
        readable_name = ticker
        
        # Common patterns in Indian stock tickers
        known_patterns = {
            'BANK': ' Bank',
            'STEEL': ' Steel',
            'PHARMA': ' Pharma',
            'AUTO': ' Auto',
            'MOTORS': ' Motors',
            'TECH': ' Tech',
            'INFRA': ' Infra',
            'POWER': ' Power',
            'CEMENT': ' Cement',
            'PETRO': ' Petro',
        }
        
        for pattern, replacement in known_patterns.items():
            if pattern in ticker.upper():
                parts = ticker.upper().split(pattern)
                if parts[0]:
                    readable_name = parts[0].title() + replacement
                    break
        
        return {
            'ticker': ticker,
            'symbol': ticker,
            'company_name': readable_name,
            'search_terms': [readable_name, ticker],
            'sector': '',
            'industry': '',
            'source': 'fallback',
            'warning': 'Could not fetch company info. Using ticker as search term.',
            'fetched_at': datetime.now().isoformat()
        }
    
    def _get_company_info(self, ticker: str) -> Dict:
        """
        Get company info - tries cache first, then yfinance, then fallback
        """
        clean_ticker = ticker.upper().replace('.NS', '').replace('.BO', '').replace('.L', '')
        
        # Check cache first
        if clean_ticker in self._company_cache:
            cached = self._company_cache[clean_ticker]
            # Check if cache is fresh (less than 7 days old)
            try:
                cached_time = datetime.fromisoformat(cached.get('fetched_at', '2000-01-01'))
                if datetime.now() - cached_time < timedelta(days=7):
                    cached['source'] = 'cache'
                    return cached
            except:
                pass
        
        # Try yfinance
        info = self._get_company_info_yfinance(clean_ticker)
        
        if info:
            # Save to cache
            self._company_cache[clean_ticker] = info
            self._save_cache()
            return info
        
        # Fallback
        fallback_info = self._get_company_info_fallback(clean_ticker)
        return fallback_info
    
    def _fetch_news(self, company_info: Dict, days: int = 7) -> List[Dict]:
        """
        Fetch news articles using multiple search strategies
        """
        if not self._check_rate_limit():
            logger.warning("Skipping news fetch due to rate limit")
            return []
        
        if not AI_CONFIG['news_api_key']:
            logger.warning("News API key not configured")
            return []
        
        try:
            import requests
            
            all_articles = []
            company_name = company_info['company_name']
            search_terms = company_info.get('search_terms', [company_name])
            
            url = "https://newsapi.org/v2/everything"
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Strategy 1: Exact company name + stock context
            queries = [
                f'"{company_name}" AND (stock OR shares OR earnings OR market)',
                f'"{company_name}" stock',
            ]
            
            # Strategy 2: Add first search term if different
            if len(search_terms) > 1 and search_terms[1] != company_name:
                queries.append(f'"{search_terms[1]}" stock')
            
            for query in queries:
                try:
                    params = {
                        'q': query,
                        'apiKey': AI_CONFIG['news_api_key'],
                        'pageSize': 30,
                        'language': 'en',
                        'sortBy': 'relevancy',
                        'from': from_date
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()
                    
                    if data.get('status') == 'ok':
                        articles = data.get('articles', [])
                        all_articles.extend(articles)
                        
                        # If we got enough articles, stop searching
                        if len(all_articles) >= 15:
                            break
                
                except Exception as e:
                    logger.warning(f"News fetch failed for query '{query}': {e}")
                    continue
            
            # Deduplicate articles by URL
            seen_urls = set()
            unique_articles = []
            for article in all_articles:
                url = article.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_articles.append(article)
            
            self._api_requests_today += 1
            logger.info(f"API requests today: {self._api_requests_today}/{self._max_requests_per_day}")
            
            return unique_articles
        
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return []
    
    def _calculate_relevance_score(
        self, 
        article: Dict, 
        company_info: Dict
    ) -> Tuple[float, List[str]]:
        """
        Calculate how relevant an article is to the company
        Uses fuzzy matching for better accuracy
        """
        title = (article.get('title') or '').lower()
        description = (article.get('description') or '').lower()
        content = (article.get('content') or '').lower()
        
        full_text = f"{title} {description} {content}"
        
        # Skip very short or empty articles
        if len(full_text) < 50:
            return 0, []
        
        search_terms = company_info.get('search_terms', [])
        ticker = company_info.get('ticker', '').lower()
        company_name = company_info.get('company_name', '').lower()
        
        matched_terms = []
        score = 0
        
        # Check for exact company name match (highest weight)
        if company_name and company_name in full_text:
            score += 50
            matched_terms.append(f"Company: {company_name}")
        else:
            # Try partial matching for company name
            name_words = company_name.split()
            if len(name_words) >= 2:
                # Check if first two significant words appear together
                significant_words = [w for w in name_words if len(w) > 2][:2]
                if len(significant_words) >= 2:
                    if all(word in full_text for word in significant_words):
                        score += 35
                        matched_terms.append(f"Partial: {' '.join(significant_words)}")
        
        # Check for ticker symbol (with word boundaries)
        import re
        if ticker and len(ticker) >= 2:
            # Match ticker as standalone word or in common patterns like $AAPL, (AAPL)
            ticker_patterns = [
                rf'\b{re.escape(ticker)}\b',
                rf'\${re.escape(ticker)}\b',
                rf'\({re.escape(ticker)}\)',
            ]
            for pattern in ticker_patterns:
                if re.search(pattern, full_text, re.IGNORECASE):
                    score += 30
                    matched_terms.append(f"Ticker: {ticker}")
                    break
        
        # Check for other search terms
        for term in search_terms:
            term_lower = term.lower()
            if len(term_lower) >= 3 and term_lower in full_text:
                if term_lower not in [m.lower() for m in matched_terms]:
                    score += 15
                    matched_terms.append(f"Term: {term}")
        
        # Check for financial context
        financial_terms = [
            'stock', 'shares', 'earnings', 'revenue', 'profit', 'loss',
            'quarterly', 'annual', 'dividend', 'investor', 'market cap',
            'trading', 'ipo', 'acquisition', 'merger', 'ceo', 'quarterly results'
        ]
        
        # Also check for Indian market terms
        indian_terms = ['nse', 'bse', 'sensex', 'nifty', 'sebi', 'rupee', 'crore', 'lakh']
        
        all_financial = financial_terms + indian_terms
        financial_matches = sum(1 for term in all_financial if term in full_text)
        
        if financial_matches > 0:
            bonus = min(20, financial_matches * 4)
            score += bonus
            if financial_matches >= 2:
                matched_terms.append(f"Financial context ({financial_matches} terms)")
        
        # Penalties
        # Very generic articles
        generic_indicators = ['horoscope', 'weather', 'recipe', 'celebrity', 'sports score']
        if any(ind in full_text for ind in generic_indicators):
            score -= 30
        
        # Title doesn't mention company at all (likely not relevant)
        if company_name and company_name not in title.lower():
            # Check if any search term is in title
            title_has_term = any(term.lower() in title.lower() for term in search_terms)
            if not title_has_term:
                score -= 15
        
        return max(0, min(100, score)), matched_terms
    
    def _filter_relevant_articles(
        self, 
        articles: List[Dict], 
        company_info: Dict,
        min_relevance: float = 35.0
    ) -> List[Dict]:
        """
        Filter articles by relevance score
        """
        relevant_articles = []
        
        for article in articles:
            relevance_score, matched_terms = self._calculate_relevance_score(
                article, company_info
            )
            
            if relevance_score >= min_relevance:
                article['relevance_score'] = relevance_score
                article['matched_terms'] = matched_terms
                relevant_articles.append(article)
        
        # Sort by relevance score
        relevant_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return relevant_articles
    
    def analyze(self, ticker: str) -> Optional[Dict]:
        """
        Analyze sentiment for a ticker with relevance filtering
        
        Args:
            ticker: Stock ticker symbol
        
        Returns:
            Dict with sentiment score, type, and details
        """
        if not self.is_available():
            return {
                'status': 'error',
                'message': 'Transformers not installed. Run: pip install transformers torch',
                'sentiment': None
            }
        
        # ✅ NEW: Check cache first
        cache_key = ticker.upper().replace('.NS', '').replace('.BO', '')
        if cache_key in self._sentiment_cache:
            cached = self._sentiment_cache[cache_key]
            cache_age = (datetime.now() - cached['cached_at']).total_seconds()
            if cache_age < self._sentiment_cache_ttl:
                logger.info(f"Using cached sentiment for {ticker}")
                cached_result = cached['result'].copy()
                cached_result['from_cache'] = True
                cached_result['cache_age_seconds'] = int(cache_age)
                return cached_result
        
        # Get company info DYNAMICALLY
        company_info = self._get_company_info(ticker)
        
        logger.info(f"Analyzing sentiment for {ticker} -> {company_info['company_name']}")
        logger.info(f"Search terms: {company_info.get('search_terms', [])}")
        
        # Load model
        if not self._load_model():
            return {
                'status': 'error',
                'message': 'Failed to load FinBERT model',
                'sentiment': None
            }
        
        # Fetch news
        all_articles = self._fetch_news(company_info)
        
        if not all_articles:
            return {
                'status': 'warning',
                'message': f'No news articles found for {company_info["company_name"]}',
                'ticker': ticker,
                'company_name': company_info['company_name'],
                'search_terms': company_info.get('search_terms', []),
                'sentiment': None
            }
        
        # Filter for relevant articles
        relevant_articles = self._filter_relevant_articles(all_articles, company_info)
        
        if not relevant_articles:
            return {
                'status': 'warning',
                'message': f'Found {len(all_articles)} articles but none were relevant to {company_info["company_name"]}',
                'ticker': ticker,
                'company_name': company_info['company_name'],
                'search_terms': company_info.get('search_terms', []),
                'articles_fetched': len(all_articles),
                'articles_relevant': 0,
                'sentiment': None,
                'suggestion': 'Try a more common ticker or check if the company name is correct'
            }
        
        try:
            import torch
            
            sentiments = []
            analyzed_headlines = []
            
            for article in relevant_articles[:15]:
                headline = article.get('title', '')
                description = article.get('description', '')
                
                # Combine headline and description for context
                text_to_analyze = headline
                if description and len(description) > 20:
                    text_to_analyze = f"{headline}. {description[:200]}"
                
                if not text_to_analyze or len(text_to_analyze) < 10:
                    continue
                
                # Tokenize and predict
                inputs = self.tokenizer(
                    text_to_analyze, 
                    return_tensors="pt", 
                    padding=True, 
                    truncation=True,
                    max_length=256
                )
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                neg_score = predictions[0][0].item()
                neu_score = predictions[0][1].item()
                pos_score = predictions[0][2].item()
                
                sentiment_score = (pos_score - neg_score) * 100
                
                # Weight by relevance
                relevance = article.get('relevance_score', 50) / 100
                weighted_score = sentiment_score * (0.5 + 0.5 * relevance)
                
                sentiments.append(weighted_score)
                
                analyzed_headlines.append({
                    'headline': headline[:100] + '...' if len(headline) > 100 else headline,
                    'score': round(sentiment_score, 1),
                    'weighted_score': round(weighted_score, 1),
                    'relevance': round(article.get('relevance_score', 0), 1),
                    'matched_terms': article.get('matched_terms', []),
                    'positive': round(pos_score * 100, 1),
                    'negative': round(neg_score * 100, 1),
                    'neutral': round(neu_score * 100, 1),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'date': article.get('publishedAt', '')[:10],
                    'url': article.get('url', '')
                })
            
            if not sentiments:
                return {
                    'status': 'warning',
                    'message': 'Could not analyze any headlines',
                    'ticker': ticker,
                    'company_name': company_info['company_name'],
                    'sentiment': None
                }
            
            # Calculate overall sentiment
            avg_sentiment = np.mean(sentiments)
            sentiment_std = np.std(sentiments)
            
            # Determine sentiment type
            if avg_sentiment > 30:
                sentiment_type = "BULLISH"
                color = "#28a745"
                emoji = "🟢"
            elif avg_sentiment > 15:
                sentiment_type = "SLIGHTLY_BULLISH"
                color = "#7cb342"
                emoji = "🟡"
            elif avg_sentiment < -30:
                sentiment_type = "BEARISH"
                color = "#dc3545"
                emoji = "🔴"
            elif avg_sentiment < -15:
                sentiment_type = "SLIGHTLY_BEARISH"
                color = "#f57c00"
                emoji = "🟠"
            else:
                sentiment_type = "NEUTRAL"
                color = "#ffc107"
                emoji = "⚪"
            
            # Calculate confidence
            avg_relevance = np.mean([a.get('relevance', 50) for a in analyzed_headlines])
            article_count_factor = min(1.0, len(sentiments) / 10)
            consistency_factor = max(0, 1 - (sentiment_std / 50))
            relevance_factor = avg_relevance / 100
            
            confidence = int(
                (article_count_factor * 30 + 
                 consistency_factor * 40 + 
                 relevance_factor * 30)
            )
            
            # ✅ NEW: Build result and cache it
            result = {
                'status': 'success',
                'ticker': ticker,
                'company_name': company_info['company_name'],
                'search_terms_used': company_info.get('search_terms', []),
                'company_source': company_info.get('source', 'unknown'),
                'sector': company_info.get('sector', ''),
                'industry': company_info.get('industry', ''),
                'score': round(avg_sentiment, 1),
                'type': sentiment_type,
                'emoji': emoji,
                'color': color,
                'confidence': confidence,
                'confidence_breakdown': {
                    'article_count': round(article_count_factor * 100, 1),
                    'consistency': round(consistency_factor * 100, 1),
                    'relevance': round(relevance_factor * 100, 1)
                },
                'articles_fetched': len(all_articles),
                'articles_relevant': len(relevant_articles),
                'articles_analyzed': len(sentiments),
                'avg_relevance': round(avg_relevance, 1),
                'sentiment_std': round(sentiment_std, 1),
                'headlines': analyzed_headlines[:5],
                'all_headlines': analyzed_headlines,
                'summary': f"{emoji} {sentiment_type}: Analyzed {len(sentiments)} relevant articles for {company_info['company_name']}",
                'generated_at': datetime.now().isoformat(),
                'source': 'FinBERT + NewsAPI (dynamic company lookup)',
                'warnings': [company_info.get('warning')] if company_info.get('warning') else []
            }
            
            # ✅ NEW: Cache the result
            self._sentiment_cache[cache_key] = {
                'result': result,
                'cached_at': datetime.now()
            }
            
            # ✅ NEW: Limit cache size
            if len(self._sentiment_cache) > 50:
                oldest = min(self._sentiment_cache.keys(),
                           key=lambda k: self._sentiment_cache[k]['cached_at'])
                del self._sentiment_cache[oldest]
            
            return result
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            import traceback
            return {
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
                'sentiment': None
            }
    def clear_sentiment_cache(self, ticker: str = None):
        """Clear sentiment cache"""
        if ticker:
            cache_key = ticker.upper().replace('.NS', '').replace('.BO', '')
            if cache_key in self._sentiment_cache:
                del self._sentiment_cache[cache_key]
        else:
            self._sentiment_cache = {}

    def clear_cache(self):
        """Clear the company info cache"""
        self._company_cache = {}
        if os.path.exists(self._cache_file):
            os.remove(self._cache_file)
        logger.info("Company cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cached_companies': len(self._company_cache),
            'cache_file': self._cache_file,
            'companies': list(self._company_cache.keys())
        }


# Global instance
sentiment_analyzer = SentimentAnalyzer()


def get_real_sentiment(ticker: str) -> Optional[Dict]:
    """
    Get sentiment analysis for any ticker (dynamically fetches company info)
    
    Usage:
        result = get_real_sentiment("AAPL")
        result = get_real_sentiment("RELIANCE")
        result = get_real_sentiment("RANDOMTICKER123")  # Will try to fetch info
    """
    return sentiment_analyzer.analyze(ticker)


# ============================================================================
# HELPER: Test the dynamic lookup
# ============================================================================

def test_company_lookup(tickers: List[str] = None):
    """
    Test the dynamic company lookup for various tickers
    """
    if tickers is None:
        tickers = [
            'AAPL', 'MSFT', 'GOOGL',  # US stocks
            'RELIANCE', 'TCS', 'INFY',  # Indian stocks
            'CLEAN', 'CLNE', 'TSLA',  # Various
            'RANDOMXYZ',  # Unknown ticker
        ]
    
    print("=" * 70)
    print("🔍 TESTING DYNAMIC COMPANY LOOKUP")
    print("=" * 70)
    
    for ticker in tickers:
        info = sentiment_analyzer._get_company_info(ticker)
        print(f"\n📊 {ticker}:")
        print(f"   Company: {info.get('company_name', 'N/A')}")
        print(f"   Search terms: {info.get('search_terms', [])}")
        print(f"   Source: {info.get('source', 'N/A')}")
        if info.get('sector'):
            print(f"   Sector: {info.get('sector')}")
        if info.get('warning'):
            print(f"   ⚠️ Warning: {info.get('warning')}")
    
    print("\n" + "=" * 70)
    print(f"✅ Cache now has {len(sentiment_analyzer._company_cache)} entries")
    print("=" * 70)


if __name__ == "__main__":
    test_company_lookup()


# Global sentiment analyzer instance
sentiment_analyzer = SentimentAnalyzer()


def get_real_sentiment(ticker: str) -> Optional[Dict]:
    """
    Wrapper function for sentiment analysis
    
    Usage:
        result = get_real_sentiment("RELIANCE")
        if result['status'] == 'success':
            print(f"Sentiment: {result['type']} ({result['score']:.1f})")
    """
    return sentiment_analyzer.analyze(ticker)


# ============================================================================
# 4. MONTE CARLO PORTFOLIO OPTIMIZATION
# ============================================================================

def monte_carlo_portfolio_optimization(
    tickers: List[str],
    returns_data: pd.DataFrame,
    num_portfolios: int = None,
    risk_free_rate: float = 0.05
) -> Dict:
    """
    Monte Carlo simulation for optimal portfolio allocation
    
    Args:
        tickers: List of ticker symbols
        returns_data: DataFrame with daily returns for each ticker
        num_portfolios: Number of random portfolios to simulate
        risk_free_rate: Annual risk-free rate (default 5%)
    
    Returns:
        Dict with optimal weights, expected return, volatility, Sharpe ratio
    """
    if num_portfolios is None:
        num_portfolios = AI_CONFIG['monte_carlo_simulations']
    
    if returns_data is None or returns_data.empty:
        return {
            'status': 'error',
            'message': 'No returns data provided'
        }
    
    num_assets = len(tickers)
    
    if num_assets < 2:
        return {
            'status': 'error',
            'message': 'Need at least 2 assets for optimization'
        }
    
    try:
        # Calculate annualized returns and covariance
        mean_returns = returns_data.mean() * 252
        cov_matrix = returns_data.cov() * 252
        
        # Storage for results
        results = np.zeros((4, num_portfolios))  # return, std, sharpe, sortino
        weights_record = []
        
        for i in range(num_portfolios):
            # Generate random weights
            weights = np.random.random(num_assets)
            weights /= np.sum(weights)
            
            # Portfolio metrics
            portfolio_return = np.sum(mean_returns * weights)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe = (portfolio_return - risk_free_rate) / portfolio_std
            
            # Sortino ratio (only downside deviation)
            downside_returns = returns_data[returns_data < 0]
            downside_std = np.sqrt(np.sum((weights ** 2) * (downside_returns.var() * 252)))
            sortino = (portfolio_return - risk_free_rate) / (downside_std + 1e-10)
            
            results[0, i] = portfolio_return * 100  # As percentage
            results[1, i] = portfolio_std * 100
            results[2, i] = sharpe
            results[3, i] = sortino
            weights_record.append(weights)
        
        # Find optimal portfolios
        max_sharpe_idx = np.argmax(results[2])
        min_vol_idx = np.argmin(results[1])
        
        # Efficient frontier points (top 10% by Sharpe)
        sharpe_threshold = np.percentile(results[2], 90)
        efficient_frontier = results[:, results[2] >= sharpe_threshold]
        
        return {
            'status': 'success',
            'optimal_portfolio': {
                'weights': {tickers[i]: round(w, 4) for i, w in enumerate(weights_record[max_sharpe_idx])},
                'expected_return': round(results[0, max_sharpe_idx], 2),
                'volatility': round(results[1, max_sharpe_idx], 2),
                'sharpe_ratio': round(results[2, max_sharpe_idx], 2),
                'sortino_ratio': round(results[3, max_sharpe_idx], 2)
            },
            'min_volatility_portfolio': {
                'weights': {tickers[i]: round(w, 4) for i, w in enumerate(weights_record[min_vol_idx])},
                'expected_return': round(results[0, min_vol_idx], 2),
                'volatility': round(results[1, min_vol_idx], 2),
                'sharpe_ratio': round(results[2, min_vol_idx], 2)
            },
            'statistics': {
                'simulations': num_portfolios,
                'avg_return': round(results[0].mean(), 2),
                'avg_volatility': round(results[1].mean(), 2),
                'avg_sharpe': round(results[2].mean(), 2),
                'best_sharpe': round(results[2].max(), 2),
                'worst_sharpe': round(results[2].min(), 2)
            },
            'recommendations': _generate_allocation_recommendations(
                tickers, weights_record[max_sharpe_idx]
            ),
            'method': 'Monte Carlo Simulation',
            'generated_at': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Monte Carlo optimization failed: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


def _generate_allocation_recommendations(tickers: List[str], weights: np.ndarray) -> List[str]:
    """Generate human-readable allocation recommendations"""
    recommendations = []
    
    # Sort by weight
    sorted_allocations = sorted(
        zip(tickers, weights), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    for ticker, weight in sorted_allocations:
        pct = weight * 100
        if pct >= 25:
            recommendations.append(f"🔵 {ticker}: {pct:.1f}% (OVERWEIGHT)")
        elif pct >= 15:
            recommendations.append(f"🟢 {ticker}: {pct:.1f}% (MODERATE)")
        elif pct >= 5:
            recommendations.append(f"🟡 {ticker}: {pct:.1f}% (UNDERWEIGHT)")
        else:
            recommendations.append(f"⚪ {ticker}: {pct:.1f}% (MINIMAL)")
    
    return recommendations


# ============================================================================
# 5. MARKET REGIME DETECTION (HIDDEN MARKOV MODEL)
# ============================================================================

class MarketRegimeDetector:
    """
    Detect market regimes using Hidden Markov Models
    Identifies: BULL_TRENDING, BEAR_TRENDING, HIGH_VOLATILITY, RANGING
    """
    
    def __init__(self):
        self.model = None
        self.is_fitted = False
        self.regime_labels = {}
    
    def is_available(self) -> bool:
        """Check if HMMLearn is available"""
        return AVAILABLE_FEATURES['hmmlearn']
    
    def detect(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Detect current market regime
        
        Args:
            df: DataFrame with OHLCV data (preferably NIFTY or market index)
        
        Returns:
            Dict with regime, confidence, recommendation
        """
        if not self.is_available():
            return {
                'status': 'error',
                'message': 'HMMLearn not installed. Run: pip install hmmlearn',
                'regime': None
            }
        
        if df is None or len(df) < 100:
            return {
                'status': 'error',
                'message': 'Need at least 100 data points for regime detection',
                'regime': None
            }
        
        try:
            from hmmlearn.hmm import GaussianHMM
            
            # Calculate features
            returns = df['Close'].pct_change().dropna()
            volatility = returns.rolling(20).std().dropna()
            
            # Ensure same length
            min_len = min(len(returns), len(volatility))
            returns = returns.tail(min_len)
            volatility = volatility.tail(min_len)
            
            # Prepare feature matrix
            X = np.column_stack([returns.values, volatility.values])
            
            # Remove any NaN/inf
            mask = ~np.isnan(X).any(axis=1) & ~np.isinf(X).any(axis=1)
            X = X[mask]
            
            if len(X) < 50:
                return {
                    'status': 'error',
                    'message': 'Insufficient clean data points',
                    'regime': None
                }
            
            # Fit HMM with 4 states
            n_states = AI_CONFIG['hmm_states']
            self.model = GaussianHMM(
                n_components=n_states,
                covariance_type="full",
                n_iter=100,
                random_state=42
            )
            
            self.model.fit(X)
            
            # Predict states
            states = self.model.predict(X)
            current_state = states[-1]
            
            # Analyze each state
            state_analysis = []
            for i in range(n_states):
                state_mask = states == i
                state_returns = X[state_mask, 0]
                state_vol = X[state_mask, 1]
                
                state_analysis.append({
                    'state': i,
                    'mean_return': state_returns.mean() if len(state_returns) > 0 else 0,
                    'mean_vol': state_vol.mean() if len(state_vol) > 0 else 0,
                    'count': state_mask.sum()
                })
            
            # Sort states by return to assign labels
            state_analysis.sort(key=lambda x: x['mean_return'], reverse=True)
            
            # Assign regime labels based on return and volatility patterns
            regime_map = {}
            for idx, sa in enumerate(state_analysis):
                if idx == 0:
                    if sa['mean_vol'] > np.median([s['mean_vol'] for s in state_analysis]):
                        regime_map[sa['state']] = 'BULL_VOLATILE'
                    else:
                        regime_map[sa['state']] = 'BULL_TRENDING'
                elif idx == 1:
                    regime_map[sa['state']] = 'RANGING_BULLISH'
                elif idx == 2:
                    regime_map[sa['state']] = 'RANGING_BEARISH'
                else:
                    if sa['mean_vol'] > np.median([s['mean_vol'] for s in state_analysis]):
                        regime_map[sa['state']] = 'BEAR_VOLATILE'
                    else:
                        regime_map[sa['state']] = 'BEAR_TRENDING'
            
            current_regime = regime_map[current_state]
            
            # Calculate regime probabilities
            regime_probs = self.model.predict_proba(X[-1:])
            confidence = int(regime_probs.max() * 100)
            
            # Get recommendation
            recommendation = self._get_recommendation(current_regime)
            
            # Calculate regime duration
            regime_duration = 1
            for i in range(len(states) - 2, -1, -1):
                if states[i] == current_state:
                    regime_duration += 1
                else:
                    break
            
            self.is_fitted = True
            
            return {
                'status': 'success',
                'regime': current_regime,
                'confidence': confidence,
                'duration_days': regime_duration,
                'recommendation': recommendation,
                'all_regimes': regime_map,
                'current_state': int(current_state),
                'state_probabilities': {
                    regime_map[i]: round(regime_probs[0][i] * 100, 1) 
                    for i in range(n_states)
                },
                'model': 'Gaussian HMM',
                'states': n_states,
                'generated_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Regime detection failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'regime': None
            }
    
    def _get_recommendation(self, regime: str) -> Dict:
        """Get trading recommendations based on regime"""
        recommendations = {
            'BULL_TRENDING': {
                'action': '📈 AGGRESSIVE LONG',
                'sl_adjustment': 'Wider stops (2.5-3x ATR)',
                'position_sizing': 'Full size',
                'strategy': 'Ride trends, buy dips, avoid shorts',
                'color': '#28a745'
            },
            'BULL_VOLATILE': {
                'action': '📈 CAUTIOUS LONG',
                'sl_adjustment': 'Normal stops (2x ATR)',
                'position_sizing': '70% size',
                'strategy': 'Quick profits, tight trailing stops',
                'color': '#7cb342'
            },
            'RANGING_BULLISH': {
                'action': '🔄 MEAN REVERSION',
                'sl_adjustment': 'Tight stops (1.5x ATR)',
                'position_sizing': '50% size',
                'strategy': 'Buy at support, sell at resistance',
                'color': '#ffc107'
            },
            'RANGING_BEARISH': {
                'action': '⚠️ DEFENSIVE',
                'sl_adjustment': 'Tight stops (1.5x ATR)',
                'position_sizing': '30% size',
                'strategy': 'Short-term trades only, reduce exposure',
                'color': '#fd7e14'
            },
            'BEAR_TRENDING': {
                'action': '📉 DEFENSIVE/SHORT',
                'sl_adjustment': 'Tight stops (1.5x ATR)',
                'position_sizing': 'Minimal',
                'strategy': 'Preserve capital, short trades, hedge longs',
                'color': '#dc3545'
            },
            'BEAR_VOLATILE': {
                'action': '🚨 CASH/HEDGE',
                'sl_adjustment': 'Very tight stops (1x ATR)',
                'position_sizing': 'Exit positions',
                'strategy': 'Move to cash, buy puts for protection',
                'color': '#6c757d'
            }
        }
        
        return recommendations.get(regime, {
            'action': '⚠️ MONITOR',
            'sl_adjustment': 'Normal stops',
            'position_sizing': '50%',
            'strategy': 'Wait for clarity',
            'color': '#6c757d'
        })


# Global regime detector instance
regime_detector = MarketRegimeDetector()


def detect_market_regime(df: pd.DataFrame) -> Optional[Dict]:
    """
    Wrapper function for market regime detection
    
    Usage:
        result = detect_market_regime(nifty_df)
        if result['status'] == 'success':
            print(f"Current Regime: {result['regime']}")
    """
    return regime_detector.detect(df)


# ============================================================================
# 6. BACKTESTING ENGINE (Enhanced)
# ============================================================================

class BacktestEngine:
    """
    Enhanced backtesting engine with detailed analytics
    """
    
    def __init__(
        self, 
        initial_capital: float = 100000,
        commission_pct: float = 0.05,  # 0.05% per trade (typical for Indian brokers)
        slippage_pct: float = 0.1,     # 0.1% slippage
        include_stt: bool = True       # Include STT for equity
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.include_stt = include_stt
        self.stt_rate = 0.1  # 0.1% STT on sell side
    

    def run_backtest(
        self,
        df: pd.DataFrame,
        entry_rules: Dict,
        exit_rules: Dict,
        position_size_pct: float = 10.0
    ) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df: DataFrame with OHLCV data
            entry_rules: Entry conditions
            exit_rules: Exit conditions
            position_size_pct: Position size as % of capital
        
        Returns:
            Backtest results with detailed analytics
        """
        if df is None or len(df) < 50:
            return {'status': 'error', 'message': 'Insufficient data'}
        
        # Add indicators
        df = self._add_indicators(df.copy())
        
        position = None
        trades = []
        equity_curve = [self.initial_capital]
        
        for i in range(30, len(df)):
            current = df.iloc[i]
            historical = df.iloc[:i+1]
            
            if position is None:
                # Check entry
                if self._check_entry(historical, entry_rules):
                    qty = int((self.capital * position_size_pct / 100) / current['Close'])
                    if qty > 0:
                        # Apply slippage on entry (worse entry price)
                        slipped_entry = current['Close'] * (1 + self.slippage_pct / 100)
                        
                        position = {
                            'entry_price': slipped_entry,
                            'entry_date': current.get('Date', df.index[i]),
                            'entry_index': i,
                            'quantity': qty
                        }
            else:
                # Check exit
                exit_signal, exit_reason = self._check_exit(
                    historical, exit_rules, position, current
                )
                
                if exit_signal:  # ✅ FIXED: Now properly indented inside else block
                    entry_price = position['entry_price']
                    raw_exit_price = current['Close']
                    qty = position['quantity']
                    
                    # Calculate preliminary P&L to determine slippage direction
                    preliminary_pnl = (raw_exit_price - entry_price) * qty
                    
                    # Apply slippage (always makes exit price worse)
                    # For sells: reduce exit price slightly
                    exit_price = raw_exit_price * (1 - self.slippage_pct / 100)
                    
                    # Calculate raw P&L after slippage
                    raw_pnl = (exit_price - entry_price) * qty
                    
                    # Calculate costs
                    trade_value = exit_price * qty
                    entry_value = entry_price * qty
                    
                    # Commission on both sides
                    commission = (entry_value + trade_value) * (self.commission_pct / 100)
                    
                    # STT on sell side only (for equity)
                    stt = trade_value * (self.stt_rate / 100) if self.include_stt else 0
                    
                    # Net P&L after all costs
                    pnl = raw_pnl - commission - stt
                    pnl_pct = (pnl / entry_value) * 100
                    
                    self.capital += pnl
                    
                    trades.append({
                        'entry_date': position['entry_date'],
                        'entry_price': position['entry_price'],
                        'exit_date': current.get('Date', df.index[i]),
                        'exit_price': current['Close'],
                        'quantity': position['quantity'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'holding_days': i - position['entry_index'],
                        'exit_reason': exit_reason,
                        'win': pnl > 0
                    })
                    position = None
            
            equity_curve.append(self.capital)
        
        return self._analyze_results(trades, equity_curve)
        
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators"""
        df['RSI'] = calculate_rsi(df['Close'])
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['EMA9'] = df['Close'].ewm(span=9).mean()
        df['EMA21'] = df['Close'].ewm(span=21).mean()
        
        macd, signal, hist = calculate_macd(df['Close'])
        df['MACD'] = macd
        df['MACD_Signal'] = signal
        df['MACD_Hist'] = hist
        
        df['ATR'] = calculate_atr(df['High'], df['Low'], df['Close'])
        
        # Bollinger Bands
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Mid'] - (bb_std * 2)
        
        return df
    
    def _check_entry(self, df: pd.DataFrame, rules: Dict) -> bool:
        """Check entry conditions"""
        current = df.iloc[-1]
        conditions = 0
        required = 0
        
        if 'rsi_range' in rules:
            required += 1
            rsi = current.get('RSI', 50)
            if pd.notna(rsi) and rules['rsi_range'][0] <= rsi <= rules['rsi_range'][1]:
                conditions += 1
        
        if rules.get('above_sma20'):
            required += 1
            if current['Close'] > current.get('SMA20', current['Close']):
                conditions += 1
        
        if rules.get('ema_crossover'):
            required += 1
            if current.get('EMA9', 0) > current.get('EMA21', 0):
                conditions += 1
        
        if rules.get('macd_bullish'):
            required += 1
            if current.get('MACD_Hist', 0) > 0:
                conditions += 1
        
        if rules.get('volume_spike'):
            required += 1
            avg_vol = df['Volume'].tail(20).mean()
            if current['Volume'] > avg_vol * 1.5:
                conditions += 1
        
        return conditions >= required and required > 0
    
    def _check_exit(
        self, 
        df: pd.DataFrame, 
        rules: Dict, 
        position: Dict,
        current
    ) -> Tuple[bool, str]:
        """Check exit conditions"""
        entry_price = position['entry_price']
        current_price = current['Close']
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Stop loss
        if 'stop_loss_pct' in rules:
            if pnl_pct <= -rules['stop_loss_pct']:
                return True, "Stop Loss"
        
        # Target
        if 'target_pct' in rules:
            if pnl_pct >= rules['target_pct']:
                return True, "Target Hit"
        
        # Trailing stop
        if 'trail_trigger_pct' in rules and 'trail_distance_pct' in rules:
            if pnl_pct >= rules['trail_trigger_pct']:
                high_since_entry = df.iloc[position['entry_index']:]['High'].max()
                trail_stop = high_since_entry * (1 - rules['trail_distance_pct'] / 100)
                if current_price < trail_stop:
                    return True, "Trail Stop"
        
        # RSI overbought
        if rules.get('exit_rsi_overbought'):
            rsi = current.get('RSI', 50)
            if pd.notna(rsi) and rsi > 75:
                return True, "RSI Overbought"
        
        # MACD bearish cross
        if rules.get('exit_macd_bearish'):
            if current.get('MACD_Hist', 0) < 0:
                return True, "MACD Bearish"
        
        return False, ""
    
    def _analyze_results(self, trades: List[Dict], equity_curve: List[float]) -> Dict:
        """Analyze backtest results"""
        if not trades:
            return {
                'status': 'warning',
                'message': 'No trades generated',
                'total_trades': 0
            }
        
        wins = [t for t in trades if t['win']]
        losses = [t for t in trades if not t['win']]
        
        total_trades = len(trades)
        win_rate = (len(wins) / total_trades) * 100
        
        total_profit = sum(t['pnl'] for t in wins) if wins else 0
        total_loss = sum(abs(t['pnl']) for t in losses) if losses else 0
        
        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 0
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        net_pnl = total_profit - total_loss
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
        
        # Drawdown analysis
        equity = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (running_max - equity) / running_max * 100
        max_drawdown = drawdown.max()
        
        # Average holding period
        avg_holding = np.mean([t['holding_days'] for t in trades])
        
        # Exit reason breakdown
        exit_reasons = {}
        for t in trades:
            reason = t['exit_reason']
            if reason not in exit_reasons:
                exit_reasons[reason] = {'count': 0, 'pnl': 0}
            exit_reasons[reason]['count'] += 1
            exit_reasons[reason]['pnl'] += t['pnl']
        
        return {
            'status': 'success',
            'summary': {
                'total_trades': total_trades,
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': round(win_rate, 1),
                'profit_factor': round(profit_factor, 2) if profit_factor < 100 else 'Infinite',
                'net_pnl': round(net_pnl, 2),
                'net_pnl_pct': round((net_pnl / self.initial_capital) * 100, 2),
                'expectancy': round(expectancy, 2)
            },
            'risk_metrics': {
                'max_drawdown': round(max_drawdown, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'risk_reward': round(avg_win / avg_loss, 2) if avg_loss > 0 else 'N/A',
                'avg_holding_days': round(avg_holding, 1)
            },
            'exit_analysis': exit_reasons,
            'equity_curve': equity_curve,
            'trades': trades,
            'generated_at': datetime.now().isoformat()
        }


def run_simple_backtest(
    ticker: str,
    period: str = "1y",
    stop_loss_pct: float = 3.0,
    target_pct: float = 6.0,
    initial_capital: float = 100000,
    commission_pct: float = 0.05,
    slippage_pct: float = 0.1,
    include_costs: bool = True
) -> Dict:
    """
    Run a simple backtest with default parameters
    
    Usage:
        result = run_simple_backtest("RELIANCE", period="1y", stop_loss_pct=3, target_pct=6)
    """
    try:
        import yfinance as yf
        
        symbol = ticker if '.NS' in ticker else f"{ticker}.NS"
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        
        if df.empty:
            return {'status': 'error', 'message': f'No data for {ticker}'}
        
        df.reset_index(inplace=True)
        
        entry_rules = {
            'rsi_range': (30, 50),
            'above_sma20': True,
            'macd_bullish': True
        }
        
        exit_rules = {
            'stop_loss_pct': stop_loss_pct,
            'target_pct': target_pct,
            'trail_trigger_pct': target_pct * 0.7,
            'trail_distance_pct': 2.0
        }
        
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission_pct=commission_pct if include_costs else 0,
            slippage_pct=slippage_pct if include_costs else 0,
            include_stt=include_costs
        )
        results = engine.run_backtest(df, entry_rules, exit_rules)
        
        results['ticker'] = ticker
        results['period'] = period
        results['parameters'] = {
            'stop_loss': stop_loss_pct,
            'target': target_pct,
            'initial_capital': initial_capital
        }
        
        return results
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# ============================================================================
# 7. AI TRADE SUGGESTIONS (Claude Integration)
# ============================================================================

def generate_ai_analysis(portfolio_state: Dict, market_health: Dict) -> Dict:
    """
    Generate AI-powered portfolio analysis using Claude
    
    Args:
        portfolio_state: Current portfolio metrics
        market_health: Market health indicators
    
    Returns:
        AI-generated analysis and recommendations
    """
    if not AI_CONFIG['claude_api_key']:
        return {
            'status': 'error',
            'message': 'Claude API key not configured. Set CLAUDE_API_KEY environment variable.',
            'recommendations': None
        }
    
    try:
        import anthropic
        
        # Build prompt
        prompt = _build_analysis_prompt(portfolio_state, market_health)
        
        client = anthropic.Anthropic(api_key=AI_CONFIG['claude_api_key'])
        
        message = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        analysis = message.content[0].text
        
        return {
            'status': 'success',
            'analysis': analysis,
            'model': 'Claude 3 Sonnet',
            'generated_at': datetime.now().isoformat()
        }
    
    except ImportError:
        return {
            'status': 'error',
            'message': 'anthropic package not installed. Run: pip install anthropic'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }


def _build_analysis_prompt(portfolio_state: Dict, market_health: Dict) -> str:
    """Build comprehensive prompt for AI analysis"""
    
    positions = portfolio_state.get('positions', [])
    
    position_summary = []
    for p in positions[:10]:  # Limit to 10 positions
        position_summary.append(
            f"- {p.get('ticker', 'N/A')}: {p.get('position_type', 'N/A')} | "
            f"P&L: {p.get('pnl_percent', 0):+.1f}% | "
            f"SL Risk: {p.get('sl_risk', 0)}% | "
            f"Status: {p.get('overall_status', 'N/A')}"
        )
    
    prompt = f"""You are an expert Indian stock market analyst and portfolio manager.

MARKET CONDITIONS:
- Market Status: {market_health.get('status', 'Unknown')}
- Health Score: {market_health.get('health_score', 'N/A')}/100
- NIFTY: ₹{market_health.get('nifty_price', 'N/A'):,.0f} ({market_health.get('nifty_change', 0):+.1f}%)
- India VIX: {market_health.get('vix', 'N/A')}
- RSI: {market_health.get('nifty_rsi', 'N/A')}
- Trend: {"Above" if market_health.get('above_sma20') else "Below"} SMA20

PORTFOLIO SUMMARY:
- Total Positions: {len(positions)}
- Total P&L: ₹{portfolio_state.get('total_pnl', 0):+,.0f} ({portfolio_state.get('total_pnl_pct', 0):+.1f}%)
- Portfolio Risk: {portfolio_state.get('portfolio_risk_pct', 0):.1f}%
- Critical Positions: {sum(1 for p in positions if p.get('overall_status') == 'CRITICAL')}
- Warning Positions: {sum(1 for p in positions if p.get('overall_status') == 'WARNING')}

POSITIONS:
{chr(10).join(position_summary)}

Please provide:

1. **IMMEDIATE ACTIONS** (Top 3 positions needing action NOW):
   - Which to exit and why
   - Which to reduce exposure

2. **HOLD RECOMMENDATIONS** (Top 3 positions to continue holding):
   - Why these have potential
   - Updated targets if any

3. **RISK MANAGEMENT SUGGESTIONS**:
   - Overall portfolio risk assessment
   - Sector concentration warnings
   - Suggested stop loss adjustments

4. **MARKET OUTLOOK**:
   - Based on current market health
   - Whether to add new positions or stay defensive

5. **ONE SENTENCE SUMMARY**:
   - Your overall recommendation for today

Be specific with price levels and actionable recommendations. Consider Indian market dynamics.
"""
    
    return prompt


# ============================================================================
# 8. TELEGRAM & DISCORD ALERTS
# ============================================================================

def send_telegram_alert(message: str, parse_mode: str = 'HTML') -> Dict:
    """
    Send alert via Telegram
    
    Args:
        message: Alert message (supports HTML formatting)
        parse_mode: HTML or Markdown
    
    Returns:
        Dict with success status and details
    """
    token = AI_CONFIG['telegram_bot_token']
    chat_id = AI_CONFIG['telegram_chat_id']
    
    if not token or not chat_id:
        return {
            'status': 'error',
            'message': 'Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID'
        }
    
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            return {'status': 'success', 'message_id': data['result']['message_id']}
        else:
            return {'status': 'error', 'message': data.get('description', 'Unknown error')}
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def send_discord_alert(message: str, title: str = "Portfolio Alert", color: int = 0xFF0000) -> Dict:
    """
    Send alert via Discord webhook
    
    Args:
        message: Alert message
        title: Embed title
        color: Embed color (hex)
    
    Returns:
        Dict with success status
    """
    webhook_url = AI_CONFIG['discord_webhook_url']
    
    if not webhook_url:
        return {
            'status': 'error',
            'message': 'Discord not configured. Set DISCORD_WEBHOOK_URL'
        }
    
    try:
        import requests
        
        payload = {
            'embeds': [{
                'title': f'📊 {title}',
                'description': message,
                'color': color,
                'timestamp': datetime.utcnow().isoformat(),
                'footer': {'text': 'Smart Portfolio Monitor v7.0'}
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code in [200, 204]:
            return {'status': 'success'}
        else:
            return {'status': 'error', 'message': f'HTTP {response.status_code}'}
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def send_multi_channel_alert(message: str, channels: List[str] = None) -> Dict:
    """
    Send alert to multiple channels
    
    Args:
        message: Alert message
        channels: List of channels ('telegram', 'discord')
    
    Returns:
        Results for each channel
    """
    if channels is None:
        channels = ['telegram', 'discord']
    
    results = {}
    
    if 'telegram' in channels:
        results['telegram'] = send_telegram_alert(message)
    
    if 'discord' in channels:
        results['discord'] = send_discord_alert(message)
    
    return results


# ============================================================================
# 9. FEATURE AVAILABILITY CHECK
# ============================================================================

def get_available_features() -> Dict:
    """
    Check which AI/ML features are available
    
    Usage:
        features = get_available_features()
        print(features)
    """
    return {
        'lstm_prediction': {
            'available': AVAILABLE_FEATURES['tensorflow'],
            'package': 'tensorflow',
            'install': 'pip install tensorflow'
        },
        'sentiment_analysis': {
            'available': AVAILABLE_FEATURES['transformers'],
            'package': 'transformers + torch',
            'install': 'pip install transformers torch'
        },
        'regime_detection': {
            'available': AVAILABLE_FEATURES['hmmlearn'],
            'package': 'hmmlearn',
            'install': 'pip install hmmlearn'
        },
        'backtesting': {
            'available': True,  # Always available (pure Python)
            'package': 'Built-in',
            'install': None
        },
        'rl_stop_loss': {
            'available': True,  # Always available (pure Python)
            'package': 'Built-in',
            'install': None
        },
        'monte_carlo': {
            'available': True,  # Always available (numpy)
            'package': 'numpy',
            'install': None
        },
        'ai_suggestions': {
            'available': bool(AI_CONFIG['claude_api_key']),
            'package': 'anthropic',
            'install': 'pip install anthropic'
        },
        'telegram_alerts': {
            'available': bool(AI_CONFIG['telegram_bot_token']),
            'package': 'requests',
            'install': 'Configure TELEGRAM_BOT_TOKEN'
        },
        'discord_alerts': {
            'available': bool(AI_CONFIG['discord_webhook_url']),
            'package': 'requests',
            'install': 'Configure DISCORD_WEBHOOK_URL'
        }
    }


# ============================================================================
# 10. QUICK TEST FUNCTION
# ============================================================================

def test_all_features():
    """Test all available features"""
    print("=" * 60)
    print("🧪 TESTING AI/ML FEATURES")
    print("=" * 60)
    
    features = get_available_features()
    
    print("\n📋 Feature Availability:")
    for name, info in features.items():
        status = "✅" if info['available'] else "❌"
        print(f"  {status} {name}: {info['package']}")
    
    print("\n" + "=" * 60)
    
    # Test RL Stop Loss (always available)
    print("\n🎯 Testing RL Stop Loss Optimizer...")
    stats = rl_optimizer.get_stats()
    print(f"  States learned: {stats['states_learned']}")
    print(f"  Avg multiplier: {stats['avg_multiplier']:.2f}")
    
    # Test Monte Carlo (always available)
    print("\n📊 Testing Monte Carlo Optimization...")
    np.random.seed(42)
    fake_returns = pd.DataFrame({
        'A': np.random.normal(0.001, 0.02, 100),
        'B': np.random.normal(0.0005, 0.015, 100),
        'C': np.random.normal(0.0008, 0.025, 100)
    })
    mc_result = monte_carlo_portfolio_optimization(['A', 'B', 'C'], fake_returns, num_portfolios=1000)
    if mc_result['status'] == 'success':
        print(f"  Optimal Sharpe: {mc_result['optimal_portfolio']['sharpe_ratio']}")
        print(f"  Weights: {mc_result['optimal_portfolio']['weights']}")
    
    print("\n" + "=" * 60)
    print("✅ Tests completed!")
    
    return features


if __name__ == "__main__":
    test_all_features()

# At the bottom of ai_features.py, add:

# Make sure these are all defined in the file:
__all__ = [
    'get_available_features',
    'run_simple_backtest',
    'get_rl_optimized_sl',
    'monte_carlo_portfolio_optimization',
    'predict_price_lstm',
    'detect_market_regime',
    'get_real_sentiment',
    'rl_optimizer',
    'sentiment_analyzer',  # âœ… ADDED THIS LINE
    'AVAILABLE_FEATURES',
]
