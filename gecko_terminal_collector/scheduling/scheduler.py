"""
Collection scheduler for orchestrating data collection tasks.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.job import Job

from gecko_terminal_collector.collectors.base import BaseDataCollector, CollectorRegistry
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.monitoring.collection_monitor import CollectionMonitor
from gecko_terminal_collector.monitoring.execution_history import ExecutionHistoryTracker
from gecko_terminal_collector.monitoring.performance_metrics import MetricsCollector
from gecko_terminal_collector.monitoring.database_manager import MonitoringDatabaseManager

logger = logging.getLogger(__name__)


class SchedulerState(Enum):
    """Scheduler state enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ScheduledCollector:
    """Configuration for a scheduled collector."""
    collector: BaseDataCollector
    interval: str
    enabled: bool = True
    max_instances: int = 1
    coalesce: bool = True
    misfire_grace_time: int = 300  # seconds
    job_id: Optional[str] = None
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    error_count: int = 0
    consecutive_errors: int = 0


@dataclass
class SchedulerConfig:
    """Configuration for the collection scheduler."""
    timezone: str = "UTC"
    max_workers: int = 10
    job_defaults: Dict[str, Any] = field(default_factory=lambda: {
        'coalesce': True,
        'max_instances': 1,
        'misfire_grace_time': 300
    })
    shutdown_timeout: int = 30  # seconds
    error_recovery_delay: int = 60  # seconds
    max_consecutive_errors: int = 5
    health_check_interval: int = 300  # seconds


