"""
Tests for the comprehensive error handling framework.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from gecko_terminal_collector.utils.error_handling import (
    ErrorHandler, RetryConfig, CircuitBreaker, CircuitBreakerState,
    CircuitBreakerOpenError
)
from gecko_terminal_collector.utils.error_classification import (
    ErrorClassifier, ErrorContext, ErrorCategory, ErrorSeverity,
    RecoveryAction, error_classifier
)
from gecko_terminal_collector.utils.resilience import (
    HealthChecker, SystemMonitor, GracefulShutdownHandler,
    HealthStatus, ComponentType
)
from gecko_terminal_collector.utils.structured_logging import (
    logging_manager, get_logger, LogContext, CorrelationIdFilter
)


class TestErrorClassification:
    """Test error classification and recovery strategies."""
    
    def test_error_classifier_initialization(self):
        """Test error classifier initializes with default rules."""
        classifier = ErrorClassifier()
        
        # Check that default classifications are set up
        assert ConnectionError in classifier._classification_rules
        assert TimeoutError in classifier._classification_rules
        assert "rate limit" in classifier._message_patterns
        assert "429" in classifier._message_patterns
    
    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        classifier = ErrorClassifier()
        
        error_context = ErrorContext(
            error=ConnectionError("Connection failed"),
            operation="test_operation",
            collector_type="test_collector",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        classification = classifier.classify_error(error_context)
        
        assert classification.category == ErrorCategory.NETWORK
        assert classification.severity == ErrorSeverity.MEDIUM
        assert classification.recovery_action == RecoveryAction.RETRY_WITH_BACKOFF
        assert classification.retry_eligible is True
        assert classification.circuit_breaker_eligible is True
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        classifier = ErrorClassifier()
        
        error_context = ErrorContext(
            error=Exception("Rate limit exceeded"),
            operation="api_call",
            collector_type="api_collector",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        classification = classifier.classify_error(error_context)
        
        assert classification.category == ErrorCategory.API_RATE_LIMIT
        assert classification.severity == ErrorSeverity.HIGH
        assert classification.recovery_action == RecoveryAction.RETRY_WITH_BACKOFF
        assert classification.cooldown_period == 900  # 15 minutes
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        classifier = ErrorClassifier()
        
        class CustomError(Exception):
            pass
        
        error_context = ErrorContext(
            error=CustomError("Unknown error"),
            operation="test_operation",
            collector_type="test_collector",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        classification = classifier.classify_error(error_context)
        
        assert classification.category == ErrorCategory.UNKNOWN
        assert classification.severity == ErrorSeverity.MEDIUM
        assert classification.recovery_action == RecoveryAction.RETRY_WITH_BACKOFF
    
    def test_register_custom_classification(self):
        """Test registering custom error classifications."""
        classifier = ErrorClassifier()
        
        from gecko_terminal_collector.utils.error_classification import ErrorClassification
        
        custom_classification = ErrorClassification(
            category=ErrorCategory.DATA_VALIDATION,
            severity=ErrorSeverity.LOW,
            recovery_action=RecoveryAction.SKIP_AND_CONTINUE,
            retry_eligible=False,
            circuit_breaker_eligible=False
        )
        
        classifier.register_classification(ValueError, custom_classification)
        
        error_context = ErrorContext(
            error=ValueError("Invalid data"),
            operation="validation",
            collector_type="validator",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        classification = classifier.classify_error(error_context)
        assert classification.category == ErrorCategory.DATA_VALIDATION
        assert classification.recovery_action == RecoveryAction.SKIP_AND_CONTINUE


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker with successful operations."""
        breaker = CircuitBreaker()
        
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        async def failing_func():
            raise Exception("Test failure")
        
        # First failure
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker._failure_count == 2
        
        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # Trigger circuit open
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half-open and then closed on success
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker._failure_count == 0


