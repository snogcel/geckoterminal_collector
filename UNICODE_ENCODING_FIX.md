# Unicode Encoding Issue Fix

## Problem Analysis

**Error**: `'charmap' codec can't encode character '\U0001f40b' in position 89: character maps to <undefined>`

**Root Cause**: Windows console encoding issue when trying to print Unicode characters (emojis, non-ASCII characters) from pool names like:
- 🐋 (whale emoji - \U0001f40b)
- 黄色带 (Chinese characters)
- Various crypto token names with special characters

**Technical Debt**: Direct `print()` statements in production code without proper encoding handling.

## Immediate Fix

### 1. Remove Debug Print Statement
The immediate cause is in `gecko_terminal_collector/collectors/new_pools_collector.py` line 684:

```python
print("pool_data: ", pool_data)  # ← This causes the Unicode error
```

### 2. Replace with Proper Logging
Instead of `print()`, use the logger with safe Unicode handling:

```python
# Safe logging with Unicode handling
self.logger.debug(f"Processing pool: {pool_data.get('id', 'unknown')}")
if self.logger.isEnabledFor(logging.DEBUG):
    # Only format detailed data for debug level
    safe_name = pool_data.get('name', 'N/A').encode('ascii', 'replace').decode('ascii')
    self.logger.debug(f"Pool name (ASCII-safe): {safe_name}")
```

## Comprehensive Solution

### 1. Create Unicode Utility Module

```python
# gecko_terminal_collector/utils/unicode_utils.py
import logging
import sys
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
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')
                logger.info("Configured UTF-8 console encoding")
            except Exception as e:
                logger.warning(f"Could not configure UTF-8 encoding: {e}")
    
    @staticmethod
    def safe_log_data(data: Dict, max_length: int = 200) -> str:
        """Create a safe, truncated representation of data for logging."""
        try:
            # Convert to JSON string with ASCII encoding
            import json
            json_str = json.dumps(data, ensure_ascii=True, separators=(',', ':'))
            
            if len(json_str) > max_length:
                return json_str[:max_length] + "..."
            
            return json_str
        except Exception as e:
            logger.warning(f"Could not serialize data for logging: {e}")
            return f"<Data serialization failed: {type(data).__name__}>"
```

### 2. Update New Pools Collector

```python
# In gecko_terminal_collector/collectors/new_pools_collector.py

from gecko_terminal_collector.utils.unicode_utils import UnicodeHandler

class NewPoolsCollector(BaseDataCollector):
    def __init__(self, ...):
        # Configure Unicode handling
        UnicodeHandler.configure_console_encoding()
        # ... rest of init
    
    async def collect(self) -> CollectionResult:
        # ... existing code ...
        
        # Replace the problematic print statement
        for pool_data in pools_data:
            try:
                # Safe logging instead of print
                safe_name = UnicodeHandler.safe_pool_name(pool_data)
                pool_id = pool_data.get('id', 'unknown')
                
                self.logger.debug(f"Processing pool {pool_id}: {safe_name}")
                
                # For detailed debugging, use safe data logging
                if self.logger.isEnabledFor(logging.DEBUG):
                    safe_data = UnicodeHandler.safe_log_data(pool_data)
                    self.logger.debug(f"Pool data: {safe_data}")
                
                # ... rest of processing ...
                
            except Exception as e:
                safe_pool_id = UnicodeHandler.safe_str(pool_data.get('id', 'unknown'))
                error_msg = f"Error processing pool {safe_pool_id}: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
                continue
```

### 3. Update Logging Configuration

```python
# In config.yaml or logging setup
logging:
  version: 1
  formatters:
    safe_formatter:
      format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      # Ensure ASCII-safe formatting
  handlers:
    console:
      class: logging.StreamHandler
      formatter: safe_formatter
      # Use UTF-8 encoding where possible
      encoding: utf-8
```

### 4. Application-Wide Unicode Policy

```python
# gecko_terminal_collector/__init__.py or main entry point

import sys
import locale
from gecko_terminal_collector.utils.unicode_utils import UnicodeHandler

def configure_unicode_support():
    """Configure application-wide Unicode support."""
    
    # Set up console encoding
    UnicodeHandler.configure_console_encoding()
    
    # Set locale for better Unicode support
    try:
        if sys.platform.startswith('win'):
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        else:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        # Fallback to system default
        pass
    
    # Set default encoding for string operations
    if hasattr(sys, 'set_int_max_str_digits'):
        # Python 3.11+ security feature
        sys.set_int_max_str_digits(0)

# Call this at application startup
configure_unicode_support()
```

## Implementation Priority

### Phase 1: Immediate Fix (5 minutes)
1. Remove/comment the problematic `print("pool_data: ", pool_data)` line
2. Replace with safe logging

### Phase 2: Robust Solution (30 minutes)
1. Create `unicode_utils.py` module
2. Update new pools collector to use safe Unicode handling
3. Configure console encoding at startup

### Phase 3: System-Wide Improvement (1 hour)
1. Audit all collectors for similar Unicode issues
2. Implement consistent Unicode handling across the application
3. Add Unicode handling tests

## Benefits

1. **Eliminates Crashes**: No more Unicode encoding errors
2. **Better Debugging**: Safe, readable log output
3. **Cross-Platform**: Works consistently on Windows, Linux, macOS
4. **Maintainable**: Centralized Unicode handling logic
5. **Future-Proof**: Handles any Unicode characters in crypto token names

## Testing

```python
# Test with problematic pool names
test_pools = [
    {"id": "test1", "name": "🐋 Whale Token"},
    {"id": "test2", "name": "黄色带 Yellow Band"},
    {"id": "test3", "name": "Café ñoño 🚀"},
    {"id": "test4", "name": "Normal Token"}
]

for pool in test_pools:
    safe_name = UnicodeHandler.safe_pool_name(pool)
    print(f"Original: {pool['name']} → Safe: {safe_name}")
```

This solution addresses the technical debt by:
- Removing unsafe `print()` statements
- Implementing proper Unicode handling
- Creating reusable utilities
- Following logging best practices
- Ensuring cross-platform compatibility