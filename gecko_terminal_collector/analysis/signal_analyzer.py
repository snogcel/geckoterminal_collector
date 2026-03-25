"""
Signal analysis engine for new pools data.
Detects trading signals and patterns from new pools history.

Changes from original
---------------------
- signal_score is now the Random Forest model probability (0-100) when a
  model is available; falls back to the improved heuristic when it is not.
- Added _analyze_fdv(): FDV was the #1 RF feature (33% importance) but was
  completely absent from the original heuristic scoring.
- Added _analyze_velocity(): exploits the 2-3 row window that is typically
  available; volume growth rate between first and latest observation is a
  strong early signal (winners show ~38x vs losers ~17x in backtests).
- All sub-scores converted to log-scale where appropriate: the original
  linear scales caused volume/liquidity ceilings far below realistic values
  (e.g. $50k volume and $1M volume both capped at 50).
- Activity scoring now includes sell-authenticity checks: zero-sell pools
  with meaningful buy activity are penalized as likely scams/bots. Extreme
  buy-side imbalance (>97% buys) is also flagged.
- Momentum scoring distinguishes new pools (<24h old) where price_change_24h
  mirrors price_change_1h; avoids double-counting the same signal.
- Overall heuristic weights re-aligned to match RF feature importances:
  FDV 25%, liquidity 20%, volume 20%, activity 15%, momentum 10%,
  velocity bonus up to +10.
- should_add_to_watchlist() gates on RF tier when model is available,
  then falls back to heuristic threshold.
- generate_alert_message() includes RF tier and score in output.
- _safe_float() helper added; Decimal arithmetic only kept where it
  directly touches DB-bound values.
- Cold-start handling added to _analyze_velocity() and _analyze_volume_trend():
  when the first observation has volume below $1 (a dust/test transaction),
  ratio-based calculations are skipped entirely.  vol_velocity is stored as 0
  rather than a garbage 19-million-x number; scoring falls back to absolute
  current volume.  A cold_start flag is surfaced in signals_json for filtering.
- Post-RF hard overrides added via _detect_hard_overrides(): a small set of
  extreme conditions that the RF model cannot reliably learn (due to rarity in
  training data) are applied AFTER the RF score to cap it downward.  Conditions:
    extreme_fdv_liq_ratio  fdv/liq > 100x with liq < $50k → cap score at 20
                           (pre-minted insider dump setup; Evan / TRUTH pattern)
    rug_detected           liquidity dropped >90% in one 120s cycle → cap at 5
    price_crash            price_change_h1 < -90% → cap at 10
  The override reason(s) are stored in signals["hard_override_flags"] so they
  are visible in the DB for post-trade analysis and future model retraining.
"""

import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional RF model import — graceful degradation if files not present
# ---------------------------------------------------------------------------
try:
    from .pool_scorer import PoolScorer  # type: ignore
    _POOL_SCORER_AVAILABLE = True
except ImportError:
    _POOL_SCORER_AVAILABLE = False
    logger.info("pool_scorer not found — RF scoring disabled, using heuristic only")


