#!/usr/bin/env python3
"""
Test suite for QLib OHLCV and Trade data export integration
Verifies QLib bin export includes OHLCV and trade data properly
"""

import pytest
import asyncio
import asyncpg
import os
import struct
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import uuid
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestQLIBOHLCVTradeExport:
    """Test QLib export integration with OHLCV and Trade data"""
    
    @pytest.fixture
    async def db_connection(self):
        """Create database connection for testing"""
        try:
            conn = await asyncpg.connect(
                host="localhost",
                port=5432,
                user="postgres",
                password="password",
                database="geckoterminal_data"
            )
            yield conn
        finally:
            await conn.close()
    
    @pytest.fixture
    def test_qlib_dir(self):
        """Create temporary QLib directory"""
        temp_dir = tempfile.mkdtemp(prefix="qlib_test_")
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def test_pool_data(self):
        """Generate test pool data"""
        pool_id = f"test_pool_{uuid.uuid4().hex[:8]}"
        base_timestamp = int(datetime.now(timezone.utc).timestamp()) - 86400  # 24 hours ago
        
        return {
            'pool_id': pool_id,
            'symbol': f"TEST_{uuid.uuid4().hex[:4].upper()}",
            'base_timestamp': base_timestamp,
            'timestamps': [base_timestamp + (i * 3600) for i in range(24)]  # 24 hourly intervals
        }
    
    async def setup_test_data(self, db_connection, test_pool_data):
        """Setup comprehensive test data for OHLCV and trades"""
        logger.info("Setting up test data for QLib export...")
        
        pool_id = test_pool_data['pool_id']
        timestamps = test_pool_data['timestamps']
        
        # Generate OHLCV data
        ohlcv_records = []
        for i, timestamp in enumerate(timestamps):
            base_price = Decimal('1.2000') + Decimal(str(i * 0.01))  # Trending upward
            ohlcv_records.append((
                pool_id,
                '1h',
                timestamp,
                datetime.fromtimestamp(timestamp, timezone.utc),
                base_price,  # open
                base_price + Decimal('0.005'),  # high
                base_price - Decimal('0.003'),  # low
                base_price + Decimal('0.002'),  # close
                Decimal('1000') + Decimal(str(i * 50)),  # volume
                (base_price + Decimal('0.002')) * (Decimal('1000') + Decimal(str(i * 50))),  # volume_usd
                datetime.now(timezone.utc)
            ))
        
        await db_connection.executemany("""
            INSERT INTO ohlcv_data (
                pool_id, timeframe, timestamp, datetime, open_price, high_price,
                low_price, close_price, volume, volume_usd, collected_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, ohlcv_records)
        
        # Generate trade data
        trade_records = []
        for i, timestamp in enumerate(timestamps):
            # Multiple trades per hour
            for j in range(3):  # 3 trades per hour
                trade_timestamp = timestamp + (j * 1200)  # 20 minutes apart
                price = Decimal('1.2000') + Decimal(str(i * 0.01)) + Decimal(str(j * 0.001))
                volume = Decimal('100') + Decimal(str(j * 25))
                
                trade_records.append((
                    pool_id,
                    f"trade_{i}_{j}_{uuid.uuid4().hex[:8]}",
                    trade_timestamp,
                    datetime.fromtimestamp(trade_timestamp, timezone.utc),
                    price,
                    price * volume,  # volume_usd
                    volume,  # amount_in
                    price * volume,  # amount_out
                    'buy' if j % 2 == 0 else 'sell',
                    f"0x{uuid.uuid4().hex[:40]}",
                    datetime.now(timezone.utc)
                ))
        
        await db_connection.executemany("""
            INSERT INTO trade_data (
                pool_id, trade_id, timestamp, datetime, price_usd, volume_usd,
                amount_in, amount_out, trade_type, trader_address, collected_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, trade_records)
        
        logger.info(f"✅ Test data setup complete: {len(ohlcv_records)} OHLCV records, {len(trade_records)} trade records")
        return len(ohlcv_records), len(trade_records)
    
    async def test_qlib_data_query_integration(self, db_connection, test_pool_data):
        """Test QLib export queries include OHLCV and trade data"""
        logger.info("Testing QLib data query integration...")
        
        await self.setup_test_data(db_connection, test_pool_data)
        pool_id = test_pool_data['pool_id']
        
        # Test OHLCV query for QLib export
        ohlcv_query = """
        SELECT 
            pool_id as symbol,
            timestamp,
            open_price as open,
            high_price as high,
            low_price as low,
            close_price as close,
            volume,
            volume_usd
        FROM ohlcv_data 
        WHERE pool_id = $1 
        ORDER BY timestamp ASC
        """
        
        ohlcv_data = await db_connection.fetch(ohlcv_query, pool_id)
        assert len(ohlcv_data) == 24, f"Expected 24 OHLCV records, got {len(ohlcv_data)}"
        
        # Verify OHLCV data structure
        first_record = ohlcv_data[0]
        assert 'symbol' in first_record
        assert 'timestamp' in first_record
        assert 'open' in first_record
        assert 'high' in first_record
        assert 'low' in first_record
        assert 'close' in first_record
        assert 'volume' in first_record
        assert 'volume_usd' in first_record
        logger.info("✅ OHLCV query structure validated for QLib export")
        
        # Test trade data aggregation query for QLib export
        trade_agg_query = """
        SELECT 
            pool_id as symbol,
            DATE_TRUNC('hour', datetime) as hour_bucket,
            COUNT(*) as trade_count,
            SUM(volume_usd) as total_volume_usd,
            AVG(price_usd) as avg_price,
            COUNT(DISTINCT trader_address) as unique_traders,
            SUM(CASE WHEN trade_type = 'buy' THEN volume_usd ELSE 0 END) as buy_volume,
            SUM(CASE WHEN trade_type = 'sell' THEN volume_usd ELSE 0 END) as sell_volume
        FROM trade_data 
        WHERE pool_id = $1 
        GROUP BY pool_id, DATE_TRUNC('hour', datetime)
        ORDER BY hour_bucket ASC
        """
        
        trade_agg_data = await db_connection.fetch(trade_agg_query, pool_id)
        assert len(trade_agg_data) == 24, f"Expected 24 hourly trade aggregations, got {len(trade_agg_data)}"
        
        # Verify trade aggregation structure
        first_agg = trade_agg_data[0]
        assert first_agg['trade_count'] == 3  # 3 trades per hour
        assert first_agg['unique_traders'] == 3  # Each trade has unique trader
        assert first_agg['buy_volume'] > 0
        assert first_agg['sell_volume'] > 0
        logger.info("✅ Trade aggregation query validated for QLib export")
        
        # Test combined OHLCV + Trade features query
        combined_query = """
        SELECT 
            o.pool_id as symbol,
            o.timestamp,
            o.open_price as open,
            o.high_price as high,
            o.low_price as low,
            o.close_price as close,
            o.volume as ohlcv_volume,
            o.volume_usd as ohlcv_volume_usd,
            COALESCE(t.trade_count, 0) as trade_count,
            COALESCE(t.unique_traders, 0) as unique_traders,
            COALESCE(t.buy_volume, 0) as buy_volume,
            COALESCE(t.sell_volume, 0) as sell_volume,
            COALESCE(t.avg_price, o.close_price) as trade_avg_price
        FROM ohlcv_data o
        LEFT JOIN (
            SELECT 
                pool_id,
                DATE_TRUNC('hour', datetime) as hour_bucket,
                COUNT(*) as trade_count,
                COUNT(DISTINCT trader_address) as unique_traders,
                SUM(CASE WHEN trade_type = 'buy' THEN volume_usd ELSE 0 END) as buy_volume,
                SUM(CASE WHEN trade_type = 'sell' THEN volume_usd ELSE 0 END) as sell_volume,
                AVG(price_usd) as avg_price
            FROM trade_data 
            WHERE pool_id = $1
            GROUP BY pool_id, DATE_TRUNC('hour', datetime)
        ) t ON o.pool_id = t.pool_id AND DATE_TRUNC('hour', o.datetime) = t.hour_bucket
        WHERE o.pool_id = $1
        ORDER BY o.timestamp ASC
        """
        
        combined_data = await db_connection.fetch(combined_query, pool_id)
        assert len(combined_data) == 24, f"Expected 24 combined records, got {len(combined_data)}"
        
        # Verify combined data has both OHLCV and trade features
        first_combined = combined_data[0]
        assert first_combined['open'] is not None
        assert first_combined['trade_count'] == 3
        assert first_combined['unique_traders'] == 3
        logger.info("✅ Combined OHLCV + Trade query validated for QLib export")
        
        return ohlcv_data, trade_agg_data, combined_data
    
    async def test_qlib_bin_file_generation(self, db_connection, test_pool_data, test_qlib_dir):
        """Test QLib bin file generation with OHLCV and trade data"""
        logger.info("Testing QLib bin file generation...")
        
        ohlcv_data, trade_agg_data, combined_data = await self.test_qlib_data_query_integration(
            db_connection, test_pool_data
        )
        
        # Create QLib directory structure
        qlib_dir = Path(test_qlib_dir)
        features_dir = qlib_dir / "features"
        calendars_dir = qlib_dir / "calendars"
        instruments_dir = qlib_dir / "instruments"
        
        features_dir.mkdir(parents=True, exist_ok=True)
        calendars_dir.mkdir(parents=True, exist_ok=True)
        instruments_dir.mkdir(parents=True, exist_ok=True)
        
        symbol = test_pool_data['symbol']
        symbol_dir = features_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        
        # Generate calendar file
        calendar_file = calendars_dir / "60min.txt"
        with open(calendar_file, 'w') as f:
            for record in combined_data:
                dt = datetime.fromtimestamp(record['timestamp'], timezone.utc)
                f.write(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        logger.info(f"✅ Calendar file created: {calendar_file}")
        
        # Generate instruments file
        instruments_file = instruments_dir / "all.txt"
        with open(instruments_file, 'w') as f:
            f.write(f"{symbol}\n")
        
        logger.info(f"✅ Instruments file created: {instruments_file}")
        
        # Generate bin files for OHLCV data
        ohlcv_features = ['open', 'high', 'low', 'close', 'ohlcv_volume', 'ohlcv_volume_usd']
        for feature in ohlcv_features:
            bin_file = symbol_dir / f"{feature}.60min.bin"
            with open(bin_file, 'wb') as f:
                for record in combined_data:
                    value = float(record[feature]) if record[feature] is not None else 0.0
                    f.write(struct.pack('<f', value))  # Little-endian float
            
            logger.info(f"✅ OHLCV bin file created: {bin_file}")
        
        # Generate bin files for trade features
        trade_features = ['trade_count', 'unique_traders', 'buy_volume', 'sell_volume']
        for feature in trade_features:
            bin_file = symbol_dir / f"{feature}.60min.bin"
            with open(bin_file, 'wb') as f:
                for record in combined_data:
                    value = float(record[feature]) if record[feature] is not None else 0.0
                    f.write(struct.pack('<f', value))
            
            logger.info(f"✅ Trade bin file created: {bin_file}")
        
        # Verify bin files were created correctly
        expected_files = ohlcv_features + trade_features
        created_files = list(symbol_dir.glob("*.60min.bin"))
        
        assert len(created_files) == len(expected_files), f"Expected {len(expected_files)} bin files, found {len(created_files)}"
        
        # Verify bin file contents
        open_bin_file = symbol_dir / "open.60min.bin"
        with open(open_bin_file, 'rb') as f:
            data = f.read()
            expected_size = len(combined_data) * 4  # 4 bytes per float
            assert len(data) == expected_size, f"Expected {expected_size} bytes, got {len(data)}"
            
            # Read first value and verify
            f.seek(0)
            first_value = struct.unpack('<f', f.read(4))[0]
            expected_first_value = float(combined_data[0]['open'])
            assert abs(first_value - expected_first_value) < 0.001, f"Expected {expected_first_value}, got {first_value}"
        
        logger.info("✅ QLib bin file generation and verification complete")
        
        return {
            'qlib_dir': qlib_dir,
            'symbol': symbol,
            'calendar_file': calendar_file,
            'instruments_file': instruments_file,
            'bin_files': created_files,
            'record_count': len(combined_data)
        }
    
    async def test_qlib_export_metadata_tracking(self, db_connection, test_pool_data, test_qlib_dir):
        """Test QLib export metadata tracking in database"""
        logger.info("Testing QLib export metadata tracking...")
        
        export_result = await self.test_qlib_bin_file_generation(db_connection, test_pool_data, test_qlib_dir)
        
        # Create export metadata record
        export_metadata = {
            'export_name': f"test_export_{uuid.uuid4().hex[:8]}",
            'export_type': 'ohlcv_trade_combined',
            'start_timestamp': test_pool_data['timestamps'][0],
            'end_timestamp': test_pool_data['timestamps'][-1],
            'networks': ['test_network'],
            'min_liquidity_usd': Decimal('1000.0'),
            'min_volume_usd': Decimal('500.0'),
            'pool_count': 1,
            'file_path': str(export_result['qlib_dir']),
            'file_size_bytes': sum(f.stat().st_size for f in export_result['bin_files']),
            'record_count': export_result['record_count'],
            'qlib_config_json': {
                'frequency': '60min',
                'features': ['open', 'high', 'low', 'close', 'ohlcv_volume', 'ohlcv_volume_usd', 
                           'trade_count', 'unique_traders', 'buy_volume', 'sell_volume'],
                'calendar': '60min.txt',
                'instruments': 'all.txt'
            },
            'feature_columns': ['ohlcv_features', 'trade_features'],
            'status': 'completed',
            'error_message': None
        }
        
        # Insert export metadata
        insert_query = """
        INSERT INTO qlib_data_exports (
            export_name, export_type, start_timestamp, end_timestamp, networks,
            min_liquidity_usd, min_volume_usd, pool_count, file_path, file_size_bytes,
            record_count, qlib_config_json, feature_columns, status, error_message,
            created_at, completed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING id
        """
        
        export_id = await db_connection.fetchval(
            insert_query,
            export_metadata['export_name'], export_metadata['export_type'],
            export_metadata['start_timestamp'], export_metadata['end_timestamp'],
            json.dumps(export_metadata['networks']), export_metadata['min_liquidity_usd'],
            export_metadata['min_volume_usd'], export_metadata['pool_count'],
            export_metadata['file_path'], export_metadata['file_size_bytes'],
            export_metadata['record_count'], json.dumps(export_metadata['qlib_config_json']),
            json.dumps(export_metadata['feature_columns']), export_metadata['status'],
            export_metadata['error_message'], datetime.now(timezone.utc), datetime.now(timezone.utc)
        )
        
        assert export_id is not None
        logger.info(f"✅ Export metadata created with ID: {export_id}")
        
        # Verify export metadata
        select_query = "SELECT * FROM qlib_data_exports WHERE id = $1"
        export_record = await db_connection.fetchrow(select_query, export_id)
        
        assert export_record is not None
        assert export_record['export_type'] == 'ohlcv_trade_combined'
        assert export_record['record_count'] == export_result['record_count']
        assert export_record['status'] == 'completed'
        
        # Verify QLib config JSON
        qlib_config = json.loads(export_record['qlib_config_json'])
        assert 'ohlcv_volume' in qlib_config['features']
        assert 'trade_count' in qlib_config['features']
        assert qlib_config['frequency'] == '60min'
        
        logger.info("✅ Export metadata tracking validated")
        
        # Cleanup
        await db_connection.execute("DELETE FROM qlib_data_exports WHERE id = $1", export_id)
        
        return export_id, export_record
    
    async def test_qlib_health_check_integration(self, db_connection, test_pool_data, test_qlib_dir):
        """Test QLib health check with OHLCV and trade data"""
        logger.info("Testing QLib health check integration...")
        
        export_result = await self.test_qlib_bin_file_generation(db_connection, test_pool_data, test_qlib_dir)
        
        # Simulate QLib health check queries
        health_checks = {
            'ohlcv_data_completeness': """
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN open_price IS NOT NULL THEN 1 END) as valid_open,
                    COUNT(CASE WHEN high_price IS NOT NULL THEN 1 END) as valid_high,
                    COUNT(CASE WHEN low_price IS NOT NULL THEN 1 END) as valid_low,
                    COUNT(CASE WHEN close_price IS NOT NULL THEN 1 END) as valid_close,
                    COUNT(CASE WHEN volume > 0 THEN 1 END) as valid_volume
                FROM ohlcv_data WHERE pool_id = $1
            """,
            'trade_data_completeness': """
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(DISTINCT trader_address) as unique_traders,
                    COUNT(CASE WHEN price_usd > 0 THEN 1 END) as valid_prices,
                    COUNT(CASE WHEN volume_usd > 0 THEN 1 END) as valid_volumes
                FROM trade_data WHERE pool_id = $1
            """,
            'data_quality_metrics': """
                SELECT 
                    o.pool_id,
                    COUNT(o.id) as ohlcv_records,
                    COUNT(t.id) as trade_records,
                    AVG(o.volume_usd) as avg_ohlcv_volume,
                    AVG(t.volume_usd) as avg_trade_volume,
                    MIN(o.timestamp) as earliest_ohlcv,
                    MAX(o.timestamp) as latest_ohlcv,
                    MIN(t.timestamp) as earliest_trade,
                    MAX(t.timestamp) as latest_trade
                FROM ohlcv_data o
                FULL OUTER JOIN trade_data t ON o.pool_id = t.pool_id
                WHERE o.pool_id = $1 OR t.pool_id = $1
                GROUP BY o.pool_id
            """
        }
        
        pool_id = test_pool_data['pool_id']
        health_results = {}
        
        for check_name, query in health_checks.items():
            result = await db_connection.fetchrow(query, pool_id)
            health_results[check_name] = dict(result) if result else {}
            logger.info(f"✅ Health check '{check_name}' completed")
        
        # Validate health check results
        ohlcv_health = health_results['ohlcv_data_completeness']
        assert ohlcv_health['total_records'] == 24
        assert ohlcv_health['valid_open'] == 24
        assert ohlcv_health['valid_volume'] == 24
        
        trade_health = health_results['trade_data_completeness']
        assert trade_health['total_trades'] == 72  # 24 hours * 3 trades per hour
        assert trade_health['unique_traders'] == 72  # Each trade has unique trader
        assert trade_health['valid_prices'] == 72
        
        quality_metrics = health_results['data_quality_metrics']
        assert quality_metrics['ohlcv_records'] == 24
        assert quality_metrics['trade_records'] == 72
        assert quality_metrics['avg_ohlcv_volume'] > 0
        assert quality_metrics['avg_trade_volume'] > 0
        
        logger.info("✅ QLib health check integration validated")
        
        # Verify bin file integrity
        bin_files_health = {}
        for bin_file in export_result['bin_files']:
            file_size = bin_file.stat().st_size
            expected_size = export_result['record_count'] * 4  # 4 bytes per float
            
            bin_files_health[bin_file.name] = {
                'file_size': file_size,
                'expected_size': expected_size,
                'integrity_ok': file_size == expected_size
            }
        
        # All bin files should have correct size
        integrity_issues = [name for name, health in bin_files_health.items() if not health['integrity_ok']]
        assert len(integrity_issues) == 0, f"Bin file integrity issues: {integrity_issues}"
        
        logger.info("✅ Bin file integrity check passed")
        
        return health_results, bin_files_health
    
    async def cleanup_test_data(self, db_connection, test_pool_data):
        """Clean up test data"""
        pool_id = test_pool_data['pool_id']
        
        await db_connection.execute("DELETE FROM trade_data WHERE pool_id = $1", pool_id)
        await db_connection.execute("DELETE FROM ohlcv_data WHERE pool_id = $1", pool_id)
        
        logger.info("✅ Test data cleanup completed")

async def run_tests():
    """Run all QLib OHLCV/Trade export tests"""
    test_instance = TestQLIBOHLCVTradeExport()
    
    async with asyncpg.create_pool(
        host="localhost",
        port=5432,
        user="postgres",
        password="password",
        database="geckoterminal_data",
        min_size=1,
        max_size=5
    ) as pool:
        async with pool.acquire() as conn:
            # Create test fixtures
            test_pool_data = {
                'pool_id': f"test_pool_{uuid.uuid4().hex[:8]}",
                'symbol': f"TEST_{uuid.uuid4().hex[:4].upper()}",
                'base_timestamp': int(datetime.now(timezone.utc).timestamp()) - 86400,
                'timestamps': []
            }
            
            base_timestamp = test_pool_data['base_timestamp']
            test_pool_data['timestamps'] = [base_timestamp + (i * 3600) for i in range(24)]
            
            temp_dir = tempfile.mkdtemp(prefix="qlib_test_")
            
            try:
                logger.info("🧪 Starting QLib OHLCV/Trade Export Test Suite")
                
                await test_instance.test_qlib_data_query_integration(conn, test_pool_data)
                await test_instance.test_qlib_bin_file_generation(conn, test_pool_data, temp_dir)
                await test_instance.test_qlib_export_metadata_tracking(conn, test_pool_data, temp_dir)
                await test_instance.test_qlib_health_check_integration(conn, test_pool_data, temp_dir)
                
                logger.info("🎉 All QLib OHLCV/Trade export tests passed!")
                return True
                
            except Exception as e:
                logger.error(f"❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
            finally:
                await test_instance.cleanup_test_data(conn, test_pool_data)
                shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)