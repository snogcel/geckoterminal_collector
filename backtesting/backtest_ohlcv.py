"""
OHLCV-based Signal Backtest
============================
Uses Postgres notification_log + ohlcv_data to simulate trading strategies
with continuous 5m candle price data instead of CSV snapshots.

Key advantages over CSV backtester:
  - Continuous 5m price data (no data_end gap issues)
  - Precise entry/exit simulation using actual OHLC
  - Uses real notification times as entry signals
  - No dependency on CSV snapshot files

Entry signals come from notification_log.entry_data (score, SM, etc.)
Price timelines come from ohlcv_data (5m candles).

Usage:
  python backtest_ohlcv.py [--min-candles 5] [--strategies all]
"""

import psycopg2
import json
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# --- Config ------------------------------------------------------
DB = {
    'host': 'localhost',
    'port': 5432,
    'database': 'gecko_terminal_collector',
    'user': 'trixia',
    'password': 'velo_car_keys_1234!'
}

# Strategy parameters (same as CSV backtester for comparison)
ENTRY_SCORE = 50
ENTRY_SMART_MONEY = 3
EXIT_SCORE_DROP = 20
STOP_LOSS_PCT = -30
TAKE_PROFIT_PCT = 50
MAX_HOLD_MINUTES = 60
POSITION_SIZE_USD = 100
BANKROLL = 1000
MAX_CONCURRENT_POSITIONS = 5
COOLDOWN_MINUTES = 24 * 60  # 24h re-entry cooldown

# Slippage model (same as CSV backtester)
ENTRY_SLIPPAGE_BPS = 50
EXIT_SLIPPAGE_BPS = 50
LIQUIDITY_IMPACT_MULT = 3
SPREAD_BPS = 30

MIN_CANDLES = 5  # Minimum 5m candles required for a token to be eligible


def calc_slippage(liquidity_usd, position_usd=POSITION_SIZE_USD):
    """Calculate total slippage in basis points."""
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
    return round(base + impact_bps + spread_premium, 1)


def apply_slippage(price, slippage_bps, is_buy=True):
    """Apply slippage to a price."""
    multiplier = slippage_bps / 10000
    if is_buy:
        return price * (1 + multiplier)
    else:
        return price * (1 - multiplier)


