"""
Tests for the comprehensive error handling framework.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from gecko_terminal_collector.utils.error_handler import (
    ErrorHandler,
    ErrorType,
    ErrorSeverity,
    ErrorContext,
    RecoveryResult,
    RateLimitRecoveryStrategy,
    DataValidationRecoveryStrategy,
    DatabaseRecoveryStrategy,
    handle_errors
)


class TestErrorClassification:
    """Test error classification functionality."""
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        handler = ErrorHandler()
        
        # Test 429 error
        error = Exception("HTTP 429: Too Many Requests")
        error_type = handler.classify_error(error)
        assert error_type == ErrorType.API_RATE_LIMIT
        
        # Test rate limit text
        error = Exception("Rate limit exceeded")
        error_type = handler.classify_error(error)
        assert error_type == ErrorType.API_RATE_LIMIT
    
    def test_classify_api_errors(self):
        """Test classification of various API errors."""
        handler = ErrorHandler()
        
        # Test authentication errors
        error = Exception("HTTP 401: Unauthorized")
        assert handler.classify_error(error) == ErrorType.API_AUTHENTICATION
        
        error = Exception("HTTP 403: Forbidden")
        assert handler.classify_error(error) == ErrorType.API_AUTHENTICATION
        
        # Test server errors
        error = Exception("HTTP 500: Internal Server Error")
        assert handler.classify_error(error) == ErrorType.API_SERVER_ERROR
        
        error = Exception("HTTP 502: Bad Gateway")
        assert handler.classify_error(error) == ErrorType.API_SERVER_ERROR
        
        # Test timeout errors
        error = Exception("API timeout occurred")
        assert handler.classify_error(error) == ErrorType.API_TIMEOUT
        
        # Test connection errors
        error = Exception("API connection failed")
        assert handler.classify_error(error) == ErrorType.API_CONNECTION
    
    def test_classify_data_errors(self):
        """Test classification of data-related errors."""
        handler = ErrorHandler()
        
        # Test validation errors
        error = Exception("Data validation failed")
        assert handler.classify_error(error) == ErrorType.DATA_VALIDATION
        
        error = Exception("Invalid data format")
        assert handler.classify_error(error) == ErrorType.DATA_VALIDATION
        
        # Test parsing errors
        error = Exception("JSON parse error")
        assert handler.classify_error(error) == ErrorType.DATA_PARSING
        
        error = Exception("Failed to parse response")
        assert handler.classify_error(error) == ErrorType.DATA_PARSING
    
    def test_classify_database_errors(self):
        """Test classification of database errors."""
        handler = ErrorHandler()
        
        # Test database connection errors
        error = Exception("Database connection failed")
        assert handler.classify_error(error) == ErrorType.DATABASE_CONNECTION
        
        error = Exception("SQL connection timeout")
        assert handler.classify_error(error) == ErrorType.DATABASE_TIMEOUT
        
        # Test constraint errors
        error = Exception("Integrity constraint violation")
        assert handler.classify_error(error) == ErrorType.DATABASE_CONSTRAINT
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        handler = ErrorHandler()
        
        error = Exception("Some unknown error")
        assert handler.classify_error(error) == ErrorType.UNKNOWN


class TestSeverityDetermination:
    """Test error severity determination."""
    
    def test_critical_severity(self):
        """Test critical severity errors."""
        handler = ErrorHandler()
        
        assert handler.determine_severity(ErrorType.API_AUTHENTICATION) == ErrorSeverity.CRITICAL
        assert handler.determine_severity(ErrorType.CONFIGURATION) == ErrorSeverity.CRITICAL
    
    def test_high_severity(self):
        """Test high severity errors."""
        handler = ErrorHandler()
        
        assert handler.determine_severity(ErrorType.DATABASE_CONNECTION) == ErrorSeverity.HIGH
        assert handler.determine_severity(ErrorType.SYSTEM_RESOURCE) == ErrorSeverity.HIGH
    
    def test_medium_severity_escalation(self):
        """Test medium severity errors that escalate to high."""
        handler = ErrorHandler()
        
        # Normal medium severity
        assert handler.determine_severity(ErrorType.API_RATE_LIMIT) == ErrorSeverity.MEDIUM
        
        # Escalated to high due to retry count
        context = {"retry_count": 3}
        assert handler.determine_severity(ErrorType.API_RATE_LIMIT, context) == ErrorSeverity.HIGH
    
    def test_low_severity(self):
        """Test low severity errors."""
        handler = ErrorHandler()
        
        assert handler.determine_severity(ErrorType.UNKNOWN) == ErrorSeverity.LOW


class TestRateLimitRecoveryStrategy:
    """Test rate limit recovery strategy."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_recovery_success(self):
        """Test successful rate limit recovery."""
        strategy = RateLimitRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.API_RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            message="Rate limit exceeded",
            details={"retry_after": 60},
            retry_count=1,
            max_retries=3
        )
        
        result = await strategy.recover(context, Exception("Rate limit"))
        
        assert result.success is True
        assert result.retry_after is not None
        assert result.retry_after > 60  # Should include backoff and jitter
        assert result.should_alert is False  # Not enough retries yet
    
    @pytest.mark.asyncio
    async def test_rate_limit_recovery_alert_threshold(self):
        """Test rate limit recovery alert generation."""
        strategy = RateLimitRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.API_RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            message="Rate limit exceeded",
            details={"retry_after": 60},
            retry_count=2,  # Should trigger alert
            max_retries=3
        )
        
        result = await strategy.recover(context, Exception("Rate limit"))
        
        assert result.success is True
        assert result.should_alert is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_recovery_max_retries(self):
        """Test rate limit recovery at max retries."""
        strategy = RateLimitRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.API_RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            message="Rate limit exceeded",
            details={"retry_after": 60},
            retry_count=3,  # At max retries
            max_retries=3
        )
        
        result = await strategy.recover(context, Exception("Rate limit"))
        
        assert result.success is False


