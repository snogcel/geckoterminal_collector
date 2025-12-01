# Config Parsing Fix Summary

## Problem

The `ConfigManager` was not parsing the `auto_watchlist_integration` and `signal_detection` configuration from `config.yaml`. The diagnostic showed:
- `auto_watchlist = False` (should be True)
- `signal_detection config not found`

## Root Cause

The Pydantic validators in `gecko_terminal_collector/config/validation.py` were missing fields that existed in the data models in `gecko_terminal_collector/config/models.py`:

1. **NetworkConfigValidator** was missing:
   - `signal_analysis`
   - `auto_watchlist_integration`

2. **SignalDetectionConfigValidator** didn't exist at all

3. **NewPoolsConfigValidator** wasn't including `signal_detection`

## Files Modified

### 1. `gecko_terminal_collector/config/models.py`

Added `SignalDetectionConfig` dataclass:
```python
@dataclass
class SignalDetectionConfig:
    """Signal detection configuration for new pools."""
    enabled: bool = True
    min_signal_score: float = 60.0
    volume_spike_threshold: float = 2.0
    liquidity_growth_threshold: float = 1.5
    momentum_lookback_hours: int = 6
    auto_watchlist_threshold: float = 75.0
    use_colors: bool = True
    use_emojis: bool = True
    enable_file_alerts: bool = True
    enable_sound_alerts: bool = False
    enable_desktop_notifications: bool = False
    enable_webhook: bool = False
    webhook_url: Optional[str] = None
    alerts_dir: str = "alerts"
```

Updated `NewPoolsConfig` to include `signal_detection`:
```python
@dataclass
class NewPoolsConfig:
    """New pools collection configuration."""
    networks: Dict[str, NetworkConfig] = field(default_factory=...)
    signal_detection: SignalDetectionConfig = field(default_factory=SignalDetectionConfig)
```

### 2. `gecko_terminal_collector/config/validation.py`

**Added imports**:
```python
from typing import List, Any, Dict, Optional  # Added Optional
```

**Added SignalDetectionConfigValidator**:
```python
class SignalDetectionConfigValidator(BaseModel):
    """Pydantic model for signal detection configuration validation."""
    enabled: bool = Field(default=True, ...)
    min_signal_score: float = Field(default=60.0, ge=0.0, le=100.0, ...)
    # ... all signal detection fields
```

**Updated NetworkConfigValidator**:
```python
class NetworkConfigValidator(BaseModel):
    enabled: bool = Field(default=True, ...)
    interval: str = Field(default="30m", ...)
    rate_limit_key: str = Field(default=None, ...)
    signal_analysis: bool = Field(default=True, ...)  # ADDED
    auto_watchlist_integration: bool = Field(default=False, ...)  # ADDED
```

**Updated NewPoolsConfigValidator**:
```python
class NewPoolsConfigValidator(BaseModel):
    networks: Dict[str, NetworkConfigValidator] = Field(...)
    signal_detection: SignalDetectionConfigValidator = Field(...)  # ADDED
```

**Updated to_legacy_config() method**:
- Converts `signal_detection` configuration
- Passes `signal_analysis` and `auto_watchlist_integration` to NetworkConfig

## Verification

Test command:
```bash
python -c "from gecko_terminal_collector.config.manager import ConfigManager; cm = ConfigManager('config.yaml'); config = cm.load_config(); print(f'Auto-watchlist: {config.new_pools.networks[\"solana\"].auto_watchlist_integration}'); print(f'Signal detection enabled: {config.new_pools.signal_detection.enabled}'); print(f'Auto-watchlist threshold: {config.new_pools.signal_detection.auto_watchlist_threshold}')"
```

Output:
```
Auto-watchlist: True
Signal detection enabled: True
Auto-watchlist threshold: 75.0
```

✅ Config is now being parsed correctly!

## Diagnostic Results

Running `python diagnose_auto_watchlist.py` now shows:

```
1. CONFIGURATION CHECK
   Signal detection enabled: True
   Auto-watchlist threshold: 75.0
   Min signal score: 60.0

   Configured networks: ['solana']
   - solana: auto_watchlist = True  ✅
```

## Remaining Issue

The diagnostic revealed the actual problem preventing auto-watchlist from working:

**20 pools in history but NOT in pools table**

This is a separate issue from config parsing. Pools with high signal scores exist in `new_pools_history` but some don't exist in the `pools` table, preventing them from being added to the watchlist due to the foreign key constraint.

However, recent pools (last 24 hours) ARE in the pools table, which means `_ensure_pool_exists()` is working correctly now. The auto-watchlist should start working for new pools going forward.

## Next Steps

1. ✅ Config parsing fixed
2. ✅ Constraint handling improved in `add_to_watchlist()`
3. ✅ Duplicate detection added to `store_new_pools_history()`
4. ⏭️ Monitor logs for auto-watchlist activity on next collection run

The system should now properly add high-signal pools to the watchlist!
