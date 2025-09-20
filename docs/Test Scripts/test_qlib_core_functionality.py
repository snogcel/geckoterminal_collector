"""
Core QLib integration functionality test - bypassing potentially corrupted files.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_technical_indicators():
    """Test technical indicator calculations directly."""
    try:
        logger.info("🧪 Testing Technical Indicators...")
        
        # Import the enhanced collector class directly
        import sys
        import os
        sys.path.append(os.getcwd())
        
        from enhanced_new_pools_collector import EnhancedNewPoolsCollector
        
        # Create a minimal mock setup
        class MockConfig:
            def __init__(self):
                self.api = MockAPIConfig()
                self.error_handling = MockErrorHandling()
        
        class MockAPIConfig:
            def __init__(self):
                self.rate_limit_delay = 0.1
                self.max_retries = 3
        
        class MockErrorHandling:
            def __init__(self):
                self.max_retries = 3
                self.backoff_factor = 1.0
        
        class MockDBManager:
            pass
        
        # Create collector instance
        config = MockConfig()
        collector = EnhancedNewPoolsCollector(
            config=config,
            db_manager=MockDBManager(),
            network="solana"
        )
        
        # Test data
        test_data = [
            {'base_token_price_usd': 1.0, 'timestamp': 1000},
            {'base_token_price_usd': 1.1, 'timestamp': 2000},
            {'base_token_price_usd': 0.9, 'timestamp': 3000},
            {'base_token_price_usd': 1.2, 'timestamp': 4000},
            {'base_token_price_usd': 1.05, 'timestamp': 5000},
        ]
        
        # Test RSI calculation
        rsi = collector._calculate_simple_rsi(test_data, Decimal('1.1'))
        logger.info(f"✅ RSI calculation: {rsi}")
        assert isinstance(rsi, Decimal)
        assert 0 <= rsi <= 100
        
        # Test MACD calculation
        macd = collector._calculate_macd(test_data, Decimal('1.1'))
        logger.info(f"✅ MACD calculation: {macd}")
        assert isinstance(macd, Decimal)
        
        # Test EMA calculation
        prices = [Decimal(str(d['base_token_price_usd'])) for d in test_data]
        ema = collector._calculate_ema(prices, 3)
        logger.info(f"✅ EMA calculation: {ema}")
        assert isinstance(ema, Decimal)
        
        # Test Bollinger position
        bollinger = collector._calculate_bollinger_position(test_data, Decimal('1.1'))
        logger.info(f"✅ Bollinger position: {bollinger}")
        assert isinstance(bollinger, Decimal)
        assert 0 <= bollinger <= 1
        
        # Test volume SMA ratio
        volume_ratio = collector._calculate_volume_sma_ratio(test_data, 1000.0)
        logger.info(f"✅ Volume SMA ratio: {volume_ratio}")
        assert isinstance(volume_ratio, Decimal)
        
        # Test liquidity stability
        liquidity_data = [
            {'reserve_in_usd': 10000, 'timestamp': 1000},
            {'reserve_in_usd': 11000, 'timestamp': 2000},
            {'reserve_in_usd': 9500, 'timestamp': 3000},
            {'reserve_in_usd': 12000, 'timestamp': 4000},
        ]
        
        stability = collector._calculate_liquidity_stability(liquidity_data)
        logger.info(f"✅ Liquidity stability: {stability}")
        assert isinstance(stability, Decimal)
        assert 0 <= stability <= 1
        
        # Test activity metrics
        attributes = {
            'transactions_h24_buys': 100,
            'transactions_h24_sells': 80,
            'volume_usd_h24': 50000,
            'price_change_percentage_h24': 5.5
        }
        
        activity_metrics = collector._calculate_activity_metrics(attributes, test_data)
        logger.info(f"✅ Activity metrics: {list(activity_metrics.keys())}")
        
        expected_keys = [
            'trader_diversity', 'whale_activity', 'retail_activity',
            'depth_imbalance', 'market_impact', 'spread_normalized', 'arbitrage_score'
        ]
        
        for key in expected_keys:
            assert key in activity_metrics
            assert isinstance(activity_metrics[key], Decimal)
        
        logger.info("✅ All technical indicator tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Technical indicators test failed: {e}")
        return False


def test_qlib_data_processing():
    """Test QLib data processing functionality."""
    try:
        logger.info("🧪 Testing QLib Data Processing...")
        
        import pandas as pd
        import numpy as np
        from qlib_integration import QLibBinDataExporter
        
        # Mock database manager
        class MockDBManager:
            def __init__(self):
                self.connection = MockConnection()
        
        class MockConnection:
            def get_session(self):
                return MockSession()
        
        class MockSession:
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            
            def add(self, record):
                pass
            
            def commit(self):
                pass
        
        # Create test data
        test_data = pd.DataFrame([
            {
                'pool_id': 'test_pool_1',
                'datetime': datetime.now(),
                'qlib_symbol': 'TEST_POOL_1_SOLANA',
                'open_price_usd': 1.0,
                'high_price_usd': 1.1,
                'low_price_usd': 0.9,
                'close_price_usd': 1.05,
                'volume_usd_h24': 10000,
                'reserve_in_usd': 50000,
                'network_id': 'solana'
            },
            {
                'pool_id': 'test_pool_2',
                'datetime': datetime.now(),
                'qlib_symbol': 'TEST_POOL_2_SOLANA',
                'open_price_usd': 2.0,
                'high_price_usd': 2.2,
                'low_price_usd': 1.8,
                'close_price_usd': 2.1,
                'volume_usd_h24': 20000,
                'reserve_in_usd': 100000,
                'network_id': 'solana'
            }
        ])
        
        # Create exporter
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = QLibBinDataExporter(
                db_manager=MockDBManager(),
                qlib_dir=temp_dir,
                freq="60min"
            )
            
            # Test data processing
            processed_data = exporter._process_for_qlib_bin(test_data)
            logger.info(f"✅ Data processing: {len(processed_data)} records")
            assert len(processed_data) == 2
            assert 'symbol' in processed_data.columns
            assert 'date' in processed_data.columns
            
            # Test instruments preparation
            instruments_data = exporter._prepare_instruments_data(processed_data)
            logger.info(f"✅ Instruments data: {len(instruments_data)} instruments")
            assert len(instruments_data) == 2
            
            # Test calendar creation
            calendar_list = sorted(processed_data['datetime'].unique())
            calendar_timestamps = [pd.Timestamp(dt) for dt in calendar_list]
            logger.info(f"✅ Calendar creation: {len(calendar_timestamps)} entries")
            
            # Test data alignment
            for symbol, symbol_data in processed_data.groupby('symbol'):
                aligned_data = exporter._align_data_with_calendar(symbol_data, calendar_timestamps)
                logger.info(f"✅ Data alignment for {symbol}: {len(aligned_data)} records")
                assert not aligned_data.empty
        
        logger.info("✅ All QLib data processing tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ QLib data processing test failed: {e}")
        return False


def test_enhanced_model_structure():
    """Test enhanced model structure."""
    try:
        logger.info("🧪 Testing Enhanced Model Structure...")
        
        from enhanced_new_pools_history_model import (
            EnhancedNewPoolsHistory, PoolFeatureVector, QLibDataExport
        )
        
        # Test model creation
        now = datetime.now()
        timestamp = int(now.timestamp())
        
        # Test EnhancedNewPoolsHistory
        history_record = EnhancedNewPoolsHistory(
            pool_id='test_pool_1',
            timestamp=timestamp,
            datetime=now,
            collection_interval='1h',
            network_id='solana',
            open_price_usd=Decimal('1.0'),
            high_price_usd=Decimal('1.1'),
            low_price_usd=Decimal('0.9'),
            close_price_usd=Decimal('1.05'),
            volume_usd_h24=Decimal('10000'),
            qlib_symbol='TEST_POOL_1_SOLANA',
            data_quality_score=Decimal('85.0')
        )
        
        logger.info(f"✅ EnhancedNewPoolsHistory created: {history_record.pool_id}")
        assert history_record.pool_id == 'test_pool_1'
        assert history_record.qlib_symbol == 'TEST_POOL_1_SOLANA'
        
        # Test PoolFeatureVector
        feature_vector = PoolFeatureVector(
            pool_id='test_pool_1',
            timestamp=timestamp,
            feature_set_version='v1.0',
            rsi_14=Decimal('0.6'),
            macd_signal=Decimal('0.1'),
            liquidity_stability=Decimal('0.8')
        )
        
        logger.info(f"✅ PoolFeatureVector created: {feature_vector.pool_id}")
        assert feature_vector.feature_set_version == 'v1.0'
        
        # Test QLibDataExport
        export_record = QLibDataExport(
            export_name='test_export',
            export_type='training',
            start_timestamp=timestamp,
            end_timestamp=timestamp + 3600,
            pool_count=100,
            status='completed'
        )
        
        logger.info(f"✅ QLibDataExport created: {export_record.export_name}")
        assert export_record.export_type == 'training'
        
        logger.info("✅ All enhanced model structure tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced model structure test failed: {e}")
        return False


async def run_core_tests():
    """Run core functionality tests."""
    logger.info("🚀 Starting Core QLib Integration Tests")
    
    test_results = {}
    
    # Run tests
    test_results['technical_indicators'] = test_technical_indicators()
    test_results['qlib_data_processing'] = test_qlib_data_processing()
    test_results['enhanced_model_structure'] = test_enhanced_model_structure()
    
    # Summary
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    logger.info(f"\n📊 Core Test Results Summary:")
    logger.info(f"   Passed: {passed_tests}/{total_tests}")
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
    
    if passed_tests == total_tests:
        logger.info("🎉 All core tests passed! QLib integration core functionality is working.")
        return True
    else:
        logger.info("⚠️  Some core tests failed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_core_tests())
    exit(0 if success else 1)