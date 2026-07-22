"""
GMGN Watchlist Generator
------------------------
Replaces the DexScreener scraper with GMGN's rich API data.
Fetches trending tokens, applies quality filters, outputs watchlist.

Usage:
    python gmgn_watchlist_export.py                  # Generate watchlist
    python gmgn_watchlist_export.py --live           # Live mode (for cron)
    python gmgn_watchlist_export.py --backtest       # Output for backtesting
    python gmgn_watchlist_export.py --signal         # Include smart money signals
"""

import subprocess
import json
import csv
import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Quality filters (based on GMGN SKILL.md criteria)
FILTERS = {
    # Hard disqualifiers (skip immediately)
    'max_rug_ratio': 0.30,
    'require_no_wash_trading': True,
    'require_renounced_mint': True,       # SOL only
    'require_renounced_freeze': True,     # SOL only

    # Smart money thresholds
    'min_smart_degen_count': 0,           # At least 2 smart money wallets
    'min_renowned_count': 0,              # KOL count (optional)

    # Safety thresholds
    'max_top10_holder_rate': 0.50,        # Top 10 holders < 40%
    'max_bundler_rate': 0.40,             # Bot bundler ratio
    'max_insider_rate': 0.30,             # Insider trading ratio
    'max_dev_team_hold_rate': 0.99,       # Dev team holding < 15%

    # Liquidity & volume
    'min_liquidity': 5000,                # Minimum $5K liquidity
    'min_volume_1h': 10000,               # Minimum $10K 1h volume
    'min_holder_count': 1,               # At least 20 holders

    # Token age (seconds)
    'max_age_hours': 2,                   # Tokens up to 6h old

    # Platform filter (SOL)
    'platforms': ['Pump.fun', 'letsbonk', 'bonkers', 'pump_mayhem',
                  'pump_mayhem_agent', 'pump_agent', 'bags'],
}

# ==============================================================================
# STRATEGY A CRITERIA (advisory tag, not a live collection gate)
# ==============================================================================
# The original DexScreener-era momentum/liquidity/volume/ranking/dex bar that
# historically produced ~5-10 trades/day. Kept deliberately separate from
# FILTERS above: FILTERS is the safety/quality gate applied at collection
# time (rug ratio, wash trading, holder concentration, etc.) and controls
# what actually makes it into the watchlist. STRATEGY_A is evaluated on
# every token that already passed FILTERS and recorded as an additional
# 'passes_strategy_a' column, so it can be analyzed retroactively against
# the aggregator's outcome data without narrowing live collection (and
# without waiting through Strategy A's naturally low daily signal count
# to build up a usable sample).
#
# Caveats vs. the original DexScreener-sourced version of this strategy:
#   - 'dex': DexScreener's 'PumpSwap' maps to GMGN's exchange code
#     'pump_amm' (see the pump/pump_amm discussion in the review thread).
#   - 'ranking': GMGN's trending rank (token.get('rank')). Only meaningful
#     for trending-sourced tokens - trenches/signal-sourced tokens may
#     report rank=0, which would trivially satisfy 'ranking<=100' without
#     reflecting real trending status. Worth excluding non-trending rows
#     from any strategy-A-conditional analysis until this is resolved.
#   - 'makers_increase': no direct GMGN equivalent (see docstring on
#     format_watchlist_entry_legacy). Computed from holder_count, which is
#     cumulative and slower-moving than the original "active traders in
#     window" metric - treat this specific condition as unreliable until
#     validated against a few days of live results.
STRATEGY_A = {
    'dex': 'pump_amm',            # DexScreener's 'PumpSwap'
    'max_age_hours': 1,
    'max_ranking': 100,
    'min_price_change_1h': 50,
    'min_price_change_5m_positive': True,  # priceChange5m > 0
    'min_liquidity': 45000,
    'min_volume': 350000,
    'min_makers_increase': 1.25,  # unreliable proxy - see caveats above
    'min_volume_spike': 2.3,
}

# Output paths
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_DIR = '/home/jon/sites/geckoterminal_collector/'  # Use same dir for now; switch to Linux path for production
BACKTEST_DIR = OUTPUT_DIR
STATE_FILE = os.path.join(WATCHLIST_DIR, 'watchlist_state.json')

# ==============================================================================
# DEACTIVATION THRESHOLDS
# ==============================================================================
# Tokens are deactivated when they hit these exit signals.
# Tokens that simply fall off trending (absent for N cycles) are retired naturally.
DEACTIVATION_THRESHOLDS = {
    # Immediate deactivation (single-cycle triggers)
    'rug_ratio_spike': 0.50,          # rug_ratio exceeds this → deactivate
    'liquidity_drop_pct': 0.50,       # liquidity drops >50% from last seen → deactivate
    'smart_money_exit': 0,            # smart_degen_count drops to 0 (was >= 2) → deactivate
    'wash_trading_detected': True,    # is_wash_trading becomes true → deactivate

    # Gradual deactivation (multi-cycle)
    'absent_cycles_retire': 3,        # absent from N consecutive watchlists → retired
    'score_decline_threshold': 0.40,  # score drops >40% from peak → flag (not auto-deactivate)

    # Monitoring windows
    'max_tracked_tokens': 500,        # max tokens to keep in state (LRU eviction)
    'state_ttl_hours': 48,            # purge tokens not seen for this long
}


import shutil
import hashlib


