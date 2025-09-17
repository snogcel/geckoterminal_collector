"""
Unicode handling utilities for safe string processing and logging.
"""

import logging
import sys
import json
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class UnicodeHandler:
    """Handle Unicode encoding issues across the application."""
    
    @staticmethod
    def safe_str(value: Any, fallback: str = "N/A") -> str:
        """Convert any value to a safe ASCII string."""
        if value is None:
            return fallback
        
        try:
            # Convert to string first
            str_value = str(value)
            # Try to encode/decode to ASCII, replacing problematic characters
            return str_value.encode('ascii', 'replace').decode('ascii')
        except Exception as e:
            logger.warning(f"Unicode conversion failed for value: {e}")
            return fallback
    
    @staticmethod
    def safe_pool_name(pool_data: Dict) -> str:
        """Extract a safe pool name for logging/display."""
        name = pool_data.get('name', '')
        pool_id = pool_data.get('id', 'unknown')
        
        if not name:
            return f"Pool_{pool_id[:8]}..."
        
        # Replace Unicode characters with ASCII equivalents
        safe_name = name.encode('ascii', 'replace').decode('ascii')
        
        # Clean up replacement characters
        safe_name = safe_name.replace('?', '_')
        
        return safe_name[:50]  # Limit length
    
    @staticmethod
    def configure_console_encoding():
        """Configure console encoding for better Unicode support."""
        if sys.platform.startswith('win'):
            try:
                # Try to set UTF-8 encoding on Windows
                import codecs
                import io
                
                # Only reconfigure if not already UTF-8
                if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding.lower() not in ['utf-8', 'utf8']:
                    # Wrap stdout/stderr with UTF-8 encoding
                    if hasattr(sys.stdout, 'buffer'):
                        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                    if hasattr(sys.stderr, 'buffer'):
                        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
                    
                    logger.info("Configured UTF-8 console encoding")
                
            except Exception as e:
                logger.warning(f"Could not configure UTF-8 encoding: {e}")
    
    @staticmethod
    def safe_log_data(data: Dict, max_length: int = 200) -> str:
        """Create a safe, truncated representation of data for logging."""
        try:
            # Convert to JSON string with ASCII encoding
            json_str = json.dumps(data, ensure_ascii=True, separators=(',', ':'))
            
            if len(json_str) > max_length:
                return json_str[:max_length] + "..."
            
            return json_str
        except Exception as e:
            logger.warning(f"Could not serialize data for logging: {e}")
            return f"<Data serialization failed: {type(data).__name__}>"
    
    @staticmethod
    def safe_format_pool_info(pool_data: Dict) -> str:
        """Format pool information safely for logging."""
        try:
            pool_id = pool_data.get('id', 'unknown')
            safe_name = UnicodeHandler.safe_pool_name(pool_data)
            volume = pool_data.get('volume_usd_h24', 0)
            liquidity = pool_data.get('reserve_in_usd', 0)
            
            # Convert to float for formatting
            try:
                volume_float = float(volume) if volume else 0
                liquidity_float = float(liquidity) if liquidity else 0
                return f"Pool {pool_id[:20]}... | {safe_name} | Vol: ${volume_float:,.0f} | Liq: ${liquidity_float:,.0f}"
            except (ValueError, TypeError):
                return f"Pool {pool_id[:20]}... | {safe_name} | Vol: {volume} | Liq: {liquidity}"
        except Exception as e:
            logger.warning(f"Error formatting pool info: {e}")
            return f"Pool {pool_data.get('id', 'unknown')[:20]}... | <formatting error>"