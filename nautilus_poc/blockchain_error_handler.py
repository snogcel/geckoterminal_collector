"""
Blockchain-specific error handling for Solana RPC and PumpSwap SDK operations.

This module implements comprehensive error handling and recovery mechanisms for blockchain operations,
including exponential backoff for RPC calls, PumpSwap SDK error categorization, network congestion
handling, and transaction failure recovery.

Requirements addressed: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Union, List
from enum import Enum
from dataclasses import dataclass
import json
from datetime import datetime, timedelta

# Solana and PumpSwap related imports (mock for now)
try:
    from solana.rpc.api import Client
    from solana.rpc.core import RPCException
    from solana.rpc.types import TxOpts
    from solders.rpc.errors import RpcError
except ImportError:
    # Mock classes for development
    class RPCException(Exception):
        pass
    
    class RpcError(Exception):
        pass
    
    class Client:
        pass
    
    class TxOpts:
        pass


class ErrorCategory(Enum):
    """Categories of blockchain errors for appropriate handling."""
    RPC_CONNECTION = "rpc_connection"
    RPC_TIMEOUT = "rpc_timeout"
    RPC_RATE_LIMIT = "rpc_rate_limit"
    TRANSACTION_FAILED = "transaction_failed"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    NETWORK_CONGESTION = "network_congestion"
    PUMPSWAP_SDK = "pumpswap_sdk"
    POOL_LIQUIDITY = "pool_liquidity"
    SLIPPAGE_EXCEEDED = "slippage_exceeded"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for error handling decisions."""
    LOW = "low"          # Retry immediately
    MEDIUM = "medium"    # Retry with backoff
    HIGH = "high"        # Retry with extended backoff
    CRITICAL = "critical"  # Stop trading, alert operators


@dataclass
class ErrorContext:
    """Context information for error handling decisions."""
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: datetime
    operation: str
    retry_count: int = 0
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    base_delay: float = 1.0
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class RecoveryAction:
    """Defines recovery actions for specific error types."""
    should_retry: bool
    delay_seconds: float
    adjust_parameters: bool = False
    parameter_adjustments: Optional[Dict[str, Any]] = None
    escalate: bool = False
    stop_trading: bool = False


