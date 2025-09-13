# Design Document

## Overview

This design transforms the GeckoTerminal collector from a watchlist-driven system to an intelligent auto-discovery system that follows the natural data dependency flow: DEXes → Pools → Tokens → OHLCV/Trades. The new architecture eliminates manual watchlist maintenance while providing better scalability and discovery capabilities.

## Architecture

### Current Architecture Problems

```
Manual Watchlist CSV → Watchlist Collector → Pool/Token Collection → OHLCV/Trades
     ↑ Manual Step        ↑ Dependency Inversion    ↑ Constrained Discovery
```

**Issues:**
- Requires manual pool address discovery and CSV maintenance
- Inverts natural data flow (pools must exist before pool discovery)
- Cannot discover new pools automatically
- Creates maintenance overhead

### New Architecture Solution

```
DEX Discovery → Pool Discovery → Token Extraction → OHLCV/Trades Collection
     ↓              ↓               ↓                    ↓
  DEX Table → Pool Table → Token Table → OHLCV/Trade Tables
```

**Benefits:**
- Follows natural foreign key dependencies
- Automatic pool discovery and population
- Scalable and maintainable
- Optional watchlist overlay for manual curation

## Components and Interfaces

### 1. Discovery Engine

**Purpose:** Orchestrates the discovery process following dependency order

```python
class DiscoveryEngine:
    """Orchestrates automatic discovery of DEXes, pools, and tokens."""
    
    async def bootstrap_system(self) -> DiscoveryResult:
        """Bootstrap empty system with initial data."""
        
    async def discover_dexes(self) -> List[DEX]:
        """Discover and populate DEX information."""
        
    async def discover_pools(self, dex_ids: List[str]) -> List[Pool]:
        """Discover pools from specified DEXes."""
        
    async def extract_tokens(self, pools: List[Pool]) -> List[Token]:
        """Extract token information from pool data."""
        
    async def apply_filters(self, pools: List[Pool]) -> List[Pool]:
        """Apply volume and activity filters to pools."""
```

### 2. Enhanced Pool Discovery Collector

**Purpose:** Replaces watchlist collector with intelligent pool discovery

```python
class PoolDiscoveryCollector(BaseDataCollector):
    """Discovers and manages pools automatically from DEXes."""
    
    def __init__(self, config: CollectionConfig, db_manager: DatabaseManager):
        self.volume_threshold = config.discovery.min_volume_usd
        self.max_pools_per_dex = config.discovery.max_pools_per_dex
        self.discovery_interval = config.discovery.interval
        
    async def collect(self) -> CollectionResult:
        """Discover new pools and update existing ones."""
        
    async def discover_top_pools(self, dex_id: str, limit: int) -> List[Pool]:
        """Discover top pools by volume for a DEX."""
        
    async def discover_new_pools(self, dex_id: str, since: datetime) -> List[Pool]:
        """Discover newly created pools since timestamp."""
        
    async def evaluate_pool_activity(self, pool_id: str) -> ActivityScore:
        """Evaluate pool activity for collection priority."""
```

### 3. Configuration Extensions

**Purpose:** Add discovery configuration options

```python
@dataclass
class DiscoveryConfig:
    """Pool discovery configuration."""
    enabled: bool = True
    min_volume_usd: Decimal = Decimal("1000")  # Minimum 24h volume
    max_pools_per_dex: int = 100  # Limit pools per DEX
    discovery_interval: str = "6h"  # How often to discover new pools
    activity_threshold: Decimal = Decimal("100")  # Minimum activity score
    new_pool_lookback_hours: int = 24  # Look for pools created in last N hours
    
@dataclass
class CollectionConfig:
    # ... existing fields ...
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    watchlist: Optional[WatchlistConfig] = None  # Make watchlist optional
```

### 4. Pool Activity Scoring

**Purpose:** Intelligent filtering based on pool activity

```python
class ActivityScorer:
    """Scores pools based on activity metrics for prioritization."""
    
    def calculate_activity_score(self, pool_data: Dict) -> Decimal:
        """Calculate composite activity score."""
        # Factors: volume, transaction count, price volatility, liquidity
        
    def should_include_pool(self, pool: Pool, score: Decimal) -> bool:
        """Determine if pool meets inclusion criteria."""
        
    def get_collection_priority(self, score: Decimal) -> CollectionPriority:
        """Map activity score to collection priority."""
```

### 5. Bootstrap Process

**Purpose:** Initialize system from empty state

```python
class SystemBootstrap:
    """Handles initial system population from empty database."""
    
    async def bootstrap(self) -> BootstrapResult:
        """Complete system bootstrap process."""
        
        # 1. Discover and populate DEXes
        dexes = await self.discovery_engine.discover_dexes()
        await self.db_manager.store_dex_data(dexes)
        
        # 2. Discover and populate pools
        all_pools = []
        for dex in dexes:
            pools = await self.discovery_engine.discover_pools([dex.id])
            filtered_pools = await self.discovery_engine.apply_filters(pools)
            all_pools.extend(filtered_pools)
        
        await self.db_manager.store_pools(all_pools)
        
        # 3. Extract and populate tokens
        tokens = await self.discovery_engine.extract_tokens(all_pools)
        await self.db_manager.store_tokens(tokens)
        
        # 4. Initialize collection schedules
        await self.scheduler.initialize_collection_schedules(all_pools)
        
        return BootstrapResult(
            dexes_discovered=len(dexes),
            pools_discovered=len(all_pools),
            tokens_discovered=len(tokens)
        )
```

