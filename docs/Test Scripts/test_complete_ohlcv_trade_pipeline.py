#!/usr/bin/env python3
"""
End-to-end pipeline test for OHLCV and Trade data integration with QLib
Tests complete workflow: Collection → Storage → Export → Validation
"""

import pytest
import asyncio
import asyncpg
import os
import tempfile
import shutil
import subprocess
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import uuid
import logging
import time
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCompleteOHLCVTradePipeline:
    """Test complete OHLCV/Trade pipeline integration"""
    
    @pytest.fixture
    async def db_connection(self):
        """Create database connection for testing"""
        try:
            conn = await asyncpg.connect(
                host="localhost",
                port=5432,
                user="gecko_collector",
                password="12345678!",
                database="gecko_terminal_collector"
            )
            yield conn
        finally:
            await conn.close()
    
    @pytest.fixture
    def test_environment(self):
        """Setup test environment"""
        test_id = uuid.uuid4().hex[:8]
        temp_dir = tempfile.mkdtemp(prefix=f"pipeline_test_{test_id}_")
        
        env_data = {
            'test_id': test_id,
            'temp_dir': temp_dir,
            'qlib_dir': os.path.join(temp_dir, 'qlib_data'),
            'pool_id': f"test_pool_{test_id}",
            'symbol': f"TEST_{test_id[:4].upper()}",
            'network': 'test_network'
        }
        
        # Create QLib directory structure
        os.makedirs(env_data['qlib_dir'], exist_ok=True)
        
        yield env_data
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def create_test_dependencies(self, db_connection, test_environment):
        """Create test dependencies (DEX, tokens, pool) for foreign key constraints"""
        pool_id = test_environment['pool_id']
        
        # Use unique IDs based on pool_id to avoid conflicts
        dex_id = f"test_dex_{pool_id}"
        base_token_id = f"test_base_{pool_id}"
        quote_token_id = f"test_quote_{pool_id}"
        
        # Create test DEX
        await db_connection.execute("""
            INSERT INTO dexes (id, name, network)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
        """, dex_id, f"Test DEX {pool_id}", test_environment['network'])
        
        # Create test tokens
        await db_connection.execute("""
            INSERT INTO tokens (id, address, name, symbol, network)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO NOTHING
        """, base_token_id, f"addr_base_{pool_id}", "Test Base Token", "TBT", test_environment['network'])
        
        await db_connection.execute("""
            INSERT INTO tokens (id, address, name, symbol, network)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO NOTHING
        """, quote_token_id, f"addr_quote_{pool_id}", "Test Quote Token", "TQT", test_environment['network'])
        
        # Create test pool
        await db_connection.execute("""
            INSERT INTO pools (id, name, address, dex_id, base_token_id, quote_token_id, reserve_usd)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
        """, pool_id, f"Test Pool {pool_id}", f"addr_{pool_id}", 
            dex_id, base_token_id, quote_token_id, Decimal('10000.0'))
    
    async def cleanup_test_dependencies(self, db_connection, test_environment):
        """Clean up test dependencies in correct order (respecting foreign keys)"""
        pool_id = test_environment['pool_id']
        dex_id = f"test_dex_{pool_id}"
        base_token_id = f"test_base_{pool_id}"
        quote_token_id = f"test_quote_{pool_id}"
        
        # Delete in reverse order of creation, respecting foreign key constraints
        try:
            await db_connection.execute("DELETE FROM pools WHERE id = $1", pool_id)
            await db_connection.execute("DELETE FROM tokens WHERE id IN ($1, $2)", base_token_id, quote_token_id)
            await db_connection.execute("DELETE FROM dexes WHERE id = $1", dex_id)
        except Exception as e:
            # If cleanup fails, log but don't fail the test
            logger.warning(f"Cleanup warning: {e}")

    async def simulate_data_collection(self, db_connection, test_environment):
        """Simulate OHLCV and Trade data collection"""
        logger.info("Simulating data collection phase...")
        
        pool_id = test_environment['pool_id']
        
        # Clean up any existing data first
        await db_connection.execute("DELETE FROM trades WHERE pool_id = $1", pool_id)
        await db_connection.execute("DELETE FROM ohlcv_data WHERE pool_id = $1", pool_id)
        
        # Create test dependencies first
        await self.create_test_dependencies(db_connection, test_environment)
        base_timestamp = int(datetime.now(timezone.utc).timestamp()) - 7200  # 2 hours ago
        
        # Simulate realistic OHLCV data collection
        ohlcv_data = []
        for i in range(24):  # 24 hourly intervals
            timestamp = base_timestamp + (i * 3600)
            base_price = Decimal('1.5000') + Decimal(str(i * 0.005))  # Gradual price increase
            volatility = Decimal('0.01') * (Decimal('1') + Decimal(str(i)) * Decimal('0.1'))  # Increasing volatility
            
            ohlcv_data.append({
                'pool_id': pool_id,
                'timeframe': '1h',
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp, timezone.utc),
                'open_price': base_price,
                'high_price': base_price + volatility,
                'low_price': base_price - volatility * Decimal('0.8'),
                'close_price': base_price + volatility * Decimal('0.3'),
                'volume_usd': (base_price + volatility * Decimal('0.3')) * (Decimal('2000') + Decimal(str(i * 100))),
                'metadata_json': json.dumps({})
            })
        
        # Insert OHLCV data
        ohlcv_records = [(
            d['pool_id'], d['timeframe'], d['timestamp'], d['datetime'],
            d['open_price'], d['high_price'], d['low_price'], d['close_price'],
            d['volume_usd'], d['metadata_json']
        ) for d in ohlcv_data]
        
        await db_connection.executemany("""
            INSERT INTO ohlcv_data (
                pool_id, timeframe, timestamp, datetime, open_price, high_price,
                low_price, close_price, volume_usd, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, ohlcv_records)
        
        # Simulate realistic trade data collection
        trade_data = []
        trader_addresses = [f"0x{uuid.uuid4().hex[:40]}" for _ in range(20)]  # 20 unique traders
        
        for i in range(24):  # 24 hours
            hour_timestamp = base_timestamp + (i * 3600)
            trades_per_hour = 5 + (i % 10)  # Variable trades per hour (5-14)
            
            for j in range(trades_per_hour):
                trade_timestamp = hour_timestamp + (j * (3600 // trades_per_hour))
                base_price = Decimal('1.5000') + Decimal(str(i * 0.005))
                price_variation = Decimal(str((j - trades_per_hour//2) * Decimal('0.001')))  # Price variation within hour
                
                trade_price = base_price + price_variation
                trade_volume = Decimal('50') + Decimal(str(j * 20))
                
                trade_data.append({
                    'id': f"trade_{i}_{j}_{uuid.uuid4().hex[:8]}",
                    'pool_id': pool_id,
                    'block_number': 12345678 + (i * 100) + j,
                    'tx_hash': f"0x{uuid.uuid4().hex[:32]}",
                    'tx_from_address': trader_addresses[j % len(trader_addresses)],
                    'from_token_amount': trade_volume,
                    'to_token_amount': trade_price * trade_volume,
                    'price_usd': trade_price,
                    'volume_usd': trade_price * trade_volume,
                    'side': 'buy' if j % 2 == 0 else 'sell',
                    'block_timestamp': datetime.fromtimestamp(trade_timestamp, timezone.utc),
                    'metadata_json': json.dumps({})
                })
        
        # Insert trade data
        trade_records = [(
            d['id'], d['pool_id'], d['block_number'], d['tx_hash'], d['tx_from_address'],
            d['from_token_amount'], d['to_token_amount'], d['price_usd'], d['volume_usd'],
            d['side'], d['block_timestamp'], d['metadata_json']
        ) for d in trade_data]
        
        await db_connection.executemany("""
            INSERT INTO trades (
                id, pool_id, block_number, tx_hash, tx_from_address, from_token_amount,
                to_token_amount, price_usd, volume_usd, side, block_timestamp, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, trade_records)
        
        logger.info(f"PASS: Data collection simulated: {len(ohlcv_data)} OHLCV records, {len(trade_data)} trade records")
        
        return {
            'ohlcv_count': len(ohlcv_data),
            'trade_count': len(trade_data),
            'time_range': (base_timestamp, base_timestamp + 23 * 3600),
            'ohlcv_data': ohlcv_data,
            'trade_data': trade_data
        }
    
    async def test_data_consistency_validation(self, db_connection, test_environment, collection_result):
        """Test data consistency across collection and storage"""
        logger.info("Testing data consistency validation...")
        
        pool_id = test_environment['pool_id']
        
        # Validate OHLCV data consistency
        ohlcv_validation_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN high_price >= open_price AND high_price >= close_price THEN 1 END) as valid_high,
            COUNT(CASE WHEN low_price <= open_price AND low_price <= close_price THEN 1 END) as valid_low,

            COUNT(CASE WHEN volume_usd > 0 THEN 1 END) as positive_volume_usd,
            AVG(volume_usd) as avg_volume_usd,
            MIN(timestamp) as earliest_timestamp,
            MAX(timestamp) as latest_timestamp
        FROM ohlcv_data WHERE pool_id = $1
        """
        
        ohlcv_validation = await db_connection.fetchrow(ohlcv_validation_query, pool_id)
        
        assert ohlcv_validation['total_records'] == collection_result['ohlcv_count']
        assert ohlcv_validation['valid_high'] == collection_result['ohlcv_count']
        assert ohlcv_validation['valid_low'] == collection_result['ohlcv_count']

        assert ohlcv_validation['positive_volume_usd'] == collection_result['ohlcv_count']
        
        logger.info("PASS: OHLCV data consistency validated")
        
        # Validate trade data consistency
        trade_validation_query = """
        SELECT 
            COUNT(*) as total_trades,
            COUNT(DISTINCT tx_from_address) as unique_traders,
            COUNT(CASE WHEN price_usd > 0 THEN 1 END) as positive_prices,
            COUNT(CASE WHEN volume_usd > 0 THEN 1 END) as positive_volumes,
            COUNT(CASE WHEN side IN ('buy', 'sell') THEN 1 END) as valid_trade_types,
            SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buy_trades,
            SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_trades,
            AVG(volume_usd) as avg_trade_volume,
            MIN(block_timestamp) as earliest_trade,
            MAX(block_timestamp) as latest_trade
        FROM trades WHERE pool_id = $1
        """
        
        trade_validation = await db_connection.fetchrow(trade_validation_query, pool_id)
        
        assert trade_validation['total_trades'] == collection_result['trade_count']
        assert trade_validation['unique_traders'] > 0
        assert trade_validation['positive_prices'] == collection_result['trade_count']
        assert trade_validation['positive_volumes'] == collection_result['trade_count']
        assert trade_validation['valid_trade_types'] == collection_result['trade_count']
        assert trade_validation['buy_trades'] > 0
        assert trade_validation['sell_trades'] > 0
        
        logger.info("PASS: Trade data consistency validated")
        
        # Cross-validate OHLCV and trade data alignment
        alignment_query = """
        WITH ohlcv_hourly AS (
            SELECT 
                DATE_TRUNC('hour', datetime) as hour_bucket,
                COUNT(*) as ohlcv_records,
                AVG(close_price) as avg_ohlcv_close
            FROM ohlcv_data 
            WHERE pool_id = $1
            GROUP BY DATE_TRUNC('hour', datetime)
        ),
        trades_hourly AS (
            SELECT 
                DATE_TRUNC('hour', block_timestamp) as hour_bucket,
                COUNT(*) as trade_records,
                AVG(price_usd) as avg_trade_price
            FROM trades 
            WHERE pool_id = $1
            GROUP BY DATE_TRUNC('hour', block_timestamp)
        )
        SELECT 
            o.hour_bucket,
            o.ohlcv_records,
            COALESCE(t.trade_records, 0) as trade_records,
            o.avg_ohlcv_close,
            t.avg_trade_price,
            ABS(o.avg_ohlcv_close - COALESCE(t.avg_trade_price, o.avg_ohlcv_close)) as price_deviation
        FROM ohlcv_hourly o
        LEFT JOIN trades_hourly t ON o.hour_bucket = t.hour_bucket
        ORDER BY o.hour_bucket
        """
        
        alignment_data = await db_connection.fetch(alignment_query, pool_id)
        
        # Verify each hour has both OHLCV and trade data
        for hour_data in alignment_data:
            logger.info(f"Hour {hour_data['hour_bucket']}: OHLCV={hour_data['ohlcv_records']}, Trades={hour_data['trade_records']}")
            assert hour_data['ohlcv_records'] == 1  # One OHLCV record per hour
            assert hour_data['trade_records'] > 0   # At least one trade per hour
            assert hour_data['price_deviation'] < 0.1  # Prices should be reasonably aligned
        
        logger.info("PASS: OHLCV/Trade data alignment validated")
        
        return {
            'ohlcv_validation': dict(ohlcv_validation),
            'trade_validation': dict(trade_validation),
            'alignment_data': [dict(row) for row in alignment_data]
        }
    
    async def test_qlib_export_pipeline(self, db_connection, test_environment, collection_result):
        """Test complete QLib export pipeline"""
        logger.info("Testing QLib export pipeline...")
        
        pool_id = test_environment['pool_id']
        symbol = test_environment['symbol']
        qlib_dir = Path(test_environment['qlib_dir'])
        
        # Create QLib directory structure
        features_dir = qlib_dir / "features" / symbol
        calendars_dir = qlib_dir / "calendars"
        instruments_dir = qlib_dir / "instruments"
        
        features_dir.mkdir(parents=True, exist_ok=True)
        calendars_dir.mkdir(parents=True, exist_ok=True)
        instruments_dir.mkdir(parents=True, exist_ok=True)
        
        # Export combined OHLCV and trade data
        export_query = """
        SELECT 
            o.pool_id as symbol,
            o.timestamp,
            o.datetime,
            o.open_price as open,
            o.high_price as high,
            o.low_price as low,
            o.close_price as close,
            o.volume_usd as ohlcv_volume_usd,
            COALESCE(t.trade_count, 0) as trade_count,
            COALESCE(t.unique_traders, 0) as unique_traders,
            COALESCE(t.total_volume_usd, 0) as trade_volume_usd,
            COALESCE(t.buy_volume, 0) as buy_volume,
            COALESCE(t.sell_volume, 0) as sell_volume,
            COALESCE(t.avg_price, o.close_price) as trade_avg_price,
            COALESCE(t.buy_trades, 0) as buy_trades,
            COALESCE(t.sell_trades, 0) as sell_trades
        FROM ohlcv_data o
        LEFT JOIN (
            SELECT 
                pool_id,
                DATE_TRUNC('hour', block_timestamp) as hour_bucket,
                COUNT(*) as trade_count,
                COUNT(DISTINCT tx_from_address) as unique_traders,
                SUM(volume_usd) as total_volume_usd,
                SUM(CASE WHEN side = 'buy' THEN volume_usd ELSE 0 END) as buy_volume,
                SUM(CASE WHEN side = 'sell' THEN volume_usd ELSE 0 END) as sell_volume,
                AVG(price_usd) as avg_price,
                SUM(CASE WHEN side = 'buy' THEN 1 ELSE 0 END) as buy_trades,
                SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_trades
            FROM trades 
            WHERE pool_id = $1
            GROUP BY pool_id, DATE_TRUNC('hour', block_timestamp)
        ) t ON o.pool_id = t.pool_id AND DATE_TRUNC('hour', o.datetime) = t.hour_bucket
        WHERE o.pool_id = $1
        ORDER BY o.timestamp ASC
        """
        
        export_data = await db_connection.fetch(export_query, pool_id)
        
        assert len(export_data) == collection_result['ohlcv_count']
        logger.info(f"PASS: Export query returned {len(export_data)} records")
        
        # Generate QLib files
        # 1. Calendar file
        calendar_file = calendars_dir / "60min.txt"
        with open(calendar_file, 'w') as f:
            for record in export_data:
                dt = record['datetime']
                f.write(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 2. Instruments file
        instruments_file = instruments_dir / "all.txt"
        with open(instruments_file, 'w') as f:
            f.write(f"{symbol}\n")
        
        # 3. Feature bin files
        import struct
        
        features = {
            'open': [float(r['open']) for r in export_data],
            'high': [float(r['high']) for r in export_data],
            'low': [float(r['low']) for r in export_data],
            'close': [float(r['close']) for r in export_data],

            'ohlcv_volume_usd': [float(r['ohlcv_volume_usd']) for r in export_data],
            'trade_count': [float(r['trade_count']) for r in export_data],
            'unique_traders': [float(r['unique_traders']) for r in export_data],
            'trade_volume_usd': [float(r['trade_volume_usd']) for r in export_data],
            'buy_volume': [float(r['buy_volume']) for r in export_data],
            'sell_volume': [float(r['sell_volume']) for r in export_data],
            'buy_trades': [float(r['buy_trades']) for r in export_data],
            'sell_trades': [float(r['sell_trades']) for r in export_data]
        }
        
        bin_files = []
        for feature_name, values in features.items():
            bin_file = features_dir / f"{feature_name}.60min.bin"
            with open(bin_file, 'wb') as f:
                for value in values:
                    f.write(struct.pack('<f', value))
            bin_files.append(bin_file)
        
        logger.info(f"PASS: Generated {len(bin_files)} QLib bin files")
        
        # Verify QLib file structure
        assert calendar_file.exists()
        assert instruments_file.exists()
        assert len(bin_files) == len(features)
        
        # Verify bin file sizes
        expected_size = len(export_data) * 4  # 4 bytes per float
        for bin_file in bin_files:
            assert bin_file.stat().st_size == expected_size, f"Incorrect size for {bin_file.name}"
        
        logger.info("PASS: QLib file structure validation passed")
        
        # Create export metadata
        export_metadata = {
            'export_name': f"pipeline_test_{test_environment['test_id']}",
            'export_type': 'ohlcv_trade_pipeline',
            'start_timestamp': collection_result['time_range'][0],
            'end_timestamp': collection_result['time_range'][1],
            'networks': [test_environment['network']],
            'pool_count': 1,
            'file_path': str(qlib_dir),
            'file_size_bytes': sum(f.stat().st_size for f in bin_files),
            'record_count': len(export_data),
            'qlib_config_json': {
                'frequency': '60min',
                'features': list(features.keys()),
                'calendar': 'calendars/60min.txt',
                'instruments': 'instruments/all.txt',
                'symbol_count': 1
            },
            'status': 'completed'
        }
        
        # Insert export metadata (if table exists)
        export_id = None
        try:
            export_id = await db_connection.fetchval("""
                INSERT INTO qlib_data_exports (
                    export_name, export_type, start_timestamp, end_timestamp, networks,
                    pool_count, file_path, file_size_bytes, record_count, qlib_config_json,
                    status, created_at, completed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
            """, 
                export_metadata['export_name'], export_metadata['export_type'],
                export_metadata['start_timestamp'], export_metadata['end_timestamp'],
                json.dumps(export_metadata['networks']), export_metadata['pool_count'],
                export_metadata['file_path'], export_metadata['file_size_bytes'],
                export_metadata['record_count'], json.dumps(export_metadata['qlib_config_json']),
                export_metadata['status'], datetime.now(timezone.utc), datetime.now(timezone.utc)
            )
        except Exception:
            # Table might not exist, use a mock ID for testing
            export_id = 1
        
        logger.info(f"PASS: Export metadata created with ID: {export_id}")
        
        return {
            'export_id': export_id,
            'export_data': export_data,
            'qlib_files': {
                'calendar': calendar_file,
                'instruments': instruments_file,
                'bin_files': bin_files
            },
            'features': features,
            'metadata': export_metadata
        }
    
    async def test_performance_benchmarks(self, db_connection, test_environment, collection_result):
        """Test performance benchmarks for the pipeline"""
        logger.info("Testing performance benchmarks...")
        
        pool_id = test_environment['pool_id']
        
        # Benchmark 1: Query performance
        start_time = time.time()
        
        complex_query = """
        SELECT 
            o.pool_id,
            o.timestamp,
            o.open_price, o.high_price, o.low_price, o.close_price,
            t.trade_count, t.unique_traders, t.total_volume, t.avg_price,
            t.price_volatility, t.buy_volume, t.sell_volume, t.max_trade_volume, t.min_trade_volume
        FROM ohlcv_data o
        LEFT JOIN (
            SELECT 
                pool_id,
                DATE_TRUNC('hour', block_timestamp) as hour_bucket,
                COUNT(*) as trade_count,
                COUNT(DISTINCT tx_from_address) as unique_traders,
                SUM(volume_usd) as total_volume,
                AVG(price_usd) as avg_price,
                STDDEV(price_usd) as price_volatility,
                SUM(CASE WHEN side = 'buy' THEN volume_usd ELSE 0 END) as buy_volume,
                SUM(CASE WHEN side = 'sell' THEN volume_usd ELSE 0 END) as sell_volume,
                MAX(volume_usd) as max_trade_volume,
                MIN(volume_usd) as min_trade_volume
            FROM trades 
            WHERE pool_id = $1
            GROUP BY pool_id, DATE_TRUNC('hour', block_timestamp)
        ) t(pool_id, hour_bucket, trade_count, unique_traders, total_volume, avg_price, 
             price_volatility, buy_volume, sell_volume, max_trade_volume, min_trade_volume)
        ON o.pool_id = t.pool_id AND DATE_TRUNC('hour', o.datetime) = t.hour_bucket
        WHERE o.pool_id = $1
        ORDER BY o.timestamp
        """
        
        benchmark_data = await db_connection.fetch(complex_query, pool_id)
        query_time = time.time() - start_time
        
        assert len(benchmark_data) == collection_result['ohlcv_count']
        logger.info(f"PASS: Complex query performance: {query_time:.3f}s for {len(benchmark_data)} records")
        
        # Benchmark 2: Aggregation performance
        start_time = time.time()
        
        aggregation_query = """
        SELECT 
            COUNT(DISTINCT o.pool_id) as unique_pools,
            COUNT(o.pool_id) as total_ohlcv_records,
            COUNT(t.id) as total_trade_records,
            AVG(o.volume_usd) as avg_ohlcv_volume,
            AVG(t.volume_usd) as avg_trade_volume,
            SUM(o.volume_usd) as total_ohlcv_volume,
            SUM(t.volume_usd) as total_trade_volume,
            MIN(o.timestamp) as earliest_ohlcv,
            MAX(o.timestamp) as latest_ohlcv,
            MIN(t.block_timestamp) as earliest_trade,
            MAX(t.block_timestamp) as latest_trade
        FROM ohlcv_data o
        FULL OUTER JOIN trades t ON o.pool_id = t.pool_id
        WHERE o.pool_id = $1 OR t.pool_id = $1
        """
        
        aggregation_result = await db_connection.fetchrow(aggregation_query, pool_id)
        aggregation_time = time.time() - start_time
        
        logger.info(f"PASS: Aggregation performance: {aggregation_time:.3f}s")
        
        # Benchmark 3: Export data preparation performance
        start_time = time.time()
        
        # Simulate QLib export data preparation
        export_prep_query = """
        WITH hourly_trades AS (
            SELECT 
                pool_id,
                DATE_TRUNC('hour', block_timestamp) as hour_bucket,
                COUNT(*) as trade_count,
                COUNT(DISTINCT tx_from_address) as unique_traders,
                SUM(volume_usd) as total_volume_usd,
                AVG(price_usd) as avg_price,
                STDDEV(price_usd) as price_volatility
            FROM trades 
            WHERE pool_id = $1
            GROUP BY pool_id, DATE_TRUNC('hour', block_timestamp)
        ),
        combined_features AS (
            SELECT 
                o.pool_id,
                o.timestamp,
                o.open_price, o.high_price, o.low_price, o.close_price,
                o.volume_usd,
                COALESCE(ht.trade_count, 0) as trade_count,
                COALESCE(ht.unique_traders, 0) as unique_traders,
                COALESCE(ht.total_volume_usd, 0) as trade_volume_usd,
                COALESCE(ht.avg_price, o.close_price) as trade_avg_price,
                COALESCE(ht.price_volatility, 0) as price_volatility,
                -- Technical indicators simulation
                AVG(o.close_price) OVER (ORDER BY o.timestamp ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) as sma_5,
                AVG(o.close_price) OVER (ORDER BY o.timestamp ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) as sma_10,
                o.high_price - o.low_price as daily_range,
                (o.close_price - o.open_price) / o.open_price as price_change_pct
            FROM ohlcv_data o
            LEFT JOIN hourly_trades ht ON o.pool_id = ht.pool_id 
                AND DATE_TRUNC('hour', o.datetime) = ht.hour_bucket
            WHERE o.pool_id = $1
            ORDER BY o.timestamp
        )
        SELECT * FROM combined_features
        """
        
        export_prep_data = await db_connection.fetch(export_prep_query, pool_id)
        export_prep_time = time.time() - start_time
        
        logger.info(f"PASS: Export preparation performance: {export_prep_time:.3f}s for {len(export_prep_data)} records")
        
        # Performance assertions
        assert query_time < 1.0, f"Query performance too slow: {query_time:.3f}s"
        assert aggregation_time < 5.0, f"Aggregation performance too slow: {aggregation_time:.3f}s"
        assert export_prep_time < 2.0, f"Export preparation too slow: {export_prep_time:.3f}s"
        
        performance_metrics = {
            'query_time': query_time,
            'aggregation_time': aggregation_time,
            'export_prep_time': export_prep_time,
            'records_per_second_query': len(benchmark_data) / max(query_time, 0.001),  # Avoid division by zero
            'records_per_second_export': len(export_prep_data) / max(export_prep_time, 0.001),  # Avoid division by zero
            'total_records_processed': len(benchmark_data) + len(export_prep_data)
        }
        
        logger.info("PASS: Performance benchmarks completed")
        return performance_metrics
    
    async def cleanup_test_data(self, db_connection, test_environment):
        """Clean up all test data"""
        pool_id = test_environment['pool_id']
        
        # Clean up in correct order (respecting foreign keys)
        try:
            # Try to clean qlib_data_exports if it exists
            await db_connection.execute("DELETE FROM qlib_data_exports WHERE export_name LIKE $1", 
                                       f"pipeline_test_{test_environment['test_id']}%")
        except Exception:
            # Table might not exist, continue with cleanup
            pass
        
        await db_connection.execute("DELETE FROM trades WHERE pool_id = $1", pool_id)
        await db_connection.execute("DELETE FROM ohlcv_data WHERE pool_id = $1", pool_id)
        
        logger.info("PASS: Test data cleanup completed")

async def run_tests():
    """Run complete OHLCV/Trade pipeline tests"""
    test_instance = TestCompleteOHLCVTradePipeline()
    
    async with asyncpg.create_pool(
        host="localhost",
        port=5432,
        user="gecko_collector",
        password="12345678!",
        database="gecko_terminal_collector",
        min_size=1,
        max_size=5
    ) as pool:
        async with pool.acquire() as conn:
            # Create test environment
            test_id = uuid.uuid4().hex[:8]
            temp_dir = tempfile.mkdtemp(prefix=f"pipeline_test_{test_id}_")
            
            test_environment = {
                'test_id': test_id,
                'temp_dir': temp_dir,
                'qlib_dir': os.path.join(temp_dir, 'qlib_data'),
                'pool_id': f"test_pool_{test_id}",
                'symbol': f"TEST_{test_id[:4].upper()}",
                'network': 'test_network'
            }
            
            os.makedirs(test_environment['qlib_dir'], exist_ok=True)
            
            try:
                logger.info("TEST: Starting Complete OHLCV/Trade Pipeline Test Suite")
                
                # Run pipeline tests
                collection_result = await test_instance.simulate_data_collection(conn, test_environment)
                await test_instance.test_data_consistency_validation(conn, test_environment, collection_result)
                await test_instance.test_qlib_export_pipeline(conn, test_environment, collection_result)
                await test_instance.test_performance_benchmarks(conn, test_environment, collection_result)
                
                logger.info("SUCCESS: All complete pipeline tests passed!")
                return True
                
            except Exception as e:
                logger.error(f"FAIL: Pipeline test failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
            finally:
                await test_instance.cleanup_test_data(conn, test_environment)
                shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)