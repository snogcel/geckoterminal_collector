"""
Tests for the WatchlistMonitor collector.
"""

import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gecko_terminal_collector.collectors.watchlist_monitor import (
    WatchlistMonitor,
    WatchlistRecord,
)
from gecko_terminal_collector.config.models import CollectionConfig, WatchlistConfig
from gecko_terminal_collector.database.models import WatchlistEntry
from gecko_terminal_collector.models.core import CollectionResult


class TestWatchlistRecord:
    """Test WatchlistRecord data class."""
    
    def test_watchlist_record_creation(self):
        """Test creating a WatchlistRecord."""
        record = WatchlistRecord(
            token_symbol="CBRL",
            token_name="Cracker Barrel Old Country Store",
            chain="SOL",
            dex="PumpSwap",
            pool_address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            network_address="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        
        assert record.token_symbol == "CBRL"
        assert record.token_name == "Cracker Barrel Old Country Store"
        assert record.chain == "SOL"
        assert record.dex == "PumpSwap"
        assert record.pool_address == "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert record.network_address == "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
    
    def test_watchlist_record_equality(self):
        """Test WatchlistRecord equality based on pool_address."""
        record1 = WatchlistRecord(
            token_symbol="CBRL",
            token_name="Cracker Barrel Old Country Store",
            chain="SOL",
            dex="PumpSwap",
            pool_address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
            network_address="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        
        record2 = WatchlistRecord(
            token_symbol="CBRL2",  # Different symbol
            token_name="Different Name",  # Different name
            chain="SOL",
            dex="PumpSwap",
            pool_address="7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",  # Same pool address
            network_address="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        
        record3 = WatchlistRecord(
            token_symbol="CBRL",
            token_name="Cracker Barrel Old Country Store",
            chain="SOL",
            dex="PumpSwap",
            pool_address="DifferentPoolAddress",  # Different pool address
            network_address="5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
        )
        
        # Records with same pool_address should be equal
        assert record1 == record2
        assert hash(record1) == hash(record2)
        
        # Records with different pool_address should not be equal
        assert record1 != record3
        assert hash(record1) != hash(record3)
    
    def test_watchlist_record_string_cleaning(self):
        """Test that WatchlistRecord properly cleans string inputs."""
        record = WatchlistRecord(
            token_symbol='  "CBRL"  ',  # With quotes and spaces
            token_name='  "Cracker Barrel"  ',
            chain='  "SOL"  ',
            dex='  "PumpSwap"  ',
            pool_address='  "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"  ',
            network_address='  "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"  '
        )
        
        assert record.token_symbol == "CBRL"
        assert record.token_name == "Cracker Barrel"
        assert record.chain == "SOL"
        assert record.dex == "PumpSwap"
        assert record.pool_address == "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
        assert record.network_address == "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"


class TestWatchlistMonitor:
    """Test WatchlistMonitor collector."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=CollectionConfig)
        
        # Mock watchlist config
        config.watchlist = MagicMock(spec=WatchlistConfig)
        config.watchlist.file_path = "test_watchlist.csv"
        config.watchlist.auto_add_new_tokens = True
        
        # Mock error handling config
        config.error_handling = MagicMock()
        config.error_handling.max_retries = 3
        config.error_handling.backoff_factor = 2.0
        config.error_handling.circuit_breaker_threshold = 5
        config.error_handling.circuit_breaker_timeout = 300
        
        # Mock API config
        config.api = MagicMock()
        config.api.timeout = 30
        config.api.rate_limit_delay = 1.0
        
        return config
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = AsyncMock()
        return db_manager
    
    @pytest.fixture
    def watchlist_monitor(self, mock_config, mock_db_manager):
        """Create a WatchlistMonitor instance."""
        return WatchlistMonitor(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
    
    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing."""
        return '''tokenSymbol,tokenName,chain,dex,poolAddress,networkAddress
"CBRL","Cracker Barrel Old Country Store","SOL","PumpSwap","7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP","5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
"TEST","Test Token","SOL","Heaven","AnotherPoolAddress123","AnotherNetworkAddress456"'''
    
    def test_get_collection_key(self, watchlist_monitor):
        """Test get_collection_key method."""
        assert watchlist_monitor.get_collection_key() == "watchlist_monitor"
    
    @pytest.mark.asyncio
    async def test_collect_file_not_found(self, watchlist_monitor):
        """Test collect when watchlist file doesn't exist."""
        # File doesn't exist by default in temp directory
        result = await watchlist_monitor.collect()
        
        assert not result.success
        assert len(result.errors) == 1
        assert "Watchlist file not found" in result.errors[0]
        assert result.records_collected == 0
    
    @pytest.mark.asyncio
    async def test_collect_file_not_modified(self, watchlist_monitor, sample_csv_content):
        """Test collect when file hasn't been modified since last check."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_file.write(sample_csv_content)
            temp_file.flush()
            temp_file.close()  # Close file handle to avoid Windows permission issues
            
            # Update config to point to temp file
            watchlist_monitor.watchlist_file_path = Path(temp_file.name)
            
            try:
                # First collection should process the file
                result1 = await watchlist_monitor.collect()
                assert result1.success
                
                # Second collection should skip (file not modified)
                result2 = await watchlist_monitor.collect()
                assert result2.success
                assert result2.records_collected == 0
                
            finally:
                try:
                    os.unlink(temp_file.name)
                except PermissionError:
                    pass  # Ignore permission errors on Windows
    
    @pytest.mark.asyncio
    async def test_parse_watchlist_csv(self, watchlist_monitor, sample_csv_content):
        """Test CSV parsing functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_file.write(sample_csv_content)
            temp_file.flush()
            temp_file.close()  # Close file handle to avoid Windows permission issues
            
            # Update config to point to temp file
            watchlist_monitor.watchlist_file_path = Path(temp_file.name)
            
            try:
                records = await watchlist_monitor._parse_watchlist_csv()
                
                assert len(records) == 2
                
                # Check first record
                assert records[0].token_symbol == "CBRL"
                assert records[0].token_name == "Cracker Barrel Old Country Store"
                assert records[0].chain == "SOL"
                assert records[0].dex == "PumpSwap"
                assert records[0].pool_address == "7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
                assert records[0].network_address == "5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
                
                # Check second record
                assert records[1].token_symbol == "TEST"
                assert records[1].token_name == "Test Token"
                assert records[1].pool_address == "AnotherPoolAddress123"
                assert records[1].network_address == "AnotherNetworkAddress456"
                
            finally:
                try:
                    os.unlink(temp_file.name)
                except PermissionError:
                    pass  # Ignore permission errors on Windows
    
    @pytest.mark.asyncio
    async def test_parse_csv_with_missing_fields(self, watchlist_monitor):
        """Test CSV parsing with missing required fields."""
        csv_content = '''tokenSymbol,tokenName,chain,dex,poolAddress,networkAddress
"CBRL","Cracker Barrel Old Country Store","SOL","PumpSwap","7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP","5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump"
"","Test Token","SOL","Heaven","AnotherPoolAddress123","AnotherNetworkAddress456"
"TEST2","","SOL","Heaven","","AnotherNetworkAddress789"'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_file.write(csv_content)
            temp_file.flush()
            temp_file.close()  # Close file handle to avoid Windows permission issues
            
            watchlist_monitor.watchlist_file_path = Path(temp_file.name)
            
            try:
                records = await watchlist_monitor._parse_watchlist_csv()
                
                # Only the first record should be valid
                assert len(records) == 1
                assert records[0].token_symbol == "CBRL"
                
            finally:
                try:
                    os.unlink(temp_file.name)
                except PermissionError:
                    pass  # Ignore permission errors on Windows
    
    def test_detect_changes(self, watchlist_monitor):
        """Test change detection logic."""
        # Set up initial state
        record1 = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        record2 = WatchlistRecord("TEST", "Test Token", "SOL", "Heaven", "pool2", "network2")
        watchlist_monitor._last_processed_records = {record1, record2}
        
        # Current records with one new, one removed, one unchanged
        record3 = WatchlistRecord("NEW", "New Token", "SOL", "PumpSwap", "pool3", "network3")
        current_records = [record1, record3]  # record1 unchanged, record3 new, record2 removed
        
        new_records, removed_records = watchlist_monitor._detect_changes(current_records)
        
        assert len(new_records) == 1
        assert new_records[0] == record3
        
        assert len(removed_records) == 1
        assert removed_records[0] == record2
    
    @pytest.mark.asyncio
    async def test_process_new_records_auto_add_enabled(self, watchlist_monitor, mock_db_manager):
        """Test processing new records when auto-add is enabled."""
        # Setup
        watchlist_monitor.auto_add_new_tokens = True
        mock_db_manager.get_watchlist_entry_by_pool_id.return_value = None  # No existing entry
        mock_db_manager.add_watchlist_entry = AsyncMock()
        
        record = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        new_records = [record]
        
        # Execute
        processed_count = await watchlist_monitor._process_new_records(new_records)
        
        # Verify
        assert processed_count == 1
        mock_db_manager.add_watchlist_entry.assert_called_once()
        
        # Check the WatchlistEntry that was added
        call_args = mock_db_manager.add_watchlist_entry.call_args[0][0]
        assert call_args.pool_id == "pool1"
        assert call_args.token_symbol == "CBRL"
        assert call_args.token_name == "Cracker Barrel"
        assert call_args.network_address == "network1"
        assert call_args.is_active is True
    
    @pytest.mark.asyncio
    async def test_process_new_records_auto_add_disabled(self, watchlist_monitor, mock_db_manager):
        """Test processing new records when auto-add is disabled."""
        # Setup
        watchlist_monitor.auto_add_new_tokens = False
        
        record = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        new_records = [record]
        
        # Execute
        processed_count = await watchlist_monitor._process_new_records(new_records)
        
        # Verify
        assert processed_count == 0
        mock_db_manager.add_watchlist_entry.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_new_records_reactivate_existing(self, watchlist_monitor, mock_db_manager):
        """Test reactivating an existing inactive watchlist entry."""
        # Setup
        watchlist_monitor.auto_add_new_tokens = True
        
        # Mock existing inactive entry
        existing_entry = MagicMock()
        existing_entry.is_active = False
        mock_db_manager.get_watchlist_entry_by_pool_id.return_value = existing_entry
        mock_db_manager.update_watchlist_entry_status = AsyncMock()
        
        record = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        new_records = [record]
        
        # Execute
        processed_count = await watchlist_monitor._process_new_records(new_records)
        
        # Verify
        assert processed_count == 1
        mock_db_manager.update_watchlist_entry_status.assert_called_once_with("pool1", True)
        mock_db_manager.add_watchlist_entry.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_removed_records(self, watchlist_monitor, mock_db_manager):
        """Test processing removed records."""
        # Setup
        mock_db_manager.update_watchlist_entry_status = AsyncMock()
        
        record = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        removed_records = [record]
        
        # Execute
        await watchlist_monitor._process_removed_records(removed_records)
        
        # Verify
        mock_db_manager.update_watchlist_entry_status.assert_called_once_with("pool1", False)
    
    @pytest.mark.asyncio
    async def test_validate_specific_data(self, watchlist_monitor):
        """Test data validation."""
        # Valid records
        record1 = WatchlistRecord("CBRL", "Cracker Barrel", "SOL", "PumpSwap", "pool1", "network1")
        record2 = WatchlistRecord("TEST", "Test Token", "SOL", "Heaven", "pool2", "network2")
        valid_data = [record1, record2]
        
        result = await watchlist_monitor._validate_specific_data(valid_data)
        assert result.is_valid
        assert len(result.errors) == 0
        
        # Invalid data - not a list
        result = await watchlist_monitor._validate_specific_data("not a list")
        assert not result.is_valid
        assert len(result.errors) == 1
        
        # Invalid records - missing required fields
        invalid_record = WatchlistRecord("", "", "SOL", "PumpSwap", "", "")
        invalid_data = [invalid_record]
        
        result = await watchlist_monitor._validate_specific_data(invalid_data)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_get_file_status(self, watchlist_monitor):
        """Test file status reporting."""
        status = watchlist_monitor.get_file_status()
        
        assert "file_path" in status
        assert "exists" in status
        assert "last_modified" in status
        assert "last_checked" in status
        assert "records_count" in status
        
        assert status["exists"] is False  # File doesn't exist in test
        assert status["records_count"] == 0  # No records processed yet
    
    def test_force_refresh(self, watchlist_monitor):
        """Test forcing a refresh."""
        # Set some initial state
        watchlist_monitor._last_modified = 12345.0
        
        # Force refresh
        watchlist_monitor.force_refresh()
        
        # Verify state was reset
        assert watchlist_monitor._last_modified is None
    
    @pytest.mark.asyncio
    async def test_full_collection_workflow(self, watchlist_monitor, mock_db_manager, sample_csv_content):
        """Test the complete collection workflow."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_file.write(sample_csv_content)
            temp_file.flush()
            temp_file.close()  # Close file handle to avoid Windows permission issues
            
            # Update config to point to temp file
            watchlist_monitor.watchlist_file_path = Path(temp_file.name)
            watchlist_monitor.auto_add_new_tokens = True
            
            # Mock database responses
            mock_db_manager.get_watchlist_entry_by_pool_id.return_value = None
            mock_db_manager.add_watchlist_entry = AsyncMock()
            
            try:
                # Execute collection
                result = await watchlist_monitor.collect()
                
                # Verify results
                assert result.success
                assert result.records_collected == 2
                assert len(result.errors) == 0
                
                # Verify database calls
                assert mock_db_manager.add_watchlist_entry.call_count == 2
                
                # Verify internal state
                assert len(watchlist_monitor._last_processed_records) == 2
                assert watchlist_monitor._last_modified is not None
                
            finally:
                try:
                    os.unlink(temp_file.name)
                except PermissionError:
                    pass  # Ignore permission errors on Windows