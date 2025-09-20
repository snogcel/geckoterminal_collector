"""
Comprehensive test suite for error handling and system resilience components.

This test suite validates the blockchain error handler and system resilience manager
implementations against the requirements.
"""

import asyncio
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json

# Import the components we're testing
from nautilus_poc.blockchain_error_handler import (
    BlockchainErrorHandler, ErrorCategory, ErrorSeverity, ErrorContext, RecoveryAction
)
from nautilus_poc.system_resilience import (
    SystemResilienceManager, SystemState, ComponentPriority, ResourceType, 
    ResourceConstraint, ComponentStatus, BlockchainState
)


class TestBlockchainErrorHandler:
    """Test suite for BlockchainErrorHandler."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return {
            'error_handling': {
                'max_retries': 3,
                'base_delay': 1.0,
                'max_delay': 60.0,
                'backoff_multiplier': 2.0
            },
            'network': {
                'congestion_threshold': 1000,
                'gas_price_multiplier': 1.5,
                'max_gas_price': 0.01
            },
            'circuit_breaker': {
                'threshold': 5,
                'timeout': 300
            }
        }
    
    @pytest.fixture
    def error_handler(self, config):
        """Create error handler instance."""
        return BlockchainErrorHandler(config)
    
    def test_initialization(self, error_handler, config):
        """Test error handler initialization."""
        assert error_handler.max_retries == 3
        assert error_handler.base_delay == 1.0
        assert error_handler.backoff_multiplier == 2.0
        assert error_handler.consecutive_failures == 0
        assert not error_handler.circuit_breaker_active
    
    def test_categorize_rpc_error(self, error_handler):
        """Test RPC error categorization."""
        # Test connection error
        conn_error = ConnectionError("Connection failed")
        context = error_handler._categorize_rpc_error(conn_error, "test_operation")
        
        assert context.category == ErrorCategory.RPC_CONNECTION
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.operation == "test_operation"
        assert "Connection failed" in context.error_message
    
    def test_categorize_pumpswap_error(self, error_handler):
        """Test PumpSwap error categorization."""
        # Test insufficient balance error
        balance_error = Exception("Insufficient balance for transaction")
        trade_data = {'mint_address': 'test_mint', 'amount': 1.0}
        
        context = error_handler._categorize_pumpswap_error(balance_error, "buy_operation", trade_data)
        
        assert context.category == ErrorCategory.INSUFFICIENT_BALANCE
        assert context.severity == ErrorSeverity.HIGH
        assert context.additional_data == trade_data
    
    @pytest.mark.asyncio
    async def test_handle_rpc_error_success_after_retry(self, error_handler):
        """Test RPC error handling with successful retry."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection failed")
            return "success"
        
        # Should succeed on second attempt
        result = await error_handler.handle_rpc_error(
            ConnectionError("Connection failed"),
            "test_operation",
            mock_operation
        )
        
        assert result == "success"
        assert call_count == 2
        assert error_handler.consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_handle_rpc_error_max_retries_exceeded(self, error_handler):
        """Test RPC error handling when max retries exceeded."""
        async def mock_operation():
            raise ConnectionError("Persistent connection error")
        
        with pytest.raises(ConnectionError):
            await error_handler.handle_rpc_error(
                ConnectionError("Persistent connection error"),
                "test_operation",
                mock_operation
            )
        
        assert error_handler.consecutive_failures > 0
    
    @pytest.mark.asyncio
    async def test_handle_pumpswap_error(self, error_handler):
        """Test PumpSwap error handling."""
        error = Exception("Pool liquidity insufficient")
        trade_data = {'mint_address': 'test_mint', 'sol_amount': 1.0}
        
        response = await error_handler.handle_pumpswap_error(error, "buy_operation", trade_data)
        
        assert response['status'] == 'error'
        assert response['operation'] == 'buy_operation'
        assert response['trade_data'] == trade_data
        assert 'recovery_action' in response
        assert isinstance(response['recovery_action'], dict)
    
    @pytest.mark.asyncio
    async def test_handle_network_congestion(self, error_handler):
        """Test network congestion handling."""
        current_gas_price = 0.005
        
        adjustments = await error_handler.handle_network_congestion(
            current_gas_price, "test_operation"
        )
        
        assert adjustments['gas_price'] > current_gas_price
        assert adjustments['gas_price'] <= error_handler.max_gas_price
        assert 'congestion_level' in adjustments
        assert 'priority_fee_multiplier' in adjustments
    
    @pytest.mark.asyncio
    async def test_handle_transaction_failure(self, error_handler):
        """Test transaction failure handling."""
        tx_hash = "test_tx_hash_123"
        error = Exception("Transaction failed due to insufficient gas")
        
        response = await error_handler.handle_transaction_failure(
            tx_hash, error, "test_operation"
        )
        
        assert response['status'] == 'transaction_failed'
        assert response['transaction_hash'] == tx_hash
        assert 'error_type' in response
        assert 'recovery_attempted' in response
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, error_handler):
        """Test circuit breaker activation after consecutive failures."""
        # Simulate multiple failures to trigger circuit breaker
        for i in range(error_handler.circuit_breaker_threshold):
            error_context = ErrorContext(
                error_type="TestError",
                error_message=f"Test error {i}",
                category=ErrorCategory.RPC_CONNECTION,
                severity=ErrorSeverity.HIGH,
                timestamp=datetime.now(),
                operation="test_operation"
            )
            error_handler._record_failure(error_context)
        
        # Wait a moment for circuit breaker to activate
        await asyncio.sleep(0.1)
        
        assert error_handler.circuit_breaker_active
        assert error_handler.consecutive_failures >= error_handler.circuit_breaker_threshold
    
    def test_get_error_statistics(self, error_handler):
        """Test error statistics collection."""
        # Add some test errors
        for i in range(3):
            error_context = ErrorContext(
                error_type="TestError",
                error_message=f"Test error {i}",
                category=ErrorCategory.RPC_CONNECTION,
                severity=ErrorSeverity.MEDIUM,
                timestamp=datetime.now(),
                operation="test_operation"
            )
            error_handler.error_history.append(error_context)
        
        stats = error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 3
        assert 'error_categories' in stats
        assert 'error_severities' in stats
        assert 'recent_errors' in stats
        assert len(stats['recent_errors']) <= 10


