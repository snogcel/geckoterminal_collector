"""
Integration tests for CSV fixture validation and data format compliance.

This test suite validates that the CSV fixtures in /specs directory contain
valid data that matches the expected API response formats and can be properly
processed by the data collection system.
"""

import pytest
import csv
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any

from gecko_terminal_collector.clients.gecko_client import MockGeckoTerminalClient
from gecko_terminal_collector.models.core import Pool, Token, OHLCVRecord, TradeRecord
# Data validation will be done inline
from gecko_terminal_collector.config.models import CollectionConfig


@pytest.fixture
def specs_path():
    """Path to specs directory containing CSV fixtures."""
    return Path("specs")


@pytest.fixture
def data_validator():
    """Simple data validator for testing data integrity."""
    class SimpleDataValidator:
        def validate_ohlcv(self, record):
            class ValidationResult:
                def __init__(self, is_valid, errors=None):
                    self.is_valid = is_valid
                    self.errors = errors or []
            
            # Simple OHLCV validation
            try:
                assert record.high_price >= record.low_price
                assert record.high_price >= record.open_price
                assert record.high_price >= record.close_price
                assert record.low_price <= record.open_price
                assert record.low_price <= record.close_price
                assert record.volume_usd >= 0
                return ValidationResult(True)
            except Exception as e:
                return ValidationResult(False, [str(e)])
        
        def validate_trade(self, record):
            class ValidationResult:
                def __init__(self, is_valid, errors=None):
                    self.is_valid = is_valid
                    self.errors = errors or []
            
            # Simple trade validation
            try:
                assert record.volume_usd > 0
                assert record.from_token_amount > 0
                assert record.to_token_amount > 0
                assert record.side in ['buy', 'sell']
                return ValidationResult(True)
            except Exception as e:
                return ValidationResult(False, [str(e)])
    
    return SimpleDataValidator()


