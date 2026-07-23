"""
Smart Money Signal Backtest
============================
Uses watchlist snapshot CSVs (gmgn_watchlist_v4.py output) to build
per-token price timelines and simulate trading strategies based on:
  1. Score threshold entry (buy when score crosses above N)
  2. Smart money cluster entry (buy when smart_degen_count jumps)
  3. Anti-dump filter (skip tokens with fast_dump flag)
  4. Combined strategy (score + smart_money + no fast_dump)

Output: performance stats per strategy, trade log, win rate, P&L.

Usage:
  python backtest_smart_money.py [--data-dir paper-trading] [--min-observations 3]
"""

import pandas as pd
import numpy as np
import glob
import os
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict

# --- Config ------------------------------------------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))  # Same dir as script
SNAPSHOT_PATTERN = "watchlist_gmgn_*.csv"
REJECTED_PATTERN = "watchlist_rejected_*.csv"

# Strategy parameters
ENTRY_SCORE = 50           # Minimum score to enter
ENTRY_SMART_MONEY = 3      # Minimum smart_degen_count to enter
EXIT_SCORE_DROP = 20       # Exit if score drops by this much from peak
STOP_LOSS_PCT = -30        # Stop loss at -30%
TAKE_PROFIT_PCT = 50       # Take profit at +50%
MAX_HOLD_MINUTES = 60      # Max hold time in minutes
POSITION_SIZE_USD = 100    # Fixed position size per trade
BANKROLL = 1000            # Starting bankroll for drawdown calc
MAX_CONCURRENT_POSITIONS = 5  # Max positions open at once
MIN_OBSERVATIONS = 2       # Min snapshots before evaluating a token
FAST_DUMP_THRESHOLD = 30   # % drop in 5m to flag as fast dump

# --- Slippage Model -----------------------------------------------
# Simulates realistic execution costs on low-liquidity Solana meme pools
ENTRY_SLIPPAGE_BPS = 50    # Base entry slippage: 0.50% (signal delay + spread)
EXIT_SLIPPAGE_BPS = 50     # Base exit slippage: 0.50% (signal delay + spread)
LIQUIDITY_IMPACT_MULT = 3  # Multiplier for liquidity impact (higher = more slippage on thin pools)
SPREAD_BPS = 30            # Bid-ask spread cost: 0.30%


def calc_slippage(liquidity_usd, position_usd=POSITION_SIZE_USD):
    """Calculate total slippage in basis points for a given pool liquidity.
    
    Components:
    1. Base slippage (fixed, covers signal delay + minimum spread)
    2. Liquidity impact (position_size / liquidity * multiplier)
    3. Spread (bid-ask, higher on thinner pools)
    
    Returns total slippage in basis points.
    """
    base = ENTRY_SLIPPAGE_BPS + SPREAD_BPS
    
    # Liquidity impact: your trade as % of pool, amplified by multiplier
    if liquidity_usd > 0:
        impact_bps = (position_usd / liquidity_usd) * 10000 * LIQUIDITY_IMPACT_MULT
    else:
        impact_bps = 500  # 5% impact if no liquidity data
    
    # Spread widens on thin pools (inverse liquidity curve)
    if liquidity_usd < 10000:
        spread_premium = 50  # Extra 0.5% spread on very thin pools
    elif liquidity_usd < 50000:
        spread_premium = 20  # Extra 0.2% on medium pools
    else:
        spread_premium = 0
    
    total_bps = base + impact_bps + spread_premium
    return round(total_bps, 1)


def apply_slippage(price, slippage_bps, is_buy=True):
    """Apply slippage to a price. Buys pay more, sells receive less."""
    multiplier = slippage_bps / 10000
    if is_buy:
        return price * (1 + multiplier)
    else:
        return price * (1 - multiplier)