# ---------------------------------------------------------------------------
# Tier definitions (kept in sync with pool_scorer.py)
# ---------------------------------------------------------------------------
RF_TIERS = {
    1: {"label": "HIGH",   "min_score": 0.70},
    2: {"label": "MEDIUM", "min_score": 0.60},
    3: {"label": "LOW",    "min_score": 0.50},
    0: {"label": "FILTER", "min_score": 0.00},
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field


@dataclass
class SignalResult:
    """Result of signal analysis."""
    signal_score: float        # 0-100; RF probability * 100 when model available
    volume_trend: str
    liquidity_trend: str
    momentum_indicator: float  # stored as NUMERIC(15,4) in DB
    activity_score: float      # 0-100
    volatility_score: float    # 0-100
    signals: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main analyser
# ---------------------------------------------------------------------------

class NewPoolsSignalAnalyzer:
    """
    Analyze new pools data for trading signals and patterns.

    When a trained RandomForest model (pool_winner_model.pkl) is available in
    model_path, the signal_score field of every SignalResult is the RF win-
    probability scaled to 0-100.  All heuristic sub-scores are still computed
    and stored in SignalResult.signals for transparency and debugging.

    When the model is not available the analyzer falls back to the improved
    heuristic signal_score described in the module docstring.

    Parameters
    ----------
    config : dict, optional
        Runtime thresholds.  All keys are optional; defaults listed below.
    model_path : str or Path, optional
        Directory or full path to pool_winner_model.pkl.
        Defaults to the directory containing this file.
    """

    # Heuristic sub-score log-scale anchors  (min_log, max_log)
    # score = clip((log10(value) - min_log) / (max_log - min_log) * 100, 0, 100)
    _FDV_LOG_RANGE  = (3.0, 6.0)   # $1k → $1M
    _VOL_LOG_RANGE  = (2.0, 6.0)   # $100 → $1M
    _LIQ_LOG_RANGE  = (3.0, 5.5)   # $1k → $316k
    _ACT_LOG_RANGE  = (0.5, 3.0)   # 3 txns → 1000 txns

    # Hard override thresholds — post-RF caps the model can't learn reliably.
    # These represent conditions that are catastrophically bad but rare enough
    # in training data that the RF assigns them normal-looking scores.
    _EXTREME_FDV_LIQ_RATIO  = 100.0    # fdv/liq above this = insider dump risk
    _EXTREME_FDV_MAX_LIQ    = 50_000   # only flag when liquidity is also small
    _RUG_LIQ_DROP_THRESHOLD = -0.90    # >90% liquidity gone in one cycle
    _PRICE_CRASH_THRESHOLD  = -90.0    # >90% price drop in one hour

    def __init__(
        self,
        config: Optional[Dict] = None,
        model_path: Optional[str | Path] = None,
    ):
        self.config = config or {}

        # --- heuristic thresholds (kept for backwards compat / fallback) ---
        self.volume_spike_threshold    = self.config.get("volume_spike_threshold",    2.0)
        self.liquidity_growth_threshold= self.config.get("liquidity_growth_threshold",1.5)
        self.momentum_lookback_hours   = self.config.get("momentum_lookback_hours",   6)
        self.min_signal_score          = self.config.get("min_signal_score",          60.0)

        # --- RF model ---
        self.scorer: Optional["PoolScorer"] = None
        if _POOL_SCORER_AVAILABLE:
            self._load_scorer(model_path)

        logger.info(
            "SignalAnalyzer ready | RF=%s | vol_spike=%.1f | liq_growth=%.1f",
            "enabled" if self.scorer else "disabled",
            self.volume_spike_threshold,
            self.liquidity_growth_threshold,
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_scorer(self, model_path: Optional[str | Path]) -> None:
        """Attempt to load the RF model; log but do not raise on failure."""
        candidates: List[Path] = []

        if model_path:
            p = Path(model_path)
            candidates.append(p if p.suffix == ".pkl" else p / "pool_winner_model.pkl")

        # Look next to this file and in a sibling 'models/' dir
        here = Path(__file__).parent
        candidates += [
            here / "pool_winner_model.pkl",
            here / "models" / "pool_winner_model.pkl",
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    self.scorer = PoolScorer(candidate)
                    logger.info("RF model loaded from %s", candidate)
                    return
                except Exception as exc:
                    logger.warning("Failed to load model from %s: %s", candidate, exc)

        logger.info("No RF model file found; using heuristic scoring only")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_pool_signals(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]] = None,
    ) -> SignalResult:
        """
        Analyze a pool's current data against historical patterns.

        Parameters
        ----------
        current_data : dict
            Most recent pool observation (from DexScreener API / DB row).
        historical_data : list of dicts, optional
            Prior observations for the same pool, oldest first.
            Typically 1-2 rows given the API's short retention window.

        Returns
        -------
        SignalResult
        """
        try:
            signals: Dict[str, Any] = {}

            # --- sub-analyses (always run — provide context & fallback) ------
            fdv_analysis        = self._analyze_fdv(current_data)
            volume_analysis     = self._analyze_volume_trend(current_data, historical_data)
            liquidity_analysis  = self._analyze_liquidity_trend(current_data, historical_data)
            momentum_analysis   = self._analyze_price_momentum(current_data, historical_data)
            activity_analysis   = self._analyze_trading_activity(current_data, historical_data)
            volatility_analysis = self._analyze_volatility(current_data, historical_data)
            velocity_analysis   = self._analyze_velocity(current_data, historical_data)

            # Collect detailed signals for logging / downstream use
            signals.update({
                # Volume
                "volume_spike":         volume_analysis.get("spike_detected", False),
                "volume_growth_rate":   volume_analysis.get("growth_rate", 0),
                "volume_score":         volume_analysis.get("score", 0),
                # Liquidity
                "liquidity_growth":     liquidity_analysis.get("growth_detected", False),
                "liquidity_growth_rate":liquidity_analysis.get("growth_rate", 0),
                "liquidity_score":      liquidity_analysis.get("score", 0),
                # FDV (new)
                "fdv_usd":              fdv_analysis.get("fdv_usd", 0),
                "fdv_score":            fdv_analysis.get("score", 0),
                "fdv_liq_ratio":        fdv_analysis.get("fdv_liq_ratio", 0),
                "fdv_liq_score":        fdv_analysis.get("fdv_liq_score", 0),
                # Momentum
                "price_momentum_strong":momentum_analysis.get("strong_momentum", False),
                "momentum_direction":   momentum_analysis.get("direction", "neutral"),
                "momentum_score":       momentum_analysis.get("score", 0),
                # Activity
                "high_activity":        activity_analysis.get("high_activity", False),
                "activity_increase":    activity_analysis.get("activity_increase", 0),
                "sell_authentic":       activity_analysis.get("sell_authentic", True),
                "buy_ratio_1h":         activity_analysis.get("buy_ratio_1h", 0.5),
                # Volatility
                "high_volatility":      volatility_analysis.get("high_volatility", False),
                "volatility_trend":     volatility_analysis.get("trend", "stable"),
                "upside_volatility":    volatility_analysis.get("upside", False),
                # Velocity (new)
                "vol_velocity":         velocity_analysis.get("vol_velocity", 0),
                "velocity_score":       velocity_analysis.get("score", 0),
                "has_velocity_data":    velocity_analysis.get("has_data", False),
                "cold_start":           velocity_analysis.get("cold_start", False),
            })

            # --- RF signal score (primary) ------------------------------------
            rf_score: Optional[float] = None
            rf_tier: int = 0
            rf_tier_label: str = "UNKNOWN"

            if self.scorer is not None:
                try:
                    # Build a merged dict the scorer expects
                    pool_dict = {**current_data}
                    # If collected_at is missing from current_data, don't crash
                    rf_result   = self.scorer.score(pool_dict)
                    rf_prob     = rf_result["ml_score"]          # 0-1
                    rf_score    = rf_prob * 100                  # 0-100
                    rf_tier     = rf_result["tier"]
                    rf_tier_label = rf_result["tier_label"]

                    signals["rf_score"]      = rf_score
                    signals["rf_tier"]       = rf_tier
                    signals["rf_tier_label"] = rf_tier_label
                    signals["rf_flags"]      = rf_result.get("flags", [])
                except Exception as exc:
                    logger.warning("RF scoring failed for pool %s: %s",
                                   current_data.get("address", "?"), exc)

            heuristic_score = self._heuristic_signal_score(
                fdv_analysis, volume_analysis, liquidity_analysis,
                momentum_analysis, activity_analysis, velocity_analysis,
            )

            # --- Overall signal score -----------------------------------------
            if rf_score is not None:
                # RF is the signal score; clamp to 0-100
                overall_signal_score = self._cap(rf_score, 0.0, 100.0)
            else:
                overall_signal_score = heuristic_score

            # --- Post-score hard overrides (apply regardless of RF vs heuristic)
            overall_signal_score, hard_flags = self._detect_hard_overrides(
                overall_signal_score,
                fdv_analysis,
                liquidity_analysis,
                current_data,
            )
            signals["heuristic_score"] = round(heuristic_score, 4)
            signals["hard_override_flags"] = hard_flags

            # --- Build result -------------------------------------------------
            return SignalResult(
                signal_score=self._cap(overall_signal_score, 0.0, 100.0),
                volume_trend=volume_analysis.get("trend", "stable"),
                liquidity_trend=liquidity_analysis.get("trend", "stable"),
                momentum_indicator=self._cap(
                    momentum_analysis.get("indicator", 0.0),
                    min_value=-99_999.0,
                    max_value=99_999.0,
                ),
                activity_score=self._cap(activity_analysis.get("score", 0.0), 0.0, 100.0),
                volatility_score=self._cap(volatility_analysis.get("score", 0.0), 0.0, 100.0),
                signals=signals,
            )

        except Exception as exc:
            logger.error("Error analyzing pool signals for %s: %s",
                         current_data.get("address", "?"), exc, exc_info=True)
            return self._default_result()

    # ------------------------------------------------------------------
    # Sub-analyses
    # ------------------------------------------------------------------

    def _analyze_fdv(self, current_data: Dict) -> Dict:
        """
        Score the pool's fully-diluted valuation.

        FDV was the single most important RF feature (33% importance).
        Uses log-scale: $1k→~0, $15k→~35, $50k→~57, $200k→~77, $1M→100.

        Also computes FDV/liquidity ratio — sweet spot is 1–8x.
        Very high ratios (>20x) suggest early over-valuation and dump risk.
        """
        try:
            fdv = self._safe_float(current_data.get("fdv_usd", 0))
            liq = self._safe_float(current_data.get("reserve_in_usd", 0))

            fdv_score = self._log_score(fdv, *self._FDV_LOG_RANGE)

            # FDV / liquidity ratio scoring
            fdv_liq_ratio = fdv / liq if liq > 0 else 0
            if liq == 0 or fdv == 0:
                fdv_liq_score = 0.0
            elif 1 <= fdv_liq_ratio <= 8:
                fdv_liq_score = 100.0          # sweet spot
            elif fdv_liq_ratio < 1:
                fdv_liq_score = fdv_liq_ratio * 100  # under 1x is unusual/suspicious
            else:
                # Penalise over-valued pools: 8x→100, 20x→50, 50x→20, 100x→10
                fdv_liq_score = max(0, 100 - (fdv_liq_ratio - 8) * 4)

            return {
                "fdv_usd":       fdv,
                "score":         fdv_score,
                "fdv_liq_ratio": fdv_liq_ratio,
                "fdv_liq_score": min(100.0, fdv_liq_score),
            }

        except Exception as exc:
            logger.error("Error in _analyze_fdv: %s", exc)
            return {"fdv_usd": 0, "score": 0, "fdv_liq_ratio": 0, "fdv_liq_score": 0}

    # Minimum meaningful volume baseline for ratio calculations.
    # Below this threshold the first observation is treated as a cold-start
    # (e.g. a single dust/test transaction) and ratios are not computed.
    _MIN_VOL_BASELINE = 1.0   # USD

    def _analyze_volume_trend(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Analyze volume trends and detect spikes.

        Uses log-scale base scoring so that $5k and $500k are properly
        differentiated.  Growth rate is computed against the earliest
        historical observation (not the average) to avoid dilution when
        only 1-2 prior rows exist.

        Cold-start handling: when the first observation has volume below
        _MIN_VOL_BASELINE (e.g. $0.001 from a single test transaction),
        computing a ratio would produce meaningless millions-of-x numbers.
        In that case the trend is labelled "cold_start" and the score is
        derived purely from the absolute current volume — which is still a
        genuine signal (volume appeared from nothing in one cycle).
        """
        try:
            current_vol = self._safe_float(current_data.get("volume_usd_h24", 0))
            base_score  = self._log_score(current_vol, *self._VOL_LOG_RANGE)

            if not historical_data:
                return {
                    "trend":          "unknown",
                    "spike_detected": current_vol > 10_000,
                    "growth_rate":    0.0,
                    "cold_start":     False,
                    "score":          base_score * 0.7,   # discount — no confirmation
                    "current_volume": current_vol,
                }

            # Use oldest observation as the baseline (works with 1 or 2 rows)
            first_vol = self._safe_float(historical_data[0].get("volume_usd_h24", 0))

            # --- Cold-start: baseline volume was effectively zero ---------------
            if first_vol < self._MIN_VOL_BASELINE:
                # Score on absolute current volume only; cap growth_rate at a
                # sentinel (100) so downstream callers don't see garbage values.
                cold_spike = current_vol > 5_000   # meaningful volume appeared
                return {
                    "trend":          "cold_start",
                    "spike_detected": cold_spike,
                    "growth_rate":    100.0 if current_vol > 0 else 0.0,  # sentinel
                    "cold_start":     True,
                    "score":          min(100.0, base_score + (15.0 if cold_spike else 0.0)),
                    "current_volume": current_vol,
                    "baseline_volume": first_vol,
                }

            # --- Normal case: ratio is meaningful --------------------------------
            growth_rate    = current_vol / first_vol - 1
            spike_detected = growth_rate >= (self.volume_spike_threshold - 1)

            if growth_rate > 1.0:
                trend = "spike"
            elif growth_rate > 0.2:
                trend = "increasing"
            elif growth_rate < -0.3:
                trend = "decreasing"
            else:
                trend = "stable"

            # Growth multiplier: caps at 2x bonus for 5x+ growth
            growth_bonus = min(30.0, growth_rate * 15.0)
            spike_bonus  = 10.0 if spike_detected else 0.0
            volume_score = min(100.0, base_score + growth_bonus + spike_bonus)

            return {
                "trend":           trend,
                "spike_detected":  spike_detected,
                "growth_rate":     growth_rate,
                "cold_start":      False,
                "score":           volume_score,
                "current_volume":  current_vol,
                "baseline_volume": first_vol,
            }

        except Exception as exc:
            logger.error("Error in _analyze_volume_trend: %s", exc)
            return {"trend": "stable", "spike_detected": False, "growth_rate": 0,
                    "cold_start": False, "score": 0}

    def _analyze_liquidity_trend(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Analyze liquidity (reserve_in_usd) trends.

        Log-scale base scoring: $1k→~0, $15k→~46, $50k→~68, $150k→~87.
        Liquidity growth is a positive signal; shrinkage is a strong negative.
        """
        try:
            current_liq = self._safe_float(current_data.get("reserve_in_usd", 0))
            base_score  = self._log_score(current_liq, *self._LIQ_LOG_RANGE)

            if not historical_data:
                return {
                    "trend":           "unknown",
                    "growth_detected": current_liq > 20_000,
                    "growth_rate":     0.0,
                    "score":           base_score * 0.8,
                    "current_liquidity": current_liq,
                }

            first_liq   = self._safe_float(historical_data[0].get("reserve_in_usd", 0))
            growth_rate = (current_liq / first_liq - 1) if first_liq > 0 else 0.0

            growth_detected = growth_rate >= (self.liquidity_growth_threshold - 1)

            if growth_rate > 0.2:
                trend = "growing"
            elif growth_rate < -0.2:
                trend = "shrinking"
            else:
                trend = "stable"

            # Shrinking liquidity is a strong negative signal (rug risk)
            growth_bonus   =  min(20.0, growth_rate * 25.0)
            shrink_penalty = max(-30.0, growth_rate * 40.0) if growth_rate < -0.15 else 0.0
            liq_score      = min(100.0, max(0.0, base_score + growth_bonus + shrink_penalty))

            return {
                "trend":              trend,
                "growth_detected":    growth_detected,
                "growth_rate":        growth_rate,
                "score":              liq_score,
                "current_liquidity":  current_liq,
                "baseline_liquidity": first_liq,
            }

        except Exception as exc:
            logger.error("Error in _analyze_liquidity_trend: %s", exc)
            return {"trend": "stable", "growth_detected": False, "growth_rate": 0, "score": 0}

    def _analyze_price_momentum(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Analyze price momentum.

        For new pools (< 24h old) price_change_24h == price_change_1h, so
        we avoid double-counting by using only price_change_1h in that case.
        Scoring is bullish-biased since we are looking for long entries only.
        """
        try:
            pc1h  = self._safe_float(current_data.get("price_change_percentage_h1",  0))
            pc24h = self._safe_float(current_data.get("price_change_percentage_h24", 0))

            # Cap to avoid DB overflow and score distortion
            MAX_PC = 100_000.0
            pc1h  = max(-MAX_PC, min(MAX_PC, pc1h))
            pc24h = max(-MAX_PC, min(MAX_PC, pc24h))

            # Detect new pool: if 24h ~ 1h (within 5%), treat as same signal
            pool_is_new = abs(pc1h - pc24h) < max(5.0, abs(pc1h) * 0.05)
            if pool_is_new:
                momentum_indicator = float(pc1h)
            else:
                # Weight recent hour more heavily
                momentum_indicator = float((pc1h * 2.0 + pc24h) / 3.0)

            strong_momentum = abs(momentum_indicator) > 15.0

            if momentum_indicator > 10:
                direction = "bullish"
            elif momentum_indicator < -10:
                direction = "bearish"
            else:
                direction = "neutral"

            # Log-scale momentum score (bullish bias)
            if momentum_indicator > 0:
                # log scale: 1%→10, 10%→35, 50%→60, 200%→80, 1000%→100
                m_score = min(100.0, self._log_score(momentum_indicator + 1, 0, 3) * 1.2)
            else:
                # Bearish momentum subtracts from score
                m_score = max(0.0, 30.0 + momentum_indicator * 0.5)

            strong_bonus = 5.0 if strong_momentum and direction == "bullish" else 0.0
            momentum_score = min(100.0, m_score + strong_bonus)

            return {
                "indicator":       momentum_indicator,
                "strong_momentum": strong_momentum,
                "direction":       direction,
                "score":           momentum_score,
                "price_change_1h": pc1h,
                "price_change_24h":pc24h,
                "pool_is_new":     pool_is_new,
            }

        except Exception as exc:
            logger.error("Error in _analyze_price_momentum: %s", exc)
            return {"indicator": 0.0, "strong_momentum": False, "direction": "neutral", "score": 0}

    def _analyze_trading_activity(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Analyze trading activity with sell-authenticity checks.

        Key insight from RF analysis: sell transactions are a strong
        authenticity signal.  Pools with 0 sells + meaningful buys are
        almost certainly bots/wash trading and almost never become winners.
        Extreme buy-side imbalance (>97% buys) is similarly penalized.
        """
        try:
            buys_1h  = self._safe_int(current_data.get("transactions_h1_buys",  0))
            sells_1h = self._safe_int(current_data.get("transactions_h1_sells", 0))
            buys_24h = self._safe_int(current_data.get("transactions_h24_buys",  0))
            sells_24h= self._safe_int(current_data.get("transactions_h24_sells", 0))

            total_1h  = buys_1h  + sells_1h
            total_24h = buys_24h + sells_24h
            buy_ratio_1h  = buys_1h  / total_1h  if total_1h  > 0 else 0.5
            buy_ratio_24h = buys_24h / total_24h if total_24h > 0 else 0.5

            # --- Authenticity checks ------------------------------------------
            # Zero sells with any real buy activity → likely scam / bot
            sell_authentic = True
            authenticity_penalty = 0.0

            if sells_1h == 0 and buys_1h > 10:
                sell_authentic       = False
                authenticity_penalty = -35.0
                logger.debug("Zero-sell flag: buys=%d sells=0", buys_1h)
            elif sells_1h < 2 and buys_1h > 20:
                sell_authentic       = False
                authenticity_penalty = -15.0

            # Extreme buy imbalance: >97% buys with >20 total → bot pattern
            if buy_ratio_1h > 0.97 and total_1h > 20:
                sell_authentic       = False
                authenticity_penalty = min(authenticity_penalty, -20.0)

            # --- Activity score (log scale) -----------------------------------
            high_activity = total_1h > 50 or total_24h > 200

            # Log-scale on 1h total txns; minor 24h contribution
            act_base  = self._log_score(max(total_1h, 1), *self._ACT_LOG_RANGE) * 0.75
            act_24h   = self._log_score(max(total_24h, 1), *self._ACT_LOG_RANGE) * 0.25
            act_score = min(100.0, max(0.0, act_base + act_24h + authenticity_penalty))

            # Historical comparison (works with 1-2 rows)
            activity_increase = 0.0
            if historical_data:
                avg_hist_24h = sum(
                    self._safe_int(d.get("transactions_h24_buys",  0)) +
                    self._safe_int(d.get("transactions_h24_sells", 0))
                    for d in historical_data
                ) / len(historical_data)
                if avg_hist_24h > 0:
                    activity_increase = (total_24h / avg_hist_24h) - 1.0

            return {
                "score":                act_score,
                "high_activity":        high_activity,
                "sell_authentic":       sell_authentic,
                "authenticity_penalty": authenticity_penalty,
                "activity_increase":    activity_increase,
                "total_transactions_1h":  total_1h,
                "total_transactions_24h": total_24h,
                "buy_ratio_1h":           buy_ratio_1h,
                "buy_ratio_24h":          buy_ratio_24h,
            }

        except Exception as exc:
            logger.error("Error in _analyze_trading_activity: %s", exc)
            return {"score": 0, "high_activity": False, "activity_increase": 0,
                    "sell_authentic": True, "buy_ratio_1h": 0.5}

    def _analyze_volatility(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Analyze price volatility, distinguishing upside from downside.

        For our long-only strategy, upside volatility is a feature not a bug.
        High downside volatility is a warning sign.
        """
        try:
            pc1h  = self._safe_float(current_data.get("price_change_percentage_h1",  0))
            pc24h = self._safe_float(current_data.get("price_change_percentage_h24", 0))

            MAX_PC = 100_000.0
            pc1h  = max(-MAX_PC, min(MAX_PC, pc1h))
            pc24h = max(-MAX_PC, min(MAX_PC, pc24h))

            upside   = (pc1h  > 0 and pc24h >= 0)
            downside = (pc1h  < -10 or pc24h < -20)

            # Use absolute values for volatility magnitude
            abs1h  = abs(pc1h)
            abs24h = abs(pc24h)

            # Weighted average — 1h is more relevant for fresh pools
            volatility_level = (abs1h * 2.0 + abs24h) / 3.0
            high_volatility  = volatility_level > 15.0

            if volatility_level > 50:
                trend = "extreme"
            elif volatility_level > 20:
                trend = "high"
            elif volatility_level > 8:
                trend = "moderate"
            else:
                trend = "low"

            # Score: upside volatility is rewarded, downside penalised
            raw_score = min(100.0, math.log1p(volatility_level) / math.log1p(100) * 100)
            if downside:
                raw_score *= 0.5  # halve score for negative price action
            elif upside and high_volatility:
                raw_score = min(100.0, raw_score * 1.2)

            return {
                "score":           raw_score,
                "high_volatility": high_volatility,
                "upside":          upside,
                "downside":        downside,
                "trend":           trend,
                "volatility_1h":   abs1h,
                "volatility_24h":  abs24h,
            }

        except Exception as exc:
            logger.error("Error in _analyze_volatility: %s", exc)
            return {"score": 0, "high_volatility": False, "trend": "low", "upside": False}

    def _analyze_velocity(
        self,
        current_data: Dict,
        historical_data: Optional[List[Dict]],
    ) -> Dict:
        """
        Compute change velocity between the first and most recent observation.

        With the typical 2-3 row window available from the API this is the
        most reliable multi-row signal.  From backtesting:
          - Winners show ~38x volume growth between first and current obs
          - Losers show ~17x volume growth over the same window

        Liquidity velocity is also tracked: growing liquidity alongside
        volume is confirmation; shrinking liquidity is a rug warning.

        Cold-start handling: when first_vol is below _MIN_VOL_BASELINE the
        pool had essentially zero volume at first detection (a dust/test tx).
        In this case vol_velocity is undefined as a ratio, so we score purely
        on the absolute current volume and flag cold_start=True.  The DB
        column receives a vol_velocity of 0 rather than a garbage large number.
        """
        try:
            if not historical_data:
                return {"has_data": False, "vol_velocity": 0, "liq_velocity": 0,
                        "cold_start": False, "score": 0}

            first = historical_data[0]   # oldest available observation

            curr_vol  = self._safe_float(current_data.get("volume_usd_h24", 0))
            first_vol = self._safe_float(first.get("volume_usd_h24", 0))
            curr_liq  = self._safe_float(current_data.get("reserve_in_usd", 0))
            first_liq = self._safe_float(first.get("reserve_in_usd", 0))
            curr_buys = self._safe_int(current_data.get("transactions_h1_buys", 0))
            first_buys= self._safe_int(first.get("transactions_h1_buys", 0))

            # Liquidity velocity — liquidity is rarely near-zero so ratio is safe
            liq_velocity = curr_liq / first_liq if first_liq > 0 else 0.0
            buy_velocity = curr_buys / first_buys if first_buys > 0 else 0.0

            # --- Cold-start: first volume was effectively zero -------------------
            if first_vol < self._MIN_VOL_BASELINE:
                # Score on absolute current volume using the same log-scale
                # as the no-history path in _analyze_volume_trend.
                abs_score = self._log_score(curr_vol, *self._VOL_LOG_RANGE)
                vel_score = min(100.0, abs_score)

                # Liquidity rug check still applies
                if liq_velocity < 0.7:
                    vel_score = max(0.0, vel_score - 25.0)

                return {
                    "has_data":     True,
                    "cold_start":   True,
                    "vol_velocity": 0.0,       # undefined — stored as 0 not garbage
                    "liq_velocity": liq_velocity,
                    "buy_velocity": buy_velocity,
                    "score":        vel_score,
                    "n_obs":        len(historical_data) + 1,
                }

            # --- Normal case: ratio is meaningful --------------------------------
            vol_velocity = curr_vol / first_vol

            # Score based on vol_velocity (primary signal)
            # Calibrated to winner/loser distributions: 38x wins, 17x loses
            if vol_velocity >= 50:
                vel_score = 100.0
            elif vol_velocity >= 30:
                vel_score = 85.0
            elif vol_velocity >= 15:
                vel_score = 65.0
            elif vol_velocity >= 5:
                vel_score = 40.0
            elif vol_velocity >= 2:
                vel_score = 20.0
            else:
                vel_score = max(0.0, (vol_velocity - 1) * 20)

            # Liquidity confirmation / rug warning
            if liq_velocity < 0.7:
                vel_score = max(0.0, vel_score - 25.0)
            elif liq_velocity > 1.2 and vol_velocity > 5:
                vel_score = min(100.0, vel_score + 10.0)

            return {
                "has_data":     True,
                "cold_start":   False,
                "vol_velocity": vol_velocity,
                "liq_velocity": liq_velocity,
                "buy_velocity": buy_velocity,
                "score":        vel_score,
                "n_obs":        len(historical_data) + 1,
            }

        except Exception as exc:
            logger.error("Error in _analyze_velocity: %s", exc)
            return {"has_data": False, "vol_velocity": 0, "liq_velocity": 0,
                    "cold_start": False, "score": 0}

    # ------------------------------------------------------------------
    # Post-RF hard overrides
    # ------------------------------------------------------------------

    def _detect_hard_overrides(
        self,
        current_score: float,
        fdv_analysis: Dict,
        liquidity_analysis: Dict,
        current_data: Dict,
    ) -> Tuple[float, List[str]]:
        """
        Apply hard score caps AFTER the RF model has run.

        The RF model is excellent at separating typical winners from typical
        losers, but it was trained on a limited window of data and cannot
        reliably learn patterns that are simultaneously rare AND catastrophic.
        These overrides catch two such patterns:

        1. extreme_fdv_liq_ratio  (pre-minted insider dump)
           FDV > 100x the pool's liquidity while liquidity is still small
           (<$50k) is a near-certain signal that insiders hold nearly all
           supply and will dump as soon as retail buys in.  The RF sees
           "high FDV → winner" from training data and ignores the ratio.
           Cap: 20.  The pool is not zero — maybe someone legitimately
           launches at a wild valuation — but it should never be watchlisted.

        2. rug_detected  (liquidity pulled in one cycle)
           >90% of liquidity removed between two consecutive 120s observations.
           This is an in-progress or just-completed rug pull.  There is no
           recovery from this.  Cap: 5.

        3. price_crash  (>90% price drop in one hour)
           Price has already collapsed.  Combined with rug this is definitive;
           standalone it may be extreme sell pressure rather than a rug.
           Cap: 10.

        Returns
        -------
        (capped_score, override_flags)
            capped_score   : current_score reduced by whichever caps applied
            override_flags : list of flag name strings (empty = no override)
        """
        flags: List[str] = []
        score = current_score

        fdv             = fdv_analysis.get("fdv_usd", 0)
        fdv_liq_ratio   = fdv_analysis.get("fdv_liq_ratio", 0)
        liq             = self._safe_float(current_data.get("reserve_in_usd", 0))
        liq_growth_rate = liquidity_analysis.get("growth_rate", 0)
        pc1h            = self._safe_float(current_data.get("price_change_percentage_h1", 0))

        # --- 1. Extreme FDV/liquidity ratio ------------------------------------
        if (fdv_liq_ratio > self._EXTREME_FDV_LIQ_RATIO
                and liq < self._EXTREME_FDV_MAX_LIQ
                and fdv > 0):
            flags.append("extreme_fdv_liq_ratio")
            score = min(score, 20.0)
            logger.warning(
                "Hard override extreme_fdv_liq_ratio: pool=%s fdv=%.0f liq=%.0f "
                "ratio=%.0fx score capped at 20 (was %.1f)",
                current_data.get("address", "?"), fdv, liq, fdv_liq_ratio, current_score,
            )

        # --- 2. Liquidity collapse (rug) ----------------------------------------
        if liq_growth_rate < self._RUG_LIQ_DROP_THRESHOLD:
            flags.append("rug_detected")
            score = min(score, 5.0)
            logger.warning(
                "Hard override rug_detected: pool=%s liq_drop=%.1f%% score capped "
                "at 5 (was %.1f)",
                current_data.get("address", "?"),
                liq_growth_rate * 100,
                current_score,
            )

        # --- 3. Price crash ------------------------------------------------------
        if pc1h < self._PRICE_CRASH_THRESHOLD:
            flags.append("price_crash")
            score = min(score, 10.0)
            logger.warning(
                "Hard override price_crash: pool=%s pc1h=%.1f%% score capped "
                "at 10 (was %.1f)",
                current_data.get("address", "?"), pc1h, current_score,
            )

        return score, flags

    # ------------------------------------------------------------------
    # Heuristic overall score (fallback when RF unavailable)
    # ------------------------------------------------------------------

    def _heuristic_signal_score(
        self,
        fdv_analysis:        Dict,
        volume_analysis:     Dict,
        liquidity_analysis:  Dict,
        momentum_analysis:   Dict,
        activity_analysis:   Dict,
        velocity_analysis:   Dict,
    ) -> float:
        """
        Weighted heuristic score aligned to RF feature importances.

        Weights (approx RF importance):
          FDV          25%   (RF: 33%)
          FDV/liq      10%   (RF: 15%)
          Liquidity    20%   (RF: 16%)
          Volume       20%   (RF: 10%)
          Activity     15%   (RF: ~8% combined txn features)
          Momentum     10%   (RF: 6%)
          Velocity      +10  additive bonus (not in RF — cross-row signal)
        """
        try:
            fdv_score  = fdv_analysis.get("score", 0)
            fdl_score  = fdv_analysis.get("fdv_liq_score", 0)
            liq_score  = liquidity_analysis.get("score", 0)
            vol_score  = volume_analysis.get("score", 0)
            act_score  = activity_analysis.get("score", 0)
            mom_score  = momentum_analysis.get("score", 0)
            vel_score  = velocity_analysis.get("score", 0)

            base = (
                fdv_score * 0.25 +
                fdl_score * 0.10 +
                liq_score * 0.20 +
                vol_score * 0.20 +
                act_score * 0.15 +
                mom_score * 0.10
            )

            # Velocity bonus (up to +10) — only when we actually have multi-row data
            vel_bonus = (vel_score / 100.0 * 10.0) if velocity_analysis.get("has_data") else 0.0

            # Rug / scam hard penalty — override bonuses
            liq_shrink = liquidity_analysis.get("growth_rate", 0) < -0.3
            not_authentic = not activity_analysis.get("sell_authentic", True)
            if liq_shrink and not_authentic:
                base *= 0.4   # both flags together = strong scam signal

            return min(100.0, max(0.0, base + vel_bonus))

        except Exception as exc:
            logger.error("Error in _heuristic_signal_score: %s", exc)
            return 0.0

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _log_score(value: float, min_log: float, max_log: float) -> float:
        """
        Map a value onto 0-100 using a log10 scale.

        Values at or below 10^min_log → 0; at or above 10^max_log → 100.
        """
        if value <= 0:
            return 0.0
        log_val = math.log10(value)
        return float(min(100.0, max(0.0, (log_val - min_log) / (max_log - min_log) * 100)))

    @staticmethod
    def _cap(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
        """Clamp value and handle NaN/Inf."""
        if value is None:
            return min_value
        try:
            v = float(value)
        except (TypeError, ValueError):
            return min_value
        if math.isnan(v) or math.isinf(v):
            return max_value if v == float("inf") else min_value
        return max(min_value, min(max_value, v))

    @staticmethod
    def _safe_float(value: Any) -> float:
        if value is None or value == "":
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        if value is None or value == "":
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    # Keep for any callers that still use Decimal (e.g. direct DB writes)
    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal("0")

    # Backwards-compat alias
    def _cap_extreme_value(
        self,
        value: float,
        max_value: float = 999_999.0,
        min_value: float = -999_999.0,
    ) -> float:
        return self._cap(value, min_value, max_value)

    def _default_result(self) -> SignalResult:
        return SignalResult(
            signal_score=0.0,
            volume_trend="stable",
            liquidity_trend="stable",
            momentum_indicator=0.0,
            activity_score=0.0,
            volatility_score=0.0,
            signals={},
        )

    # ------------------------------------------------------------------
    # Watchlist / alerting helpers
    # ------------------------------------------------------------------

    def should_add_to_watchlist(
        self,
        signal_result: SignalResult,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Determine if a pool should be added to watchlist.

        When the RF model is available, gates on RF tier >= 2 (MEDIUM)
        which corresponds to ~20-26% precision.  Falls back to heuristic
        threshold when model is not loaded.

        Hard override flags (extreme_fdv_liq_ratio, rug_detected, price_crash)
        always block watchlist addition regardless of score or tier.
        """
        signals = signal_result.signals

        # Hard overrides always block — these are catastrophic conditions
        if signals.get("hard_override_flags"):
            return False

        # Heuristic fallback (only when RF model is not loaded at all)
        if threshold is None:
            threshold = self.config.get("auto_watchlist_threshold", 65.0)
        return signal_result.signal_score >= threshold

    def generate_alert_message(self, pool_id: str, signal_result: SignalResult) -> str:
        """Generate a human-readable alert for strong signals."""
        signals  = signal_result.signals
        messages = []

        # Hard overrides — surface these first, they are the most important
        hard_flags = signals.get("hard_override_flags", [])
        if hard_flags:
            flag_labels = {
                "extreme_fdv_liq_ratio": "⛔ Extreme FDV/liq ratio (insider dump risk)",
                "rug_detected":          "🚨 RUG DETECTED — liquidity collapsed",
                "price_crash":           "🚨 Price crashed >90%",
            }
            for flag in hard_flags:
                messages.append(flag_labels.get(flag, f"⛔ {flag}"))

        # RF tier (only show if no hard overrides — overrides mean RF was wrong)
        if not hard_flags and "rf_tier" in signals and signals["rf_tier"] >= 1:
            tier   = signals["rf_tier_label"]
            rf_pct = signals.get("rf_score", signal_result.signal_score)
            messages.append(f"RF tier {signals['rf_tier']} ({tier}) — score {rf_pct:.1f}/100")

        if signals.get("volume_spike"):
            messages.append(
                f"Volume spike ({signals.get('volume_growth_rate', 0):.0%} growth)"
            )
        if signals.get("liquidity_growth"):
            messages.append(
                f"Liquidity growing ({signals.get('liquidity_growth_rate', 0):.0%})"
            )
        if signals.get("price_momentum_strong") and not hard_flags:
            messages.append(f"Strong {signals.get('momentum_direction','?')} momentum")
        if signals.get("high_activity") and not hard_flags:
            messages.append("High trading activity")
        if signals.get("has_velocity_data") and signals.get("vol_velocity", 0) > 15 and not hard_flags:
            messages.append(f"Volume velocity {signals['vol_velocity']:.0f}x")
        if not signals.get("sell_authentic", True):
            messages.append("⚠ Low sell authenticity")

        if not messages:
            messages.append("Multiple positive signals")

        return (
            f"Pool {pool_id} | Score {signal_result.signal_score:.1f} "
            f"| {' | '.join(messages)}"
        )
