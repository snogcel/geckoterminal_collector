#!/usr/bin/env python3
"""
Demonstration of the collection monitoring and coordination system.

This example shows how to use the monitoring components to track
collection execution, performance metrics, and system health.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gecko_terminal_collector.monitoring.execution_history import ExecutionHistoryTracker
from gecko_terminal_collector.monitoring.performance_metrics import MetricsCollector
from gecko_terminal_collector.monitoring.collection_monitor import CollectionMonitor, AlertLevel
from gecko_terminal_collector.models.core import CollectionResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def alert_handler(alert):
    """Example alert handler function."""
    print(f"\n🚨 ALERT: {alert.level.value.upper()}")
    print(f"   Collector: {alert.collector_type}")
    print(f"   Message: {alert.message}")
    print(f"   Time: {alert.timestamp}")
    print(f"   Metadata: {alert.metadata}")
    print()


async def simulate_collection_execution(
    collector_type: str,
    execution_time: float,
    records_collected: int,
    success: bool,
    errors: list = None
) -> CollectionResult:
    """Simulate a collection execution."""
    await asyncio.sleep(execution_time)
    
    return CollectionResult(
        success=success,
        records_collected=records_collected,
        errors=errors or [],
        collection_time=datetime.now(),
        collector_type=collector_type
    )


async def main():
    """Main demonstration function."""
    print("🔍 Collection Monitoring and Coordination Demo")
    print("=" * 50)
    
    # Initialize monitoring components
    execution_history = ExecutionHistoryTracker()
    metrics_collector = MetricsCollector()
    collection_monitor = CollectionMonitor(execution_history, metrics_collector)
    
    # Add alert handler
    collection_monitor.add_alert_handler(alert_handler)
    
    # Configure monitoring thresholds for demo
    collection_monitor.health_config["max_consecutive_failures"] = 2
    collection_monitor.health_config["min_success_rate_24h"] = 80.0
    
    metrics_collector.set_threshold("max_execution_time", 5.0)
    metrics_collector.set_threshold("min_success_rate", 85.0)
    
    print("\n📊 Simulating collection executions...")
    
    # Simulate successful executions for "pool_collector"
    for i in range(5):
        execution_id = f"pool_collector_exec_{i}"
        
        # Start execution tracking
        record = execution_history.start_execution(
            collector_type="pool_collector",
            execution_id=execution_id,
            metadata={"batch": i + 1}
        )
        
        # Simulate execution
        result = await simulate_collection_execution(
            collector_type="pool_collector",
            execution_time=2.0 + (i * 0.5),  # Gradually slower
            records_collected=50 + (i * 10),
            success=True
        )
        
        # Complete execution tracking
        execution_history.complete_execution(execution_id, result)
        
        # Record metrics
        execution_time = record.duration_seconds or 2.0 + (i * 0.5)
        metrics_collector.record_execution(
            collector_type="pool_collector",
            execution_time=execution_time,
            records_collected=result.records_collected,
            success=result.success
        )
        
        # Update monitoring
        collection_monitor.update_from_execution(
            collector_type="pool_collector",
            result=result,
            execution_time=execution_time
        )
        
        print(f"   ✅ pool_collector execution {i+1}: {result.records_collected} records in {execution_time:.1f}s")
    
    # Simulate mixed results for "trade_collector"
    for i in range(4):
        execution_id = f"trade_collector_exec_{i}"
        
        record = execution_history.start_execution(
            collector_type="trade_collector",
            execution_id=execution_id
        )
        
        # Make some executions fail
        success = i < 2  # First 2 succeed, last 2 fail
        
        result = await simulate_collection_execution(
            collector_type="trade_collector",
            execution_time=3.0,
            records_collected=25 if success else 0,
            success=success,
            errors=[] if success else [f"API error in execution {i+1}"]
        )
        
        execution_history.complete_execution(execution_id, result)
        
        execution_time = record.duration_seconds or 3.0
        metrics_collector.record_execution(
            collector_type="trade_collector",
            execution_time=execution_time,
            records_collected=result.records_collected,
            success=result.success
        )
        
        collection_monitor.update_from_execution(
            collector_type="trade_collector",
            result=result,
            execution_time=execution_time
        )
        
        status = "✅" if success else "❌"
        print(f"   {status} trade_collector execution {i+1}: {'Success' if success else 'Failed'}")
    
    # Simulate slow executions for "ohlcv_collector"
    for i in range(3):
        execution_id = f"ohlcv_collector_exec_{i}"
        
        record = execution_history.start_execution(
            collector_type="ohlcv_collector",
            execution_id=execution_id
        )
        
        # Make executions progressively slower
        execution_time = 6.0 + (i * 2.0)  # 6s, 8s, 10s
        
        result = await simulate_collection_execution(
            collector_type="ohlcv_collector",
            execution_time=execution_time,
            records_collected=100,
            success=True
        )
        
        execution_history.complete_execution(execution_id, result)
        
        metrics_collector.record_execution(
            collector_type="ohlcv_collector",
            execution_time=execution_time,
            records_collected=result.records_collected,
            success=result.success
        )
        
        collection_monitor.update_from_execution(
            collector_type="ohlcv_collector",
            result=result,
            execution_time=execution_time
        )
        
        print(f"   🐌 ohlcv_collector execution {i+1}: {result.records_collected} records in {execution_time:.1f}s")
    
    print("\n📈 Performance Metrics Summary:")
    print("-" * 30)
    
    # Display performance metrics
    all_metrics = metrics_collector.get_metrics()
    for collector_type, metrics in all_metrics.items():
        print(f"\n{collector_type}:")
        print(f"  Executions: {metrics.execution_count}")
        print(f"  Success Rate: {metrics.success_rate:.1f}%")
        print(f"  Avg Execution Time: {metrics.average_execution_time:.2f}s")
        print(f"  Total Records: {metrics.total_records_collected}")
        print(f"  Records/Second: {metrics.records_per_second:.2f}")
    
    # Display aggregated metrics
    aggregated = metrics_collector.get_aggregated_metrics()
    print(f"\nSystem Overview:")
    print(f"  Total Collectors: {aggregated['total_collectors']}")
    print(f"  Total Executions: {aggregated['total_executions']}")
    print(f"  Overall Success Rate: {aggregated['overall_success_rate']:.1f}%")
    print(f"  Total Records: {aggregated['total_records_collected']}")
    
    print("\n🏥 Health Status:")
    print("-" * 20)
    
    # Display health status
    health_summary = collection_monitor.get_system_health_summary()
    print(f"Overall Status: {health_summary['overall_status'].upper()}")
    print(f"Healthy Collectors: {health_summary['healthy_collectors']}")
    print(f"Warning Collectors: {health_summary['warning_collectors']}")
    print(f"Critical Collectors: {health_summary['critical_collectors']}")
    print(f"Average Health Score: {health_summary['average_health_score']:.1f}")
    
    # Display individual collector health
    collector_health = collection_monitor.get_collector_health()
    for collector_type, health in collector_health.items():
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🚨",
            "unknown": "❓"
        }
        emoji = status_emoji.get(health.status.value, "❓")
        
        print(f"\n{emoji} {collector_type}:")
        print(f"  Status: {health.status.value}")
        print(f"  Success Rate (24h): {health.success_rate_24h:.1f}%")
        print(f"  Consecutive Failures: {health.consecutive_failures}")
        print(f"  Health Score: {health.health_score:.1f}")
        if health.issues:
            print(f"  Issues: {', '.join(health.issues)}")
    
    print("\n🚨 Active Alerts:")
    print("-" * 15)
    
    # Display alerts
    alerts = collection_monitor.get_alerts()
    if alerts:
        for alert in alerts:
            level_emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨"
            }
            emoji = level_emoji.get(alert.level.value, "❓")
            
            print(f"{emoji} {alert.level.value.upper()}: {alert.collector_type}")
            print(f"   {alert.message}")
            print(f"   Time: {alert.timestamp.strftime('%H:%M:%S')}")
    else:
        print("No active alerts")
    
    print("\n📊 Performance Alerts:")
    print("-" * 20)
    
    # Display performance alerts
    perf_alerts = metrics_collector.get_performance_alerts()
    if perf_alerts:
        for alert in perf_alerts:
            severity_emoji = {
                "warning": "⚠️",
                "error": "❌",
                "critical": "🚨"
            }
            emoji = severity_emoji.get(alert["severity"], "❓")
            
            print(f"{emoji} {alert['collector_type']}: {alert['message']}")
    else:
        print("No performance alerts")
    
    print("\n📋 Execution History Sample:")
    print("-" * 30)
    
    # Display recent execution history
    recent_history = execution_history.get_execution_history(limit=5)
    for record in recent_history:
        status_emoji = {
            "success": "✅",
            "failure": "❌",
            "partial": "⚠️",
            "cancelled": "🚫"
        }
        emoji = status_emoji.get(record.status.value, "❓")
        
        duration = f"{record.duration_seconds:.2f}s" if record.duration_seconds else "unknown"
        print(f"{emoji} {record.collector_type}: {record.records_collected} records in {duration}")
    
    print("\n📈 Execution Statistics:")
    print("-" * 25)
    
    # Display execution statistics
    for collector_type in ["pool_collector", "trade_collector", "ohlcv_collector"]:
        stats = execution_history.get_execution_statistics(collector_type)
        print(f"\n{collector_type}:")
        print(f"  Total Executions: {stats['total_executions']}")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
        print(f"  Average Duration: {stats['average_duration']:.2f}s")
        print(f"  Total Records: {stats['total_records_collected']}")
    
    print("\n🎯 Custom Metrics Example:")
    print("-" * 25)
    
    # Record some custom metrics
    metrics_collector.record_custom_metric("api_calls_per_minute", 45.5, {"endpoint": "/pools"})
    metrics_collector.record_custom_metric("api_calls_per_minute", 52.3, {"endpoint": "/trades"})
    metrics_collector.record_custom_metric("memory_usage_mb", 128.7)
    
    custom_metrics = metrics_collector.get_custom_metrics()
    for metric_name, values in custom_metrics.items():
        print(f"\n{metric_name}:")
        for value in values[-3:]:  # Show last 3 values
            labels_str = f" ({value.labels})" if value.labels else ""
            print(f"  {value.value}{labels_str} at {value.timestamp.strftime('%H:%M:%S')}")
    
    print("\n✨ Monitoring Demo Complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())