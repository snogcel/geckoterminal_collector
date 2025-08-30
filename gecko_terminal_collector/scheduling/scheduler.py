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
        metadata_tracker: Optional[MetadataTracker] = None
    ):
        """
        Initialize the collection scheduler.
        
        Args:
            config: Collection configuration
            scheduler_config: Scheduler-specific configuration
            metadata_tracker: Optional metadata tracker for statistics
        """
        self.config = config
        self.scheduler_config = scheduler_config or SchedulerConfig()
        self.metadata_tracker = metadata_tracker or MetadataTracker()
        
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
        
        logger.info("Collection scheduler initialized")
    
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
        
        try:
            logger.info(f"Executing collector: {collector.get_collection_key()}")
            
            # Execute collection with error handling
            result = await collector.collect_with_error_handling()
            
            # Log results
            if result.success:
                logger.info(
                    f"Collection completed for {collector.get_collection_key()}: "
                    f"{result.records_collected} records"
                )
            else:
                logger.warning(
                    f"Collection failed for {collector.get_collection_key()}: "
                    f"{'; '.join(result.errors)}"
                )
                raise Exception(f"Collection failed: {'; '.join(result.errors)}")
                
        except Exception as e:
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