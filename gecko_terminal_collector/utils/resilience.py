"""
System resilience utilities including health checks, graceful shutdown, and monitoring.
"""

import asyncio
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set
import psutil
import gc

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ComponentType(Enum):
    """Types of system components that can be monitored."""
    DATABASE = "database"
    API_CLIENT = "api_client"
    COLLECTOR = "collector"
    SCHEDULER = "scheduler"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    component_name: str
    component_type: ComponentType
    status: HealthStatus
    message: str
    timestamp: datetime
    response_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_connections: int
    process_count: int
    timestamp: datetime


class HealthChecker:
    """
    Comprehensive health checking system for monitoring component health.
    
    Provides configurable health checks for different system components
    with automatic status determination and alerting capabilities.
    """
    
    def __init__(self):
        self._health_checks: Dict[str, Callable] = {}
        self._health_history: Dict[str, List[HealthCheckResult]] = {}
        self._health_thresholds: Dict[str, Dict[str, float]] = {}
        self._last_check_times: Dict[str, datetime] = {}
        self._setup_default_checks()
    
    def _setup_default_checks(self) -> None:
        """Set up default system health checks."""
        
        # Memory health check
        self.register_health_check(
            "system_memory",
            self._check_memory_health,
            ComponentType.MEMORY,
            thresholds={
                "warning": 80.0,  # 80% memory usage
                "critical": 95.0  # 95% memory usage
            }
        )
        
        # Disk health check
        self.register_health_check(
            "system_disk",
            self._check_disk_health,
            ComponentType.DISK,
            thresholds={
                "warning": 80.0,  # 80% disk usage
                "critical": 95.0  # 95% disk usage
            }
        )
    
    def register_health_check(
        self,
        name: str,
        check_function: Callable,
        component_type: ComponentType,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Register a health check function.
        
        Args:
            name: Unique name for the health check
            check_function: Async function that returns HealthCheckResult
            component_type: Type of component being checked
            thresholds: Optional thresholds for status determination
        """
        self._health_checks[name] = check_function
        self._health_thresholds[name] = thresholds or {}
        self._health_history[name] = []
        logger.info(f"Registered health check: {name} ({component_type.value})")
    
    async def check_health(self, component_name: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """
        Execute health checks for specified component or all components.
        
        Args:
            component_name: Specific component to check, or None for all
            
        Returns:
            Dictionary mapping component names to health check results
        """
        results = {}
        
        checks_to_run = {}
        if component_name:
            if component_name in self._health_checks:
                checks_to_run[component_name] = self._health_checks[component_name]
        else:
            checks_to_run = self._health_checks
        
        for name, check_func in checks_to_run.items():
            try:
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                if isinstance(result, HealthCheckResult):
                    result.response_time_ms = response_time
                    results[name] = result
                else:
                    # Create result from returned data
                    results[name] = HealthCheckResult(
                        component_name=name,
                        component_type=ComponentType.NETWORK,  # Default
                        status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                        message=str(result) if result else "Check failed",
                        timestamp=datetime.now(),
                        response_time_ms=response_time
                    )
                
                # Store in history
                self._health_history[name].append(results[name])
                
                # Keep only recent history (last 100 checks)
                if len(self._health_history[name]) > 100:
                    self._health_history[name] = self._health_history[name][-100:]
                
                self._last_check_times[name] = datetime.now()
                
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = HealthCheckResult(
                    component_name=name,
                    component_type=ComponentType.NETWORK,
                    status=HealthStatus.CRITICAL,
                    message=f"Health check error: {str(e)}",
                    timestamp=datetime.now(),
                    response_time_ms=0.0
                )
        
        return results
    
    async def _check_memory_health(self) -> HealthCheckResult:
        """Check system memory health."""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            available_mb = memory.available / (1024 * 1024)
            
            thresholds = self._health_thresholds.get("system_memory", {})
            warning_threshold = thresholds.get("warning", 80.0)
            critical_threshold = thresholds.get("critical", 95.0)
            
            if memory_percent >= critical_threshold:
                status = HealthStatus.CRITICAL
                message = f"Critical memory usage: {memory_percent:.1f}%"
            elif memory_percent >= warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}%"
            
            return HealthCheckResult(
                component_name="system_memory",
                component_type=ComponentType.MEMORY,
                status=status,
                message=message,
                timestamp=datetime.now(),
                response_time_ms=0.0,
                metadata={
                    "memory_percent": memory_percent,
                    "available_mb": available_mb,
                    "total_mb": memory.total / (1024 * 1024),
                    "used_mb": memory.used / (1024 * 1024)
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component_name="system_memory",
                component_type=ComponentType.MEMORY,
                status=HealthStatus.CRITICAL,
                message=f"Memory check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0.0
            )
    
    async def _check_disk_health(self) -> HealthCheckResult:
        """Check system disk health."""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            free_gb = disk.free / (1024 * 1024 * 1024)
            
            thresholds = self._health_thresholds.get("system_disk", {})
            warning_threshold = thresholds.get("warning", 80.0)
            critical_threshold = thresholds.get("critical", 95.0)
            
            if disk_percent >= critical_threshold:
                status = HealthStatus.CRITICAL
                message = f"Critical disk usage: {disk_percent:.1f}%"
            elif disk_percent >= warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {disk_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {disk_percent:.1f}%"
            
            return HealthCheckResult(
                component_name="system_disk",
                component_type=ComponentType.DISK,
                status=status,
                message=message,
                timestamp=datetime.now(),
                response_time_ms=0.0,
                metadata={
                    "disk_percent": disk_percent,
                    "free_gb": free_gb,
                    "total_gb": disk.total / (1024 * 1024 * 1024),
                    "used_gb": disk.used / (1024 * 1024 * 1024)
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                component_name="system_disk",
                component_type=ComponentType.DISK,
                status=HealthStatus.CRITICAL,
                message=f"Disk check failed: {str(e)}",
                timestamp=datetime.now(),
                response_time_ms=0.0
            )
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        summary = {
            "overall_status": HealthStatus.HEALTHY.value,
            "total_components": len(self._health_checks),
            "healthy_components": 0,
            "degraded_components": 0,
            "unhealthy_components": 0,
            "critical_components": 0,
            "components": {},
            "last_check": None
        }
        
        worst_status = HealthStatus.HEALTHY
        latest_check = None
        
        for name, history in self._health_history.items():
            if not history:
                continue
            
            latest_result = history[-1]
            summary["components"][name] = {
                "status": latest_result.status.value,
                "message": latest_result.message,
                "last_check": latest_result.timestamp.isoformat(),
                "response_time_ms": latest_result.response_time_ms
            }
            
            # Count by status
            if latest_result.status == HealthStatus.HEALTHY:
                summary["healthy_components"] += 1
            elif latest_result.status == HealthStatus.DEGRADED:
                summary["degraded_components"] += 1
                if worst_status == HealthStatus.HEALTHY:
                    worst_status = HealthStatus.DEGRADED
            elif latest_result.status == HealthStatus.UNHEALTHY:
                summary["unhealthy_components"] += 1
                if worst_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                    worst_status = HealthStatus.UNHEALTHY
            elif latest_result.status == HealthStatus.CRITICAL:
                summary["critical_components"] += 1
                worst_status = HealthStatus.CRITICAL
            
            # Track latest check time
            if latest_check is None or latest_result.timestamp > latest_check:
                latest_check = latest_result.timestamp
        
        summary["overall_status"] = worst_status.value
        summary["last_check"] = latest_check.isoformat() if latest_check else None
        
        return summary
    
    def get_component_history(self, component_name: str, limit: int = 10) -> List[HealthCheckResult]:
        """Get health check history for a specific component."""
        history = self._health_history.get(component_name, [])
        return history[-limit:] if history else []


class GracefulShutdownHandler:
    """
    Handles graceful shutdown of the system with proper resource cleanup.
    
    Provides signal handling, resource cleanup coordination, and
    shutdown timeout management to ensure clean system termination.
    """
    
    def __init__(self, shutdown_timeout: int = 30):
        self.shutdown_timeout = shutdown_timeout
        self._shutdown_callbacks: List[Callable] = []
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        if sys.platform != "win32":
            # Unix-like systems
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        else:
            # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._is_shutting_down = True
        
        # Set shutdown event in async context
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._shutdown_event.set)
        except RuntimeError:
            # No running loop, set event directly
            asyncio.run(self._trigger_shutdown())
    
    async def _trigger_shutdown(self) -> None:
        """Trigger shutdown event."""
        self._shutdown_event.set()
    
    def register_shutdown_callback(self, callback: Callable) -> None:
        """
        Register a callback to be called during shutdown.
        
        Args:
            callback: Async or sync function to call during shutdown
        """
        self._shutdown_callbacks.append(callback)
        logger.debug(f"Registered shutdown callback: {callback.__name__}")
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Execute graceful shutdown sequence."""
        if self._is_shutting_down:
            logger.info("Shutdown already in progress")
            return
        
        self._is_shutting_down = True
        logger.info("Starting graceful shutdown sequence...")
        
        start_time = time.time()
        
        # Execute shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                callback_name = getattr(callback, '__name__', str(callback))
                logger.info(f"Executing shutdown callback: {callback_name}")
                
                if asyncio.iscoroutinefunction(callback):
                    await asyncio.wait_for(callback(), timeout=10)
                else:
                    callback()
                    
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown callback {callback_name} timed out")
            except Exception as e:
                logger.error(f"Error in shutdown callback {callback_name}: {e}")
        
        # Force garbage collection
        gc.collect()
        
        elapsed = time.time() - start_time
        logger.info(f"Graceful shutdown completed in {elapsed:.2f} seconds")
    
    @property
    def is_shutting_down(self) -> bool:
        """Check if system is shutting down."""
        return self._is_shutting_down


class SystemMonitor:
    """
    Comprehensive system monitoring with metrics collection and alerting.
    
    Monitors system resources, component health, and performance metrics
    with configurable alerting and automatic recovery actions.
    """
    
    def __init__(
        self,
        health_checker: Optional[HealthChecker] = None,
        monitoring_interval: int = 60
    ):
        self.health_checker = health_checker or HealthChecker()
        self.monitoring_interval = monitoring_interval
        self._monitoring_task: Optional[asyncio.Task] = None
        self._metrics_history: List[SystemMetrics] = []
        self._alert_callbacks: List[Callable] = []
        self._is_monitoring = False
    
    def register_alert_callback(self, callback: Callable) -> None:
        """
        Register callback for system alerts.
        
        Args:
            callback: Function to call when alerts are triggered
        """
        self._alert_callbacks.append(callback)
    
    async def start_monitoring(self) -> None:
        """Start continuous system monitoring."""
        if self._is_monitoring:
            logger.warning("System monitoring already running")
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started system monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self._is_monitoring = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped system monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._is_monitoring:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                self._metrics_history.append(metrics)
                
                # Keep only recent metrics (last 1000 entries)
                if len(self._metrics_history) > 1000:
                    self._metrics_history = self._metrics_history[-1000:]
                
                # Run health checks
                health_results = await self.health_checker.check_health()
                
                # Check for alerts
                await self._check_alerts(metrics, health_results)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_mb=memory.available / (1024 * 1024),
                disk_usage_percent=(disk.used / disk.total) * 100,
                disk_free_gb=disk.free / (1024 * 1024 * 1024),
                network_connections=len(psutil.net_connections()),
                process_count=len(psutil.pids()),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_connections=0,
                process_count=0,
                timestamp=datetime.now()
            )
    
    async def _check_alerts(
        self, 
        metrics: SystemMetrics, 
        health_results: Dict[str, HealthCheckResult]
    ) -> None:
        """Check for alert conditions and trigger callbacks."""
        alerts = []
        
        # Check system resource alerts
        if metrics.memory_percent > 90:
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")
        
        if metrics.disk_usage_percent > 90:
            alerts.append(f"High disk usage: {metrics.disk_usage_percent:.1f}%")
        
        if metrics.cpu_percent > 90:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        
        # Check health status alerts
        for name, result in health_results.items():
            if result.status in [HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]:
                alerts.append(f"Component {name} is {result.status.value}: {result.message}")
        
        # Trigger alert callbacks
        if alerts:
            for callback in self._alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alerts, metrics, health_results)
                    else:
                        callback(alerts, metrics, health_results)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self._metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {"error": "No metrics available for the specified period"}
        
        return {
            "period_hours": hours,
            "sample_count": len(recent_metrics),
            "cpu_percent": {
                "avg": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                "max": max(m.cpu_percent for m in recent_metrics),
                "min": min(m.cpu_percent for m in recent_metrics)
            },
            "memory_percent": {
                "avg": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                "max": max(m.memory_percent for m in recent_metrics),
                "min": min(m.memory_percent for m in recent_metrics)
            },
            "disk_usage_percent": {
                "avg": sum(m.disk_usage_percent for m in recent_metrics) / len(recent_metrics),
                "max": max(m.disk_usage_percent for m in recent_metrics),
                "min": min(m.disk_usage_percent for m in recent_metrics)
            },
            "latest_metrics": {
                "timestamp": recent_metrics[-1].timestamp.isoformat(),
                "cpu_percent": recent_metrics[-1].cpu_percent,
                "memory_percent": recent_metrics[-1].memory_percent,
                "memory_available_mb": recent_metrics[-1].memory_available_mb,
                "disk_usage_percent": recent_metrics[-1].disk_usage_percent,
                "disk_free_gb": recent_metrics[-1].disk_free_gb,
                "network_connections": recent_metrics[-1].network_connections,
                "process_count": recent_metrics[-1].process_count
            }
        }