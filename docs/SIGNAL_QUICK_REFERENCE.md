# Signal Analysis Quick Reference Card

## Signal Score Ranges

| Score | Quality | Action | Typical Characteristics |
|-------|---------|--------|------------------------|
| **90-100** | 🔥 Exceptional | Strong Buy Signal | Volume spike + Liquidity growth + Strong momentum + High activity |
| **75-89** | ⭐ Strong | Buy Consideration | Multiple positive indicators, good momentum |
| **60-74** | ✓ Moderate | Monitor Closely | Some positive signals, worth watching |
| **40-59** | ~ Weak | Watch | Limited signals, wait for development |
| **0-39** | ✗ None | Pass | No significant signals detected |

---

## Component Weights

```
Volume:     ████████████████████████████████ 30%
Liquidity:  ████████████████████ 20%
Momentum:   ████████████████████ 20%
Activity:   ████████████████████ 20%
Volatility: ██████████ 10%
```

---

## Trend Classifications

### Volume Trend
- `spike` - Growth >100% (spike detected)
- `increasing` - Growth >10%
- `stable` - Growth -30% to 10%
- `decreasing` - Growth <-30%
- `unknown` - Insufficient data

### Liquidity Trend
- `growing` - Growth >30%
- `stable` - Growth -20% to 30%
- `shrinking` - Growth <-20%
- `unknown` - Insufficient data

### Momentum Direction
- `bullish` - Momentum >5%
- `neutral` - Momentum -5% to 5%
- `bearish` - Momentum <-5%

### Volatility Level
- `extreme` - >20% volatility
- `high` - >10% volatility
- `moderate` - >5% volatility
- `low` - ≤5% volatility

---

## Signal Bonuses

| Condition | Bonus Points | Trigger |
|-----------|--------------|---------|
| Volume Spike | +10 | Volume growth ≥100% |
| Liquidity Growth | +8 | Liquidity growth ≥50% |
| Strong Momentum | +5 | Momentum >10% |
| High Activity | +5 | >50 tx/1h OR >500 tx/24h |

---

## Default Thresholds

```yaml
min_signal_score: 60.0              # Minimum for alerts
volume_spike_threshold: 2.0         # 2x = 100% increase
liquidity_growth_threshold: 1.5     # 1.5x = 50% increase
momentum_lookback_hours: 6          # Hours for momentum calc
auto_watchlist_threshold: 75.0      # Auto-add to watchlist
```

---

## Alert Message Format

```
Strong signal detected: Pool {pool_id} - Signal Score: {score} - {reasons}
```

**Example:**
```
Strong signal detected: Pool solana_ABC123 - Signal Score: 85.3 - 
Volume spike detected (150% increase), Liquidity growth (67% increase), 
Strong bullish momentum
```

---

## Quick Interpretation Guide

### 🔥 Exceptional Signal (90-100)
**What it means:** Multiple strong indicators firing simultaneously
**Typical pattern:** Volume spike + Liquidity growth + Bullish momentum + High activity
**Action:** Strong buy consideration, verify fundamentals
**Risk:** High volatility likely

### ⭐ Strong Signal (75-89)
**What it means:** Several positive indicators, good momentum
**Typical pattern:** Volume increasing + Growing liquidity + Positive momentum
**Action:** Buy consideration, monitor entry point
**Risk:** Moderate volatility

### ✓ Moderate Signal (60-74)
**What it means:** Some positive signals, worth monitoring
**Typical pattern:** Volume or liquidity growth + Some momentum
**Action:** Add to watchlist, wait for confirmation
**Risk:** May not develop further

### ~ Weak Signal (40-59)
**What it means:** Limited positive indicators
**Typical pattern:** Stable metrics, low activity
**Action:** Watch for development, no immediate action
**Risk:** Low probability of significant move

