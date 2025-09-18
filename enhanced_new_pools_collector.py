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
        super().__init__(config, db_manager, network, **kwargs)
        
        # Collection interval configuration
        self.collection_intervals = kwargs.get('collection_intervals', ['1h'])
        self.enable_feature_engineering = kwargs.get('enable_feature_engineering', True)
        self.qlib_integration = kwargs.get('qlib_integration', True)
        
        # Feature engineering configuration
        self.lookback_periods = {
            'short': 24,   # 24 hours
            'medium': 168, # 7 days
            'long': 720    # 30 days
        }
        
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
                    'qlib_integration_enabled': self.qlib_integration
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
                'volume_usd_interval': self._safe_decimal(attributes.get('volume_usd_h24')),  # Placeholder
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
            
            # Technical indicators (simplified implementations)
            rsi = self._calculate_simple_rsi(historical_data, current_price)
            trend_strength = min(abs(price_change_h24 or 0), 100)
            
            return {
                'buy_sell_ratio_interval': buy_sell_ratio_h24,
                'buy_sell_ratio_h24': buy_sell_ratio_h24,
                'volume_weighted_price': vwap,
                'price_volatility': volatility,
                'liquidity_change_percentage': liquidity_change,
                'liquidity_depth_usd': current_liquidity,
                'trend_strength': trend_strength,
                'relative_strength_index': rsi,
                'moving_average_convergence': Decimal('0'),  # Placeholder
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
                'macd_signal': Decimal('0'),  # Placeholder
                'bollinger_position': Decimal('0.5'),  # Placeholder
                'volume_sma_ratio': Decimal('1.0'),  # Placeholder
                
                # Liquidity features
                'liquidity_stability': Decimal('0.5'),  # Placeholder
                'liquidity_growth_rate': Decimal('0'),  # Placeholder
                'depth_imbalance': Decimal('0.5'),  # Placeholder
                
                # Activity features
                'trader_diversity_score': Decimal('0.5'),  # Placeholder
                'whale_activity_indicator': Decimal('0'),  # Placeholder
                'retail_activity_score': Decimal('0.5'),  # Placeholder
                
                # Market structure features
                'bid_ask_spread_normalized': Decimal('0.01'),  # Placeholder
                'market_impact_score': Decimal('0.5'),  # Placeholder
                'arbitrage_opportunity': Decimal('0'),  # Placeholder
                
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