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

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

AI_CONFIG = {
    # API Keys - Set these for full functionality
    'claude_api_key': os.getenv('CLAUDE_API_KEY', ''),
    'news_api_key': '0efbb77b-0d77-40c7-b7fc-424627fb3e8d',  # Get free from newsapi.org
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
    
    def is_available(self) -> bool:
        """Check if TensorFlow is available"""
        return AVAILABLE_FEATURES['tensorflow']
    
    def predict(self, df: pd.DataFrame, periods: int = 5) -> Optional[Dict]:
        """
        Predict next N periods using LSTM
        
        Args:
            df: DataFrame with 'Close' prices
            periods: Number of days to predict
        
        Returns:
            Dict with predictions, confidence, etc.
        """
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
            
            # Prepare data
            close_prices = df['Close'].values.reshape(-1, 1)
            self.scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data = self.scaler.fit_transform(close_prices)
            
            # Create sequences
            sequence_length = AI_CONFIG['lstm_sequence_length']
            X, y = [], []
            
            for i in range(sequence_length, len(scaled_data)):
                X.append(scaled_data[i-sequence_length:i, 0])
                y.append(scaled_data[i, 0])
            
            X, y = np.array(X), np.array(y)
            X = np.reshape(X, (X.shape[0], X.shape[1], 1))
            
            # Split data (80% train, 20% validation)
            split = int(len(X) * 0.8)
            X_train, X_val = X[:split], X[split:]
            y_train, y_val = y[:split], y[split:]
            
            # Build LSTM model
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
            
            # Train with validation
            history = self.model.fit(
                X_train, y_train,
                batch_size=AI_CONFIG['lstm_batch_size'],
                epochs=AI_CONFIG['lstm_epochs'],
                validation_data=(X_val, y_val),
                verbose=0
            )
            
            # Calculate training metrics
            train_loss = history.history['loss'][-1]
            val_loss = history.history['val_loss'][-1]
            
            # Predict next periods
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
        self.epsilon = 0.1  # Exploration rate
        self.trade_history = []
        
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
            'discount_factor': self.gamma
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
# 3. REAL SENTIMENT ANALYSIS WITH FINBERT
# ============================================================================

class SentimentAnalyzer:
    """
    Financial sentiment analysis using FinBERT model
    Analyzes news headlines to determine market sentiment
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
    
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
    
    def _fetch_news(self, ticker: str, days: int = 7) -> List[Dict]:
        """Fetch news articles for a ticker"""
        if not AI_CONFIG['news_api_key']:
            logger.warning("News API key not configured")
            return []
        
        try:
            import requests
            
            # Map common tickers to search terms
            search_terms = {
                'RELIANCE': 'Reliance Industries',
                'TCS': 'Tata Consultancy Services',
                'INFY': 'Infosys',
                'HDFCBANK': 'HDFC Bank',
                'ICICIBANK': 'ICICI Bank',
                'SBIN': 'State Bank of India',
                'TATAMOTORS': 'Tata Motors',
                'MARUTI': 'Maruti Suzuki',
            }
            
            query = search_terms.get(ticker.upper().replace('.NS', ''), ticker)
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': f'"{query}" stock OR shares',
                'apiKey': AI_CONFIG['news_api_key'],
                'pageSize': 20,
                'language': 'en',
                'sortBy': 'publishedAt',
                'from': (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'ok':
                return data.get('articles', [])
            else:
                logger.warning(f"News API error: {data.get('message')}")
                return []
        
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return []
    
    def analyze(self, ticker: str) -> Optional[Dict]:
        """
        Analyze sentiment for a ticker
        
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
        
        # Load model
        if not self._load_model():
            return {
                'status': 'error',
                'message': 'Failed to load FinBERT model',
                'sentiment': None
            }
        
        # Fetch news
        articles = self._fetch_news(ticker)
        
        if not articles:
            return {
                'status': 'warning',
                'message': 'No news articles found',
                'sentiment': None
            }
        
        try:
            import torch
            
            sentiments = []
            analyzed_headlines = []
            
            for article in articles[:15]:  # Analyze up to 15 articles
                headline = article.get('title', '')
                if not headline or len(headline) < 10:
                    continue
                
                # Tokenize and predict
                inputs = self.tokenizer(
                    headline, 
                    return_tensors="pt", 
                    padding=True, 
                    truncation=True,
                    max_length=128
                )
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                # FinBERT outputs: [negative, neutral, positive]
                neg_score = predictions[0][0].item()
                neu_score = predictions[0][1].item()
                pos_score = predictions[0][2].item()
                
                # Calculate composite score (-100 to +100)
                sentiment_score = (pos_score - neg_score) * 100
                sentiments.append(sentiment_score)
                
                analyzed_headlines.append({
                    'headline': headline[:100] + '...' if len(headline) > 100 else headline,
                    'score': sentiment_score,
                    'positive': pos_score,
                    'negative': neg_score,
                    'neutral': neu_score,
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'date': article.get('publishedAt', '')[:10]
                })
            
            if not sentiments:
                return {
                    'status': 'warning',
                    'message': 'Could not analyze any headlines',
                    'sentiment': None
                }
            
            # Calculate overall sentiment
            avg_sentiment = np.mean(sentiments)
            sentiment_std = np.std(sentiments)
            
            if avg_sentiment > 25:
                sentiment_type = "BULLISH"
                color = "#28a745"
            elif avg_sentiment > 10:
                sentiment_type = "SLIGHTLY_BULLISH"
                color = "#7cb342"
            elif avg_sentiment < -25:
                sentiment_type = "BEARISH"
                color = "#dc3545"
            elif avg_sentiment < -10:
                sentiment_type = "SLIGHTLY_BEARISH"
                color = "#f57c00"
            else:
                sentiment_type = "NEUTRAL"
                color = "#ffc107"
            
            # Confidence based on consistency
            confidence = max(0, min(100, int(100 - sentiment_std)))
            
            return {
                'status': 'success',
                'ticker': ticker,
                'score': round(avg_sentiment, 1),
                'type': sentiment_type,
                'color': color,
                'confidence': confidence,
                'articles_analyzed': len(sentiments),
                'headlines': analyzed_headlines[:5],  # Top 5
                'summary': f"Analyzed {len(sentiments)} articles. Overall: {sentiment_type}",
                'generated_at': datetime.now().isoformat(),
                'source': 'FinBERT + NewsAPI'
            }
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'sentiment': None
            }


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
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
    
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
                        position = {
                            'entry_price': current['Close'],
                            'entry_date': current.get('Date', df.index[i]),
                            'entry_index': i,
                            'quantity': qty
                        }
            else:
                # Check exit
                exit_signal, exit_reason = self._check_exit(
                    historical, exit_rules, position, current
                )
                
                if exit_signal:
                    pnl = (current['Close'] - position['entry_price']) * position['quantity']
                    pnl_pct = ((current['Close'] - position['entry_price']) / position['entry_price']) * 100
                    
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
    initial_capital: float = 100000
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
        
        engine = BacktestEngine(initial_capital=initial_capital)
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
    'AVAILABLE_FEATURES',
]
