"""
Performance metrics collection and reporting for operational visibility.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import asyncio
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels
        }


@dataclass
class PerformanceMetrics:
    """Container for performance metrics data."""
    collector_type: str
    execution_count: int = 0
    total_execution_time: float = 0.0
    total_records_collected: int = 0
    error_count: int = 0
    last_execution_time: Optional[datetime] = None
    average_execution_time: float = 0.0
    records_per_second: float = 0.0
    success_rate: float = 100.0
    
    def update_from_execution(
        self,
        execution_time: float,
        records_collected: int,
        success: bool
    ) -> None:
        """Update metrics from a single execution."""
        self.execution_count += 1
        self.total_execution_time += execution_time
        self.total_records_collected += records_collected
        self.last_execution_time = datetime.now()
        
        if not success:
            self.error_count += 1
        
        # Calculate derived metrics
        self.average_execution_time = self.total_execution_time / self.execution_count
        self.success_rate = ((self.execution_count - self.error_count) / self.execution_count) * 100
        
        if execution_time > 0:
            self.records_per_second = records_collected / execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "collector_type": self.collector_type,
            "execution_count": self.execution_count,
            "total_execution_time": self.total_execution_time,
            "average_execution_time": self.average_execution_time,
            "total_records_collected": self.total_records_collected,
            "records_per_second": self.records_per_second,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None
        }


class MetricsCollector:
    """
    Collects and manages performance metrics for collection operations.
    
    Provides comprehensive metrics collection with time-series data,
    aggregation capabilities, and operational visibility features.
    """
    
    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.
        
        Args:
            retention_hours: Hours to retain detailed metric data
        """
        self.retention_hours = retention_hours
        self._metrics: Dict[str, PerformanceMetrics] = {}
        self._time_series: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        self._custom_metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._start_time = datetime.now()
        
        # Metric thresholds for alerting
        self.thresholds = {
            "max_execution_time": 300.0,  # 5 minutes
            "min_success_rate": 80.0,     # 80%
            "max_error_rate": 20.0,       # 20%
            "min_records_per_second": 1.0  # 1 record/second
        }
    
    def record_execution(
        self,
        collector_type: str,
        execution_time: float,
        records_collected: int,
        success: bool,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record metrics from a collection execution.
        
        Args:
            collector_type: Type of collector
            execution_time: Time taken for execution in seconds
            records_collected: Number of records collected
            success: Whether the execution was successful
            labels: Optional labels for the metric
        """
        # Update performance metrics
        if collector_type not in self._metrics:
            self._metrics[collector_type] = PerformanceMetrics(collector_type)
        
        metrics = self._metrics[collector_type]
        metrics.update_from_execution(execution_time, records_collected, success)
        
        # Record time-series data
        now = datetime.now()
        self._add_time_series_point(collector_type, "execution_time", execution_time, now)
        self._add_time_series_point(collector_type, "records_collected", records_collected, now)
        self._add_time_series_point(collector_type, "success", 1.0 if success else 0.0, now)
        
        # Record custom metric
        self.record_custom_metric(
            f"{collector_type}_execution",
            execution_time,
            labels or {}
        )
        
        logger.debug(
            f"Recorded metrics for {collector_type}: "
            f"{execution_time:.2f}s, {records_collected} records, "
            f"success: {success}"
        )
    
    def record_custom_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a custom metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels for the metric
        """
        metric_value = MetricValue(
            value=value,
            timestamp=datetime.now(),
            labels=labels or {}
        )
        
        self._custom_metrics[metric_name].append(metric_value)
        
        # Maintain retention limit
        self._cleanup_custom_metrics(metric_name)
    
    def _add_time_series_point(
        self,
        collector_type: str,
        metric_name: str,
        value: float,
        timestamp: datetime
    ) -> None:
        """Add a point to time-series data."""
        series = self._time_series[collector_type][metric_name]
        series.append((timestamp, value))
        
        # Maintain retention limit
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        while series and series[0][0] < cutoff_time:
            series.popleft()
    
    def _cleanup_custom_metrics(self, metric_name: str) -> None:
        """Clean up old custom metric values."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        metrics = self._custom_metrics[metric_name]
        
        # Remove old values
        self._custom_metrics[metric_name] = [
            m for m in metrics if m.timestamp >= cutoff_time
        ]
    
    def get_metrics(self, collector_type: Optional[str] = None) -> Dict[str, PerformanceMetrics]:
        """
        Get performance metrics.
        
        Args:
            collector_type: Optional filter by collector type
            
        Returns:
            Dictionary of performance metrics
        """
        if collector_type:
            return {collector_type: self._metrics.get(collector_type)} if collector_type in self._metrics else {}
        return self._metrics.copy()
    
    def get_time_series_data(
        self,
        collector_type: str,
        metric_name: str,
        time_window: Optional[timedelta] = None
    ) -> List[tuple[datetime, float]]:
        """
        Get time-series data for a specific metric.
        
        Args:
            collector_type: Collector type
            metric_name: Name of the metric
            time_window: Optional time window to filter data
            
        Returns:
            List of (timestamp, value) tuples
        """
        if collector_type not in self._time_series:
            return []
        
        if metric_name not in self._time_series[collector_type]:
            return []
        
        data = list(self._time_series[collector_type][metric_name])
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            data = [(ts, val) for ts, val in data if ts >= cutoff_time]
        
        return data
    
    def get_aggregated_metrics(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics across all collectors.
        
        Args:
            time_window: Optional time window for aggregation
            
        Returns:
            Dictionary with aggregated metrics
        """
        total_executions = sum(m.execution_count for m in self._metrics.values())
        total_records = sum(m.total_records_collected for m in self._metrics.values())
        total_errors = sum(m.error_count for m in self._metrics.values())
        
        if total_executions > 0:
            overall_success_rate = ((total_executions - total_errors) / total_executions) * 100
            average_execution_time = sum(m.total_execution_time for m in self._metrics.values()) / total_executions
        else:
            overall_success_rate = 100.0
            average_execution_time = 0.0
        
        uptime = datetime.now() - self._start_time
        
        return {
            "total_collectors": len(self._metrics),
            "total_executions": total_executions,
            "total_records_collected": total_records,
            "total_errors": total_errors,
            "overall_success_rate": overall_success_rate,
            "average_execution_time": average_execution_time,
            "system_uptime_seconds": uptime.total_seconds(),
            "time_window": str(time_window) if time_window else "all_time"
        }
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """
        Get performance alerts based on configured thresholds.
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        for collector_type, metrics in self._metrics.items():
            # Check execution time threshold
            if metrics.average_execution_time > self.thresholds["max_execution_time"]:
                alerts.append({
                    "type": "performance",
                    "severity": "warning",
                    "collector_type": collector_type,
                    "message": f"Average execution time ({metrics.average_execution_time:.2f}s) exceeds threshold ({self.thresholds['max_execution_time']}s)",
                    "metric": "execution_time",
                    "value": metrics.average_execution_time,
                    "threshold": self.thresholds["max_execution_time"]
                })
            
            # Check success rate threshold
            if metrics.success_rate < self.thresholds["min_success_rate"]:
                alerts.append({
                    "type": "reliability",
                    "severity": "error",
                    "collector_type": collector_type,
                    "message": f"Success rate ({metrics.success_rate:.1f}%) below threshold ({self.thresholds['min_success_rate']}%)",
                    "metric": "success_rate",
                    "value": metrics.success_rate,
                    "threshold": self.thresholds["min_success_rate"]
                })
            
            # Check records per second threshold
            if metrics.records_per_second < self.thresholds["min_records_per_second"]:
                alerts.append({
                    "type": "performance",
                    "severity": "warning",
                    "collector_type": collector_type,
                    "message": f"Records per second ({metrics.records_per_second:.2f}) below threshold ({self.thresholds['min_records_per_second']})",
                    "metric": "records_per_second",
                    "value": metrics.records_per_second,
                    "threshold": self.thresholds["min_records_per_second"]
                })
        
        return alerts
    
    def get_custom_metrics(
        self,
        metric_name: Optional[str] = None,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, List[MetricValue]]:
        """
        Get custom metrics data.
        
        Args:
            metric_name: Optional filter by metric name
            time_window: Optional time window to filter data
            
        Returns:
            Dictionary of custom metrics
        """
        if metric_name:
            metrics = {metric_name: self._custom_metrics.get(metric_name, [])}
        else:
            metrics = dict(self._custom_metrics)
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            filtered_metrics = {}
            for name, values in metrics.items():
                filtered_metrics[name] = [
                    v for v in values if v.timestamp >= cutoff_time
                ]
            metrics = filtered_metrics
        
        return metrics
    
    def export_metrics(
        self,
        format_type: str = "dict",
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Export all metrics data for external analysis.
        
        Args:
            format_type: Export format ("dict", "prometheus", etc.)
            time_window: Optional time window for data
            
        Returns:
            Exported metrics data
        """
        export_data = {
            "export_time": datetime.now().isoformat(),
            "system_uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "performance_metrics": {
                name: metrics.to_dict() for name, metrics in self._metrics.items()
            },
            "aggregated_metrics": self.get_aggregated_metrics(time_window),
            "alerts": self.get_performance_alerts(),
            "custom_metrics": {}
        }
        
        # Export custom metrics
        custom_metrics = self.get_custom_metrics(time_window=time_window)
        for name, values in custom_metrics.items():
            export_data["custom_metrics"][name] = [v.to_dict() for v in values]
        
        # Export time series data if requested
        if time_window:
            export_data["time_series"] = {}
            for collector_type in self._time_series:
                export_data["time_series"][collector_type] = {}
                for metric_name in self._time_series[collector_type]:
                    data = self.get_time_series_data(collector_type, metric_name, time_window)
                    export_data["time_series"][collector_type][metric_name] = [
                        {"timestamp": ts.isoformat(), "value": val} for ts, val in data
                    ]
        
        return export_data
    
    def reset_metrics(self, collector_type: Optional[str] = None) -> None:
        """
        Reset metrics data.
        
        Args:
            collector_type: Optional collector type to reset, or None for all
        """
        if collector_type:
            if collector_type in self._metrics:
                del self._metrics[collector_type]
            if collector_type in self._time_series:
                del self._time_series[collector_type]
            logger.info(f"Reset metrics for {collector_type}")
        else:
            self._metrics.clear()
            self._time_series.clear()
            self._custom_metrics.clear()
            self._start_time = datetime.now()
            logger.info("Reset all metrics")
    
    def set_threshold(self, metric_name: str, value: float) -> None:
        """
        Set a performance threshold for alerting.
        
        Args:
            metric_name: Name of the metric threshold
            value: Threshold value
        """
        self.thresholds[metric_name] = value
        logger.info(f"Set threshold for {metric_name}: {value}")
    
    def get_health_score(self, collector_type: Optional[str] = None) -> float:
        """
        Calculate a health score based on various metrics.
        
        Args:
            collector_type: Optional collector type filter
            
        Returns:
            Health score between 0.0 and 100.0
        """
        if collector_type:
            if collector_type not in self._metrics:
                return 100.0  # No data means healthy
            metrics = [self._metrics[collector_type]]
        else:
            metrics = list(self._metrics.values())
        
        if not metrics:
            return 100.0
        
        total_score = 0.0
        for metric in metrics:
            # Success rate contributes 50% to health score
            success_score = metric.success_rate * 0.5
            
            # Execution time contributes 30% (inverse relationship)
            max_time = self.thresholds["max_execution_time"]
            time_score = max(0, (max_time - metric.average_execution_time) / max_time) * 30
            
            # Records per second contributes 20%
            min_rps = self.thresholds["min_records_per_second"]
            rps_score = min(20, (metric.records_per_second / min_rps) * 20)
            
            total_score += success_score + time_score + rps_score
        
        return total_score / len(metrics)