"""
Unit tests for the ActivityScorer class.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch
from gecko_terminal_collector.utils.activity_scorer import (
    ActivityScorer,
    ActivityMetrics,
    ScoringWeights,
    CollectionPriority
)


class TestActivityMetrics:
    """Test cases for ActivityMetrics dataclass."""
    
    def test_valid_metrics_creation(self):
        """Test creating ActivityMetrics with valid data."""
        metrics = ActivityMetrics(
            volume_24h_usd=Decimal("10000"),
            transaction_count_24h=100,
            liquidity_usd=Decimal("50000")
        )
        
        assert metrics.volume_24h_usd == Decimal("10000")
        assert metrics.transaction_count_24h == 100
        assert metrics.liquidity_usd == Decimal("50000")
        assert metrics.price_change_24h is None
        assert metrics.market_cap_usd is None
    
    def test_metrics_with_optional_fields(self):
        """Test creating ActivityMetrics with optional fields."""
        metrics = ActivityMetrics(
            volume_24h_usd=Decimal("10000"),
            transaction_count_24h=100,
            liquidity_usd=Decimal("50000"),
            price_change_24h=Decimal("5.5"),
            market_cap_usd=Decimal("1000000")
        )
        
        assert metrics.price_change_24h == Decimal("5.5")
        assert metrics.market_cap_usd == Decimal("1000000")
    
    def test_negative_volume_raises_error(self):
        """Test that negative volume raises ValueError."""
        with pytest.raises(ValueError, match="Volume cannot be negative"):
            ActivityMetrics(
                volume_24h_usd=Decimal("-1000"),
                transaction_count_24h=100,
                liquidity_usd=Decimal("50000")
            )
    
    def test_negative_transaction_count_raises_error(self):
        """Test that negative transaction count raises ValueError."""
        with pytest.raises(ValueError, match="Transaction count cannot be negative"):
            ActivityMetrics(
                volume_24h_usd=Decimal("10000"),
                transaction_count_24h=-10,
                liquidity_usd=Decimal("50000")
            )
    
    def test_negative_liquidity_raises_error(self):
        """Test that negative liquidity raises ValueError."""
        with pytest.raises(ValueError, match="Liquidity cannot be negative"):
            ActivityMetrics(
                volume_24h_usd=Decimal("10000"),
                transaction_count_24h=100,
                liquidity_usd=Decimal("-50000")
            )


class TestScoringWeights:
    """Test cases for ScoringWeights dataclass."""
    
    def test_default_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        weights = ScoringWeights()
        total = weights.volume_weight + weights.transaction_weight + weights.liquidity_weight + weights.volatility_weight
        assert abs(total - Decimal("1.0")) < Decimal("0.001")
    
    def test_custom_valid_weights(self):
        """Test creating ScoringWeights with custom valid weights."""
        weights = ScoringWeights(
            volume_weight=Decimal("0.5"),
            transaction_weight=Decimal("0.3"),
            liquidity_weight=Decimal("0.15"),
            volatility_weight=Decimal("0.05")
        )
        
        total = weights.volume_weight + weights.transaction_weight + weights.liquidity_weight + weights.volatility_weight
        assert abs(total - Decimal("1.0")) < Decimal("0.001")
    
    def test_invalid_weights_sum_raises_error(self):
        """Test that weights not summing to 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Scoring weights must sum to 1.0"):
            ScoringWeights(
                volume_weight=Decimal("0.5"),
                transaction_weight=Decimal("0.3"),
                liquidity_weight=Decimal("0.3"),  # Total = 1.1
                volatility_weight=Decimal("0.1")
            )


