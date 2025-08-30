"""
Execution history tracking for collection operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from gecko_terminal_collector.models.core import CollectionResult

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRecord:
    """Record of a single collection execution."""
    collector_type: str
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    records_collected: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate execution duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds."""
        duration = self.duration
        return duration.total_seconds() if duration else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution record to dictionary."""
        return {
            "collector_type": self.collector_type,
            "execution_id": self.execution_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "records_collected": self.records_collected,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata
        }


class ExecutionHistoryTracker:
    """
    Tracks execution history for all collection operations.
    
    Provides detailed logging and analysis of collection executions
    with configurable retention and query capabilities.
    """
    
    def __init__(self, max_records_per_collector: int = 100):
        """
        Initialize execution history tracker.
        
        Args:
            max_records_per_collector: Maximum records to keep per collector type
        """
        self.max_records_per_collector = max_records_per_collector
        self._execution_history: Dict[str, List[ExecutionRecord]] = {}
        self._active_executions: Dict[str, ExecutionRecord] = {}
    
    def start_execution(
        self,
        collector_type: str,
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionRecord:
        """
        Start tracking a new execution.
        
        Args:
            collector_type: Type of collector being executed
            execution_id: Unique identifier for this execution
            metadata: Optional metadata for the execution
            
        Returns:
            ExecutionRecord for the started execution
        """
        record = ExecutionRecord(
            collector_type=collector_type,
            execution_id=execution_id,
            start_time=datetime.now(),
            metadata=metadata or {}
        )
        
        self._active_executions[execution_id] = record
        
        logger.info(f"Started execution tracking for {collector_type} ({execution_id})")
        return record
    
    def complete_execution(
        self,
        execution_id: str,
        result: CollectionResult,
        warnings: Optional[List[str]] = None
    ) -> Optional[ExecutionRecord]:
        """
        Complete an execution and update its record.
        
        Args:
            execution_id: Execution ID to complete
            result: Collection result
            warnings: Optional list of warnings
            
        Returns:
            Completed ExecutionRecord or None if not found
        """
        if execution_id not in self._active_executions:
            logger.warning(f"No active execution found for ID: {execution_id}")
            return None
        
        record = self._active_executions.pop(execution_id)
        record.end_time = datetime.now()
        record.records_collected = result.records_collected
        record.errors = result.errors.copy()
        record.warnings = warnings or []
        
        # Determine status
        if result.success:
            if warnings:
                record.status = ExecutionStatus.PARTIAL
            else:
                record.status = ExecutionStatus.SUCCESS
        else:
            record.status = ExecutionStatus.FAILURE
        
        # Store in history
        self._add_to_history(record)
        
        duration_str = f"{record.duration_seconds:.2f}s" if record.duration_seconds is not None else "unknown"
        logger.info(
            f"Completed execution {execution_id} for {record.collector_type}: "
            f"{record.status.value} ({duration_str}, "
            f"{record.records_collected} records)"
        )
        
        return record
    
    def cancel_execution(self, execution_id: str, reason: str = "Cancelled") -> Optional[ExecutionRecord]:
        """
        Cancel an active execution.
        
        Args:
            execution_id: Execution ID to cancel
            reason: Reason for cancellation
            
        Returns:
            Cancelled ExecutionRecord or None if not found
        """
        if execution_id not in self._active_executions:
            return None
        
        record = self._active_executions.pop(execution_id)
        record.end_time = datetime.now()
        record.status = ExecutionStatus.CANCELLED
        record.errors.append(reason)
        
        self._add_to_history(record)
        
        logger.warning(f"Cancelled execution {execution_id}: {reason}")
        return record
    
    def _add_to_history(self, record: ExecutionRecord) -> None:
        """Add a record to the execution history."""
        collector_type = record.collector_type
        
        if collector_type not in self._execution_history:
            self._execution_history[collector_type] = []
        
        history = self._execution_history[collector_type]
        history.append(record)
        
        # Maintain maximum records limit
        if len(history) > self.max_records_per_collector:
            history.pop(0)  # Remove oldest record
    
    def get_execution_history(
        self,
        collector_type: Optional[str] = None,
        limit: Optional[int] = None,
        status_filter: Optional[ExecutionStatus] = None
    ) -> List[ExecutionRecord]:
        """
        Get execution history with optional filtering.
        
        Args:
            collector_type: Filter by collector type
            limit: Maximum number of records to return
            status_filter: Filter by execution status
            
        Returns:
            List of ExecutionRecord objects
        """
        records = []
        
        if collector_type:
            records = self._execution_history.get(collector_type, []).copy()
        else:
            for history in self._execution_history.values():
                records.extend(history)
        
        # Apply status filter
        if status_filter:
            records = [r for r in records if r.status == status_filter]
        
        # Sort by start time (most recent first)
        records.sort(key=lambda r: r.start_time, reverse=True)
        
        # Apply limit
        if limit:
            records = records[:limit]
        
        return records
    
    def get_active_executions(self) -> List[ExecutionRecord]:
        """
        Get list of currently active executions.
        
        Returns:
            List of active ExecutionRecord objects
        """
        return list(self._active_executions.values())
    
    def get_execution_statistics(
        self,
        collector_type: Optional[str] = None,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Get execution statistics for analysis.
        
        Args:
            collector_type: Filter by collector type
            time_window: Only include executions within this time window
            
        Returns:
            Dictionary with execution statistics
        """
        records = self.get_execution_history(collector_type)
        
        # Apply time window filter
        if time_window:
            cutoff_time = datetime.now() - time_window
            records = [r for r in records if r.start_time >= cutoff_time]
        
        if not records:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "total_records_collected": 0
            }
        
        # Calculate statistics
        total_executions = len(records)
        successful_executions = len([r for r in records if r.status == ExecutionStatus.SUCCESS])
        partial_executions = len([r for r in records if r.status == ExecutionStatus.PARTIAL])
        failed_executions = len([r for r in records if r.status == ExecutionStatus.FAILURE])
        
        durations = [r.duration_seconds for r in records if r.duration_seconds is not None]
        average_duration = sum(durations) / len(durations) if durations else 0.0
        
        total_records = sum(r.records_collected for r in records)
        
        success_rate = (successful_executions + partial_executions) / total_executions * 100
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "partial_executions": partial_executions,
            "failed_executions": failed_executions,
            "success_rate": success_rate,
            "average_duration": average_duration,
            "total_records_collected": total_records,
            "time_window": str(time_window) if time_window else "all_time"
        }
    
    def get_recent_failures(
        self,
        collector_type: Optional[str] = None,
        hours: int = 24
    ) -> List[ExecutionRecord]:
        """
        Get recent failed executions.
        
        Args:
            collector_type: Filter by collector type
            hours: Number of hours to look back
            
        Returns:
            List of failed ExecutionRecord objects
        """
        time_window = timedelta(hours=hours)
        records = self.get_execution_history(collector_type, status_filter=ExecutionStatus.FAILURE)
        
        cutoff_time = datetime.now() - time_window
        return [r for r in records if r.start_time >= cutoff_time]
    
    def cleanup_old_records(self, days_to_keep: int = 30) -> int:
        """
        Clean up old execution records.
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            Number of records removed
        """
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        removed_count = 0
        
        for collector_type, history in self._execution_history.items():
            original_count = len(history)
            self._execution_history[collector_type] = [
                r for r in history if r.start_time >= cutoff_time
            ]
            removed_count += original_count - len(self._execution_history[collector_type])
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old execution records")
        
        return removed_count
    
    def export_history(
        self,
        collector_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Export execution history for external analysis.
        
        Args:
            collector_type: Filter by collector type
            limit: Maximum number of records to export
            
        Returns:
            Dictionary with execution history data
        """
        records = self.get_execution_history(collector_type, limit)
        
        return {
            "export_time": datetime.now().isoformat(),
            "total_records": len(records),
            "collector_type_filter": collector_type,
            "executions": [record.to_dict() for record in records],
            "statistics": self.get_execution_statistics(collector_type)
        }