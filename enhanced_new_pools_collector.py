"""
Enhanced New Pools Collector for QLib Integration and Predictive Modeling
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
import hashlib
import json

from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.models.core import CollectionResult
from enhanced_new_pools_history_model import EnhancedNewPoolsHistory, PoolFeatureVector

logger = logging.getLogger(__name__)


class EnhancedNewPoolsCollector(NewPoolsCollector):
    """
    Enhanced new pools collector with advanced time series tracking,
    feature engineering, and QLib integration capabilities.
    """
    
    def __init__(self, config, db_manager, network: str, **kwargs):
        # Set network before calling super() to avoid logger initialization issues
        self.network = network
        
        # Extract enhanced-specific kwargs before calling super()
        collection_intervals = kwargs.pop('collection_intervals', ['1h'])
        enable_feature_engineering = kwargs.pop('enable_feature_engineering', True)
        qlib_integration = kwargs.pop('qlib_integration', True)
        auto_watchlist_enabled = kwargs.pop('auto_watchlist_enabled', True)
        auto_watchlist_threshold = kwargs.pop('auto_watchlist_threshold', 75.0)
        
        # Initialize parent class with network and remaining kwargs
        super().__init__(config, db_manager, network, **kwargs)
        
        # Set enhanced-specific attributes (after parent init to override any parent settings)
        self.collection_intervals = collection_intervals
        self.enable_feature_engineering = enable_feature_engineering
        self.qlib_integration = qlib_integration
        self.auto_watchlist_enabled = auto_watchlist_enabled  # Override parent's setting
        self.auto_watchlist_threshold = auto_watchlist_threshold
        
        # Feature engineering configuration
        self.lookback_periods = {
            'short': 24,   # 24 hours
            'medium': 168, # 7 days
            'long': 720    # 30 days
        }
        
        # Initialize signal analyzer for auto-watchlist (override parent's analyzer if needed)
        if self.auto_watchlist_enabled:
            from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
            self.signal_analyzer = NewPoolsSignalAnalyzer({
                'auto_watchlist_threshold': self.auto_watchlist_threshold
            })
        
    async def collect(self) -> CollectionResult:
        """
        Enhanced collection with time series optimization and feature engineering.
        """
        start_time = datetime.now()
        errors = []
        total_records = 0
        
        try:
            self.logger.info(f"Starting enhanced new pools collection for network: {self.network}")
            
            # Get new pools data
            response = await self.make_api_request(
                self.client.get_new_pools_by_network,
                self.network
            )
            
            if not response or (isinstance(response, dict) and 'data' not in response):
                error_msg = f"No data received from API for network {self.network}"
                self.logger.warning(error_msg)
                return self.create_failure_result([error_msg], 0, start_time)
            
            # Normalize response data
            pools_data = self._normalize_response_data(response)
            self.logger.info(f"Received {len(pools_data)} new pools from API")
            
            # Process each collection interval
            for interval in self.collection_intervals:
                interval_records = await self._process_interval_data(pools_data, interval)
                total_records += interval_records
            
            # Perform feature engineering if enabled
            if self.enable_feature_engineering:
                feature_records = await self._generate_feature_vectors(pools_data)
                total_records += feature_records
            
            # Auto-watchlist integration if enabled
            if self.auto_watchlist_enabled:
                watchlist_additions = await self._process_auto_watchlist(pools_data)
                self.logger.info(f"Auto-watchlist: {watchlist_additions} pools added")
            
            # Generate QLib exports if enabled
            if self.qlib_integration:
                await self._update_qlib_data()
            
            self.logger.info(
                f"Enhanced collection completed for {self.network}: "
                f"{total_records} total records processed"
            )
            
            return CollectionResult(
                success=True,
                records_collected=total_records,
                errors=errors,
                collection_time=start_time,
                collector_type=f"enhanced_{self.get_collection_key()}",
                metadata={
                    'network': self.network,
                    'intervals_processed': len(self.collection_intervals),
                    'feature_engineering_enabled': self.enable_feature_engineering,
                    'qlib_integration_enabled': self.qlib_integration,
                    'auto_watchlist_enabled': self.auto_watchlist_enabled,
                    'auto_watchlist_threshold': self.auto_watchlist_threshold
                }
            )
            
        except Exception as e:
            error_msg = f"Enhanced collection failed for {self.network}: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            return self.create_failure_result(errors, total_records, start_time)
    
    async def _process_interval_data(self, pools_data: List[Dict], interval: str) -> int:
        """
        Process pools data for a specific time interval.
        
        Args:
            pools_data: List of pool data from API
            interval: Time interval ('1h', '4h', '1d')
            
        Returns:
            Number of records processed
        """
        records_processed = 0
        current_time = datetime.now()
        timestamp = int(current_time.timestamp())
        
        for pool_data in pools_data:
            try:
                # Create enhanced history record
                enhanced_record = await self._create_enhanced_history_record(
                    pool_data, interval, current_time, timestamp
                )
                
                if enhanced_record:
                    await self._store_enhanced_history_record(enhanced_record)
                    records_processed += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing pool {pool_data.get('id')} for interval {interval}: {e}")
                continue
        
        return records_processed
    
    async def _create_enhanced_history_record(
        self, 
        pool_data: Dict, 
        interval: str, 
        current_time: datetime, 
        timestamp: int
    ) -> Optional[Dict]:
        """
        Create enhanced history record with additional time series and ML features.
        """
        try:
            # Get basic pool info
            basic_record = self._create_history_record(pool_data)
            if not basic_record:
                return None
            
            # Extract attributes
            attributes = pool_data.get('attributes', {})
            pool_id = pool_data.get('id')
            
            # Calculate OHLC data (simulated from current price)
            current_price = self._safe_decimal(attributes.get('base_token_price_usd'))
            if current_price:
                # For new implementation, use current price as all OHLC values
                # In production, you'd calculate these from tick data
                ohlc_data = {
                    'open_price_usd': current_price,
                    'high_price_usd': current_price * Decimal('1.001'),  # Slight variation
                    'low_price_usd': current_price * Decimal('0.999'),
                    'close_price_usd': current_price
                }
            else:
                ohlc_data = {}
            
            # Calculate advanced metrics
            advanced_metrics = await self._calculate_advanced_metrics(pool_id, attributes)
            
            # Calculate pool age
            pool_age_hours = self._calculate_pool_age_hours(attributes.get('pool_created_at'))
            
            # Generate QLib symbol
            qlib_symbol = self._generate_qlib_symbol(pool_id, attributes)
            
            # Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(attributes)
            
            # Create API response hash for deduplication
            api_response_hash = self._create_response_hash(pool_data)
            
            # Enhanced record data
            enhanced_data = {
                **basic_record,
                
                # Time series keys
                'timestamp': timestamp,
                'datetime': current_time,
                'collection_interval': interval,
                
                # OHLC data
                **ohlc_data,
                
                # Enhanced volume metrics
                'volume_usd_interval': self._calculate_interval_volume(attributes, interval),
                'volume_usd_h1': self._safe_decimal(attributes.get('volume_usd_h1', 0)),
                
                # Token symbols
                'base_token_symbol': self._extract_token_symbol(attributes, 'base'),
                'quote_token_symbol': self._extract_token_symbol(attributes, 'quote'),
                
                # Advanced metrics
                **advanced_metrics,
                
                # Pool lifecycle
                'pool_age_hours': pool_age_hours,
                'is_new_pool': pool_age_hours < 168 if pool_age_hours else True,  # < 7 days
                
                # Data quality and metadata
                'data_quality_score': data_quality_score,
                'collection_source': 'gecko_terminal_api',
                'api_response_hash': api_response_hash,
                
                # QLib integration
                'qlib_symbol': qlib_symbol,
                'qlib_features_json': await self._generate_qlib_features(pool_data, attributes),
                
                # Timestamps
                'collected_at': current_time,
                'processed_at': None  # Will be set during feature engineering
            }
            
            return enhanced_data
            
        except Exception as e:
            self.logger.error(f"Error creating enhanced history record: {e}")
            return None
    
    async def _calculate_advanced_metrics(self, pool_id: str, attributes: Dict) -> Dict:
        """Calculate advanced metrics for ML features."""
        try:
            # Get historical data for calculations
            historical_data = await self._get_pool_historical_data(pool_id, hours=24)
            
            # Calculate buy/sell ratios
            buys_h24 = self._safe_int(attributes.get('transactions_h24_buys', 0))
            sells_h24 = self._safe_int(attributes.get('transactions_h24_sells', 0))
            buy_sell_ratio_h24 = buys_h24 / max(sells_h24, 1)
            
            # Calculate volume-weighted average price (simplified)
            volume_24h = self._safe_decimal(attributes.get('volume_usd_h24', 0))
            current_price = self._safe_decimal(attributes.get('base_token_price_usd', 0))
            vwap = current_price  # Simplified - in production, calculate from trades
            
            # Calculate volatility (simplified)
            price_change_h24 = self._safe_decimal(attributes.get('price_change_percentage_h24', 0))
            volatility = abs(price_change_h24) if price_change_h24 else Decimal('0')
            
            # Calculate liquidity metrics
            current_liquidity = self._safe_decimal(attributes.get('reserve_in_usd', 0))
            liquidity_change = Decimal('0')  # Would calculate from historical data
            
            # Technical indicators (real implementations)
            rsi = self._calculate_simple_rsi(historical_data, current_price)
            macd = self._calculate_macd(historical_data, current_price)
            trend_strength = min(abs(price_change_h24 or 0), 100)
            
            # Calculate liquidity change from historical data
            liquidity_change = self._calculate_liquidity_change(historical_data, current_liquidity)
            
            return {
                'buy_sell_ratio_interval': buy_sell_ratio_h24,
                'buy_sell_ratio_h24': buy_sell_ratio_h24,
                'volume_weighted_price': vwap,
                'price_volatility': volatility,
                'liquidity_change_percentage': liquidity_change,
                'liquidity_depth_usd': current_liquidity,
                'trend_strength': trend_strength,
                'relative_strength_index': rsi,
                'moving_average_convergence': macd,
                'support_resistance_level': current_price
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating advanced metrics: {e}")
            return {}
    
    def _calculate_simple_rsi(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate a simplified RSI indicator."""
        try:
            if not historical_data or not current_price:
                return Decimal('50')  # Neutral RSI
            
            # Simplified RSI calculation
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
            self.logger.error(f"Error calculating RSI: {e}")
            return Decimal('50')
    
    def _calculate_macd(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate MACD (Moving Average Convergence Divergence) indicator."""
        try:
            if not historical_data or len(historical_data) < 26:
                return Decimal('0')  # Need at least 26 periods for MACD
            
            # Extract prices
            prices = [self._safe_decimal(record.get('base_token_price_usd', 0)) for record in historical_data]
            prices = [p for p in prices if p > 0]
            
            if len(prices) < 26:
                return Decimal('0')
            
            # Calculate EMAs (12-period and 26-period)
            ema_12 = self._calculate_ema(prices[-12:], 12)
            ema_26 = self._calculate_ema(prices[-26:], 26)
            
            # MACD line = EMA(12) - EMA(26)
            macd_line = ema_12 - ema_26
            
            return macd_line
            
        except Exception as e:
            self.logger.error(f"Error calculating MACD: {e}")
            return Decimal('0')
    
    def _calculate_ema(self, prices: List[Decimal], period: int) -> Decimal:
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
            self.logger.error(f"Error calculating EMA: {e}")
            return Decimal('0')
    
    def _calculate_liquidity_change(self, historical_data: List[Dict], current_liquidity: Decimal) -> Decimal:
        """Calculate liquidity change percentage from historical data."""
        try:
            if not historical_data or not current_liquidity:
                return Decimal('0')
            
            # Get liquidity values from historical data
            liquidity_values = []
            for record in historical_data:
                liquidity = self._safe_decimal(record.get('reserve_in_usd', 0))
                if liquidity > 0:
                    liquidity_values.append(liquidity)
            
            if not liquidity_values:
                return Decimal('0')
            
            # Calculate average historical liquidity
            avg_historical_liquidity = sum(liquidity_values) / len(liquidity_values)
            
            if avg_historical_liquidity == 0:
                return Decimal('0')
            
            # Calculate percentage change
            change_percentage = ((current_liquidity - avg_historical_liquidity) / avg_historical_liquidity) * 100
            
            return change_percentage
            
        except Exception as e:
            self.logger.error(f"Error calculating liquidity change: {e}")
            return Decimal('0')
    
    def _calculate_bollinger_position(self, historical_data: List[Dict], current_price: Decimal) -> Decimal:
        """Calculate position within Bollinger Bands (0-1 scale)."""
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
            self.logger.error(f"Error calculating Bollinger position: {e}")
            return Decimal('0.5')
    
    def _calculate_volume_sma_ratio(self, historical_data: List[Dict], current_volume: float) -> Decimal:
        """Calculate ratio of current volume to simple moving average."""
        try:
            if not historical_data or current_volume <= 0:
                return Decimal('1.0')
            
            # Extract volume values
            volumes = []
            for record in historical_data:
                volume = float(self._safe_decimal(record.get('volume_usd_h24', 0)))
                if volume > 0:
                    volumes.append(volume)
            
            if not volumes:
                return Decimal('1.0')
            
            # Calculate simple moving average
            sma_volume = sum(volumes) / len(volumes)
            
            if sma_volume == 0:
                return Decimal('1.0')
            
            # Calculate ratio
            ratio = Decimal(str(current_volume)) / Decimal(str(sma_volume))
            return ratio
            
        except Exception as e:
            self.logger.error(f"Error calculating volume SMA ratio: {e}")
            return Decimal('1.0')
    
    def _calculate_liquidity_stability(self, historical_data: List[Dict]) -> Decimal:
        """Calculate liquidity stability score (0-1, higher = more stable)."""
        try:
            if not historical_data or len(historical_data) < 5:
                return Decimal('0.5')
            
            # Extract liquidity values
            liquidity_values = []
            for record in historical_data:
                liquidity = float(self._safe_decimal(record.get('reserve_in_usd', 0)))
                if liquidity > 0:
                    liquidity_values.append(liquidity)
            
            if len(liquidity_values) < 2:
                return Decimal('0.5')
            
            # Calculate coefficient of variation (lower = more stable)
            mean_liquidity = sum(liquidity_values) / len(liquidity_values)
            
            if mean_liquidity == 0:
                return Decimal('0')
            
            # Calculate standard deviation
            variance = sum((liq - mean_liquidity) ** 2 for liq in liquidity_values) / len(liquidity_values)
            std_dev = variance ** 0.5
            
            # Coefficient of variation
            cv = std_dev / mean_liquidity
            
            # Convert to stability score (inverse of CV, capped at 1)
            stability = max(0, 1 - cv)
            return Decimal(str(min(stability, 1.0)))
            
        except Exception as e:
            self.logger.error(f"Error calculating liquidity stability: {e}")
            return Decimal('0.5')
    
    def _calculate_liquidity_growth_rate(self, historical_data: List[Dict]) -> Decimal:
        """Calculate liquidity growth rate over the historical period."""
        try:
            if not historical_data or len(historical_data) < 2:
                return Decimal('0')
            
            # Extract liquidity values with timestamps
            liquidity_points = []
            for record in historical_data:
                liquidity = float(self._safe_decimal(record.get('reserve_in_usd', 0)))
                timestamp = record.get('timestamp', 0)
                if liquidity > 0 and timestamp > 0:
                    liquidity_points.append((timestamp, liquidity))
            
            if len(liquidity_points) < 2:
                return Decimal('0')
            
            # Sort by timestamp
            liquidity_points.sort(key=lambda x: x[0])
            
            # Calculate growth rate between first and last points
            first_liquidity = liquidity_points[0][1]
            last_liquidity = liquidity_points[-1][1]
            time_diff_hours = (liquidity_points[-1][0] - liquidity_points[0][0]) / 3600
            
            if first_liquidity == 0 or time_diff_hours <= 0:
                return Decimal('0')
            
            # Calculate hourly growth rate
            growth_rate = ((last_liquidity - first_liquidity) / first_liquidity) / time_diff_hours
            return Decimal(str(growth_rate))
            
        except Exception as e:
            self.logger.error(f"Error calculating liquidity growth rate: {e}")
            return Decimal('0')
    
    def _calculate_activity_metrics(self, attributes: Dict, historical_data: List[Dict]) -> Dict[str, Decimal]:
        """Calculate various activity-based metrics."""
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
            
            # Depth imbalance (simplified - based on transaction imbalance)
            if total_transactions > 0:
                imbalance = abs(buys_24h - sells_24h) / total_transactions
                metrics['depth_imbalance'] = Decimal(str(imbalance))
            else:
                metrics['depth_imbalance'] = Decimal('0.5')
            
            # Market impact score (based on price volatility vs volume)
            price_change = abs(float(self._safe_decimal(attributes.get('price_change_percentage_h24', 0))))
            if volume_24h > 0:
                impact_score = min(price_change / (volume_24h / 1000), 1.0)  # Normalize
                metrics['market_impact'] = Decimal(str(impact_score))
            else:
                metrics['market_impact'] = Decimal('0.5')
            
            # Spread normalized (simplified estimate based on volatility)
            volatility = price_change / 100  # Convert percentage to decimal
            spread_estimate = min(volatility * 0.1, 0.05)  # Cap at 5%
            metrics['spread_normalized'] = Decimal(str(spread_estimate))
            
            # Arbitrage opportunity (based on price volatility and volume)
            if volume_24h > 1000 and price_change > 5:  # High volume and volatility
                arb_score = min((price_change - 5) / 20, 1.0)  # Scale from 5% to 25%
                metrics['arbitrage_score'] = Decimal(str(arb_score))
            else:
                metrics['arbitrage_score'] = Decimal('0')
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating activity metrics: {e}")
            return {
                'trader_diversity': Decimal('0.5'),
                'whale_activity': Decimal('0'),
                'retail_activity': Decimal('0.5'),
                'depth_imbalance': Decimal('0.5'),
                'market_impact': Decimal('0.5'),
                'spread_normalized': Decimal('0.01'),
                'arbitrage_score': Decimal('0')
            }
    
    def _calculate_interval_volume(self, attributes: Dict, interval: str) -> Decimal:
        """Calculate volume for the specific collection interval."""
        try:
            # Map intervals to appropriate volume fields
            if interval == '1h':
                return self._safe_decimal(attributes.get('volume_usd_h1', 0))
            elif interval == '4h':
                # Estimate 4h volume as fraction of 24h volume
                volume_24h = self._safe_decimal(attributes.get('volume_usd_h24', 0))
                return volume_24h * Decimal('0.167')  # 4/24 hours
            elif interval == '1d':
                return self._safe_decimal(attributes.get('volume_usd_h24', 0))
            else:
                # Default to 1h volume
                return self._safe_decimal(attributes.get('volume_usd_h1', 0))
                
        except Exception as e:
            self.logger.error(f"Error calculating interval volume: {e}")
            return Decimal('0')
    
    def _calculate_pool_age_hours(self, created_at_str: Optional[str]) -> Optional[int]:
        """Calculate pool age in hours."""
        try:
            if not created_at_str:
                return None
            
            # Parse creation timestamp
            if created_at_str.endswith('Z'):
                created_at_str = created_at_str[:-1] + '+00:00'
            
            created_at = datetime.fromisoformat(created_at_str)
            age_delta = datetime.now(created_at.tzinfo) - created_at
            
            return int(age_delta.total_seconds() / 3600)
            
        except Exception as e:
            self.logger.error(f"Error calculating pool age: {e}")
            return None
    
    def _generate_qlib_symbol(self, pool_id: str, attributes: Dict) -> str:
        """Generate QLib-compatible symbol."""
        try:
            # Extract meaningful symbol from pool data
            name = attributes.get('name', '')
            if name and '/' in name:
                symbol = name.replace('/', '_').upper()
            else:
                symbol = f"POOL_{pool_id[:8].upper()}"
            
            return f"{symbol}_{self.network.upper()}"
            
        except Exception as e:
            self.logger.error(f"Error generating QLib symbol: {e}")
            return f"UNKNOWN_{pool_id[:8]}"
    
    async def _get_pool_historical_data(self, pool_id: str, hours: int = 24) -> List[Dict]:
        """
        Get historical data for a pool from the database.
        
        Args:
            pool_id: Pool ID to get data for
            hours: Number of hours of historical data to retrieve
            
        Returns:
            List of historical data records
        """
        try:
            if not pool_id:
                return []
            
            # Calculate timestamp for historical data
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # Query historical data from enhanced history table
            with self.db_manager.connection.get_session() as session:
                from enhanced_new_pools_history_model import EnhancedNewPoolsHistory
                
                historical_records = session.query(EnhancedNewPoolsHistory).filter(
                    EnhancedNewPoolsHistory.pool_id == pool_id,
                    EnhancedNewPoolsHistory.timestamp >= cutoff_timestamp
                ).order_by(EnhancedNewPoolsHistory.timestamp.desc()).limit(100).all()
                
                # Convert to dictionaries
                historical_data = []
                for record in historical_records:
                    historical_data.append({
                        'pool_id': record.pool_id,
                        'timestamp': record.timestamp,
                        'base_token_price_usd': record.close_price_usd or record.open_price_usd,
                        'volume_usd_h24': record.volume_usd_h24,
                        'reserve_in_usd': record.reserve_in_usd,
                        'transactions_h24_buys': record.transactions_h24_buys,
                        'transactions_h24_sells': record.transactions_h24_sells,
                        'price_change_percentage_h1': record.price_change_percentage_h1,
                        'price_change_percentage_h24': record.price_change_percentage_h24
                    })
                
                return historical_data
                
        except Exception as e:
            self.logger.error(f"Error getting historical data for pool {pool_id}: {e}")
            return []
    
    def _calculate_data_quality_score(self, attributes: Dict) -> Decimal:
        """Calculate data quality score (0-100)."""
        try:
            score = Decimal('100')
            
            # Deduct points for missing critical fields
            critical_fields = [
                'base_token_price_usd', 'volume_usd_h24', 'reserve_in_usd',
                'transactions_h24_buys', 'transactions_h24_sells'
            ]
            
            for field in critical_fields:
                if not attributes.get(field):
                    score -= Decimal('15')
            
            # Deduct points for zero values in important fields
            if self._safe_decimal(attributes.get('volume_usd_h24', 0)) == 0:
                score -= Decimal('10')
            
            if self._safe_decimal(attributes.get('reserve_in_usd', 0)) == 0:
                score -= Decimal('10')
            
            return max(score, Decimal('0'))
            
        except Exception as e:
            self.logger.error(f"Error calculating data quality score: {e}")
            return Decimal('50')
    
    def _create_response_hash(self, pool_data: Dict) -> str:
        """Create hash of API response for deduplication."""
        try:
            # Create deterministic hash of the pool data
            data_str = json.dumps(pool_data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception as e:
            self.logger.error(f"Error creating response hash: {e}")
            return ""
    
    async def _generate_qlib_features(self, pool_data: Dict, attributes: Dict) -> Dict:
        """Generate pre-computed features for QLib."""
        try:
            features = {
                'price': float(self._safe_decimal(attributes.get('base_token_price_usd', 0))),
                'volume': float(self._safe_decimal(attributes.get('volume_usd_h24', 0))),
                'liquidity': float(self._safe_decimal(attributes.get('reserve_in_usd', 0))),
                'market_cap': float(self._safe_decimal(attributes.get('market_cap_usd', 0))),
                'price_change_24h': float(self._safe_decimal(attributes.get('price_change_percentage_h24', 0))),
                'transactions_24h': self._safe_int(attributes.get('transactions_h24_buys', 0)) + 
                                   self._safe_int(attributes.get('transactions_h24_sells', 0)),
                'buy_ratio': self._safe_int(attributes.get('transactions_h24_buys', 0)) / 
                           max(self._safe_int(attributes.get('transactions_h24_buys', 0)) + 
                               self._safe_int(attributes.get('transactions_h24_sells', 0)), 1)
            }
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error generating QLib features: {e}")
            return {}
    
    async def _store_enhanced_history_record(self, record_data: Dict) -> None:
        """Store enhanced history record."""
        try:
            history_entry = EnhancedNewPoolsHistory(**record_data)
            
            # Use database manager to store
            if hasattr(self.db_manager, 'store_enhanced_new_pools_history'):
                await self.db_manager.store_enhanced_new_pools_history(history_entry)
            else:
                # Fallback to session-based storage
                with self.db_manager.connection.get_session() as session:
                    session.add(history_entry)
                    session.commit()
            
            self.logger.debug(f"Stored enhanced history record for pool: {record_data['pool_id']}")
            
        except Exception as e:
            self.logger.error(f"Error storing enhanced history record: {e}")
            raise
    
    async def _generate_feature_vectors(self, pools_data: List[Dict]) -> int:
        """Generate feature vectors for machine learning."""
        if not self.enable_feature_engineering:
            return 0
        
        vectors_created = 0
        current_time = datetime.now()
        timestamp = int(current_time.timestamp())
        
        for pool_data in pools_data:
            try:
                pool_id = pool_data.get('id')
                if not pool_id:
                    continue
                
                # Generate feature vector
                feature_vector = await self._create_feature_vector(
                    pool_id, pool_data, timestamp, current_time
                )
                
                if feature_vector:
                    await self._store_feature_vector(feature_vector)
                    vectors_created += 1
                    
            except Exception as e:
                self.logger.error(f"Error generating feature vector for {pool_data.get('id')}: {e}")
                continue
        
        return vectors_created
    
    async def _create_feature_vector(
        self, 
        pool_id: str, 
        pool_data: Dict, 
        timestamp: int, 
        current_time: datetime
    ) -> Optional[Dict]:
        """Create feature vector for ML models."""
        try:
            attributes = pool_data.get('attributes', {})
            
            # Get historical data for feature engineering
            historical_data = await self._get_pool_historical_data(pool_id, hours=168)  # 7 days
            
            # Calculate technical indicators
            rsi_14 = self._calculate_simple_rsi(historical_data, 
                                              self._safe_decimal(attributes.get('base_token_price_usd', 0)))
            
            # Normalize RSI to 0-1 range
            rsi_normalized = float(rsi_14) / 100.0
            
            # Calculate other features
            volume_24h = float(self._safe_decimal(attributes.get('volume_usd_h24', 0)))
            liquidity = float(self._safe_decimal(attributes.get('reserve_in_usd', 0)))
            
            # Calculate advanced features
            macd_signal = self._calculate_macd(historical_data, self._safe_decimal(attributes.get('base_token_price_usd', 0)))
            bollinger_position = self._calculate_bollinger_position(historical_data, self._safe_decimal(attributes.get('base_token_price_usd', 0)))
            volume_sma_ratio = self._calculate_volume_sma_ratio(historical_data, volume_24h)
            
            # Liquidity features
            liquidity_stability = self._calculate_liquidity_stability(historical_data)
            liquidity_growth_rate = self._calculate_liquidity_growth_rate(historical_data)
            
            # Activity features
            activity_metrics = self._calculate_activity_metrics(attributes, historical_data)
            
            # Temporal features
            hour_of_day = current_time.hour
            day_of_week = current_time.weekday()
            is_weekend = day_of_week >= 5
            
            # Create feature vector
            feature_vector = {
                'pool_id': pool_id,
                'timestamp': timestamp,
                'feature_set_version': 'v1.0',
                
                # Technical indicators
                'rsi_14': Decimal(str(rsi_normalized)),
                'macd_signal': macd_signal,
                'bollinger_position': bollinger_position,
                'volume_sma_ratio': volume_sma_ratio,
                
                # Liquidity features
                'liquidity_stability': liquidity_stability,
                'liquidity_growth_rate': liquidity_growth_rate,
                'depth_imbalance': activity_metrics.get('depth_imbalance', Decimal('0.5')),
                
                # Activity features
                'trader_diversity_score': activity_metrics.get('trader_diversity', Decimal('0.5')),
                'whale_activity_indicator': activity_metrics.get('whale_activity', Decimal('0')),
                'retail_activity_score': activity_metrics.get('retail_activity', Decimal('0.5')),
                
                # Market structure features
                'bid_ask_spread_normalized': activity_metrics.get('spread_normalized', Decimal('0.01')),
                'market_impact_score': activity_metrics.get('market_impact', Decimal('0.5')),
                'arbitrage_opportunity': activity_metrics.get('arbitrage_score', Decimal('0')),
                
                # Temporal features
                'hour_of_day': hour_of_day,
                'day_of_week': day_of_week,
                'is_weekend': is_weekend,
                
                # Target variables (to be calculated later)
                'price_return_1h': None,
                'price_return_4h': None,
                'price_return_24h': None,
                'volume_change_1h': None,
                
                # Risk indicators
                'drawdown_risk': Decimal('0.1'),  # Placeholder
                'volatility_regime': 'medium',  # Placeholder
                
                # Feature vector as JSON
                'feature_vector_json': {
                    'technical': [float(rsi_normalized)],
                    'liquidity': [liquidity],
                    'volume': [volume_24h],
                    'temporal': [hour_of_day, day_of_week, int(is_weekend)]
                },
                
                'created_at': current_time
            }
            
            return feature_vector
            
        except Exception as e:
            self.logger.error(f"Error creating feature vector: {e}")
            return None
    
    async def _store_feature_vector(self, feature_data: Dict) -> None:
        """Store feature vector."""
        try:
            feature_vector = PoolFeatureVector(**feature_data)
            
            # Store using database manager
            with self.db_manager.connection.get_session() as session:
                session.add(feature_vector)
                session.commit()
            
            self.logger.debug(f"Stored feature vector for pool: {feature_data['pool_id']}")
            
        except Exception as e:
            self.logger.error(f"Error storing feature vector: {e}")
            raise
    
    async def _process_auto_watchlist(self, pools_data: List[Dict]) -> int:
        """
        Process pools for auto-watchlist integration based on signal analysis.
        
        Args:
            pools_data: List of pool data from API
            
        Returns:
            Number of pools added to watchlist
        """
        if not self.auto_watchlist_enabled or not hasattr(self, 'signal_analyzer'):
            return 0
        
        watchlist_additions = 0
        
        for pool_data in pools_data:
            try:
                # Analyze pool signals
                signal_result = await self._analyze_pool_signals(pool_data)
                
                if signal_result and self.signal_analyzer.should_add_to_watchlist(signal_result):
                    success = await self._handle_auto_watchlist(pool_data, signal_result)
                    if success:
                        watchlist_additions += 1
                        
            except Exception as e:
                self.logger.error(f"Error processing auto-watchlist for pool {pool_data.get('id')}: {e}")
                continue
        
        return watchlist_additions
    
    async def _analyze_pool_signals(self, pool_data: Dict) -> Optional[Any]:
        """
        Analyze pool signals using the signal analyzer.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            SignalResult or None if analysis fails
        """
        try:
            # Get historical data for better signal analysis
            pool_id = pool_data.get('id')
            historical_data = await self._get_pool_historical_data(pool_id, hours=24) if pool_id else []
            
            # Analyze signals - pass attributes as the analyzer expects flattened data
            attributes = pool_data.get('attributes', {})
            signal_result = self.signal_analyzer.analyze_pool_signals(attributes, historical_data)
            
            return signal_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing pool signals: {e}")
            return None
    
    async def _handle_auto_watchlist(self, pool_data: Dict, signal_result: Any) -> bool:
        """
        Handle auto-addition of pool to watchlist based on signal strength.
        
        Args:
            pool_data: Pool data from API
            signal_result: Signal analysis result
            
        Returns:
            True if successfully added to watchlist
        """
        try:
            pool_id = pool_data.get('id')
            if not pool_id:
                return False
            
            # Check if pool is already in watchlist
            if hasattr(self.db_manager, 'is_pool_in_watchlist'):
                if await self.db_manager.is_pool_in_watchlist(pool_id):
                    self.logger.debug(f"Pool {pool_id} already in watchlist")
                    return False
            
            # Extract pool information
            attributes = pool_data.get('attributes', {})
            
            # Extract token symbols
            base_symbol = self._extract_token_symbol(attributes, 'base')
            quote_symbol = self._extract_token_symbol(attributes, 'quote')
            token_symbol = f"{base_symbol}/{quote_symbol}" if base_symbol and quote_symbol else base_symbol or f"POOL_{pool_id[:8]}"
            
            # Create watchlist entry with enhanced metadata
            watchlist_data = {
                'pool_id': pool_id,
                'token_symbol': token_symbol,
                'token_name': attributes.get('name', f"Pool {pool_id[:8]}..."),
                'network_address': attributes.get('address', ''),
                'is_active': True,
                'metadata_json': {
                    'auto_added': True,
                    'signal_score': float(signal_result.signal_score),
                    'volume_trend': signal_result.volume_trend,
                    'liquidity_trend': signal_result.liquidity_trend,
                    'momentum_indicator': float(signal_result.momentum_indicator),
                    'activity_score': float(signal_result.activity_score),
                    'volatility_score': float(signal_result.volatility_score),
                    'added_at': datetime.now().isoformat(),
                    'source': 'enhanced_new_pools_collector',
                    'network': self.network,
                    'collection_interval': self.collection_intervals[0] if self.collection_intervals else '1h',
                    'signals': signal_result.signals
                }
            }
            
            # Add to watchlist
            if hasattr(self.db_manager, 'add_to_watchlist'):
                await self.db_manager.add_to_watchlist(watchlist_data)
                
                # Generate alert message
                alert_message = self.signal_analyzer.generate_alert_message(pool_id, signal_result)
                self.logger.info(f"🎯 Auto-watchlist: {alert_message}")
                
                return True
            else:
                self.logger.warning("Watchlist functionality not available in database manager")
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling auto-watchlist for pool {pool_data.get('id')}: {e}")
            return False
    
    async def _update_qlib_data(self) -> None:
        """Update QLib data exports."""
        if not self.qlib_integration:
            return
        
        try:
            # This would trigger QLib data export process
            # Implementation depends on your QLib setup
            self.logger.info("QLib data update triggered")
            
        except Exception as e:
            self.logger.error(f"Error updating QLib data: {e}")
    
    def _safe_decimal(self, value, default=None) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or value == '':
            return default
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0) -> int:
        """Safely convert value to int."""
        if value is None or value == '':
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    def _extract_token_symbol(self, attributes: Dict, token_type: str) -> Optional[str]:
        """Extract token symbol from attributes."""
        try:
            name = attributes.get('name', '')
            if name and '/' in name:
                parts = name.split('/')
                if token_type == 'base' and len(parts) > 0:
                    return parts[0].strip().upper()
                elif token_type == 'quote' and len(parts) > 1:
                    return parts[1].strip().upper()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting {token_type} token symbol: {e}")
            return None