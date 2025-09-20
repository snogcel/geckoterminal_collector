"""
Standalone test for technical indicators without importing the full collector.
"""

import logging
from decimal import Decimal
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Standalone technical indicators implementation."""
    
    def _safe_decimal(self, value) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None:
            return Decimal('0')
        try:
            return Decimal(str(value))
        except:
            return Decimal('0')
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int."""
        if value is None:
            return 0
        try:
            return int(value)
        except:
            return 0
    
    def calculate_rsi(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate RSI indicator."""
        try:
            if not historical_data or not current_price:
                return Decimal('50')  # Neutral RSI
            
            # Extract prices
            prices = [self._safe_decimal(record.get('base_token_price_usd', 0)) for record in historical_data]
            prices = [p for p in prices if p > 0]
            
            if len(prices) < 2:
                return Decimal('50')
            
            # Calculate price changes
            gains = []
            losses = []
            
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(Decimal('0'))
                else:
                    gains.append(Decimal('0'))
                    losses.append(abs(change))
            
            if not gains and not losses:
                return Decimal('50')
            
            avg_gain = sum(gains) / len(gains) if gains else Decimal('0')
            avg_loss = sum(losses) / len(losses) if losses else Decimal('0')
            
            if avg_loss == 0:
                return Decimal('100')
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return min(max(rsi, Decimal('0')), Decimal('100'))
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return Decimal('50')
    
    def calculate_ema(self, prices: List[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        try:
            if not prices or len(prices) < period:
                return Decimal('0')
            
            # Calculate smoothing factor
            alpha = Decimal('2') / (period + 1)
            
            # Start with simple moving average for first value
            ema = sum(prices[:period]) / period
            
            # Calculate EMA for remaining values
            for price in prices[period:]:
                ema = alpha * price + (1 - alpha) * ema
            
            return ema
            
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return Decimal('0')
    
    def calculate_macd(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate MACD indicator."""
        try:
            if not historical_data or len(historical_data) < 26:
                return Decimal('0')  # Need at least 26 periods for MACD
            
            # Extract prices
            prices = [self._safe_decimal(record.get('base_token_price_usd', 0)) for record in historical_data]
            prices = [p for p in prices if p > 0]
            
            if len(prices) < 26:
                return Decimal('0')
            
            # Calculate EMAs (12-period and 26-period)
            ema_12 = self.calculate_ema(prices[-12:], 12)
            ema_26 = self.calculate_ema(prices[-26:], 26)
            
            # MACD line = EMA(12) - EMA(26)
            macd_line = ema_12 - ema_26
            
            return macd_line
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return Decimal('0')
    
    def calculate_bollinger_position(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate position within Bollinger Bands."""
        try:
            if not historical_data or len(historical_data) < 20:
                return Decimal('0.5')  # Neutral position
            
            # Extract prices
            prices = [self._safe_decimal(record.get('base_token_price_usd', 0)) for record in historical_data]
            prices = [p for p in prices if p > 0]
            
            if len(prices) < 20:
                return Decimal('0.5')
            
            # Calculate 20-period moving average and standard deviation
            recent_prices = prices[-20:]
            sma = sum(recent_prices) / len(recent_prices)
            
            # Calculate standard deviation
            variance = sum((price - sma) ** 2 for price in recent_prices) / len(recent_prices)
            std_dev = variance ** Decimal('0.5')
            
            # Bollinger Bands
            upper_band = sma + (2 * std_dev)
            lower_band = sma - (2 * std_dev)
            
            # Calculate position (0 = lower band, 1 = upper band, 0.5 = middle)
            if upper_band == lower_band:
                return Decimal('0.5')
            
            position = (current_price - lower_band) / (upper_band - lower_band)
            return min(max(position, Decimal('0')), Decimal('1'))
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger position: {e}")
            return Decimal('0.5')
    
    def calculate_activity_metrics(self, attributes: Dict, historical_data: List[Dict]) -> Dict[str, Decimal]:
        """Calculate activity-based metrics."""
        try:
            metrics = {}
            
            # Get current transaction data
            buys_24h = self._safe_int(attributes.get('transactions_h24_buys', 0))
            sells_24h = self._safe_int(attributes.get('transactions_h24_sells', 0))
            total_transactions = buys_24h + sells_24h
            
            # Trader diversity score (based on buy/sell balance)
            if total_transactions > 0:
                buy_ratio = buys_24h / total_transactions
                # Diversity is highest when buy/sell ratio is close to 0.5
                diversity = 1 - abs(buy_ratio - 0.5) * 2
                metrics['trader_diversity'] = Decimal(str(max(0, diversity)))
            else:
                metrics['trader_diversity'] = Decimal('0')
            
            # Whale activity indicator (based on volume per transaction)
            volume_24h = float(self._safe_decimal(attributes.get('volume_usd_h24', 0)))
            if total_transactions > 0 and volume_24h > 0:
                avg_transaction_size = volume_24h / total_transactions
                # Normalize whale activity (higher avg transaction size = more whale activity)
                whale_score = min(avg_transaction_size / 10000, 1.0)  # Cap at $10k avg
                metrics['whale_activity'] = Decimal(str(whale_score))
            else:
                metrics['whale_activity'] = Decimal('0')
            
            # Retail activity score (inverse of whale activity)
            metrics['retail_activity'] = Decimal('1') - metrics['whale_activity']
            
            # Market impact score (based on price volatility vs volume)
            price_change = abs(float(self._safe_decimal(attributes.get('price_change_percentage_h24', 0))))
            if volume_24h > 0:
                impact_score = min(price_change / (volume_24h / 1000), 1.0)  # Normalize
                metrics['market_impact'] = Decimal(str(impact_score))
            else:
                metrics['market_impact'] = Decimal('0.5')
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating activity metrics: {e}")
            return {
                'trader_diversity': Decimal('0.5'),
                'whale_activity': Decimal('0'),
                'retail_activity': Decimal('0.5'),
                'market_impact': Decimal('0.5')
            }


def test_standalone_indicators():
    """Test standalone technical indicators."""
    try:
        logger.info("🧪 Testing Standalone Technical Indicators...")
        
        indicators = TechnicalIndicators()
        
        # Test data
        test_data = [
            {'base_token_price_usd': 1.0, 'timestamp': 1000},
            {'base_token_price_usd': 1.1, 'timestamp': 2000},
            {'base_token_price_usd': 0.9, 'timestamp': 3000},
            {'base_token_price_usd': 1.2, 'timestamp': 4000},
            {'base_token_price_usd': 1.05, 'timestamp': 5000},
        ]
        
        # Extend test data for better calculations
        for i in range(25):
            price = 1.0 + (i % 10) * 0.1
            test_data.append({
                'base_token_price_usd': price,
                'timestamp': 6000 + i * 1000
            })
        
        current_price = Decimal('1.1')
        
        # Test RSI
        rsi = indicators.calculate_rsi(test_data, current_price)
        logger.info(f"✅ RSI: {rsi}")
        assert isinstance(rsi, Decimal)
        assert 0 <= rsi <= 100
        
        # Test MACD
        macd = indicators.calculate_macd(test_data, current_price)
        logger.info(f"✅ MACD: {macd}")
        assert isinstance(macd, Decimal)
        
        # Test EMA
        prices = [Decimal(str(d['base_token_price_usd'])) for d in test_data]
        ema_12 = indicators.calculate_ema(prices, 12)
        ema_26 = indicators.calculate_ema(prices, 26)
        logger.info(f"✅ EMA(12): {ema_12}, EMA(26): {ema_26}")
        assert isinstance(ema_12, Decimal)
        assert isinstance(ema_26, Decimal)
        
        # Test Bollinger Bands
        bollinger = indicators.calculate_bollinger_position(test_data, current_price)
        logger.info(f"✅ Bollinger Position: {bollinger}")
        assert isinstance(bollinger, Decimal)
        assert 0 <= bollinger <= 1
        
        # Test Activity Metrics
        attributes = {
            'transactions_h24_buys': 120,
            'transactions_h24_sells': 80,
            'volume_usd_h24': 75000,
            'price_change_percentage_h24': 8.5
        }
        
        activity = indicators.calculate_activity_metrics(attributes, test_data)
        logger.info(f"✅ Activity Metrics: {list(activity.keys())}")
        
        expected_keys = ['trader_diversity', 'whale_activity', 'retail_activity', 'market_impact']
        for key in expected_keys:
            assert key in activity
            assert isinstance(activity[key], Decimal)
            logger.info(f"   {key}: {activity[key]}")
        
        # Validate logical relationships
        assert activity['retail_activity'] == Decimal('1') - activity['whale_activity']
        assert 0 <= activity['trader_diversity'] <= 1
        
        logger.info("✅ All standalone technical indicator tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Standalone indicators test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_standalone_indicators()
    if success:
        logger.info("🎉 Technical indicators are working correctly!")
    else:
        logger.info("❌ Technical indicators test failed.")
    exit(0 if success else 1)