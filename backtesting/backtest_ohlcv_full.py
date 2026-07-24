"""
OHLCV Backtest — Full Watchlist Population
===========================================
Uses enhanced_watchlist_history + ohlcv_data to simulate trading strategies
across the ENTIRE watchlist population, not just notified tokens.

This eliminates the notification filter bias and gives a fair comparison
of strategy performance across all tokens.

Key differences from notification-based backtest:
  - Tests ALL watchlist observations, not just notified ones
  - Score/SM/rug from metadata_json.original_data
  - Multiple entry points per token (different observation times)
  - Fair comparison of contrarian vs momentum strategies

Usage:
  python backtest_ohlcv_full.py [--min-candles 10] [--min-observations 2]
"""

import psycopg2
import json
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict


def normalize_ts(ts):
    """Strip timezone info for consistent comparison."""
    if ts is None:
        return None
    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
        return ts.replace(tzinfo=None)
    return ts

# --- Config ------------------------------------------------------
DB = {
    'host': 'localhost',
    'port': 5432,
    'database': 'gecko_terminal_collector',
    'user': 'trixia',
    'password': 'velo_car_keys_1234!'
}

# Strategy parameters
STOP_LOSS_PCT = -30
TAKE_PROFIT_PCT = 50
MAX_HOLD_MINUTES = 60
POSITION_SIZE_USD = 100
BANKROLL = 1000
MAX_CONCURRENT_POSITIONS = 5
COOLDOWN_MINUTES = 24 * 60

# Slippage model
ENTRY_SLIPPAGE_BPS = 50
EXIT_SLIPPAGE_BPS = 50
LIQUIDITY_IMPACT_MULT = 3
SPREAD_BPS = 30

MIN_CANDLES = 10
MIN_OBSERVATIONS = 2  # Min observations before entry


def calc_slippage(liquidity_usd, position_usd=POSITION_SIZE_USD):
    liquidity_usd = float(liquidity_usd)
    position_usd = float(position_usd)
    base = ENTRY_SLIPPAGE_BPS + SPREAD_BPS
    if liquidity_usd > 0:
        impact_bps = (position_usd / liquidity_usd) * 10000 * LIQUIDITY_IMPACT_MULT
    else:
        impact_bps = 500
    if liquidity_usd < 10000:
        spread_premium = 50
    elif liquidity_usd < 50000:
        spread_premium = 20
    else:
        spread_premium = 0
    return round(float(base + impact_bps + spread_premium), 1)


def apply_slippage(price, slippage_bps, is_buy=True):
    price = float(price)
    multiplier = float(slippage_bps) / 10000.0
    if is_buy:
        return price * (1 + multiplier)
    else:
        return price * (1 - multiplier)


def load_watchlist_observations(min_observations=MIN_OBSERVATIONS):
    """Load all enhanced_watchlist_history entries with score/SM data and OHLCV."""
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # Get all observations with score/SM data and OHLCV coverage
    cur.execute("""
        SELECT DISTINCT
            e.pool_address,
            e.token_symbol,
            e.collected_at,
            e.liquidity,
            e.volume,
            e.price_change_5m,
            e.price_change_1h,
            e.market_cap,
            (e.metadata_json::json->'original_data'->>'score')::float as score,
            (e.metadata_json::json->'original_data'->>'smart_degen_count')::int as smart_degen,
            (e.metadata_json::json->'original_data'->>'rug_ratio')::float as rug_ratio,
            (e.metadata_json::json->'original_data'->>'bundler_rate')::float as bundler_rate,
            (e.metadata_json::json->'original_data'->>'renowned_count')::int as renowned,
            (e.metadata_json::json->'original_data'->>'endpoint') as endpoint,
            (e.metadata_json::json->'original_data'->>'dex') as dex,
            (e.metadata_json::json->'original_data'->>'price')::float as notif_price
        FROM enhanced_watchlist_history e
        WHERE e.metadata_json IS NOT NULL
          AND (e.metadata_json::json->'original_data'->>'smart_degen_count') IS NOT NULL
          AND (e.metadata_json::json->'original_data'->>'score') IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM ohlcv_data o
            WHERE o.pool_id = 'solana_' || e.pool_address
              AND o.timeframe = '5m'
          )
        ORDER BY e.pool_address, e.collected_at
    """)

    observations = []
    for row in cur.fetchall():
        observations.append({
            'pool_address': row[0],
            'symbol': row[1],
            'collected_at': row[2],
            'liquidity': row[3] or 0,
            'volume': row[4] or 0,
            'price_change_5m': row[5],
            'price_change_1h': row[6],
            'market_cap': row[7] or 0,
            'score': row[8],
            'smart_degen': row[9] or 0,
            'rug_ratio': row[10] or 0,
            'bundler_rate': row[11] or 0,
            'renowned': row[12] or 0,
            'endpoint': row[13] or 'unknown',
            'dex': row[14] or '',
            'notif_price': row[15],
        })


    conn.close()
    print("Loaded %d observations with score/SM data" % len(observations))
    return observations