class WatchlistStateManager:
    """
    Tracks token state across watchlist cycles for threshold-based deactivation.

    State schema (per token in watchlist_state.json):
    {
      "<token_address>": {
        "first_seen": "2026-07-21T14:00:00Z",
        "last_seen": "2026-07-21T14:30:00Z",
        "last_seen_cycle": 42,
        "consecutive_absent": 0,
        "peak_score": 78,
        "prev_metrics": {
          "rug_ratio": 0.08,
          "liquidity": 32969,
          "smart_degen_count": 17,
          "holder_count": 1061,
          "is_wash_trading": false
        },
        "active": true,
        "deactivation_reason": null,
        "deactivated_at": null
      }
    }
    """

    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self.state = self._load()
        self.cycle_number = self._compute_cycle_number()

    def _load(self):
        """Load state from disk, or return empty state."""
        if not os.path.exists(self.state_file):
            return {'tokens': {}, 'meta': {'total_cycles': 0, 'last_run': None}}
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Migrate old format if needed
            if 'tokens' not in data:
                data = {'tokens': data, 'meta': {'total_cycles': 0, 'last_run': None}}
            return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [WARN] Could not load state file: {e}. Starting fresh.")
            return {'tokens': {}, 'meta': {'total_cycles': 0, 'last_run': None}}

    def save(self):
        """Persist state to disk."""
        self.state['meta']['last_run'] = datetime.now(timezone.utc).isoformat()
        self.state['meta']['total_cycles'] = self.cycle_number
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
        except IOError as e:
            print(f"  [ERROR] Could not save state: {e}")

    def _compute_cycle_number(self):
        """Derive a monotonically increasing cycle number from total_runs."""
        return self.state.get('meta', {}).get('total_cycles', 0) + 1

    def get_token_state(self, address):
        """Get tracked state for a token, or None."""
        return self.state['tokens'].get(address)

    def update_token(self, address, token_data, active=True, deactivation_reason=None):
        """
        Update tracked state for a token after a watchlist cycle.
        If the token was previously tracked, preserve first_seen and peak_score.
        """
        now = datetime.now(timezone.utc).isoformat()
        prev = self.state['tokens'].get(address)

        current_score = score_token(token_data)
        current_metrics = {
            'rug_ratio': token_data.get('rug_ratio', 0) or 0,
            'liquidity': _first_present(token_data, 'liquidity', default=0) or 0,
            'smart_degen_count': token_data.get('smart_degen_count', 0) or 0,
            'holder_count': token_data.get('holder_count', 0) or 0,
            'is_wash_trading': token_data.get('is_wash_trading', False),
        }

        if prev:
            prev['last_seen'] = now
            prev['last_seen_cycle'] = self.cycle_number
            prev['consecutive_absent'] = 0
            prev['peak_score'] = max(prev.get('peak_score', 0), current_score)
            prev['prev_metrics'] = current_metrics
            prev['active'] = active
            prev['deactivation_reason'] = deactivation_reason
            if deactivation_reason:
                prev['deactivated_at'] = now
        else:
            self.state['tokens'][address] = {
                'first_seen': now,
                'last_seen': now,
                'last_seen_cycle': self.cycle_number,
                'consecutive_absent': 0,
                'peak_score': current_score,
                'prev_metrics': current_metrics,
                'active': active,
                'deactivation_reason': deactivation_reason,
                'deactivated_at': now if deactivation_reason else None,
            }

    def mark_absent(self, address):
        """Increment absent counter for a token not seen in this cycle."""
        prev = self.state['tokens'].get(address)
        if prev:
            prev['consecutive_absent'] = prev.get('consecutive_absent', 0) + 1

    def detect_deactivations(self, address, token_data):
        """
        Check if a token should be deactivated based on threshold changes.
        Returns (should_deactivate: bool, reason: str or None).
        """
        prev = self.state['tokens'].get(address)
        if not prev or not prev.get('active'):
            return False, None

        prev_metrics = prev.get('prev_metrics', {})
        thresholds = DEACTIVATION_THRESHOLDS

        # --- Immediate triggers ---

        # Rug ratio spike
        rug = token_data.get('rug_ratio', 0) or 0
        if rug > thresholds['rug_ratio_spike']:
            return True, f"rug_ratio_spike:{rug:.2f}>{thresholds['rug_ratio_spike']}"

        # Liquidity collapse
        liq = _first_present(token_data, 'liquidity', default=0) or 0
        prev_liq = prev_metrics.get('liquidity', 0)
        if prev_liq > 0 and liq > 0:
            liq_drop = 1 - (liq / prev_liq)
            if liq_drop > thresholds['liquidity_drop_pct']:
                return True, f"liq_drop:{liq_drop:.0%}>{thresholds['liquidity_drop_pct']:.0%}"

        # Smart money exit (was well-tracked, now gone)
        smart = token_data.get('smart_degen_count', 0) or 0
        prev_smart = prev_metrics.get('smart_degen_count', 0)
        if prev_smart >= 2 and smart <= thresholds['smart_money_exit']:
            return True, f"smart_money_exit:{prev_smart}->{smart}"

        # Wash trading newly detected
        wash = token_data.get('is_wash_trading', False)
        prev_wash = prev_metrics.get('is_wash_trading', False)
        if wash and not prev_wash:
            return True, "wash_trading_detected"

        # --- Gradual: natural retirement (absent too many cycles) ---
        # This is handled in retire_absent_tokens(), not here

        return False, None

    def retire_absent_tokens(self):
        """
        Deactivate tokens that have been absent for too many consecutive cycles.
        Returns list of (address, reason) tuples for newly retired tokens.
        """
        retired = []
        threshold = DEACTIVATION_THRESHOLDS['absent_cycles_retire']

        for addr, token_state in self.state['tokens'].items():
            if not token_state.get('active'):
                continue
            absent_count = token_state.get('consecutive_absent', 0)
            if absent_count >= threshold:
                token_state['active'] = False
                token_state['deactivation_reason'] = f"absent_{absent_count}_cycles"
                token_state['deactivated_at'] = datetime.now(timezone.utc).isoformat()
                retired.append((addr, token_state['deactivation_reason']))

        return retired

    def purge_stale(self):
        """
        Remove tokens not seen within the TTL window to prevent unbounded state growth.
        Returns count of purged tokens.
        """
        ttl_hours = DEACTIVATION_THRESHOLDS['state_ttl_hours']
        now = datetime.now(timezone.utc).timestamp()
        max_tokens = DEACTIVATION_THRESHOLDS['max_tracked_tokens']

        # First: TTL purge
        purged = 0
        to_remove = []
        for addr, ts in self.state['tokens'].items():
            last_seen_str = ts.get('last_seen', '')
            if not last_seen_str:
                continue
            try:
                last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                age_hours = (now - last_seen.timestamp()) / 3600
                if age_hours > ttl_hours:
                    to_remove.append(addr)
            except (ValueError, TypeError):
                continue

        for addr in to_remove:
            del self.state['tokens'][addr]
            purged += 1

        # Second: LRU eviction if over max
        if len(self.state['tokens']) > max_tokens:
            sorted_tokens = sorted(
                self.state['tokens'].items(),
                key=lambda x: x[1].get('last_seen', ''),
                reverse=False  # oldest first
            )
            excess = len(self.state['tokens']) - max_tokens
            for addr, _ in sorted_tokens[:excess]:
                del self.state['tokens'][addr]
                purged += 1

        return purged

    def get_active_tokens(self):
        """Return dict of address -> token_state for all active tokens."""
        return {addr: ts for addr, ts in self.state['tokens'].items() if ts.get('active')}

    def get_stats(self):
        """Return summary statistics about tracked tokens."""
        tokens = self.state['tokens']
        active = sum(1 for t in tokens.values() if t.get('active'))
        inactive = len(tokens) - active
        return {
            'total_tracked': len(tokens),
            'active': active,
            'inactive': inactive,
            'total_cycles': self.cycle_number - 1,
        }

