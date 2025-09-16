"""
Watchlist CSV file monitoring and processing.

This module provides functionality to monitor watchlist CSV files for changes,
parse the CSV data with proper address type handling, and detect new tokens
for processing.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import WatchlistEntry
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.utils.metadata import MetadataTracker

logger = logging.getLogger(__name__)


class WatchlistRecord:
    """Represents a single record from the watchlist CSV."""
    
    def __init__(
        self,
        token_symbol: str,
        token_name: str,
        chain: str,
        dex: str,
        pool_address: str,
        network_address: str
    ):
        self.token_symbol = token_symbol.strip().strip('"')
        self.token_name = token_name.strip().strip('"')
        self.chain = chain.strip().strip('"')
        self.dex = dex.strip().strip('"')
        self.pool_address = pool_address.strip().strip('"')  # This is the "id" address
        self.network_address = network_address.strip().strip('"')  # This is the "base_token_id" address
    
    def __eq__(self, other):
        if not isinstance(other, WatchlistRecord):
            return False
        return self.pool_address == other.pool_address
    
    def __hash__(self):
        return hash(self.pool_address)
    
    def __repr__(self):
        return f"WatchlistRecord(symbol={self.token_symbol}, pool={self.pool_address})"


class WatchlistMonitor(BaseDataCollector):
    """
    Monitors watchlist CSV file for changes and processes new tokens.
    
    This collector detects changes to the watchlist CSV file, parses the content
    with proper address type handling (pool vs network addresses), and identifies
    new tokens that need to be processed for data collection.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False
    ):
        """
        Initialize the watchlist monitor.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        #print("---")
        #print("- init watchlist monitor-")
        #print("---")

        self.watchlist_file_path = Path(config.watchlist.file_path)
        self.auto_add_new_tokens = config.watchlist.auto_add_new_tokens
        
        # Track file modification time for change detection
        self._last_modified: Optional[float] = None
        self._last_processed_records: Set[WatchlistRecord] = set()
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "watchlist_monitor"
    
    async def collect(self) -> CollectionResult:
        """
        Monitor watchlist file for changes and process new tokens.
        
        Returns:
            CollectionResult with details about the monitoring operation
        """
        start_time = datetime.now()
        errors = []
        records_processed = 0
        
        try:
            # Check if watchlist file exists
            if not self.watchlist_file_path.exists():
                error_msg = f"Watchlist file not found: {self.watchlist_file_path}"
                logger.warning(error_msg)
                return self.create_failure_result([error_msg], collection_time=start_time)
            
            # Check if file has been modified since last check
            current_modified = os.path.getmtime(self.watchlist_file_path)
            
            if self._last_modified is not None and current_modified <= self._last_modified:
                logger.debug("Watchlist file has not been modified since last check")
                return self.create_success_result(0, start_time)
            
            # Parse the CSV file
            logger.info(f"Processing watchlist file: {self.watchlist_file_path}")
            current_records = await self._parse_watchlist_csv()
            
            if not current_records:
                logger.warning("No valid records found in watchlist file")
                self._last_modified = current_modified
                return self.create_success_result(0, start_time)
            
            # Detect changes
            new_records, removed_records = self._detect_changes(current_records)
            
            # Process new records
            if new_records:
                logger.info(f"Found {len(new_records)} new watchlist entries")
                processed_count = await self._process_new_records(new_records)
                records_processed += processed_count
            
            # Process removed records
            if removed_records:
                logger.info(f"Found {len(removed_records)} removed watchlist entries")
                await self._process_removed_records(removed_records)
            
            # Update tracking state
            self._last_modified = current_modified
            self._last_processed_records = set(current_records)
            
            logger.info(
                f"Watchlist monitoring completed: {records_processed} new records processed, "
                f"{len(removed_records)} records deactivated"
            )
            
            return self.create_success_result(records_processed, start_time)
            
        except Exception as e:
            error_msg = f"Error monitoring watchlist: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            return self.create_failure_result(errors, records_processed, start_time)
    
    async def _parse_watchlist_csv(self) -> List[WatchlistRecord]:
        """
        Parse the watchlist CSV file and return list of records.
        
        Returns:
            List of WatchlistRecord objects
        """
        records = []
        
        try:
            with open(self.watchlist_file_path, 'r', encoding='utf-8') as file:
                # Use csv.DictReader to handle CSV parsing properly
                reader = csv.DictReader(file)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 since header is row 1
                    try:
                        # Validate required fields
                        required_fields = ['tokenSymbol', 'tokenName', 'chain', 'dex', 'poolAddress', 'networkAddress']
                        missing_fields = [field for field in required_fields if field not in row or not row[field].strip()]
                        
                        if missing_fields:
                            logger.warning(
                                f"Row {row_num}: Missing required fields: {missing_fields}. Skipping row."
                            )
                            continue
                        
                        # Create record with proper address type handling
                        record = WatchlistRecord(
                            token_symbol=row['tokenSymbol'],
                            token_name=row['tokenName'],
                            chain=row['chain'],
                            dex=row['dex'],
                            pool_address=row['poolAddress'],  # This is the "id" address for pool operations
                            network_address=row['networkAddress']  # This is the "base_token_id" for token operations
                        )
                        
                        # Validate addresses are not empty after cleaning
                        if not record.pool_address or not record.network_address:
                            logger.warning(f"Row {row_num}: Empty addresses after cleaning. Skipping row.")
                            continue
                        
                        records.append(record)
                        
                    except Exception as e:
                        logger.warning(f"Row {row_num}: Error parsing row: {e}. Skipping row.")
                        continue
                        
        except Exception as e:
            logger.error(f"Error reading watchlist CSV file: {e}")
            raise
        
        logger.info(f"Parsed {len(records)} valid records from watchlist CSV")
        return records
    
    def _detect_changes(self, current_records: List[WatchlistRecord]) -> Tuple[List[WatchlistRecord], List[WatchlistRecord]]:
        """
        Detect new and removed records by comparing with last processed set.
        
        Args:
            current_records: Current records from CSV file
            
        Returns:
            Tuple of (new_records, removed_records)
        """
        current_set = set(current_records)
        
        # Find new records (in current but not in last processed)
        new_records = [record for record in current_records if record not in self._last_processed_records]
        
        # Find removed records (in last processed but not in current)
        removed_records = [record for record in self._last_processed_records if record not in current_set]
        
        return new_records, removed_records
    
    async def _process_new_records(self, new_records: List[WatchlistRecord]) -> int:
        """
        Process new watchlist records by adding them to the database.
        
        Args:
            new_records: List of new WatchlistRecord objects
            
        Returns:
            Number of records successfully processed
        """
        processed_count = 0

        print("called _process_new_records")
        
        if not self.auto_add_new_tokens:
            logger.info("Auto-add new tokens is disabled. New records will not be added automatically.")
            return processed_count
        
        for record in new_records:
            try:
                # Check if pool already exists in watchlist
                existing_entry = await self.db_manager.get_watchlist_entry_by_pool_id(record.pool_address)
                
                if existing_entry:
                    if not existing_entry.is_active:
                        # Reactivate existing entry
                        await self.db_manager.update_watchlist_entry_status(record.pool_address, True)
                        logger.info(f"Reactivated watchlist entry for pool: {record.pool_address}")
                        processed_count += 1
                    else:
                        logger.debug(f"Pool {record.pool_address} already in active watchlist")
                else:
                    # Create new watchlist entry
                    watchlist_entry = WatchlistEntry(
                        pool_id=record.pool_address,
                        token_symbol=record.token_symbol,
                        token_name=record.token_name,
                        network_address=record.network_address,
                        is_active=True
                    )
                    
                    await self.db_manager.add_watchlist_entry(watchlist_entry)
                    logger.info(f"Added new watchlist entry: {record.token_symbol} ({record.pool_address})")
                    processed_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing new record {record}: {e}")
                continue
        
        return processed_count
    
    async def _process_removed_records(self, removed_records: List[WatchlistRecord]) -> None:
        """
        Process removed watchlist records by deactivating them in the database.
        
        Args:
            removed_records: List of removed WatchlistRecord objects
        """
        for record in removed_records:
            try:
                # Deactivate the watchlist entry instead of deleting to preserve historical data
                await self.db_manager.update_watchlist_entry_status(record.pool_address, False)
                logger.info(f"Deactivated watchlist entry for pool: {record.pool_address}")
                
            except Exception as e:
                logger.error(f"Error deactivating record {record}: {e}")
                continue
    
    async def _validate_specific_data(self, data: List[WatchlistRecord]) -> Optional[ValidationResult]:
        """
        Validate watchlist records.
        
        Args:
            data: List of WatchlistRecord objects to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not isinstance(data, list):
            errors.append("Data must be a list of WatchlistRecord objects")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Validate individual records
        pool_addresses_seen = set()
        
        for i, record in enumerate(data):
            if not isinstance(record, WatchlistRecord):
                errors.append(f"Record {i}: Must be a WatchlistRecord object")
                continue
            
            # Check for duplicate pool addresses within the same file
            if record.pool_address in pool_addresses_seen:
                warnings.append(f"Record {i}: Duplicate pool address {record.pool_address}")
            else:
                pool_addresses_seen.add(record.pool_address)
            
            # Validate required fields
            if not record.token_symbol:
                errors.append(f"Record {i}: Missing token symbol")
            
            if not record.pool_address:
                errors.append(f"Record {i}: Missing pool address")
            
            if not record.network_address:
                errors.append(f"Record {i}: Missing network address")
            
            # Validate address formats (basic validation)
            if record.pool_address and len(record.pool_address) < 10:
                warnings.append(f"Record {i}: Pool address seems too short: {record.pool_address}")
            
            if record.network_address and len(record.network_address) < 10:
                warnings.append(f"Record {i}: Network address seems too short: {record.network_address}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def get_file_status(self) -> Dict[str, any]:
        """
        Get current status of the watchlist file.
        
        Returns:
            Dictionary with file status information
        """
        status = {
            "file_path": str(self.watchlist_file_path),
            "exists": self.watchlist_file_path.exists(),
            "last_modified": None,
            "last_checked": self._last_modified,
            "records_count": len(self._last_processed_records)
        }
        
        if self.watchlist_file_path.exists():
            status["last_modified"] = os.path.getmtime(self.watchlist_file_path)
        
        return status
    
    def force_refresh(self) -> None:
        """
        Force a refresh by resetting the last modified timestamp.
        This will cause the next collect() call to process the file regardless of modification time.
        """
        self._last_modified = None
        logger.info("Forced watchlist refresh - next collection will process the file")