def build_timelines(observations, min_observations=MIN_OBSERVATIONS):
    """Group observations by pool and build OHLCV timelines."""
    # Group by pool
    by_pool = defaultdict(list)
    for obs in observations:
        by_pool[obs['pool_address']].append(obs)

    PRE_WINDOW = 30   # minutes before first observation
    POST_WINDOW = 240  # minutes after last observation

    timelines = {}
    skipped = 0

    for pool, obs_list in by_pool.items():
        obs_list.sort(key=lambda x: x['collected_at'])

        if len(obs_list) < min_observations:
            skipped += 1
            continue

        first_obs = obs_list[0]
        last_obs = obs_list[-1]

        after = first_obs['collected_at'] - timedelta(minutes=PRE_WINDOW)
        before = last_obs['collected_at'] + timedelta(minutes=POST_WINDOW)

        # Load OHLCV
        conn = psycopg2.connect(**DB)
        cur = conn.cursor()
        pool_id = 'solana_' + pool
        cur.execute("""
            SELECT datetime, open_price, high_price, low_price, close_price, volume_usd
            FROM ohlcv_data
            WHERE pool_id = %s AND timeframe = '5m'
              AND datetime >= %s AND datetime <= %s
            ORDER BY datetime
        """, (pool_id, after, before))
        candles = []
        for row in cur.fetchall():
            candles.append({
                'ts': row[0],
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': float(row[5]),
            })
        conn.close()

        if len(candles) < min_observations:
            skipped += 1
            continue

        # Find entry price for each observation. Skip (don't just leave
        # un-keyed) any observation with no candle at/after its own
        # timestamp - simulate_strategy() reads obs['entry_price']
        # unconditionally, so an observation missing this key will KeyError
        # downstream rather than silently doing the wrong thing.
        valid_obs = []
        dropped_no_price = 0
        for obs in obs_list:
            obs_time = obs['collected_at'].replace(tzinfo=None) if obs['collected_at'].tzinfo else obs['collected_at']
            entry_price = None
            entry_candle_idx = None
            for i, c in enumerate(candles):
                c_ts = c['ts'].replace(tzinfo=None) if c['ts'].tzinfo else c['ts']
                if c_ts >= obs_time:
                    entry_price = float(c['open'])
                    entry_candle_idx = i
                    break
            if entry_price is None:
                # No candle covers this observation's time - skip it rather
                # than substituting a stale (possibly earlier-than-entry)
                # candle price, which previously produced negative hold
                # times when the exit-scan found a trigger before entry_ts.
                dropped_no_price += 1
                continue
            obs['entry_price'] = entry_price
            obs['entry_candle_idx'] = entry_candle_idx
            valid_obs.append(obs)

        if dropped_no_price:
            print("  [WARN] pool %s: dropped %d/%d observation(s) with no covering candle" % (
                pool, dropped_no_price, len(obs_list)))

        if len(valid_obs) < min_observations:
            skipped += 1
            continue

        obs_list = valid_obs

        key = pool
        timelines[key] = {
            'symbol': first_obs['symbol'],
            'pool_address': pool,
            'observations': obs_list,
            'candles': candles,
        }

    print("Built %d timelines (skipped %d with < %d observations)" % (
        len(timelines), skipped, min_observations))
    return timelines