def _resolve_gmgn_cli():
    """
    Find the gmgn-cli executable regardless of platform or install location.
    Priority: GMGN_CLI_PATH env var override -> PATH lookup (works for both
    gmgn-cli and gmgn-cli.cmd via shutil.which's PATHEXT handling on Windows,
    and the plain shim on Linux/macOS) -> error.
    """
    override = os.environ.get("GMGN_CLI_PATH")
    if override:
        return override

    found = shutil.which("gmgn-cli")
    if found:
        return found

    raise FileNotFoundError(
        "Could not find gmgn-cli on PATH. Either install it globally "
        "(npm install -g gmgn-cli) or set the GMGN_CLI_PATH environment "
        "variable to its full path."
    )

GMGN_CLI = _resolve_gmgn_cli()

def run_gmgn_cmd(args):
    """Run a gmgn-cli command and return parsed JSON."""
    cmd = [GMGN_CLI] + args + ["--raw"]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
        if result.returncode != 0:
            print(f"  [ERROR] gmgn-cli {' '.join(args[:3])}... failed: {stderr[:200]}")
            return None
        return json.loads(stdout)
    except json.JSONDecodeError:
        print(f"  [ERROR] Invalid JSON from gmgn-cli {' '.join(args[:3])}...")
        return None
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] gmgn-cli timed out")
        return None


def fetch_trending(interval="1h", limit=100):
    """Fetch trending tokens from GMGN."""
    print(f"Fetching {interval} trending (limit={limit})...")
    args = [
        "market", "trending",
        "--chain", "sol",
        "--interval", interval,
        "--limit", str(limit),
        "--order-by", "volume",
    ]
    # Add platform filters
    for p in FILTERS['platforms']:
        args += ["--platform", p]

    data = run_gmgn_cmd(args)
    if not data or data.get('code') != 0:
        print(f"  [ERROR] Failed to fetch trending: {data}")
        return []

    tokens = data.get('data', {}).get('rank', [])
    print(f"  Got {len(tokens)} tokens")
    return tokens


def fetch_signal(signal_types=None, limit=50):
    """Fetch smart money signals."""
    if signal_types is None:
        signal_types = [12, 13]  # Smart money buy + Platform call

    print(f"Fetching signals (types={signal_types})...")
    groups = json.dumps([{"signal_type": signal_types}])
    args = [
        "market", "signal",
        "--chain", "sol",
        "--groups", groups,
        "--raw",
    ]    

    data = run_gmgn_cmd(args)
    if not data:
        print(f"  [ERROR] Failed to fetch signals")
        return []

    # Signal endpoint returns a list directly
    signals = data if isinstance(data, list) else data.get('data', []) if isinstance(data, dict) else []
    print(f"  Got {len(signals)} signals")
    return signals


def fetch_trenches(token_types=None, limit=80):
    """Fetch new token launches from trenches."""
    if token_types is None:
        token_types = ["new_creation", "near_completion"]

    print(f"Fetching trenches (types={token_types})...")
    args = [
        "market", "trenches",
        "--chain", "sol",
        "--filter-preset", "smart-money",
        "--sort-by", "smart_degen_count",
        "--limit", str(limit),
        "--raw",
    ]
    for tt in token_types:
        args += ["--type", tt]
    for p in FILTERS['platforms']:
        args += ["--launchpad-platform", p]

    data = run_gmgn_cmd(args)
    if not data:
        print(f"  [ERROR] Failed to fetch trenches")
        return []

    # Trenches response structure: {code: 0, data: {new_creation: [...], pump: [...]}}
    resp_data = data.get('data', data) if isinstance(data, dict) else {}

    all_tokens = []
    for tt in token_types:
        key = "pump" if tt == "near_completion" else tt
        tokens = resp_data.get(key, []) if isinstance(resp_data, dict) else []
        for t in tokens:
            t['_endpoint'] = tt
            t['_timeframe'] = tt
        all_tokens.extend(tokens)
        print(f"  {tt}: {len(tokens)} tokens")

    return all_tokens


def fetch_token_detail(address):
    """Fetch detailed token info."""
    args = ["token", "info", "--chain", "sol", "--address", address]
    data = run_gmgn_cmd(args)
    if not data:
        print("  [WARN] empty result set for token info lookup")                
        return None    
    detail = data.get('pool', {})
    if not detail:
        print(f"  [WARN] token info returned empty for {address[:20]}... (lookup likely failed)")
        return None
    return detail


def get_age_hours(token):
    """
    Compute token age in hours from whichever timestamp field is present.
    GMGN's endpoints don't share a schema:
      - market trending  -> 'creation_timestamp' / 'open_timestamp'
      - market trenches  -> 'created_timestamp' / 'created_timestamp_us' (open_timestamp
                             is legitimately 0 pre-migration, not missing)
      - token info       -> can return an empty dict entirely on a failed lookup
    Returns None (age unknown) if nothing usable is found, rather than
    silently defaulting to the Unix epoch.
    """
    now = datetime.now(timezone.utc).timestamp()

    candidates = [
        token.get('open_timestamp') or None,       # trending / post-migration trenches
        token.get('created_timestamp') or None,     # trenches (seconds)
        token.get('creation_timestamp') or None,    # trending (fallback name)
    ]
    us = token.get('created_timestamp_us')
    if us:
        candidates.append(us / 1_000_000)

    ts = next((c for c in candidates if c), None)
    if ts is None:
        return None

    return (now - ts) / 3600


def quality_check(token):
    """
    Apply quality filters to a token.
    Returns (pass, reason) tuple.
    """
    f = FILTERS

    # --- Hard disqualifiers ---
    age_hours = get_age_hours(token)
    if age_hours is None:
        return False, "age_unknown"
    if age_hours > f['max_age_hours']:
        return False, f"age={age_hours:.1f}h>{f['max_age_hours']}h"

    rug_ratio = token.get('rug_ratio', 0) or 0
    if rug_ratio > f['max_rug_ratio']:
        return False, f"rug_ratio={rug_ratio:.2f}>{f['max_rug_ratio']}"

    if f['require_no_wash_trading'] and token.get('is_wash_trading', False):
        return False, "wash_trading=true"

    # SOL-specific safety
    if f['require_renounced_mint'] and token.get('renounced_mint', 0) != 1:
        return False, "mint_not_renounced"

    if f['require_renounced_freeze'] and token.get('renounced_freeze_account', 0) != 1:
        return False, "freeze_not_renounced"

    # --- Smart money ---
    smart_count = token.get('smart_degen_count', 0) or 0
    if smart_count < f['min_smart_degen_count']:
        return False, f"smart_degen={smart_count}<{f['min_smart_degen_count']}"

    # --- Safety thresholds ---
    top10 = token.get('top_10_holder_rate', 0) or 0
    if top10 > f['max_top10_holder_rate']:
        return False, f"top10={top10:.2f}>{f['max_top10_holder_rate']}"

    bundler = token.get('bundler_rate', 0) or 0
    if bundler > f['max_bundler_rate']:
        return False, f"bundler={bundler:.2f}>{f['max_bundler_rate']}"

    insider = token.get('rat_trader_amount_rate', 0) or 0
    if insider > f['max_insider_rate']:
        return False, f"insider={insider:.2f}>{f['max_insider_rate']}"

    dev_hold = token.get('dev_team_hold_rate', 0) or 0
    if dev_hold > f['max_dev_team_hold_rate']:
        return False, f"dev_hold={dev_hold:.2f}>{f['max_dev_team_hold_rate']}"

    # --- Liquidity & volume ---
    liq = token.get('liquidity', 0) or 0
    if liq < f['min_liquidity']:
        return False, f"liq={liq:.0f}<{f['min_liquidity']}"

    vol = token.get('volume', 0) or 0
    if vol < f['min_volume_1h']:
        return False, f"vol={vol:.0f}<{f['min_volume_1h']}"

    holders = token.get('holder_count', 0) or 0
    if holders < f['min_holder_count']:
        return False, f"holders={holders}<{f['min_holder_count']}"

    return True, "pass"


