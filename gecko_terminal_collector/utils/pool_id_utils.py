"""
Pool ID utilities for handling network-prefixed pool identifiers.

This module provides utilities to handle the technical debt around pool ID formats
where GeckoTerminal API returns IDs like "solana_ABC123" but some parts of the system
expect just "ABC123" or vice versa.
"""

import re
from typing import Optional, Tuple


class PoolIDUtils:
    """Utilities for handling pool ID formats and network prefixes."""
    
    # Known network prefixes from GeckoTerminal API
    KNOWN_NETWORKS = {
        'solana', 'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 
        'avalanche', 'fantom', 'base', 'sui-network', 'ton-network'
    }
    
    @staticmethod
    def parse_pool_id(pool_id: str) -> Tuple[Optional[str], str]:
        """
        Parse a pool ID to extract network and address components.
        
        Args:
            pool_id: Pool ID in format "network_address" or just "address"
            
        Returns:
            Tuple of (network, address) where network may be None
            
        Examples:
            >>> PoolIDUtils.parse_pool_id("solana_ABC123")
            ('solana', 'ABC123')
            >>> PoolIDUtils.parse_pool_id("ABC123")
            (None, 'ABC123')
        """
        if '_' not in pool_id:
            return None, pool_id
            
        parts = pool_id.split('_', 1)
        if len(parts) == 2 and parts[0] in PoolIDUtils.KNOWN_NETWORKS:
            return parts[0], parts[1]
        else:
            # If prefix is not a known network, treat entire string as address
            return None, pool_id
    
    @staticmethod
    def ensure_network_prefix(pool_id: str, network: str) -> str:
        """
        Ensure pool ID has the correct network prefix.
        
        Args:
            pool_id: Pool ID that may or may not have network prefix
            network: Network name to ensure as prefix
            
        Returns:
            Pool ID with network prefix
            
        Examples:
            >>> PoolIDUtils.ensure_network_prefix("ABC123", "solana")
            'solana_ABC123'
            >>> PoolIDUtils.ensure_network_prefix("solana_ABC123", "solana")
            'solana_ABC123'
            >>> PoolIDUtils.ensure_network_prefix("ethereum_ABC123", "solana")
            'solana_ABC123'  # Replaces incorrect network
        """
        existing_network, address = PoolIDUtils.parse_pool_id(pool_id)
        return f"{network}_{address}"
    
    @staticmethod
    def remove_network_prefix(pool_id: str) -> str:
        """
        Remove network prefix from pool ID, returning just the address.
        
        Args:
            pool_id: Pool ID that may have network prefix
            
        Returns:
            Pool address without network prefix
            
        Examples:
            >>> PoolIDUtils.remove_network_prefix("solana_ABC123")
            'ABC123'
            >>> PoolIDUtils.remove_network_prefix("ABC123")
            'ABC123'
        """
        _, address = PoolIDUtils.parse_pool_id(pool_id)
        return address
    
    @staticmethod
    def get_network_from_pool_id(pool_id: str) -> Optional[str]:
        """
        Extract network from pool ID.
        
        Args:
            pool_id: Pool ID that may have network prefix
            
        Returns:
            Network name or None if no valid network prefix found
        """
        network, _ = PoolIDUtils.parse_pool_id(pool_id)
        return network
    
    @staticmethod
    def normalize_pool_id(pool_id: str, default_network: str = "solana") -> str:
        """
        Normalize pool ID to ensure consistent format with network prefix.
        
        Args:
            pool_id: Pool ID in any format
            default_network: Network to use if none is detected
            
        Returns:
            Normalized pool ID with network prefix
        """
        network, address = PoolIDUtils.parse_pool_id(pool_id)
        if network is None:
            network = default_network
        return f"{network}_{address}"
    
    @staticmethod
    def is_valid_pool_id_format(pool_id: str) -> bool:
        """
        Check if pool ID follows expected format.
        
        Args:
            pool_id: Pool ID to validate
            
        Returns:
            True if format is valid
        """
        if not pool_id or not isinstance(pool_id, str):
            return False
            
        # Must be at least some minimum length
        if len(pool_id) < 5:
            return False
            
        # If it has a prefix, it should be a known network
        network, address = PoolIDUtils.parse_pool_id(pool_id)
        if '_' in pool_id and network is None:
            # Has underscore but not a known network prefix
            return False
            
        # Address part should be alphanumeric (allowing some special chars)
        if not re.match(r'^[a-zA-Z0-9_-]+$', address):
            return False
            
        return True


# Convenience functions for backward compatibility
def ensure_solana_prefix(pool_id: str) -> str:
    """Ensure pool ID has solana_ prefix."""
    return PoolIDUtils.ensure_network_prefix(pool_id, "solana")


def remove_solana_prefix(pool_id: str) -> str:
    """Remove solana_ prefix from pool ID."""
    return PoolIDUtils.remove_network_prefix(pool_id)


def normalize_pool_id_for_network(pool_id: str, network: str) -> str:
    """Normalize pool ID for specific network."""
    return PoolIDUtils.ensure_network_prefix(pool_id, network)