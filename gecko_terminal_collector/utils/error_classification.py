"""
Error classification and recovery strategy logic for different failure types.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Type, Optional, Callable, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors that can occur in the system."""
    NETWORK = "network"
    API_RATE_LIMIT = "api_rate_limit"
    API_CLIENT = "api_client"
    DATA_VALIDATION = "data_validation"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Recovery actions that can be taken for different error types."""
    RETRY_IMMEDIATE = "retry_immediate"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    RETRY_WITH_CIRCUIT_BREAKER = "retry_with_circuit_breaker"
    SKIP_AND_CONTINUE = "skip_and_continue"
    FAIL_FAST = "fail_fast"
    ESCALATE = "escalate"
    RESET_CONNECTION = "reset_connection"
    REDUCE_LOAD = "reduce_load"


@dataclass
class ErrorClassification:
    """Classification of an error with recovery strategy."""
    category: ErrorCategory
    severity: ErrorSeverity
    recovery_action: RecoveryAction
    retry_eligible: bool
    circuit_breaker_eligible: bool
    escalation_threshold: int = 3
    cooldown_period: int = 300  # seconds
    description: str = ""


@dataclass
class ErrorContext:
    """Context information about an error occurrence."""
    error: Exception
    operation: str
    collector_type: str
    timestamp: datetime
    attempt_number: int
    additional_context: Dict[str, Any]


class ErrorClassifier:
    """
    Classifies errors and determines appropriate recovery strategies.
    
    Provides intelligent error classification based on exception types,
    error messages, and operational context to determine the best
    recovery strategy for each type of failure.
    """
    
    def __init__(self):
        self._classification_rules: Dict[Type[Exception], ErrorClassification] = {}
        self._message_patterns: Dict[str, ErrorClassification] = {}
        self._setup_default_classifications()
    
    def _setup_default_classifications(self) -> None:
        """Set up default error classifications for common exception types."""
        
        # Network-related errors
        self.register_classification(
            ConnectionError,
            ErrorClassification(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.RETRY_WITH_BACKOFF,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=5,
                description="Network connection failure"
            )
        )
        
        self.register_classification(
            TimeoutError,
            ErrorClassification(
                category=ErrorCategory.TIMEOUT,
                severity=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.RETRY_WITH_BACKOFF,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=3,
                description="Operation timeout"
            )
        )
        
        # API-related errors
        self.register_message_pattern(
            "rate limit",
            ErrorClassification(
                category=ErrorCategory.API_RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_BACKOFF,
                retry_eligible=True,
                circuit_breaker_eligible=False,
                escalation_threshold=10,
                cooldown_period=900,  # 15 minutes
                description="API rate limit exceeded"
            )
        )
        
        self.register_message_pattern(
            "429",
            ErrorClassification(
                category=ErrorCategory.API_RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_BACKOFF,
                retry_eligible=True,
                circuit_breaker_eligible=False,
                escalation_threshold=10,
                cooldown_period=900,
                description="HTTP 429 Too Many Requests"
            )
        )
        
        self.register_message_pattern(
            "401",
            ErrorClassification(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                recovery_action=RecoveryAction.FAIL_FAST,
                retry_eligible=False,
                circuit_breaker_eligible=False,
                description="Authentication failure"
            )
        )
        
        self.register_message_pattern(
            "403",
            ErrorClassification(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                recovery_action=RecoveryAction.FAIL_FAST,
                retry_eligible=False,
                circuit_breaker_eligible=False,
                description="Authorization failure"
            )
        )
        
        self.register_message_pattern(
            "500",
            ErrorClassification(
                category=ErrorCategory.API_CLIENT,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_CIRCUIT_BREAKER,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=3,
                description="Server internal error"
            )
        )
        
        self.register_message_pattern(
            "502",
            ErrorClassification(
                category=ErrorCategory.API_CLIENT,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_CIRCUIT_BREAKER,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=3,
                description="Bad gateway"
            )
        )
        
        self.register_message_pattern(
            "503",
            ErrorClassification(
                category=ErrorCategory.API_CLIENT,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_CIRCUIT_BREAKER,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=3,
                description="Service unavailable"
            )
        )
        
        # Data validation errors
        self.register_classification(
            ValueError,
            ErrorClassification(
                category=ErrorCategory.DATA_VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                recovery_action=RecoveryAction.SKIP_AND_CONTINUE,
                retry_eligible=False,
                circuit_breaker_eligible=False,
                description="Data validation failure"
            )
        )
        
        # Database errors
        self.register_message_pattern(
            "database",
            ErrorClassification(
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.RETRY_WITH_CIRCUIT_BREAKER,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=3,
                description="Database operation failure"
            )
        )
        
        self.register_message_pattern(
            "connection pool",
            ErrorClassification(
                category=ErrorCategory.RESOURCE_EXHAUSTION,
                severity=ErrorSeverity.HIGH,
                recovery_action=RecoveryAction.REDUCE_LOAD,
                retry_eligible=True,
                circuit_breaker_eligible=True,
                escalation_threshold=2,
                description="Database connection pool exhausted"
            )
        )
        
        # Memory/Resource errors
        self.register_classification(
            MemoryError,
            ErrorClassification(
                category=ErrorCategory.RESOURCE_EXHAUSTION,
                severity=ErrorSeverity.CRITICAL,
                recovery_action=RecoveryAction.REDUCE_LOAD,
                retry_eligible=False,
                circuit_breaker_eligible=True,
                escalation_threshold=1,
                description="Memory exhaustion"
            )
        )
    
    def register_classification(
        self,
        exception_type: Type[Exception],
        classification: ErrorClassification
    ) -> None:
        """
        Register an error classification for a specific exception type.
        
        Args:
            exception_type: Exception class to classify
            classification: Classification details
        """
        self._classification_rules[exception_type] = classification
        logger.debug(f"Registered classification for {exception_type.__name__}")
    
    def register_message_pattern(
        self,
        pattern: str,
        classification: ErrorClassification
    ) -> None:
        """
        Register an error classification for error messages containing a pattern.
        
        Args:
            pattern: String pattern to match in error messages (case-insensitive)
            classification: Classification details
        """
        self._message_patterns[pattern.lower()] = classification
        logger.debug(f"Registered message pattern classification for '{pattern}'")
    
    def classify_error(self, error_context: ErrorContext) -> ErrorClassification:
        """
        Classify an error and determine the appropriate recovery strategy.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            ErrorClassification with recovery strategy
        """
        error = error_context.error
        error_message = str(error).lower()
        
        # First, try to match by exception type
        for exception_type, classification in self._classification_rules.items():
            if isinstance(error, exception_type):
                logger.debug(
                    f"Classified error as {classification.category.value} "
                    f"based on exception type {exception_type.__name__}"
                )
                return classification
        
        # Then, try to match by message patterns
        for pattern, classification in self._message_patterns.items():
            if pattern in error_message:
                logger.debug(
                    f"Classified error as {classification.category.value} "
                    f"based on message pattern '{pattern}'"
                )
                return classification
        
        # Default classification for unknown errors
        logger.warning(f"Unknown error type: {type(error).__name__}: {error}")
        return ErrorClassification(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            recovery_action=RecoveryAction.RETRY_WITH_BACKOFF,
            retry_eligible=True,
            circuit_breaker_eligible=True,
            escalation_threshold=3,
            description=f"Unknown error: {type(error).__name__}"
        )
    
    def should_retry(self, error_context: ErrorContext) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            True if the error should be retried
        """
        classification = self.classify_error(error_context)
        return classification.retry_eligible
    
    def should_use_circuit_breaker(self, error_context: ErrorContext) -> bool:
        """
        Determine if circuit breaker should be used for this error type.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            True if circuit breaker should be used
        """
        classification = self.classify_error(error_context)
        return classification.circuit_breaker_eligible
    
    def get_escalation_threshold(self, error_context: ErrorContext) -> int:
        """
        Get the escalation threshold for this error type.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            Number of failures before escalation
        """
        classification = self.classify_error(error_context)
        return classification.escalation_threshold
    
    def get_cooldown_period(self, error_context: ErrorContext) -> int:
        """
        Get the cooldown period for this error type.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            Cooldown period in seconds
        """
        classification = self.classify_error(error_context)
        return classification.cooldown_period
    
    def get_recovery_action(self, error_context: ErrorContext) -> RecoveryAction:
        """
        Get the recommended recovery action for this error.
        
        Args:
            error_context: Context information about the error
            
        Returns:
            Recommended recovery action
        """
        classification = self.classify_error(error_context)
        return classification.recovery_action
    
    def get_classification_summary(self) -> Dict[str, int]:
        """
        Get a summary of registered error classifications.
        
        Returns:
            Dictionary with counts of classifications by category
        """
        summary = {}
        
        # Count exception type classifications
        for classification in self._classification_rules.values():
            category = classification.category.value
            summary[category] = summary.get(category, 0) + 1
        
        # Count message pattern classifications
        for classification in self._message_patterns.values():
            category = classification.category.value
            summary[f"{category}_patterns"] = summary.get(f"{category}_patterns", 0) + 1
        
        return summary


# Global error classifier instance
error_classifier = ErrorClassifier()