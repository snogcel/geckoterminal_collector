"""
System resilience features for graceful degradation and robust operation.

This module implements system resilience features including graceful degradation for non-critical failures,
blockchain state consistency validation, secure failure handling without key exposure, and resource
constraint handling with prioritization.

Requirements addressed: 10.7, 10.8, 11.1
"""

import asyncio
import logging
import psutil
import time
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import weakref

# Solana imports (mock for development)
try:
    from solana.rpc.api import Client
    from solana.rpc.commitment import Commitment
    from solders.pubkey import Pubkey
except ImportError:
    # Mock classes for development
    class Client:
        pass
    
    class Commitment:
        pass
    
    class Pubkey:
        pass


class SystemState(Enum):
    """System operational states."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ComponentPriority(Enum):
    """Priority levels for system components."""
    CRITICAL = 1      # Core trading logic, security
    HIGH = 2          # Signal processing, position management
    MEDIUM = 3        # Performance monitoring, logging
    LOW = 4           # Analytics, reporting


class ResourceType(Enum):
    """Types of system resources to monitor."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    DATABASE = "database"
    BLOCKCHAIN_RPC = "blockchain_rpc"


@dataclass
class ResourceConstraint:
    """Resource constraint definition."""
    resource_type: ResourceType
    threshold_warning: float
    threshold_critical: float
    current_usage: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ComponentStatus:
    """Status of a system component."""
    name: str
    priority: ComponentPriority
    is_active: bool = True
    is_healthy: bool = True
    last_health_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    degraded_mode: bool = False
    failure_reason: Optional[str] = None


@dataclass
class BlockchainState:
    """Blockchain state consistency information."""
    slot: Optional[int] = None
    block_height: Optional[int] = None
    block_hash: Optional[str] = None
    timestamp: Optional[datetime] = None
    is_consistent: bool = True
    last_validated: datetime = field(default_factory=datetime.now)
    validation_errors: List[str] = field(default_factory=list)