def score_token(token):
    """
    Score a token (0-100) based on multiple quality factors.
    Higher = better opportunity.
    """
    score = 0

    # Smart money (0-30 points)
    smart = token.get('smart_degen_count', 0) or 0
    score += min(30, smart * 3)

    # Renowned/KOL (0-15 points)
    renowned = token.get('renowned_count', 0) or 0
    score += min(15, renowned * 5)

    # Rug ratio inverse (0-20 points)
    rug = token.get('rug_ratio', 0) or 0
    score += max(0, 20 * (1 - rug / 0.3))

    # Liquidity (0-10 points)
    liq = token.get('liquidity', 0) or 0
    score += min(10, liq / 5000)

    # Volume (0-10 points)
    vol = token.get('volume', 0) or 0
    score += min(10, vol / 50000)

    # Top 10 holder concentration (0-10 points) — lower is better
    top10 = token.get('top_10_holder_rate', 0) or 0
    score += max(0, 10 * (1 - top10 / 0.5))

    # Creator status bonus (0-5 points)
    if token.get('creator_close', False):
        score += 5

    return min(100, int(score))


def evaluate_strategy_a(row):
    """
    Check an already-formatted watchlist row against STRATEGY_A criteria.
    Returns (passes: bool, reasons: list[str]) - reasons lists every failed
    condition (not just the first), since this is an analysis tag, not a
    gate that needs to short-circuit for speed.

    Operates on the row dict (post prev/volume_spike computation) rather
    than the raw token, so it reuses the same field mapping already done
    in format_watchlist_entry_legacy instead of re-deriving it.
    """
    sa = STRATEGY_A
    reasons = []

    if row['dex'] != sa['dex']:
        reasons.append(f"dex={row['dex']!r}!={sa['dex']!r}")

    if row['age_hours'] > sa['max_age_hours']:
        reasons.append(f"age={row['age_hours']:.2f}h>{sa['max_age_hours']}h")

    ranking = row['ranking'] or 0
    if ranking > sa['max_ranking'] or ranking == 0:
        reasons.append(f"ranking={ranking}>{sa['max_ranking']} (or unranked)")

    pc1h = row['priceChange1h'] or 0
    if pc1h < sa['min_price_change_1h']:
        reasons.append(f"priceChange1h={pc1h:.1f}<{sa['min_price_change_1h']}")

    pc5m = row['priceChange5m'] or 0
    if sa['min_price_change_5m_positive'] and pc5m <= 0:
        reasons.append(f"priceChange5m={pc5m:.2f}<=0")

    liq = row['liquidity'] or 0
    if liq < sa['min_liquidity']:
        reasons.append(f"liquidity={liq:.0f}<{sa['min_liquidity']}")

    vol = row['volume'] or 0
    if vol < sa['min_volume']:
        reasons.append(f"volume={vol:.0f}<{sa['min_volume']}")

    makers_inc = row['makers_increase']
    if makers_inc == '' or makers_inc < sa['min_makers_increase']:
        reasons.append(f"makers_increase={makers_inc!r}<{sa['min_makers_increase']} (unreliable proxy)")

    vol_spike = row['volume_spike']
    if vol_spike == '' or vol_spike < sa['min_volume_spike']:
        reasons.append(f"volume_spike={vol_spike!r}<{sa['min_volume_spike']}")

    return (len(reasons) == 0), reasons


def _first_present(token, *keys, default=0):
    """Try several field names in order (GMGN's schema differs by endpoint)."""
    for k in keys:
        v = token.get(k)
        if v is not None:
            return v
    return default


