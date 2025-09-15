# New Pools History Collection Implementation Plan

## Overview
Enhance the existing New Pools History Collection system to create a comprehensive pool discovery and monitoring workflow that automatically integrates with the watchlist system.

## Current State Analysis

### ✅ Existing Components
- `NewPoolsCollector` - Functional collector for new pools
- `NewPoolsHistory` model - Comprehensive historical data structure
- `store_new_pools_history()` - Database storage method
- Basic API integration with `get_new_pools_by_network()`

### ❌ Issues to Address
1. **Watchlist Integration Gap** - New pools not automatically added to watchlist
2. **Collection Strategy** - No clear trigger mechanism for regular collection
3. **Data Flow Logic** - History records not properly integrated with discovery workflow
4. **Validation Refinement** - Some validation logic needs improvement

## 🎯 Implementation Strategy

### Phase 1: Enhanced Collection Logic (Immediate)

#### 1.1 Smart Watchlist Integration
```python
class EnhancedNewPoolsCollector(NewPoolsCollector):
    """Enhanced collector with automatic watchlist integration."""
    
    async def collect(self) -> CollectionResult:
        # Existing collection logic...
        
        # NEW: Auto-add promising pools to watchlist
        for pool_data in pools_data:
            if self._should_add_to_watchlist(pool_data):
                await self._add_to_watchlist(pool_data)
    
    def _should_add_to_watchlist(self, pool_data: Dict) -> bool:
        """Determine if pool should be auto-added to watchlist."""
        attributes = pool_data.get('attributes', {})
        
        # Criteria for auto-watchlist addition:
        # 1. Minimum liquidity threshold
        # 2. Recent creation (within last 24h)
        # 3. Minimum trading activity
        # 4. Not already in watchlist
        
        reserve_usd = float(attributes.get('reserve_in_usd', 0))
        volume_24h = float(attributes.get('volume_usd_h24', 0))
        
        return (
            reserve_usd >= 1000 and  # Min $1K liquidity
            volume_24h >= 100 and   # Min $100 daily volume
            self._is_recently_created(attributes)
        )
```

#### 1.2 Collection Scheduling Enhancement
```python
# Enhanced CLI command for scheduled collection
gecko-cli run-collector new-pools --network solana --auto-watchlist --schedule hourly
```

#### 1.3 Activity Scoring Integration
```python
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer

class SmartPoolDiscovery:
    """Smart pool discovery with activity scoring."""
    
    async def evaluate_pool(self, pool_data: Dict) -> Dict:
        """Evaluate pool with activity scoring."""
        scorer = ActivityScorer()
        
        # Calculate activity score
        activity_score = scorer.calculate_pool_activity_score(pool_data)
        
        # Determine actions based on score
        actions = {
            'add_to_watchlist': activity_score >= 70,
            'priority_monitoring': activity_score >= 85,
            'alert_threshold': activity_score >= 95
        }
        
        return {
            'pool_id': pool_data.get('id'),
            'activity_score': activity_score,
            'recommended_actions': actions,
            'evaluation_timestamp': datetime.now()
        }
```

### Phase 2: Advanced Analytics & Monitoring (Next Sprint)

#### 2.1 Pool Performance Tracking
```python
class PoolPerformanceTracker:
    """Track pool performance over time."""
    
    async def analyze_pool_trends(self, pool_id: str, days: int = 7) -> Dict:
        """Analyze pool performance trends."""
        
        # Get historical data from new_pools_history
        history = await self.db_manager.get_pool_history(pool_id, days)
        
        # Calculate metrics
        metrics = {
            'liquidity_trend': self._calculate_liquidity_trend(history),
            'volume_trend': self._calculate_volume_trend(history),
            'price_volatility': self._calculate_price_volatility(history),
            'trading_activity': self._calculate_trading_activity(history)
        }
        
        return metrics
```

