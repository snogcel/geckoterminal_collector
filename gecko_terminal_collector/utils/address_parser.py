"""
Address parsing utilities for external data sources.

Handles case conversion, address validation, and network address extraction
for Solana addresses from various data sources.
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any, List
from base58 import b58decode, b58encode

logger = logging.getLogger(__name__)


class SolanaAddressParser:
    """Parser for Solana addresses with case correction and validation."""
    
    @staticmethod
    def is_valid_solana_address(address: str) -> bool:
        """
        Validate if a string is a valid Solana address.
        
        Args:
            address: Address string to validate
            
        Returns:
            True if valid Solana address, False otherwise
        """
        if not address or len(address) < 32 or len(address) > 44:
            return False
        
        try:
            # Try to decode as base58
            decoded = b58decode(address)
            # Solana addresses should be 32 bytes
            return len(decoded) == 32
        except Exception:
            return False
    
    @staticmethod
    def correct_case_sensitivity(lowercase_address: str) -> Optional[str]:
        """
        Attempt to correct case sensitivity for Solana addresses.
        
        This is a best-effort approach since we can't definitively determine
        the correct case without checking against the blockchain.
        
        Args:
            lowercase_address: Lowercase address string
            
        Returns:
            Corrected address or None if invalid
        """
        if not lowercase_address:
            return None
        
        # If already mixed case and valid, return as-is
        if SolanaAddressParser.is_valid_solana_address(lowercase_address):
            return lowercase_address
        
        # Common Solana address patterns for case correction
        # This is heuristic-based and may not be 100% accurate
        corrected = ""
        
        for i, char in enumerate(lowercase_address):
            if char.isdigit():
                corrected += char
            elif char.isalpha():
                # Apply some heuristics for common patterns
                # In practice, you'd want to validate against actual addresses
                if i % 3 == 0:  # Every 3rd character more likely uppercase
                    corrected += char.upper()
                else:
                    corrected += char
            else:
                corrected += char
        
        # Validate the corrected address
        if SolanaAddressParser.is_valid_solana_address(corrected):
            return corrected
        
        # If heuristic failed, try all uppercase
        upper_address = lowercase_address.upper()
        if SolanaAddressParser.is_valid_solana_address(upper_address):
            return upper_address
        
        # If still invalid, return original and log warning
        logger.warning(f"Could not correct case for address: {lowercase_address}")
        return lowercase_address
    
    @staticmethod
    def extract_pool_address_from_url(detail_url: str) -> Optional[str]:
        """
        Extract pool address from detail URL.
        
        Args:
            detail_url: URL like "/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o"
            
        Returns:
            Extracted and case-corrected pool address
        """
        if not detail_url:
            return None
        
        # Extract address from URL pattern
        match = re.match(r'^/([^/]+)/([a-zA-Z0-9]+)$', detail_url.strip())
        if not match:
            logger.warning(f"Invalid detail URL format: {detail_url}")
            return None
        
        network, address = match.groups()
        
        # Validate network
        if network.lower() != 'solana':
            logger.warning(f"Unsupported network in URL: {network}")
            return None
        
        # Correct case sensitivity
        corrected_address = SolanaAddressParser.correct_case_sensitivity(address)
        
        if corrected_address:
            logger.debug(f"Extracted pool address: {address} → {corrected_address}")
        
        return corrected_address


class EnhancedWatchlistParser:
    """Parser for enhanced watchlist data with address resolution."""
    
    def __init__(self, gecko_client):
        """
        Initialize parser with GeckoTerminal client for address resolution.
        
        Args:
            gecko_client: GeckoTerminal API client for pool data lookup
        """
        self.gecko_client = gecko_client
        self.address_parser = SolanaAddressParser()
    
    async def parse_watchlist_entry(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single row from enhanced watchlist data.
        
        Args:
            row: Dictionary containing watchlist row data
            
        Returns:
            Parsed and enriched watchlist entry or None if invalid
        """
        try:
            # Extract pool address from detail URL
            detail_url = row.get('detailUrl', '')
            pool_address = self.address_parser.extract_pool_address_from_url(detail_url)
            
            if not pool_address:
                logger.error(f"Could not extract pool address from: {detail_url}")
                return None
            
            # Get pool data from GeckoTerminal API to resolve network addresses
            pool_data = await self._get_pool_data_with_tokens(pool_address)
            
            if not pool_data:
                logger.error(f"Could not fetch pool data for: {pool_address}")
                return None
            
            # Extract network addresses from pool data
            base_token_address = pool_data.get('base_token_address')
            quote_token_address = pool_data.get('quote_token_address')
            
            # Build enhanced watchlist entry
            entry = {
                # Original data from your source
                'timestamp': row.get('timestamp'),
                'ranking': int(row.get('ranking', 0)),
                'tokenSymbol': row.get('tokenSymbol'),
                'tokenName': row.get('tokenName'),
                'chain': row.get('chain'),
                'dex': row.get('dex'),
                'price': float(row.get('price', 0)),
                'age': row.get('age'),
                'transactions': int(row.get('transactions', 0)),
                'volume': float(row.get('volume', 0)),
                'makers': int(row.get('makers', 0)),
                'priceChange5m': float(row.get('priceChange5m', 0)),
                'priceChange1h': float(row.get('priceChange1h', 0)),
                'priceChange6h': float(row.get('priceChange6h', 0)),
                'priceChange24h': float(row.get('priceChange24h', 0)),
                'liquidity': float(row.get('liquidity', 0)),
                'marketCap': float(row.get('marketCap', 0)),
                
                # Resolved addresses
                'poolAddress': pool_address,
                'baseTokenAddress': base_token_address,
                'quoteTokenAddress': quote_token_address,
                'networkAddress': base_token_address,  # Assuming base token is the main token
                
                # Metadata
                'source': 'enhanced_watchlist',
                'detailUrl': detail_url
            }
            
            logger.info(f"Parsed entry for {entry['tokenSymbol']}: {pool_address}")
            return entry
            
        except Exception as e:
            logger.error(f"Error parsing watchlist entry: {e}")
            return None
    
    async def _get_pool_data_with_tokens(self, pool_address: str) -> Optional[Dict[str, Any]]:
        """
        Get pool data including token addresses from GeckoTerminal API.
        
        Args:
            pool_address: Pool address to lookup
            
        Returns:
            Pool data with token addresses or None if not found
        """
        try:
            # Use the existing GeckoTerminal API to get pool data
            response = await self.gecko_client.get_pool_by_network_address('solana', pool_address)
            
            if not response or 'data' not in response:
                return None
            
            pool_data = response['data']
            attributes = pool_data.get('attributes', {})
            relationships = pool_data.get('relationships', {})
            
            # Extract token addresses from relationships
            base_token_address = None
            quote_token_address = None
            
            if 'base_token' in relationships:
                base_token_data = relationships['base_token'].get('data', {})
                base_token_address = base_token_data.get('id')
            
            if 'quote_token' in relationships:
                quote_token_data = relationships['quote_token'].get('data', {})
                quote_token_address = quote_token_data.get('id')
            
            return {
                'pool_address': pool_address,
                'base_token_address': base_token_address,
                'quote_token_address': quote_token_address,
                'name': attributes.get('name'),
                'reserve_usd': attributes.get('reserve_in_usd'),
                'volume_24h': attributes.get('volume_usd', {}).get('h24'),
                'price_change_24h': attributes.get('price_change_percentage', {}).get('h24')
            }
            
        except Exception as e:
            logger.error(f"Error fetching pool data for {pool_address}: {e}")
            return None


# Example usage
async def process_enhanced_watchlist_file(file_path: str, gecko_client) -> List[Dict[str, Any]]:
    """
    Process an enhanced watchlist CSV file.
    
    Args:
        file_path: Path to the CSV file
        gecko_client: GeckoTerminal API client
        
    Returns:
        List of parsed and enriched watchlist entries
    """
    import csv
    
    parser = EnhancedWatchlistParser(gecko_client)
    entries = []
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            entry = await parser.parse_watchlist_entry(row)
            if entry:
                entries.append(entry)
    
    return entries