class TestErrorHandler:
    """Test enhanced error handler functionality."""
    
    def test_error_handler_initialization(self):
        """Test error handler initializes correctly."""
        retry_config = RetryConfig(max_retries=3, base_delay=1.0)
        handler = ErrorHandler(retry_config)
        
        assert handler.retry_config.max_retries == 3
        assert handler.retry_config.base_delay == 1.0
        assert isinstance(handler.error_classifier, ErrorClassifier)
        assert len(handler._circuit_breakers) == 0
        assert len(handler._error_history) == 0
    
    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """Test retry mechanism with successful operation."""
        handler = ErrorHandler()
        
        async def success_func():
            return "success"
        
        result = await handler.with_retry(
            success_func,
            context="test_operation",
            collector_type="test_collector"
        )
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_with_retry_eventual_success(self):
        """Test retry mechanism with eventual success."""
        handler = ErrorHandler(RetryConfig(max_retries=3, base_delay=0.01))
        
        call_count = 0
        
        async def eventually_success_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await handler.with_retry(
            eventually_success_func,
            context="test_operation",
            collector_type="test_collector"
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_with_retry_fail_fast_error(self):
        """Test retry mechanism with fail-fast error."""
        handler = ErrorHandler()
        
        async def auth_error_func():
            raise Exception("401 Unauthorized")
        
        with pytest.raises(Exception, match="401 Unauthorized"):
            await handler.with_retry(
                auth_error_func,
                context="api_call",
                collector_type="api_collector"
            )
    
    @pytest.mark.asyncio
    async def test_with_retry_skip_and_continue(self):
        """Test retry mechanism with skip and continue error."""
        handler = ErrorHandler()
        
        async def validation_error_func():
            raise ValueError("Invalid data")
        
        result = await handler.with_retry(
            validation_error_func,
            context="validation",
            collector_type="validator"
        )
        
        assert result is None  # Should return None for skip and continue
    
    def test_error_statistics(self):
        """Test error statistics collection."""
        handler = ErrorHandler()
        
        # Simulate some errors
        error_context1 = ErrorContext(
            error=ConnectionError("Connection failed"),
            operation="test_op1",
            collector_type="collector1",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        error_context2 = ErrorContext(
            error=ValueError("Invalid data"),
            operation="test_op2",
            collector_type="collector2",
            timestamp=datetime.now(),
            attempt_number=1,
            additional_context={}
        )
        
        handler._record_error(error_context1)
        handler._record_error(error_context2)
        
        stats = handler.get_error_statistics()
        
        assert stats["total_operations"] == 2
        assert stats["total_errors"] == 2
        assert "network" in stats["error_by_category"]
        assert "data_validation" in stats["error_by_category"]
        assert len(stats["recent_errors"]) == 2
    
    def test_health_score_calculation(self):
        """Test health score calculation."""
        handler = ErrorHandler()
        
        # No errors should give perfect health score
        assert handler.get_health_score() == 1.0
        
        # Add some errors
        for i in range(5):
            error_context = ErrorContext(
                error=ConnectionError("Connection failed"),
                operation=f"test_op_{i}",
                collector_type="test_collector",
                timestamp=datetime.now(),
                attempt_number=1,
                additional_context={}
            )
            handler._record_error(error_context)
        
        health_score = handler.get_health_score()
        assert 0.0 <= health_score <= 1.0
        assert health_score < 1.0  # Should be less than perfect due to errors


class TestHealthChecker:
    """Test health checking functionality."""
    
    def test_health_checker_initialization(self):
        """Test health checker initializes with default checks."""
        checker = HealthChecker()
        
        assert "system_memory" in checker._health_checks
        assert "system_disk" in checker._health_checks
        assert len(checker._health_history) >= 2  # At least memory and disk
    
    @pytest.mark.asyncio
    async def test_memory_health_check(self):
        """Test memory health check."""
        checker = HealthChecker()
        
        result = await checker._check_memory_health()
        
        assert result.component_name == "system_memory"
        assert result.component_type == ComponentType.MEMORY
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
        assert "memory usage" in result.message.lower()
        assert "memory_percent" in result.metadata
    
    @pytest.mark.asyncio
    async def test_disk_health_check(self):
        """Test disk health check."""
        checker = HealthChecker()
        
        result = await checker._check_disk_health()
        
        assert result.component_name == "system_disk"
        assert result.component_type == ComponentType.DISK
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
        assert "disk usage" in result.message.lower()
        assert "disk_percent" in result.metadata
    
    @pytest.mark.asyncio
    async def test_custom_health_check_registration(self):
        """Test registering custom health checks."""
        checker = HealthChecker()
        
        async def custom_check():
            from gecko_terminal_collector.utils.resilience import HealthCheckResult
            return HealthCheckResult(
                component_name="custom_component",
                component_type=ComponentType.API_CLIENT,
                status=HealthStatus.HEALTHY,
                message="Custom check passed",
                timestamp=datetime.now(),
                response_time_ms=10.0
            )
        
        checker.register_health_check(
            "custom_component",
            custom_check,
            ComponentType.API_CLIENT
        )
        
        results = await checker.check_health("custom_component")
        
        assert "custom_component" in results
        assert results["custom_component"].status == HealthStatus.HEALTHY
        assert results["custom_component"].message == "Custom check passed"
    
    def test_health_summary(self):
        """Test health summary generation."""
        checker = HealthChecker()
        
        # Add some mock health results
        from gecko_terminal_collector.utils.resilience import HealthCheckResult
        
        healthy_result = HealthCheckResult(
            component_name="test_healthy",
            component_type=ComponentType.API_CLIENT,
            status=HealthStatus.HEALTHY,
            message="All good",
            timestamp=datetime.now(),
            response_time_ms=50.0
        )
        
        unhealthy_result = HealthCheckResult(
            component_name="test_unhealthy",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.CRITICAL,
            message="Connection failed",
            timestamp=datetime.now(),
            response_time_ms=0.0
        )
        
        checker._health_history["test_healthy"] = [healthy_result]
        checker._health_history["test_unhealthy"] = [unhealthy_result]
        
        summary = checker.get_health_summary()
        
        assert summary["overall_status"] == HealthStatus.CRITICAL.value
        assert summary["healthy_components"] == 1
        assert summary["critical_components"] == 1
        assert "test_healthy" in summary["components"]
        assert "test_unhealthy" in summary["components"]


class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_logging_manager_setup(self):
        """Test logging manager setup."""
        # Reset logging manager state
        logging_manager._configured = False
        
        logging_manager.setup_logging(
            log_level="DEBUG",
            console_output=True,
            structured_format=True
        )
        
        assert logging_manager._configured is True
        stats = logging_manager.get_log_stats()
        assert stats["configured"] is True
        assert "console" in stats["handlers"]
    
    def test_correlation_id_management(self):
        """Test correlation ID management."""
        # Test creating correlation ID
        corr_id = logging_manager.create_correlation_id()
        assert isinstance(corr_id, str)
        assert len(corr_id) > 0
        
        # Test setting and getting correlation ID
        logging_manager.set_correlation_id(corr_id)
        assert logging_manager.get_correlation_id() == corr_id
        
        # Test clearing correlation ID
        logging_manager.clear_correlation_id()
        assert logging_manager.get_correlation_id() is None
    
    def test_contextual_logger(self):
        """Test contextual logger functionality."""
        context = LogContext(
            collector_type="test_collector",
            operation="test_operation",
            pool_id="test_pool"
        )
        
        logger = get_logger("test_logger", context)
        
        assert logger.context.collector_type == "test_collector"
        assert logger.context.operation == "test_operation"
        assert logger.context.pool_id == "test_pool"
        
        # Test context updates
        new_logger = logger.with_context(operation="new_operation")
        assert new_logger.context.operation == "new_operation"
        assert new_logger.context.collector_type == "test_collector"  # Should be preserved
    
    def test_correlation_id_filter(self):
        """Test correlation ID filter."""
        import logging
        
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Test with no correlation ID
        result = filter_instance.filter(record)
        assert result is True
        assert record.correlation_id == "unknown"
        
        # Test with correlation ID set
        logging_manager.set_correlation_id("test-correlation-id")
        result = filter_instance.filter(record)
        assert result is True
        assert record.correlation_id == "test-correlation-id"


class TestGracefulShutdown:
    """Test graceful shutdown functionality."""
    
    def test_shutdown_handler_initialization(self):
        """Test shutdown handler initializes correctly."""
        handler = GracefulShutdownHandler(shutdown_timeout=30)
        
        assert handler.shutdown_timeout == 30
        assert len(handler._shutdown_callbacks) == 0
        assert handler._is_shutting_down is False
    
    def test_register_shutdown_callback(self):
        """Test registering shutdown callbacks."""
        handler = GracefulShutdownHandler()
        
        def test_callback():
            pass
        
        handler.register_shutdown_callback(test_callback)
        
        assert len(handler._shutdown_callbacks) == 1
        assert test_callback in handler._shutdown_callbacks
    
    @pytest.mark.asyncio
    async def test_shutdown_execution(self):
        """Test shutdown execution with callbacks."""
        handler = GracefulShutdownHandler()
        
        callback_executed = False
        
        async def async_callback():
            nonlocal callback_executed
            callback_executed = True
        
        handler.register_shutdown_callback(async_callback)
        
        await handler.shutdown()
        
        assert callback_executed is True
        assert handler.is_shutting_down is True


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from gecko_terminal_collector.config.models import CollectionConfig, ErrorConfig
    
    config = CollectionConfig()
    config.error_handling = ErrorConfig(
        max_retries=3,
        backoff_factor=2.0,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300
    )
    
    return config


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing."""
    mock = AsyncMock()
    mock.get_session = AsyncMock()
    mock.initialize = AsyncMock()
    mock.close_all_connections = AsyncMock()
    return mock


class TestIntegration:
    """Integration tests for error handling framework."""
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_config):
        """Test integration of error handling components."""
        from gecko_terminal_collector.utils.error_handling import RetryConfig
        
        retry_config = RetryConfig(
            max_retries=mock_config.error_handling.max_retries,
            base_delay=1.0,
            backoff_factor=mock_config.error_handling.backoff_factor,
            jitter=True
        )
        
        error_handler = ErrorHandler(retry_config)
        
        # Test with various error types
        call_count = 0
        
        async def mixed_errors_func():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise ConnectionError("Network error")
            elif call_count == 2:
                raise Exception("Rate limit exceeded")
            else:
                return "success"
        
        result = await error_handler.with_retry(
            mixed_errors_func,
            context="integration_test",
            collector_type="test_collector"
        )
        
        assert result == "success"
        assert call_count == 3
        
        # Check error statistics
        stats = error_handler.get_error_statistics()
        assert stats["total_errors"] == 2
        assert "network" in stats["error_by_category"]
        assert "api_rate_limit" in stats["error_by_category"]
    
    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, mock_db_manager):
        """Test integration of health monitoring components."""
        from gecko_terminal_collector.monitoring.health_endpoints import SystemHealthEndpoints
        
        health_endpoints = SystemHealthEndpoints(db_manager=mock_db_manager)
        
        # Test health status
        health_status = await health_endpoints.get_health_status()
        
        assert "timestamp" in health_status
        assert "overall_status" in health_status
        assert "components" in health_status
        assert "system_metrics" in health_status
        
        # Test readiness status
        readiness = await health_endpoints.get_readiness_status()
        
        assert "ready" in readiness
        assert "status" in readiness
        assert "checked_components" in readiness