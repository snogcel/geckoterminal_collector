"""
Activity scoring system for pool discovery and prioritization.

This module provides intelligent filtering and prioritization of pools based on
activity metrics like volume, transaction count, and liquidity.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CollectionPriority(Enum):
    """Collection priority levels for pools."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    PAUSED = "paused"


@dataclass
class ActivityMetrics:
    """Container for pool activity metrics."""
    volume_24h_usd: Decimal
    transaction_count_24h: int
    liquidity_usd: Decimal
    price_change_24h: Optional[Decimal] = None
    market_cap_usd: Optional[Decimal] = None
    
    def __post_init__(self):
        """Validate metrics after initialization."""
        if self.volume_24h_usd < 0:
            raise ValueError("Volume cannot be negative")
        if self.transaction_count_24h < 0:
            raise ValueError("Transaction count cannot be negative")
        if self.liquidity_usd < 0:
            raise ValueError("Liquidity cannot be negative")


@dataclass
class ScoringWeights:
    """Weights for different activity metrics in scoring calculation."""
    volume_weight: Decimal = Decimal("0.4")
    transaction_weight: Decimal = Decimal("0.3")
    liquidity_weight: Decimal = Decimal("0.2")
    volatility_weight: Decimal = Decimal("0.1")
    
    def __post_init__(self):
        """Validate that weights sum to 1.0."""
        total = self.volume_weight + self.transaction_weight + self.liquidity_weight + self.volatility_weight
        if abs(total - Decimal("1.0")) > Decimal("0.001"):
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