### ✗ No Signal (0-39)
**What it means:** No significant trading opportunity detected
**Typical pattern:** Low volume, stable/decreasing liquidity
**Action:** Pass, focus on higher-scoring pools
**Risk:** N/A

---

## Configuration Presets

### Aggressive (More Signals)
```yaml
min_signal_score: 50.0
volume_spike_threshold: 1.5         # 50% increase
liquidity_growth_threshold: 1.3     # 30% increase
```

### Balanced (Default)
```yaml
min_signal_score: 60.0
volume_spike_threshold: 2.0         # 100% increase
liquidity_growth_threshold: 1.5     # 50% increase
```

### Conservative (Fewer, Higher Quality)
```yaml
min_signal_score: 75.0
volume_spike_threshold: 3.0         # 200% increase
liquidity_growth_threshold: 2.0     # 100% increase
```

---

## Common Patterns

### 🚀 Breakout Pattern (Score: 85-100)
- Volume spike: ✓
- Liquidity growing: ✓
- Strong bullish momentum: ✓
- High activity: ✓
- **Action:** Strong buy signal

### 📈 Growth Pattern (Score: 70-85)
- Volume increasing: ✓
- Liquidity growing: ✓
- Moderate momentum: ✓
- **Action:** Buy consideration

### 👀 Watch Pattern (Score: 60-70)
- Volume stable/increasing: ~
- Liquidity stable: ~
- Some momentum: ~
- **Action:** Monitor closely

### ⚠️ Risky Pattern (Score: 75+, High Volatility)
- Strong signals: ✓
- Extreme volatility: ⚠️
- **Action:** Proceed with caution, smaller position

---

## Database Query Examples

### Top Signals Today
```sql
SELECT pool_id, signal_score, volume_trend, liquidity_trend
FROM new_pools_history
WHERE DATE(collected_at) = CURRENT_DATE
  AND signal_score >= 75
ORDER BY signal_score DESC
LIMIT 10;
```

### Volume Spikes
```sql
SELECT pool_id, signal_score, volume_trend, volume_usd_h24
FROM new_pools_history
WHERE volume_trend = 'spike'
  AND collected_at >= datetime('now', '-1 hour')
ORDER BY signal_score DESC;
```

### Growing Liquidity
```sql
SELECT pool_id, signal_score, liquidity_trend, reserve_in_usd
FROM new_pools_history
WHERE liquidity_trend = 'growing'
  AND signal_score >= 70
ORDER BY collected_at DESC
LIMIT 20;
```

---

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| No signals appearing | `enabled: false` or threshold too high | Check config, lower `min_signal_score` |
| Too many signals | Threshold too low | Increase `min_signal_score` to 70-75 |
| Signals not accurate | Insufficient historical data | Wait 24h for data collection |
| Missing trend data | Database not migrated | Run migration script |

---

## Key Metrics to Watch

1. **Signal Score** - Overall strength (aim for 75+)
2. **Volume Trend** - Look for 'spike' or 'increasing'
3. **Liquidity Trend** - Prefer 'growing'
4. **Momentum Direction** - 'bullish' is best
5. **Activity Score** - Higher = more interest

---

## Risk Management

- ✅ **DO:** Use signals as one input in decision-making
- ✅ **DO:** Verify fundamentals before trading
- ✅ **DO:** Use position sizing and stop losses
- ✅ **DO:** Track signal accuracy over time
- ❌ **DON'T:** Trade on signals alone
- ❌ **DON'T:** Ignore high volatility warnings
- ❌ **DON'T:** Chase every signal
- ❌ **DON'T:** Use full position on single signal

---

## Further Reading

- [Complete Signal Analysis Guide](SIGNAL_ANALYSIS_GUIDE.md) - Detailed calculations and formulas
- [Signal Updates Summary](SIGNAL_UPDATES_SUMMARY.md) - Recent changes and migration info
- [Interval Configuration](INTERVAL_CONFIGURATION.md) - Optimize collection frequency
