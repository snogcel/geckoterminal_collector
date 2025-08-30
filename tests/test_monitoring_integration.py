"""
Tests for monitoring integration with collection system.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from gecko_terminal_collector.monitoring.execution_history import (
    ExecutionHistoryTracker, ExecutionRecord, ExecutionStatus
)
from gecko_terminal_collector.monitoring.performance_metrics import (
    MetricsCollector, PerformanceMetrics
)
from gecko_terminal_collector.monitoring.collection_monitor import (
    CollectionMonitor, CollectionStatus, AlertLevel, Alert
)
from gecko_terminal_collector.models.core import CollectionResult


class TestExecutionHistoryTracker:
    """Test cases for ExecutionHistoryTracker."""
    
    def test_start_execution(self):
        """Test starting execution tracking."""
        tracker = ExecutionHistoryTracker()
        
        record = tracker.start_execution(
            collector_type="test_collector",
            execution_id="test_exec_1",
            metadata={"test": "data"}
        )
        
        assert record.collector_type == "test_collector"
        assert record.execution_id == "test_exec_1"
        assert record.metadata == {"test": "data"}
        assert record.end_time is None
        assert record.status == ExecutionStatus.SUCCESS
        
        # Check active executions
        active = tracker.get_active_executions()
        assert len(active) == 1
        assert active[0].execution_id == "test_exec_1"
    
    def test_complete_execution_success(self):
        """Test completing successful execution."""
        tracker = ExecutionHistoryTracker()
        
        # Start execution
        tracker.start_execution("test_collector", "test_exec_1")
        
        # Create successful result
        result = CollectionResult(
            success=True,
            records_collected=100,
            errors=[],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        
        # Complete execution
        record = tracker.complete_execution("test_exec_1", result, warnings=["test warning"])
        
        assert record is not None
        assert record.status == ExecutionStatus.PARTIAL  # Has warnings
        assert record.records_collected == 100
        assert record.warnings == ["test warning"]
        assert record.end_time is not None
        
        # Check no longer active
        active = tracker.get_active_executions()
        assert len(active) == 0
        
        # Check in history
        history = tracker.get_execution_history()
        assert len(history) == 1
        assert history[0].execution_id == "test_exec_1"
    
    def test_complete_execution_failure(self):
        """Test completing failed execution."""
        tracker = ExecutionHistoryTracker()
        
        # Start execution
        tracker.start_execution("test_collector", "test_exec_1")
        
        # Create failed result
        result = CollectionResult(
            success=False,
            records_collected=0,
            errors=["Test error"],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        
        # Complete execution
        record = tracker.complete_execution("test_exec_1", result)
        
        assert record is not None
        assert record.status == ExecutionStatus.FAILURE
        assert record.records_collected == 0
        assert record.errors == ["Test error"]
    
    def test_cancel_execution(self):
        """Test cancelling execution."""
        tracker = ExecutionHistoryTracker()
        
        # Start execution
        tracker.start_execution("test_collector", "test_exec_1")
        
        # Cancel execution
        record = tracker.cancel_execution("test_exec_1", "Test cancellation")
        
        assert record is not None
        assert record.status == ExecutionStatus.CANCELLED
        assert "Test cancellation" in record.errors
        assert record.end_time is not None
    
    def test_get_execution_statistics(self):
        """Test getting execution statistics."""
        tracker = ExecutionHistoryTracker()
        
        # Add some execution records
        for i in range(5):
            tracker.start_execution("test_collector", f"exec_{i}")
            
            success = i < 4  # 4 successful, 1 failed
            result = CollectionResult(
                success=success,
                records_collected=10 if success else 0,
                errors=[] if success else ["Error"],
                collection_time=datetime.now(),
                collector_type="test_collector"
            )
            
            tracker.complete_execution(f"exec_{i}", result)
        
        stats = tracker.get_execution_statistics("test_collector")
        
        assert stats["total_executions"] == 5
        assert stats["successful_executions"] == 4
        assert stats["failed_executions"] == 1
        assert stats["success_rate"] == 80.0
        assert stats["total_records_collected"] == 40
    
    def test_cleanup_old_records(self):
        """Test cleaning up old execution records."""
        tracker = ExecutionHistoryTracker(max_records_per_collector=3)
        
        # Add more records than the limit
        for i in range(5):
            tracker.start_execution("test_collector", f"exec_{i}")
            result = CollectionResult(
                success=True,
                records_collected=10,
                errors=[],
                collection_time=datetime.now(),
                collector_type="test_collector"
            )
            tracker.complete_execution(f"exec_{i}", result)
        
        # Check that only max records are kept
        history = tracker.get_execution_history("test_collector")
        assert len(history) == 3
        
        # Should keep the most recent ones
        execution_ids = [r.execution_id for r in history]
        assert "exec_4" in execution_ids
        assert "exec_3" in execution_ids
        assert "exec_2" in execution_ids


class TestMetricsCollector:
    """Test cases for MetricsCollector."""
    
    def test_record_execution(self):
        """Test recording execution metrics."""
        collector = MetricsCollector()
        
        collector.record_execution(
            collector_type="test_collector",
            execution_time=5.0,
            records_collected=100,
            success=True
        )
        
        metrics = collector.get_metrics("test_collector")
        assert "test_collector" in metrics
        
        metric = metrics["test_collector"]
        assert metric.execution_count == 1
        assert metric.total_execution_time == 5.0
        assert metric.total_records_collected == 100
        assert metric.error_count == 0
        assert metric.success_rate == 100.0
        assert metric.average_execution_time == 5.0
    
    def test_record_multiple_executions(self):
        """Test recording multiple executions."""
        collector = MetricsCollector()
        
        # Record successful execution
        collector.record_execution("test_collector", 3.0, 50, True)
        
        # Record failed execution
        collector.record_execution("test_collector", 7.0, 0, False)
        
        # Record another successful execution
        collector.record_execution("test_collector", 5.0, 75, True)
        
        metrics = collector.get_metrics("test_collector")["test_collector"]
        
        assert metrics.execution_count == 3
        assert metrics.total_execution_time == 15.0
        assert metrics.total_records_collected == 125
        assert metrics.error_count == 1
        assert abs(metrics.success_rate - 66.67) < 0.01  # 2/3 * 100
        assert metrics.average_execution_time == 5.0
    
    def test_get_aggregated_metrics(self):
        """Test getting aggregated metrics across collectors."""
        collector = MetricsCollector()
        
        # Record metrics for multiple collectors
        collector.record_execution("collector_1", 2.0, 30, True)
        collector.record_execution("collector_1", 3.0, 40, True)
        collector.record_execution("collector_2", 4.0, 50, True)
        collector.record_execution("collector_2", 6.0, 0, False)
        
        aggregated = collector.get_aggregated_metrics()
        
        assert aggregated["total_collectors"] == 2
        assert aggregated["total_executions"] == 4
        assert aggregated["total_records_collected"] == 120
        assert aggregated["total_errors"] == 1
        assert aggregated["overall_success_rate"] == 75.0
    
    def test_performance_alerts(self):
        """Test performance alert generation."""
        collector = MetricsCollector()
        
        # Set low threshold for testing
        collector.set_threshold("max_execution_time", 2.0)
        collector.set_threshold("min_success_rate", 90.0)
        
        # Record slow execution
        collector.record_execution("slow_collector", 5.0, 10, True)
        
        # Record failed executions to trigger success rate alert
        for i in range(3):
            collector.record_execution("failing_collector", 1.0, 0, False)
        
        alerts = collector.get_performance_alerts()
        
        # Should have alerts for both collectors
        alert_types = [alert["collector_type"] for alert in alerts]
        assert "slow_collector" in alert_types
        assert "failing_collector" in alert_types
        
        # Check alert details
        slow_alert = next(a for a in alerts if a["collector_type"] == "slow_collector")
        assert slow_alert["metric"] == "execution_time"
        assert slow_alert["severity"] == "warning"
        
        failing_alert = next(a for a in alerts if a["collector_type"] == "failing_collector")
        assert failing_alert["metric"] == "success_rate"
        assert failing_alert["severity"] == "error"
    
    def test_custom_metrics(self):
        """Test custom metric recording."""
        collector = MetricsCollector()
        
        collector.record_custom_metric(
            "api_calls_per_minute",
            120.5,
            labels={"endpoint": "/pools", "method": "GET"}
        )
        
        custom_metrics = collector.get_custom_metrics("api_calls_per_minute")
        assert "api_calls_per_minute" in custom_metrics
        
        metrics = custom_metrics["api_calls_per_minute"]
        assert len(metrics) == 1
        assert metrics[0].value == 120.5
        assert metrics[0].labels == {"endpoint": "/pools", "method": "GET"}
    
    def test_health_score_calculation(self):
        """Test health score calculation."""
        collector = MetricsCollector()
        
        # Record perfect performance
        collector.record_execution("perfect_collector", 1.0, 100, True)
        collector.record_execution("perfect_collector", 1.5, 150, True)
        
        health_score = collector.get_health_score("perfect_collector")
        assert health_score > 90.0  # Should be high for good performance
        
        # Record poor performance
        collector.record_execution("poor_collector", 400.0, 1, False)  # Slow and failed
        
        poor_health_score = collector.get_health_score("poor_collector")
        assert poor_health_score < 50.0  # Should be low for poor performance


class TestCollectionMonitor:
    """Test cases for CollectionMonitor."""
    
    @pytest.fixture
    def monitor_components(self):
        """Create monitor components for testing."""
        execution_history = ExecutionHistoryTracker()
        metrics_collector = MetricsCollector()
        monitor = CollectionMonitor(execution_history, metrics_collector)
        return execution_history, metrics_collector, monitor
    
    def test_update_from_execution_success(self, monitor_components):
        """Test updating monitor from successful execution."""
        execution_history, metrics_collector, monitor = monitor_components
        
        # First add execution to history so success rate calculation works
        execution_history.start_execution("test_collector", "test_exec_1")
        
        result = CollectionResult(
            success=True,
            records_collected=100,
            errors=[],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        
        execution_history.complete_execution("test_exec_1", result)
        monitor.update_from_execution("test_collector", result, 5.0)
        
        # Check health status
        health = monitor.get_collector_health("test_collector")
        assert "test_collector" in health
        
        collector_health = health["test_collector"]
        assert collector_health.status == CollectionStatus.HEALTHY
        assert collector_health.consecutive_failures == 0
        assert collector_health.last_success is not None
    
    def test_update_from_execution_failure(self, monitor_components):
        """Test updating monitor from failed execution."""
        execution_history, metrics_collector, monitor = monitor_components
        
        result = CollectionResult(
            success=False,
            records_collected=0,
            errors=["Test error"],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        
        monitor.update_from_execution("test_collector", result, 5.0)
        
        # Check health status
        health = monitor.get_collector_health("test_collector")
        collector_health = health["test_collector"]
        
        assert collector_health.consecutive_failures == 1
        assert collector_health.last_failure is not None
    
    def test_alert_generation_critical(self, monitor_components):
        """Test critical alert generation."""
        execution_history, metrics_collector, monitor = monitor_components
        
        # Configure for quick alert generation
        monitor.health_config["max_consecutive_failures"] = 2
        
        # Record multiple failures
        for i in range(3):
            result = CollectionResult(
                success=False,
                records_collected=0,
                errors=[f"Error {i}"],
                collection_time=datetime.now(),
                collector_type="test_collector"
            )
            monitor.update_from_execution("test_collector", result, 5.0)
        
        # Check for critical alerts
        alerts = monitor.get_alerts(level=AlertLevel.CRITICAL)
        assert len(alerts) > 0
        
        critical_alert = alerts[0]
        assert critical_alert.level == AlertLevel.CRITICAL
        assert critical_alert.collector_type == "test_collector"
        assert "critical state" in critical_alert.message.lower()
    
    def test_alert_acknowledgment(self, monitor_components):
        """Test alert acknowledgment."""
        execution_history, metrics_collector, monitor = monitor_components
        
        # Create an alert by triggering failures
        monitor.health_config["max_consecutive_failures"] = 1
        
        result = CollectionResult(
            success=False,
            records_collected=0,
            errors=["Test error"],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        monitor.update_from_execution("test_collector", result, 5.0)
        
        # Get the alert
        alerts = monitor.get_alerts()
        assert len(alerts) > 0
        
        alert_id = alerts[0].id
        
        # Acknowledge the alert
        success = monitor.acknowledge_alert(alert_id)
        assert success
        
        # Check that alert is acknowledged
        acknowledged_alerts = monitor.get_alerts(unresolved_only=False)
        acknowledged_alert = next(a for a in acknowledged_alerts if a.id == alert_id)
        assert acknowledged_alert.acknowledged
    
    def test_system_health_summary(self, monitor_components):
        """Test system health summary."""
        execution_history, metrics_collector, monitor = monitor_components
        
        # Add healthy collector with execution history
        execution_history.start_execution("healthy_collector", "healthy_exec_1")
        healthy_result = CollectionResult(
            success=True,
            records_collected=100,
            errors=[],
            collection_time=datetime.now(),
            collector_type="healthy_collector"
        )
        execution_history.complete_execution("healthy_exec_1", healthy_result)
        monitor.update_from_execution("healthy_collector", healthy_result, 2.0)
        
        # Add unhealthy collector with execution history
        monitor.health_config["max_consecutive_failures"] = 1
        execution_history.start_execution("unhealthy_collector", "unhealthy_exec_1")
        unhealthy_result = CollectionResult(
            success=False,
            records_collected=0,
            errors=["Error"],
            collection_time=datetime.now(),
            collector_type="unhealthy_collector"
        )
        execution_history.complete_execution("unhealthy_exec_1", unhealthy_result)
        monitor.update_from_execution("unhealthy_collector", unhealthy_result, 10.0)
        
        summary = monitor.get_system_health_summary()
        
        assert summary["total_collectors"] == 2
        assert summary["healthy_collectors"] >= 1
        assert summary["critical_collectors"] >= 1
        assert "overall_status" in summary
    
    def test_alert_suppression(self, monitor_components):
        """Test alert suppression functionality."""
        execution_history, metrics_collector, monitor = monitor_components
        
        # Suppress alerts for test collector (will warn about no event loop)
        monitor.suppress_alerts("test_collector", duration_minutes=1)
        
        # Try to trigger an alert
        monitor.health_config["max_consecutive_failures"] = 1
        execution_history.start_execution("test_collector", "test_exec_1")
        result = CollectionResult(
            success=False,
            records_collected=0,
            errors=["Test error"],
            collection_time=datetime.now(),
            collector_type="test_collector"
        )
        execution_history.complete_execution("test_exec_1", result)
        monitor.update_from_execution("test_collector", result, 5.0)
        
        # Should have no alerts due to suppression
        alerts = monitor.get_alerts()
        test_alerts = [a for a in alerts if a.collector_type == "test_collector"]
        assert len(test_alerts) == 0


@pytest.mark.asyncio
class TestMonitoringIntegration:
    """Integration tests for monitoring components."""
    
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        # Create monitoring components
        execution_history = ExecutionHistoryTracker()
        metrics_collector = MetricsCollector()
        monitor = CollectionMonitor(execution_history, metrics_collector)
        
        collector_type = "integration_test_collector"
        
        # Simulate a collection execution
        execution_id = f"{collector_type}_test_1"
        
        # Start execution tracking
        record = execution_history.start_execution(
            collector_type=collector_type,
            execution_id=execution_id
        )
        
        # Simulate execution time
        await asyncio.sleep(0.1)
        
        # Create successful result
        result = CollectionResult(
            success=True,
            records_collected=150,
            errors=[],
            collection_time=datetime.now(),
            collector_type=collector_type
        )
        
        # Complete execution tracking
        completed_record = execution_history.complete_execution(execution_id, result)
        
        # Record metrics
        execution_time = completed_record.duration_seconds
        metrics_collector.record_execution(
            collector_type=collector_type,
            execution_time=execution_time,
            records_collected=150,
            success=True
        )
        
        # Update monitoring
        monitor.update_from_execution(collector_type, result, execution_time)
        
        # Verify all components have data
        assert len(execution_history.get_execution_history()) == 1
        assert collector_type in metrics_collector.get_metrics()
        assert collector_type in monitor.get_collector_health()
        
        # Check health status
        health = monitor.get_collector_health(collector_type)[collector_type]
        assert health.status == CollectionStatus.HEALTHY
        assert health.total_executions == 1
        assert health.consecutive_failures == 0
        
        # Check metrics
        perf_metrics = metrics_collector.get_metrics(collector_type)[collector_type]
        assert perf_metrics.execution_count == 1
        assert perf_metrics.total_records_collected == 150
        assert perf_metrics.success_rate == 100.0
        
        # Check execution history
        history = execution_history.get_execution_history(collector_type)
        assert len(history) == 1
        assert history[0].status == ExecutionStatus.SUCCESS
        assert history[0].records_collected == 150
    
    async def test_monitoring_with_failures(self):
        """Test monitoring behavior with failures."""
        execution_history = ExecutionHistoryTracker()
        metrics_collector = MetricsCollector()
        monitor = CollectionMonitor(execution_history, metrics_collector)
        
        collector_type = "failing_collector"
        
        # Configure for quick alert generation
        monitor.health_config["max_consecutive_failures"] = 2
        
        # Simulate multiple failed executions
        for i in range(3):
            execution_id = f"{collector_type}_fail_{i}"
            
            # Start and complete failed execution
            execution_history.start_execution(collector_type, execution_id)
            
            result = CollectionResult(
                success=False,
                records_collected=0,
                errors=[f"Failure {i}"],
                collection_time=datetime.now(),
                collector_type=collector_type
            )
            
            execution_history.complete_execution(execution_id, result)
            
            # Record metrics and update monitoring
            metrics_collector.record_execution(collector_type, 5.0, 0, False)
            monitor.update_from_execution(collector_type, result, 5.0)
        
        # Check that collector is marked as critical
        health = monitor.get_collector_health(collector_type)[collector_type]
        assert health.status == CollectionStatus.CRITICAL
        assert health.consecutive_failures == 3
        
        # Check that alerts were generated
        alerts = monitor.get_alerts()
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical_alerts) > 0
        
        # Check metrics show poor performance
        perf_metrics = metrics_collector.get_metrics(collector_type)[collector_type]
        assert perf_metrics.success_rate == 0.0
        assert perf_metrics.error_count == 3
        
        # Check execution history shows all failures
        history = execution_history.get_execution_history(collector_type)
        assert len(history) == 3
        assert all(r.status == ExecutionStatus.FAILURE for r in history)