"""
Health check endpoints and system status monitoring.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from gecko_terminal_collector.utils.resilience import (
    HealthChecker, SystemMonitor, HealthStatus, ComponentType
)
from gecko_terminal_collector.utils.error_handling import ErrorHandler
from gecko_terminal_collector.utils.structured_logging import get_logger, LogContext
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.clients import BaseGeckoClient

logger = get_logger(__name__)


class SystemHealthEndpoints:
    """
    Provides health check endpoints and system status monitoring.
    
    Offers comprehensive health monitoring with detailed component status,
    system metrics, and operational health indicators for monitoring
    and alerting systems.
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        api_client: Optional[BaseGeckoClient] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        self.db_manager = db_manager
        self.api_client = api_client
        self.error_handler = error_handler
        self.health_checker = HealthChecker()
        self.system_monitor = SystemMonitor(self.health_checker)
        
        # Register component-specific health checks
        self._register_component_health_checks()
    
    def _register_component_health_checks(self) -> None:
        """Register health checks for system components."""
        
        # Database health check
        if self.db_manager:
            self.health_checker.register_health_check(
                "database_connection",
                self._check_database_health,
                ComponentType.DATABASE,
                thresholds={"response_time_ms": 1000}
            )
        
        # API client health check
        if self.api_client:
            self.health_checker.register_health_check(
                "api_client",
                self._check_api_health,
                ComponentType.API_CLIENT,
                thresholds={"response_time_ms": 5000}
            )
        
        # Error handler health check
        if self.error_handler:
            self.health_checker.register_health_check(
                "error_handler",
                self._check_error_handler_health,
                ComponentType.COLLECTOR,
                thresholds={"error_rate": 0.1}  # 10% error rate threshold
            )
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = datetime.now()
            
            # Test database connection with a simple query
            async with self.db_manager.get_session() as session:
                result = await session.execute("SELECT 1")
                await result.fetchone()
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            status = HealthStatus.HEALTHY
            message = f"Database connection healthy (response: {response_time:.1f}ms)"
            
            if response_time > 1000:  # 1 second threshold
                status = HealthStatus.DEGRADED
                message = f"Database response slow: {response_time:.1f}ms"
            
            return {
                "status": status.value,
                "message": message,
                "response_time_ms": response_time,
                "connection_pool_size": getattr(self.db_manager.engine.pool, 'size', 0),
                "checked_out_connections": getattr(self.db_manager.engine.pool, 'checkedout', 0)
            }
            
        except Exception as e:
            logger.error("Database health check failed", exc_info=True)
            return {
                "status": HealthStatus.CRITICAL.value,
                "message": f"Database connection failed: {str(e)}",
                "response_time_ms": 0,
                "error": str(e)
            }
    
    async def _check_api_health(self) -> Dict[str, Any]:
        """Check API client connectivity and performance."""
        try:
            start_time = datetime.now()
            
            # Test API connectivity with a simple request
            # This would depend on the specific API client implementation
            # For now, we'll simulate a basic connectivity check
            await asyncio.sleep(0.1)  # Simulate API call
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            status = HealthStatus.HEALTHY
            message = f"API client healthy (response: {response_time:.1f}ms)"
            
            if response_time > 5000:  # 5 second threshold
                status = HealthStatus.DEGRADED
                message = f"API response slow: {response_time:.1f}ms"
            
            return {
                "status": status.value,
                "message": message,
                "response_time_ms": response_time,
                "client_type": self.api_client.__class__.__name__
            }
            
        except Exception as e:
            logger.error("API health check failed", exc_info=True)
            return {
                "status": HealthStatus.CRITICAL.value,
                "message": f"API connection failed: {str(e)}",
                "response_time_ms": 0,
                "error": str(e)
            }
    
    async def _check_error_handler_health(self) -> Dict[str, Any]:
        """Check error handler status and error rates."""
        try:
            health_score = self.error_handler.get_health_score()
            error_stats = self.error_handler.get_error_statistics()
            
            status = HealthStatus.HEALTHY
            message = f"Error handler healthy (health score: {health_score:.2f})"
            
            if health_score < 0.5:
                status = HealthStatus.CRITICAL
                message = f"High error rate detected (health score: {health_score:.2f})"
            elif health_score < 0.8:
                status = HealthStatus.DEGRADED
                message = f"Elevated error rate (health score: {health_score:.2f})"
            
            return {
                "status": status.value,
                "message": message,
                "health_score": health_score,
                "total_errors": error_stats.get("total_errors", 0),
                "error_categories": error_stats.get("error_by_category", {}),
                "circuit_breakers": self.error_handler.get_circuit_breaker_status()
            }
            
        except Exception as e:
            logger.error("Error handler health check failed", exc_info=True)
            return {
                "status": HealthStatus.CRITICAL.value,
                "message": f"Error handler check failed: {str(e)}",
                "error": str(e)
            }
    
    async def get_health_status(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive health status for all or specific components.
        
        Args:
            component: Specific component to check, or None for all
            
        Returns:
            Dictionary with health status information
        """
        try:
            # Run health checks
            health_results = await self.health_checker.check_health(component)
            
            # Get health summary
            health_summary = self.health_checker.get_health_summary()
            
            # Get system metrics
            system_metrics = self.system_monitor.get_metrics_summary(hours=1)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": health_summary["overall_status"],
                "components": {
                    name: {
                        "status": result.status.value,
                        "message": result.message,
                        "last_check": result.timestamp.isoformat(),
                        "response_time_ms": result.response_time_ms,
                        "metadata": result.metadata
                    }
                    for name, result in health_results.items()
                },
                "summary": health_summary,
                "system_metrics": system_metrics
            }
            
        except Exception as e:
            logger.error("Failed to get health status", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "components": {},
                "summary": {},
                "system_metrics": {}
            }
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """
        Get readiness status indicating if the system is ready to serve requests.
        
        Returns:
            Dictionary with readiness information
        """
        try:
            # Check critical components for readiness
            critical_checks = []
            
            if self.db_manager:
                critical_checks.append("database_connection")
            if self.api_client:
                critical_checks.append("api_client")
            
            ready = True
            failed_components = []
            
            for component in critical_checks:
                health_results = await self.health_checker.check_health(component)
                if component in health_results:
                    result = health_results[component]
                    if result.status in [HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]:
                        ready = False
                        failed_components.append(component)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "ready": ready,
                "status": "ready" if ready else "not_ready",
                "failed_components": failed_components,
                "checked_components": critical_checks
            }
            
        except Exception as e:
            logger.error("Failed to get readiness status", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "ready": False,
                "status": "error",
                "error": str(e),
                "failed_components": [],
                "checked_components": []
            }
    
    async def get_liveness_status(self) -> Dict[str, Any]:
        """
        Get liveness status indicating if the system is alive and functioning.
        
        Returns:
            Dictionary with liveness information
        """
        try:
            # Basic liveness check - system is responding
            return {
                "timestamp": datetime.now().isoformat(),
                "alive": True,
                "status": "alive",
                "uptime_seconds": self._get_uptime_seconds()
            }
            
        except Exception as e:
            logger.error("Failed to get liveness status", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "alive": False,
                "status": "error",
                "error": str(e),
                "uptime_seconds": 0
            }
    
    def _get_uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        try:
            import psutil
            return time.time() - psutil.boot_time()
        except:
            return 0.0
    
    async def get_metrics(self, hours: int = 1) -> Dict[str, Any]:
        """
        Get system metrics for the specified time period.
        
        Args:
            hours: Number of hours of metrics to retrieve
            
        Returns:
            Dictionary with system metrics
        """
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "period_hours": hours,
                "system_metrics": self.system_monitor.get_metrics_summary(hours),
                "health_summary": self.health_checker.get_health_summary(),
                "error_statistics": self.error_handler.get_error_statistics() if self.error_handler else {}
            }
            
        except Exception as e:
            logger.error("Failed to get metrics", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "period_hours": hours,
                "error": str(e),
                "system_metrics": {},
                "health_summary": {},
                "error_statistics": {}
            }
    
    async def start_monitoring(self) -> None:
        """Start continuous system monitoring."""
        try:
            await self.system_monitor.start_monitoring()
            logger.info("System monitoring started")
        except Exception as e:
            logger.error("Failed to start system monitoring", exc_info=True)
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        try:
            await self.system_monitor.stop_monitoring()
            logger.info("System monitoring stopped")
        except Exception as e:
            logger.error("Failed to stop system monitoring", exc_info=True)
            raise
    
    def register_alert_callback(self, callback) -> None:
        """Register callback for system alerts."""
        self.system_monitor.register_alert_callback(callback)
    
    async def reset_health_history(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Reset health check history for debugging or maintenance.
        
        Args:
            component: Specific component to reset, or None for all
            
        Returns:
            Dictionary with reset confirmation
        """
        try:
            if component:
                # Reset specific component history
                if component in self.health_checker._health_history:
                    self.health_checker._health_history[component] = []
                    logger.info(f"Reset health history for component: {component}")
                    return {
                        "timestamp": datetime.now().isoformat(),
                        "reset": True,
                        "component": component,
                        "message": f"Health history reset for {component}"
                    }
                else:
                    return {
                        "timestamp": datetime.now().isoformat(),
                        "reset": False,
                        "component": component,
                        "message": f"Component {component} not found"
                    }
            else:
                # Reset all component history
                self.health_checker._health_history.clear()
                self.health_checker._last_check_times.clear()
                logger.info("Reset all health history")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "reset": True,
                    "component": "all",
                    "message": "All health history reset"
                }
                
        except Exception as e:
            logger.error("Failed to reset health history", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "reset": False,
                "error": str(e),
                "message": "Failed to reset health history"
            }


import time