def load_snapshots(data_dir):
    """Load all watchlist snapshot CSVs into a single DataFrame."""
    pattern = os.path.join(data_dir, SNAPSHOT_PATTERN)
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"No snapshot files found matching {pattern}")
        return pd.DataFrame()
    
    dfs = []
    for f in files:
        fname = os.path.basename(f)  # assign BEFORE the read, so failures can report it
        try:
            df = pd.read_csv(f, low_memory=False)
            if df.empty and len(df.columns) == 0:
                # Truly empty file (no header at all) - not the same as a
                # header-only "no candidates this cycle" file, which reads
                # fine as a 0-row DataFrame and needs no special handling.
                print(f"  Skip {fname}: file has no columns (likely 0 bytes / truncated write)")
                continue
            # Extract timestamp from filename for reliability
            parts = fname.replace('.csv', '').split('_')
            # parts: [watchlist, gmgn, YYYY, MM, DD, HHMM]
            ts_str = f"{parts[2]}-{parts[3]}-{parts[4]} {parts[5][:2]}:{parts[5][2:]}"
            df['_file_ts'] = pd.to_datetime(ts_str, format='%Y-%m-%d %H:%M', errors='coerce')
            # Use actual timestamp column if available
            if 'timestamp' in df.columns:
                df['_snap_ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
            else:
                df['_snap_ts'] = df['_file_ts']
            dfs.append(df)
        except Exception as e:
            print(f"  Skip {fname}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(files)} snapshots, {len(combined)} total rows")
    return combined


def build_token_timelines(df):
    """Build per-token price and indicator timelines from snapshots."""
    timelines = {}
    df['_address'] = df['detailUrl'].str.extract(r'/solana/(.+)')

    missing = df['_address'].isna().sum()
    if missing:
        print(f"  [WARN] {missing} row(s) have no resolvable address (missing/malformed "
              f"detailUrl) and will be silently dropped by groupby - check this isn't a "
              f"large fraction of your data.")

    for token, group in df.groupby('_address'):
        # Sort by snapshot time
        group = group.sort_values('_snap_ts').reset_index(drop=True)
        
        # Need at least MIN_OBSERVATIONS snapshots
        if len(group) < MIN_OBSERVATIONS:
            continue
        
        # Extract address from detailUrl if available
        address = ''
        if 'detailUrl' in group.columns:
            url = group['detailUrl'].iloc[0]
            if isinstance(url, str) and '/solana/' in url:
                address = url.split('/solana/')[-1]
        
        # Build timeline
        timeline = {
            'symbol': group['tokenSymbol'].iloc[0] if 'tokenSymbol' in group.columns else token,
            'name': group['tokenName'].iloc[0] if 'tokenName' in group.columns else token,
            'address': address,
            'snapshots': []
        }
        
        for _, row in group.iterrows():
            snap = {
                'ts': row['_snap_ts'],
                'dex': row.get('dex', ''),
                'price': float(row['price']) if pd.notna(row.get('price')) else None,
                'score': float(row['score']) if pd.notna(row.get('score')) else None,
                'smart_degen': int(row['smart_degen_count']) if pd.notna(row.get('smart_degen_count')) else 0,
                'rug_ratio': float(row['rug_ratio']) if pd.notna(row.get('rug_ratio')) else 0,
                'liquidity': float(row['liquidity']) if pd.notna(row.get('liquidity')) else 0,
                'volume': float(row['volume']) if pd.notna(row.get('volume')) else 0,
                'makers': int(row['makers']) if pd.notna(row.get('makers')) else 0,
                'price_change_5m': float(row['priceChange5m']) if pd.notna(row.get('priceChange5m')) else None,
                'price_change_1h': float(row['priceChange1h']) if pd.notna(row.get('priceChange1h')) else None,
                'is_active': row.get('is_active', True),
                'flags': str(row.get('flags', '')),
                'cycles_tracked': int(row['cycles_tracked']) if pd.notna(row.get('cycles_tracked')) else 1,
                'peak_score': float(row.get('peak_score', row.get('score', 0))) if pd.notna(row.get('peak_score', row.get('score'))) else 0,
                'endpoint': str(row.get('endpoint', 'unknown')),
            }
            timeline['snapshots'].append(snap)
        
        timelines[token] = timeline
    
    print(f"Built timelines for {len(timelines)} tokens (>= {MIN_OBSERVATIONS} observations)")
    return timelines


def simulate_strategy(timelines, strategy_fn, strategy_name):
    """Run a strategy across all token timelines with concurrent position tracking.
    
    Positions are tracked globally across all tokens, simulating a real portfolio
    where you can hold multiple tokens simultaneously up to MAX_CONCURRENT_POSITIONS.
    """
    # Collect all snapshots across all tokens, sorted by time
    all_snaps = []
    for symbol, timeline in timelines.items():
        for i, snap in enumerate(timeline['snapshots']):
            all_snaps.append((snap['ts'], symbol, timeline, i, snap))
    all_snaps.sort(key=lambda x: x[0])

    # A data_end exit near the very edge of the whole dataset almost always
    # means "this token is still being tracked, we just haven't collected a
    # newer cycle yet" (unresolved) rather than "this token genuinely stopped
    # trending and fell out of the watchlist" (resolved, in the past). Use a
    # tolerance window rather than exact equality, since different tokens'
    # last observations won't land on the exact same cron tick.
    global_last_ts = all_snaps[-1][0] if all_snaps else None
    UNRESOLVED_TOLERANCE_MINUTES = 15
    
    # Global state
    open_positions = []  # List of active positions across all tokens
    completed = []
    max_concurrent_seen = 0
    concurrent_samples = []  # (timestamp, count) for tracking exposure over time
    
    # Track per-token state to prevent re-entry on same token while holding
    held_tokens = set()
    position_cooldown = {}  # symbol -> exit_ts (when position closed)
    COOLDOWN_MINUTES = 24 * 60  # 24-hour cooldown before re-entry (matches Telegram notification cooldown)
    
    for ts, symbol, timeline, idx, snap in all_snaps:
        if snap['price'] is None:
            continue
        
        # Check exits for all open positions
        still_open = []
        for pos in open_positions:
            # Use the token's current snapshot if available, otherwise skip exit check
            if pos['symbol'] == symbol:
                current_price = snap['price']
                current_snap = snap
            else:
                # We don't have the latest price for this token in this iteration
                # Keep it open, will be checked when its token's snapshot comes up
                still_open.append(pos)
                continue
            
            # Apply exit slippage: you receive LESS than the signal price
            liquidity = snap.get('liquidity', 50000)
            exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
            actual_exit_price = apply_slippage(current_price, exit_slip_bps, is_buy=False)
            
            entry_price = pos['entry_price']
            pnl_pct = (actual_exit_price - entry_price) / entry_price * 100
            hold_minutes = (ts - pos['entry_ts']).total_seconds() / 60
            
            # Track peak score
            if current_snap['score'] is not None and current_snap['score'] > pos.get('peak_score', 0):
                pos['peak_score'] = current_snap['score']
            
            exit_reason = None
            
            # Stop loss
            if pnl_pct <= STOP_LOSS_PCT:
                exit_reason = 'stop_loss'
            # Take profit
            elif pnl_pct >= TAKE_PROFIT_PCT:
                exit_reason = 'take_profit'
            # Max hold time
            elif hold_minutes >= MAX_HOLD_MINUTES:
                exit_reason = 'timeout'
            # Score collapse
            elif current_snap['score'] is not None and pos.get('peak_score', 0) - current_snap['score'] >= EXIT_SCORE_DROP:
                exit_reason = 'score_collapse'
            # Token went inactive
            elif current_snap.get('is_active') is False:
                exit_reason = 'inactive'
            # This is the last observation we have for THIS token specifically
            # (not the last observation in the whole dataset) - close here so
            # the position frees its concurrency slot at the correct point in
            # wall-clock time, instead of squatting on a slot for the rest of
            # the backtest until the global post-loop force-close runs.
            elif idx == len(timeline['snapshots']) - 1:
                exit_reason = 'data_end'
            
            if exit_reason:
                is_unresolved = (
                    exit_reason == 'data_end' and global_last_ts is not None
                    and (global_last_ts - ts).total_seconds() / 60 <= UNRESOLVED_TOLERANCE_MINUTES
                )
                completed.append({
                    'symbol': pos['symbol'],
                    'name': pos['name'],
                    'address': pos['address'],
                    'entry_ts': pos['entry_ts'],
                    'exit_ts': ts,
                    'entry_price': pos['entry_price'],
                    'signal_price': pos.get('signal_price', pos['entry_price']),
                    'exit_price': actual_exit_price,
                    'signal_exit_price': current_price,
                    'pnl_pct': pnl_pct,
                    'hold_minutes': hold_minutes,
                    'exit_reason': exit_reason,
                    'unresolved': is_unresolved,
                    'entry_score': pos.get('entry_score', 0),
                    'entry_smart_degen': pos.get('entry_smart_degen', 0),
                    'peak_score': pos.get('peak_score', 0),
                    'strategy': strategy_name,
                    'concurrent_positions_at_entry': pos.get('concurrent_at_entry', 0),
                    'entry_slippage_bps': pos.get('entry_slippage_bps', 0),
                    'exit_slippage_bps': exit_slip_bps,
                    'liquidity_at_entry': pos.get('liquidity_at_entry', 0),
                    'liquidity_at_exit': liquidity,
                })
                held_tokens.discard(pos['symbol'])
                position_cooldown[pos['symbol']] = ts  # Record exit time for 24h cooldown
            else:
                still_open.append(pos)
        
        open_positions = still_open
        
        # Track concurrent position count
        concurrent_samples.append((ts, len(open_positions)))
        max_concurrent_seen = max(max_concurrent_seen, len(open_positions))
        
        # Check entry for this token (if we don't already hold it)
        # Require at least MIN_OBSERVATIONS snapshots before entry
        # 24-hour cooldown: can re-enter after position closed + 24h
        cooldown_ok = (symbol not in position_cooldown or
                       (ts - position_cooldown[symbol]).total_seconds() / 60 > COOLDOWN_MINUTES)
        if (symbol not in held_tokens and cooldown_ok
                and len(open_positions) < MAX_CONCURRENT_POSITIONS
                and idx + 1 >= MIN_OBSERVATIONS):
            token_snaps = timeline['snapshots']
            should_enter, reason = strategy_fn(snap, token_snaps[:idx+1], idx)
            if should_enter:
                # Apply entry slippage: you pay MORE than the signal price
                liquidity = snap.get('liquidity', 50000)
                entry_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
                actual_entry_price = apply_slippage(snap['price'], entry_slip_bps, is_buy=True)
                
                pos = {
                    'symbol': symbol,
                    'name': timeline['name'],
                    'address': timeline['address'],
                    'entry_idx': idx,
                    'entry_price': actual_entry_price,
                    'signal_price': snap['price'],
                    'entry_ts': snap['ts'],
                    'entry_score': snap['score'],
                    'entry_smart_degen': snap['smart_degen'],
                    'peak_score': snap['score'] or 0,
                    'reason': reason,
                    'concurrent_at_entry': len(open_positions),
                    'entry_slippage_bps': entry_slip_bps,
                    'liquidity_at_entry': liquidity,
                }
                open_positions.append(pos)
                held_tokens.add(symbol)
                
                # Track concurrent after entry
                concurrent_samples.append((ts, len(open_positions)))
                max_concurrent_seen = max(max_concurrent_seen, len(open_positions))
    
    # Safety net only: after the inline data_end fix, a position should only
    # reach here if it was entered on its own token's literal last-ever
    # observation (no further snapshot existed to trigger the inline check
    # above). This is normal, not a bug - it most often means the token is
    # among your most recently tracked ones, and its outcome genuinely isn't
    # known yet (no newer data has been collected). It is NOT typically a
    # null-price issue.
    if open_positions:
        print(f"  [WARN] {len(open_positions)} position(s) entered on their token's "
              f"final available observation - closing at last known price. Likely "
              f"still-open/unresolved positions (your most recently tracked tokens), "
              f"not a data problem.")
    for pos in open_positions:
        token_timeline = timelines.get(pos['symbol'])
        if not token_timeline or not token_timeline['snapshots']:
            print(f"  [WARN] {pos['symbol']}: no timeline found at force-close - position dropped uncounted.")
            continue
        last = token_timeline['snapshots'][-1]
        if last['price'] is None:
            print(f"  [WARN] {pos['symbol']}: final observation has a null price - "
                  f"position dropped uncounted (this is the genuine null-price edge case).")
            continue
        # Apply exit slippage
        liquidity = last.get('liquidity', 50000)
        exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
        actual_exit_price = apply_slippage(last['price'], exit_slip_bps, is_buy=False)
        pnl_pct = (actual_exit_price - pos['entry_price']) / pos['entry_price'] * 100
        hold_minutes = (last['ts'] - pos['entry_ts']).total_seconds() / 60
        is_unresolved = (
            global_last_ts is not None
            and (global_last_ts - last['ts']).total_seconds() / 60 <= UNRESOLVED_TOLERANCE_MINUTES
        )
        completed.append({
            'symbol': pos['symbol'],
            'name': pos['name'],
            'address': pos['address'],
            'entry_ts': pos['entry_ts'],
            'exit_ts': last['ts'],
            'entry_price': pos['entry_price'],
            'signal_price': pos.get('signal_price', pos['entry_price']),
            'exit_price': actual_exit_price,
            'signal_exit_price': last['price'],
            'pnl_pct': pnl_pct,
            'hold_minutes': hold_minutes,
            'exit_reason': 'data_end',
            'unresolved': is_unresolved,
            'entry_score': pos.get('entry_score', 0),
            'entry_smart_degen': pos.get('entry_smart_degen', 0),
            'peak_score': pos.get('peak_score', 0),
            'strategy': strategy_name,
            'concurrent_positions_at_entry': pos.get('concurrent_at_entry', 0),
            'entry_slippage_bps': pos.get('entry_slippage_bps', 0),
            'exit_slippage_bps': exit_slip_bps,
            'liquidity_at_entry': pos.get('liquidity_at_entry', 0),
            'liquidity_at_exit': liquidity,
        })
    
    # Compute concurrent position stats
    if concurrent_samples:
        avg_concurrent = sum(c for _, c in concurrent_samples) / len(concurrent_samples)
    else:
        avg_concurrent = 0
    
    # Attach concurrency stats to completed trades for reporting
    concurrency_stats = {
        'max_concurrent': max_concurrent_seen,
        'avg_concurrent': round(avg_concurrent, 1),
        'total_unique_tokens_traded': len(set(t['symbol'] for t in completed)),
    }
    
    return completed, concurrency_stats


# --- Strategies --------------------------------------------------

def strategy_score_threshold(snap, history, idx):
    """Enter when score crosses above threshold."""
    if snap['score'] is None:
        return False, ''
    if snap['score'] >= ENTRY_SCORE:
        # Additional filters
        if snap['liquidity'] < 5000:
            return False, ''
        if snap['rug_ratio'] > 0.3:
            return False, ''
               
        return True, f'score={snap["score"]}'
    return False, ''

def strategy_smart_money_cluster_clean(snap, history, idx):
    """
    Same entry as strategy_smart_money_cluster (smart_degen jump >= 3),
    but adds a volume/liquidity ratio cap — the single strongest predictor
    found in the token_summary backtest (rho=-0.41, p<0.0001). Excludes
    entries during what's likely a wash-trading or manipulation spike
    rather than genuine organic volume.
    """
    if len(history) < 2:
        return False, ''
    prev = history[-2]
    if prev['smart_degen'] is None or snap['smart_degen'] is None:
        return False, ''
    jump = snap['smart_degen'] - prev['smart_degen']
    if jump < 3 or snap['smart_degen'] < ENTRY_SMART_MONEY:
        return False, ''
    if snap['liquidity'] < 5000:
        return False, ''
    return True, f'smart_money_jump=+{jump},total={snap["smart_degen"]}'

def strategy_smart_money_cluster(snap, history, idx):
    """Enter when smart_degen_count jumps by 3+ from previous snapshot."""
    if len(history) < 2:
        return False, ''
    prev = history[-2]
    if prev['smart_degen'] is None or snap['smart_degen'] is None:
        return False, ''
    jump = snap['smart_degen'] - prev['smart_degen']
    if jump >= 3 and snap['smart_degen'] >= ENTRY_SMART_MONEY:
        if snap['liquidity'] < 5000:
            return False, ''
        return True, f'smart_money_jump=+{jump},total={snap["smart_degen"]}'
    return False, ''


def strategy_smart_money_full(snap, history, idx):
    """Ultra-tight signal token strategy: high-quality entries with strong conviction."""
    if snap['smart_degen'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 65:
        return False, ''
    if snap['smart_degen'] < 10:
        return False, ''
    if snap['liquidity'] < 20000:
        return False, ''
    if snap['rug_ratio'] > 0.08:
        return False, ''
    if snap['price_change_1h'] is not None and snap['price_change_1h'] < 50:
        return False, ''
    return True, f'sm={snap["smart_degen"]},score={snap["score"]},liq={snap["liquidity"]:.0f}'


def strategy_combined(snap, history, idx):
    """Combined: score >= 60 AND smart_degen >= 4 AND no fast_dump AND liquidity > 10k."""
    if snap['score'] is None:
        return False, ''
    
    # Check for fast_dump flag in recent history
    has_fast_dump = False
    for h in history[-3:]:
        if h.get('flags') and 'fast_dump' in str(h['flags']):
            has_fast_dump = True
            break    
    if (snap['score'] >= 60 and 
        snap['smart_degen'] >= 4 and
        not has_fast_dump and
        snap['liquidity'] >= 10000 and
        snap['rug_ratio'] <= 0.15 and
        snap['dex'] in ['pump_amm']):
        return True, f'score={snap["score"]},sm={snap["smart_degen"]},liq={snap["liquidity"]:.0f}'
    return False, ''


def strategy_momentum(snap, history, idx):
    """Enter on price momentum: trending-only, score >= 50, smart money, relaxed filters."""
    if snap['score'] is None or snap['price_change_5m'] is None:
        return False, ''
    if (snap.get('endpoint') == 'trending' and
        snap['price_change_5m'] >= -10 and
        snap['price_change_1h'] >= 25 and
        snap['score'] >= 50 and
        snap['smart_degen'] >= 3 and
        snap['liquidity'] >= 5000 and
        snap['dex'] in ['pump_amm']):
        return True, f'momentum={snap["price_change_5m"]:.1f}%,score={snap["score"]}'
    return False, ''


# --- Contrarian Strategies (based on signal analysis) --------------------------

def strategy_contrarianModerate(snap, history, idx):
    """Signal tokens with MODERATE scores (50-65) but strong smart money.
    Thesis: High-score tokens are past their prime. Moderate scores with
    conviction (SM >= 8) catch tokens before the algorithm fully recognizes them."""
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 50 or snap['score'] > 65:
        return False, ''  # Moderate score band
    if snap['smart_degen'] < 8:
        return False, ''  # Strong smart money conviction
    if snap['liquidity'] < 10000:
        return False, ''  # Minimum liquidity
    if snap['rug_ratio'] > 0.10:
        return False, ''
    if snap['price_change_1h'] is not None and snap['price_change_1h'] < 50:
        return False, ''
    return True, f'contrarian:score={snap["score"]},sm={snap["smart_degen"]},liq={snap["liquidity"]:.0f}'


def strategy_contrarianLowCap(snap, history, idx):
    """Signal tokens with LOW market cap but high smart money.
    Thesis: Small MC tokens with smart money attention have the most room to grow."""
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 50:
        return False, ''
    if snap['smart_degen'] < 10:
        return False, ''  # High SM conviction
    if snap['liquidity'] < 10000:
        return False, ''
    if snap['liquidity'] > 30000:
        return False, ''  # Low liquidity cap = small MC
    if snap['rug_ratio'] > 0.08:
        return False, ''
    if snap['price_change_1h'] is not None and snap['price_change_1h'] < 50:
        return False, ''
    return True, f'lowcap:sm={snap["smart_degen"]},liq={snap["liquidity"]:.0f},score={snap["score"]}'


def strategy_contrarianVolume(snap, history, idx):
    """Signal tokens with LOW bundler rate (organic activity).
    Thesis: High bundler rate = bot manipulation. Low bundler = organic growth."""
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 55:
        return False, ''
    if snap['smart_degen'] < 7:
        return False, ''
    if snap['liquidity'] < 10000:
        return False, ''
    if snap['rug_ratio'] > 0.10:
        return False, ''
    if snap.get('bundler_rate', 0) > 0.15:
        return False, ''  # Low bundler = organic
    if snap['price_change_1h'] is not None and snap['price_change_1h'] < 50:
        return False, ''
    return True, f'organic:score={snap["score"]},sm={snap["smart_degen"]},bundler={snap.get("bundler_rate",0):.3f}'


def strategy_contrarianBalanced(snap, history, idx):
    """Balanced contrarian: moderate score + high SM + low MC + organic volume.
    Combines the best insights from winning patterns."""
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 55 or snap['score'] > 75:
        return False, ''  # Sweet spot: 55-75
    if snap['smart_degen'] < 10:
        return False, ''  # Strong SM
    if snap['liquidity'] < 15000:
        return False, ''
    if snap['liquidity'] > 35000:
        return False, ''  # Keep MC moderate
    if snap['rug_ratio'] > 0.08:
        return False, ''
    if snap.get('bundler_rate', 0) > 0.20:
        return False, ''  # Not too bot-heavy
    if snap['price_change_1h'] is not None and snap['price_change_1h'] < 50:
        return False, ''
    return True, f'balanced:score={snap["score"]},sm={snap["smart_degen"]},liq={snap["liquidity"]:.0f}'


# --- Analysis ----------------------------------------------------

def compute_drawdown(trades):
    """Compute equity curve, max drawdown, and streak stats from a list of trades.
    
    Drawdown is calculated against total equity (BANKROLL + P&L), so percentages
    reflect real risk relative to starting capital.
    """
    if not trades:
        return {}
    
    # Sort trades by exit time to build equity curve in order
    sorted_trades = sorted(trades, key=lambda x: x['exit_ts'])
    
    # Equity curve starts at BANKROLL, not $0 P&L
    equity = [BANKROLL]
    peak = BANKROLL
    max_dd_pct = 0.0
    max_dd_usd = 0.0
    max_dd_duration_min = 0.0
    current_dd_start = None
    
    # Streak tracking
    win_streak = 0
    loss_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    current_streak_type = None
    streak_count = 0
    
    # Running P&L
    running_pnl = 0.0
    
    for t in sorted_trades:
        pnl_usd = t['pnl_pct'] / 100 * POSITION_SIZE_USD
        running_pnl += pnl_usd
        total_equity = BANKROLL + running_pnl
        equity.append(total_equity)
        
        # Drawdown tracking (against total equity)
        if total_equity > peak:
            peak = total_equity
            current_dd_start = None  # New peak, reset drawdown start
        
        dd_pct = ((peak - total_equity) / peak * 100) if peak > 0 else 0
        dd_usd = peak - total_equity
        
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            max_dd_usd = dd_usd
            if current_dd_start is None:
                current_dd_start = t['exit_ts']
        
        if dd_pct > 0 and current_dd_start is not None:
            dd_duration = (t['exit_ts'] - current_dd_start).total_seconds() / 60
            if dd_duration > max_dd_duration_min:
                max_dd_duration_min = dd_duration
        
        # Streak tracking
        is_win = t['pnl_pct'] > 0
        streak_type = 'win' if is_win else 'loss'
        
        if streak_type == current_streak_type:
            streak_count += 1
        else:
            streak_count = 1
            current_streak_type = streak_type
        
        if is_win:
            win_streak = streak_count
            loss_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
        else:
            loss_streak = streak_count
            win_streak = 0
            max_loss_streak = max(max_loss_streak, loss_streak)
    
    total_return = running_pnl
    final_equity = BANKROLL + running_pnl
    calmar = (total_return / max_dd_usd) if max_dd_usd > 0 else float('inf')
    
    return {
        'max_drawdown_pct': round(max_dd_pct, 2),
        'max_drawdown_usd': round(max_dd_usd, 2),
        'max_drawdown_duration_min': round(max_dd_duration_min, 1),
        'calmar_ratio': round(calmar, 2),
        'max_win_streak': max_win_streak,
        'max_loss_streak': max_loss_streak,
        'final_equity': round(final_equity, 2),
        'peak_equity': round(peak, 2),
    }


def analyze_trades(trades, strategy_name):
    """Compute performance metrics for a set of trades."""
    if not trades:
        return {
            'strategy': strategy_name,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'total_pnl': 0,
            'max_win': 0,
            'max_loss': 0,
            'avg_hold_minutes': 0,
            'profit_factor': 0,
            'max_drawdown_pct': 0,
            'max_drawdown_usd': 0,
            'max_drawdown_duration_min': 0,
            'calmar_ratio': 0,
            'max_win_streak': 0,
            'max_loss_streak': 0,
        }
    
    df = pd.DataFrame(trades)
    wins = len(df[df['pnl_pct'] > 0])
    losses = len(df[df['pnl_pct'] <= 0])
    total = len(df)
    
    gross_profit = df[df['pnl_pct'] > 0]['pnl_pct'].sum()
    gross_loss = abs(df[df['pnl_pct'] <= 0]['pnl_pct'].sum())
    
    # Position-size-weighted P&L
    df['pnl_usd'] = df['pnl_pct'] / 100 * POSITION_SIZE_USD
    
    # Slippage cost analysis
    if 'entry_slippage_bps' in df.columns:
        df['total_slippage_bps'] = df['entry_slippage_bps'] + df['exit_slippage_bps']
        df['slippage_cost_usd'] = df['total_slippage_bps'] / 10000 * POSITION_SIZE_USD
        total_slippage_usd = df['slippage_cost_usd'].sum()
        avg_slippage_bps = df['total_slippage_bps'].mean()
        # P&L without slippage (what you'd have if execution were perfect)
        df['pnl_no_slip'] = df.apply(
            lambda r: ((r.get('signal_exit_price', r['exit_price']) - r.get('signal_price', r['entry_price'])) 
                       / r.get('signal_price', r['entry_price']) * 100) if r.get('signal_price') else r['pnl_pct'], 
            axis=1
        )
        df['pnl_no_slip_usd'] = df['pnl_no_slip'] / 100 * POSITION_SIZE_USD
        gross_profit_no_slip = df[df['pnl_no_slip'] > 0]['pnl_no_slip'].sum()
        gross_loss_no_slip = abs(df[df['pnl_no_slip'] <= 0]['pnl_no_slip'].sum())
    else:
        total_slippage_usd = 0
        avg_slippage_bps = 0
        gross_profit_no_slip = gross_profit
        gross_loss_no_slip = gross_loss
    
    # Drawdown stats
    dd = compute_drawdown(trades)
    
    return {
        'strategy': strategy_name,
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
        'avg_pnl': round(df['pnl_pct'].mean(), 2),
        'median_pnl': round(df['pnl_pct'].median(), 2),
        'total_pnl': round(df['pnl_usd'].sum(), 2),
        'total_pnl_pct': round(df['pnl_pct'].sum(), 2),
        'max_win': round(df['pnl_pct'].max(), 2),
        'max_loss': round(df['pnl_pct'].min(), 2),
        'avg_hold_minutes': round(df['hold_minutes'].mean(), 1),
        'profit_factor': round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf'),
        'avg_entry_score': round(df['entry_score'].mean(), 1),
        'avg_entry_smart_degen': round(df['entry_smart_degen'].mean(), 1),
        'exit_reasons': df['exit_reason'].value_counts().to_dict(),
        'total_slippage_usd': round(total_slippage_usd, 2),
        'avg_slippage_bps': round(avg_slippage_bps, 1),
        'pnl_without_slippage': round(df['pnl_no_slip_usd'].sum(), 2) if 'pnl_no_slip_usd' in df.columns else round(df['pnl_usd'].sum(), 2),
        'profit_factor_no_slip': round(gross_profit_no_slip / gross_loss_no_slip, 2) if gross_loss_no_slip > 0 else float('inf'),
        'max_drawdown_pct': dd['max_drawdown_pct'],
        'max_drawdown_usd': dd['max_drawdown_usd'],
        'max_drawdown_duration_min': dd['max_drawdown_duration_min'],
        'calmar_ratio': dd['calmar_ratio'],
        'max_win_streak': dd['max_win_streak'],
        'max_loss_streak': dd['max_loss_streak'],
        'peak_equity': dd['peak_equity'],
        'final_equity': dd['final_equity'],
    }


def print_results(results, all_trades, concurrency_by_strategy):
    """Print formatted backtest results."""
    print("\n" + "=" * 90)
    print("SMART MONEY SIGNAL BACKTEST RESULTS")
    print("=" * 90)
    print(f"Position size: ${POSITION_SIZE_USD} | Stop loss: {STOP_LOSS_PCT}% | Take profit: {TAKE_PROFIT_PCT}%")
    print(f"Max hold: {MAX_HOLD_MINUTES} min | Max concurrent: {MAX_CONCURRENT_POSITIONS} | Min obs: {MIN_OBSERVATIONS}")
    print("-" * 90)
    
    # Summary table
    print(f"\n{'Strategy':<25} {'Trades':>7} {'Win%':>7} {'Avg P&L':>9} {'Total $':>9} {'PF':>6} {'MaxDD%':>8} {'Calmar':>7} {'MaxCon':>7}")
    print("-" * 100)
    for r in results:
        conc = concurrency_by_strategy.get(r['strategy'], {})
        max_con = conc.get('max_concurrent', 0)
        print(f"{r['strategy']:<25} {r['total_trades']:>7} {r['win_rate']:>6.1f}% {r['avg_pnl']:>8.1f}% ${r['total_pnl']:>8.2f} {r['profit_factor']:>6.2f} {r['max_drawdown_pct']:>7.1f}% {r['calmar_ratio']:>7.2f} {max_con:>7}")
    
    # Detailed breakdown per strategy
    for r in results:
        if r['total_trades'] == 0:
            continue
        conc = concurrency_by_strategy.get(r['strategy'], {})
        print(f"\n{'-' * 60}")
        print(f"  {r['strategy']} -- {r['total_trades']} trades")
        print(f"{'-' * 60}")
        print(f"  Win rate:      {r['win_rate']}% ({r['wins']}W / {r['losses']}L)")
        print(f"  Avg P&L:       {r['avg_pnl']}% | Median: {r['median_pnl']}%")
        print(f"  Total P&L:     ${r['total_pnl']} ({r['total_pnl_pct']}%)")
        print(f"  Profit factor: {r['profit_factor']}")
        print(f"  Peak equity:   ${r['peak_equity']} (bankroll + P&L) | Final: ${r['final_equity']}")
        print(f"  Max drawdown:  {r['max_drawdown_pct']}% (${r['max_drawdown_usd']} USD)")
        print(f"  Max DD period: {r['max_drawdown_duration_min']} min")
        print(f"  Calmar ratio:  {r['calmar_ratio']} (return / max DD)")
        print(f"  Best streak:   {r['max_win_streak']}W | Worst streak: {r['max_loss_streak']}L")
        print(f"  Concurrency:   max={conc.get('max_concurrent', 0)} | avg={conc.get('avg_concurrent', 0)} | unique tokens={conc.get('total_unique_tokens_traded', 0)}")
        print(f"  Avg hold:      {r['avg_hold_minutes']} min")
        print(f"  Avg entry score: {r['avg_entry_score']} | Avg entry SM: {r['avg_entry_smart_degen']}")
        print(f"  Exit reasons:  {r['exit_reasons']}")
        print(f"  --- Slippage ---")
        print(f"  Total cost:    ${r['total_slippage_usd']} ({r['avg_slippage_bps']} avg bps)")
        print(f"  P&L w/o slip:  ${r['pnl_without_slippage']} (vs ${r['total_pnl']} with slippage)")
        print(f"  PF w/o slip:   {r['profit_factor_no_slip']} (vs {r['profit_factor']} with slippage)")
    
    # Top trades across all strategies
    if all_trades:
        print(f"\n{'=' * 80}")
        print("TOP 10 TRADES (by P&L %)")
        print("=" * 80)
        top = sorted(all_trades, key=lambda x: x['pnl_pct'], reverse=True)[:10]
        for t in top:
            emoji = "+" if t['pnl_pct'] > 0 else "-"
            print(f"  {emoji} {t['symbol']:<15} {t['pnl_pct']:>+8.1f}%  ${t['entry_price']:.8f} -> ${t['exit_price']:.8f}  {t['hold_minutes']:.0f}min  [{t['strategy']}]")
            print(f"     Entry score={t['entry_score']}, SM={t['entry_smart_degen']} | Exit: {t['exit_reason']}")
    
    # Worst trades
    if all_trades:
        print(f"\n{'=' * 80}")
        print("BOTTOM 10 TRADES (by P&L %)")
        print("=" * 80)
        worst = sorted(all_trades, key=lambda x: x['pnl_pct'])[:10]
        for t in worst:
            emoji = "+" if t['pnl_pct'] > 0 else "-"
            print(f"  {emoji} {t['symbol']:<15} {t['pnl_pct']:>+8.1f}%  ${t['entry_price']:.8f} -> ${t['exit_price']:.8f}  {t['hold_minutes']:.0f}min  [{t['strategy']}]")
            print(f"     Entry score={t['entry_score']}, SM={t['entry_smart_degen']} | Exit: {t['exit_reason']}")


def save_trades(trades, filepath):
    """Save trade log to CSV."""
    if not trades:
        return
    df = pd.DataFrame(trades)
    df.to_csv(filepath, index=False)
    print(f"\nTrade log saved to {filepath}")


# --- Main --------------------------------------------------------

def main():
    print("Loading snapshots...")
    df = load_snapshots(DATA_DIR)
    if df.empty:
        print("No data found. Exiting.")
        return
    
    print(f"\nBuilding token timelines...")
    timelines = build_token_timelines(df)
    
    if not timelines:
        print("No timelines built. Exiting.")
        return
    
    # Define strategies
    strategies = [
        ("score_threshold", strategy_score_threshold, "Score >= 65"),
        ("smart_money_full", strategy_smart_money_full, "Signal SM Full"),
        ("smart_money_cluster_clean", strategy_smart_money_cluster_clean, "SM Jump +3"),
        ("combined", strategy_combined, "Combined Filter"),
        ("momentum", strategy_momentum, "Momentum + SM"),
        ("contrarianModerate", strategy_contrarianModerate, "Contrarian Moderate"),
        ("contrarianLowCap", strategy_contrarianLowCap, "Contrarian Low Cap"),
        ("contrarianVolume", strategy_contrarianVolume, "Contrarian Organic"),
        ("contrarianBalanced", strategy_contrarianBalanced, "Contrarian Balanced"),
    ]
    
    all_results = []
    all_trades = []
    concurrency_by_strategy = {}
    
    for name, fn, label in strategies:
        print(f"\nRunning strategy: {label}...")
        trades, conc_stats = simulate_strategy(timelines, fn, label)
        result = analyze_trades(trades, label)
        all_results.append(result)
        all_trades.extend(trades)
        concurrency_by_strategy[label] = conc_stats
        print(f"  -> {result['total_trades']} trades, {result['win_rate']}% win rate, ${result['total_pnl']} P&L")
        print(f"     Max concurrent: {conc_stats['max_concurrent']}, Unique tokens: {conc_stats['total_unique_tokens_traded']}")
    
    # Print results
    print_results(all_results, all_trades, concurrency_by_strategy)
    
    # Save trade log
    if all_trades:
        save_trades(all_trades, os.path.join(DATA_DIR, 'backtest_smart_money_trades.csv'))
    
    # Save summary
    summary_path = os.path.join(DATA_DIR, 'backtest_smart_money_summary.json')
    with open(summary_path, 'w') as f:
        json.dump({
            'run_ts': datetime.now().isoformat(),
            'config': {
                'entry_score': ENTRY_SCORE,
                'entry_smart_money': ENTRY_SMART_MONEY,
                'stop_loss_pct': STOP_LOSS_PCT,
                'take_profit_pct': TAKE_PROFIT_PCT,
                'max_hold_minutes': MAX_HOLD_MINUTES,
                'position_size_usd': POSITION_SIZE_USD,
                'max_concurrent_positions': MAX_CONCURRENT_POSITIONS,
                'min_observations': MIN_OBSERVATIONS,
            },
            'results': all_results,
            'concurrency': concurrency_by_strategy,
            'total_tokens_analyzed': len(timelines),
        }, f, indent=2)
    print(f"Summary saved to {summary_path}")


if __name__ == '__main__':
    main()