class TestDataValidationRecoveryStrategy:
    """Test data validation recovery strategy."""
    
    @pytest.mark.asyncio
    async def test_partial_success_recovery(self):
        """Test partial success data validation recovery."""
        strategy = DataValidationRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.DATA_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Some data invalid",
            details={
                "valid_data": [{"id": 1}, {"id": 2}],
                "invalid_data": [{"id": "invalid"}]
            }
        )
        
        result = await strategy.recover(context, Exception("Validation failed"))
        
        assert result.success is True
        assert result.partial_success is True
        assert result.recovered_data == [{"id": 1}, {"id": 2}]
        assert result.should_alert is False  # Less than 10% invalid
    
    @pytest.mark.asyncio
    async def test_high_invalid_rate_alert(self):
        """Test alert generation for high invalid data rate."""
        strategy = DataValidationRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.DATA_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Many records invalid",
            details={
                "valid_data": [{"id": 1}],
                "invalid_data": [{"id": "invalid1"}, {"id": "invalid2"}]  # >10% invalid
            }
        )
        
        result = await strategy.recover(context, Exception("Validation failed"))
        
        assert result.success is True
        assert result.partial_success is True
        assert result.should_alert is True
    
    @pytest.mark.asyncio
    async def test_complete_validation_failure(self):
        """Test complete validation failure."""
        strategy = DataValidationRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.DATA_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="All data invalid",
            details={
                "valid_data": [],
                "invalid_data": [{"id": "invalid1"}, {"id": "invalid2"}]
            }
        )
        
        result = await strategy.recover(context, Exception("Validation failed"))
        
        assert result.success is False
        assert result.should_alert is True


