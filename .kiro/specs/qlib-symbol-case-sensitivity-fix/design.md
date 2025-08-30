# Design Document

## Overview

This design addresses the case-sensitivity issue in the QLib integration layer by implementing a robust symbol mapping system that preserves cryptocurrency address case while providing case-insensitive lookup capabilities. The solution maintains backward compatibility while ensuring reliable symbol-to-pool mapping.

## Architecture

### Current Problem Analysis

The current implementation has these issues:
1. Symbol generation preserves case correctly (`_generate_symbol_name` method)
2. Reverse lookup (`_get_pool_for_symbol`) expects exact case match
3. External systems (QLib, data processing tools) often normalize symbols to lowercase
4. Case mismatch breaks the symbol-to-pool mapping

### Proposed Solution Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   QLib Client   │───▶│  Symbol Mapper   │───▶│   Pool Cache    │
│                 │    │                  │    │                 │
│ - Case variants │    │ - Case mapping   │    │ - Original data │
│ - Lookup calls  │    │ - Fuzzy matching │    │ - Pool objects  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  Database Layer  │
                       │                  │
                       │ - Pool storage   │
                       │ - Index queries  │
                       └──────────────────┘
```

## Components and Interfaces

### 1. Enhanced Symbol Mapper

**Purpose:** Provide robust symbol-to-pool mapping with case-insensitive lookup capabilities.

**Key Methods:**
- `generate_symbol(pool: Pool) -> str`: Generate case-preserving symbol
- `lookup_pool(symbol: str) -> Optional[Pool]`: Case-insensitive pool lookup
- `normalize_symbol(symbol: str) -> str`: Create normalized lookup key
- `get_symbol_variants(symbol: str) -> List[str]`: Get all case variants

**Implementation Strategy:**
```python
class SymbolMapper:
    def __init__(self):
        self._symbol_to_pool_cache = {}  # Case-sensitive cache
        self._normalized_to_symbol_cache = {}  # Lowercase -> original mapping
    
    def generate_symbol(self, pool: Pool) -> str:
        # Keep existing logic - preserve original case
        symbol = pool.id
        # ... existing normalization logic
        return symbol
    
    def lookup_pool(self, symbol: str) -> Optional[Pool]:
        # Try exact match first
        if symbol in self._symbol_to_pool_cache:
            return self._symbol_to_pool_cache[symbol]
        
        # Try case-insensitive match
        normalized = symbol.lower()
        if normalized in self._normalized_to_symbol_cache:
            original_symbol = self._normalized_to_symbol_cache[normalized]
            return self._symbol_to_pool_cache.get(original_symbol)
        
        # Fallback to database lookup
        return self._database_lookup(symbol)
```

### 2. Enhanced QLib Exporter

**Modifications to existing `QLibExporter` class:**

1. **Replace direct symbol handling with SymbolMapper**
2. **Add case-insensitive lookup methods**
3. **Maintain backward compatibility**

**New/Modified Methods:**
- `_get_pool_for_symbol_flexible(symbol: str) -> Optional[Pool]`: Enhanced lookup
- `get_symbol_list_with_metadata() -> Dict[str, Dict]`: Include case info
- `validate_symbol_compatibility(symbols: List[str]) -> Dict[str, bool]`: Check compatibility

### 3. Symbol Cache Management

**Purpose:** Efficient caching of symbol mappings to avoid repeated database queries.

**Cache Structure:**
```python
{
    # Case-sensitive symbol -> Pool mapping
    "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP": Pool(...),
    
    # Normalized (lowercase) -> original symbol mapping
    "normalized_cache": {
        "solana_7bqjg2zdmkbekgsmfuqnvbvqevwavgl8ueo33zqdl3np": "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP"
    }
}
```

## Data Models

### Symbol Metadata Model

```python
@dataclass
class SymbolMetadata:
    original_symbol: str
    normalized_symbol: str
    pool_id: str
    case_sensitive: bool = True
    created_at: datetime
    last_accessed: datetime
```

### Enhanced Pool Lookup Result

```python
@dataclass
class PoolLookupResult:
    pool: Optional[Pool]
    matched_symbol: str
    lookup_method: str  # "exact", "case_insensitive", "database"
    confidence: float
```

## Error Handling

### Case-Sensitivity Error Types

1. **SymbolNotFoundError**: Symbol doesn't exist in any case variant
2. **AmbiguousSymbolError**: Multiple pools match case-insensitive lookup
3. **CaseMismatchWarning**: Symbol found but with different case

### Error Recovery Strategies

1. **Graceful Degradation**: Fall back to database search if cache misses
2. **Fuzzy Matching**: Use Levenshtein distance for near-matches
3. **User Feedback**: Provide suggestions for similar symbols

## Testing Strategy

### Unit Tests

1. **Symbol Generation Tests**
   - Verify case preservation
   - Test special character handling
   - Validate uniqueness

2. **Lookup Tests**
   - Exact case matching
   - Case-insensitive matching
   - Cache hit/miss scenarios
   - Database fallback

3. **Cache Management Tests**
   - Cache population
   - Cache invalidation
   - Memory usage limits

### Integration Tests

1. **End-to-End Workflow Tests**
   - Watchlist → Symbol generation → Lookup → Export
   - Mixed case symbol lists
   - External system integration

2. **Performance Tests**
   - Large symbol list processing
   - Cache efficiency
   - Database query optimization

### Compatibility Tests

1. **Backward Compatibility**
   - Existing QLib export workflows
   - Legacy symbol formats
   - API contract preservation

2. **External System Integration**
   - QLib framework compatibility
   - Pandas DataFrame processing
   - CSV export/import

## Implementation Phases

### Phase 1: Core Symbol Mapper
- Implement SymbolMapper class
- Add case-insensitive lookup logic
- Create comprehensive unit tests

### Phase 2: QLib Exporter Integration
- Modify QLibExporter to use SymbolMapper
- Add enhanced lookup methods
- Maintain backward compatibility

### Phase 3: Cache Optimization
- Implement efficient caching strategies
- Add cache management utilities
- Performance optimization

### Phase 4: Error Handling & Validation
- Add comprehensive error handling
- Implement validation methods
- Create diagnostic utilities

## Performance Considerations

### Memory Usage
- Limit cache size to prevent memory bloat
- Use LRU eviction for symbol cache
- Lazy loading of pool objects

### Query Optimization
- Index database queries by normalized symbols
- Batch symbol lookups where possible
- Cache frequently accessed symbols

### Scalability
- Support for large symbol lists (10k+ symbols)
- Efficient bulk operations
- Minimal database round trips

## Security Considerations

### Input Validation
- Sanitize symbol inputs to prevent injection
- Validate symbol format constraints
- Rate limiting for lookup operations

### Data Integrity
- Verify symbol-to-pool mappings
- Detect and handle corrupted cache data
- Audit trail for symbol modifications