"""
Enhanced SQLAlchemy database manager with comprehensive metadata population.
"""

import json
import logging
import uuid
import decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import (
    CollectionMetadata as CollectionMetadataModel,
    ExecutionHistory as ExecutionHistoryModel,
    PerformanceMetrics as PerformanceMetricsModel,
    SystemAlerts as SystemAlertsModel,
)

logger = logging.getLogger(__name__)


class CollectionResult:
    """Data class for collection run results."""
    
    def __init__(
        self,
        collector_type: str,
        execution_id: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        status: str = "success",
        records_collected: int = 0,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.collector_type = collector_type
        self.execution_id = execution_id
        self.start_time = start_time
        self.end_time = end_time or datetime.utcnow()
        self.status = status
        self.records_collected = records_collected
        self.errors = errors or []
        self.warnings = warnings or []
        self.metadata = metadata or {}
        
    @property
    def success(self) -> bool:
        """Check if collection was successful."""
        return self.status == "success"
    
    @property
    def execution_time(self) -> float:
        """Get execution time in seconds."""
        return (self.end_time - self.start_time).total_seconds()


class EnhancedDatabaseManager(SQLAlchemyDatabaseManager):
    """
    Enhanced SQLAlchemy database manager with comprehensive metadata population.
    
    Extends the base SQLAlchemy manager with methods for storing collection
    metadata, execution history, performance metrics, and system alerts.
    """
    
    async def store_collection_run(self, result: CollectionResult) -> None:
        """
        Store comprehensive collection run information across all metadata tables.
        
        Args:
            result: Collection result containing all run information
        """
        with self.connection.get_session() as session:
            try:
                # Store execution history
                await self._store_execution_history(session, result)
                
                # Update collection metadata
                await self._update_collection_metadata(session, result)
                
                # Store performance metrics
                await self._store_performance_metrics(session, result)
                
                # Create system alerts for failures
                if not result.success:
                    await self._create_system_alert(session, result)
                
                session.commit()
                logger.info(f"Stored collection run metadata for {result.collector_type}")
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing collection run metadata: {e}")
                raise
    
    async def _store_execution_history(self, session: Session, result: CollectionResult) -> None:
        """Store execution history record."""
        execution_record = ExecutionHistoryModel(
            collector_type=result.collector_type,
            execution_id=result.execution_id,
            start_time=result.start_time,
            end_time=result.end_time,
            status=result.status,
            records_collected=result.records_collected,
            execution_time=result.execution_time,
            error_message="; ".join(result.errors) if result.errors else None,
            warnings=json.dumps(result.warnings) if result.warnings else None,
            execution_metadata=json.dumps(result.metadata) if result.metadata else None,
        )
        session.add(execution_record)
    
    async def _update_collection_metadata(self, session: Session, result: CollectionResult) -> None:
        """Update collection metadata with aggregated statistics."""
        # Get or create collection metadata record
        metadata = session.query(CollectionMetadataModel).filter_by(
            collector_type=result.collector_type
        ).first()
        
        if not metadata:
            metadata = CollectionMetadataModel(
                collector_type=result.collector_type,
                run_count=0,
                error_count=0,
                total_execution_time=Decimal('0.0'),
                total_records_collected=0,
                average_execution_time=Decimal('0.0'),
                success_rate=Decimal('100.0'),
                health_score=Decimal('100.0'),
            )
            session.add(metadata)
        
        # Update statistics
        metadata.last_run = result.end_time
        metadata.run_count += 1
        metadata.total_execution_time += Decimal(str(result.execution_time))
        metadata.total_records_collected += result.records_collected
        
        if result.success:
            metadata.last_success = result.end_time
        else:
            metadata.error_count += 1
            metadata.last_error = "; ".join(result.errors) if result.errors else "Unknown error"
        
        # Calculate derived metrics
        metadata.average_execution_time = metadata.total_execution_time / metadata.run_count
        metadata.success_rate = Decimal('100.0') * (metadata.run_count - metadata.error_count) / metadata.run_count
        
        # Calculate health score (weighted combination of success rate and recent performance)
        recent_success_weight = Decimal('0.7')
        execution_time_weight = Decimal('0.3')
        
        # Recent success factor (based on last 10 runs)
        recent_runs = session.query(ExecutionHistoryModel).filter_by(
            collector_type=result.collector_type
        ).order_by(desc(ExecutionHistoryModel.start_time)).limit(10).all()
        
        if recent_runs:
            recent_successes = sum(1 for run in recent_runs if run.status == "success")
            recent_success_rate = Decimal(str(recent_successes)) / len(recent_runs)
        else:
            recent_success_rate = Decimal('1.0') if result.success else Decimal('0.0')
        
        # Execution time factor (penalize very slow executions)
        avg_time_minutes = metadata.average_execution_time / 60
        time_penalty = max(Decimal('0.0'), min(Decimal('1.0'), avg_time_minutes / 10))  # Penalty starts at 10 minutes
        execution_time_factor = Decimal('1.0') - time_penalty
        
        metadata.health_score = (
            recent_success_weight * recent_success_rate * 100 +
            execution_time_weight * execution_time_factor * 100
        )
        
        metadata.last_updated = datetime.utcnow()
    
    async def _store_performance_metrics(self, session: Session, result: CollectionResult) -> None:
        """Store performance metrics from collection run."""
        base_metrics = [
            ("execution_time", result.execution_time),
            ("records_collected", result.records_collected),
            ("success", 1 if result.success else 0),
        ]
        
        # Add custom metrics from result metadata
        custom_metrics = []
        if result.metadata:
            for key, value in result.metadata.items():
                if isinstance(value, (int, float, Decimal)):
                    custom_metrics.append((key, value))
        
        # Store all metrics
        for metric_name, metric_value in base_metrics + custom_metrics:
            try:
                # Convert metric value to Decimal safely
                if isinstance(metric_value, bool):
                    decimal_value = Decimal('1' if metric_value else '0')
                elif isinstance(metric_value, (int, float)):
                    decimal_value = Decimal(str(metric_value))
                elif isinstance(metric_value, Decimal):
                    decimal_value = metric_value
                else:
                    # Skip non-numeric values
                    logger.warning(f"Skipping non-numeric metric {metric_name}={metric_value}")
                    continue
                
                metric_record = PerformanceMetricsModel(
                    collector_type=result.collector_type,
                    metric_name=metric_name,
                    metric_value=decimal_value,
                    timestamp=result.end_time,
                    labels=json.dumps({"execution_id": result.execution_id}),
                )
                session.add(metric_record)
            except (ValueError, TypeError, decimal.InvalidOperation) as e:
                logger.warning(f"Skipping invalid metric {metric_name}={metric_value}: {e}")
    
    async def _create_system_alert(self, session: Session, result: CollectionResult) -> None:
        """Create system alert for failed collection runs."""
        alert_id = f"{result.collector_type}_{result.execution_id}_{int(result.end_time.timestamp())}"
        
        # Determine alert level based on error patterns
        error_text = " ".join(result.errors).lower()
        if "rate limit" in error_text or "429" in error_text:
            level = "warning"
        elif "timeout" in error_text or "connection" in error_text:
            level = "warning"
        else:
            level = "error"
        
        alert = SystemAlertsModel(
            alert_id=alert_id,
            level=level,
            collector_type=result.collector_type,
            message=f"Collection failed: {'; '.join(result.errors)}",
            timestamp=result.end_time,
            acknowledged=False,
            resolved=False,
            alert_metadata=json.dumps({
                "execution_id": result.execution_id,
                "execution_time": result.execution_time,
                "records_collected": result.records_collected,
                "warnings": result.warnings,
            }),
        )
        session.add(alert)
    
    async def bulk_store_with_metadata(
        self,
        data: List[Any],
        collector_type: str,
        store_method: str,
        execution_id: Optional[str] = None
    ) -> CollectionResult:
        """
        Store data with automatic metadata tracking and bulk optimization.
        
        Args:
            data: List of data objects to store
            collector_type: Type of collector performing the operation
            store_method: Name of the storage method to call
            execution_id: Optional execution ID (generated if not provided)
            
        Returns:
            CollectionResult with operation details
        """
        execution_id = execution_id or str(uuid.uuid4())
        start_time = datetime.utcnow()
        errors = []
        warnings = []
        records_stored = 0
        
        try:
            # Get the storage method
            storage_method = getattr(self, store_method)
            if not storage_method:
                raise AttributeError(f"Storage method '{store_method}' not found")
            
            # Perform bulk storage with chunking for large datasets
            chunk_size = 1000  # Configurable chunk size
            total_chunks = (len(data) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                try:
                    chunk_stored = await storage_method(chunk)
                    records_stored += chunk_stored
                    
                    # Log progress for large operations
                    if total_chunks > 1:
                        chunk_num = (i // chunk_size) + 1
                        logger.info(f"Processed chunk {chunk_num}/{total_chunks} for {collector_type}")
                        
                except Exception as e:
                    error_msg = f"Error storing chunk {i//chunk_size + 1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            end_time = datetime.utcnow()
            status = "success" if not errors else ("partial" if records_stored > 0 else "failure")
            
            # Create collection result
            result = CollectionResult(
                collector_type=collector_type,
                execution_id=execution_id,
                start_time=start_time,
                end_time=end_time,
                status=status,
                records_collected=records_stored,
                errors=errors,
                warnings=warnings,
                metadata={
                    "total_input_records": len(data),
                    "chunk_size": chunk_size,
                    "total_chunks": total_chunks,
                    "storage_method": store_method,
                }
            )
            
            # Store metadata
            await self.store_collection_run(result)
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_msg = f"Bulk storage failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            result = CollectionResult(
                collector_type=collector_type,
                execution_id=execution_id,
                start_time=start_time,
                end_time=end_time,
                status="failure",
                records_collected=records_stored,
                errors=errors,
                warnings=warnings,
                metadata={
                    "total_input_records": len(data),
                    "storage_method": store_method,
                }
            )
            
            # Store metadata even for failures
            try:
                await self.store_collection_run(result)
            except Exception as meta_error:
                logger.error(f"Failed to store metadata for failed operation: {meta_error}")
            
            return result
    
    async def get_collection_statistics(self, collector_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive collection statistics.
        
        Args:
            collector_type: Optional collector type filter
            
        Returns:
            Dictionary containing collection statistics
        """
        with self.connection.get_session() as session:
            stats = {}
            
            # Base query
            metadata_query = session.query(CollectionMetadataModel)
            if collector_type:
                metadata_query = metadata_query.filter_by(collector_type=collector_type)
            
            metadata_records = metadata_query.all()
            
            for metadata in metadata_records:
                collector_stats = {
                    "last_run": metadata.last_run.isoformat() if metadata.last_run else None,
                    "last_success": metadata.last_success.isoformat() if metadata.last_success else None,
                    "run_count": metadata.run_count,
                    "error_count": metadata.error_count,
                    "success_rate": float(metadata.success_rate),
                    "health_score": float(metadata.health_score),
                    "average_execution_time": float(metadata.average_execution_time),
                    "total_records_collected": metadata.total_records_collected,
                    "last_error": metadata.last_error,
                }
                
                # Get recent execution history
                recent_executions = session.query(ExecutionHistoryModel).filter_by(
                    collector_type=metadata.collector_type
                ).order_by(desc(ExecutionHistoryModel.start_time)).limit(10).all()
                
                collector_stats["recent_executions"] = [
                    {
                        "execution_id": exec.execution_id,
                        "start_time": exec.start_time.isoformat(),
                        "status": exec.status,
                        "records_collected": exec.records_collected,
                        "execution_time": float(exec.execution_time) if exec.execution_time else None,
                    }
                    for exec in recent_executions
                ]
                
                # Get active alerts
                active_alerts = session.query(SystemAlertsModel).filter(
                    and_(
                        SystemAlertsModel.collector_type == metadata.collector_type,
                        SystemAlertsModel.resolved == False
                    )
                ).order_by(desc(SystemAlertsModel.timestamp)).limit(5).all()
                
                collector_stats["active_alerts"] = [
                    {
                        "alert_id": alert.alert_id,
                        "level": alert.level,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "acknowledged": alert.acknowledged,
                    }
                    for alert in active_alerts
                ]
                
                stats[metadata.collector_type] = collector_stats
            
            return stats
    
    async def get_performance_metrics(
        self,
        collector_type: str,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics for analysis.
        
        Args:
            collector_type: Collector type to query
            metric_name: Optional specific metric name
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of records to return
            
        Returns:
            List of performance metric records
        """
        with self.connection.get_session() as session:
            query = session.query(PerformanceMetricsModel).filter_by(
                collector_type=collector_type
            )
            
            if metric_name:
                query = query.filter_by(metric_name=metric_name)
            
            if start_time:
                query = query.filter(PerformanceMetricsModel.timestamp >= start_time)
            
            if end_time:
                query = query.filter(PerformanceMetricsModel.timestamp <= end_time)
            
            metrics = query.order_by(desc(PerformanceMetricsModel.timestamp)).limit(limit).all()
            
            return [
                {
                    "metric_name": metric.metric_name,
                    "metric_value": float(metric.metric_value),
                    "timestamp": metric.timestamp.isoformat(),
                    "labels": json.loads(metric.labels) if metric.labels else {},
                }
                for metric in metrics
            ]
    
    async def resolve_system_alert(self, alert_id: str, resolved_by: Optional[str] = None) -> bool:
        """
        Resolve a system alert.
        
        Args:
            alert_id: Alert ID to resolve
            resolved_by: Optional identifier of who resolved the alert
            
        Returns:
            True if alert was resolved, False if not found
        """
        with self.connection.get_session() as session:
            try:
                alert = session.query(SystemAlertsModel).filter_by(alert_id=alert_id).first()
                
                if not alert:
                    return False
                
                alert.resolved = True
                alert.updated_at = datetime.utcnow()
                
                # Update metadata if provided
                if resolved_by:
                    metadata = json.loads(alert.alert_metadata) if alert.alert_metadata else {}
                    metadata["resolved_by"] = resolved_by
                    metadata["resolved_at"] = datetime.utcnow().isoformat()
                    alert.alert_metadata = json.dumps(metadata)
                
                session.commit()
                logger.info(f"Resolved system alert: {alert_id}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error resolving alert {alert_id}: {e}")
                raise
    
    async def cleanup_old_metadata(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old metadata beyond the retention period.
        
        Args:
            days_to_keep: Number of days of metadata to retain
            
        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        cleanup_stats = {}
        
        with self.connection.get_session() as session:
            try:
                # Clean up execution history
                deleted_executions = session.query(ExecutionHistoryModel).filter(
                    ExecutionHistoryModel.created_at < cutoff_date
                ).delete()
                cleanup_stats["execution_history"] = deleted_executions
                
                # Clean up performance metrics
                deleted_metrics = session.query(PerformanceMetricsModel).filter(
                    PerformanceMetricsModel.created_at < cutoff_date
                ).delete()
                cleanup_stats["performance_metrics"] = deleted_metrics
                
                # Clean up resolved system alerts
                deleted_alerts = session.query(SystemAlertsModel).filter(
                    and_(
                        SystemAlertsModel.created_at < cutoff_date,
                        SystemAlertsModel.resolved == True
                    )
                ).delete()
                cleanup_stats["system_alerts"] = deleted_alerts
                
                session.commit()
                logger.info(f"Cleaned up old metadata: {cleanup_stats}")
                
                return cleanup_stats
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error cleaning up metadata: {e}")
                raise
    
    async def get_all_pools(self, limit: Optional[int] = None) -> List:
        """
        Get all pools from the database.
        
        Args:
            limit: Optional limit on number of pools to return
            
        Returns:
            List of Pool objects
        """
        try:
            # Use the parent class method to get pools
            # This is a simplified implementation - in practice you'd want to implement
            # a more efficient method in the base class
            pools = []
            
            # Get all DEXes first
            dexes = await self.get_dexes_by_network("solana")  # Assuming solana network
            
            for dex in dexes:
                dex_pools = await self.get_pools_by_dex(dex.id)
                pools.extend(dex_pools)
                
                if limit and len(pools) >= limit:
                    pools = pools[:limit]
                    break
            
            return pools
            
        except Exception as e:
            logger.error(f"Error getting all pools: {e}")
            return []
    
    async def get_pool_by_address(self, address: str):
        """
        Get pool by address.
        
        Args:
            address: Pool address to search for
            
        Returns:
            Pool object if found, None otherwise
        """
        try:
            with self.connection.get_session() as session:
                from gecko_terminal_collector.database.models import PoolModel
                
                pool_model = session.query(PoolModel).filter_by(address=address).first()
                if pool_model:
                    # Convert to Pool object
                    from gecko_terminal_collector.models.core import Pool
                    return Pool(
                        id=pool_model.id,
                        address=pool_model.address,
                        name=pool_model.name,
                        dex_id=pool_model.dex_id,
                        base_token_id=pool_model.base_token_id,
                        quote_token_id=pool_model.quote_token_id,
                        reserve_usd=pool_model.reserve_usd,
                        created_at=pool_model.created_at
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting pool by address {address}: {e}")
            return None
    
    async def search_pools_by_name_or_id(self, search_term: str, limit: int = 10) -> List:
        """
        Search pools by name or ID.
        
        Args:
            search_term: Term to search for
            limit: Maximum number of results to return
            
        Returns:
            List of Pool objects matching the search term
        """
        try:
            with self.connection.get_session() as session:
                from gecko_terminal_collector.database.models import PoolModel
                from gecko_terminal_collector.models.core import Pool
                
                # Search by ID or name (case-insensitive)
                pool_models = session.query(PoolModel).filter(
                    (PoolModel.id.ilike(f"%{search_term}%")) |
                    (PoolModel.name.ilike(f"%{search_term}%"))
                ).limit(limit).all()
                
                pools = []
                for pool_model in pool_models:
                    pool = Pool(
                        id=pool_model.id,
                        address=pool_model.address,
                        name=pool_model.name,
                        dex_id=pool_model.dex_id,
                        base_token_id=pool_model.base_token_id,
                        quote_token_id=pool_model.quote_token_id,
                        reserve_usd=pool_model.reserve_usd,
                        created_at=pool_model.created_at
                    )
                    pools.append(pool)
                
                return pools
                
        except Exception as e:
            logger.error(f"Error searching pools by name or ID '{search_term}': {e}")
            return []