class TestActivityScorer:
    """Test cases for ActivityScorer class."""
    
    def test_default_initialization(self):
        """Test ActivityScorer initialization with default parameters."""
        scorer = ActivityScorer()
        
        assert scorer.min_volume_threshold == Decimal("1000")
        assert scorer.min_liquidity_threshold == Decimal("5000")
        assert scorer.min_transaction_threshold == 10
        assert scorer.activity_threshold == Decimal("25")
        assert isinstance(scorer.weights, ScoringWeights)
    
    def test_custom_initialization(self):
        """Test ActivityScorer initialization with custom parameters."""
        custom_weights = ScoringWeights(
            volume_weight=Decimal("0.5"),
            transaction_weight=Decimal("0.25"),
            liquidity_weight=Decimal("0.2"),
            volatility_weight=Decimal("0.05")
        )
        
        scorer = ActivityScorer(
            min_volume_threshold=Decimal("5000"),
            min_liquidity_threshold=Decimal("10000"),
            min_transaction_threshold=50,
            activity_threshold=Decimal("40"),
            weights=custom_weights
        )
        
        assert scorer.min_volume_threshold == Decimal("5000")
        assert scorer.min_liquidity_threshold == Decimal("10000")
        assert scorer.min_transaction_threshold == 50
        assert scorer.activity_threshold == Decimal("40")
        assert scorer.weights == custom_weights
    
    def test_extract_metrics_from_pool_data(self):
        """Test extracting metrics from typical pool data structure."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "10000.50"},
                "transactions": {"h24": 150},
                "reserve_in_usd": "75000.25",
                "price_change_percentage": {"h24": "5.5"}
            }
        }
        
        scorer = ActivityScorer()
        metrics = scorer._extract_metrics(pool_data)
        
        assert metrics.volume_24h_usd == Decimal("10000.50")
        assert metrics.transaction_count_24h == 150
        assert metrics.liquidity_usd == Decimal("75000.25")
        assert metrics.price_change_24h == Decimal("5.5")
    
    def test_extract_metrics_flat_structure(self):
        """Test extracting metrics from flat pool data structure."""
        pool_data = {
            "volume_usd": {"h24": "5000"},
            "transactions": {"h24": 75},
            "reserve_in_usd": "25000"
        }
        
        scorer = ActivityScorer()
        metrics = scorer._extract_metrics(pool_data)
        
        assert metrics.volume_24h_usd == Decimal("5000")
        assert metrics.transaction_count_24h == 75
        assert metrics.liquidity_usd == Decimal("25000")
        assert metrics.price_change_24h is None
    
    def test_extract_metrics_missing_data(self):
        """Test extracting metrics when some data is missing."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": None},
                "transactions": {},
                "reserve_in_usd": ""
            }
        }
        
        scorer = ActivityScorer()
        metrics = scorer._extract_metrics(pool_data)
        
        assert metrics.volume_24h_usd == Decimal("0")
        assert metrics.transaction_count_24h == 0
        assert metrics.liquidity_usd == Decimal("0")
    
    def test_calculate_volume_score(self):
        """Test volume score calculation."""
        scorer = ActivityScorer()
        
        # Test zero volume
        assert scorer._calculate_volume_score(Decimal("0")) == Decimal("0")
        
        # Test various volume levels
        score_1k = scorer._calculate_volume_score(Decimal("1000"))
        score_10k = scorer._calculate_volume_score(Decimal("10000"))
        score_100k = scorer._calculate_volume_score(Decimal("100000"))
        
        # Higher volume should give higher score
        assert score_1k < score_10k < score_100k
        
        # All scores should be between 0 and 100
        assert 0 <= score_1k <= 100
        assert 0 <= score_10k <= 100
        assert 0 <= score_100k <= 100
    
    def test_calculate_transaction_score(self):
        """Test transaction score calculation."""
        scorer = ActivityScorer()
        
        # Test zero transactions
        assert scorer._calculate_transaction_score(0) == Decimal("0")
        
        # Test various transaction levels
        score_10 = scorer._calculate_transaction_score(10)
        score_100 = scorer._calculate_transaction_score(100)
        score_400 = scorer._calculate_transaction_score(400)
        
        # Higher transaction count should give higher score
        assert score_10 < score_100 < score_400
        
        # All scores should be between 0 and 100
        assert 0 <= score_10 <= 100
        assert 0 <= score_100 <= 100
        assert 0 <= score_400 <= 100
    
    def test_calculate_liquidity_score(self):
        """Test liquidity score calculation."""
        scorer = ActivityScorer()
        
        # Test zero liquidity
        assert scorer._calculate_liquidity_score(Decimal("0")) == Decimal("0")
        
        # Test various liquidity levels
        score_5k = scorer._calculate_liquidity_score(Decimal("5000"))
        score_50k = scorer._calculate_liquidity_score(Decimal("50000"))
        score_500k = scorer._calculate_liquidity_score(Decimal("500000"))
        
        # Higher liquidity should give higher score
        assert score_5k < score_50k < score_500k
        
        # All scores should be between 0 and 100
        assert 0 <= score_5k <= 100
        assert 0 <= score_50k <= 100
        assert 0 <= score_500k <= 100
    
    def test_calculate_volatility_score(self):
        """Test volatility score calculation."""
        scorer = ActivityScorer()
        
        # Test no price change data
        assert scorer._calculate_volatility_score(None) == Decimal("50")
        
        # Test zero change
        assert scorer._calculate_volatility_score(Decimal("0")) == Decimal("0")
        
        # Test positive and negative changes (should be same due to abs)
        score_pos = scorer._calculate_volatility_score(Decimal("10"))
        score_neg = scorer._calculate_volatility_score(Decimal("-10"))
        assert score_pos == score_neg
        
        # Test various volatility levels
        score_5 = scorer._calculate_volatility_score(Decimal("5"))
        score_10 = scorer._calculate_volatility_score(Decimal("10"))
        score_20 = scorer._calculate_volatility_score(Decimal("20"))
        
        # Higher volatility should give higher score
        assert score_5 < score_10 <= score_20
        
        # All scores should be between 0 and 100
        assert 0 <= score_5 <= 100
        assert 0 <= score_10 <= 100
        assert 0 <= score_20 <= 100
    
    def test_calculate_activity_score_integration(self):
        """Test complete activity score calculation."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "50000"},
                "transactions": {"h24": 200},
                "reserve_in_usd": "100000",
                "price_change_percentage": {"h24": "8.5"}
            }
        }
        
        scorer = ActivityScorer()
        score = scorer.calculate_activity_score(pool_data)
        
        # Score should be a valid decimal between 0 and 100
        assert isinstance(score, Decimal)
        assert 0 <= score <= 100
    
    def test_should_include_pool_meets_all_criteria(self):
        """Test pool inclusion when all criteria are met."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "10000"},  # Above 1000 threshold
                "transactions": {"h24": 50},      # Above 10 threshold
                "reserve_in_usd": "50000",        # Above 5000 threshold
                "price_change_percentage": {"h24": "5"}
            }
        }
        
        scorer = ActivityScorer()
        
        # Mock the activity score to be above threshold
        with patch.object(scorer, 'calculate_activity_score', return_value=Decimal("30")):
            assert scorer.should_include_pool(pool_data) is True
    
    def test_should_include_pool_low_volume(self):
        """Test pool exclusion due to low volume."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "500"},     # Below 1000 threshold
                "transactions": {"h24": 50},
                "reserve_in_usd": "50000"
            }
        }
        
        scorer = ActivityScorer()
        assert scorer.should_include_pool(pool_data) is False
    
    def test_should_include_pool_low_liquidity(self):
        """Test pool exclusion due to low liquidity."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "10000"},
                "transactions": {"h24": 50},
                "reserve_in_usd": "2000"          # Below 5000 threshold
            }
        }
        
        scorer = ActivityScorer()
        assert scorer.should_include_pool(pool_data) is False
    
    def test_should_include_pool_low_transactions(self):
        """Test pool exclusion due to low transaction count."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "10000"},
                "transactions": {"h24": 5},       # Below 10 threshold
                "reserve_in_usd": "50000"
            }
        }
        
        scorer = ActivityScorer()
        assert scorer.should_include_pool(pool_data) is False
    
    def test_should_include_pool_low_activity_score(self):
        """Test pool exclusion due to low activity score."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "10000"},
                "transactions": {"h24": 50},
                "reserve_in_usd": "50000"
            }
        }
        
        scorer = ActivityScorer()
        
        # Mock the activity score to be below threshold
        with patch.object(scorer, 'calculate_activity_score', return_value=Decimal("20")):
            assert scorer.should_include_pool(pool_data) is False
    
    def test_get_collection_priority_mapping(self):
        """Test collection priority mapping based on activity scores."""
        scorer = ActivityScorer()
        
        # Test HIGH priority
        assert scorer.get_collection_priority(Decimal("85")) == CollectionPriority.HIGH
        assert scorer.get_collection_priority(Decimal("75")) == CollectionPriority.HIGH
        
        # Test NORMAL priority
        assert scorer.get_collection_priority(Decimal("65")) == CollectionPriority.NORMAL
        assert scorer.get_collection_priority(Decimal("50")) == CollectionPriority.NORMAL
        
        # Test LOW priority
        assert scorer.get_collection_priority(Decimal("35")) == CollectionPriority.LOW
        assert scorer.get_collection_priority(Decimal("25")) == CollectionPriority.LOW
        
        # Test PAUSED priority
        assert scorer.get_collection_priority(Decimal("15")) == CollectionPriority.PAUSED
        assert scorer.get_collection_priority(Decimal("0")) == CollectionPriority.PAUSED
    
    def test_error_handling_invalid_pool_data(self):
        """Test error handling with invalid pool data."""
        scorer = ActivityScorer()
        
        # Test with completely empty data - should handle gracefully
        score = scorer.calculate_activity_score({})
        assert isinstance(score, Decimal)
        # Score should be 5.0 (volatility neutral score of 50 * 0.1 weight)
        assert score == Decimal("5.0")
        
        # Test should_include_pool returns False on error
        assert scorer.should_include_pool({}) is False
    
    def test_error_handling_malformed_metrics(self):
        """Test error handling with malformed metric values."""
        pool_data = {
            "attributes": {
                "volume_usd": {"h24": "invalid"},
                "transactions": {"h24": "not_a_number"},
                "reserve_in_usd": None
            }
        }
        
        scorer = ActivityScorer()
        metrics = scorer._extract_metrics(pool_data)
        
        # Should default to safe values
        assert metrics.volume_24h_usd == Decimal("0")
        assert metrics.transaction_count_24h == 0
        assert metrics.liquidity_usd == Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__])