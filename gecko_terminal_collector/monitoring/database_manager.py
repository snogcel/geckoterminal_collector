"""
Database manager extension for monitoring data persistence.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from gecko_terminal_collector.database.models import (
    CollectionMetadata, ExecutionHistory, PerformanceMetrics, SystemAlerts
)
from gecko_terminal_collector.monitoring.execution_history import ExecutionRecord, ExecutionStatus
from gecko_terminal_collector.monitoring.collection_monitor import Alert, AlertLevel

logger = logging.getLogger(__name__)


class MonitoringDatabaseManager:
    """
    Database manager for monitoring data persistence.
    
    Handles storage and retrieval of execution history, performance metrics,
    and system alerts with efficient querying and data retention management.
    """
    
    def __init__(self, session_factory):
        """
        Initialize monitoring database manager.
        
        Args:
            session_factory: SQLAlchemy session factory
        """
        self.session_factory = session_factory
    
    def store_execution_record(self, record: ExecutionRecord) -> bool:
        """
        Store an execution record in the database.
        
        Args:
            record: ExecutionRecord to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self.session_factory() as session:
                # Check if record already exists
                existing = session.query(ExecutionHistory).filter_by(
                    execution_id=record.execution_id
                ).first()
                
                if existing:
                    # Update existing record
                    existing.end_time = record.end_time
                    existing.status = record.status.value
                    existing.records_collected = record.records_collected
                    existing.execution_time = record.duration_seconds
                    existing.error_message = "; ".join(record.errors) if record.errors else None
                    existing.warnings = json.dumps(record.warnings) if record.warnings else None
                    existing.execution_metadata = json.dumps(record.metadata) if record.metadata else None
                else:
                    # Create new record
                    db_record = ExecutionHistory(
                        collector_type=record.collector_type,
                        execution_id=record.execution_id,
                        start_time=record.start_time,
                        end_time=record.end_time,
                        status=record.status.value,
                        records_collected=record.records_collected,
                        execution_time=record.duration_seconds,
                        error_message="; ".join(record.errors) if record.errors else None,
                        warnings=json.dumps(record.warnings) if record.warnings else None,
                        execution_metadata=json.dumps(record.metadata) if record.metadata else None
                    )
                    session.add(db_record)
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing execution record {record.execution_id}: {e}")
            return False
    
    def get_execution_history(
        self,
        collector_type: Optional[str] = None,
        limit: Optional[int] = None,
        status_filter: Optional[ExecutionStatus] = None,
        time_window: Optional[timedelta] = None
    ) -> List[ExecutionRecord]:
        """
        Retrieve execution history from database.
        
        Args:
            collector_type: Filter by collector type
            limit: Maximum number of records to return
            status_filter: Filter by execution status
            time_window: Only include records within this time window
            
        Returns:
            List of ExecutionRecord objects
        """
        try:
            with self.session_factory() as session:
                query = session.query(ExecutionHistory)
                
                # Apply filters
                if collector_type:
                    query = query.filter(ExecutionHistory.collector_type == collector_type)
                
                if status_filter:
                    query = query.filter(ExecutionHistory.status == status_filter.value)
                
                if time_window:
                    cutoff_time = datetime.now() - time_window
                    query = query.filter(ExecutionHistory.start_time >= cutoff_time)
                
                # Order by start time (most recent first)
                query = query.order_by(desc(ExecutionHistory.start_time))
                
                # Apply limit
                if limit:
                    query = query.limit(limit)
                
                db_records = query.all()
                
                # Convert to ExecutionRecord objects
                records = []
                for db_record in db_records:
                    try:
                        warnings = json.loads(db_record.warnings) if db_record.warnings else []
                        metadata = json.loads(db_record.execution_metadata) if db_record.execution_metadata else {}
                        errors = [db_record.error_message] if db_record.error_message else []
                        
                        record = ExecutionRecord(
                            collector_type=db_record.collector_type,
                            execution_id=db_record.execution_id,
                            start_time=db_record.start_time,
                            end_time=db_record.end_time,
                            status=ExecutionStatus(db_record.status),
                            records_collected=db_record.records_collected,
                            errors=errors,
                            warnings=warnings,
                            metadata=metadata
                        )
                        records.append(record)
                    except Exception as e:
                        logger.warning(f"Error converting execution record {db_record.execution_id}: {e}")
                
                return records
                
        except Exception as e:
            logger.error(f"Error retrieving execution history: {e}")
            return []
    
    def store_performance_metric(
        self,
        collector_type: str,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Store a performance metric in the database.
        
        Args:
            collector_type: Type of collector
            metric_name: Name of the metric
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
            labels: Optional labels for the metric
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self.session_factory() as session:
                metric = PerformanceMetrics(
                    collector_type=collector_type,
                    metric_name=metric_name,
                    metric_value=value,
                    timestamp=timestamp or datetime.now(),
                    labels=json.dumps(labels) if labels else None
                )
                session.add(metric)
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing performance metric {metric_name}: {e}")
            return False
    
    def get_performance_metrics(
        self,
        collector_type: Optional[str] = None,
        metric_name: Optional[str] = None,
        time_window: Optional[timedelta] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve performance metrics from database.
        
        Args:
            collector_type: Filter by collector type
            metric_name: Filter by metric name
            time_window: Only include metrics within this time window
            limit: Maximum number of records to return
            
        Returns:
            List of metric dictionaries
        """
        try:
            with self.session_factory() as session:
                query = session.query(PerformanceMetrics)
                
                # Apply filters
                if collector_type:
                    query = query.filter(PerformanceMetrics.collector_type == collector_type)
                
                if metric_name:
                    query = query.filter(PerformanceMetrics.metric_name == metric_name)
                
                if time_window:
                    cutoff_time = datetime.now() - time_window
                    query = query.filter(PerformanceMetrics.timestamp >= cutoff_time)
                
                # Order by timestamp (most recent first)
                query = query.order_by(desc(PerformanceMetrics.timestamp))
                
                # Apply limit
                if limit:
                    query = query.limit(limit)
                
                db_metrics = query.all()
                
                # Convert to dictionaries
                metrics = []
                for db_metric in db_metrics:
                    try:
                        labels = json.loads(db_metric.labels) if db_metric.labels else {}
                        
                        metric = {
                            "collector_type": db_metric.collector_type,
                            "metric_name": db_metric.metric_name,
                            "value": float(db_metric.metric_value),
                            "timestamp": db_metric.timestamp,
                            "labels": labels
                        }
                        metrics.append(metric)
                    except Exception as e:
                        logger.warning(f"Error converting performance metric {db_metric.id}: {e}")
                
                return metrics
                
        except Exception as e:
            logger.error(f"Error retrieving performance metrics: {e}")
            return []
    
    def store_alert(self, alert: Alert) -> bool:
        """
        Store an alert in the database.
        
        Args:
            alert: Alert to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self.session_factory() as session:
                # Check if alert already exists
                existing = session.query(SystemAlerts).filter_by(
                    alert_id=alert.id
                ).first()
                
                if existing:
                    # Update existing alert
                    existing.acknowledged = alert.acknowledged
                    existing.resolved = alert.resolved
                    existing.alert_metadata = json.dumps(alert.metadata) if alert.metadata else None
                else:
                    # Create new alert
                    db_alert = SystemAlerts(
                        alert_id=alert.id,
                        level=alert.level.value,
                        collector_type=alert.collector_type,
                        message=alert.message,
                        timestamp=alert.timestamp,
                        acknowledged=alert.acknowledged,
                        resolved=alert.resolved,
                        alert_metadata=json.dumps(alert.metadata) if alert.metadata else None
                    )
                    session.add(db_alert)
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing alert {alert.id}: {e}")
            return False
    
    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        collector_type: Optional[str] = None,
        unresolved_only: bool = True,
        limit: Optional[int] = None
    ) -> List[Alert]:
        """
        Retrieve alerts from database.
        
        Args:
            level: Filter by alert level
            collector_type: Filter by collector type
            unresolved_only: Only return unresolved alerts
            limit: Maximum number of alerts to return
            
        Returns:
            List of Alert objects
        """
        try:
            with self.session_factory() as session:
                query = session.query(SystemAlerts)
                
                # Apply filters
                if level:
                    query = query.filter(SystemAlerts.level == level.value)
                
                if collector_type:
                    query = query.filter(SystemAlerts.collector_type == collector_type)
                
                if unresolved_only:
                    query = query.filter(SystemAlerts.resolved == False)
                
                # Order by timestamp (most recent first)
                query = query.order_by(desc(SystemAlerts.timestamp))
                
                # Apply limit
                if limit:
                    query = query.limit(limit)
                
                db_alerts = query.all()
                
                # Convert to Alert objects
                alerts = []
                for db_alert in db_alerts:
                    try:
                        metadata = json.loads(db_alert.alert_metadata) if db_alert.alert_metadata else {}
                        
                        alert = Alert(
                            id=db_alert.alert_id,
                            level=AlertLevel(db_alert.level),
                            collector_type=db_alert.collector_type,
                            message=db_alert.message,
                            timestamp=db_alert.timestamp,
                            metadata=metadata,
                            acknowledged=db_alert.acknowledged,
                            resolved=db_alert.resolved
                        )
                        alerts.append(alert)
                    except Exception as e:
                        logger.warning(f"Error converting alert {db_alert.alert_id}: {e}")
                
                return alerts
                
        except Exception as e:
            logger.error(f"Error retrieving alerts: {e}")
            return []
    
    def update_collection_metadata(
        self,
        collector_type: str,
        execution_time: float,
        records_collected: int,
        success: bool,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update collection metadata for a collector.
        
        Args:
            collector_type: Type of collector
            execution_time: Execution time in seconds
            records_collected: Number of records collected
            success: Whether the execution was successful
            error_message: Optional error message
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self.session_factory() as session:
                # Get or create metadata record
                metadata = session.query(CollectionMetadata).filter_by(
                    collector_type=collector_type
                ).first()
                
                if not metadata:
                    metadata = CollectionMetadata(collector_type=collector_type)
                    session.add(metadata)
                
                # Update metadata
                metadata.last_run = datetime.now()
                metadata.run_count = (metadata.run_count or 0) + 1
                metadata.total_execution_time = (metadata.total_execution_time or 0) + execution_time
                metadata.total_records_collected = (metadata.total_records_collected or 0) + records_collected
                
                if success:
                    metadata.last_success = datetime.now()
                    metadata.last_error = None
                else:
                    metadata.error_count = (metadata.error_count or 0) + 1
                    metadata.last_error = error_message
                
                # Calculate derived metrics
                if metadata.run_count > 0:
                    metadata.average_execution_time = metadata.total_execution_time / metadata.run_count
                    success_count = metadata.run_count - (metadata.error_count or 0)
                    metadata.success_rate = (success_count / metadata.run_count) * 100
                
                # Calculate health score (simplified)
                if metadata.success_rate >= 95:
                    metadata.health_score = 100.0
                elif metadata.success_rate >= 80:
                    metadata.health_score = 80.0
                elif metadata.success_rate >= 60:
                    metadata.health_score = 60.0
                else:
                    metadata.health_score = 40.0
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error updating collection metadata for {collector_type}: {e}")
            return False
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """
        Clean up old monitoring data.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Dictionary with counts of removed records
        """
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        removed_counts = {}
        
        try:
            with self.session_factory() as session:
                # Clean up execution history
                execution_count = session.query(ExecutionHistory).filter(
                    ExecutionHistory.start_time < cutoff_time
                ).count()
                
                session.query(ExecutionHistory).filter(
                    ExecutionHistory.start_time < cutoff_time
                ).delete()
                
                removed_counts["execution_history"] = execution_count
                
                # Clean up performance metrics
                metrics_count = session.query(PerformanceMetrics).filter(
                    PerformanceMetrics.timestamp < cutoff_time
                ).count()
                
                session.query(PerformanceMetrics).filter(
                    PerformanceMetrics.timestamp < cutoff_time
                ).delete()
                
                removed_counts["performance_metrics"] = metrics_count
                
                # Clean up resolved alerts
                alerts_count = session.query(SystemAlerts).filter(
                    and_(
                        SystemAlerts.timestamp < cutoff_time,
                        SystemAlerts.resolved == True
                    )
                ).count()
                
                session.query(SystemAlerts).filter(
                    and_(
                        SystemAlerts.timestamp < cutoff_time,
                        SystemAlerts.resolved == True
                    )
                ).delete()
                
                removed_counts["system_alerts"] = alerts_count
                
                session.commit()
                
                total_removed = sum(removed_counts.values())
                if total_removed > 0:
                    logger.info(f"Cleaned up {total_removed} old monitoring records")
                
        except Exception as e:
            logger.error(f"Error cleaning up old monitoring data: {e}")
        
        return removed_counts