class TestCSVFixtureValidation:
    """Test CSV fixture files for data format compliance."""
    
    def test_dexes_csv_format(self, specs_path):
        """Test get_dexes_by_network.csv format and content."""
        csv_file = specs_path / "get_dexes_by_network.csv"
        
        if not csv_file.exists():
            pytest.skip(f"Fixture file {csv_file} not found")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Verify CSV has data
        assert len(rows) > 0, "DEX CSV should contain at least one row"
        
        # Verify required columns
        required_columns = ['id', 'type', 'name']
        for row in rows:
            for col in required_columns:
                assert col in row, f"Missing required column: {col}"
                assert row[col].strip(), f"Empty value in column: {col}"
            
            # Verify type is 'dex'
            assert row['type'] == 'dex', f"Invalid type: {row['type']}"
            
            # Verify ID format (should be alphanumeric with hyphens)
            assert row['id'].replace('-', '').replace('_', '').isalnum(), f"Invalid DEX ID format: {row['id']}"
    
    def test_watchlist_csv_format(self, specs_path):
        """Test watchlist.csv format and content."""
        csv_file = specs_path / "watchlist.csv"
        
        if not csv_file.exists():
            pytest.skip(f"Fixture file {csv_file} not found")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Verify CSV has data
        assert len(rows) > 0, "Watchlist CSV should contain at least one row"
        
        # Verify required columns
        required_columns = ['tokenSymbol', 'tokenName', 'chain', 'dex', 'poolAddress', 'networkAddress']
        for row in rows:
            for col in required_columns:
                assert col in row, f"Missing required column: {col}"
                assert row[col].strip(), f"Empty value in column: {col}"
            
            # Verify chain is SOL
            assert row['chain'] == 'SOL', f"Invalid chain: {row['chain']}"
            
            # Verify address formats (should be base58-like)
            pool_addr = row['poolAddress']
            network_addr = row['networkAddress']
            
            assert len(pool_addr) > 20, f"Pool address too short: {pool_addr}"
            assert len(network_addr) > 20, f"Network address too short: {network_addr}"
            assert pool_addr.isalnum(), f"Invalid pool address format: {pool_addr}"
            assert network_addr.isalnum(), f"Invalid network address format: {network_addr}"
    
    def test_ohlcv_csv_format(self, specs_path):
        """Test get_ohlcv.csv format and content."""
        csv_file = specs_path / "get_ohlcv.csv"
        
        if not csv_file.exists():
            pytest.skip(f"Fixture file {csv_file} not found")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Verify CSV has data
        assert len(rows) > 0, "OHLCV CSV should contain at least one row"
        
        # Verify required columns
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume_usd', 'datetime']
        for row in rows:
            for col in required_columns:
                assert col in row, f"Missing required column: {col}"
                assert row[col].strip(), f"Empty value in column: {col}"
            
            # Verify numeric values
            timestamp = int(row['timestamp'])
            open_price = float(row['open'])
            high_price = float(row['high'])
            low_price = float(row['low'])
            close_price = float(row['close'])
            volume_usd = float(row['volume_usd'])
            
            # Verify OHLC relationships
            assert high_price >= open_price, f"High < Open: {high_price} < {open_price}"
            assert high_price >= close_price, f"High < Close: {high_price} < {close_price}"
            assert low_price <= open_price, f"Low > Open: {low_price} > {open_price}"
            assert low_price <= close_price, f"Low > Close: {low_price} > {close_price}"
            assert high_price >= low_price, f"High < Low: {high_price} < {low_price}"
            
            # Verify positive values
            assert open_price > 0, f"Non-positive open price: {open_price}"
            assert high_price > 0, f"Non-positive high price: {high_price}"
            assert low_price > 0, f"Non-positive low price: {low_price}"
            assert close_price > 0, f"Non-positive close price: {close_price}"
            assert volume_usd >= 0, f"Negative volume: {volume_usd}"
            
            # Verify timestamp is reasonable (not too old or future)
            dt = datetime.fromtimestamp(timestamp)
            assert dt.year >= 2020, f"Timestamp too old: {dt}"
            assert dt.year <= 2030, f"Timestamp too far in future: {dt}"
    
    def test_trades_csv_format(self, specs_path):
        """Test get_trades.csv format and content."""
        csv_file = specs_path / "get_trades.csv"
        
        if not csv_file.exists():
            pytest.skip(f"Fixture file {csv_file} not found")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Verify CSV has data
        assert len(rows) > 0, "Trades CSV should contain at least one row"
        
        # Verify required columns
        required_columns = [
            'id', 'type', 'block_number', 'tx_hash', 'tx_from_address',
            'from_token_amount', 'to_token_amount', 'volume_usd', 'side'
        ]
        
        for row in rows:
            for col in required_columns:
                assert col in row, f"Missing required column: {col}"
                assert row[col].strip(), f"Empty value in column: {col}"
            
            # Verify type is 'trade'
            assert row['type'] == 'trade', f"Invalid type: {row['type']}"
            
            # Verify numeric values
            block_number = int(row['block_number'])
            from_amount = float(row['from_token_amount'])
            to_amount = float(row['to_token_amount'])
            volume_usd = float(row['volume_usd'])
            
            # Verify positive values
            assert block_number > 0, f"Non-positive block number: {block_number}"
            assert from_amount > 0, f"Non-positive from amount: {from_amount}"
            assert to_amount > 0, f"Non-positive to amount: {to_amount}"
            assert volume_usd > 0, f"Non-positive volume: {volume_usd}"
            
            # Verify side is valid
            assert row['side'] in ['buy', 'sell'], f"Invalid side: {row['side']}"
            
            # Verify hash formats
            tx_hash = row['tx_hash']
            assert len(tx_hash) > 40, f"Transaction hash too short: {tx_hash}"
    
    def test_top_pools_csv_format(self, specs_path):
        """Test top pools CSV files format and content."""
        csv_files = [
            "get_top_pools_by_network_dex_heaven.csv",
            "get_top_pools_by_network_dex_pumpswap.csv"
        ]
        
        for csv_filename in csv_files:
            csv_file = specs_path / csv_filename
            
            if not csv_file.exists():
                continue  # Skip if file doesn't exist
            
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if len(rows) == 0:
                continue  # Skip empty files
            
            # Verify required columns
            required_columns = [
                'id', 'type', 'name', 'address', 'reserve_in_usd',
                'dex_id', 'base_token_id', 'quote_token_id', 'network_id'
            ]
            
            for row in rows:
                for col in required_columns:
                    assert col in row, f"Missing required column: {col} in {csv_filename}"
                    # Some columns may be empty, so don't assert non-empty
                
                # Verify type is 'pool'
                if row['type']:
                    assert row['type'] == 'pool', f"Invalid type: {row['type']} in {csv_filename}"
                
                # Verify numeric values if present
                if row['reserve_in_usd']:
                    reserve_usd = float(row['reserve_in_usd'])
                    assert reserve_usd >= 0, f"Negative reserve: {reserve_usd} in {csv_filename}"


