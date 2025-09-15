"""
Enhanced new pools collector with automatic watchlist integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.database.models import WatchlistEntry
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer

logger = logging.getLogger(__name__)


class EnhancedNewPoolsCollector(NewPoolsCollector):
    """
    Enhanced new pools collector with automatic watchlist integration and smart filtering.
    
    This collector extends the base NewPoolsCollector to automatically evaluate
    discovered pools and add promising ones to the watchlist based on configurable criteria.
    """
    
    def __init__(
        self,
        config,
        db_manager,
        network: str,
        auto_watchlist: bool = False,
        min_liquidity_usd: float = 1000.0,
        min_volume_24h_usd: float = 100.0,
        max_age_hours: int = 24,
        min_activity_score: float = 60.0,
        **kwargs
    ):
        """
        Initialize the enhanced new pools collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            network: Network identifier to collect pools for
            auto_watchlist: Whether to automatically add pools to watchlist
            min_liquidity_usd: Minimum liquidity in USD for watchlist consideration
            min_volume_24h_usd: Minimum 24h volume in USD for watchlist consideration
            max_age_hours: Maximum age in hours for "new" pool consideration
            min_activity_score: Minimum activity score for watchlist addition
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(config, db_manager, network, **kwargs)
        
        # Auto-watchlist configuration
        self.auto_watchlist = auto_watchlist
        self.min_liquidity_usd = min_liquidity_usd
        self.min_volume_24h_usd = min_volume_24h_usd
        self.max_age_hours = max_age_hours
        self.min_activity_score = min_activity_score
        
        # Initialize activity scorer
        self.activity_scorer = ActivityScorer()
        
        # Statistics tracking
        self.stats = {
            'pools_evaluated': 0,
            'pools_added_to_watchlist': 0,
            'pools_rejected_liquidity': 0,
            'pools_rejected_volume': 0,
            'pools_rejected_age': 0,
            'pools_rejected_activity': 0,
            'pools_already_in_watchlist': 0
        }
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        return f"enhanced_new_pools_{self.network}"
    
    async def collect(self) -> CollectionResult:
        """
        Collect new pools data with enhanced watchlist integration.
        
        Returns:
            CollectionResult with collection status and enhanced statistics
        """
        # Reset statistics for this collection run
        self.stats = {key: 0 for key in self.stats.keys()}
        
        # Run base collection logic
        result = await super().collect()
        
        # If auto-watchlist is enabled and base collection was successful
        if self.auto_watchlist and result.success:
            await self._process_auto_watchlist(result)
        
        # Add enhanced statistics to result metadata
        if result.metadata:
            result.metadata.update({
                'auto_watchlist_enabled': self.auto_watchlist,
                'watchlist_stats': self.stats.copy(),
                'watchlist_criteria': {
                    'min_liquidity_usd': self.min_liquidity_usd,
                    'min_volume_24h_usd': self.min_volume_24h_usd,
                    'max_age_hours': self.max_age_hours,
                    'min_activity_score': self.min_activity_score
                }
            })
        
        return result
    
    async def _process_auto_watchlist(self, collection_result: CollectionResult) -> None:
        """
        Process pools for automatic watchlist addition.
        
        Args:
            collection_result: Result from the base collection process
        """
        try:
            self.logger.info(f"Processing auto-watchlist for {self.network} pools...")
            
            # Re-fetch the pools data that was just collected
            # In a real implementation, we'd pass this data through the collection process
            # For now, we'll fetch recent pools from the database
            recent_pools = await self._get_recently_collected_pools()
            
            for pool_data in recent_pools:
                await self._evaluate_pool_for_watchlist(pool_data)
            
            self.logger.info(
                f"Auto-watchlist processing completed: "
                f"{self.stats['pools_evaluated']} evaluated, "
                f"{self.stats['pools_added_to_watchlist']} added to watchlist"
            )
            
        except Exception as e:
            self.logger.error(f"Error in auto-watchlist processing: {e}")
    
    async def _get_recently_collected_pools(self) -> List[Dict]:
        """
        Get pools that were recently collected (within the last hour).
        
        Returns:
            List of pool data dictionaries
        """
        try:
            # This would need to be implemented in the database manager
            # For now, return empty list as placeholder
            return []
            
        except Exception as e:
            self.logger.error(f"Error fetching recently collected pools: {e}")
            return []
    
    async def _evaluate_pool_for_watchlist(self, pool_data: Dict) -> None:
        """
        Evaluate a single pool for watchlist addition.
        
        Args:
            pool_data: Pool data dictionary from new_pools_history
        """
        try:
            self.stats['pools_evaluated'] += 1
            
            pool_id = pool_data.get('pool_id')
            if not pool_id:
                return
            
            # Check if already in watchlist
            if await self._is_already_in_watchlist(pool_id):
                self.stats['pools_already_in_watchlist'] += 1
                return
            
            # Apply filtering criteria
            if not await self._meets_watchlist_criteria(pool_data):
                return
            
            # Calculate activity score
            activity_score = self.activity_scorer.calculate_pool_activity_score(pool_data)
            
            if activity_score < self.min_activity_score:
                self.stats['pools_rejected_activity'] += 1
                self.logger.debug(
                    f"Pool {pool_id} rejected for low activity score: {activity_score}"
                )
                return
            
            # Add to watchlist
            await self._add_pool_to_watchlist(pool_data, activity_score)
            
        except Exception as e:
            self.logger.error(f"Error evaluating pool {pool_data.get('pool_id')}: {e}")
    
    async def _is_already_in_watchlist(self, pool_id: str) -> bool:
        """
        Check if pool is already in the watchlist.
        
        Args:
            pool_id: Pool identifier
            
        Returns:
            True if pool is already in watchlist
        """
        try:
            existing_entry = await self.db_manager.get_watchlist_entry_by_pool_id(pool_id)
            return existing_entry is not None
            
        except Exception as e:
            self.logger.error(f"Error checking watchlist for pool {pool_id}: {e}")
            return False
    
    async def _meets_watchlist_criteria(self, pool_data: Dict) -> bool:
        """
        Check if pool meets basic watchlist criteria.
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            True if pool meets criteria
        """
        try:
            # Extract values with safe conversion
            reserve_usd = float(pool_data.get('reserve_in_usd', 0) or 0)
            volume_24h = float(pool_data.get('volume_usd_h24', 0) or 0)
            
            # Check liquidity threshold
            if reserve_usd < self.min_liquidity_usd:
                self.stats['pools_rejected_liquidity'] += 1
                return False
            
            # Check volume threshold
            if volume_24h < self.min_volume_24h_usd:
                self.stats['pools_rejected_volume'] += 1
                return False
            
            # Check age threshold
            if not self._is_recently_created(pool_data):
                self.stats['pools_rejected_age'] += 1
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking criteria for pool {pool_data.get('pool_id')}: {e}")
            return False
    
    def _is_recently_created(self, pool_data: Dict) -> bool:
        """
        Check if pool was created recently (within max_age_hours).
        
        Args:
            pool_data: Pool data dictionary
            
        Returns:
            True if pool is recently created
        """
        try:
            pool_created_at = pool_data.get('pool_created_at')
            if not pool_created_at:
                return False
            
            # Handle different datetime formats
            if isinstance(pool_created_at, str):
                if pool_created_at.endswith('Z'):
                    pool_created_at = pool_created_at[:-1] + '+00:00'
                pool_created_at = datetime.fromisoformat(pool_created_at)
            
            # Check if created within the specified time window
            age_threshold = datetime.now() - timedelta(hours=self.max_age_hours)
            return pool_created_at >= age_threshold
            
        except Exception as e:
            self.logger.error(f"Error checking pool age: {e}")
            return False
    
    async def _add_pool_to_watchlist(self, pool_data: Dict, activity_score: float) -> None:
        """
        Add pool to watchlist with auto-generated metadata.
        
        Args:
            pool_data: Pool data dictionary
            activity_score: Calculated activity score
        """
        try:
            pool_id = pool_data.get('pool_id')
            pool_name = pool_data.get('name', '')
            
            # Extract token symbol from pool name (e.g., "TOKEN / SOL" -> "TOKEN")
            token_symbol = self._extract_token_symbol(pool_name)
            
            # Create watchlist entry
            watchlist_entry = WatchlistEntry(
                pool_id=pool_id,
                token_symbol=token_symbol,
                token_name=pool_name,
                network_address=pool_data.get('base_token_id', ''),
                is_active=True
            )
            
            # Store the entry
            await self.db_manager.add_watchlist_entry(watchlist_entry)
            
            self.stats['pools_added_to_watchlist'] += 1
            
            self.logger.info(
                f"Added pool to watchlist: {pool_id} ({token_symbol}) "
                f"- Activity Score: {activity_score:.1f}"
            )
            
        except Exception as e:
            self.logger.error(f"Error adding pool to watchlist {pool_data.get('pool_id')}: {e}")
    
    def _extract_token_symbol(self, pool_name: str) -> str:
        """
        Extract token symbol from pool name.
        
        Args:
            pool_name: Pool name (e.g., "TOKEN / SOL")
            
        Returns:
            Extracted token symbol or truncated pool name
        """
        if not pool_name:
            return "UNKNOWN"
        
        # Handle common pool name formats
        if ' / ' in pool_name:
            # Format: "TOKEN / SOL" -> "TOKEN"
            return pool_name.split(' / ')[0].strip()
        elif '/' in pool_name:
            # Format: "TOKEN/SOL" -> "TOKEN"
            return pool_name.split('/')[0].strip()
        else:
            # Use first 10 characters if no clear separator
            return pool_name[:10].strip()
    
    def get_collection_stats(self) -> Dict:
        """
        Get detailed collection statistics.
        
        Returns:
            Dictionary with collection and watchlist statistics
        """
        return {
            'collector_type': self.get_collection_key(),
            'network': self.network,
            'auto_watchlist_enabled': self.auto_watchlist,
            'criteria': {
                'min_liquidity_usd': self.min_liquidity_usd,
                'min_volume_24h_usd': self.min_volume_24h_usd,
                'max_age_hours': self.max_age_hours,
                'min_activity_score': self.min_activity_score
            },
            'stats': self.stats.copy()
        }