#### 2.2 Automated Alerts System
```python
class PoolAlertSystem:
    """Automated alert system for pool events."""
    
    async def check_alert_conditions(self, pool_data: Dict) -> List[Dict]:
        """Check for alert-worthy conditions."""
        
        alerts = []
        attributes = pool_data.get('attributes', {})
        
        # Volume spike detection
        if self._detect_volume_spike(attributes):
            alerts.append({
                'type': 'volume_spike',
                'severity': 'high',
                'message': f"Volume spike detected: {attributes.get('volume_usd_h24')}"
            })
        
        # Liquidity drain detection
        if self._detect_liquidity_drain(attributes):
            alerts.append({
                'type': 'liquidity_drain',
                'severity': 'critical',
                'message': "Significant liquidity reduction detected"
            })
        
        return alerts
```

### Phase 3: Integration & Optimization (Future)

#### 3.1 Cross-Platform Integration
- DexScreener API integration for additional data validation
- Multiple DEX monitoring across networks
- Real-time WebSocket feeds for instant updates

#### 3.2 Machine Learning Enhancement
- Predictive modeling for pool success probability
- Anomaly detection for unusual trading patterns
- Automated parameter tuning for watchlist criteria

## 🔧 Implementation Steps

### Step 1: Enhance Current Collector (This Sprint)
1. **Add Smart Watchlist Integration**
   - Implement `_should_add_to_watchlist()` logic
   - Add automatic watchlist entry creation
   - Include activity scoring criteria

2. **Improve Collection Scheduling**
   - Add CLI parameters for auto-watchlist mode
   - Implement configurable collection intervals
   - Add dry-run mode for testing criteria

3. **Enhanced Validation & Error Handling**
   - Improve data validation logic
   - Add comprehensive error recovery
   - Implement retry mechanisms for failed operations

### Step 2: Create Management Interface (This Sprint)
1. **New CLI Commands**
   ```bash
   # Enhanced collection with auto-watchlist
   gecko-cli collect-new-pools --network solana --auto-watchlist --min-liquidity 1000
   
   # Pool discovery analysis
   gecko-cli analyze-pool-discovery --days 7 --format json
   
   # Watchlist management from discovery
   gecko-cli manage-discovery-watchlist --action review --criteria volume_spike
   ```

2. **Monitoring Dashboard Data**
   - Pool discovery statistics
   - Watchlist addition rates
   - Activity score distributions
   - Collection success metrics

### Step 3: Testing & Validation (This Sprint)
1. **Comprehensive Test Suite**
   - Unit tests for new logic
   - Integration tests with watchlist system
   - Performance tests for large datasets

2. **Real-World Validation**
   - Test with live Solana data
   - Validate watchlist integration
   - Monitor collection performance

## 📊 Success Metrics

### Immediate Goals (This Sprint)
- ✅ Automatic watchlist integration working
- ✅ Enhanced collection scheduling implemented
- ✅ Improved validation and error handling
- ✅ New CLI commands functional

### Performance Targets
- **Collection Efficiency**: Process 100+ pools per minute
- **Watchlist Accuracy**: 80%+ of auto-added pools show activity
- **System Reliability**: 99%+ successful collection runs
- **Data Quality**: <1% validation errors

### Long-term Objectives
- **Predictive Accuracy**: 70%+ success rate for pool performance prediction
- **Alert Precision**: <5% false positive rate for alerts
- **Integration Coverage**: Support for 5+ networks and 10+ DEXes

## 🚀 Quick Start Implementation

### Immediate Actions (Today)
1. **Enhance NewPoolsCollector** with watchlist integration
2. **Add CLI parameters** for auto-watchlist mode
3. **Implement activity scoring** criteria
4. **Create test scenarios** for validation

### This Week
1. **Deploy enhanced collector** in development
2. **Test with live data** and validate results
3. **Create monitoring dashboard** queries
4. **Document new workflows** and usage patterns

This implementation plan transforms the basic new pools collection into a comprehensive pool discovery and monitoring system that automatically integrates with your existing watchlist infrastructure.