def simulate_strategy(timelines, strategy_fn, strategy_name):
    """Run strategy across all timelines with concurrent position tracking."""
    # Collect all entry points
    entries = []
    for key, tl in timelines.items():
        for obs in tl['observations']:
            snap = {
                'score': obs['score'],
                'smart_degen': obs['smart_degen'],
                'renowned': obs['renowned'],
                'rug_ratio': obs['rug_ratio'],
                'bundler_rate': obs['bundler_rate'],
                'liquidity': obs['liquidity'],
                'volume': obs['volume'],
                'market_cap': obs['market_cap'],
                'endpoint': obs['endpoint'],
                'dex': obs['dex'],
                'price': obs['entry_price'],
                'price_change_5m': obs['price_change_5m'],
                'price_change_1h': obs['price_change_1h'],
            }
            entries.append((obs['collected_at'], key, tl, snap, obs))

    entries.sort(key=lambda x: x[0])

    open_positions = []
    completed = []
    held_tokens = set()
    position_cooldown = {}
    max_concurrent_seen = 0
    concurrent_samples = []

    for ts, key, tl, snap, obs in entries:
        pool = tl['pool_address']

        # --- Check exits for ALL open positions at this timestamp ---
        still_open = []
        for pos in open_positions:
            # Find this position's timeline
            pos_tl = None
            for k, candidate_tl in timelines.items():
                if candidate_tl['pool_address'] == pos['pool']:
                    pos_tl = candidate_tl
                    break
            if pos_tl is None:
                still_open.append(pos)
                continue

            candles = pos_tl['candles']
            entry_idx = pos.get('entry_candle_idx', 0)
            exit_reason = None
            exit_price = None
            exit_ts = None
            peak_price = pos['entry_price']

            for i in range(entry_idx, len(candles)):
                c = candles[i]
                # Only check candles up to current timestamp
                if normalize_ts(c['ts']) > normalize_ts(ts):
                    break
                entry_p = pos['entry_price']

                if c['high'] > peak_price:
                    peak_price = c['high']

                low_pnl = (c['low'] - entry_p) / entry_p * 100
                peak_pnl = (peak_price - entry_p) / entry_p * 100

                if low_pnl <= STOP_LOSS_PCT:
                    exit_price = entry_p * (1 + STOP_LOSS_PCT / 100)
                    exit_reason = 'stop_loss'
                    exit_ts = normalize_ts(c['ts'])
                    break
                if peak_pnl >= TAKE_PROFIT_PCT:
                    exit_price = entry_p * (1 + TAKE_PROFIT_PCT / 100)
                    exit_reason = 'take_profit'
                    exit_ts = normalize_ts(c['ts'])
                    break
                hold_minutes = (normalize_ts(c['ts']) - normalize_ts(pos['entry_ts'])).total_seconds() / 60
                if hold_minutes >= MAX_HOLD_MINUTES:
                    exit_price = c['close']
                    exit_reason = 'timeout'
                    exit_ts = normalize_ts(c['ts'])
                    break

            if exit_reason:
                liquidity = pos.get('liquidity', 50000)
                exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
                actual_exit_price = apply_slippage(exit_price, exit_slip_bps, is_buy=False)
                pnl_pct = (actual_exit_price - pos['entry_price']) / pos['entry_price'] * 100
                hold_min = (normalize_ts(exit_ts) - normalize_ts(pos['entry_ts'])).total_seconds() / 60

                completed.append({
                    'symbol': pos['symbol'],
                    'pool': pos['pool'],
                    'entry_ts': pos['entry_ts'],
                    'exit_ts': exit_ts,
                    'entry_price': pos['entry_price'],
                    'exit_price': actual_exit_price,
                    'pnl_pct': pnl_pct,
                    'hold_minutes': hold_min,
                    'exit_reason': exit_reason,
                    'strategy': strategy_name,
                    'entry_score': pos.get('entry_score', 0),
                    'entry_smart_degen': pos.get('entry_smart_degen', 0),
                    'liquidity': pos.get('liquidity', 0),
                    'entry_slippage_bps': pos.get('entry_slippage_bps', 0),
                    'exit_slippage_bps': exit_slip_bps,
                    'signal_price': pos.get('signal_price', pos['entry_price']),
                })
                held_tokens.discard(pool)
                position_cooldown[pool] = normalize_ts(exit_ts)
            else:
                still_open.append(pos)

        open_positions = still_open
        concurrent_samples.append((ts, len(open_positions)))
        max_concurrent_seen = max(max_concurrent_seen, len(open_positions))

        # --- Check entry ---
        cooldown_ok = (pool not in position_cooldown or
                       (ts - position_cooldown[pool]).total_seconds() / 60 > COOLDOWN_MINUTES)

        if (pool not in held_tokens and cooldown_ok
                and len(open_positions) < MAX_CONCURRENT_POSITIONS):
            should_enter, reason = strategy_fn(snap)
            if should_enter:
                entry_slip_bps = calc_slippage(snap['liquidity'], POSITION_SIZE_USD)
                actual_entry_price = apply_slippage(tl['candles'][obs['entry_candle_idx']]['open'],
                                                    entry_slip_bps, is_buy=True)
                pos = {
                    'symbol': tl['symbol'],
                    'pool': pool,
                    'entry_price': actual_entry_price,
                    'signal_price': tl['candles'][obs['entry_candle_idx']]['open'],
                    'entry_ts': ts,
                    'entry_candle_idx': obs['entry_candle_idx'],
                    'entry_score': snap.get('score', 0),
                    'entry_smart_degen': snap.get('smart_degen', 0),
                    'liquidity': snap.get('liquidity', 0),
                    'reason': reason,
                    'entry_slippage_bps': entry_slip_bps,
                }
                open_positions.append(pos)
                held_tokens.add(pool)
                concurrent_samples.append((ts, len(open_positions)))
                max_concurrent_seen = max(max_concurrent_seen, len(open_positions))

    # Force-close remaining
    for pos in open_positions:
        for key, tl in timelines.items():
            if tl['pool_address'] == pos['pool']:
                last_candle = tl['candles'][-1]
                liquidity = pos.get('liquidity', 50000)
                exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
                actual_exit_price = apply_slippage(last_candle['close'], exit_slip_bps, is_buy=False)
                pnl_pct = (actual_exit_price - pos['entry_price']) / pos['entry_price'] * 100
                hold_min = (normalize_ts(last_candle['ts']) - normalize_ts(pos['entry_ts'])).total_seconds() / 60
                completed.append({
                    'symbol': pos['symbol'],
                    'pool': pos['pool'],
                    'entry_ts': pos['entry_ts'],
                    'exit_ts': normalize_ts(last_candle['ts']),
                    'entry_price': pos['entry_price'],
                    'exit_price': actual_exit_price,
                    'pnl_pct': pnl_pct,
                    'hold_minutes': hold_min,
                    'exit_reason': 'data_end_ohlcv',
                    'strategy': strategy_name,
                    'entry_score': pos.get('entry_score', 0),
                    'entry_smart_degen': pos.get('entry_smart_degen', 0),
                    'liquidity': pos.get('liquidity', 0),
                    'entry_slippage_bps': pos.get('entry_slippage_bps', 0),
                    'exit_slippage_bps': exit_slip_bps,
                    'signal_price': pos.get('signal_price', pos['entry_price']),
                })
                break

    avg_concurrent = sum(c for _, c in concurrent_samples) / len(concurrent_samples) if concurrent_samples else 0
    concurrency_stats = {
        'max_concurrent': max_concurrent_seen,
        'avg_concurrent': round(avg_concurrent, 1),
        'total_unique_tokens': len(set(t['symbol'] for t in completed)),
    }
    return completed, concurrency_stats