def load_previous_snapshot(path):
    """
    Read the watchlist CSV from the previous run (before it gets overwritten)
    so this run can compute prev_* / makers_increase / volume_spike deltas.
    Keyed by detailUrl since that embeds the token address. Returns {} if the
    file doesn't exist yet or is in an unrecognized (e.g. old GMGN-column) format.
    """
    prev = {}
    if not os.path.exists(path):
        return prev
    try:
        with open(path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                key = row.get('detailUrl')
                if not key:
                    continue
                try:
                    prev[key] = {
                        'makers': float(row.get('makers', 0) or 0),
                        'volume': float(row.get('volume', 0) or 0),
                        'ranking': float(row.get('ranking', 0) or 0),
                        'price': float(row.get('price', 0) or 0),
                        'liquidity': float(row.get('liquidity', 0) or 0),
                    }
                except ValueError:
                    continue
    except Exception as e:
        print(f"  [WARN] Could not read previous snapshot for deltas: {e}")
    return prev


def get_pool_address(token):
    """
    Extract the pool address from whichever schema location it lives in.
    Returns None if not present (e.g. 'trending'-sourced tokens, whose
    payload has no pool address field at all).
    """
    
    if token.get('pool_address'):
        return token['pool_address']
    if token.get('biggest_pool_address'):
        return token['biggest_pool_address']
    pool = token.get('pool') or {}
    return pool.get('pool_address') or pool.get('address')


def enrich_missing_pool_addresses(passed):
    """
    For tokens whose source endpoint doesn't carry a pool address
    ('trending'), fetch it via a token-detail lookup. Only run against the
    already-filtered passed list (typically single digits), not the full
    collected pool - keeps the extra API cost negligible.
    """
    for token, source in passed:
        if get_pool_address(token) is not None:
            continue
        addr = token.get('address', '')
        if not addr:
            continue
        detail = fetch_token_detail(addr)        
        if detail:
            pool_addr = get_pool_address(detail)
            if pool_addr:
                token['pool_address'] = pool_addr
        time.sleep(0.5)  # rate-limit courtesy, same as the signal-detail fetch


def apply_signal_metadata(token, detail=None):
    """Mark a token as coming from the signal endpoint and merge detail data."""
    if detail is not None:
        merged = dict(token)
        merged.update(detail)
        merged['_endpoint'] = 'signal'
        merged['_timeframe'] = 'signal'
        return merged

    token['_endpoint'] = 'signal'
    token['_timeframe'] = 'signal'
    return token


def format_watchlist_entry_legacy(token, source, prev_lookup, now):
    """
    Format a token to match the older extract_watchlist.py / DexScreener-era
    CSV schema (watchlist_updated_micro.csv), rather than the richer GMGN
    column set. Known gaps vs. the original DexScreener source, since GMGN
    doesn't carry 1:1 equivalents for every field:
      - 'makers' (unique traders in window) has no GMGN equivalent; using
        holder_count as the closest proxy — NOT the same metric.
      - priceChange6h/24h aren't present on GMGN's trending/trenches/signal
        payloads, only on a nested price sub-object from token detail
        lookups, so they're left blank rather than guessed.
      - 'dex' passes through GMGN's raw exchange code (e.g. 'pump_amm')
        rather than DexScreener's display name (e.g. 'PumpSwap').
      - detailUrl now uses the pool address (matching DexScreener's URL
        convention) wherever GMGN's payload provides one. 'trending'-sourced
        tokens don't carry a pool address in that endpoint's response, so
        those get backfilled via enrich_missing_pool_addresses() before
        formatting — falls back to the token/mint address only if that
        lookup itself fails.
    """
    age_hours = get_age_hours(token)
    if age_hours is None:
        age_hours = 0
    age_str = f"{int(age_hours * 60)}m" if age_hours < 1 else f"{age_hours:.1f}h"

    addr = (get_pool_address(token))
    detail_url = f"/solana/{addr}" if addr else ''

    buys = _first_present(token, 'buys', 'buys_24h', default=0) or 0
    sells = _first_present(token, 'sells', 'sells_24h', default=0) or 0
    price = _first_present(token, 'price', default=0) or 0
    volume = _first_present(token, 'volume', 'volume_24h', default=0) or 0
    liquidity = _first_present(token, 'liquidity', default=0) or 0
    market_cap = _first_present(token, 'market_cap', 'usd_market_cap', default=0) or 0
    ranking = token.get('rank', 0) or 0
    makers = token.get('holder_count', 0) or 0  # approximation, see docstring

    row = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'endpoint': token.get('_endpoint', source),
        'timeframe': token.get('_timeframe', source),
        'ranking': ranking,
        'tokenSymbol': token.get('symbol', ''),
        'tokenName': token.get('name', ''),
        'chain': 'SOL',
        'dex': token.get('exchange', ''),
        'price': price,
        'age': age_str,
        'transactions': buys + sells,
        'volume': volume,
        'makers': makers,
        'priceChange5m': token.get('price_change_percent5m', 0) or 0,
        'priceChange1h': token.get('price_change_percent1h', 0) or 0,
        'priceChange6h': '',   # not available from GMGN trending/trenches/signal
        'priceChange24h': '',  # not available from GMGN trending/trenches/signal
        'liquidity': liquidity,
        'marketCap': market_cap,
        'detailUrl': detail_url,
        'age_hours': round(age_hours, 2),
    }

    prev = prev_lookup.get(detail_url)
    if prev:
        row['prev_makers'] = prev['makers']
        row['prev_volume'] = prev['volume']
        row['prev_ranking'] = prev['ranking']
        row['prev_price'] = prev['price']
        row['prev_liquidity'] = prev['liquidity']
        row['makers_increase'] = (makers / prev['makers']) if prev['makers'] else ''
        row['volume_spike'] = (volume / prev['volume']) if prev['volume'] else ''
    else:
        # No prior snapshot for this token (new to the watchlist this run) -
        # leaving these blank rather than fabricating a 0 or a 1.0x ratio.
        row['prev_makers'] = ''
        row['prev_volume'] = ''
        row['prev_ranking'] = ''
        row['prev_price'] = ''
        row['prev_liquidity'] = ''
        row['makers_increase'] = ''
        row['volume_spike'] = ''

    # --- Strategy A advisory tag (does NOT gate live collection - see
    # STRATEGY_A config block for rationale) ---
    passes_sa, sa_reasons = evaluate_strategy_a(row)
    row['passes_strategy_a'] = passes_sa
    row['strategy_a_fail_reasons'] = ';'.join(sa_reasons)

    # --- GMGN enrichment columns (appended after the legacy schema, for
    # extended_watchlist_history to pick up by name) ---
    row['score'] = score_token(token)
    row['smart_degen_count'] = token.get('smart_degen_count', 0) or 0
    row['renowned_count'] = token.get('renowned_count', 0) or 0
    row['rug_ratio'] = token.get('rug_ratio', 0) or 0
    row['bundler_rate'] = token.get('bundler_rate', 0) or 0
    row['insider_rate'] = token.get('rat_trader_amount_rate', 0) or 0
    row['top10_holder_rate'] = token.get('top_10_holder_rate', 0) or 0
    row['dev_team_hold_rate'] = token.get('dev_team_hold_rate', 0) or 0
    row['is_wash_trading'] = token.get('is_wash_trading', False)
    row['renounced_mint'] = token.get('renounced_mint', 0)
    row['renounced_freeze'] = token.get('renounced_freeze_account', 0)
    row['creator_status'] = token.get('creator_token_status', '')
    row['sniper_count'] = token.get('sniper_count', 0) or 0
    row['bot_degen_count'] = token.get('bot_degen_count', 0) or 0
    row['burn_status'] = token.get('burn_status', '')
    row['launchpad'] = token.get('launchpad_platform', '')

    # --- Cycle tracking columns ---
    row['is_active'] = True  # will be overridden by caller
    row['deactivation_reason'] = ''
    row['cycles_tracked'] = 0
    row['peak_score'] = 0

    return row