## Data Models

### Enhanced Pool Model

```python
@dataclass
class Pool:
    # ... existing fields ...
    activity_score: Optional[Decimal] = None
    discovery_source: str = "auto"  # "auto", "watchlist", "manual"
    collection_priority: str = "normal"  # "high", "normal", "low", "paused"
    last_activity_check: Optional[datetime] = None
    auto_discovered_at: Optional[datetime] = None
```

### Discovery Metadata

```python
class DiscoveryMetadata(Base):
    """Track discovery operations and statistics."""
    
    __tablename__ = "discovery_metadata"
    
    id = Column(Integer, primary_key=True)
    discovery_type = Column(String(50), nullable=False)  # "dex", "pool", "token"
    target_dex = Column(String(50))
    pools_discovered = Column(Integer, default=0)
    pools_filtered = Column(Integer, default=0)
    discovery_time = Column(DateTime, nullable=False)
    execution_time_seconds = Column(Numeric(10, 3))
    api_calls_made = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.current_timestamp())
```

## Error Handling

### Discovery Failures

1. **DEX Discovery Failure**: Fall back to configured DEX list, log warning
2. **Pool Discovery Failure**: Continue with existing pools, retry on next cycle
3. **Token Extraction Failure**: Skip problematic pools, continue with others
4. **API Rate Limiting**: Implement exponential backoff and resume discovery

### Data Consistency

1. **Foreign Key Violations**: Ensure DEXes exist before pools, pools before tokens
2. **Duplicate Detection**: Use upsert logic with proper unique constraints
3. **Orphaned Records**: Implement cleanup jobs for orphaned tokens/pools

## Testing Strategy

### Unit Tests

1. **DiscoveryEngine**: Test each discovery method independently
2. **ActivityScorer**: Test scoring algorithm with various pool scenarios
3. **PoolDiscoveryCollector**: Test collection logic and filtering
4. **SystemBootstrap**: Test bootstrap process with mock data

### Integration Tests

1. **End-to-End Discovery**: Test complete discovery flow from empty database
2. **Watchlist Compatibility**: Test system with and without watchlist files
3. **Performance Testing**: Test discovery with large numbers of pools
4. **Failure Recovery**: Test system behavior with various failure scenarios

### Migration Testing

1. **Existing System Migration**: Test migration from watchlist-based to discovery-based
2. **Data Preservation**: Ensure existing pool/token data is preserved
3. **Configuration Migration**: Test configuration updates and backward compatibility

## Migration Strategy

### Phase 1: Parallel Implementation

1. Implement discovery system alongside existing watchlist system
2. Add configuration flag to enable/disable discovery
3. Test discovery system without affecting existing functionality

### Phase 2: Gradual Transition

1. Enable discovery by default for new installations
2. Provide migration tool to convert watchlist to discovery configuration
3. Maintain watchlist support for existing users

### Phase 3: Deprecation

1. Mark watchlist-only mode as deprecated
2. Encourage users to migrate to discovery mode
3. Eventually remove watchlist-only support (with sufficient notice)

## Performance Considerations

### API Efficiency

1. **Batch Operations**: Use multi-pool APIs where available
2. **Rate Limiting**: Respect API limits with intelligent backoff
3. **Caching**: Cache discovery results to reduce API calls
4. **Pagination**: Handle large result sets efficiently

### Database Performance

1. **Bulk Inserts**: Use bulk operations for large pool/token sets
2. **Indexing**: Ensure proper indexes on discovery-related queries
3. **Cleanup**: Regular cleanup of inactive pools and old discovery metadata

### Memory Management

1. **Streaming**: Process large discovery results in batches
2. **Connection Pooling**: Efficient database connection management
3. **Resource Cleanup**: Proper cleanup of discovery resources

## Monitoring and Observability

### Discovery Metrics

1. **Pools Discovered**: Track new pools found per discovery cycle
2. **Discovery Success Rate**: Monitor API success rates and failures
3. **Activity Score Distribution**: Monitor pool activity score patterns
4. **Collection Coverage**: Track percentage of active pools being monitored

### Alerting

1. **Discovery Failures**: Alert on repeated discovery failures
2. **Low Pool Count**: Alert if discovered pool count drops significantly
3. **API Issues**: Alert on API rate limiting or connectivity issues
4. **Performance Degradation**: Alert on slow discovery operations

This design provides a robust, scalable solution that eliminates the manual watchlist dependency while maintaining flexibility for users who want manual curation capabilities.