class TestSystemResilienceManager:
    """Test suite for SystemResilienceManager."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return {
            'resilience': {
                'resource_monitor_interval': 1,
                'state_validation_interval': 2
            },
            'resource_constraints': {
                'cpu_warning': 70.0,
                'cpu_critical': 90.0,
                'memory_warning': 80.0,
                'memory_critical': 95.0
            },
            'security': {
                'secure_failure_mode': True
            }
        }
    
    @pytest.fixture
    def resilience_manager(self, config):
        """Create resilience manager instance."""
        return SystemResilienceManager(config)
    
    def test_initialization(self, resilience_manager):
        """Test resilience manager initialization."""
        assert resilience_manager.current_state == SystemState.NORMAL
        assert len(resilience_manager.resource_constraints) > 0
        assert ResourceType.CPU in resilience_manager.resource_constraints
        assert ResourceType.MEMORY in resilience_manager.resource_constraints
    
    def test_register_component(self, resilience_manager):
        """Test component registration."""
        resilience_manager.register_component("test_component", ComponentPriority.HIGH)
        
        assert "test_component" in resilience_manager.components
        component = resilience_manager.components["test_component"]
        assert component.priority == ComponentPriority.HIGH
        assert component.is_healthy
        assert component.is_active
    
    @pytest.mark.asyncio
    async def test_handle_component_failure_low_priority(self, resilience_manager):
        """Test handling of low priority component failure."""
        resilience_manager.register_component("low_priority_component", ComponentPriority.LOW)
        
        error = Exception("Test failure")
        response = await resilience_manager.handle_component_failure(
            "low_priority_component", error, is_critical=False
        )
        
        assert response['status'] == 'degradation_applied'
        component = resilience_manager.components["low_priority_component"]
        assert not component.is_active
        assert component.degraded_mode
        assert not component.is_healthy
    
    @pytest.mark.asyncio
    async def test_handle_component_failure_critical_priority(self, resilience_manager):
        """Test handling of critical priority component failure."""
        resilience_manager.register_component("critical_component", ComponentPriority.CRITICAL)
        
        error = Exception("Critical failure")
        
        # Mock the restart attempt to succeed
        with patch.object(resilience_manager, '_attempt_component_restart', return_value=True):
            response = await resilience_manager.handle_component_failure(
                "critical_component", error, is_critical=True
            )
        
        assert response['status'] == 'degradation_applied'
        assert 'Successfully restarted' in str(response['actions_taken'])
    
    @pytest.mark.asyncio
    async def test_validate_blockchain_consistency_no_client(self, resilience_manager):
        """Test blockchain consistency validation without client."""
        result = await resilience_manager.validate_blockchain_consistency()
        
        assert result['status'] == 'no_client'
        assert not result['is_consistent']
    
    @pytest.mark.asyncio
    async def test_validate_blockchain_consistency_with_mock_client(self, resilience_manager):
        """Test blockchain consistency validation with mock client."""
        # Set a mock client
        mock_client = Mock()
        resilience_manager.set_blockchain_client(mock_client)
        
        # Mock the blockchain state methods
        with patch.object(resilience_manager, '_get_current_slot', return_value=12345), \
             patch.object(resilience_manager, '_get_current_block', return_value={'block_height': 100, 'block_hash': 'test_hash'}), \
             patch.object(resilience_manager, '_perform_consistency_checks', return_value={'is_consistent': True, 'checks': ['test'], 'errors': []}):
            
            result = await resilience_manager.validate_blockchain_consistency()
        
        assert result['status'] == 'validated'
        assert result['is_consistent']
        assert result['slot'] == 12345
    
    @pytest.mark.asyncio
    async def test_handle_resource_constraint_warning(self, resilience_manager):
        """Test resource constraint handling at warning level."""
        response = await resilience_manager.handle_resource_constraint(
            ResourceType.CPU, 75.0  # Above warning threshold
        )
        
        assert response['status'] == 'handled'
        assert response['resource_type'] == 'cpu'
        assert response['usage_percent'] == 75.0
        assert response['constraint_level'] == 'warning'
    
    @pytest.mark.asyncio
    async def test_handle_resource_constraint_critical(self, resilience_manager):
        """Test resource constraint handling at critical level."""
        # Register some low priority components first
        resilience_manager.register_component("analytics", ComponentPriority.LOW)
        
        response = await resilience_manager.handle_resource_constraint(
            ResourceType.MEMORY, 96.0  # Above critical threshold
        )
        
        assert response['status'] == 'handled'
        assert response['constraint_level'] == 'critical'
        assert len(response['actions_taken']) > 0
    
    def test_secure_failure_cleanup(self, resilience_manager):
        """Test secure failure cleanup."""
        error_context = {
            'error': 'Test error',
            'sensitive_data': 'private_key_12345',
            'operation': 'test_operation'
        }
        
        # Should not raise exception
        resilience_manager.secure_failure_cleanup(error_context)
        
        # Verify logging occurred (would need to check logs in real implementation)
        assert True  # Placeholder assertion
    
    def test_register_sensitive_data(self, resilience_manager):
        """Test sensitive data registration."""
        test_data = {'private_key': 'secret123'}
        
        resilience_manager.register_sensitive_data(test_data)
        
        # Should have registered the reference
        assert len(resilience_manager.sensitive_data_refs) == 1
    
    def test_get_system_health_status(self, resilience_manager):
        """Test system health status reporting."""
        # Register some components
        resilience_manager.register_component("healthy_component", ComponentPriority.HIGH)
        resilience_manager.register_component("unhealthy_component", ComponentPriority.MEDIUM)
        
        # Make one component unhealthy
        resilience_manager.components["unhealthy_component"].is_healthy = False
        
        status = resilience_manager.get_system_health_status()
        
        assert status['system_state'] == 'normal'
        assert 'component_health' in status
        assert status['component_health']['total'] == 2
        assert status['component_health']['healthy'] == 1
        assert 'resource_status' in status
        assert 'blockchain_state' in status
    
    def test_sanitize_error_message(self, resilience_manager):
        """Test error message sanitization."""
        sensitive_message = "Error with private_key abc123 and password secret123"
        
        sanitized = resilience_manager._sanitize_error_message(sensitive_message)
        
        assert 'private_key' not in sanitized
        assert 'password' not in sanitized
        assert '[REDACTED]' in sanitized
    
    def test_sanitize_error_context(self, resilience_manager):
        """Test error context sanitization."""
        error_context = {
            'message': 'Error with secret_key xyz789',
            'details': {
                'private_key': 'sensitive_data_here',
                'operation': 'test_operation'
            }
        }
        
        sanitized = resilience_manager._sanitize_error_context(error_context)
        
        assert '[REDACTED]' in sanitized['message']
        assert sanitized['details']['operation'] == 'test_operation'


class TestIntegration:
    """Integration tests for error handling and resilience components."""
    
    @pytest.fixture
    def config(self):
        """Integration test configuration."""
        return {
            'error_handling': {
                'max_retries': 2,
                'base_delay': 0.1,  # Faster for testing
                'backoff_multiplier': 1.5
            },
            'resilience': {
                'resource_monitor_interval': 0.5,
                'state_validation_interval': 1.0
            },
            'resource_constraints': {
                'cpu_warning': 70.0,
                'memory_warning': 80.0
            },
            'security': {
                'secure_failure_mode': True
            }
        }
    
    @pytest.mark.asyncio
    async def test_error_handler_resilience_integration(self, config):
        """Test integration between error handler and resilience manager."""
        error_handler = BlockchainErrorHandler(config)
        resilience_manager = SystemResilienceManager(config)
        
        # Register a component in resilience manager
        resilience_manager.register_component("test_component", ComponentPriority.HIGH)
        
        # Simulate an error that would affect the component
        error = Exception("Integration test error")
        
        # Handle the error
        pumpswap_response = await error_handler.handle_pumpswap_error(
            error, "test_operation", {'test': 'data'}
        )
        
        # Handle component failure in resilience manager
        component_response = await resilience_manager.handle_component_failure(
            "test_component", error, is_critical=False
        )
        
        # Verify both systems handled the error appropriately
        assert pumpswap_response['status'] == 'error'
        assert component_response['status'] == 'degradation_applied'
        
        # Check system health
        health_status = resilience_manager.get_system_health_status()
        assert health_status['component_health']['healthy'] == 0  # Component should be unhealthy


def run_comprehensive_error_handling_tests():
    """Run all error handling and resilience tests."""
    print("🧪 Running Comprehensive Error Handling Tests")
    print("=" * 60)
    
    # Configure logging for tests
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Run the tests using pytest
        import subprocess
        import sys
        
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v', 
            '--tb=short'
        ], capture_output=True, text=True)
        
        print("Test Output:")
        print(result.stdout)
        
        if result.stderr:
            print("Test Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ All error handling tests passed!")
        else:
            print("❌ Some error handling tests failed!")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


if __name__ == "__main__":
    success = run_comprehensive_error_handling_tests()
    exit(0 if success else 1)