def format_watchlist_entry(token, source="trending"):
    """Format a token for the watchlist CSV."""
    now = datetime.now(timezone.utc)
    age_hours = get_age_hours(token)

    if age_hours < 1:
        age_str = f"{int(age_hours * 60)}m"
    else:
        age_str = f"{age_hours:.1f}h"

    return {
        'timestamp': now.isoformat(),
        'pool_address': token.get('address', ''),
        'token_name': token.get('name', ''),
        'token_symbol': token.get('symbol', ''),
        'chain': 'solana',
        'dex': token.get('exchange', 'pump_amm'),
        'price_usd': token.get('price', 0),
        'market_cap': token.get('market_cap', 0),
        'liquidity': token.get('liquidity', 0),
        'volume_1h': token.get('volume', 0),
        'price_change_1h': token.get('price_change_percent1h', 0),
        'price_change_5m': token.get('price_change_percent5m', 0),
        'holder_count': token.get('holder_count', 0),
        'smart_degen_count': token.get('smart_degen_count', 0),
        'renowned_count': token.get('renowned_count', 0),
        'rug_ratio': token.get('rug_ratio', 0),
        'bundler_rate': token.get('bundler_rate', 0),
        'insider_rate': token.get('rat_trader_amount_rate', 0),
        'top10_holder_rate': token.get('top_10_holder_rate', 0),
        'dev_team_hold_rate': token.get('dev_team_hold_rate', 0),
        'is_wash_trading': token.get('is_wash_trading', False),
        'renounced_mint': token.get('renounced_mint', 0),
        'renounced_freeze': token.get('renounced_freeze_account', 0),
        'creator_status': token.get('creator_token_status', ''),
        'sniper_count': token.get('sniper_count', 0),
        'bot_degen_count': token.get('bot_degen_count', 0),
        'burn_status': token.get('burn_status', ''),
        'launchpad': token.get('launchpad_platform', ''),
        'age_hours': round(age_hours, 2),
        'age_str': age_str,
        'score': score_token(token),
        'source': source,
        'quality_reason': '',
    }


