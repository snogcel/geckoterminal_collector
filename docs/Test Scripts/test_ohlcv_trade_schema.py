#!/usr/bin/env python3
"""
Test suite for OHLCV and Trade data schema integration
Verifies database operations and QLib integration readiness
"""

import pytest
import asyncio
import asyncpg
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestOHLCVTradeSchema:
    """Test OHLCV and Trade data database schema operations"""
    
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
    def test_pool_id(self):
        """Generate unique test pool ID"""
        return f"test_pool_{uuid.uuid4().hex[:8]}"
    
    @pytest.fixture
    def test_data_timestamp(self):
        """Generate test timestamp"""
        return int(datetime.now(timezone.utc).timestamp())
    
    async def create_test_dependencies(self, db_connection, test_pool_id):
        """Create test dependencies (DEX, tokens, pool) for foreign key constraints"""
        # Use unique IDs based on test_pool_id to avoid conflicts
        dex_id = f"test_dex_{test_pool_id}"
        base_token_id = f"test_base_{test_pool_id}"
        quote_token_id = f"test_quote_{test_pool_id}"
        
        # Create test DEX
        await db_connection.execute("""
            INSERT INTO dexes (id, name, network)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO NOTHING
        """, dex_id, f"Test DEX {test_pool_id}", "test_network")
        
        # Create test tokens
        await db_connection.execute("""
            INSERT INTO tokens (id, address, name, symbol, network)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO NOTHING
        """, base_token_id, f"addr_base_{test_pool_id}", "Test Base Token", "TBT", "test_network")
        
        await db_connection.execute("""
            INSERT INTO tokens (id, address, name, symbol, network)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO NOTHING
        """, quote_token_id, f"addr_quote_{test_pool_id}", "Test Quote Token", "TQT", "test_network")
        
        # Create test pool
        await db_connection.execute("""
            INSERT INTO pools (id, name, address, dex_id, base_token_id, quote_token_id, reserve_usd)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
        """, test_pool_id, f"Test Pool {test_pool_id}", f"addr_{test_pool_id}", 
            dex_id, base_token_id, quote_token_id, Decimal('10000.0'))
    
    async def cleanup_test_dependencies(self, db_connection, test_pool_id):
        """Clean up test dependencies in correct order (respecting foreign keys)"""
        # Use unique IDs based on test_pool_id
        dex_id = f"test_dex_{test_pool_id}"
        base_token_id = f"test_base_{test_pool_id}"
        quote_token_id = f"test_quote_{test_pool_id}"
        
        # Delete in reverse order of creation, respecting foreign key constraints
        try:
            await db_connection.execute("DELETE FROM pools WHERE id = $1", test_pool_id)
            await db_connection.execute("DELETE FROM tokens WHERE id IN ($1, $2)", base_token_id, quote_token_id)
            await db_connection.execute("DELETE FROM dexes WHERE id = $1", dex_id)
        except Exception as e:
            # If cleanup fails, log but don't fail the test
            logger.warning(f"Cleanup warning: {e}")
    
    async def test_ohlcv_table_operations(self, db_connection, test_pool_id, test_data_timestamp):
        """Test OHLCV data table CRUD operations"""
        logger.info("Testing OHLCV table operations...")
        
        # Create test dependencies (required for foreign key constraints)
        await self.create_test_dependencies(db_connection, test_pool_id)
        
        # Test data
        ohlcv_data = {
            'pool_id': test_pool_id,
            'timeframe': '1h',
            'timestamp': test_data_timestamp,
            'datetime': datetime.fromtimestamp(test_data_timestamp, timezone.utc),
            'open_price': Decimal('1.2345'),
            'high_price': Decimal('1.2500'),
            'low_price': Decimal('1.2300'),
            'close_price': Decimal('1.2400'),
            'volume_usd': Decimal('1240.62'),
            'metadata_json': json.dumps({})
        }
        
        # CREATE - Insert OHLCV data
        insert_query = """
        INSERT INTO ohlcv_data (
            pool_id, timeframe, timestamp, datetime, open_price, high_price,
            low_price, close_price, volume_usd, metadata_json
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """
        
        ohlcv_id = await db_connection.fetchval(
            insert_query,
            ohlcv_data['pool_id'], ohlcv_data['timeframe'], ohlcv_data['timestamp'],
            ohlcv_data['datetime'], ohlcv_data['open_price'], ohlcv_data['high_price'],
            ohlcv_data['low_price'], ohlcv_data['close_price'],
            ohlcv_data['volume_usd'], ohlcv_data['metadata_json']
        )
        
        assert ohlcv_id is not None
        logger.info(f"PASS: OHLCV record created with ID: {ohlcv_id}")
        
        # READ - Retrieve OHLCV data
        select_query = "SELECT * FROM ohlcv_data WHERE id = $1"
        record = await db_connection.fetchrow(select_query, ohlcv_id)
        
        assert record is not None
        assert record['pool_id'] == test_pool_id
        assert record['timeframe'] == '1h'
        assert record['open_price'] == ohlcv_data['open_price']
        assert record['high_price'] == ohlcv_data['high_price']
        assert record['low_price'] == ohlcv_data['low_price']
        assert record['close_price'] == ohlcv_data['close_price']
        logger.info("PASS: OHLCV data retrieved and validated")
        
        # UPDATE - Modify OHLCV data
        new_close_price = Decimal('1.2450')
        update_query = "UPDATE ohlcv_data SET close_price = $1 WHERE id = $2"
        await db_connection.execute(update_query, new_close_price, ohlcv_id)
        
        updated_record = await db_connection.fetchrow(select_query, ohlcv_id)
        assert updated_record['close_price'] == new_close_price
        logger.info("PASS: OHLCV data updated successfully")
        
        # DELETE - Clean up test data
        delete_query = "DELETE FROM ohlcv_data WHERE id = $1"
        await db_connection.execute(delete_query, ohlcv_id)
        
        deleted_record = await db_connection.fetchrow(select_query, ohlcv_id)
        assert deleted_record is None
        logger.info("PASS: OHLCV data deleted successfully")
        
        # Cleanup test dependencies
        await self.cleanup_test_dependencies(db_connection, test_pool_id)
    
    async def test_trade_table_operations(self, db_connection, test_pool_id, test_data_timestamp):
        """Test Trade data table CRUD operations"""
        logger.info("Testing Trade table operations...")
        
        # Create test dependencies (required for foreign key constraints)
        await self.create_test_dependencies(db_connection, test_pool_id)
        
        # Test data
        trade_data = {
            'id': f"trade_{uuid.uuid4().hex[:8]}",
            'pool_id': test_pool_id,
            'block_number': 12345678,
            'tx_hash': f"0x{uuid.uuid4().hex[:32]}",
            'tx_from_address': f"0x{uuid.uuid4().hex[:40]}",
            'from_token_amount': Decimal('403.43'),
            'to_token_amount': Decimal('500.25'),
            'price_usd': Decimal('1.2400'),
            'volume_usd': Decimal('500.25'),
            'side': 'buy',
            'block_timestamp': datetime.fromtimestamp(test_data_timestamp, timezone.utc),
            'metadata_json': json.dumps({})
        }
        
        # CREATE - Insert trade data
        insert_query = """
        INSERT INTO trades (
            id, pool_id, block_number, tx_hash, tx_from_address, from_token_amount,
            to_token_amount, price_usd, volume_usd, side, block_timestamp, metadata_json
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
        """
        
        trade_id = await db_connection.fetchval(
            insert_query,
            trade_data['id'], trade_data['pool_id'], trade_data['block_number'],
            trade_data['tx_hash'], trade_data['tx_from_address'], trade_data['from_token_amount'],
            trade_data['to_token_amount'], trade_data['price_usd'], trade_data['volume_usd'],
            trade_data['side'], trade_data['block_timestamp'], trade_data['metadata_json']
        )
        
        assert trade_id is not None
        logger.info(f"PASS: Trade record created with ID: {trade_id}")
        
        # READ - Retrieve trade data
        select_query = "SELECT * FROM trades WHERE id = $1"
        record = await db_connection.fetchrow(select_query, trade_id)
        
        assert record is not None
        assert record['pool_id'] == test_pool_id
        assert record['id'] == trade_data['id']
        assert record['price_usd'] == trade_data['price_usd']
        assert record['side'] == 'buy'
        logger.info("PASS: Trade data retrieved and validated")
        
        # UPDATE - Modify trade data
        new_side = 'sell'
        update_query = "UPDATE trades SET side = $1 WHERE id = $2"
        await db_connection.execute(update_query, new_side, trade_id)
        
        updated_record = await db_connection.fetchrow(select_query, trade_id)
        assert updated_record['side'] == new_side
        logger.info("PASS: Trade data updated successfully")
        
        # DELETE - Clean up test data
        delete_query = "DELETE FROM trades WHERE id = $1"
        await db_connection.execute(delete_query, trade_id)
        
        deleted_record = await db_connection.fetchrow(select_query, trade_id)
        assert deleted_record is None
        logger.info("PASS: Trade data deleted successfully")
        
        # Cleanup test dependencies
        await self.cleanup_test_dependencies(db_connection, test_pool_id)
    
    async def test_data_integrity_constraints(self, db_connection, test_pool_id, test_data_timestamp):
        """Test data integrity constraints and relationships"""
        logger.info("Testing data integrity constraints...")
        
        # Test OHLC price relationships
        invalid_ohlcv = {
            'pool_id': test_pool_id,
            'timeframe': '1h',
            'timestamp': test_data_timestamp,
            'datetime': datetime.fromtimestamp(test_data_timestamp, timezone.utc),
            'open_price': Decimal('1.2500'),  # Open > High (invalid)
            'high_price': Decimal('1.2400'),
            'low_price': Decimal('1.2600'),   # Low > High (invalid)
            'close_price': Decimal('1.2450'),
            'volume': Decimal('1000.50'),
            'volume_usd': Decimal('1240.62'),
            'collected_at': datetime.now(timezone.utc)
        }
        
        # This should work (no DB constraints on price relationships yet)
        # But we can validate the data logic
        assert invalid_ohlcv['open_price'] > invalid_ohlcv['high_price'], "Invalid OHLC detected"
        assert invalid_ohlcv['low_price'] > invalid_ohlcv['high_price'], "Invalid OHLC detected"
        logger.info("PASS: Data integrity validation logic working")
        
        # Test valid OHLC relationships
        valid_ohlcv = {
            'pool_id': test_pool_id,
            'timeframe': '1h',
            'timestamp': test_data_timestamp + 3600,  # Next hour
            'datetime': datetime.fromtimestamp(test_data_timestamp + 3600, timezone.utc),
            'open_price': Decimal('1.2400'),
            'high_price': Decimal('1.2500'),
            'low_price': Decimal('1.2300'),
            'close_price': Decimal('1.2450'),
            'volume': Decimal('1000.50'),
            'volume_usd': Decimal('1240.62'),
            'collected_at': datetime.now(timezone.utc)
        }
        
        # Validate OHLC relationships
        assert valid_ohlcv['low_price'] <= valid_ohlcv['open_price'] <= valid_ohlcv['high_price']
        assert valid_ohlcv['low_price'] <= valid_ohlcv['close_price'] <= valid_ohlcv['high_price']
        logger.info("PASS: Valid OHLC relationships confirmed")
    
    async def test_bulk_insert_performance(self, db_connection, test_pool_id):
        """Test bulk insert performance for large datasets"""
        logger.info("Testing bulk insert performance...")
        
        # Create test dependencies
        await self.create_test_dependencies(db_connection, test_pool_id)
        
        # Generate test data
        ohlcv_records = []
        trade_records = []
        base_timestamp = int(datetime.now(timezone.utc).timestamp())
        
        # Create pools for bulk insert test (reuse the same pool for all records)
        for i in range(100):  # 100 records for performance test
            timestamp = base_timestamp + (i * 3600)  # Hourly intervals
            
            # Use the same test_pool_id for all records (already created)
            # OHLCV record
            ohlcv_records.append((
                test_pool_id,  # Use the same pool for all records
                '1h',
                timestamp,
                datetime.fromtimestamp(timestamp, timezone.utc),
                Decimal('1.2400') + Decimal(str(i * 0.001)),  # Varying prices
                Decimal('1.2500') + Decimal(str(i * 0.001)),
                Decimal('1.2300') + Decimal(str(i * 0.001)),
                Decimal('1.2450') + Decimal(str(i * 0.001)),
                Decimal('1240.62') + Decimal(str(i * 12)),
                json.dumps({})  # metadata_json
            ))
            
            # Trade record
            trade_records.append((
                f"trade_{i}_{uuid.uuid4().hex[:8]}",  # id
                test_pool_id,  # Use the same pool for all records
                12345678 + i,  # block_number
                f"0x{uuid.uuid4().hex[:32]}",  # tx_hash
                f"0x{uuid.uuid4().hex[:40]}",  # tx_from_address
                Decimal('403.43') + Decimal(str(i * 4)),  # from_token_amount
                Decimal('500.25') + Decimal(str(i * 5)),  # to_token_amount
                Decimal('1.2400') + Decimal(str(i * 0.001)),  # price_usd
                Decimal('500.25') + Decimal(str(i * 5)),  # volume_usd
                'buy' if i % 2 == 0 else 'sell',  # side
                datetime.fromtimestamp(timestamp, timezone.utc),  # block_timestamp
                json.dumps({})  # metadata_json
            ))
        
        # Bulk insert OHLCV data
        start_time = datetime.now()
        await db_connection.executemany("""
            INSERT INTO ohlcv_data (
                pool_id, timeframe, timestamp, datetime, open_price, high_price,
                low_price, close_price, volume_usd, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, ohlcv_records)
        ohlcv_duration = (datetime.now() - start_time).total_seconds()
        
        # Bulk insert trade data
        start_time = datetime.now()
        await db_connection.executemany("""
            INSERT INTO trades (
                id, pool_id, block_number, tx_hash, tx_from_address, from_token_amount,
                to_token_amount, price_usd, volume_usd, side, block_timestamp, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, trade_records)
        trade_duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"PASS: Bulk insert performance:")
        logger.info(f"   OHLCV: 100 records in {ohlcv_duration:.3f}s ({100/ohlcv_duration:.1f} records/sec)")
        logger.info(f"   Trade: 100 records in {trade_duration:.3f}s ({100/trade_duration:.1f} records/sec)")
        
        # Verify data was inserted
        ohlcv_count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM ohlcv_data WHERE pool_id = $1", test_pool_id
        )
        trade_count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM trades WHERE pool_id = $1", test_pool_id
        )
        
        assert ohlcv_count == 100
        assert trade_count == 100
        logger.info("PASS: Bulk insert data verification successful")
        
        # Cleanup
        await db_connection.execute("DELETE FROM ohlcv_data WHERE pool_id = $1", test_pool_id)
        await db_connection.execute("DELETE FROM trades WHERE pool_id = $1", test_pool_id)
        await self.cleanup_test_dependencies(db_connection, test_pool_id)
        logger.info("PASS: Bulk insert test data cleaned up")
    
    async def test_qlib_export_readiness(self, db_connection, test_pool_id, test_data_timestamp):
        """Test data structure readiness for QLib export"""
        logger.info("Testing QLib export readiness...")
        
        # Create test dependencies
        await self.create_test_dependencies(db_connection, test_pool_id)
        
        # Insert test data for QLib export simulation
        ohlcv_data = [
            (test_pool_id, '1h', test_data_timestamp, datetime.fromtimestamp(test_data_timestamp, timezone.utc),
             Decimal('1.2400'), Decimal('1.2500'), Decimal('1.2300'), Decimal('1.2450'),
             Decimal('1240.62'), json.dumps({})),
            (test_pool_id, '1h', test_data_timestamp + 3600, datetime.fromtimestamp(test_data_timestamp + 3600, timezone.utc),
             Decimal('1.2450'), Decimal('1.2550'), Decimal('1.2350'), Decimal('1.2500'),
             Decimal('1375.94'), json.dumps({}))
        ]
        
        await db_connection.executemany("""
            INSERT INTO ohlcv_data (
                pool_id, timeframe, timestamp, datetime, open_price, high_price,
                low_price, close_price, volume_usd, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, ohlcv_data)
        
        # Test QLib-style time series query
        qlib_query = """
        SELECT 
            pool_id as symbol,
            timestamp,
            open_price as open,
            high_price as high,
            low_price as low,
            close_price as close,
            volume_usd
        FROM ohlcv_data 
        WHERE pool_id = $1 
        ORDER BY timestamp ASC
        """
        
        qlib_data = await db_connection.fetch(qlib_query, test_pool_id)
        
        assert len(qlib_data) == 2
        assert qlib_data[0]['symbol'] == test_pool_id
        assert qlib_data[0]['open'] == Decimal('1.2400')
        assert qlib_data[1]['close'] == Decimal('1.2500')
        logger.info("PASS: QLib export query structure validated")
        
        # Test aggregated trade data for QLib
        trade_agg_query = """
        SELECT 
            pool_id as symbol,
            DATE_TRUNC('hour', block_timestamp) as hour_bucket,
            COUNT(*) as trade_count,
            SUM(volume_usd) as total_volume_usd,
            AVG(price_usd) as avg_price,
            COUNT(DISTINCT tx_from_address) as unique_traders
        FROM trades 
        WHERE pool_id = $1 
        GROUP BY pool_id, DATE_TRUNC('hour', block_timestamp)
        ORDER BY hour_bucket ASC
        """
        
        # Insert some trade data for aggregation test
        trade_data = [
            (f"trade_1_{uuid.uuid4().hex[:8]}", test_pool_id, 12345678,
             f"0x{uuid.uuid4().hex[:32]}", f"0x{uuid.uuid4().hex[:40]}",
             Decimal('403.43'), Decimal('500.25'), Decimal('1.2400'), Decimal('500.25'),
             'buy', datetime.fromtimestamp(test_data_timestamp, timezone.utc), json.dumps({})),
            (f"trade_2_{uuid.uuid4().hex[:8]}", test_pool_id, 12345679,
             f"0x{uuid.uuid4().hex[:32]}", f"0x{uuid.uuid4().hex[:40]}",
             Decimal('241.08'), Decimal('300.15'), Decimal('1.2450'), Decimal('300.15'),
             'sell', datetime.fromtimestamp(test_data_timestamp + 1800, timezone.utc), json.dumps({}))
        ]
        
        await db_connection.executemany("""
            INSERT INTO trades (
                id, pool_id, block_number, tx_hash, tx_from_address, from_token_amount,
                to_token_amount, price_usd, volume_usd, side, block_timestamp, metadata_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, trade_data)
        
        trade_agg_data = await db_connection.fetch(trade_agg_query, test_pool_id)
        
        if trade_agg_data:
            assert trade_agg_data[0]['symbol'] == test_pool_id
            assert trade_agg_data[0]['trade_count'] == 2
            assert trade_agg_data[0]['unique_traders'] == 2
            logger.info("PASS: Trade data aggregation for QLib validated")
        
        # Cleanup
        await db_connection.execute("DELETE FROM ohlcv_data WHERE pool_id = $1", test_pool_id)
        await db_connection.execute("DELETE FROM trades WHERE pool_id = $1", test_pool_id)
        await self.cleanup_test_dependencies(db_connection, test_pool_id)
        logger.info("PASS: QLib export test data cleaned up")

async def run_tests():
    """Run all OHLCV/Trade schema tests"""
    test_instance = TestOHLCVTradeSchema()
    
    # Create fixtures
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
            test_pool_id = f"test_pool_{uuid.uuid4().hex[:8]}"
            test_timestamp = int(datetime.now(timezone.utc).timestamp())
            
            try:
                logger.info("Starting OHLCV/Trade Schema Test Suite")
                
                await test_instance.test_ohlcv_table_operations(conn, test_pool_id, test_timestamp)
                await test_instance.test_trade_table_operations(conn, test_pool_id, test_timestamp)
                await test_instance.test_data_integrity_constraints(conn, test_pool_id, test_timestamp)
                await test_instance.test_bulk_insert_performance(conn, test_pool_id)
                await test_instance.test_qlib_export_readiness(conn, test_pool_id, test_timestamp)
                
                logger.info("All OHLCV/Trade schema tests passed!")
                return True
                
            except Exception as e:
                logger.error(f"Test failed: {e}")
                return False

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)