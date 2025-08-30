"""
Watchlist processing utilities for loading and parsing watchlist CSV files.
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from gecko_terminal_collector.config.models import CollectionConfig

logger = logging.getLogger(__name__)


class WatchlistProcessor:
    """
    Utility class for processing watchlist CSV files.
    
    Handles loading, parsing, and validation of watchlist entries
    for use in data collection workflows.
    """
    
    def __init__(self, config: CollectionConfig):
        """
        Initialize watchlist processor.
        
        Args:
            config: System configuration
        """
        self.config = config
        
    async def load_watchlist(self, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load watchlist items from CSV file.
        
        Args:
            file_path: Path to watchlist CSV file (optional, uses default if not provided)
            
        Returns:
            List of watchlist item dictionaries
        """
        if file_path is None:
            file_path = "specs/watchlist.csv"  # Default path
            
        try:
            watchlist_path = Path(file_path)
            
            if not watchlist_path.exists():
                logger.error(f"Watchlist file not found: {file_path}")
                return []
            
            watchlist_items = []
            
            with open(watchlist_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    try:
                        # Clean and validate row data
                        item = self._clean_watchlist_item(row)
                        
                        if self._validate_watchlist_item(item):
                            watchlist_items.append(item)
                        else:
                            logger.warning(f"Invalid watchlist item at row {row_num}: {item}")
                            
                    except Exception as e:
                        logger.error(f"Error processing watchlist row {row_num}: {e}")
                        continue
            
            logger.info(f"Loaded {len(watchlist_items)} valid watchlist items from {file_path}")
            return watchlist_items
            
        except Exception as e:
            logger.error(f"Error loading watchlist from {file_path}: {e}")
            return []
    
    def _clean_watchlist_item(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        Clean and normalize watchlist item data.
        
        Args:
            row: Raw CSV row data
            
        Returns:
            Cleaned watchlist item dictionary
        """
        # Remove quotes and whitespace from all fields
        cleaned = {}
        for key, value in row.items():
            if isinstance(value, str):
                # Remove surrounding quotes and whitespace
                cleaned_value = value.strip().strip('"').strip("'").strip()
                cleaned[key] = cleaned_value if cleaned_value else None
            else:
                cleaned[key] = value
        
        return cleaned
    
    def _validate_watchlist_item(self, item: Dict[str, Any]) -> bool:
        """
        Validate watchlist item has required fields.
        
        Args:
            item: Watchlist item dictionary
            
        Returns:
            True if item is valid, False otherwise
        """
        required_fields = ['tokenSymbol', 'chain', 'dex']
        
        # Check required fields
        for field in required_fields:
            if not item.get(field):
                logger.warning(f"Missing required field '{field}' in watchlist item")
                return False
        
        # Must have either poolAddress or networkAddress
        if not item.get('poolAddress') and not item.get('networkAddress'):
            logger.warning("Watchlist item must have either poolAddress or networkAddress")
            return False
        
        # Validate chain matches configuration (allow SOL as alias for SOLANA)
        expected_chain = self.config.dexes.network.upper()
        item_chain = item.get('chain', '').upper()
        
        # Allow SOL as alias for SOLANA
        if item_chain == 'SOL' and expected_chain == 'SOLANA':
            item_chain = 'SOLANA'
        
        if item_chain != expected_chain:
            logger.warning(f"Chain mismatch: expected {expected_chain}, got {item_chain}")
            return False
        
        # Validate DEX is in configured targets (case insensitive)
        item_dex = item.get('dex', '').lower()
        configured_dexes = [dex.lower() for dex in self.config.dexes.targets]
        
        if item_dex not in configured_dexes:
            logger.warning(f"DEX '{item_dex}' not in configured targets: {configured_dexes}")
            return False
        
        return True
    
    async def find_watchlist_item(self, 
                                 identifier: str, 
                                 file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find a specific watchlist item by symbol, pool address, or network address.
        
        Args:
            identifier: Token symbol, pool address, or network address to search for
            file_path: Path to watchlist CSV file (optional)
            
        Returns:
            Matching watchlist item or None if not found
        """
        watchlist_items = await self.load_watchlist(file_path)
        
        identifier_lower = identifier.lower()
        
        for item in watchlist_items:
            # Check token symbol (case insensitive)
            if item.get('tokenSymbol', '').lower() == identifier_lower:
                return item
            
            # Check pool address (exact match)
            if item.get('poolAddress') == identifier:
                return item
            
            # Check network address (exact match)
            if item.get('networkAddress') == identifier:
                return item
        
        return None
    
    async def get_watchlist_summary(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary statistics about the watchlist.
        
        Args:
            file_path: Path to watchlist CSV file (optional)
            
        Returns:
            Dictionary with watchlist summary statistics
        """
        watchlist_items = await self.load_watchlist(file_path)
        
        if not watchlist_items:
            return {
                'total_items': 0,
                'by_dex': {},
                'by_chain': {},
                'has_pool_address': 0,
                'has_network_address': 0
            }
        
        # Count by DEX
        dex_counts = {}
        for item in watchlist_items:
            dex = item.get('dex', 'Unknown')
            dex_counts[dex] = dex_counts.get(dex, 0) + 1
        
        # Count by chain
        chain_counts = {}
        for item in watchlist_items:
            chain = item.get('chain', 'Unknown')
            chain_counts[chain] = chain_counts.get(chain, 0) + 1
        
        # Count address types
        pool_address_count = sum(1 for item in watchlist_items if item.get('poolAddress'))
        network_address_count = sum(1 for item in watchlist_items if item.get('networkAddress'))
        
        return {
            'total_items': len(watchlist_items),
            'by_dex': dex_counts,
            'by_chain': chain_counts,
            'has_pool_address': pool_address_count,
            'has_network_address': network_address_count,
            'items': watchlist_items
        }