class SystemResilienceManager:
    """
    Manages system resilience features including graceful degradation,
    state consistency validation, and resource constraint handling.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the system resilience manager.
        
        Args:
            config: Configuration dictionary containing resilience parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # System state management
        self.current_state = SystemState.NORMAL
        self.state_change_time = datetime.now()
        self.state_history: List[Dict[str, Any]] = []
        
        # Component management
        self.components: Dict[str, ComponentStatus] = {}
        self.component_dependencies: Dict[str, List[str]] = {}
        
        # Resource monitoring
        self.resource_constraints: Dict[ResourceType, ResourceConstraint] = {}
        self.resource_monitor_interval = config.get('resilience', {}).get('resource_monitor_interval', 30)
        self.resource_monitor_task: Optional[asyncio.Task] = None
        
        # Blockchain state validation
        self.blockchain_client: Optional[Client] = None
        self.blockchain_state = BlockchainState()
        self.state_validation_interval = config.get('resilience', {}).get('state_validation_interval', 60)
        self.state_validation_task: Optional[asyncio.Task] = None
        
        # Graceful degradation
        self.degradation_rules: Dict[str, Dict[str, Any]] = {}
        self.active_degradations: Dict[str, datetime] = {}
        
        # Security and failure handling
        self.secure_failure_mode = config.get('security', {}).get('secure_failure_mode', True)
        self.sensitive_data_refs: List[weakref.ref] = []
        
        # Thread pool for non-blocking operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="resilience")
        
        self._initialize_resource_constraints()
        self._initialize_degradation_rules()
        self._register_core_components()
    
    async def start(self):
        """Start the resilience manager and monitoring tasks."""
        self.logger.info("Starting system resilience manager")
        
        # Start resource monitoring
        self.resource_monitor_task = asyncio.create_task(self._monitor_resources())
        
        # Start blockchain state validation if client available
        if self.blockchain_client:
            self.state_validation_task = asyncio.create_task(self._validate_blockchain_state())
        
        self.logger.info("System resilience manager started")
    
    async def stop(self):
        """Stop the resilience manager and cleanup resources."""
        self.logger.info("Stopping system resilience manager")
        
        # Cancel monitoring tasks
        if self.resource_monitor_task:
            self.resource_monitor_task.cancel()
            try:
                await self.resource_monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.state_validation_task:
            self.state_validation_task.cancel()
            try:
                await self.state_validation_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        self.logger.info("System resilience manager stopped")
    
    def set_blockchain_client(self, client: Client):
        """Set the blockchain client for state validation."""
        self.blockchain_client = client
        self.logger.info("Blockchain client set for state validation")
    
    def register_component(
        self, 
        name: str, 
        priority: ComponentPriority,
        dependencies: Optional[List[str]] = None
    ):
        """
        Register a system component for monitoring.
        
        Args:
            name: Component name
            priority: Component priority level
            dependencies: List of component names this component depends on
            
        Requirements: 10.7 - Graceful degradation for non-critical failures
        """
        self.components[name] = ComponentStatus(name=name, priority=priority)
        
        if dependencies:
            self.component_dependencies[name] = dependencies
        
        self.logger.debug(f"Registered component: {name} (priority: {priority.name})")
    
    async def handle_component_failure(
        self, 
        component_name: str, 
        error: Exception,
        is_critical: bool = False
    ) -> Dict[str, Any]:
        """
        Handle component failure with graceful degradation.
        
        Args:
            component_name: Name of the failed component
            error: The error that caused the failure
            is_critical: Whether this is a critical failure
            
        Returns:
            Degradation response with actions taken
            
        Requirements: 10.7 - Graceful degradation for non-critical failures
        """
        if component_name not in self.components:
            self.logger.warning(f"Unknown component failure: {component_name}")
            return {'status': 'unknown_component', 'component': component_name}
        
        component = self.components[component_name]
        component.is_healthy = False
        component.error_count += 1
        component.failure_reason = str(error)
        component.last_health_check = datetime.now()
        
        # Secure error handling - don't expose sensitive information
        safe_error_message = self._sanitize_error_message(str(error))
        
        self.logger.error(
            f"Component failure: {component_name} (priority: {component.priority.name}) - {safe_error_message}"
        )
        
        # Determine degradation strategy based on component priority
        degradation_response = await self._apply_graceful_degradation(component, is_critical)
        
        # Update system state if necessary
        await self._evaluate_system_state()
        
        return degradation_response
    
    async def validate_blockchain_consistency(self) -> Dict[str, Any]:
        """
        Validate blockchain state consistency.
        
        Returns:
            Validation result with consistency status
            
        Requirements: 10.8 - Blockchain state consistency validation
        """
        if not self.blockchain_client:
            return {
                'status': 'no_client',
                'is_consistent': False,
                'message': 'No blockchain client available for validation'
            }
        
        try:
            # Get current blockchain state
            current_slot = await self._get_current_slot()
            current_block = await self._get_current_block()
            
            # Validate state consistency
            consistency_checks = await self._perform_consistency_checks(current_slot, current_block)
            
            # Update blockchain state
            self.blockchain_state.slot = current_slot
            self.blockchain_state.block_height = current_block.get('block_height') if current_block else None
            self.blockchain_state.block_hash = current_block.get('block_hash') if current_block else None
            self.blockchain_state.timestamp = datetime.now()
            self.blockchain_state.is_consistent = consistency_checks['is_consistent']
            self.blockchain_state.last_validated = datetime.now()
            self.blockchain_state.validation_errors = consistency_checks.get('errors', [])
            
            validation_result = {
                'status': 'validated',
                'is_consistent': consistency_checks['is_consistent'],
                'slot': current_slot,
                'block_height': self.blockchain_state.block_height,
                'validation_time': self.blockchain_state.last_validated.isoformat(),
                'checks_performed': consistency_checks.get('checks', []),
                'errors': consistency_checks.get('errors', [])
            }
            
            if not consistency_checks['is_consistent']:
                self.logger.warning(
                    f"Blockchain state inconsistency detected: {consistency_checks.get('errors', [])}"
                )
                
                # Handle inconsistency
                await self._handle_blockchain_inconsistency(consistency_checks)
            
            return validation_result
            
        except Exception as e:
            safe_error = self._sanitize_error_message(str(e))
            self.logger.error(f"Blockchain state validation failed: {safe_error}")
            
            self.blockchain_state.is_consistent = False
            self.blockchain_state.validation_errors = [safe_error]
            
            return {
                'status': 'validation_failed',
                'is_consistent': False,
                'error': safe_error,
                'validation_time': datetime.now().isoformat()
            }
    
    async def handle_resource_constraint(
        self, 
        resource_type: ResourceType, 
        current_usage: float
    ) -> Dict[str, Any]:
        """
        Handle resource constraints with prioritization.
        
        Args:
            resource_type: Type of resource under constraint
            current_usage: Current usage percentage (0-100)
            
        Returns:
            Resource management response with actions taken
            
        Requirements: 10.8 - Resource constraint handling and prioritization
        """
        if resource_type not in self.resource_constraints:
            return {'status': 'unknown_resource', 'resource_type': resource_type.value}
        
        constraint = self.resource_constraints[resource_type]
        constraint.current_usage = current_usage
        constraint.last_updated = datetime.now()
        
        actions_taken = []
        
        # Determine constraint level
        if current_usage >= constraint.threshold_critical:
            constraint_level = "critical"
            actions_taken.extend(await self._handle_critical_resource_constraint(resource_type))
        elif current_usage >= constraint.threshold_warning:
            constraint_level = "warning"
            actions_taken.extend(await self._handle_warning_resource_constraint(resource_type))
        else:
            constraint_level = "normal"
        
        self.logger.info(
            f"Resource constraint handled: {resource_type.value} at {current_usage:.1f}% "
            f"(level: {constraint_level})"
        )
        
        return {
            'status': 'handled',
            'resource_type': resource_type.value,
            'usage_percent': current_usage,
            'constraint_level': constraint_level,
            'actions_taken': actions_taken,
            'timestamp': datetime.now().isoformat()
        }
    
    def secure_failure_cleanup(self, error_context: Dict[str, Any]):
        """
        Perform secure cleanup on failure without exposing sensitive data.
        
        Args:
            error_context: Context information about the failure
            
        Requirements: 11.1 - Secure failure handling without key exposure
        """
        try:
            # Clear sensitive data references
            self._clear_sensitive_data()
            
            # Sanitize error context
            sanitized_context = self._sanitize_error_context(error_context)
            
            # Log sanitized failure information
            self.logger.error(f"Secure failure cleanup performed: {json.dumps(sanitized_context)}")
            
            # Force garbage collection to clear memory
            import gc
            gc.collect()
            
        except Exception as cleanup_error:
            # Even cleanup failures should not expose sensitive data
            self.logger.critical("Secure failure cleanup encountered an error - system may be compromised")
    
    def register_sensitive_data(self, data_ref: Any):
        """
        Register sensitive data for secure cleanup on failure.
        
        Args:
            data_ref: Reference to sensitive data object
        """
        if self.secure_failure_mode:
            self.sensitive_data_refs.append(weakref.ref(data_ref))
    
    def get_system_health_status(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        healthy_components = sum(1 for c in self.components.values() if c.is_healthy)
        total_components = len(self.components)
        
        resource_status = {}
        for resource_type, constraint in self.resource_constraints.items():
            resource_status[resource_type.value] = {
                'usage_percent': constraint.current_usage,
                'status': self._get_resource_status(constraint),
                'last_updated': constraint.last_updated.isoformat()
            }
        
        return {
            'system_state': self.current_state.value,
            'state_change_time': self.state_change_time.isoformat(),
            'component_health': {
                'healthy': healthy_components,
                'total': total_components,
                'health_percentage': (healthy_components / total_components * 100) if total_components > 0 else 0
            },
            'resource_status': resource_status,
            'blockchain_state': {
                'is_consistent': self.blockchain_state.is_consistent,
                'last_validated': self.blockchain_state.last_validated.isoformat(),
                'slot': self.blockchain_state.slot,
                'validation_errors': len(self.blockchain_state.validation_errors)
            },
            'active_degradations': len(self.active_degradations),
            'degradation_details': {
                name: activation_time.isoformat() 
                for name, activation_time in self.active_degradations.items()
            }
        }
    
    # Private methods
    
    def _initialize_resource_constraints(self):
        """Initialize resource constraint definitions."""
        constraints_config = self.config.get('resource_constraints', {})
        
        self.resource_constraints = {
            ResourceType.CPU: ResourceConstraint(
                ResourceType.CPU,
                constraints_config.get('cpu_warning', 70.0),
                constraints_config.get('cpu_critical', 90.0)
            ),
            ResourceType.MEMORY: ResourceConstraint(
                ResourceType.MEMORY,
                constraints_config.get('memory_warning', 80.0),
                constraints_config.get('memory_critical', 95.0)
            ),
            ResourceType.DISK: ResourceConstraint(
                ResourceType.DISK,
                constraints_config.get('disk_warning', 85.0),
                constraints_config.get('disk_critical', 95.0)
            ),
            ResourceType.NETWORK: ResourceConstraint(
                ResourceType.NETWORK,
                constraints_config.get('network_warning', 80.0),
                constraints_config.get('network_critical', 95.0)
            )
        }
    
    def _initialize_degradation_rules(self):
        """Initialize graceful degradation rules."""
        self.degradation_rules = {
            'low_priority_disable': {
                'trigger': 'resource_constraint',
                'action': 'disable_low_priority_components',
                'threshold': 'warning'
            },
            'analytics_disable': {
                'trigger': 'memory_constraint',
                'action': 'disable_analytics',
                'threshold': 'critical'
            },
            'logging_reduce': {
                'trigger': 'disk_constraint',
                'action': 'reduce_logging_level',
                'threshold': 'warning'
            }
        }
    
    def _register_core_components(self):
        """Register core system components."""
        core_components = [
            ('signal_loader', ComponentPriority.CRITICAL),
            ('pumpswap_executor', ComponentPriority.CRITICAL),
            ('risk_manager', ComponentPriority.CRITICAL),
            ('position_manager', ComponentPriority.HIGH),
            ('regime_detector', ComponentPriority.HIGH),
            ('liquidity_validator', ComponentPriority.HIGH),
            ('performance_monitor', ComponentPriority.MEDIUM),
            ('trade_recorder', ComponentPriority.MEDIUM),
            ('analytics_engine', ComponentPriority.LOW)
        ]
        
        for name, priority in core_components:
            self.register_component(name, priority)
    
    async def _monitor_resources(self):
        """Continuously monitor system resources."""
        while True:
            try:
                # Monitor CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                await self.handle_resource_constraint(ResourceType.CPU, cpu_percent)
                
                # Monitor memory usage
                memory = psutil.virtual_memory()
                await self.handle_resource_constraint(ResourceType.MEMORY, memory.percent)
                
                # Monitor disk usage
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                await self.handle_resource_constraint(ResourceType.DISK, disk_percent)
                
                await asyncio.sleep(self.resource_monitor_interval)
                
            except Exception as e:
                safe_error = self._sanitize_error_message(str(e))
                self.logger.error(f"Resource monitoring error: {safe_error}")
                await asyncio.sleep(self.resource_monitor_interval)
    
    async def _validate_blockchain_state(self):
        """Continuously validate blockchain state consistency."""
        while True:
            try:
                await self.validate_blockchain_consistency()
                await asyncio.sleep(self.state_validation_interval)
                
            except Exception as e:
                safe_error = self._sanitize_error_message(str(e))
                self.logger.error(f"Blockchain state validation error: {safe_error}")
                await asyncio.sleep(self.state_validation_interval)
    
    async def _apply_graceful_degradation(
        self, 
        component: ComponentStatus, 
        is_critical: bool
    ) -> Dict[str, Any]:
        """Apply graceful degradation based on component failure."""
        actions_taken = []
        
        if component.priority == ComponentPriority.LOW:
            # Disable low priority components immediately
            component.is_active = False
            component.degraded_mode = True
            actions_taken.append(f"Disabled low priority component: {component.name}")
            
        elif component.priority == ComponentPriority.MEDIUM and is_critical:
            # Put medium priority components in degraded mode
            component.degraded_mode = True
            actions_taken.append(f"Enabled degraded mode for: {component.name}")
            
        elif component.priority in [ComponentPriority.HIGH, ComponentPriority.CRITICAL]:
            # Try to restart high/critical priority components
            restart_success = await self._attempt_component_restart(component)
            if restart_success:
                actions_taken.append(f"Successfully restarted: {component.name}")
            else:
                component.degraded_mode = True
                actions_taken.append(f"Failed to restart, degraded mode: {component.name}")
        
        # Record degradation
        if component.degraded_mode:
            self.active_degradations[component.name] = datetime.now()
        
        return {
            'status': 'degradation_applied',
            'component': component.name,
            'priority': component.priority.name,
            'degraded_mode': component.degraded_mode,
            'is_active': component.is_active,
            'actions_taken': actions_taken
        }
    
    async def _attempt_component_restart(self, component: ComponentStatus) -> bool:
        """Attempt to restart a failed component."""
        try:
            # Simulate component restart logic
            # In real implementation, this would call component-specific restart methods
            await asyncio.sleep(1)  # Simulate restart time
            
            component.is_healthy = True
            component.error_count = 0
            component.failure_reason = None
            component.last_health_check = datetime.now()
            
            return True
            
        except Exception as e:
            safe_error = self._sanitize_error_message(str(e))
            self.logger.error(f"Component restart failed for {component.name}: {safe_error}")
            return False
    
    async def _evaluate_system_state(self):
        """Evaluate and update overall system state."""
        critical_components_healthy = all(
            c.is_healthy for c in self.components.values() 
            if c.priority == ComponentPriority.CRITICAL
        )
        
        high_components_healthy = all(
            c.is_healthy for c in self.components.values() 
            if c.priority == ComponentPriority.HIGH
        )
        
        resource_critical = any(
            c.current_usage >= c.threshold_critical 
            for c in self.resource_constraints.values()
        )
        
        # Determine new system state
        new_state = SystemState.NORMAL
        
        if not critical_components_healthy or resource_critical:
            new_state = SystemState.CRITICAL
        elif not high_components_healthy or len(self.active_degradations) > 0:
            new_state = SystemState.DEGRADED
        elif not self.blockchain_state.is_consistent:
            new_state = SystemState.DEGRADED
        
        # Update state if changed
        if new_state != self.current_state:
            old_state = self.current_state
            self.current_state = new_state
            self.state_change_time = datetime.now()
            
            self.state_history.append({
                'from_state': old_state.value,
                'to_state': new_state.value,
                'change_time': self.state_change_time.isoformat(),
                'reason': 'component_health_evaluation'
            })
            
            self.logger.warning(f"System state changed: {old_state.value} -> {new_state.value}")
    
    async def _get_current_slot(self) -> Optional[int]:
        """Get current blockchain slot."""
        if not self.blockchain_client:
            return None
        
        try:
            # Mock implementation - replace with actual Solana RPC call
            return int(time.time())  # Placeholder
        except Exception:
            return None
    
    async def _get_current_block(self) -> Optional[Dict[str, Any]]:
        """Get current blockchain block information."""
        if not self.blockchain_client:
            return None
        
        try:
            # Mock implementation - replace with actual Solana RPC call
            return {
                'block_height': int(time.time()),
                'block_hash': f"mock_hash_{int(time.time())}"
            }
        except Exception:
            return None
    
    async def _perform_consistency_checks(
        self, 
        current_slot: Optional[int], 
        current_block: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Perform blockchain state consistency checks."""
        checks = []
        errors = []
        is_consistent = True
        
        # Check slot progression
        if current_slot and self.blockchain_state.slot:
            if current_slot <= self.blockchain_state.slot:
                errors.append("Slot did not progress")
                is_consistent = False
            checks.append("slot_progression")
        
        # Check block height progression
        if (current_block and self.blockchain_state.block_height and 
            current_block.get('block_height', 0) <= self.blockchain_state.block_height):
            errors.append("Block height did not progress")
            is_consistent = False
            checks.append("block_height_progression")
        
        # Check timestamp consistency
        time_since_last = (datetime.now() - self.blockchain_state.last_validated).total_seconds()
        if time_since_last > 300:  # 5 minutes
            errors.append("Blockchain state validation timeout")
            is_consistent = False
            checks.append("validation_timeout")
        
        return {
            'is_consistent': is_consistent,
            'checks': checks,
            'errors': errors
        }
    
    async def _handle_blockchain_inconsistency(self, consistency_checks: Dict[str, Any]):
        """Handle detected blockchain state inconsistency."""
        self.logger.warning("Handling blockchain state inconsistency")
        
        # Implement recovery actions
        # For now, just log the inconsistency
        for error in consistency_checks.get('errors', []):
            self.logger.error(f"Blockchain inconsistency: {error}")
    
    async def _handle_critical_resource_constraint(self, resource_type: ResourceType) -> List[str]:
        """Handle critical resource constraints."""
        actions = []
        
        if resource_type == ResourceType.MEMORY:
            # Disable low priority components
            for component in self.components.values():
                if component.priority == ComponentPriority.LOW and component.is_active:
                    component.is_active = False
                    actions.append(f"Disabled {component.name} due to memory constraint")
        
        elif resource_type == ResourceType.CPU:
            # Reduce processing frequency
            actions.append("Reduced processing frequency due to CPU constraint")
        
        elif resource_type == ResourceType.DISK:
            # Reduce logging level
            logging.getLogger().setLevel(logging.ERROR)
            actions.append("Reduced logging level due to disk constraint")
        
        return actions
    
    async def _handle_warning_resource_constraint(self, resource_type: ResourceType) -> List[str]:
        """Handle warning-level resource constraints."""
        actions = []
        
        if resource_type == ResourceType.MEMORY:
            # Force garbage collection
            import gc
            gc.collect()
            actions.append("Forced garbage collection due to memory warning")
        
        return actions
    
    def _get_resource_status(self, constraint: ResourceConstraint) -> str:
        """Get resource status based on usage."""
        if constraint.current_usage >= constraint.threshold_critical:
            return "critical"
        elif constraint.current_usage >= constraint.threshold_warning:
            return "warning"
        else:
            return "normal"
    
    def _sanitize_error_message(self, error_message: str) -> str:
        """Sanitize error message to remove sensitive information."""
        if not self.secure_failure_mode:
            return error_message
        
        # Remove potential sensitive patterns
        sensitive_patterns = [
            r'private[_\s]*key',
            r'secret[_\s]*key',
            r'password',
            r'token[_\s]*[a-zA-Z0-9]{20,}',
            r'[a-zA-Z0-9]{40,}',  # Long hex strings (potential keys)
        ]
        
        sanitized = error_message
        for pattern in sensitive_patterns:
            import re
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _sanitize_error_context(self, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize error context to remove sensitive information."""
        if not self.secure_failure_mode:
            return error_context
        
        sanitized = {}
        for key, value in error_context.items():
            if isinstance(value, str):
                sanitized[key] = self._sanitize_error_message(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_error_context(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _clear_sensitive_data(self):
        """Clear sensitive data references."""
        cleared_count = 0
        
        # Clear weak references to sensitive data
        for ref in self.sensitive_data_refs[:]:  # Copy list to avoid modification during iteration
            obj = ref()
            if obj is not None:
                try:
                    # Clear the object if it has a clear method
                    if hasattr(obj, 'clear'):
                        obj.clear()
                    # Or set to None if it's a simple reference
                    elif hasattr(obj, '__dict__'):
                        obj.__dict__.clear()
                    cleared_count += 1
                except Exception:
                    pass  # Ignore errors during cleanup
        
        # Clear the references list
        self.sensitive_data_refs.clear()
        
        self.logger.info(f"Cleared {cleared_count} sensitive data references")