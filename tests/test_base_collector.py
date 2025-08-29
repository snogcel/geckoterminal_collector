"""
Unit tests for base collector interface and common functionality.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.base import BaseDataCollector, CollectorRegistry
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.config.models import CollectionConfig, ErrorConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.error_handling import (
    ErrorHandler, CircuitBreaker, CircuitBreakerOpenError, RetryConfig
)
from gecko_terminal_collector.utils.metadata import MetadataTracker


class MockDataCollector(BaseDataCollector):
    """Test implementation of BaseDataCollector for testing."""
    
    def __init__(self, *args, should_fail=False, fail_count=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.call_count = 0
    
    async def collect(self) -> CollectionResult:
        """Test implementation that can simulate success or failure."""
        self.call_count += 1
        
        if self.should_fail and self.call_count <= self.fail_count:
            raise ValueError(f"Simulated failure #{self.call_count}")
        
        return self.create_success_result(
            records_collected=10,
            collection_time=datetime.now()
        )
    
    def get_collection_key(self) -> str:
        return "test_collector"
    
    async def _validate_specific_data(self, data) -> ValidationResult:
        """Test-specific validation."""
        errors = []
        warnings = []
        
        if isinstance(data, dict) and data.get("invalid"):
            errors.append("Test validation error")
        
        if isinstance(data, dict) and data.get("warning"):
            warnings.append("Test validation warning")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


@pytest.fixture
def config():
    """Create test configuration."""
    return CollectionConfig(
        error_handling=ErrorConfig(
            max_retries=3,
            backoff_factor=2.0,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=300
        )
    )


@pytest.fixture
def db_manager():
    """Create mock database manager."""
    return MagicMock(spec=DatabaseManager)


@pytest.fixture
def metadata_tracker():
    """Create metadata tracker."""
    return MetadataTracker()


@pytest.fixture
def test_collector(config, db_manager, metadata_tracker):
    """Create test collector instance."""
    return MockDataCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=True
    )


class TestBaseDataCollector:
    """Test cases for BaseDataCollector."""
    
    def test_initialization(self, config, db_manager, metadata_tracker):
        """Test collector initialization."""
        collector = MockDataCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        assert collector.config == config
        assert collector.db_manager == db_manager
        assert collector.metadata_tracker == metadata_tracker
        assert collector.use_mock is True
        assert isinstance(collector.error_handler, ErrorHandler)
    
    def test_get_collection_key(self, test_collector):
        """Test collection key retrieval."""
        assert test_collector.get_collection_key() == "test_collector"
    
    @pytest.mark.asyncio
    async def test_successful_collection(self, test_collector):
        """Test successful data collection."""
        result = await test_collector.collect_with_error_handling()
        
        assert result.success is True
        assert result.records_collected == 10
        assert result.errors == []
        assert result.collector_type == "test_collector"
        assert isinstance(result.collection_time, datetime)
    
    @pytest.mark.asyncio
    async def test_failed_collection(self, config, db_manager, metadata_tracker):
        """Test failed data collection."""
        collector = MockDataCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True,
            should_fail=True,
            fail_count=5  # Fail more times than max retries
        )
        
        result = await collector.collect_with_error_handling()
        
        assert result.success is False
        assert result.records_collected == 0
        assert len(result.errors) > 0
        assert "Collection failed" in result.errors[0]
        assert result.collector_type == "test_collector"
    
    @pytest.mark.asyncio
    async def test_retry_logic_success(self, config, db_manager, metadata_tracker):
        """Test retry logic with eventual success."""
        collector = MockDataCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True,
            should_fail=True,
            fail_count=2  # Fail 2 times, then succeed
        )
        
        result = await collector.collect_with_error_handling()
        
        assert result.success is True
        assert result.records_collected == 10
        assert collector.call_count == 3  # 2 failures + 1 success
    
    @pytest.mark.asyncio
    async def test_data_validation_success(self, test_collector):
        """Test successful data validation."""
        data = {"valid": True}
        result = await test_collector.validate_data(data)
        
        assert result.is_valid is True
        assert result.errors == []
    
    @pytest.mark.asyncio
    async def test_data_validation_failure(self, test_collector):
        """Test data validation failure."""
        data = {"invalid": True}
        result = await test_collector.validate_data(data)
        
        assert result.is_valid is False
        assert "Test validation error" in result.errors
    
    @pytest.mark.asyncio
    async def test_data_validation_warning(self, test_collector):
        """Test data validation with warnings."""
        data = {"warning": True}
        result = await test_collector.validate_data(data)
        
        assert result.is_valid is True
        assert "Test validation warning" in result.warnings
    
    @pytest.mark.asyncio
    async def test_data_validation_none(self, test_collector):
        """Test validation of None data."""
        result = await test_collector.validate_data(None)
        
        assert result.is_valid is False
        assert "Data cannot be None" in result.errors
    
    @pytest.mark.asyncio
    async def test_data_validation_empty_list(self, test_collector):
        """Test validation of empty list."""
        result = await test_collector.validate_data([])
        
        assert result.is_valid is True
        assert "empty results" in result.warnings[0]
    
    def test_create_success_result(self, test_collector):
        """Test creation of success result."""
        result = test_collector.create_success_result(records_collected=5)
        
        assert result.success is True
        assert result.records_collected == 5
        assert result.errors == []
        assert result.collector_type == "test_collector"
    
    def test_create_failure_result(self, test_collector):
        """Test creation of failure result."""
        errors = ["Error 1", "Error 2"]
        result = test_collector.create_failure_result(errors=errors, records_collected=3)
        
        assert result.success is False
        assert result.records_collected == 3
        assert result.errors == errors
        assert result.collector_type == "test_collector"
    
    @pytest.mark.asyncio
    async def test_execute_with_retry(self, test_collector):
        """Test execute_with_retry method."""
        async def test_operation():
            return "success"
        
        result = await test_collector.execute_with_retry(
            test_operation,
            "test operation"
        )
        
        assert result == "success"
    
    def test_get_metadata(self, test_collector):
        """Test metadata retrieval."""
        metadata = test_collector.get_metadata()
        
        assert metadata.collector_type == "test_collector"
        assert metadata.total_runs == 0
    
    def test_get_circuit_breaker_status(self, test_collector):
        """Test circuit breaker status retrieval."""
        status = test_collector.get_circuit_breaker_status()
        
        assert isinstance(status, dict)


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    def test_initialization(self):
        """Test error handler initialization."""
        config = RetryConfig(max_retries=5, backoff_factor=3.0)
        handler = ErrorHandler(config)
        
        assert handler.retry_config.max_retries == 5
        assert handler.retry_config.backoff_factor == 3.0
    
    def test_get_circuit_breaker(self):
        """Test circuit breaker creation and retrieval."""
        handler = ErrorHandler()
        
        breaker1 = handler.get_circuit_breaker("test1")
        breaker2 = handler.get_circuit_breaker("test1")  # Same name
        breaker3 = handler.get_circuit_breaker("test2")  # Different name
        
        assert breaker1 is breaker2  # Same instance
        assert breaker1 is not breaker3  # Different instances
    
    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """Test retry logic with immediate success."""
        handler = ErrorHandler()
        
        async def success_operation():
            return "success"
        
        result = await handler.with_retry(success_operation, "test")
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_with_retry_eventual_success(self):
        """Test retry logic with eventual success."""
        handler = ErrorHandler(RetryConfig(max_retries=3, base_delay=0.01))
        call_count = 0
        
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await handler.with_retry(flaky_operation, "test")
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_with_retry_all_failures(self):
        """Test retry logic when all attempts fail."""
        handler = ErrorHandler(RetryConfig(max_retries=2, base_delay=0.01))
        
        async def failing_operation():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            await handler.with_retry(failing_operation, "test")
    
    @pytest.mark.asyncio
    async def test_with_circuit_breaker(self):
        """Test retry with circuit breaker."""
        handler = ErrorHandler()
        
        async def success_operation():
            return "success"
        
        result = await handler.with_retry(
            success_operation,
            "test",
            circuit_breaker_name="test_breaker"
        )
        assert result == "success"
    
    def test_handle_error_logging(self):
        """Test error handling and logging."""
        handler = ErrorHandler()
        
        # Test different error types
        with patch('gecko_terminal_collector.utils.error_handling.logger') as mock_logger:
            handler.handle_error(ConnectionError("Network error"), "test", "test_collector")
            mock_logger.warning.assert_called_once()
            
            handler.handle_error(ValueError("Data error"), "test", "test_collector")
            mock_logger.error.assert_called()


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60
        assert breaker.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful function call through circuit breaker."""
        breaker = CircuitBreaker()
        
        async def success_function():
            return "success"
        
        result = await breaker.call(success_function)
        assert result == "success"
        assert breaker.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        async def failing_function():
            raise ValueError("Test failure")
        
        # First failure
        with pytest.raises(ValueError):
            await breaker.call(failing_function)
        assert breaker.state.value == "closed"
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_function)
        assert breaker.state.value == "open"
        
        # Third call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_function)
    
    @pytest.mark.asyncio
    async def test_circuit_recovery(self):
        """Test circuit breaker recovery after timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_function():
            raise ValueError("Test failure")
        
        async def success_function():
            return "success"
        
        # Trigger circuit open
        with pytest.raises(ValueError):
            await breaker.call(failing_function)
        assert breaker.state.value == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half-open and then closed on success
        result = await breaker.call(success_function)
        assert result == "success"
        assert breaker.state.value == "closed"


class TestCollectorRegistry:
    """Test cases for CollectorRegistry."""
    
    def test_initialization(self):
        """Test registry initialization."""
        registry = CollectorRegistry()
        
        assert len(registry._collectors) == 0
        assert isinstance(registry.metadata_tracker, MetadataTracker)
    
    def test_register_collector(self, config, db_manager):
        """Test collector registration."""
        registry = CollectorRegistry()
        collector = MockDataCollector(config, db_manager, use_mock=True)
        
        registry.register(collector)
        
        assert len(registry._collectors) == 1
        assert registry.get_collector("test_collector") == collector
        assert collector.metadata_tracker == registry.metadata_tracker
    
    def test_get_collector_keys(self, config, db_manager):
        """Test getting all collector keys."""
        registry = CollectorRegistry()
        collector1 = MockDataCollector(config, db_manager, use_mock=True)
        
        # Create second collector with different key
        class TestCollector2(MockDataCollector):
            def get_collection_key(self):
                return "test_collector_2"
        
        collector2 = TestCollector2(config, db_manager, use_mock=True)
        
        registry.register(collector1)
        registry.register(collector2)
        
        keys = registry.get_collector_keys()
        assert "test_collector" in keys
        assert "test_collector_2" in keys
        assert len(keys) == 2
    
    def test_unregister_collector(self, config, db_manager):
        """Test collector unregistration."""
        registry = CollectorRegistry()
        collector = MockDataCollector(config, db_manager, use_mock=True)
        
        registry.register(collector)
        assert registry.get_collector("test_collector") is not None
        
        result = registry.unregister("test_collector")
        assert result is True
        assert registry.get_collector("test_collector") is None
        
        # Try to unregister non-existent collector
        result = registry.unregister("non_existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_collect_all_success(self, config, db_manager):
        """Test collecting from all registered collectors successfully."""
        registry = CollectorRegistry()
        collector = MockDataCollector(config, db_manager, use_mock=True)
        registry.register(collector)
        
        results = await registry.collect_all()
        
        assert len(results) == 1
        assert "test_collector" in results
        assert results["test_collector"].success is True
        assert results["test_collector"].records_collected == 10
    
    @pytest.mark.asyncio
    async def test_collect_all_with_failures(self, config, db_manager):
        """Test collecting from all collectors with some failures."""
        registry = CollectorRegistry()
        
        # Successful collector
        collector1 = MockDataCollector(config, db_manager, use_mock=True)
        
        # Failing collector
        class FailingCollector(MockDataCollector):
            def get_collection_key(self):
                return "failing_collector"
            
            async def collect(self):
                raise RuntimeError("Always fails")
        
        collector2 = FailingCollector(config, db_manager, use_mock=True)
        
        registry.register(collector1)
        registry.register(collector2)
        
        results = await registry.collect_all()
        
        assert len(results) == 2
        assert results["test_collector"].success is True
        assert results["failing_collector"].success is False
    
    def test_get_health_status(self, config, db_manager):
        """Test getting health status for all collectors."""
        registry = CollectorRegistry()
        collector = MockDataCollector(config, db_manager, use_mock=True)
        registry.register(collector)
        
        # Simulate some collection history
        metadata = registry.metadata_tracker.get_metadata("test_collector")
        metadata.total_runs = 10
        metadata.successful_runs = 9
        
        health_status = registry.get_health_status()
        
        assert "test_collector" in health_status
        assert health_status["test_collector"] is True  # 90% success rate
    
    def test_get_registry_summary(self, config, db_manager):
        """Test getting comprehensive registry summary."""
        registry = CollectorRegistry()
        collector = MockDataCollector(config, db_manager, use_mock=True)
        registry.register(collector)
        
        summary = registry.get_registry_summary()
        
        assert summary["total_collectors"] == 1
        assert "test_collector" in summary["registered_collectors"]
        assert "health_status" in summary
        assert "metadata_summary" in summary