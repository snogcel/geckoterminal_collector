"""
Collection metadata tracking and management utilities.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from gecko_terminal_collector.models.core import CollectionResult

logger = logging.getLogger(__name__)


@dataclass
class CollectionMetadata:
    """Metadata for tracking collection operations."""
    collector_type: str
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_records_collected: int = 0
    last_error: Optional[str] = None
    error_history: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Check if collector is considered healthy (>80% success rate)."""
        return self.success_rate >= 80.0
    
    def update_from_result(self, result: CollectionResult) -> None:
        """Update metadata from a collection result."""
        self.last_run = result.collection_time
        self.total_runs += 1
        self.total_records_collected += result.records_collected
        
        if result.success:
            self.successful_runs += 1
            self.last_success = result.collection_time
            self.last_error = None
        else:
            self.failed_runs += 1
            if result.errors:
                error_msg = "; ".join(result.errors)
                self.last_error = error_msg
                self.error_history.append(f"{result.collection_time}: {error_msg}")
                
                # Keep only last 10 errors
                if len(self.error_history) > 10:
                    self.error_history = self.error_history[-10:]
    
    def to_dict(self) -> Dict:
        """Convert metadata to dictionary for serialization."""
        return {
            "collector_type": self.collector_type,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "total_records_collected": self.total_records_collected,
            "last_error": self.last_error,
            "error_history": self.error_history,
            "is_healthy": self.is_healthy
        }


class MetadataTracker:
    """
    Tracks collection metadata for all collectors.
    
    Provides centralized tracking of collection statistics,
    success rates, and error history for monitoring and debugging.
    """
    
    def __init__(self):
        self._metadata: Dict[str, CollectionMetadata] = {}
    
    def get_metadata(self, collector_type: str) -> CollectionMetadata:
        """Get metadata for a collector type, creating if not exists."""
        if collector_type not in self._metadata:
            self._metadata[collector_type] = CollectionMetadata(collector_type)
        return self._metadata[collector_type]
    
    def update_metadata(self, result: CollectionResult) -> None:
        """Update metadata from a collection result."""
        metadata = self.get_metadata(result.collector_type)
        metadata.update_from_result(result)
        
        logger.info(
            f"Updated metadata for {result.collector_type}: "
            f"Success rate: {metadata.success_rate:.1f}%, "
            f"Total runs: {metadata.total_runs}, "
            f"Records collected: {result.records_collected}"
        )
    
    def get_all_metadata(self) -> Dict[str, CollectionMetadata]:
        """Get metadata for all collectors."""
        return self._metadata.copy()
    
    def get_health_summary(self) -> Dict[str, bool]:
        """Get health status for all collectors."""
        return {
            collector_type: metadata.is_healthy
            for collector_type, metadata in self._metadata.items()
        }
    
    def get_unhealthy_collectors(self) -> List[str]:
        """Get list of collectors with poor health status."""
        return [
            collector_type
            for collector_type, metadata in self._metadata.items()
            if not metadata.is_healthy and metadata.total_runs > 0
        ]
    
    def reset_metadata(self, collector_type: str) -> None:
        """Reset metadata for a specific collector."""
        if collector_type in self._metadata:
            del self._metadata[collector_type]
            logger.info(f"Reset metadata for {collector_type}")
    
    def export_summary(self) -> Dict:
        """Export summary of all collection metadata."""
        summary = {
            "total_collectors": len(self._metadata),
            "healthy_collectors": len([m for m in self._metadata.values() if m.is_healthy]),
            "unhealthy_collectors": self.get_unhealthy_collectors(),
            "collectors": {
                collector_type: metadata.to_dict()
                for collector_type, metadata in self._metadata.items()
            }
        }
        
        # Calculate overall statistics
        if self._metadata:
            total_runs = sum(m.total_runs for m in self._metadata.values())
            successful_runs = sum(m.successful_runs for m in self._metadata.values())
            total_records = sum(m.total_records_collected for m in self._metadata.values())
            
            summary["overall_stats"] = {
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "overall_success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0,
                "total_records_collected": total_records
            }
        
        return summary