def generate_watchlist():
    """Main watchlist generation pipeline."""
    print("=" * 70)
    print("GMGN WATCHLIST GENERATOR")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # Initialize state manager
    state = WatchlistStateManager()
    print(f"State: cycle #{state.cycle_number}, "
          f"tracking {state.state['meta'].get('total_cycles', 0)} prior cycles")

    all_tokens = {}  # address -> token data

    # 1. Fetch trending (multiple intervals for coverage)
    for interval in ["1m", "5m", "1h"]:
        tokens = fetch_trending(interval=interval, limit=100)
        for t in tokens:
            addr = t.get('address', '')
            if addr and addr not in all_tokens:
                t['_endpoint'] = 'trending'
                t['_timeframe'] = interval
                all_tokens[addr] = t
        time.sleep(1)  # Rate limit courtesy

    # 2. Fetch smart money signals
    signals = fetch_signal(signal_types=[12, 13])  # Smart money buy + Platform call
    signal_addresses = set()
    for s in signals:
        addr = s.get('token_address', '')
        if addr:
            signal_addresses.add(addr)
            existing = all_tokens.get(addr)
            if existing is None:
                detail = fetch_token_detail(addr)
                if detail:
                    all_tokens[addr] = apply_signal_metadata({}, detail)
                else:
                    signal_token = dict(s)
                    all_tokens[addr] = apply_signal_metadata(signal_token)
                # print(detail if detail else s)
                time.sleep(0.5)
            else:
                all_tokens[addr] = apply_signal_metadata(existing)

    # 3. Fetch trenches (new launches)
    trenches = fetch_trenches(token_types=["new_creation", "near_completion"])
    for t in trenches:
        addr = t.get('address', '')
        if addr and addr not in all_tokens:
            all_tokens[addr] = t

    print(f"\nTotal unique tokens collected: {len(all_tokens)}")

    # 4. Quality check and score
    print("\n--- Quality Check ---")
    passed = []  # list of (token, source) tuples
    failed_reasons = {}
    rejected_sample = []  # stratified sample for baseline comparison
    rejected_by_reason = {}  # reason -> list of tokens
    for addr, token in all_tokens.items():
        ok, reason = quality_check(token)
        if ok:
            source = "signal" if (addr in signal_addresses or token.get('_endpoint') == 'signal') else "trending"
            passed.append((token, source))
        else:
            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
            # Track rejected tokens by top failure reason for stratified sampling
            top_reason = reason.split('=')[0].split('(')[0]  # normalize (e.g. 'rug_ratio', 'age')
            rejected_by_reason.setdefault(top_reason, []).append((token, reason))

    # Build stratified sample: up to 2 per failure reason, ~10-15 total
    import random
    for reason_key, tokens in rejected_by_reason.items():
        sample_size = min(2, len(tokens))
        rejected_sample.extend(random.sample(tokens, sample_size))
    random.shuffle(rejected_sample)
    rejected_sample = rejected_sample[:15]

    print(f"  Passed: {len(passed)}")
    print(f"  Failed: {sum(failed_reasons.values())}")
    for reason, count in sorted(failed_reasons.items(), key=lambda x: -x[1])[:10]:
        print(f"    {reason}: {count}")
    print(f"  Rejected sample: {len(rejected_sample)}")

    # 5. Deactivation detection
    print("\n--- Deactivation Check ---")
    deactivations = []
    passed_addresses = set()
    for token, source in passed:
        addr = token.get('address', '') or get_pool_address(token) or ''
        if not addr:
            continue
        passed_addresses.add(addr)

        should_deactivate, reason = state.detect_deactivations(addr, token)
        if should_deactivate:
            deactivations.append((addr, token.get('symbol', ''), reason))
            state.update_token(addr, token, active=False, deactivation_reason=reason)
        else:
            state.update_token(addr, token, active=True)

    # Mark tokens from previous cycle that are no longer in this cycle
    absent_tokens = []
    for addr in list(state.state['tokens'].keys()):
        if addr not in passed_addresses and state.state['tokens'][addr].get('active'):
            state.mark_absent(addr)
            absent_count = state.state['tokens'][addr].get('consecutive_absent', 0)
            sym = state.state['tokens'][addr].get('prev_metrics', {}).get('symbol', addr[:8])
            if absent_count > 0:
                absent_tokens.append((addr, sym, absent_count))

    # Retire tokens absent too many cycles
    retired = state.retire_absent_tokens()

    # Purge stale state
    purged = state.purge_stale()

    # Report
    if deactivations:
        print(f"  Deactivated: {len(deactivations)}")
        for addr, sym, reason in deactivations[:5]:
            print(f"    {sym or addr[:12]}: {reason}")
    if retired:
        print(f"  Retired (absent): {len(retired)}")
        for addr, reason in retired[:5]:
            print(f"    {addr[:12]}: {reason}")
    if absent_tokens:
        print(f"  Absent (tracking): {len(absent_tokens)}")
    if purged:
        print(f"  Purged stale: {purged}")
    if not deactivations and not retired:
        print("  No deactivations this cycle")

    # 6. Sort by score
    passed.sort(key=lambda pair: score_token(pair[0]), reverse=True)

    # 7. Write watchlist CSV BEFORE printing (print may crash on Unicode)
    now = datetime.now(timezone.utc)
    live_file = os.path.join(WATCHLIST_DIR, "watchlist_updated_gmgn.csv")
    prev_lookup = load_previous_snapshot(live_file)  # read BEFORE we overwrite it

    enrich_missing_pool_addresses(passed)  # backfill pool address for 'trending' rows

    rows = []
    for token, source in passed:
        row = format_watchlist_entry_legacy(token, source, prev_lookup, now)
        # Overlay cycle tracking data
        addr = token.get('address', '') or get_pool_address(token) or ''
        token_state = state.get_token_state(addr) if addr else None
        if token_state:
            row['is_active'] = token_state.get('active', True)
            row['deactivation_reason'] = token_state.get('deactivation_reason', '') or ''
            row['cycles_tracked'] = state.cycle_number - (token_state.get('last_seen_cycle', state.cycle_number) - token_state.get('consecutive_absent', 0)) + 1
            row['peak_score'] = token_state.get('peak_score', score_token(token))
        else:
            row['is_active'] = True
            row['deactivation_reason'] = ''
            row['cycles_tracked'] = 1
            row['peak_score'] = score_token(token)
        rows.append(row)

    timestamp_str = datetime.now().strftime('%Y_%m_%d_%H%M')
    watchlist_file = os.path.join(OUTPUT_DIR, f"watchlist_gmgn_{timestamp_str}.csv")

    # on production we save only the live watchlist, not the timestamped one
    """ if rows:
        fieldnames = list(rows[0].keys())
        try:
            with open(watchlist_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"\nWatchlist saved: {watchlist_file} ({len(rows)} tokens)")
        except Exception as e:
            print(f"  [ERROR] Could not write watchlist: {e}") """

    # 8. Also write to the live watchlist location
    try:
        if rows:
            fieldnames = list(rows[0].keys())
            with open(live_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Live watchlist updated: {live_file}")
    except Exception as e:
        print(f"  [WARN] Could not write live watchlist: {e}")

    # 8b. Write rejected tokens sample for baseline comparison
    if rejected_sample:
        rejected_file = os.path.join(OUTPUT_DIR, f"watchlist_rejected_{timestamp_str}.csv")
        rejected_rows = []
        for token, reason in rejected_sample:
            age_hours = get_age_hours(token)
            try:
                r_score = score_token(token)
            except (TypeError, ValueError):
                r_score = 0
            rejected_rows.append({
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': token.get('symbol', ''),
                'name': token.get('name', ''),
                'address': token.get('address', ''),
                'price': _first_present(token, 'price', default=0) or 0,
                'volume': _first_present(token, 'volume', default=0) or 0,
                'liquidity': _first_present(token, 'liquidity', default=0) or 0,
                'market_cap': _first_present(token, 'market_cap', 'usd_market_cap', default=0) or 0,
                'holder_count': token.get('holder_count', 0) or 0,
                'score': r_score,
                'rug_ratio': token.get('rug_ratio', 0) or 0,
                'smart_degen_count': token.get('smart_degen_count', 0) or 0,
                'renowned_count': token.get('renowned_count', 0) or 0,
                'top_10_holder_rate': token.get('top_10_holder_rate', 0) or 0,
                'bundler_rate': token.get('bundler_rate', 0) or 0,
                'insider_rate': token.get('rat_trader_amount_rate', 0) or 0,
                'dev_team_hold_rate': token.get('dev_team_hold_rate', 0) or 0,
                'is_wash_trading': token.get('is_wash_trading', False),
                'renounced_mint': token.get('renounced_mint', 0),
                'renounced_freeze': token.get('renounced_freeze_account', 0),
                'age_hours': round(age_hours, 2) if age_hours else '',
                'failure_reason': reason,
            })
        try:
            fieldnames_r = list(rejected_rows[0].keys())
            with open(rejected_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames_r)
                writer.writeheader()
                writer.writerows(rejected_rows)
            print(f"Rejected sample saved: {rejected_file} ({len(rejected_rows)} tokens)")
        except Exception as e:
            print(f"  [WARN] Could not write rejected sample: {e}")

    # 9. Save state
    state.save()

    # 10. Print top results (may crash on Unicode — CSV is already saved)
    print(f"\n--- Top {min(20, len(passed))} Tokens ---")
    print(f"{'#':>3} {'Symbol':>8} {'Score':>5} {'Price':>12} {'MCap':>10} {'Liq':>8} "
          f"{'Vol1h':>8} {'1h%':>7} {'SM':>3} {'Rug':>5} {'Source':>8}")
    print("-" * 95)
    for i, (token, source) in enumerate(passed[:20], 1):
        price = _first_present(token, 'price', default=0) or 0
        mcap = _first_present(token, 'market_cap', 'usd_market_cap', default=0) or 0
        liq = _first_present(token, 'liquidity', default=0) or 0
        vol = _first_present(token, 'volume', 'volume_24h', default=0) or 0
        pct1h = token.get('price_change_percent1h', 0) or 0
        smart = token.get('smart_degen_count', 0) or 0
        rug = token.get('rug_ratio', 0) or 0
        try:
            print(f"{i:>3} {token.get('symbol',''):>8} {score_token(token):>5} "
                  f"${price:>10.6f} ${mcap:>8,.0f} ${liq:>7,.0f} "
                  f"${vol:>7,.0f} {pct1h:>+6.1f}% "
                  f"{smart:>3} {rug:>5.2f} {source:>8}")
        except UnicodeEncodeError:
            print(f"{i:>3} {'[?]':>8} {score_token(token):>5} "
                  f"${price:>10.6f} ${mcap:>8,.0f} ${liq:>7,.0f} "
                  f"${vol:>7,.0f} {pct1h:>+6.1f}% "
                  f"{smart:>3} {rug:>5.2f} {source:>8}")

    # 11. Summary stats
    stats = state.get_stats()
    print(f"\n--- State Summary ---")
    print(f"  Active: {stats['active']} | Inactive: {stats['inactive']} | Total tracked: {stats['total_tracked']}")
    print(f"  Cycle: #{stats['total_cycles']}")
    print(f"\n--- Summary ---")
    print(f"  Total collected: {len(all_tokens)}")
    print(f"  Passed quality: {len(passed)}")
    if passed:
        avg_score = sum(score_token(t) for t, _ in passed) / len(passed)
        avg_smart = sum(t.get('smart_degen_count', 0) or 0 for t, _ in passed) / len(passed)
        avg_rug = sum(t.get('rug_ratio', 0) or 0 for t, _ in passed) / len(passed)
        signal_count = sum(1 for _, source in passed if source == 'signal')
        print(f"  Avg score: {avg_score:.1f}")
        print(f"  Avg smart degens: {avg_smart:.1f}")
        print(f"  Avg rug ratio: {avg_rug:.3f}")
        print(f"  Signal tokens: {signal_count}")

    # 12. Append eval log line (script writes this, not the cron agent — avoids UTF-16 encoding issue)
    """ eval_log_path = os.path.join(os.path.dirname(OUTPUT_DIR), 'memory', 'watchlist-eval-log.md')
    try:
        now_local = datetime.now().strftime('%Y-%m-%d %H:%M')
        retired_count = len(retired)
        errors = 'none'
        log_line = f"{now_local} | cycle #{state.cycle_number} | collected {len(all_tokens)} | passed {len(passed)} | active {stats['active']} | retired {retired_count} | errors: {errors}\n"
        with open(eval_log_path, 'a', encoding='utf-8') as f:
            f.write(log_line)
    except Exception as e:
        print(f"  [WARN] Could not write eval log: {e}") """

    return rows


if __name__ == '__main__':
    load_dotenv()  # Load .env from script directory or CWD
    import argparse
    parser = argparse.ArgumentParser(description='GMGN Watchlist Generator')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Default: generate watchlist
    gen_parser = subparsers.add_parser('generate', help='Generate watchlist (default)')
    gen_parser.add_argument('--live', action='store_true', help='Live mode for cron')
    gen_parser.add_argument('--signal', action='store_true', help='Include signal fetch')
    gen_parser.add_argument('--backtest', action='store_true', help='Backtest mode')

    # Status: show state summary
    subparsers.add_parser('status', help='Show watchlist state summary')

    # Active: list active tokens
    active_parser = subparsers.add_parser('active', help='List active tokens')
    active_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # History: show token history
    hist_parser = subparsers.add_parser('history', help='Show token tracking history')
    hist_parser.add_argument('address', help='Token address')

    # Deactivate: manually deactivate a token
    deact_parser = subparsers.add_parser('deactivate', help='Manually deactivate a token')
    deact_parser.add_argument('address', help='Token address')
    deact_parser.add_argument('--reason', default='manual', help='Deactivation reason')

    # Purge: clean stale state
    subparsers.add_parser('purge', help='Purge stale tokens from state')

    # Export: dump active tokens for production DB import
    export_parser = subparsers.add_parser('export', help='Export active tokens for production')
    export_parser.add_argument('--format', choices=['csv', 'json', 'sql'], default='csv', help='Output format')
    export_parser.add_argument('--output', help='Output file path')

    args = parser.parse_args()

    # Default to generate if no subcommand
    if args.command is None:
        args.command = 'generate'
        args.live = False
        args.signal = False
        args.backtest = False

    if args.command == 'generate':
        generate_watchlist()

    elif args.command == 'status':
        state = WatchlistStateManager()
        stats = state.get_stats()
        print(f"Watchlist State Summary")
        print(f"  Cycle: #{stats['total_cycles']}")
        print(f"  Active tokens: {stats['active']}")
        print(f"  Inactive tokens: {stats['inactive']}")
        print(f"  Total tracked: {stats['total_tracked']}")
        print(f"  Last run: {state.state['meta'].get('last_run', 'never')}")

    elif args.command == 'active':
        state = WatchlistStateManager()
        active = state.get_active_tokens()
        if args.json:
            import json as json_mod
            print(json_mod.dumps(active, indent=2))
        else:
            if not active:
                print("No active tokens.")
            else:
                print(f"{'Address':<44} {'Score':>5} {'Last Seen':>20} {'Cycles':>6} {'Reason'}")
                print("-" * 100)
                for addr, ts in sorted(active.items(), key=lambda x: x[1].get('peak_score', 0), reverse=True):
                    print(f"{addr:<44} {ts.get('peak_score', 0):>5} {ts.get('last_seen', '?'):>20} "
                          f"{state.cycle_number - ts.get('last_seen_cycle', state.cycle_number) + 1:>6} "
                          f"{ts.get('deactivation_reason', '') or ''}")

    elif args.command == 'history':
        state = WatchlistStateManager()
        ts = state.get_token_state(args.address)
        if not ts:
            print(f"Token {args.address} not found in state.")
        else:
            import json as json_mod
            print(json_mod.dumps(ts, indent=2))

    elif args.command == 'deactivate':
        state = WatchlistStateManager()
        ts = state.get_token_state(args.address)
        if not ts:
            print(f"Token {args.address} not found in state. Adding as deactivated.")
            state.state['tokens'][args.address] = {
                'first_seen': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'last_seen_cycle': state.cycle_number,
                'consecutive_absent': 0,
                'peak_score': 0,
                'prev_metrics': {},
                'active': False,
                'deactivation_reason': args.reason,
                'deactivated_at': datetime.now(timezone.utc).isoformat(),
            }
        else:
            ts['active'] = False
            ts['deactivation_reason'] = args.reason
            ts['deactivated_at'] = datetime.now(timezone.utc).isoformat()
        state.save()
        print(f"Token {args.address} deactivated: {args.reason}")

    elif args.command == 'purge':
        state = WatchlistStateManager()
        purged = state.purge_stale()
        state.save()
        print(f"Purged {purged} stale tokens.")
        stats = state.get_stats()
        print(f"Remaining: {stats['total_tracked']} tracked ({stats['active']} active)")

    elif args.command == 'export':
        state = WatchlistStateManager()
        active = state.get_active_tokens()

        if args.format == 'json':
            import json as json_mod
            output = json_mod.dumps(active, indent=2)
        elif args.format == 'csv':
            import io
            buf = io.StringIO()
            if active:
                writer = csv.DictWriter(buf, fieldnames=['address'] + list(next(iter(active.values())).keys()))
                writer.writeheader()
                for addr, ts in active.items():
                    row = {'address': addr}
                    row.update(ts)
                    writer.writerow(row)
            output = buf.getvalue()
        elif args.format == 'sql':
            lines = []
            for addr, ts in active.items():
                metrics = json.dumps(ts.get('prev_metrics', {}))
                lines.append(
                    f"INSERT INTO watchlist_tokens (address, first_seen, last_seen, peak_score, active, metrics) "
                    f"VALUES ('{addr}', '{ts.get('first_seen', '')}', '{ts.get('last_seen', '')}', "
                    f"{ts.get('peak_score', 0)}, true, '{metrics}'::jsonb) "
                    f"ON CONFLICT (address) DO UPDATE SET last_seen = EXCLUDED.last_seen, "
                    f"peak_score = GREATEST(watchlist_tokens.peak_score, EXCLUDED.peak_score), "
                    f"metrics = EXCLUDED.metrics;"
                )
            output = '\n'.join(lines)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"Exported {len(active)} active tokens to {args.output}")
        else:
            print(output)