class TestFixtureDataIntegrity:
    """Test data integrity and consistency across fixtures."""
    
    @pytest.mark.asyncio
    async def test_mock_client_fixture_loading(self, specs_path):
        """Test that mock client properly loads and processes all fixtures."""
        client = MockGeckoTerminalClient(str(specs_path))
        
        # Test DEX data loading
        dexes = await client.get_dexes_by_network("solana")
        assert isinstance(dexes, list)
        
        # Test top pools loading for different DEXes
        heaven_pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        assert "data" in heaven_pools
        assert isinstance(heaven_pools["data"], list)
        
        pumpswap_pools = await client.get_top_pools_by_network_dex("solana", "pumpswap")
        assert "data" in pumpswap_pools
        assert isinstance(pumpswap_pools["data"], list)
        
        # Test OHLCV data loading
        ohlcv_data = await client.get_ohlcv_data("solana", "test_pool")
        assert "data" in ohlcv_data
        assert "attributes" in ohlcv_data["data"]
        assert "ohlcv_list" in ohlcv_data["data"]["attributes"]
        
        # Test trades data loading
        trades_data = await client.get_trades("solana", "test_pool")
        assert "data" in trades_data
        assert isinstance(trades_data["data"], list)
    
    @pytest.mark.asyncio
    async def test_fixture_data_validation(self, specs_path, data_validator):
        """Test that fixture data passes validation rules."""
        client = MockGeckoTerminalClient(str(specs_path))
        
        # Test OHLCV data validation
        ohlcv_data = await client.get_ohlcv_data("solana", "test_pool")
        ohlcv_list = ohlcv_data["data"]["attributes"]["ohlcv_list"]
        
        if ohlcv_list:
            for ohlcv_entry in ohlcv_list[:5]:  # Test first 5 entries
                # Convert to OHLCVRecord format
                record = OHLCVRecord(
                    pool_id="test_pool",
                    timeframe="1h",
                    timestamp=int(ohlcv_entry[0]),
                    open_price=Decimal(str(ohlcv_entry[1])),
                    high_price=Decimal(str(ohlcv_entry[2])),
                    low_price=Decimal(str(ohlcv_entry[3])),
                    close_price=Decimal(str(ohlcv_entry[4])),
                    volume_usd=Decimal(str(ohlcv_entry[5])),
                    datetime=datetime.fromtimestamp(int(ohlcv_entry[0]))
                )
                
                # Validate the record
                validation_result = data_validator.validate_ohlcv(record)
                assert validation_result.is_valid, f"OHLCV validation failed: {validation_result.errors}"
        
        # Test trade data validation
        trades_data = await client.get_trades("solana", "test_pool")
        
        if trades_data["data"]:
            for trade_data in trades_data["data"][:5]:  # Test first 5 trades
                attributes = trade_data["attributes"]
                
                # Convert to TradeRecord format
                record = TradeRecord(
                    id=trade_data["id"],
                    pool_id="test_pool",
                    block_number=int(attributes["block_number"]),
                    tx_hash=attributes["tx_hash"],
                    from_token_amount=Decimal(str(attributes["from_token_amount"])),
                    to_token_amount=Decimal(str(attributes["to_token_amount"])),
                    price_usd=Decimal(str(attributes.get("price_from_in_usd", 0))),
                    volume_usd=Decimal(str(attributes["volume_usd"])),
                    side=attributes["side"],
                    block_timestamp=datetime.fromisoformat(attributes["block_timestamp"].replace('Z', '+00:00'))
                )
                
                # Validate the record
                validation_result = data_validator.validate_trade(record)
                assert validation_result.is_valid, f"Trade validation failed: {validation_result.errors}"
    
    def test_fixture_cross_references(self, specs_path):
        """Test cross-references between different fixture files."""
        # Load watchlist to get pool addresses
        watchlist_file = specs_path / "watchlist.csv"
        if not watchlist_file.exists():
            pytest.skip("Watchlist fixture not found")
        
        with open(watchlist_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            watchlist_rows = list(reader)
        
        if not watchlist_rows:
            pytest.skip("Watchlist fixture is empty")
        
        # Get pool addresses from watchlist
        pool_addresses = [row['poolAddress'] for row in watchlist_rows]
        network_addresses = [row['networkAddress'] for row in watchlist_rows]
        
        # Check if these addresses appear in other fixtures
        # This is more of a consistency check than a strict requirement
        
        # Load top pools fixtures
        heaven_pools_file = specs_path / "get_top_pools_by_network_dex_heaven.csv"
        if heaven_pools_file.exists():
            with open(heaven_pools_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                heaven_rows = list(reader)
            
            heaven_addresses = [row['address'] for row in heaven_rows if row.get('address')]
            
            # Check for any overlap (not required, but good to know)
            overlap = set(pool_addresses) & set(heaven_addresses)
            # Just log the result, don't assert
            print(f"Pool address overlap between watchlist and heaven pools: {len(overlap)}")
    
    def test_fixture_data_ranges(self, specs_path):
        """Test that fixture data contains reasonable value ranges."""
        # Test OHLCV price ranges
        ohlcv_file = specs_path / "get_ohlcv.csv"
        if ohlcv_file.exists():
            with open(ohlcv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if rows:
                prices = []
                volumes = []
                
                for row in rows:
                    prices.extend([
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close'])
                    ])
                    volumes.append(float(row['volume_usd']))
                
                # Check price ranges (should be reasonable for crypto)
                min_price = min(prices)
                max_price = max(prices)
                
                assert min_price > 0, f"Minimum price should be positive: {min_price}"
                assert max_price < 1e10, f"Maximum price seems unreasonably high: {max_price}"
                
                # Check volume ranges
                min_volume = min(volumes)
                max_volume = max(volumes)
                
                assert min_volume >= 0, f"Volume should be non-negative: {min_volume}"
                assert max_volume < 1e12, f"Maximum volume seems unreasonably high: {max_volume}"
        
        # Test trade volume ranges
        trades_file = specs_path / "get_trades.csv"
        if trades_file.exists():
            with open(trades_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if rows:
                volumes = [float(row['volume_usd']) for row in rows]
                
                min_volume = min(volumes)
                max_volume = max(volumes)
                
                assert min_volume > 0, f"Trade volume should be positive: {min_volume}"
                assert max_volume < 1e10, f"Maximum trade volume seems unreasonably high: {max_volume}"


class TestFixtureErrorHandling:
    """Test error handling with malformed or missing fixture data."""
    
    @pytest.mark.asyncio
    async def test_missing_fixture_handling(self):
        """Test handling of missing fixture files."""
        # Use non-existent directory
        client = MockGeckoTerminalClient("nonexistent_directory")
        
        # Should handle gracefully without crashing
        dexes = await client.get_dexes_by_network("solana")
        assert isinstance(dexes, list)
        
        pools = await client.get_top_pools_by_network_dex("solana", "heaven")
        assert "data" in pools
        assert isinstance(pools["data"], list)
        
        ohlcv = await client.get_ohlcv_data("solana", "test_pool")
        assert "data" in ohlcv
        
        trades = await client.get_trades("solana", "test_pool")
        assert "data" in trades
    
    @pytest.mark.asyncio
    async def test_empty_fixture_handling(self, tmp_path):
        """Test handling of empty fixture files."""
        # Create empty CSV files
        empty_dir = tmp_path / "empty_fixtures"
        empty_dir.mkdir()
        
        # Create empty CSV files with headers only
        (empty_dir / "get_dexes_by_network.csv").write_text("id,type,name\n")
        (empty_dir / "get_ohlcv.csv").write_text("timestamp,open,high,low,close,volume_usd,datetime\n")
        (empty_dir / "get_trades.csv").write_text("id,type,block_number,tx_hash,volume_usd,side\n")
        
        client = MockGeckoTerminalClient(str(empty_dir))
        
        # Should handle empty files gracefully
        dexes = await client.get_dexes_by_network("solana")
        assert isinstance(dexes, list)
        assert len(dexes) == 0
        
        ohlcv = await client.get_ohlcv_data("solana", "test_pool")
        assert "data" in ohlcv
        ohlcv_list = ohlcv["data"]["attributes"]["ohlcv_list"]
        assert isinstance(ohlcv_list, list)
        assert len(ohlcv_list) == 0
        
        trades = await client.get_trades("solana", "test_pool")
        assert "data" in trades
        assert isinstance(trades["data"], list)
        assert len(trades["data"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])