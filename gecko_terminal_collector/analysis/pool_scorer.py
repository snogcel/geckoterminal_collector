"""
pool_scorer.py
==============
Live ML scoring for new PumpSwap pools on Solana.
Predicts probability that a newly observed pool will become a
DexScreener micro-cap watchlist breakout candidate.

Model: RandomForest (ROC-AUC 0.87, trained on 39,811 pools)
Trained: Feb 20 – Mar 5 2026 | Network: Solana | DEX: PumpSwap

Usage
-----
    from pool_scorer import PoolScorer

    scorer = PoolScorer("pool_winner_model.pkl")

    # Score a single pool dict (from your DexScreener API response)
    result = scorer.score(pool_data)
    print(result)
    # {'address': '...', 'ml_score': 0.73, 'tier': 1, 'tier_label': 'HIGH',
    #  'flags': [], 'features': {...}}

    # Score a list of pools (e.g. batch from new-pools endpoint)
    results = scorer.score_batch(pool_list)

    # Score a pandas DataFrame (your new_pools_history rows)
    df_scored = scorer.score_dataframe(df)
"""

import pickle
import json
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier definitions (based on backtest precision/recall analysis)
# ---------------------------------------------------------------------------
"""
TIERS = {
    1: {"label": "HIGH",   "min_score": 0.70, "precision": 0.26, "pools_per_day": 274},
    2: {"label": "MEDIUM", "min_score": 0.60, "precision": 0.20, "pools_per_day": 484},
    3: {"label": "LOW",    "min_score": 0.25, "precision": 0.10, "pools_per_day": 1500},
    0: {"label": "FILTER", "min_score": 0.00, "precision": 0.01, "pools_per_day": None},
} """

# UPDATE 2026-03-24: Adjusted tier thresholds based on backtest performance analysis.
TIERS = {
    1: {"label": "HIGH",   "min_score": 0.70, "precision": 0.30, "pools_per_day": 354},
    2: {"label": "MEDIUM", "min_score": 0.60, "precision": 0.26, "pools_per_day": 462},
    3: {"label": "LOW",    "min_score": 0.50, "precision": 0.21, "pools_per_day": 622},
    0: {"label": "FILTER", "min_score": 0.00, "precision": 0.01, "pools_per_day": None},
}

# Scam/noise filter: pools matching ANY of these are almost certainly worthless
SCAM_RULES = [
    ("zero_sells_low_fdv", lambda r: r.get("transactions_h1_sells", 0) == 0
                                     and r.get("fdv_usd", 0) < 5_000),
    ("near_zero_volume",   lambda r: r.get("volume_usd_h24", 0) < 200),
    ("extreme_fdv_liq_ratio", lambda r:
        (r.get("fdv_usd") or 0) / max(r.get("reserve_in_usd") or 1, 1) > 100
        and (r.get("reserve_in_usd") or 0) < 50_000
        and (r.get("fdv_usd") or 0) > 0),
]

# Feature column order must match training exactly
FEATURE_COLS = [
    "log_vol",
    "log_fdv",
    "log_reserve",
    "log_buys",
    "log_sells",
    "buy_sell_ratio",
    "vol_per_liq",
    "total_txns_h1",
    "sells_pct",
    "price_change_percentage_h1",
    "fdv_liq_ratio",
    "age_min",
]


# ---------------------------------------------------------------------------
# Feature engineering — mirrors training pipeline exactly
# ---------------------------------------------------------------------------
def engineer_features(pool: dict[str, Any]) -> dict[str, float]:
    """
    Transform a raw pool observation dict into the 12 model features.

    Expected input keys (all available from DexScreener /new-pools endpoint):
        volume_usd_h24              float   24-hour volume in USD
        fdv_usd                     float   fully diluted valuation (can be None)
        reserve_in_usd              float   pool liquidity reserve (can be None)
        transactions_h1_buys        int     buy transactions in last hour
        transactions_h1_sells       int     sell transactions in last hour
        price_change_percentage_h1  float   1-hour price change %
        pool_created_at             str     ISO timestamp of pool creation
        collected_at                str     ISO timestamp of this observation
    """
    vol       = float(pool.get("volume_usd_h24") or 0)
    fdv       = float(pool.get("fdv_usd") or 0)
    reserve   = float(pool.get("reserve_in_usd") or 0)
    buys      = float(pool.get("transactions_h1_buys") or 0)
    sells     = float(pool.get("transactions_h1_sells") or 0)
    pc1h      = float(pool.get("price_change_percentage_h1") or 0)

    total_txns  = buys + sells
    buy_sell_r  = buys / (sells + 1)
    vol_per_liq = vol / (reserve + 1)
    sells_pct   = sells / (total_txns + 1)
    fdv_liq_r   = fdv / (reserve + 1)

    # Pool age in minutes
    age_min = 0.0
    try:
        created_raw   = pool.get("pool_created_at")
        collected_raw = pool.get("collected_at")
        if created_raw and collected_raw:
            def _parse(ts):
                if isinstance(ts, (int, float)):
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                ts = str(ts).replace(" ", "T")
                if ts.endswith("+00"):
                    ts += ":00"
                return datetime.fromisoformat(ts).astimezone(timezone.utc)
            created   = _parse(created_raw)
            collected = _parse(collected_raw)
            age_min   = max(0.0, (collected - created).total_seconds() / 60)
    except Exception as exc:
        logger.debug("age_min calculation failed: %s", exc)

    return {
        "log_vol":                    float(np.log1p(vol)),
        "log_fdv":                    float(np.log1p(fdv)),
        "log_reserve":                float(np.log1p(reserve)),
        "log_buys":                   float(np.log1p(buys)),
        "log_sells":                  float(np.log1p(sells)),
        "buy_sell_ratio":             float(buy_sell_r),
        "vol_per_liq":                float(vol_per_liq),
        "total_txns_h1":              float(total_txns),
        "sells_pct":                  float(sells_pct),
        "price_change_percentage_h1": float(pc1h),
        "fdv_liq_ratio":              float(fdv_liq_r),
        "age_min":                    float(age_min),
        # Raw values kept for transparency / rule checks
        "_raw_vol":    vol,
        "_raw_fdv":    fdv,
        "_raw_reserve": reserve,
        "_raw_buys":   buys,
        "_raw_sells":  sells,
    }