class ActivityScorer:
    """
    Scores pools based on activity metrics for prioritization and filtering.
    
    The scoring system evaluates pools based on multiple factors:
    - 24h trading volume (USD)
    - Transaction count (24h)
    - Available liquidity (USD)
    - Price volatility (optional)
    
    Scores are normalized to a 0-100 scale where higher scores indicate
    more active and valuable pools for data collection.
    """
    
    def __init__(
        self,
        min_volume_threshold: Decimal = Decimal("1000"),
        min_liquidity_threshold: Decimal = Decimal("5000"),
        min_transaction_threshold: int = 10,
        activity_threshold: Decimal = Decimal("25"),
        weights: Optional[ScoringWeights] = None
    ):
        """
        Initialize the activity scorer with configurable thresholds.
        
        Args:
            min_volume_threshold: Minimum 24h volume (USD) for pool inclusion
            min_liquidity_threshold: Minimum liquidity (USD) for pool inclusion
            min_transaction_threshold: Minimum 24h transaction count for inclusion
            activity_threshold: Minimum activity score for pool inclusion
            weights: Custom scoring weights (uses defaults if None)
        """
        self.min_volume_threshold = min_volume_threshold
        self.min_liquidity_threshold = min_liquidity_threshold
        self.min_transaction_threshold = min_transaction_threshold
        self.activity_threshold = activity_threshold
        self.weights = weights or ScoringWeights()
        
        logger.info(
            f"ActivityScorer initialized with thresholds: "
            f"volume=${min_volume_threshold}, liquidity=${min_liquidity_threshold}, "
            f"transactions={min_transaction_threshold}, activity_score={activity_threshold}"
        )
    
    def calculate_activity_score(self, pool_data: Dict[str, Any]) -> Decimal:
        """
        Calculate composite activity score for a pool.
        
        The score is calculated as a weighted combination of normalized metrics:
        - Volume score (0-100): Based on 24h trading volume
        - Transaction score (0-100): Based on 24h transaction count
        - Liquidity score (0-100): Based on available liquidity
        - Volatility score (0-100): Based on price change (if available)
        
        Args:
            pool_data: Dictionary containing pool metrics from API response
            
        Returns:
            Activity score between 0 and 100
            
        Raises:
            ValueError: If required metrics are missing or invalid
        """
        try:
            # Extract metrics from pool data
            metrics = self._extract_metrics(pool_data)
            
            # Calculate individual component scores
            volume_score = self._calculate_volume_score(metrics.volume_24h_usd)
            transaction_score = self._calculate_transaction_score(metrics.transaction_count_24h)
            liquidity_score = self._calculate_liquidity_score(metrics.liquidity_usd)
            volatility_score = self._calculate_volatility_score(metrics.price_change_24h)
            
            # Calculate weighted composite score
            composite_score = (
                volume_score * self.weights.volume_weight +
                transaction_score * self.weights.transaction_weight +
                liquidity_score * self.weights.liquidity_weight +
                volatility_score * self.weights.volatility_weight
            )
            
            # Ensure score is within bounds
            final_score = max(Decimal("0"), min(Decimal("100"), composite_score))
            
            logger.debug(
                f"Activity score calculated: {final_score:.2f} "
                f"(volume: {volume_score:.1f}, transactions: {transaction_score:.1f}, "
                f"liquidity: {liquidity_score:.1f}, volatility: {volatility_score:.1f})"
            )
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating activity score: {e}")
            raise ValueError(f"Failed to calculate activity score: {e}")
    
    def should_include_pool(self, pool_data: Dict[str, Any]) -> bool:
        """
        Determine if a pool meets inclusion criteria based on thresholds.
        
        A pool is included if it meets ALL of the following criteria:
        - 24h volume >= min_volume_threshold
        - Liquidity >= min_liquidity_threshold  
        - 24h transactions >= min_transaction_threshold
        - Activity score >= activity_threshold
        
        Args:
            pool_data: Dictionary containing pool metrics from API response
            
        Returns:
            True if pool should be included, False otherwise
        """
        try:
            # Extract metrics
            metrics = self._extract_metrics(pool_data)
            
            # Check basic thresholds
            if metrics.volume_24h_usd < self.min_volume_threshold:
                logger.debug(f"Pool excluded: volume {metrics.volume_24h_usd} < {self.min_volume_threshold}")
                return False
                
            if metrics.liquidity_usd < self.min_liquidity_threshold:
                logger.debug(f"Pool excluded: liquidity {metrics.liquidity_usd} < {self.min_liquidity_threshold}")
                return False
                
            if metrics.transaction_count_24h < self.min_transaction_threshold:
                logger.debug(f"Pool excluded: transactions {metrics.transaction_count_24h} < {self.min_transaction_threshold}")
                return False
            
            # Check activity score threshold
            activity_score = self.calculate_activity_score(pool_data)
            if activity_score < self.activity_threshold:
                logger.debug(f"Pool excluded: activity score {activity_score} < {self.activity_threshold}")
                return False
            
            logger.debug(f"Pool included: activity score {activity_score:.2f}")
            return True
            
        except Exception as e:
            logger.warning(f"Error evaluating pool inclusion: {e}")
            return False
    
    def get_collection_priority(self, activity_score: Decimal) -> CollectionPriority:
        """
        Map activity score to collection priority level.
        
        Priority mapping:
        - HIGH: score >= 75 (very active pools)
        - NORMAL: 50 <= score < 75 (moderately active pools)
        - LOW: 25 <= score < 50 (less active but viable pools)
        - PAUSED: score < 25 (inactive pools)
        
        Args:
            activity_score: Activity score between 0 and 100
            
        Returns:
            Collection priority level
        """
        if activity_score >= Decimal("75"):
            return CollectionPriority.HIGH
        elif activity_score >= Decimal("50"):
            return CollectionPriority.NORMAL
        elif activity_score >= Decimal("25"):
            return CollectionPriority.LOW
        else:
            return CollectionPriority.PAUSED
    
    def _extract_metrics(self, pool_data: Dict[str, Any]) -> ActivityMetrics:
        """
        Extract activity metrics from pool data dictionary.
        
        Args:
            pool_data: Raw pool data from API response
            
        Returns:
            ActivityMetrics object with extracted values
            
        Raises:
            ValueError: If required metrics are missing or invalid
        """
        try:
            # Handle different possible data structures from API
            attributes = pool_data.get("attributes", pool_data)
            
            # Extract volume (handle both string and numeric formats)
            volume_raw = attributes.get("volume_usd", {})
            if isinstance(volume_raw, dict):
                volume_24h = volume_raw.get("h24", "0")
            else:
                volume_24h = volume_raw or "0"
            
            # Extract transaction count
            transactions_raw = attributes.get("transactions", {})
            if isinstance(transactions_raw, dict):
                tx_count_24h = transactions_raw.get("h24", 0)
            else:
                tx_count_24h = transactions_raw or 0
            
            # Extract liquidity/reserve
            reserve_usd = attributes.get("reserve_in_usd", "0")
            
            # Extract price change (optional)
            price_change_raw = attributes.get("price_change_percentage", {})
            price_change_24h = None
            if isinstance(price_change_raw, dict):
                price_change_str = price_change_raw.get("h24")
                if price_change_str is not None:
                    price_change_24h = Decimal(str(price_change_str))
            
            # Convert to Decimal with proper error handling
            try:
                volume_24h_usd = Decimal(str(volume_24h)) if volume_24h else Decimal("0")
            except (ValueError, TypeError, Exception):
                volume_24h_usd = Decimal("0")
            
            try:
                liquidity_usd = Decimal(str(reserve_usd)) if reserve_usd else Decimal("0")
            except (ValueError, TypeError, Exception):
                liquidity_usd = Decimal("0")
            
            try:
                transaction_count_24h = int(tx_count_24h) if tx_count_24h else 0
            except (ValueError, TypeError, Exception):
                transaction_count_24h = 0
            
            return ActivityMetrics(
                volume_24h_usd=volume_24h_usd,
                transaction_count_24h=transaction_count_24h,
                liquidity_usd=liquidity_usd,
                price_change_24h=price_change_24h
            )
            
        except Exception as e:
            raise ValueError(f"Failed to extract metrics from pool data: {e}")
    
    def _calculate_volume_score(self, volume_24h_usd: Decimal) -> Decimal:
        """
        Calculate normalized volume score (0-100).
        
        Uses logarithmic scaling to handle wide range of volumes:
        - $0: score = 0
        - $1,000: score ≈ 20
        - $10,000: score ≈ 40
        - $100,000: score ≈ 60
        - $1,000,000: score ≈ 80
        - $10,000,000+: score ≈ 100
        """
        if volume_24h_usd <= 0:
            return Decimal("0")
        
        # Logarithmic scaling with base adjustment
        import math
        log_volume = Decimal(str(math.log10(float(volume_24h_usd))))
        
        # Scale: log10(1000) = 3 -> 20, log10(10M) = 7 -> 100
        score = (log_volume - Decimal("3")) * Decimal("20")
        
        return max(Decimal("0"), min(Decimal("100"), score))
    
    def _calculate_transaction_score(self, transaction_count_24h: int) -> Decimal:
        """
        Calculate normalized transaction score (0-100).
        
        Uses square root scaling for transaction counts:
        - 0 transactions: score = 0
        - 10 transactions: score ≈ 20
        - 100 transactions: score ≈ 63
        - 400 transactions: score ≈ 100
        """
        if transaction_count_24h <= 0:
            return Decimal("0")
        
        # Square root scaling
        import math
        sqrt_tx = Decimal(str(math.sqrt(transaction_count_24h)))
        
        # Scale: sqrt(400) = 20 -> 100
        score = sqrt_tx * Decimal("5")
        
        return max(Decimal("0"), min(Decimal("100"), score))
    
    def _calculate_liquidity_score(self, liquidity_usd: Decimal) -> Decimal:
        """
        Calculate normalized liquidity score (0-100).
        
        Uses logarithmic scaling similar to volume:
        - $0: score = 0
        - $5,000: score ≈ 20
        - $50,000: score ≈ 40
        - $500,000: score ≈ 60
        - $5,000,000: score ≈ 80
        - $50,000,000+: score ≈ 100
        """
        if liquidity_usd <= 0:
            return Decimal("0")
        
        # Logarithmic scaling with base adjustment for liquidity
        import math
        log_liquidity = Decimal(str(math.log10(float(liquidity_usd))))
        
        # Scale: log10(5000) ≈ 3.7 -> 20, log10(50M) ≈ 7.7 -> 100
        score = (log_liquidity - Decimal("3.7")) * Decimal("20")
        
        return max(Decimal("0"), min(Decimal("100"), score))
    
    def _calculate_volatility_score(self, price_change_24h: Optional[Decimal]) -> Decimal:
        """
        Calculate normalized volatility score (0-100).
        
        Higher volatility indicates more trading activity:
        - No price change data: score = 50 (neutral)
        - 0% change: score = 0
        - ±5% change: score ≈ 50
        - ±10% change: score ≈ 75
        - ±20%+ change: score = 100
        """
        if price_change_24h is None:
            return Decimal("50")  # Neutral score when data unavailable
        
        # Use absolute value of price change
        abs_change = abs(price_change_24h)
        
        # Linear scaling up to 20% change
        score = min(abs_change * Decimal("5"), Decimal("100"))
        
        return score