# --- Strategies --------------------------------------------------

def strategy_score_threshold(snap):
    if snap['score'] is None:
        return False, ''
    if snap['score'] >= 50:
        if snap['liquidity'] < 5000:
            return False, ''
        if snap['rug_ratio'] > 0.3:
            return False, ''
        return True, 'score=%s' % snap['score']
    return False, ''


def strategy_smart_money_full(snap):
    if snap['smart_degen'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] is None or snap['score'] < 65:
        return False, ''
    if snap['smart_degen'] < 10:
        return False, ''
    if snap['liquidity'] < 20000:
        return False, ''
    if snap['rug_ratio'] > 0.08:
        return False, ''
    return True, 'sm=%s,score=%s' % (snap['smart_degen'], snap['score'])


def strategy_combined(snap):
    if snap['score'] is None:
        return False, ''
    if (snap['score'] >= 60 and
        snap['smart_degen'] >= 4 and
        snap['liquidity'] >= 10000 and
        snap['rug_ratio'] <= 0.15 and
        snap['dex'] in ['pump_amm']):
        return True, 'score=%s,sm=%s' % (snap['score'], snap['smart_degen'])
    return False, ''


def strategy_momentum(snap):
    if snap['score'] is None or snap['price_change_5m'] is None or snap['price_change_1h'] is None:
        return False, ''
    if (snap['price_change_5m'] >= 0 and
        snap['price_change_1h'] >= 50 and
        snap.get('endpoint') == 'trending' and
        snap['score'] >= 50 and
        snap['smart_degen'] >= 3 and
        snap['liquidity'] >= 5000 and
        snap['dex'] in ['pump_amm']):
        return True, 'momentum:score=%s,sm=%s,pc5m=%s,pc1h=%s' % (
            snap['score'], snap['smart_degen'], snap['price_change_5m'], snap['price_change_1h'])
    return False, ''


