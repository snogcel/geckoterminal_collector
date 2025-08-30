"""
Collection status monitoring and failure alerting system.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum

from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.monitoring.execution_history import ExecutionHistoryTracker, ExecutionStatus
from gecko_terminal_collector.monitoring.performance_metrics import MetricsCollector

logger = logging.getLogger(__name__)


class CollectionStatus(Enum):
    """Collection status enumeration."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert information."""
    id: str
    level: AlertLevel
    collector_type: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "level": self.level.value,
            "collector_type": self.collector_type,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


@dataclass
class CollectorHealthStatus:
    """Health status for a collector."""
    collector_type: str
    status: CollectionStatus
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    success_rate_24h: float = 100.0
    average_execution_time: float = 0.0
    total_executions: int = 0
    health_score: float = 100.0
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "collector_type": self.collector_type,
            "status": self.status.value,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "consecutive_failures": self.consecutive_failures,
            "success_rate_24h": self.success_rate_24h,
            "average_execution_time": self.average_execution_time,
            "total_executions": self.total_executions,
            "health_score": self.health_score,
            "issues": self.issues
        }


class CollectionMonitor:
    """
    Monitors collection operations and provides alerting capabilities.
    
    Tracks collector health, generates alerts for failures and performance issues,
    and provides comprehensive monitoring and reporting functionality.
    """
    
    def __init__(
        self,
        execution_history: ExecutionHistoryTracker,
        metrics_collector: MetricsCollector,
        alert_handlers: Optional[List[Callable[[Alert], None]]] = None
    ):
        """
        Initialize collection monitor.
        
        Args:
            execution_history: Execution history tracker
            metrics_collector: Performance metrics collector
            alert_handlers: Optional list of alert handler functions
        """
        self.execution_history = execution_history
        self.metrics_collector = metrics_collector
        self.alert_handlers = alert_handlers or []
        
        # Alert management
        self._alerts: Dict[str, Alert] = {}
        self._alert_counter = 0
        self._suppressed_alerts: Set[str] = set()
        
        # Health monitoring configuration
        self.health_config = {
            "max_consecutive_failures": 3,
            "min_success_rate_24h": 80.0,
            "max_execution_time": 300.0,  # 5 minutes
            "stale_threshold_hours": 6,   # Consider stale if no execution in 6 hours
            "alert_cooldown_minutes": 30  # Minimum time between similar alerts
        }
        
        # Monitoring state
        self._collector_health: Dict[str, CollectorHealthStatus] = {}
        self._last_alert_times: Dict[str, datetime] = {}
        
        logger.info("Collection monitor initialized")
    
    def update_from_execution(
        self,
        collector_type: str,
        result: CollectionResult,
        execution_time: float
    ) -> None:
        """
        Update monitoring data from a collection execution.
        
        Args:
            collector_type: Type of collector
            result: Collection result
            execution_time: Execution time in seconds
        """
        # Update health status
        self._update_collector_health(collector_type, result, execution_time)
        
        # Check for alerts
        self._check_for_alerts(collector_type)
        
        logger.debug(f"Updated monitoring data for {collector_type}")
    
    def _update_collector_health(
        self,
        collector_type: str,
        result: CollectionResult,
        execution_time: float
    ) -> None:
        """Update health status for a collector."""
        if collector_type not in self._collector_health:
            self._collector_health[collector_type] = CollectorHealthStatus(
                collector_type=collector_type,
                status=CollectionStatus.UNKNOWN
            )
        
        health = self._collector_health[collector_type]
        health.total_executions += 1
        
        if result.success:
            health.last_success = result.collection_time
            health.consecutive_failures = 0
        else:
            health.last_failure = result.collection_time
            health.consecutive_failures += 1
        
        # Calculate 24-hour success rate
        stats = self.execution_history.get_execution_statistics(
            collector_type=collector_type,
            time_window=timedelta(hours=24)
        )
        health.success_rate_24h = stats.get("success_rate", 100.0)
        
        # If no executions in history, use current execution for success rate
        if stats.get("total_executions", 0) == 0:
            health.success_rate_24h = 100.0 if result.success else 0.0
        
        # Get performance metrics
        metrics = self.metrics_collector.get_metrics(collector_type)
        if collector_type in metrics:
            perf_metrics = metrics[collector_type]
            health.average_execution_time = perf_metrics.average_execution_time
        
        # Calculate health score
        health.health_score = self.metrics_collector.get_health_score(collector_type)
        
        # Determine status and issues
        health.issues.clear()
        
        if health.consecutive_failures >= self.health_config["max_consecutive_failures"]:
            health.status = CollectionStatus.CRITICAL
            health.issues.append(f"Consecutive failures: {health.consecutive_failures}")
        elif health.success_rate_24h < self.health_config["min_success_rate_24h"]:
            health.status = CollectionStatus.WARNING
            health.issues.append(f"Low success rate: {health.success_rate_24h:.1f}%")
        elif health.average_execution_time > self.health_config["max_execution_time"]:
            health.status = CollectionStatus.WARNING
            health.issues.append(f"Slow execution: {health.average_execution_time:.1f}s")
        elif self._is_collector_stale(collector_type):
            health.status = CollectionStatus.WARNING
            health.issues.append("No recent executions")
        else:
            health.status = CollectionStatus.HEALTHY
    
    def _is_collector_stale(self, collector_type: str) -> bool:
        """Check if a collector is stale (no recent executions)."""
        health = self._collector_health.get(collector_type)
        if not health or not health.last_success:
            return True
        
        stale_threshold = timedelta(hours=self.health_config["stale_threshold_hours"])
        return datetime.now() - health.last_success > stale_threshold
    
    def _check_for_alerts(self, collector_type: str) -> None:
        """Check if alerts should be generated for a collector."""
        health = self._collector_health.get(collector_type)
        if not health:
            return
        
        # Check alert cooldown
        alert_key = f"{collector_type}_{health.status.value}"
        if self._is_alert_suppressed(alert_key):
            return
        
        # Generate alerts based on status
        if health.status == CollectionStatus.CRITICAL:
            self._create_alert(
                AlertLevel.CRITICAL,
                collector_type,
                f"Collector in critical state: {'; '.join(health.issues)}",
                {"consecutive_failures": health.consecutive_failures}
            )
        elif health.status == CollectionStatus.WARNING:
            self._create_alert(
                AlertLevel.WARNING,
                collector_type,
                f"Collector performance issues: {'; '.join(health.issues)}",
                {"success_rate": health.success_rate_24h}
            )
    
    def _is_alert_suppressed(self, alert_key: str) -> bool:
        """Check if an alert type is currently suppressed."""
        if alert_key in self._suppressed_alerts:
            return True
        
        # Check cooldown period
        if alert_key in self._last_alert_times:
            cooldown = timedelta(minutes=self.health_config["alert_cooldown_minutes"])
            if datetime.now() - self._last_alert_times[alert_key] < cooldown:
                return True
        
        return False
    
    def _create_alert(
        self,
        level: AlertLevel,
        collector_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create and process a new alert."""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}_{int(datetime.now().timestamp())}"
        
        alert = Alert(
            id=alert_id,
            level=level,
            collector_type=collector_type,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self._alerts[alert_id] = alert
        
        # Update alert tracking
        alert_key = f"{collector_type}_{level.value}"
        self._last_alert_times[alert_key] = alert.timestamp
        
        # Send to alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
        
        logger.warning(f"Generated {level.value} alert for {collector_type}: {message}")
        return alert
    
    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler function."""
        self.alert_handlers.append(handler)
        logger.info("Added alert handler")
    
    def remove_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove an alert handler function."""
        if handler in self.alert_handlers:
            self.alert_handlers.remove(handler)
            logger.info("Removed alert handler")
    
    def get_collector_health(self, collector_type: Optional[str] = None) -> Dict[str, CollectorHealthStatus]:
        """
        Get health status for collectors.
        
        Args:
            collector_type: Optional filter by collector type
            
        Returns:
            Dictionary of collector health statuses
        """
        if collector_type:
            return {collector_type: self._collector_health.get(collector_type)} if collector_type in self._collector_health else {}
        return self._collector_health.copy()
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get overall system health summary.
        
        Returns:
            Dictionary with system health information
        """
        if not self._collector_health:
            return {
                "overall_status": CollectionStatus.UNKNOWN.value,
                "total_collectors": 0,
                "healthy_collectors": 0,
                "warning_collectors": 0,
                "critical_collectors": 0,
                "average_health_score": 100.0
            }
        
        status_counts = {
            CollectionStatus.HEALTHY: 0,
            CollectionStatus.WARNING: 0,
            CollectionStatus.CRITICAL: 0,
            CollectionStatus.UNKNOWN: 0
        }
        
        total_health_score = 0.0
        for health in self._collector_health.values():
            status_counts[health.status] += 1
            total_health_score += health.health_score
        
        # Determine overall status
        if status_counts[CollectionStatus.CRITICAL] > 0:
            overall_status = CollectionStatus.CRITICAL
        elif status_counts[CollectionStatus.WARNING] > 0:
            overall_status = CollectionStatus.WARNING
        elif status_counts[CollectionStatus.HEALTHY] > 0:
            overall_status = CollectionStatus.HEALTHY
        else:
            overall_status = CollectionStatus.UNKNOWN
        
        average_health_score = total_health_score / len(self._collector_health)
        
        return {
            "overall_status": overall_status.value,
            "total_collectors": len(self._collector_health),
            "healthy_collectors": status_counts[CollectionStatus.HEALTHY],
            "warning_collectors": status_counts[CollectionStatus.WARNING],
            "critical_collectors": status_counts[CollectionStatus.CRITICAL],
            "unknown_collectors": status_counts[CollectionStatus.UNKNOWN],
            "average_health_score": average_health_score
        }
    
    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        collector_type: Optional[str] = None,
        unresolved_only: bool = True
    ) -> List[Alert]:
        """
        Get alerts with optional filtering.
        
        Args:
            level: Filter by alert level
            collector_type: Filter by collector type
            unresolved_only: Only return unresolved alerts
            
        Returns:
            List of Alert objects
        """
        alerts = list(self._alerts.values())
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if collector_type:
            alerts = [a for a in alerts if a.collector_type == collector_type]
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        # Sort by timestamp (most recent first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            
        Returns:
            True if alert was found and acknowledged, False otherwise
        """
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            logger.info(f"Acknowledged alert {alert_id}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            
        Returns:
            True if alert was found and resolved, False otherwise
        """
        if alert_id in self._alerts:
            self._alerts[alert_id].resolved = True
            logger.info(f"Resolved alert {alert_id}")
            return True
        return False
    
    def suppress_alerts(self, collector_type: str, duration_minutes: int = 60) -> None:
        """
        Suppress alerts for a collector type.
        
        Args:
            collector_type: Collector type to suppress alerts for
            duration_minutes: Duration to suppress alerts
        """
        # Add to suppressed set
        for status in CollectionStatus:
            alert_key = f"{collector_type}_{status.value}"
            self._suppressed_alerts.add(alert_key)
        
        # Schedule removal of suppression
        async def remove_suppression():
            await asyncio.sleep(duration_minutes * 60)
            for status in CollectionStatus:
                alert_key = f"{collector_type}_{status.value}"
                self._suppressed_alerts.discard(alert_key)
            logger.info(f"Removed alert suppression for {collector_type}")
        
        try:
            asyncio.create_task(remove_suppression())
        except RuntimeError:
            # No event loop running, suppression will be permanent
            logger.warning(f"No event loop running, alert suppression for {collector_type} will be permanent")
        logger.info(f"Suppressed alerts for {collector_type} for {duration_minutes} minutes")
    
    def cleanup_old_alerts(self, days_to_keep: int = 7) -> int:
        """
        Clean up old resolved alerts.
        
        Args:
            days_to_keep: Number of days of alerts to keep
            
        Returns:
            Number of alerts removed
        """
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        
        alerts_to_remove = [
            alert_id for alert_id, alert in self._alerts.items()
            if alert.resolved and alert.timestamp < cutoff_time
        ]
        
        for alert_id in alerts_to_remove:
            del self._alerts[alert_id]
        
        if alerts_to_remove:
            logger.info(f"Cleaned up {len(alerts_to_remove)} old alerts")
        
        return len(alerts_to_remove)
    
    def export_monitoring_data(self) -> Dict[str, Any]:
        """
        Export comprehensive monitoring data.
        
        Returns:
            Dictionary with all monitoring information
        """
        return {
            "export_time": datetime.now().isoformat(),
            "system_health": self.get_system_health_summary(),
            "collector_health": {
                name: health.to_dict() for name, health in self._collector_health.items()
            },
            "alerts": {
                "total_alerts": len(self._alerts),
                "unresolved_alerts": len([a for a in self._alerts.values() if not a.resolved]),
                "alerts_by_level": {
                    level.value: len([a for a in self._alerts.values() if a.level == level])
                    for level in AlertLevel
                },
                "recent_alerts": [
                    alert.to_dict() for alert in self.get_alerts(unresolved_only=False)[:10]
                ]
            },
            "configuration": self.health_config
        }