def _feature_vector(features: dict) -> np.ndarray:
    """Return the 12-element feature vector in the exact training order."""
    return np.array([[features[c] for c in FEATURE_COLS]], dtype=float)


# ---------------------------------------------------------------------------
# Scam / noise flags
# ---------------------------------------------------------------------------
def detect_flags(pool: dict[str, Any]) -> list[str]:
    triggered = []
    for name, rule in SCAM_RULES:
        try:
            if rule(pool):
                triggered.append(name)
        except Exception:
            pass
    return triggered


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------
def assign_tier(score: float, flags: list[str]) -> int:
    if flags:
        return 0  # FILTER immediately if scam flags present
    if score >= TIERS[1]["min_score"]:
        return 1
    if score >= TIERS[2]["min_score"]:
        return 2
    if score >= TIERS[3]["min_score"]:
        return 3
    return 0


# ---------------------------------------------------------------------------
# Main scorer class
# ---------------------------------------------------------------------------
class PoolScorer:
    """
    Load the serialised Random Forest model and score new pool observations.

    Parameters
    ----------
    model_path : str or Path
        Path to the pickled RandomForestClassifier (.pkl).
    metadata_path : str or Path, optional
        Path to the companion JSON metadata file. Used for logging / validation.
    """

    def __init__(
        self,
        model_path: str | Path = "pool_winner_model.pkl",
        metadata_path: str | Path | None = None,
    ):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        with open(model_path, "rb") as fh:
            self.model = pickle.load(fh)

        self.metadata: dict = {}
        if metadata_path is None:
            candidate = model_path.with_name(model_path.stem + "_metadata.json")
            if candidate.exists():
                metadata_path = candidate

        if metadata_path and Path(metadata_path).exists():
            with open(metadata_path) as fh:
                self.metadata = json.load(fh)

        logger.info(
            "PoolScorer loaded: %s | features=%d | trained_on=%s",
            model_path.name,
            self.model.n_features_in_,
            self.metadata.get("trained_on", "unknown"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, pool: dict[str, Any]) -> dict[str, Any]:
        """
        Score a single pool observation.

        Parameters
        ----------
        pool : dict
            Raw pool dict from DexScreener API or your new_pools_history table.

        Returns
        -------
        dict with keys:
            address       str    pool address
            ml_score      float  0–1 probability of becoming a watchlist winner
            tier          int    0 (filter) | 1 (high) | 2 (medium) | 3 (low)
            tier_label    str    "FILTER" | "HIGH" | "MEDIUM" | "LOW"
            flags         list   scam/noise flags triggered (empty = clean)
            features      dict   engineered features used (for logging/debug)
            scored_at     str    UTC ISO timestamp
        """
        features = engineer_features(pool)
        flags    = detect_flags(pool)

        # Still score even if flagged — useful for logging & model retraining
        X = _feature_vector(features)
        ml_score = float(self.model.predict_proba(X)[0, 1])

        tier = assign_tier(ml_score, flags)

        return {
            "address":    pool.get("address", ""),
            "name":       pool.get("name", ""),
            "ml_score":   round(ml_score, 4),
            "tier":       tier,
            "tier_label": TIERS[tier]["label"],
            "flags":      flags,
            "features":   {k: round(v, 6) for k, v in features.items()},
            "scored_at":  datetime.now(timezone.utc).isoformat(),
        }

    def score_batch(
        self, pools: list[dict[str, Any]], min_tier: int = 0
    ) -> list[dict[str, Any]]:
        """
        Score a list of pool dicts and return results sorted by ml_score desc.

        Parameters
        ----------
        pools : list of dicts
        min_tier : int
            Filter results to only tiers >= min_tier.
            E.g. min_tier=1 returns only HIGH conviction pools.

        Returns
        -------
        list of score result dicts, sorted by ml_score descending.
        """
        results = [self.score(p) for p in pools]
        results.sort(key=lambda r: r["ml_score"], reverse=True)
        if min_tier > 0:
            results = [r for r in results if r["tier"] >= min_tier]
        return results

    def score_dataframe(
        self,
        df: pd.DataFrame,
        address_col: str = "address",
        sort: bool = True,
    ) -> pd.DataFrame:
        """
        Score every row of a DataFrame and append ml_score / tier columns.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain the columns used by engineer_features().
        address_col : str
            Column to use as the pool identifier.
        sort : bool
            If True, sort output by ml_score descending.

        Returns
        -------
        pd.DataFrame with added columns:
            ml_score, tier, tier_label, scam_flags
        """
        records = df.to_dict(orient="records")
        results = [self.score(r) for r in records]

        df = df.copy()
        df["ml_score"]   = [r["ml_score"]   for r in results]
        df["tier"]       = [r["tier"]        for r in results]
        df["tier_label"] = [r["tier_label"]  for r in results]
        df["scam_flags"] = [",".join(r["flags"]) if r["flags"] else "" for r in results]

        if sort:
            df = df.sort_values("ml_score", ascending=False)

        return df

    def get_threshold_info(self, threshold: float | None = None) -> dict | list:
        """
        Return performance stats for a given threshold (or all thresholds).
        Pulled from the metadata JSON if available.
        """
        perf = self.metadata.get("threshold_performance", {})
        if threshold is not None:
            key = str(round(threshold, 2))
            return perf.get(key, {"note": f"No data for threshold {threshold}"})
        return perf

    def summary(self) -> str:
        """Human-readable model summary."""
        lines = [
            "=" * 60,
            "  PoolScorer — Micro-Cap Winner Prediction Model",
            "=" * 60,
            f"  Trained on : {self.metadata.get('trained_on', 'N/A')}",
            f"  Samples    : {self.metadata.get('n_train_samples', 'N/A'):,}",
            f"  Winners    : {self.metadata.get('n_winners_train', 'N/A'):,} "
            f"({self.metadata.get('baseline_precision', 0)*100:.1f}% base rate)",
            f"  ROC-AUC    : {self.metadata.get('roc_auc_cv', 'N/A')}",
            f"  Features   : {len(FEATURE_COLS)}",
            "",
            "  Operating tiers:",
            "    Tier 1 (HIGH)   score ≥ 0.70 → ~274 pools/day | 26% precision",
            "    Tier 2 (MEDIUM) score ≥ 0.60 → ~484 pools/day | 20% precision",
            "    Tier 3 (LOW)    score ≥ 0.25 → ~1500 pools/day | 10% precision",
            "    Tier 0 (FILTER) scam flags or score < 0.25",
            "=" * 60,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI / quick-test entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    model_file = sys.argv[1] if len(sys.argv) > 1 else "pool_winner_model.pkl"
    scorer = PoolScorer(model_file)
    print(scorer.summary())

    # Synthetic test cases to verify live behaviour
    test_pools = [
        {
            "address": "TEST_HIGH_CONVICTION",
            "name": "MOCK / SOL",
            "fdv_usd": 65_000,
            "reserve_in_usd": 28_000,
            "volume_usd_h24": 42_000,
            "transactions_h1_buys": 180,
            "transactions_h1_sells": 75,
            "price_change_percentage_h1": 38.5,
            "pool_created_at": "2026-03-05T10:00:00+00:00",
            "collected_at":    "2026-03-05T10:03:00+00:00",
        },
        {
            "address": "TEST_MEDIUM_CONVICTION",
            "name": "DEGEN / SOL",
            "fdv_usd": 32_000,
            "reserve_in_usd": 18_000,
            "volume_usd_h24": 12_000,
            "transactions_h1_buys": 60,
            "transactions_h1_sells": 22,
            "price_change_percentage_h1": 15.0,
            "pool_created_at": "2026-03-05T09:00:00+00:00",
            "collected_at":    "2026-03-05T09:05:00+00:00",
        },
        {
            "address": "TEST_LIKELY_SCAM",
            "name": "MOON100X / SOL",
            "fdv_usd": 3_500,
            "reserve_in_usd": 1_200,
            "volume_usd_h24": 180,
            "transactions_h1_buys": 4,
            "transactions_h1_sells": 0,        # <-- scam flag
            "price_change_percentage_h1": 0.0,
            "pool_created_at": "2026-03-05T11:00:00+00:00",
            "collected_at":    "2026-03-05T11:01:00+00:00",
        },
    ]

    print("\nTest scores:")
    print(f"  {'Name':<25} {'Score':>7}  {'Tier':<8}  {'Flags'}")
    print("  " + "-" * 60)
    for pool in test_pools:
        result = scorer.score(pool)
        flags_str = ", ".join(result["flags"]) or "—"
        print(f"  {result['name']:<25} {result['ml_score']:>7.4f}  "
              f"{result['tier_label']:<8}  {flags_str}")