class BlockchainErrorHandler:
    """
    Comprehensive error handler for blockchain operations.
    
    Handles Solana RPC errors, PumpSwap SDK errors, network congestion,
    and implements recovery strategies with exponential backoff.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the blockchain error handler.
        
        Args:
            config: Configuration dictionary containing error handling parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Error handling configuration
        self.max_retries = config.get('error_handling', {}).get('max_retries', 3)
        self.base_delay = config.get('error_handling', {}).get('base_delay', 1.0)
        self.max_delay = config.get('error_handling', {}).get('max_delay', 60.0)
        self.backoff_multiplier = config.get('error_handling', {}).get('backoff_multiplier', 2.0)
        
        # Network congestion handling
        self.congestion_threshold = config.get('network', {}).get('congestion_threshold', 1000)
        self.gas_price_multiplier = config.get('network', {}).get('gas_price_multiplier', 1.5)
        self.max_gas_price = config.get('network', {}).get('max_gas_price', 0.01)  # SOL
        
        # Error tracking
        self.error_history: List[ErrorContext] = []
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        
        # Circuit breaker state
        self.circuit_breaker_threshold = config.get('circuit_breaker', {}).get('threshold', 10)
        self.circuit_breaker_timeout = config.get('circuit_breaker', {}).get('timeout', 300)  # 5 minutes
        self.circuit_breaker_active = False
        self.circuit_breaker_activated_at: Optional[datetime] = None
    
    async def handle_rpc_error(
        self, 
        error: Exception, 
        operation: str, 
        operation_func: Callable,
        *args, 
        **kwargs
    ) -> Any:
        """
        Handle Solana RPC errors with exponential backoff retry logic.
        
        Args:
            error: The RPC error that occurred
            operation: Description of the operation that failed
            operation_func: Function to retry
            *args: Arguments for the operation function
            **kwargs: Keyword arguments for the operation function
            
        Returns:
            Result of successful operation or raises final error
            
        Requirements: 10.1 - Solana RPC error handling with exponential backoff
        """
        error_context = self._categorize_rpc_error(error, operation)
        recovery_action = self._determine_recovery_action(error_context)
        
        self.logger.warning(
            f"RPC error in {operation}: {error_context.error_message} "
            f"(Category: {error_context.category.value}, Severity: {error_context.severity.value})"
        )
        
        if not recovery_action.should_retry:
            self._log_final_failure(error_context)
            raise error
        
        # Implement exponential backoff retry
        for attempt in range(self.max_retries):
            error_context.retry_count = attempt + 1
            
            if attempt > 0:  # Don't delay on first attempt
                delay = min(
                    self.base_delay * (self.backoff_multiplier ** attempt),
                    self.max_delay
                )
                
                self.logger.info(
                    f"Retrying {operation} in {delay:.2f} seconds "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
            
            try:
                # Adjust parameters if needed for congestion
                if recovery_action.adjust_parameters and recovery_action.parameter_adjustments:
                    kwargs.update(recovery_action.parameter_adjustments)
                
                result = await operation_func(*args, **kwargs)
                
                # Success - reset failure tracking
                self._record_success(operation)
                return result
                
            except Exception as retry_error:
                self.logger.warning(
                    f"Retry {attempt + 1} failed for {operation}: {str(retry_error)}"
                )
                
                # Update error context for potential escalation
                if attempt == self.max_retries - 1:
                    error_context.error_message = str(retry_error)
                    self._record_failure(error_context)
                    
                    if recovery_action.escalate:
                        await self._escalate_error(error_context)
                    
                    raise retry_error
        
        # Should not reach here, but safety fallback
        self._record_failure(error_context)
        raise error
    
    async def handle_pumpswap_error(
        self, 
        error: Exception, 
        operation: str, 
        trade_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle PumpSwap SDK errors with categorization and recovery.
        
        Args:
            error: The PumpSwap SDK error
            operation: Description of the trading operation
            trade_data: Context data about the trade
            
        Returns:
            Error response dictionary with recovery recommendations
            
        Requirements: 10.2 - PumpSwap SDK error categorization and recovery
        """
        error_context = self._categorize_pumpswap_error(error, operation, trade_data)
        recovery_action = self._determine_recovery_action(error_context)
        
        error_response = {
            'status': 'error',
            'error_type': error_context.error_type,
            'error_message': error_context.error_message,
            'category': error_context.category.value,
            'severity': error_context.severity.value,
            'operation': operation,
            'trade_data': trade_data,
            'timestamp': error_context.timestamp.isoformat(),
            'retry_recommended': recovery_action.should_retry,
            'recovery_action': {
                'should_retry': recovery_action.should_retry,
                'delay_seconds': recovery_action.delay_seconds,
                'adjust_parameters': recovery_action.adjust_parameters,
                'parameter_adjustments': recovery_action.parameter_adjustments,
                'stop_trading': recovery_action.stop_trading
            }
        }
        
        # Log the error with appropriate level
        log_level = logging.ERROR if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else logging.WARNING
        self.logger.log(
            log_level,
            f"PumpSwap error in {operation}: {error_context.error_message} "
            f"(Category: {error_context.category.value})"
        )
        
        # Record failure for circuit breaker tracking
        self._record_failure(error_context)
        
        # Handle critical errors
        if recovery_action.stop_trading:
            await self._activate_circuit_breaker(error_context)
        
        return error_response
    
    async def handle_network_congestion(
        self, 
        current_gas_price: float, 
        operation: str
    ) -> Dict[str, Any]:
        """
        Handle network congestion by adjusting gas prices and retry parameters.
        
        Args:
            current_gas_price: Current gas price in SOL
            operation: Description of the operation
            
        Returns:
            Adjusted parameters for congestion handling
            
        Requirements: 10.3 - Network congestion handling with gas price adjustment
        """
        self.logger.info(f"Handling network congestion for {operation}")
        
        # Calculate adjusted gas price
        adjusted_gas_price = min(
            current_gas_price * self.gas_price_multiplier,
            self.max_gas_price
        )
        
        # Determine congestion level
        congestion_level = self._assess_congestion_level(current_gas_price)
        
        adjustments = {
            'gas_price': adjusted_gas_price,
            'congestion_level': congestion_level,
            'priority_fee_multiplier': self._get_priority_fee_multiplier(congestion_level),
            'timeout_multiplier': self._get_timeout_multiplier(congestion_level),
            'retry_delay_multiplier': self._get_retry_delay_multiplier(congestion_level)
        }
        
        self.logger.info(
            f"Network congestion adjustments for {operation}: "
            f"Gas price: {current_gas_price:.6f} -> {adjusted_gas_price:.6f} SOL, "
            f"Congestion level: {congestion_level}"
        )
        
        return adjustments
    
    async def handle_transaction_failure(
        self, 
        tx_hash: str, 
        error: Exception, 
        operation: str,
        retry_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Handle transaction failures with recovery and retry logic.
        
        Args:
            tx_hash: Transaction hash that failed
            error: The transaction error
            operation: Description of the operation
            retry_func: Optional function to retry the transaction
            
        Returns:
            Transaction failure response with recovery recommendations
            
        Requirements: 10.4 - Transaction failure recovery and retry logic
        """
        error_context = self._categorize_transaction_error(error, operation, tx_hash)
        recovery_action = self._determine_recovery_action(error_context)
        
        failure_response = {
            'status': 'transaction_failed',
            'transaction_hash': tx_hash,
            'error_type': error_context.error_type,
            'error_message': error_context.error_message,
            'category': error_context.category.value,
            'severity': error_context.severity.value,
            'operation': operation,
            'timestamp': error_context.timestamp.isoformat(),
            'recovery_attempted': False,
            'recovery_successful': False
        }
        
        self.logger.error(
            f"Transaction failed for {operation}: {tx_hash} - {error_context.error_message}"
        )
        
        # Attempt recovery if recommended and retry function provided
        if recovery_action.should_retry and retry_func:
            try:
                self.logger.info(f"Attempting transaction recovery for {operation}")
                
                # Wait for recommended delay
                if recovery_action.delay_seconds > 0:
                    await asyncio.sleep(recovery_action.delay_seconds)
                
                # Retry the transaction
                retry_result = await retry_func()
                
                failure_response.update({
                    'recovery_attempted': True,
                    'recovery_successful': True,
                    'recovery_result': retry_result
                })
                
                self.logger.info(f"Transaction recovery successful for {operation}")
                
            except Exception as recovery_error:
                failure_response.update({
                    'recovery_attempted': True,
                    'recovery_successful': False,
                    'recovery_error': str(recovery_error)
                })
                
                self.logger.error(
                    f"Transaction recovery failed for {operation}: {str(recovery_error)}"
                )
        
        # Record failure for tracking
        self._record_failure(error_context)
        
        return failure_response
    
    def _categorize_rpc_error(self, error: Exception, operation: str) -> ErrorContext:
        """Categorize RPC errors for appropriate handling."""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Determine category and severity based on error type and message
        if isinstance(error, (ConnectionError, OSError)):
            category = ErrorCategory.RPC_CONNECTION
            severity = ErrorSeverity.MEDIUM
        elif isinstance(error, TimeoutError):
            category = ErrorCategory.RPC_TIMEOUT
            severity = ErrorSeverity.MEDIUM
        elif "rate limit" in error_message.lower():
            category = ErrorCategory.RPC_RATE_LIMIT
            severity = ErrorSeverity.HIGH
        elif isinstance(error, (RPCException, RpcError)):
            category = ErrorCategory.TRANSACTION_FAILED
            severity = ErrorSeverity.HIGH
        else:
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.MEDIUM
        
        return ErrorContext(
            error_type=error_type,
            error_message=error_message,
            category=category,
            severity=severity,
            timestamp=datetime.now(),
            operation=operation
        )
    
    def _categorize_pumpswap_error(
        self, 
        error: Exception, 
        operation: str, 
        trade_data: Dict[str, Any]
    ) -> ErrorContext:
        """Categorize PumpSwap SDK errors."""
        error_type = type(error).__name__
        error_message = str(error)
        
        # Analyze error message for specific PumpSwap issues
        if "insufficient" in error_message.lower() and "balance" in error_message.lower():
            category = ErrorCategory.INSUFFICIENT_BALANCE
            severity = ErrorSeverity.HIGH
        elif "liquidity" in error_message.lower():
            category = ErrorCategory.POOL_LIQUIDITY
            severity = ErrorSeverity.MEDIUM
        elif "slippage" in error_message.lower():
            category = ErrorCategory.SLIPPAGE_EXCEEDED
            severity = ErrorSeverity.MEDIUM
        elif "network" in error_message.lower() or "congestion" in error_message.lower():
            category = ErrorCategory.NETWORK_CONGESTION
            severity = ErrorSeverity.HIGH
        else:
            category = ErrorCategory.PUMPSWAP_SDK
            severity = ErrorSeverity.MEDIUM
        
        return ErrorContext(
            error_type=error_type,
            error_message=error_message,
            category=category,
            severity=severity,
            timestamp=datetime.now(),
            operation=operation,
            additional_data=trade_data
        )
    
    def _categorize_transaction_error(
        self, 
        error: Exception, 
        operation: str, 
        tx_hash: str
    ) -> ErrorContext:
        """Categorize transaction-specific errors."""
        error_type = type(error).__name__
        error_message = str(error)
        
        category = ErrorCategory.TRANSACTION_FAILED
        
        # Determine severity based on error type
        if "insufficient" in error_message.lower():
            severity = ErrorSeverity.HIGH
        elif "timeout" in error_message.lower():
            severity = ErrorSeverity.MEDIUM
        else:
            severity = ErrorSeverity.HIGH
        
        return ErrorContext(
            error_type=error_type,
            error_message=error_message,
            category=category,
            severity=severity,
            timestamp=datetime.now(),
            operation=operation,
            additional_data={'transaction_hash': tx_hash}
        )
    
    def _determine_recovery_action(self, error_context: ErrorContext) -> RecoveryAction:
        """Determine appropriate recovery action based on error context."""
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            return RecoveryAction(
                should_retry=False,
                delay_seconds=0,
                stop_trading=True
            )
        
        # Category-specific recovery logic
        if error_context.category == ErrorCategory.RPC_CONNECTION:
            return RecoveryAction(
                should_retry=True,
                delay_seconds=self.base_delay * (2 ** error_context.retry_count)
            )
        
        elif error_context.category == ErrorCategory.RPC_TIMEOUT:
            return RecoveryAction(
                should_retry=True,
                delay_seconds=self.base_delay * (1.5 ** error_context.retry_count)
            )
        
        elif error_context.category == ErrorCategory.RPC_RATE_LIMIT:
            return RecoveryAction(
                should_retry=True,
                delay_seconds=min(30 * (2 ** error_context.retry_count), 300)  # Max 5 minutes
            )
        
        elif error_context.category == ErrorCategory.NETWORK_CONGESTION:
            return RecoveryAction(
                should_retry=True,
                delay_seconds=10 * (1.5 ** error_context.retry_count),
                adjust_parameters=True,
                parameter_adjustments={'priority_fee_multiplier': 1.5}
            )
        
        elif error_context.category == ErrorCategory.INSUFFICIENT_BALANCE:
            return RecoveryAction(
                should_retry=False,
                delay_seconds=0,
                stop_trading=True
            )
        
        elif error_context.category == ErrorCategory.POOL_LIQUIDITY:
            return RecoveryAction(
                should_retry=False,  # Skip this trade
                delay_seconds=0
            )
        
        elif error_context.category == ErrorCategory.SLIPPAGE_EXCEEDED:
            return RecoveryAction(
                should_retry=True,
                delay_seconds=5,
                adjust_parameters=True,
                parameter_adjustments={'max_slippage_percent': 1.2}  # Increase tolerance slightly
            )
        
        else:  # Unknown or general errors
            return RecoveryAction(
                should_retry=error_context.severity != ErrorSeverity.CRITICAL,
                delay_seconds=self.base_delay * (2 ** error_context.retry_count),
                escalate=error_context.severity == ErrorSeverity.CRITICAL
            )
    
    def _assess_congestion_level(self, gas_price: float) -> str:
        """Assess network congestion level based on gas price."""
        if gas_price < 0.001:
            return "low"
        elif gas_price < 0.005:
            return "medium"
        elif gas_price < 0.01:
            return "high"
        else:
            return "extreme"
    
    def _get_priority_fee_multiplier(self, congestion_level: str) -> float:
        """Get priority fee multiplier based on congestion level."""
        multipliers = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5,
            "extreme": 2.0
        }
        return multipliers.get(congestion_level, 1.0)
    
    def _get_timeout_multiplier(self, congestion_level: str) -> float:
        """Get timeout multiplier based on congestion level."""
        multipliers = {
            "low": 1.0,
            "medium": 1.5,
            "high": 2.0,
            "extreme": 3.0
        }
        return multipliers.get(congestion_level, 1.0)
    
    def _get_retry_delay_multiplier(self, congestion_level: str) -> float:
        """Get retry delay multiplier based on congestion level."""
        multipliers = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5,
            "extreme": 2.0
        }
        return multipliers.get(congestion_level, 1.0)
    
    def _record_success(self, operation: str):
        """Record successful operation for failure tracking."""
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        
        self.logger.debug(f"Operation successful: {operation}")
    
    def _record_failure(self, error_context: ErrorContext):
        """Record failed operation for circuit breaker tracking."""
        self.consecutive_failures += 1
        self.error_history.append(error_context)
        
        # Trim error history to last 100 entries
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]
        
        # Check if circuit breaker should activate
        if (self.consecutive_failures >= self.circuit_breaker_threshold and 
            not self.circuit_breaker_active):
            asyncio.create_task(self._activate_circuit_breaker(error_context))
    
    async def _activate_circuit_breaker(self, error_context: ErrorContext):
        """Activate circuit breaker to stop trading."""
        self.circuit_breaker_active = True
        self.circuit_breaker_activated_at = datetime.now()
        
        self.logger.critical(
            f"Circuit breaker activated due to {self.consecutive_failures} consecutive failures. "
            f"Last error: {error_context.error_message}"
        )
        
        # Schedule circuit breaker reset
        asyncio.create_task(self._schedule_circuit_breaker_reset())
    
    async def _schedule_circuit_breaker_reset(self):
        """Schedule circuit breaker reset after timeout."""
        await asyncio.sleep(self.circuit_breaker_timeout)
        
        self.circuit_breaker_active = False
        self.circuit_breaker_activated_at = None
        self.consecutive_failures = 0
        
        self.logger.info("Circuit breaker reset - trading resumed")
    
    async def _escalate_error(self, error_context: ErrorContext):
        """Escalate critical errors to operators."""
        escalation_data = {
            'timestamp': error_context.timestamp.isoformat(),
            'operation': error_context.operation,
            'error_type': error_context.error_type,
            'error_message': error_context.error_message,
            'category': error_context.category.value,
            'severity': error_context.severity.value,
            'consecutive_failures': self.consecutive_failures,
            'additional_data': error_context.additional_data
        }
        
        self.logger.critical(f"ESCALATED ERROR: {json.dumps(escalation_data, indent=2)}")
        
        # In production, this would send alerts to monitoring systems
        # For now, we log the escalation
    
    def _log_final_failure(self, error_context: ErrorContext):
        """Log final failure after all retries exhausted."""
        self.logger.error(
            f"Final failure for {error_context.operation} after {error_context.retry_count} retries: "
            f"{error_context.error_message}"
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring and analysis."""
        if not self.error_history:
            return {
                'total_errors': 0,
                'consecutive_failures': self.consecutive_failures,
                'circuit_breaker_active': self.circuit_breaker_active,
                'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None
            }
        
        # Analyze error history
        error_categories = {}
        error_severities = {}
        
        for error in self.error_history:
            category = error.category.value
            severity = error.severity.value
            
            error_categories[category] = error_categories.get(category, 0) + 1
            error_severities[severity] = error_severities.get(severity, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'consecutive_failures': self.consecutive_failures,
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_activated_at': self.circuit_breaker_activated_at.isoformat() if self.circuit_breaker_activated_at else None,
            'last_success_time': self.last_success_time.isoformat() if self.last_success_time else None,
            'error_categories': error_categories,
            'error_severities': error_severities,
            'recent_errors': [
                {
                    'timestamp': error.timestamp.isoformat(),
                    'operation': error.operation,
                    'category': error.category.value,
                    'severity': error.severity.value,
                    'message': error.error_message
                }
                for error in self.error_history[-10:]  # Last 10 errors
            ]
        }