def strategy_momentum_clean(snap):
    if snap['score'] is None or snap['price_change_5m'] is None or snap['price_change_1h'] is None:
        return False, ''
    if not (snap['price_change_5m'] >= 0 and snap['price_change_1h'] >= 50
            and snap.get('endpoint') == 'trending'
            and snap['score'] >= 50 and snap['smart_degen'] >= 3
            and snap['liquidity'] >= 5000 and snap['dex'] in ['pump_amm']):
        return False, ''
    vol_liq_ratio = (snap['volume'] / snap['liquidity']) if snap['liquidity'] else 999
    if vol_liq_ratio >= 15:
        return False, ''
    return True, 'momentum_clean:pc5m=%s,pc1h=%s,vol_liq=%.1f' % (
        snap['price_change_5m'], snap['price_change_1h'], vol_liq_ratio)


def strategy_contrarian_moderate(snap):
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 50 or snap['score'] > 65:
        return False, ''
    if snap['smart_degen'] < 8:
        return False, ''
    if snap['liquidity'] < 10000:
        return False, ''
    if snap['rug_ratio'] > 0.10:
        return False, ''
    return True, 'contrarian:score=%s,sm=%s' % (snap['score'], snap['smart_degen'])


def strategy_contrarian_balanced(snap):
    if snap['score'] is None:
        return False, ''
    if not snap.get('endpoint', '').startswith('signal'):
        return False, ''
    if snap['score'] < 55 or snap['score'] > 75:
        return False, ''
    if snap['smart_degen'] < 10:
        return False, ''
    if snap['liquidity'] < 15000:
        return False, ''
    if snap['liquidity'] > 35000:
        return False, ''
    if snap['rug_ratio'] > 0.08:
        return False, ''
    if snap.get('bundler_rate', 0) > 0.20:
        return False, ''
    return True, 'balanced:score=%s,sm=%s' % (snap['score'], snap['smart_degen'])


def strategy_contrarian_organic(snap):
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
        return False, ''
    return True, 'organic:score=%s,sm=%s' % (snap['score'], snap['smart_degen'])


# Broader strategies that work across all endpoints
def strategy_high_conviction(snap):
    """High score + high SM, any endpoint."""
    if snap['score'] is None:
        return False, ''
    if snap['score'] >= 70 and snap['smart_degen'] >= 10:
        if snap['liquidity'] >= 15000 and snap['rug_ratio'] <= 0.10:
            return True, 'high_conv:score=%s,sm=%s' % (snap['score'], snap['smart_degen'])
    return False, ''


def strategy_low_cap_momentum(snap):
    """Low MC + momentum + SM, any endpoint."""
    if snap['score'] is None:
        return False, ''
    if (snap['market_cap'] > 0 and snap['market_cap'] < 100000 and
        snap['smart_degen'] >= 5 and snap['score'] >= 50 and
        snap['liquidity'] >= 5000 and snap['rug_ratio'] <= 0.15):
        return True, 'lowcap:mc=%s,sm=%s' % (snap['market_cap'], snap['smart_degen'])
    return False, ''


def strategy_organic_growth(snap):
    """Low bundler rate + moderate SM, any endpoint."""
    if snap['score'] is None:
        return False, ''
    if (snap.get('bundler_rate', 1) < 0.10 and
        snap['smart_degen'] >= 5 and snap['score'] >= 55 and
        snap['liquidity'] >= 10000 and snap['rug_ratio'] <= 0.10):
        return True, 'organic growth:bundle=%.3f,sm=%s' % (snap.get('bundler_rate', 0), snap['smart_degen'])
    return False, ''