def load_notifications():
    """Load all notification entries with their metadata."""
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, token_symbol, token_address, pool_address,
               notification_type, sent_at, entry_data
        FROM notification_log
        ORDER BY sent_at
    """)

    notifications = []
    for row in cur.fetchall():
        entry_data = json.loads(row[6]) if row[6] else {}
        notifications.append({
            'id': row[0],
            'symbol': row[1],
            'token_address': row[2],
            'pool_address': row[3],
            'type': row[4],
            'sent_at': row[5],
            # Metadata from entry_data
            'score': entry_data.get('score'),
            'smart_degen': entry_data.get('smart_degen_count', 0),
            'renowned': entry_data.get('renowned_count', 0),
            'rug_ratio': entry_data.get('rug_ratio', 0),
            'bundler_rate': entry_data.get('bundler_rate', 0),
            'liquidity': entry_data.get('liquidity', 0),
            'market_cap': entry_data.get('marketCap', 0),
            'price': entry_data.get('price'),
            'endpoint': entry_data.get('endpoint', 'unknown'),
            'dex': entry_data.get('dex', ''),
            'source': entry_data.get('source', ''),
        })

    conn.close()
    print(f"Loaded {len(notifications)} notifications")
    return notifications


def load_ohlcv(pool_address, after_time, before_time):
    """Load 5m OHLCV candles for a pool within a time window."""
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    pool_id = f"solana_{pool_address}"

    cur.execute("""
        SELECT datetime, open_price, high_price, low_price, close_price, volume_usd
        FROM ohlcv_data
        WHERE pool_id = %s
          AND timeframe = '5m'
          AND datetime >= %s
          AND datetime <= %s
        ORDER BY datetime
    """, (pool_id, after_time, before_time))

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
    return candles


def build_token_timelines(notifications, min_candles=MIN_CANDLES):
    """Build per-token OHLCV timelines from notifications + ohlcv_data.
    
    For each notification, fetch 5m candles starting 30min before notification
    (for pre-entry context) through 4 hours after (for exit simulation).
    """
    # Expand window: 30min before for context, 4h after for exits
    PRE_WINDOW_MINUTES = 30
    POST_WINDOW_MINUTES = 240

    timelines = {}
    skipped = 0

    for notif in notifications:
        pool = notif['pool_address']
        if not pool:
            skipped += 1
            continue

        after = notif['sent_at'] - timedelta(minutes=PRE_WINDOW_MINUTES)
        before = notif['sent_at'] + timedelta(minutes=POST_WINDOW_MINUTES)

        candles = load_ohlcv(pool, after, before)

        if len(candles) < min_candles:
            skipped += 1
            continue

        # Find the candle closest to notification time for entry price
        entry_price = None
        entry_candle_idx = None
        for i, c in enumerate(candles):
            if c['ts'] >= notif['sent_at']:
                entry_price = c['open']  # Enter at open of next candle after signal
                entry_candle_idx = i
                break

        if entry_price is None:
            # Notification is after all candles; use last close
            entry_price = candles[-1]['close']
            entry_candle_idx = len(candles) - 1

        # Build the combined timeline
        key = f"{pool}_{notif['sent_at'].isoformat()}"
        timelines[key] = {
            'symbol': notif['symbol'],
            'pool_address': pool,
            'notification': notif,
            'candles': candles,
            'entry_price': entry_price,
            'entry_candle_idx': entry_candle_idx,
        }

    print(f"Built {len(timelines)} timelines (skipped {skipped} with < {min_candles} candles)")
    return timelines


def simulate_strategy(timelines, strategy_fn, strategy_name):
    """Run a strategy across all OHLCV timelines with concurrent position tracking.
    
    Unlike the CSV backtester, OHLCV gives us continuous 5m candle data,
    so we can simulate exits at precise candle boundaries instead of
    snapshot-to-snapshot jumps.
    """
    # Collect all entry points sorted by time
    entries = []
    for key, tl in timelines.items():
        notif = tl['notification']
        snap = {
            'score': notif['score'],
            'smart_degen': notif['smart_degen'],
            'renowned': notif['renowned'],
            'rug_ratio': notif['rug_ratio'],
            'bundler_rate': notif['bundler_rate'],
            'liquidity': notif['liquidity'],
            'market_cap': notif['market_cap'],
            'endpoint': notif['endpoint'],
            'dex': notif['dex'],
            'price': tl['entry_price'],
        }
        entries.append((notif['sent_at'], key, tl, snap))

    entries.sort(key=lambda x: x[0])

    open_positions = []
    completed = []
    held_tokens = set()
    position_cooldown = {}
    max_concurrent_seen = 0
    concurrent_samples = []

    for ts, key, tl, snap in entries:
        pool = tl['pool_address']

        # --- Check exits for ALL open positions using their own timelines ---
        still_open = []
        for pos in open_positions:
            # Find the timeline for this position's pool
            pos_tl = None
            for k, candidate_tl in timelines.items():
                if candidate_tl['pool_address'] == pos['pool']:
                    pos_tl = candidate_tl
                    break
            
            if pos_tl is None:
                still_open.append(pos)
                continue
            
            # Walk through candles from entry to current timestamp
            candles = pos_tl['candles']
            entry_idx = pos.get('entry_candle_idx', 0)
            exit_reason = None
            exit_price = None
            exit_ts = None

            for i in range(entry_idx + 1, len(candles)):
                c = candles[i]
                # Stop evaluating past current time
                if c['ts'] > ts:
                    break
                entry_p = pos['entry_price']

                low_pnl = (c['low'] - entry_p) / entry_p * 100
                high_pnl = (c['high'] - entry_p) / entry_p * 100

                # Check stop loss (worst case: hit at low)
                if low_pnl <= STOP_LOSS_PCT:
                    exit_price = entry_p * (1 + STOP_LOSS_PCT / 100)
                    exit_reason = 'stop_loss'
                    exit_ts = c['ts']
                    break

                # Check take profit (best case: hit at high)
                if high_pnl >= TAKE_PROFIT_PCT:
                    exit_price = entry_p * (1 + TAKE_PROFIT_PCT / 100)
                    exit_reason = 'take_profit'
                    exit_ts = c['ts']
                    break

                # Check timeout
                hold_minutes = (c['ts'] - pos['entry_ts']).total_seconds() / 60
                if hold_minutes >= MAX_HOLD_MINUTES:
                    exit_price = c['close']
                    exit_reason = 'timeout'
                    exit_ts = c['ts']
                    break

            if exit_reason:
                # Apply exit slippage
                liquidity = pos.get('liquidity', 50000)
                exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
                actual_exit_price = apply_slippage(exit_price, exit_slip_bps, is_buy=False)

                pnl_pct = (actual_exit_price - pos['entry_price']) / pos['entry_price'] * 100
                hold_min = (exit_ts - pos['entry_ts']).total_seconds() / 60

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
                position_cooldown[pool] = exit_ts
            else:
                still_open.append(pos)

        open_positions = still_open

        # Track concurrency
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
                actual_entry_price = apply_slippage(tl['entry_price'], entry_slip_bps, is_buy=True)

                pos = {
                    'symbol': tl['symbol'],
                    'pool': pool,
                    'entry_price': actual_entry_price,
                    'signal_price': tl['entry_price'],
                    'entry_ts': ts,
                    'entry_candle_idx': tl['entry_candle_idx'],
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

    # Force-close remaining positions at last candle
    for pos in open_positions:
        # Find the timeline for this pool
        for key, tl in timelines.items():
            if tl['pool_address'] == pos['pool']:
                last_candle = tl['candles'][-1]
                liquidity = pos.get('liquidity', 50000)
                exit_slip_bps = calc_slippage(liquidity, POSITION_SIZE_USD)
                actual_exit_price = apply_slippage(last_candle['close'], exit_slip_bps, is_buy=False)
                pnl_pct = (actual_exit_price - pos['entry_price']) / pos['entry_price'] * 100
                hold_min = (last_candle['ts'] - pos['entry_ts']).total_seconds() / 60

                completed.append({
                    'symbol': pos['symbol'],
                    'pool': pos['pool'],
                    'entry_ts': pos['entry_ts'],
                    'exit_ts': last_candle['ts'],
                    'entry_price': pos['entry_price'],
                    'exit_price': actual_exit_price,
                    'pnl_pct': pnl_pct,
                    'hold_minutes': hold_min,
                    'exit_reason': 'data_end_ohlcv',  # OHLCV ran out
                    'strategy': strategy_name,
                    'entry_score': pos.get('entry_score', 0),
                    'entry_smart_degen': pos.get('entry_smart_degen', 0),
                    'liquidity': pos.get('liquidity', 0),
                    'entry_slippage_bps': pos.get('entry_slippage_bps', 0),
                    'exit_slippage_bps': exit_slip_bps,
                    'signal_price': pos.get('signal_price', pos['entry_price']),
                })
                break

    # Compute concurrency stats
    if concurrent_samples:
        avg_concurrent = sum(c for _, c in concurrent_samples) / len(concurrent_samples)
    else:
        avg_concurrent = 0

    concurrency_stats = {
        'max_concurrent': max_concurrent_seen,
        'avg_concurrent': round(avg_concurrent, 1),
        'total_unique_tokens': len(set(t['symbol'] for t in completed)),
    }

    return completed, concurrency_stats


# --- Strategies --------------------------------------------------
# These mirror the CSV backtester strategies but use notification-time data only.
# Score/SM are static (from notification); price comes from OHLCV candles.

def strategy_score_threshold(snap):
    """Enter when score >= threshold."""
    if snap['score'] is None:
        return False, ''
    if snap['score'] >= ENTRY_SCORE:
        if snap['liquidity'] < 5000:
            return False, ''
        if snap['rug_ratio'] > 0.3:
            return False, ''
        return True, f'score={snap["score"]}'
    return False, ''


def strategy_smart_money_full(snap):
    """Signal-only, high conviction: score >= 65, SM >= 10, signal endpoint."""
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
    return True, f'sm={snap["smart_degen"]},score={snap["score"]}'


def strategy_combined(snap):
    """Combined: score >= 60, SM >= 4, no high rug, pump_amm."""
    if snap['score'] is None:
        return False, ''
    if (snap['score'] >= 60 and
        snap['smart_degen'] >= 4 and
        snap['liquidity'] >= 10000 and
        snap['rug_ratio'] <= 0.15 and
        snap['dex'] in ['pump_amm']):
        return True, f'score={snap["score"]},sm={snap["smart_degen"]}'
    return False, ''


def strategy_momentum(snap):
    """Trending-only, score >= 50, SM >= 3."""
    if snap['score'] is None:
        return False, ''
    if (snap.get('endpoint') == 'trending' and
        snap['score'] >= 50 and
        snap['smart_degen'] >= 3 and
        snap['liquidity'] >= 5000 and
        snap['dex'] in ['pump_amm']):
        return True, f'momentum:score={snap["score"]},sm={snap["smart_degen"]}'
    return False, ''


def strategy_contrarian_moderate(snap):
    """Moderate scores (50-65) with strong SM."""
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
    return True, f'contrarian:score={snap["score"]},sm={snap["smart_degen"]}'


def strategy_contrarian_balanced(snap):
    """Balanced contrarian: moderate score + high SM + low MC + organic."""
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
    return True, f'balanced:score={snap["score"]},sm={snap["smart_degen"]}'


def strategy_contrarian_organic(snap):
    """Low bundler rate = organic activity."""
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
    return True, f'organic:score={snap["score"]},sm={snap["smart_degen"]}'


# --- Analysis ----------------------------------------------------

def compute_drawdown(trades):
    """Compute equity curve and max drawdown from trades."""
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

    total_return = running_pnl
    calmar = (total_return / max_dd_usd) if max_dd_usd > 0 else float('inf')

    return {
        'max_drawdown_pct': round(max_dd_pct, 2),
        'max_drawdown_usd': round(max_dd_usd, 2),
        'calmar_ratio': round(calmar, 2),
        'final_equity': round(BANKROLL + running_pnl, 2),
        'peak_equity': round(peak, 2),
    }


def analyze_trades(trades, strategy_name):
    """Compute performance metrics for a set of trades."""
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
    """Print formatted backtest results."""
    print("\n" + "=" * 100)
    print("OHLCV SIGNAL BACKTEST RESULTS")
    print("=" * 100)
    print(f"Position size: ${POSITION_SIZE_USD} | Stop loss: {STOP_LOSS_PCT}% | Take profit: {TAKE_PROFIT_PCT}%")
    print(f"Max hold: {MAX_HOLD_MINUTES} min | Max concurrent: {MAX_CONCURRENT_POSITIONS}")
    print("-" * 100)

    # Summary table
    print(f"\n{'Strategy':<25} {'Trades':>7} {'Win%':>7} {'Avg P&L':>9} {'Total $':>9} {'PF':>6} {'MaxDD%':>8} {'Calmar':>7}")
    print("-" * 90)
    for r in results:
        print(f"{r['strategy']:<25} {r['total_trades']:>7} {r['win_rate']:>6.1f}% {r['avg_pnl']:>8.1f}% ${r['total_pnl']:>8.2f} {r['profit_factor']:>6.2f} {r['max_drawdown_pct']:>7.1f}% {r['calmar_ratio']:>7.2f}")

    # Detailed breakdown
    for r in results:
        if r['total_trades'] == 0:
            continue
        conc = concurrency_by_strategy.get(r['strategy'], {})
        print(f"\n{'-' * 60}")
        print(f"  {r['strategy']} -- {r['total_trades']} trades")
        print(f"{'-' * 60}")
        print(f"  Win rate:      {r['win_rate']}% ({r['wins']}W / {r['losses']}L)")
        print(f"  Avg P&L:       {r['avg_pnl']}% | Median: {r['median_pnl']}%")
        print(f"  Total P&L:     ${r['total_pnl']}")
        print(f"  Profit factor: {r['profit_factor']}")
        print(f"  Peak equity:   ${r['peak_equity']} | Final: ${r['final_equity']}")
        print(f"  Max drawdown:  {r['max_drawdown_pct']}%")
        print(f"  Calmar ratio:  {r['calmar_ratio']}")
        print(f"  Avg hold:      {r['avg_hold_minutes']} min")
        print(f"  Avg entry score: {r['avg_entry_score']} | Avg entry SM: {r['avg_entry_smart_degen']}")
        print(f"  Exit reasons:  {r['exit_reasons']}")

    # All trades
    if all_trades:
        print(f"\n{'=' * 100}")
        print("ALL TRADES (sorted by P&L)")
        print("=" * 100)
        sorted_trades = sorted(all_trades, key=lambda x: x['pnl_pct'], reverse=True)
        for t in sorted_trades:
            emoji = "+" if t['pnl_pct'] > 0 else "-"
            print(f"  {emoji} {t['symbol']:<15} {t['pnl_pct']:>+8.1f}%  ${t['entry_price']:.8f} -> ${t['exit_price']:.8f}  {t['hold_minutes']:.0f}min  [{t['strategy']}]  exit={t['exit_reason']}")
            print(f"     score={t['entry_score']}, SM={t['entry_smart_degen']}, liq=${t['liquidity']:.0f}")


def save_trades(trades, filepath):
    """Save trade log to CSV."""
    import pandas as pd
    if not trades:
        return
    df = pd.DataFrame(trades)
    df.to_csv(filepath, index=False)
    print(f"\nTrade log saved to {filepath}")


# --- Main --------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='OHLCV Signal Backtest')
    parser.add_argument('--min-candles', type=int, default=MIN_CANDLES,
                        help='Minimum 5m candles required per token')
    parser.add_argument('--strategies', default='all',
                        help='Comma-separated strategy names, or "all"')
    args = parser.parse_args()

    print("Loading notifications from Postgres...")
    notifications = load_notifications()

    print(f"\nBuilding OHLCV timelines (min_candles={args.min_candles})...")
    timelines = build_token_timelines(notifications, min_candles=args.min_candles)

    if not timelines:
        print("No timelines built. Exiting.")
        return

    # Define strategies
    all_strategies = [
        ("score_threshold", strategy_score_threshold, "Score >= 65"),
        ("smart_money_full", strategy_smart_money_full, "Signal SM Full"),
        ("combined", strategy_combined, "Combined Filter"),
        ("momentum", strategy_momentum, "Momentum + SM"),
        ("contrarianModerate", strategy_contrarian_moderate, "Contrarian Moderate"),
        ("contrarianBalanced", strategy_contrarian_balanced, "Contrarian Balanced"),
        ("contrarianOrganic", strategy_contrarian_organic, "Contrarian Organic"),
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
        print(f"\nRunning strategy: {label}...")
        trades, conc_stats = simulate_strategy(timelines, fn, label)
        result = analyze_trades(trades, label)
        all_results.append(result)
        all_trades.extend(trades)
        concurrency_by_strategy[label] = conc_stats
        print(f"  -> {result['total_trades']} trades, {result['win_rate']}% win rate, ${result['total_pnl']} P&L")

    # Print results
    print_results(results=all_results, all_trades=all_trades,
                  concurrency_by_strategy=concurrency_by_strategy)

    # Save trade log
    if all_trades:
        save_trades(all_trades, os.path.join(os.path.dirname(__file__), 'backtest_ohlcv_trades.csv'))


if __name__ == '__main__':
    main()