class TestDatabaseRecoveryStrategy:
    """Test database recovery strategy."""
    
    @pytest.mark.asyncio
    async def test_database_recovery_retry(self):
        """Test database recovery with retry."""
        strategy = DatabaseRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.DATABASE_CONNECTION,
            severity=ErrorSeverity.HIGH,
            message="Connection failed",
            retry_count=1,
            max_retries=3,
            backoff_seconds=2.0
        )
        
        result = await strategy.recover(context, Exception("DB connection failed"))
        
        assert result.success is True
        assert result.retry_after == 4.0  # 2 * (2^1)
        assert result.should_alert is False  # Not enough retries yet
    
    @pytest.mark.asyncio
    async def test_database_recovery_max_retries(self):
        """Test database recovery at max retries."""
        strategy = DatabaseRecoveryStrategy()
        
        context = ErrorContext(
            error_type=ErrorType.DATABASE_CONNECTION,
            severity=ErrorSeverity.HIGH,
            message="Connection failed",
            retry_count=3,  # At max retries
            max_retries=3
        )
        
        result = await strategy.recover(context, Exception("DB connection failed"))
        
        assert result.success is False
        assert result.should_alert is True


class TestErrorHandler:
    """Test the main ErrorHandler class."""
    
    @pytest.mark.asyncio
    async def test_handle_error_with_recovery(self):
        """Test error handling with successful recovery."""
        mock_db = AsyncMock()
        handler = ErrorHandler(mock_db)
        
        # Mock a rate limit error
        error = Exception("HTTP 429: Too Many Requests")
        
        result = await handler.handle_error(
            error,
            component="test_collector",
            operation="collect_data",
            context={"retry_after": 30},
            max_retries=3
        )
        
        assert result.success is True
        assert result.retry_after is not None
        assert "Rate limit recovery" in result.message
    
    @pytest.mark.asyncio
    async def test_handle_error_with_alert_creation(self):
        """Test error handling with system alert creation."""
        mock_db = AsyncMock()
        handler = ErrorHandler(mock_db)
        
        # Mock a critical error
        error = Exception("HTTP 401: Unauthorized")
        
        result = await handler.handle_error(
            error,
            component="test_collector",
            operation="collect_data",
            max_retries=3
        )
        
        assert result.success is False
        assert result.should_alert is True
        
        # Verify alert creation was called
        mock_db.create_system_alert.assert_called_once()
        
        # Check alert data
        call_args = mock_db.create_system_alert.call_args[0][0]
        assert call_args["level"] == "critical"
        assert call_args["collector_type"] == "test_collector"
        assert "unauthorized" in call_args["message"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_error_no_strategy(self):
        """Test error handling when no recovery strategy is available."""
        handler = ErrorHandler()
        
        # Mock an unknown error type
        error = Exception("Some unknown error")
        
        result = await handler.handle_error(
            error,
            component="test_collector",
            operation="collect_data"
        )
        
        assert result.success is False
        assert "No recovery strategy" in result.message
    
    def test_generate_actionable_messages(self):
        """Test generation of actionable error messages."""
        handler = ErrorHandler()
        
        # Test rate limit message
        context = ErrorContext(
            error_type=ErrorType.API_RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            message="Rate limit exceeded",
            component="test_collector",
            operation="collect_data"
        )
        
        message = handler._generate_actionable_message(context)
        assert "Reduce API call frequency" in message
        
        # Test authentication message
        context.error_type = ErrorType.API_AUTHENTICATION
        message = handler._generate_actionable_message(context)
        assert "Check API credentials" in message
        
        # Test data validation message
        context.error_type = ErrorType.DATA_VALIDATION
        context.details = {"invalid_data": [1, 2, 3]}
        message = handler._generate_actionable_message(context)
        assert "Review data quality" in message
        assert "3 invalid records" in message
    
    def test_error_statistics(self):
        """Test error statistics tracking."""
        handler = ErrorHandler()
        
        # Simulate some errors
        handler.error_counts = {
            "collector1.operation1.api_rate_limit": 5,
            "collector1.operation2.data_validation": 3,
            "collector2.operation1.database_connection": 2,
        }
        
        stats = handler.get_error_statistics()
        
        assert stats["total_errors"] == 10
        assert len(stats["error_breakdown"]) == 3
        assert stats["most_frequent_errors"][0][1] == 5  # Highest count first


class TestErrorHandlerDecorator:
    """Test the error handler decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful function execution."""
        
        @handle_errors(component="test_component", operation="test_operation")
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_retry(self):
        """Test decorator with retry on recoverable error."""
        call_count = 0
        
        @handle_errors(component="test_component", max_retries=2)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTTP 429: Rate limit")
            return "success_after_retry"
        
        # Mock the sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_function()
        
        assert result == "success_after_retry"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_decorator_partial_success(self):
        """Test decorator with partial success recovery."""
        
        @handle_errors(component="test_component")
        async def test_function():
            # Simulate a validation error with partial success
            error = Exception("Validation failed")
            # This would normally be handled by the error handler
            # For testing, we'll simulate the partial success scenario
            raise error
        
        # We need to mock the error handler to return partial success
        with patch('gecko_terminal_collector.utils.error_handler.ErrorHandler') as mock_handler_class:
            mock_handler = mock_handler_class.return_value
            mock_handler.handle_error.return_value = RecoveryResult(
                success=True,
                message="Partial success",
                partial_success=True,
                recovered_data=["partial", "data"]
            )
            
            result = await test_function()
            assert result == ["partial", "data"]
    
    @pytest.mark.asyncio
    async def test_decorator_max_retries_exceeded(self):
        """Test decorator when max retries are exceeded."""
        
        @handle_errors(component="test_component", max_retries=1)
        async def test_function():
            raise Exception("Persistent error")
        
        with pytest.raises(Exception, match="Operation failed after 1 retries"):
            await test_function()


class TestErrorHandlerIntegration:
    """Integration tests for the error handling framework."""
    
    @pytest.mark.asyncio
    async def test_full_error_handling_workflow(self):
        """Test complete error handling workflow."""
        mock_db = AsyncMock()
        handler = ErrorHandler(mock_db)
        
        # Simulate a series of errors leading to alert
        errors = [
            Exception("HTTP 429: Rate limit"),
            Exception("HTTP 429: Rate limit"),
            Exception("HTTP 429: Rate limit"),  # Should trigger alert
        ]
        
        results = []
        for i, error in enumerate(errors):
            result = await handler.handle_error(
                error,
                component="integration_test",
                operation="test_operation",
                context={"retry_count": i, "retry_after": 60},
                max_retries=3
            )
            results.append(result)
        
        # First two should succeed with retry
        assert results[0].success is True
        assert results[1].success is True
        
        # Third should trigger alert
        assert results[2].should_alert is True
        
        # Verify alert was created
        mock_db.create_system_alert.assert_called()
    
    @pytest.mark.asyncio
    async def test_data_validation_partial_success_workflow(self):
        """Test data validation with partial success workflow."""
        mock_db = AsyncMock()
        handler = ErrorHandler(mock_db)
        
        # Simulate validation error with mixed data
        error = Exception("Data validation failed")
        context = {
            "valid_data": [{"id": 1}, {"id": 2}, {"id": 3}],
            "invalid_data": [{"id": "bad"}]
        }
        
        result = await handler.handle_error(
            error,
            component="validation_test",
            operation="validate_data",
            context=context
        )
        
        assert result.success is True
        assert result.partial_success is True
        assert len(result.recovered_data) == 3
        assert result.should_alert is False  # Low invalid rate
    
    @pytest.mark.asyncio
    async def test_error_frequency_tracking(self):
        """Test error frequency tracking across multiple errors."""
        handler = ErrorHandler()
        
        # Simulate multiple errors from same component/operation
        for i in range(5):
            await handler.handle_error(
                Exception("HTTP 429: Rate limit"),
                component="frequency_test",
                operation="test_op"
            )
        
        # Check error frequency tracking
        error_key = "frequency_test.test_op.api_rate_limit"
        assert handler.error_counts[error_key] == 5
        
        stats = handler.get_error_statistics()
        assert stats["total_errors"] == 5
        assert error_key in stats["error_breakdown"]


if __name__ == "__main__":
    pytest.main([__file__])