# --- Analysis ----------------------------------------------------

def compute_drawdown(trades):
    if not trades:
        return {}
    sorted_trades = sorted(trades, key=lambda x: x['exit_ts'])
    equity = [BANKROLL]
    peak = BANKROLL
    max_dd_pct = 0.0
    max_dd_usd = 0.0
    running_pnl = 0.0
    for t in sorted_trades:
        pnl_usd = t['pnl_pct'] / 100 * POSITION_SIZE_USD
        running_pnl += pnl_usd
        total_equity = BANKROLL + running_pnl
        equity.append(total_equity)
        if total_equity > peak:
            peak = total_equity
        dd_pct = ((peak - total_equity) / peak * 100) if peak > 0 else 0
        dd_usd = peak - total_equity
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            max_dd_usd = dd_usd
    calmar = (running_pnl / max_dd_usd) if max_dd_usd > 0 else float('inf')
    return {
        'max_drawdown_pct': round(max_dd_pct, 2),
        'max_drawdown_usd': round(max_dd_usd, 2),
        'calmar_ratio': round(calmar, 2),
        'final_equity': round(BANKROLL + running_pnl, 2),
        'peak_equity': round(peak, 2),
    }


def analyze_trades(trades, strategy_name):
    if not trades:
        return {
            'strategy': strategy_name,
            'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
            'avg_pnl': 0, 'total_pnl': 0, 'max_win': 0, 'max_loss': 0,
            'avg_hold_minutes': 0, 'profit_factor': 0,
            'max_drawdown_pct': 0, 'calmar_ratio': 0,
        }

    import pandas as pd
    df = pd.DataFrame(trades)
    wins = len(df[df['pnl_pct'] > 0])
    losses = len(df[df['pnl_pct'] <= 0])
    total = len(df)
    gross_profit = df[df['pnl_pct'] > 0]['pnl_pct'].sum() if wins > 0 else 0
    gross_loss = abs(df[df['pnl_pct'] <= 0]['pnl_pct'].sum()) if losses > 0 else 0
    df['pnl_usd'] = df['pnl_pct'] / 100 * POSITION_SIZE_USD
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
        'max_win': round(df['pnl_pct'].max(), 2),
        'max_loss': round(df['pnl_pct'].min(), 2),
        'avg_hold_minutes': round(df['hold_minutes'].mean(), 1),
        'profit_factor': round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf'),
        'avg_entry_score': round(df['entry_score'].mean(), 1),
        'avg_entry_smart_degen': round(df['entry_smart_degen'].mean(), 1),
        'exit_reasons': df['exit_reason'].value_counts().to_dict(),
        'max_drawdown_pct': dd['max_drawdown_pct'],
        'calmar_ratio': dd['calmar_ratio'],
        'final_equity': dd['final_equity'],
        'peak_equity': dd['peak_equity'],
    }