class CollectionScheduler:
    """
    Scheduler for orchestrating data collection tasks with configurable intervals.
    
    Provides async coordination, error recovery, and comprehensive monitoring
    of collection operations using APScheduler as the underlying scheduler.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        scheduler_config: Optional[SchedulerConfig] = None,
        metadata_tracker: Optional[MetadataTracker] = None,
        monitoring_db_manager: Optional[MonitoringDatabaseManager] = None
    ):
        """
        Initialize the collection scheduler.
        
        Args:
            config: Collection configuration
            scheduler_config: Scheduler-specific configuration
            metadata_tracker: Optional metadata tracker for statistics
            monitoring_db_manager: Optional monitoring database manager
        """
        self.config = config
        self.scheduler_config = scheduler_config or SchedulerConfig()
        self.metadata_tracker = metadata_tracker or MetadataTracker()
        
        # Initialize monitoring components
        self.execution_history = ExecutionHistoryTracker()
        self.metrics_collector = MetricsCollector()
        self.collection_monitor = CollectionMonitor(
            self.execution_history,
            self.metrics_collector
        )
        self.monitoring_db_manager = monitoring_db_manager
        
        # Initialize APScheduler
        self._scheduler = AsyncIOScheduler(
            timezone=self.scheduler_config.timezone,
            job_defaults=self.scheduler_config.job_defaults
        )
        
        # State management
        self._state = SchedulerState.STOPPED
        self._scheduled_collectors: Dict[str, ScheduledCollector] = {}
        self._collector_registry = CollectorRegistry(self.metadata_tracker)
        
        # Error recovery
        self._error_recovery_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        
        # Setup event listeners
        self._setup_event_listeners()
        
        logger.info("Collection scheduler initialized with monitoring")
    
    def _setup_event_listeners(self) -> None:
        """Setup APScheduler event listeners for monitoring and error handling."""
        
        def job_executed_listener(event: JobExecutionEvent):
            """Handle successful job execution."""
            job_id = event.job_id
            if job_id in self._scheduled_collectors:
                scheduled_collector = self._scheduled_collectors[job_id]
                scheduled_collector.last_run = datetime.now()
                scheduled_collector.last_success = datetime.now()
                scheduled_collector.consecutive_errors = 0
                
                logger.debug(f"Job {job_id} executed successfully")
        
        def job_error_listener(event: JobExecutionEvent):
            """Handle job execution errors."""
            job_id = event.job_id
            if job_id in self._scheduled_collectors:
                scheduled_collector = self._scheduled_collectors[job_id]
                scheduled_collector.last_run = datetime.now()
                scheduled_collector.error_count += 1
                scheduled_collector.consecutive_errors += 1
                
                logger.error(
                    f"Job {job_id} failed: {event.exception}. "
                    f"Consecutive errors: {scheduled_collector.consecutive_errors}"
                )
                
                # Trigger error recovery if needed
                if (scheduled_collector.consecutive_errors >= 
                    self.scheduler_config.max_consecutive_errors):
                    asyncio.create_task(self._handle_collector_error_recovery(job_id))
        
        self._scheduler.add_listener(job_executed_listener, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
    
    def register_collector(
        self,
        collector: BaseDataCollector,
        interval: str,
        enabled: bool = True,
        **kwargs
    ) -> str:
        """
        Register a collector for scheduled execution.
        
        Args:
            collector: Collector instance to schedule
            interval: Interval string (e.g., '1h', '30m', '1d')
            enabled: Whether the collector should be enabled initially
            **kwargs: Additional scheduling options
            
        Returns:
            Job ID for the scheduled collector
        """
        collector_key = collector.get_collection_key()
        job_id = f"collector_{collector_key}"
        
        # Register collector in registry
        self._collector_registry.register(collector)
        
        # Create scheduled collector configuration
        scheduled_collector = ScheduledCollector(
            collector=collector,
            interval=interval,
            enabled=enabled,
            job_id=job_id,
            **kwargs
        )
        
        self._scheduled_collectors[job_id] = scheduled_collector
        
        # Add job to scheduler if running
        if self._state == SchedulerState.RUNNING and enabled:
            self._add_collector_job(scheduled_collector)
        
        logger.info(f"Registered collector {collector_key} with interval {interval}")
        return job_id
    
    def unregister_collector(self, job_id: str) -> bool:
        """
        Unregister a scheduled collector.
        
        Args:
            job_id: Job ID of the collector to unregister
            
        Returns:
            True if collector was found and removed, False otherwise
        """
        if job_id not in self._scheduled_collectors:
            return False
        
        # Remove from scheduler
        try:
            self._scheduler.remove_job(job_id)
        except Exception as e:
            logger.warning(f"Error removing job {job_id}: {e}")
        
        # Clean up
        scheduled_collector = self._scheduled_collectors.pop(job_id)
        collector_key = scheduled_collector.collector.get_collection_key()
        self._collector_registry.unregister(collector_key)
        
        # Cancel error recovery task if exists
        if job_id in self._error_recovery_tasks:
            self._error_recovery_tasks[job_id].cancel()
            del self._error_recovery_tasks[job_id]
        
        logger.info(f"Unregistered collector {collector_key}")
        return True
    
    def enable_collector(self, job_id: str) -> bool:
        """
        Enable a scheduled collector.
        
        Args:
            job_id: Job ID of the collector to enable
            
        Returns:
            True if collector was found and enabled, False otherwise
        """
        if job_id not in self._scheduled_collectors:
            return False
        
        scheduled_collector = self._scheduled_collectors[job_id]
        if not scheduled_collector.enabled:
            scheduled_collector.enabled = True
            
            if self._state == SchedulerState.RUNNING:
                self._add_collector_job(scheduled_collector)
            
            logger.info(f"Enabled collector {job_id}")
        
        return True
    
    def disable_collector(self, job_id: str) -> bool:
        """
        Disable a scheduled collector.
        
        Args:
            job_id: Job ID of the collector to disable
            
        Returns:
            True if collector was found and disabled, False otherwise
        """
        if job_id not in self._scheduled_collectors:
            return False
        
        scheduled_collector = self._scheduled_collectors[job_id]
        if scheduled_collector.enabled:
            scheduled_collector.enabled = False
            
            try:
                self._scheduler.remove_job(job_id)
            except Exception as e:
                logger.warning(f"Error removing job {job_id}: {e}")
            
            logger.info(f"Disabled collector {job_id}")
        
        return True
    
    def _add_collector_job(self, scheduled_collector: ScheduledCollector) -> None:
        """Add a collector job to the scheduler."""
        trigger = self._create_trigger(scheduled_collector.interval)
        
        self._scheduler.add_job(
            func=self._execute_collector,
            trigger=trigger,
            args=[scheduled_collector.job_id],
            id=scheduled_collector.job_id,
            name=f"Collector: {scheduled_collector.collector.get_collection_key()}",
            max_instances=scheduled_collector.max_instances,
            coalesce=scheduled_collector.coalesce,
            misfire_grace_time=scheduled_collector.misfire_grace_time
        )
        
        logger.debug(f"Added job {scheduled_collector.job_id} to scheduler")
    
    def _create_trigger(self, interval: str) -> IntervalTrigger:
        """
        Create an APScheduler trigger from interval string.
        
        Args:
            interval: Interval string (e.g., '1h', '30m', '1d')
            
        Returns:
            IntervalTrigger instance
        """
        if not interval or len(interval) < 2:
            raise ValueError(f"Invalid interval format: {interval}")
        
        unit = interval[-1].lower()
        try:
            value = int(interval[:-1])
        except ValueError:
            raise ValueError(f"Invalid interval format: {interval}")
        
        if unit == 'm':
            return IntervalTrigger(minutes=value)
        elif unit == 'h':
            return IntervalTrigger(hours=value)
        elif unit == 'd':
            return IntervalTrigger(days=value)
        elif unit == 's':
            return IntervalTrigger(seconds=value)
        else:
            raise ValueError(f"Unsupported interval unit: {unit}")
    
    async def _execute_collector(self, job_id: str) -> None:
        """
        Execute a collector with error handling and metadata tracking.
        
        Args:
            job_id: Job ID of the collector to execute
        """
        if job_id not in self._scheduled_collectors:
            logger.error(f"Unknown job ID: {job_id}")
            return
        
        scheduled_collector = self._scheduled_collectors[job_id]
        collector = scheduled_collector.collector
        collector_type = collector.get_collection_key()
        
        # Generate unique execution ID
        execution_id = f"{collector_type}_{int(datetime.now().timestamp())}_{job_id}"
        
        # Start execution tracking
        execution_record = self.execution_history.start_execution(
            collector_type=collector_type,
            execution_id=execution_id,
            metadata={"job_id": job_id, "scheduled": True}
        )
        
        start_time = datetime.now()
        
        try:
            logger.info(f"Executing collector: {collector_type} ({execution_id})")
            
            # Execute collection with error handling
            result = await collector.collect_with_error_handling()
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Complete execution tracking
            warnings = []
            if hasattr(result, 'warnings') and result.warnings:
                warnings.extend(result.warnings)
            
            self.execution_history.complete_execution(
                execution_id=execution_id,
                result=result,
                warnings=warnings
            )
            
            # Record performance metrics
            self.metrics_collector.record_execution(
                collector_type=collector_type,
                execution_time=execution_time,
                records_collected=result.records_collected,
                success=result.success,
                labels={"job_id": job_id}
            )
            
            # Update monitoring
            self.collection_monitor.update_from_execution(
                collector_type=collector_type,
                result=result,
                execution_time=execution_time
            )
            
            # Store in database if available
            if self.monitoring_db_manager:
                self.monitoring_db_manager.store_execution_record(execution_record)
                self.monitoring_db_manager.update_collection_metadata(
                    collector_type=collector_type,
                    execution_time=execution_time,
                    records_collected=result.records_collected,
                    success=result.success,
                    error_message="; ".join(result.errors) if result.errors else None
                )
            
            # Log results
            if result.success:
                logger.info(
                    f"Collection completed for {collector_type}: "
                    f"{result.records_collected} records in {execution_time:.2f}s"
                )
            else:
                logger.warning(
                    f"Collection failed for {collector_type}: "
                    f"{'; '.join(result.errors)}"
                )
                raise Exception(f"Collection failed: {'; '.join(result.errors)}")
                
        except Exception as e:
            # Calculate execution time for failed execution
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Create failed result for tracking
            failed_result = CollectionResult(
                success=False,
                records_collected=0,
                errors=[str(e)],
                collection_time=datetime.now(),
                collector_type=collector_type
            )
            
            # Complete execution tracking with failure
            self.execution_history.complete_execution(
                execution_id=execution_id,
                result=failed_result
            )
            
            # Record failed metrics
            self.metrics_collector.record_execution(
                collector_type=collector_type,
                execution_time=execution_time,
                records_collected=0,
                success=False,
                labels={"job_id": job_id, "error": str(e)}
            )
            
            # Update monitoring
            self.collection_monitor.update_from_execution(
                collector_type=collector_type,
                result=failed_result,
                execution_time=execution_time
            )
            
            # Store in database if available
            if self.monitoring_db_manager:
                self.monitoring_db_manager.store_execution_record(execution_record)
                self.monitoring_db_manager.update_collection_metadata(
                    collector_type=collector_type,
                    execution_time=execution_time,
                    records_collected=0,
                    success=False,
                    error_message=str(e)
                )
            
            logger.error(f"Error executing collector {job_id}: {e}")
            raise  # Re-raise to trigger APScheduler error handling
    
    async def _handle_collector_error_recovery(self, job_id: str) -> None:
        """
        Handle error recovery for a collector with consecutive failures.
        
        Args:
            job_id: Job ID of the failing collector
        """
        if job_id not in self._scheduled_collectors:
            return
        
        scheduled_collector = self._scheduled_collectors[job_id]
        collector_key = scheduled_collector.collector.get_collection_key()
        
        logger.warning(
            f"Starting error recovery for collector {collector_key} "
            f"after {scheduled_collector.consecutive_errors} consecutive errors"
        )
        
        # Disable collector temporarily
        self.disable_collector(job_id)
        
        # Wait for recovery delay
        await asyncio.sleep(self.scheduler_config.error_recovery_delay)
        
        # Check if scheduler is still running and collector still exists
        if self._state != SchedulerState.RUNNING or job_id not in self._scheduled_collectors:
            return
        
        # Reset error count and re-enable collector
        scheduled_collector.consecutive_errors = 0
        self.enable_collector(job_id)
        
        logger.info(f"Error recovery completed for collector {collector_key}")
    
    async def start(self) -> None:
        """
        Start the collection scheduler.
        
        Initializes all registered collectors and begins scheduled execution.
        """
        if self._state != SchedulerState.STOPPED:
            logger.warning(f"Scheduler already in state: {self._state}")
            return
        
        self._state = SchedulerState.STARTING
        logger.info("Starting collection scheduler")
        
        try:
            # Start APScheduler
            self._scheduler.start()
            
            # Add all enabled collector jobs
            for scheduled_collector in self._scheduled_collectors.values():
                if scheduled_collector.enabled:
                    self._add_collector_job(scheduled_collector)
            
            # Start health check task
            asyncio.create_task(self._health_check_loop())
            
            self._state = SchedulerState.RUNNING
            logger.info(
                f"Collection scheduler started with "
                f"{len(self._scheduled_collectors)} collectors"
            )
            
        except Exception as e:
            self._state = SchedulerState.ERROR
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the collection scheduler gracefully.
        
        Waits for running jobs to complete before shutting down.
        """
        if self._state not in [SchedulerState.RUNNING, SchedulerState.ERROR]:
            logger.warning(f"Scheduler not running, current state: {self._state}")
            return
        
        self._state = SchedulerState.STOPPING
        logger.info("Stopping collection scheduler")
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel error recovery tasks
            for task in self._error_recovery_tasks.values():
                task.cancel()
            self._error_recovery_tasks.clear()
            
            # Shutdown scheduler with timeout
            self._scheduler.shutdown(wait=True)
            
            # Wait for any remaining tasks
            await asyncio.sleep(1)
            
            self._state = SchedulerState.STOPPED
            logger.info("Collection scheduler stopped")
            
        except Exception as e:
            self._state = SchedulerState.ERROR
            logger.error(f"Error stopping scheduler: {e}")
            raise
    
    async def _health_check_loop(self) -> None:
        """Periodic health check for collectors and scheduler."""
        while self._state == SchedulerState.RUNNING and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.scheduler_config.health_check_interval)
                
                if self._shutdown_event.is_set():
                    break
                
                # Check collector health
                unhealthy_collectors = self._collector_registry.get_unhealthy_collectors()
                if unhealthy_collectors:
                    logger.warning(f"Unhealthy collectors detected: {unhealthy_collectors}")
                
                # Log scheduler status
                logger.debug(f"Scheduler health check: {len(self._scheduled_collectors)} collectors")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive scheduler status.
        
        Returns:
            Dictionary with scheduler and collector status information
        """
        collector_status = {}
        for job_id, scheduled_collector in self._scheduled_collectors.items():
            collector_status[job_id] = {
                "collector_key": scheduled_collector.collector.get_collection_key(),
                "interval": scheduled_collector.interval,
                "enabled": scheduled_collector.enabled,
                "last_run": scheduled_collector.last_run,
                "last_success": scheduled_collector.last_success,
                "error_count": scheduled_collector.error_count,
                "consecutive_errors": scheduled_collector.consecutive_errors
            }
        
        return {
            "state": self._state.value,
            "total_collectors": len(self._scheduled_collectors),
            "enabled_collectors": sum(1 for sc in self._scheduled_collectors.values() if sc.enabled),
            "running_jobs": len(self._scheduler.get_jobs()) if self._scheduler.running else 0,
            "collectors": collector_status,
            "registry_summary": self._collector_registry.get_registry_summary(),
            "scheduler_running": self._scheduler.running
        }
    
    def get_collector_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status for a specific collector.
        
        Args:
            job_id: Job ID of the collector
            
        Returns:
            Collector status dictionary or None if not found
        """
        print("get_collector_status for job_id: ", job_id)
        
        print("self._scheduled_collectors: ", self._scheduled_collectors)

        if job_id not in self._scheduled_collectors:
            return None        

        scheduled_collector = self._scheduled_collectors[job_id]
        return {
            "job_id": job_id,
            "collector_key": scheduled_collector.collector.get_collection_key(),
            "interval": scheduled_collector.interval,
            "enabled": scheduled_collector.enabled,
            "last_run": scheduled_collector.last_run,
            "last_success": scheduled_collector.last_success,
            "error_count": scheduled_collector.error_count,
            "consecutive_errors": scheduled_collector.consecutive_errors,
            "metadata": scheduled_collector.collector.get_metadata()
        }
    
    async def execute_collector_now(self, job_id: str) -> CollectionResult:
        """
        Execute a collector immediately, outside of its scheduled time.
        
        Args:
            job_id: Job ID of the collector to execute
            
        Returns:
            CollectionResult from the execution
        """
        if job_id not in self._scheduled_collectors:
            raise ValueError(f"Unknown job ID: {job_id}")
        
        scheduled_collector = self._scheduled_collectors[job_id]
        collector = scheduled_collector.collector
        
        logger.info(f"Executing collector {collector.get_collection_key()} on demand")
        
        # Execute collection
        result = await collector.collect_with_error_handling()
        
        # Update scheduled collector metadata
        scheduled_collector.last_run = datetime.now()
        if result.success:
            scheduled_collector.last_success = datetime.now()
            scheduled_collector.consecutive_errors = 0
        else:
            scheduled_collector.error_count += 1
            scheduled_collector.consecutive_errors += 1
        
        return result
    
    def list_collectors(self) -> List[str]:
        """
        Get list of all registered collector job IDs.
        
        Returns:
            List of job IDs
        """
        return list(self._scheduled_collectors.keys())
    
    def get_next_run_times(self) -> Dict[str, Optional[datetime]]:
        """
        Get next scheduled run times for all collectors.
        
        Returns:
            Dictionary mapping job IDs to their next run times
        """
        next_runs = {}
        
        for job_id in self._scheduled_collectors.keys():
            try:
                job = self._scheduler.get_job(job_id)
                next_runs[job_id] = job.next_run_time if job else None
            except Exception:
                next_runs[job_id] = None
        
        return next_runs
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring status for all collectors.
        
        Returns:
            Dictionary with monitoring information
        """
        return {
            "scheduler_status": self.get_status(),
            "system_health": self.collection_monitor.get_system_health_summary(),
            "collector_health": {
                name: health.to_dict() 
                for name, health in self.collection_monitor.get_collector_health().items()
            },
            "performance_metrics": self.metrics_collector.get_aggregated_metrics(),
            "recent_alerts": [
                alert.to_dict() for alert in self.collection_monitor.get_alerts(limit=10)
            ],
            "execution_statistics": {
                collector_type: self.execution_history.get_execution_statistics(collector_type)
                for collector_type in self._collector_registry.get_collector_keys()
            }
        }
    
    def get_performance_metrics(
        self,
        collector_type: Optional[str] = None,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for collectors.
        
        Args:
            collector_type: Optional filter by collector type
            time_window: Optional time window for metrics
            
        Returns:
            Dictionary with performance metrics
        """
        return {
            "metrics": self.metrics_collector.get_metrics(collector_type),
            "aggregated": self.metrics_collector.get_aggregated_metrics(time_window),
            "alerts": self.metrics_collector.get_performance_alerts(),
            "custom_metrics": self.metrics_collector.get_custom_metrics(time_window=time_window)
        }
    
    def get_execution_history(
        self,
        collector_type: Optional[str] = None,
        limit: Optional[int] = None,
        time_window: Optional[timedelta] = None
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for collectors.
        
        Args:
            collector_type: Optional filter by collector type
            limit: Maximum number of records to return
            time_window: Optional time window for history
            
        Returns:
            List of execution record dictionaries
        """
        records = self.execution_history.get_execution_history(
            collector_type=collector_type,
            limit=limit
        )
        
        if time_window:
            cutoff_time = datetime.now() - time_window
            records = [r for r in records if r.start_time >= cutoff_time]
        
        return [record.to_dict() for record in records]
    
    def get_alerts(
        self,
        level: Optional[str] = None,
        collector_type: Optional[str] = None,
        unresolved_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get system alerts.
        
        Args:
            level: Optional filter by alert level
            collector_type: Optional filter by collector type
            unresolved_only: Only return unresolved alerts
            
        Returns:
            List of alert dictionaries
        """
        from gecko_terminal_collector.monitoring.collection_monitor import AlertLevel
        
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                logger.warning(f"Invalid alert level: {level}")
        
        alerts = self.collection_monitor.get_alerts(
            level=alert_level,
            collector_type=collector_type,
            unresolved_only=unresolved_only
        )
        
        return [alert.to_dict() for alert in alerts]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            
        Returns:
            True if alert was acknowledged, False otherwise
        """
        success = self.collection_monitor.acknowledge_alert(alert_id)
        
        # Update in database if available
        if success and self.monitoring_db_manager:
            alerts = self.collection_monitor.get_alerts(unresolved_only=False)
            for alert in alerts:
                if alert.id == alert_id:
                    self.monitoring_db_manager.store_alert(alert)
                    break
        
        return success
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            
        Returns:
            True if alert was resolved, False otherwise
        """
        success = self.collection_monitor.resolve_alert(alert_id)
        
        # Update in database if available
        if success and self.monitoring_db_manager:
            alerts = self.collection_monitor.get_alerts(unresolved_only=False)
            for alert in alerts:
                if alert.id == alert_id:
                    self.monitoring_db_manager.store_alert(alert)
                    break
        
        return success
    
    def suppress_alerts(self, collector_type: str, duration_minutes: int = 60) -> None:
        """
        Suppress alerts for a collector type.
        
        Args:
            collector_type: Collector type to suppress alerts for
            duration_minutes: Duration to suppress alerts
        """
        self.collection_monitor.suppress_alerts(collector_type, duration_minutes)
    
    def cleanup_monitoring_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """
        Clean up old monitoring data.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Dictionary with counts of removed records
        """
        # Clean up in-memory data
        execution_removed = self.execution_history.cleanup_old_records(days_to_keep)
        alert_removed = self.collection_monitor.cleanup_old_alerts(days_to_keep)
        
        cleanup_counts = {
            "execution_history_memory": execution_removed,
            "alerts_memory": alert_removed
        }
        
        # Clean up database data if available
        if self.monitoring_db_manager:
            db_counts = self.monitoring_db_manager.cleanup_old_data(days_to_keep)
            cleanup_counts.update(db_counts)
        
        return cleanup_counts
    
    def export_monitoring_data(self) -> Dict[str, Any]:
        """
        Export comprehensive monitoring data for analysis.
        
        Returns:
            Dictionary with all monitoring data
        """
        return {
            "export_time": datetime.now().isoformat(),
            "scheduler_info": self.get_status(),
            "monitoring_status": self.get_monitoring_status(),
            "execution_history": self.execution_history.export_history(),
            "performance_metrics": self.metrics_collector.export_metrics(),
            "collection_monitor": self.collection_monitor.export_monitoring_data()
        }