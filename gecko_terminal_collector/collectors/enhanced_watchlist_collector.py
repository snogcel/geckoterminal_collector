"""
Enhanced Watchlist Collector using rich external data sources.

This collector processes enhanced watchlist data with pre-calculated metrics,
rankings, and price changes, while resolving network addresses via API calls.
"""

import asyncio
import csv
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.utils.address_parser import EnhancedWatchlistParser
from gecko_terminal_collector.utils.database_address_resolver import EnhancedWatchlistDatabaseParser
from gecko_terminal_collector.utils.telegram_notifier import TelegramNotifier
#from gecko_terminal_collector.utils.telegram_notifier_enriched import TelegramNotifier

logger = logging.getLogger(__name__)


class EnhancedWatchlistCollector(BaseDataCollector):
    """
    Collector for enhanced watchlist data with rich metrics.
    
    Processes CSV files with pre-calculated metrics, rankings, and price changes,
    while resolving network addresses through GeckoTerminal API calls.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False,
        watchlist_sources: Optional[List[str]] = None
    ):
        """
        Initialize the enhanced watchlist collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
            watchlist_sources: List of source segments to collect (default: all available)
        """
        super().__init__(config, db_manager, metadata_tracker, use_mock)
        
        # Available source segments
        self.available_sources = ["lowcap", "micro", "midcap", "oldlowcap", "oldmicro", "reference"]
        self.sources_to_collect = watchlist_sources or self.available_sources
        
        self.network = config.dexes['network'] if isinstance(config.dexes, dict) else config.dexes.network
        
        # Use database parser instead of API parser for better efficiency
        self.parser = EnhancedWatchlistDatabaseParser(self.db_manager)
        self._parser_initialized = False

        # Telegram notifier — credentials come from env vars
        self.telegram = TelegramNotifier()
        
        # Rate limiting configuration
        self.rate_limit_delay = getattr(config, 'rate_limit_delay', 1.0)  # 1 second between API calls
        self.batch_size = getattr(config, 'batch_size', 10)  # Process 10 entries at a time
        
        # Tracking for metrics
        self._last_file_modified = {}  # Track per source
        self._entries_processed = 0
        self._addresses_resolved = 0
        self._api_calls_made = 0
        self._sources_processed = 0
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return "enhanced_watchlist_collector"
    
    async def collect(self) -> CollectionResult:
        """
        Collect enhanced watchlist data from multiple source files.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now(tz=timezone.utc)
        errors = []
        total_records_collected = 0
        
        try:
            logger.info(f"Starting enhanced watchlist collection for sources: {self.sources_to_collect}")
            
            # Initialize database parser if needed
            if not self._parser_initialized:
                logger.info("Initializing database address resolver...")
                init_stats = await self.parser.initialize()
                self._parser_initialized = True
                logger.info(f"Database resolver ready: {init_stats['total_mappings']} address mappings loaded")
            
            # Reset metrics
            self._entries_processed = 0
            self._addresses_resolved = 0
            self._api_calls_made = 0  # Should be 0 with database resolver
            self._sources_processed = 0
            
            # Process each source
            for source in self.sources_to_collect:
                try:
                    source_file = Path(f"watchlist_updated_{source}.csv")
                    
                    if not source_file.exists():
                        logger.warning(f"Source file not found: {source_file}")
                        continue
                    
                    # Check if file has been modified since last collection
                    current_modified = source_file.stat().st_mtime
                    if (source in self._last_file_modified and 
                        current_modified <= self._last_file_modified[source]):
                        logger.info(f"Source {source} unchanged since last collection")
                        continue
                    
                    logger.info(f"Processing source: {source} from file: {source_file}")
                    
                    # Process the source file
                    entries = await self._process_source_file(source, source_file)
                    
                    if entries:
                        # Store entries with rate limiting
                        stored_count = await self._store_enhanced_entries_with_history(source, entries)
                        total_records_collected += stored_count
                        
                        # Update file modification time
                        self._last_file_modified[source] = current_modified
                        
                        logger.info(f"Source {source}: {stored_count} entries stored")
                    else:
                        logger.warning(f"No valid entries found in source: {source}")
                    
                    self._sources_processed += 1
                    
                    # Rate limiting between sources
                    if self._sources_processed < len(self.sources_to_collect):
                        await asyncio.sleep(self.rate_limit_delay)
                        
                except Exception as e:
                    error_msg = f"Error processing source {source}: {e}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    continue
            
            logger.info(
                f"Enhanced watchlist collection completed: "
                f"{total_records_collected} total entries stored, "
                f"{self._sources_processed} sources processed, "
                f"{self._addresses_resolved} addresses resolved via database lookup "
                f"(0 API calls - using database resolver)"
            )
            
            # Create result with metadata
            result = self.create_success_result(total_records_collected, start_time)
            result.metadata = {
                'sources_processed': self._sources_processed,
                'sources_to_collect': self.sources_to_collect,
                'entries_processed': self._entries_processed,
                'addresses_resolved': self._addresses_resolved,
                'api_calls_made': 0,  # Database resolver doesn't make API calls
                'database_lookups': self._addresses_resolved,
                'errors': errors
            }
            
            if errors and total_records_collected == 0:
                return self.create_failure_result(errors, start_time)
            
            return result
            
        except Exception as e:
            error_msg = f"Error in enhanced watchlist collection: {e}"
            logger.error(error_msg, exc_info=True)
            return self.create_failure_result([error_msg], start_time)
    
    async def _process_source_file(self, source: str, source_file: Path) -> List[Dict[str, Any]]:
        """
        Process a single enhanced watchlist source CSV file.
        
        Args:
            source: Source name (e.g., 'reference', 'lowcap')
            source_file: Path to the CSV file
        
        Returns:
            List of parsed and enriched entries
        """
        entries = []
        
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, 1):
                    self._entries_processed += 1
                    
                    try:
                        # Parse and enrich the entry using database lookup (no API calls)
                        entry = await self.parser.parse_watchlist_entry(row)
                        # No API calls made with database resolver
                        
                        if entry:
                            # Add source information
                            entry['source'] = source
                            # Keep the original ranking from CSV, don't overwrite with row number
                            # entry['ranking'] is already set by the parser from the CSV data
                            entries.append(entry)
                            self._addresses_resolved += 1
                            logger.debug(f"Processed {source} entry {row_num}: {entry['tokenSymbol']} (resolved from {entry.get('resolvedFrom', 'unknown')})")
                        else:
                            logger.warning(f"Failed to resolve {source} entry at row {row_num} from database")
                        
                        # Minimal delay for database operations (much faster than API calls)
                        if row_num % (self.batch_size * 5) == 0:  # Less frequent delays
                            await asyncio.sleep(0.1)  # Much shorter delay
                            
                    except Exception as e:
                        logger.error(f"Error processing {source} row {row_num}: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error reading {source} file {source_file}: {e}")
            raise
        
        logger.info(f"Processed {len(entries)} valid entries from {source} ({self._entries_processed} total rows)")
        return entries
    
    async def _store_enhanced_entries_with_history(self, source: str, entries: List[Dict[str, Any]]) -> int:
        """
        Store enhanced watchlist entries in database with historical tracking.
        
        Args:
            source: Source name for the entries
            entries: List of parsed entries to store
            
        Returns:
            Number of entries successfully stored
        """
        stored_count = 0
        
        for entry in entries:
            try:
                # Store pool information
                await self._store_pool_data(entry)
                
                # Store token information
                await self._store_token_data(entry)
                
                # Store historical entry FIRST (before watchlist check)
                await self._store_enhanced_watchlist_history_entry(entry)
                
                # Store enhanced watchlist entry (checks for 3rd occurrence and notifies)
                await self._store_enhanced_watchlist_entry(entry)
                
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Error storing {source} entry {entry.get('tokenSymbol', 'unknown')}: {e}")
                continue
        
        return stored_count
    
    async def _store_pool_data(self, entry: Dict[str, Any]) -> None:
        """Store pool data from enhanced entry."""
        from gecko_terminal_collector.database.models import Pool
        
        pool_data = Pool(
            id=f"{self.network}_{entry['poolAddress']}",
            address=entry['poolAddress'],
            name=f"{entry['tokenSymbol']}/{entry.get('quoteTokenSymbol', 'UNKNOWN')}",
            dex_id=entry['dex'].lower(),
            base_token_id=entry.get('baseTokenAddress'),
            quote_token_id=entry.get('quoteTokenAddress'),
            reserve_usd=Decimal(str(entry.get('liquidity', 0))),
            created_at=datetime.now(tz=timezone.utc),
            last_updated=datetime.now(tz=timezone.utc),
            
            # Enhanced fields
            activity_score=min(100.0, entry.get('ranking', 100) / 10.0),  # Convert ranking to score
            discovery_source="enhanced_watchlist",
            collection_priority="high",  # Enhanced watchlist entries are high priority
            metadata_json=json.dumps({
                'source': 'enhanced_watchlist',
                'original_ranking': entry.get('ranking'),
                'volume_24h': entry.get('volume'),
                'market_cap': entry.get('marketCap'),
                'age': entry.get('age'),
                'makers': entry.get('makers')
            })
        )
        
        await self.db_manager.store_pool(pool_data)
    
    async def _store_token_data(self, entry: Dict[str, Any]) -> None:
        """Store token data from enhanced entry."""
        from gecko_terminal_collector.database.models import Token
        
        if not entry.get('baseTokenAddress'):
            return
        
        token_data = Token(
            id=entry['baseTokenAddress'],
            address=entry['baseTokenAddress'],
            name=entry['tokenName'],
            symbol=entry['tokenSymbol'],
            decimals=None,  # Not provided in enhanced data
            network=self.network,
            last_updated=datetime.now(tz=timezone.utc),
            metadata_json=json.dumps({
                'source': 'enhanced_watchlist',
                'price': entry.get('price'),
                'market_cap': entry.get('marketCap'),
                'age': entry.get('age'),
                'price_changes': {
                    '5m': entry.get('priceChange5m'),
                    '1h': entry.get('priceChange1h'),
                    '6h': entry.get('priceChange6h'),
                    '24h': entry.get('priceChange24h')
                }
            })
        )
        
        await self.db_manager.store_token(token_data)
    
    async def _store_enhanced_watchlist_entry(self, entry: Dict[str, Any]) -> None:
        """Store enhanced watchlist entry."""
        from gecko_terminal_collector.database.models import WatchlistEntry
        
        watchlist_entry = WatchlistEntry(
            pool_id=f"{self.network}_{entry['poolAddress']}",
            token_symbol=entry['tokenSymbol'],
            token_name=entry['tokenName'],
            network_address=entry.get('baseTokenAddress'),
            is_active=True,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
            metadata_json=json.dumps({
                'source': 'enhanced_watchlist',
                'ranking': entry.get('ranking'),
                'volume': entry.get('volume'),
                'liquidity': entry.get('liquidity'),
                'transactions': entry.get('transactions'),
                'makers': entry.get('makers'),
                'price_changes': {
                    '5m': entry.get('priceChange5m'),
                    '1h': entry.get('priceChange1h'),
                    '6h': entry.get('priceChange6h'),
                    '24h': entry.get('priceChange24h')
                },
                'detail_url': entry.get('detailUrl'),
                'processed_at': datetime.now(tz=timezone.utc).isoformat()
            })
        )

        is_new = await self.db_manager.store_watchlist_entry(watchlist_entry)        

        # Two-part filtering: 
        # 1. is_new = True (3rd occurrence in 24h)
        # 2. Quality criteria must be met
        
        if is_new:
            # Log that we hit the 3rd occurrence threshold
            logger.info(f"🎯 Token {entry['tokenSymbol']} hit 3rd occurrence threshold - checking quality criteria...")
            
            # Check each criterion individually for debugging
            criteria_met = {
                'priceChange5m >= 0': entry.get('priceChange5m', -999) >= 0,
                'priceChange1h >= 0': entry.get('priceChange1h', -999) >= 0,
                'score >= 30': entry.get('score', 0) >= 30,
                'smart_degen_count >= 0': entry.get('smart_degen_count', 0) >= 0,
                'liquidity >= 5000': entry.get('liquidity', 0) >= 5000,
                'dex in [pump_amm, pump]': entry.get('dex', '') in ['pump_amm', 'pump']
            }
            
            # Log each criterion status
            for criterion, met in criteria_met.items():
                status = "✅" if met else "❌"
                actual_value = entry.get(criterion.split()[0], 'N/A')
                logger.info(f"  {status} {criterion}: {actual_value}")
            
            # Check if all criteria are met
            all_criteria_met = all(criteria_met.values())
            
            if all_criteria_met:
                logger.info(
                    f"🔔 New watchlist entry: {entry['tokenSymbol']} "
                    f"(pool {entry['poolAddress']}) — sending Telegram notification"
                )
                sent = self.telegram.notify_new_watchlist_entry(entry)
                if not sent:
                    logger.error(
                        f"❌ Telegram notification FAILED for {entry['tokenSymbol']} "
                        f"(pool {entry['poolAddress']})"
                    )
                else:
                    logger.info(f"✅ Telegram notification sent for {entry['tokenSymbol']}")
            else:
                failed_criteria = [k for k, v in criteria_met.items() if not v]
                logger.info(
                    f"⏭️  Token {entry['tokenSymbol']} hit 3rd occurrence but failed quality criteria: "
                    f"{', '.join(failed_criteria)}"
                )
        else:
            # Not the 3rd occurrence yet
            logger.debug(f"Token {entry['tokenSymbol']} not yet at 3rd occurrence threshold")

    async def _store_enhanced_watchlist_history_entry(self, entry: Dict[str, Any]) -> None:
        """Store enhanced watchlist history entry."""
        from gecko_terminal_collector.database.models import EnhancedWatchlistHistory
        
        # Parse age to determine data timestamp (approximate)
        data_timestamp = datetime.now(tz=timezone.utc)  # Default to now
        
        history_entry = EnhancedWatchlistHistory(
            source=entry['source'],
            ranking=entry['ranking'],
            
            # Token and pool identification
            token_symbol=entry['tokenSymbol'],
            token_name=entry['tokenName'],
            pool_address=entry['poolAddress'],
            base_token_address=entry.get('baseTokenAddress'),
            quote_token_address=entry.get('quoteTokenAddress'),
            quote_token_symbol=entry.get('quoteTokenSymbol'),
            
            # Network and DEX information
            network=self.network,
            dex=entry['dex'],
            
            # Price and market data
            price=Decimal(str(entry.get('price', 0))) if entry.get('price') else None,
            market_cap=Decimal(str(entry.get('marketCap', 0))) if entry.get('marketCap') else None,
            liquidity=Decimal(str(entry.get('liquidity', 0))) if entry.get('liquidity') else None,
            volume=Decimal(str(entry.get('volume', 0))) if entry.get('volume') else None,
            
            # Price changes
            price_change_5m=Decimal(str(entry.get('priceChange5m', 0))) if entry.get('priceChange5m') else None,
            price_change_1h=Decimal(str(entry.get('priceChange1h', 0))) if entry.get('priceChange1h') else None,
            price_change_6h=Decimal(str(entry.get('priceChange6h', 0))) if entry.get('priceChange6h') else None,
            price_change_24h=Decimal(str(entry.get('priceChange24h', 0))) if entry.get('priceChange24h') else None,
            
            # Activity metrics
            transactions=entry.get('transactions'),
            makers=entry.get('makers'),
            age=entry.get('age'),
            
            # URLs and metadata
            detail_url=entry.get('detailUrl'),
            
            # Timestamps
            collected_at=datetime.now(tz=timezone.utc),
            data_timestamp=data_timestamp,
            
            # Additional metadata
            metadata_json=json.dumps({
                'source': entry['source'],
                'original_data': entry,
                'processed_at': datetime.now(tz=timezone.utc).isoformat(),
                'collector_version': '2.0'
            })
        )
        
        await self.db_manager.store_enhanced_watchlist_history(history_entry)
    
    async def get_collection_statistics(self) -> Dict[str, Any]:
        """Get collection statistics for monitoring."""
        return {
            'collector_type': self.get_collection_key(),
            'available_sources': self.available_sources,
            'sources_to_collect': self.sources_to_collect,
            'sources_processed': self._sources_processed,
            'last_modified_per_source': self._last_file_modified,
            'entries_processed': self._entries_processed,
            'addresses_resolved': self._addresses_resolved,
            'api_calls_made': self._api_calls_made,
            'rate_limit_delay': self.rate_limit_delay,
            'batch_size': self.batch_size,
            'resolution_rate': (
                self._addresses_resolved / self._entries_processed 
                if self._entries_processed > 0 else 0
            )
        }


# Example usage and testing
async def test_enhanced_watchlist_collector():
    """Test function for the enhanced watchlist collector."""
    # This would be used for testing the collector
    pass