def print_results(results, all_trades, concurrency_by_strategy):
    print("\n" + "=" * 100)
    print("FULL WATCHLIST OHLCV BACKTEST RESULTS")
    print("=" * 100)
    print("Position size: $%d | SL: %d%% | TP: %d%% | Max hold: %d min" % (
        POSITION_SIZE_USD, STOP_LOSS_PCT, TAKE_PROFIT_PCT, MAX_HOLD_MINUTES))
    print("-" * 100)

    print("\n%-30s %7s %7s %9s %9s %6s %8s %7s" % (
        'Strategy', 'Trades', 'Win%', 'Avg P&L', 'Total $', 'PF', 'MaxDD%', 'Calmar'))
    print("-" * 100)
    for r in results:
        print("%-30s %7d %6.1f%% %+8.1f%% $%8.2f %6.2f %7.1f%% %7.2f" % (
            r['strategy'], r['total_trades'], r['win_rate'], r['avg_pnl'],
            r['total_pnl'], r['profit_factor'], r['max_drawdown_pct'], r['calmar_ratio']))

    for r in results:
        if r['total_trades'] == 0:
            continue
        print("\n%s" % ('-' * 60))
        print("  %s -- %d trades" % (r['strategy'], r['total_trades']))
        print("%s" % ('-' * 60))
        print("  Win rate:      %s%% (%dW / %dL)" % (r['win_rate'], r['wins'], r['losses']))
        print("  Avg P&L:       %s%% | Median: %s%%" % (r['avg_pnl'], r['median_pnl']))
        print("  Total P&L:     $%s" % r['total_pnl'])
        print("  Profit factor: %s" % r['profit_factor'])
        print("  Peak/Final:    $%s / $%s" % (r['peak_equity'], r['final_equity']))
        print("  Max drawdown:  %s%%" % r['max_drawdown_pct'])
        print("  Calmar ratio:  %s" % r['calmar_ratio'])
        print("  Avg hold:      %s min" % r['avg_hold_minutes'])
        print("  Avg entry:     score=%s SM=%s" % (r['avg_entry_score'], r['avg_entry_smart_degen']))
        print("  Exit reasons:  %s" % r['exit_reasons'])

    if all_trades:
        print("\n%s" % ('=' * 100))
        print("ALL TRADES (sorted by P&L)")
        print("=" * 100)
        sorted_trades = sorted(all_trades, key=lambda x: x['pnl_pct'], reverse=True)
        for t in sorted_trades:
            emoji = "+" if t['pnl_pct'] > 0 else "-"
            print("  %s %-15s %+8.1f%%  $%.8f -> $%.8f  %5.0fmin  [%s]  exit=%s" % (
                emoji, t['symbol'], t['pnl_pct'], t['entry_price'], t['exit_price'],
                t['hold_minutes'], t['strategy'], t['exit_reason']))
            print("     score=%s, SM=%s, liq=$%s" % (
                t['entry_score'], t['entry_smart_degen'], t['liquidity']))


def save_trades(trades, filepath):
    import pandas as pd
    if not trades:
        return
    df = pd.DataFrame(trades)
    df.to_csv(filepath, index=False)
    print("\nTrade log saved to %s" % filepath)


# --- Main --------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Full Watchlist OHLCV Backtest')
    parser.add_argument('--min-candles', type=int, default=MIN_CANDLES)
    parser.add_argument('--min-observations', type=int, default=MIN_OBSERVATIONS)
    parser.add_argument('--strategies', default='all')
    args = parser.parse_args()

    print("Loading watchlist observations...")
    observations = load_watchlist_observations(min_observations=args.min_observations)

    print("\nBuilding timelines...")
    timelines = build_timelines(observations, min_observations=args.min_observations)

    if not timelines:
        print("No timelines built. Exiting.")
        return

    all_strategies = [
        ("score_threshold", strategy_score_threshold, "Score >= 50"),
        ("smart_money_full", strategy_smart_money_full, "Signal SM Full"),
        ("combined", strategy_combined, "Combined Filter"),
        ("momentum", strategy_momentum, "Momentum + SM"),
        ("contrarianModerate", strategy_contrarian_moderate, "Contrarian Moderate"),
        ("contrarianBalanced", strategy_contrarian_balanced, "Contrarian Balanced"),
        ("contrarianOrganic", strategy_contrarian_organic, "Contrarian Organic"),
        ("highConviction", strategy_high_conviction, "High Conviction"),
        ("lowCapMomentum", strategy_low_cap_momentum, "Low Cap Momentum"),
        ("organicGrowth", strategy_organic_growth, "Organic Growth"),
    ]

    if args.strategies == 'all':
        strategies = all_strategies
    else:
        names = [s.strip() for s in args.strategies.split(',')]
        strategies = [(n, fn, label) for n, fn, label in all_strategies if n in names]

    all_results = []
    all_trades = []
    concurrency_by_strategy = {}

    for name, fn, label in strategies:
        print("\nRunning strategy: %s..." % label)
        trades, conc_stats = simulate_strategy(timelines, fn, label)
        result = analyze_trades(trades, label)
        all_results.append(result)
        all_trades.extend(trades)
        concurrency_by_strategy[label] = conc_stats
        print("  -> %d trades, %s%% win rate, $%s P&L" % (
            result['total_trades'], result['win_rate'], result['total_pnl']))

    print_results(results=all_results, all_trades=all_trades,
                  concurrency_by_strategy=concurrency_by_strategy)

    if all_trades:
        save_trades(all_trades, os.path.join(os.path.dirname(__file__), 'backtest_ohlcv_full_trades.csv'))


if __name__ == '__main__':
    main()