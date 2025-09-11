"""
Statistics and monitoring engine for new pools collection.

This module provides comprehensive statistics collection, analysis, and reporting
for new pools collection activities with network and DEX distribution analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session

from gecko_terminal_collector.database.models import (
    NewPoolsHistory as NewPoolsHistoryModel,
    Pool as PoolModel,
    CollectionMetadata as CollectionMetadataModel,
    ExecutionHistory as ExecutionHistoryModel,
    SystemAlerts as SystemAlertsModel
)

logger = logging.getLogger(__name__)


@dataclass
class CollectionStatistics:
    """Container for collection statistics."""
    total_pools: int
    total_history_records: int
    network_distribution: Dict[str, int]
    dex_distribution: Dict[str, int]
    collection_activity: List[Dict[str, Any]]
    recent_records: List[Dict[str, Any]]
    error_summary: Dict[str, Any]
    rate_limiting_context: Dict[str, Any]


@dataclass
class NetworkStatistics:
    """Container for network-specific statistics."""
    network_id: str
    total_pools: int
    total_history_records: int
    dex_distribution: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    collection_timeline: List[Dict[str, Any]]


@dataclass
class ErrorContext:
    """Container for error reporting with rate limiting context."""
    error_count: int
    recent_errors: List[Dict[str, Any]]
    rate_limiting_errors: int
    validation_errors: int
    database_errors: int
    api_errors: int
    recovery_suggestions: List[str]


class StatisticsEngine:
    """
    Comprehensive statistics and monitoring engine for new pools collection.
    
    Provides database statistics collection, network and DEX distribution analysis,
    recent records retrieval with filtering, collection activity timeline tracking,
    and comprehensive error reporting with rate limiting context.
    """
    
    def __init__(self, db_manager):
        """
        Initialize statistics engine.
        
        Args:
            db_manager: Database manager instance for data access
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    async def get_comprehensive_statistics(
        self,
        network_filter: Optional[str] = None,
        limit: int = 10,
        hours_back: int = 24
    ) -> CollectionStatistics:
        """
        Get comprehensive statistics for new pools collection.
        
        Args:
            network_filter: Optional network to filter by
            limit: Number of recent records to retrieve
            hours_back: Hours to look back for activity timeline
        
        Returns:
            CollectionStatistics object with all statistics
        """
        self.logger.info(f"Collecting comprehensive statistics (network: {network_filter}, limit: {limit})")
        
        with self.db_manager.connection.get_session() as session:
            try:
                # Get basic counts
                total_pools = await self._get_total_pools_count(session, network_filter)
                total_history = await self._get_total_history_count(session, network_filter)
                
                # Get distribution analysis
                network_dist = await self._get_network_distribution(session, network_filter)
                dex_dist = await self._get_dex_distribution(session, network_filter)
                
                # Get collection activity timeline
                activity = await self._get_collection_activity(session, network_filter, hours_back)
                
                # Get recent records
                recent = await self._get_recent_records(session, network_filter, limit)
                
                # Get error summary
                error_summary = await self._get_error_summary(session, network_filter, hours_back)
                
                # Get rate limiting context
                rate_context = await self._get_rate_limiting_context(session, hours_back)
                
                return CollectionStatistics(
                    total_pools=total_pools,
                    total_history_records=total_history,
                    network_distribution=network_dist,
                    dex_distribution=dex_dist,
                    collection_activity=activity,
                    recent_records=recent,
                    error_summary=error_summary,
                    rate_limiting_context=rate_context
                )
                
            except Exception as e:
                self.logger.error(f"Error collecting comprehensive statistics: {e}")
                raise
    
    async def get_network_statistics(self, network_id: str, limit: int = 10) -> NetworkStatistics:
        """
        Get detailed statistics for a specific network.
        
        Args:
            network_id: Network identifier (e.g., 'solana', 'ethereum')
            limit: Number of recent records to retrieve
        
        Returns:
            NetworkStatistics object with network-specific data
        """
        self.logger.info(f"Collecting statistics for network: {network_id}")
        
        with self.db_manager.connection.get_session() as session:
            try:
                # Get network-specific counts
                total_pools = await self._get_total_pools_count(session, network_id)
                total_history = await self._get_total_history_count(session, network_id)
                
                # Get DEX distribution for this network
                dex_dist = await self._get_dex_distribution(session, network_id)
                
                # Get recent activity for this network
                recent_activity = await self._get_recent_records(session, network_id, limit)
                
                # Get collection timeline for this network
                timeline = await self._get_collection_activity(session, network_id, 24)
                
                return NetworkStatistics(
                    network_id=network_id,
                    total_pools=total_pools,
                    total_history_records=total_history,
                    dex_distribution=dex_dist,
                    recent_activity=recent_activity,
                    collection_timeline=timeline
                )
                
            except Exception as e:
                self.logger.error(f"Error collecting network statistics for {network_id}: {e}")
                raise
    
    async def get_error_analysis(
        self,
        network_filter: Optional[str] = None,
        hours_back: int = 24
    ) -> ErrorContext:
        """
        Get comprehensive error analysis with rate limiting context.
        
        Args:
            network_filter: Optional network to filter by
            hours_back: Hours to look back for error analysis
        
        Returns:
            ErrorContext object with error analysis and recovery suggestions
        """
        self.logger.info(f"Analyzing errors (network: {network_filter}, hours: {hours_back})")
        
        with self.db_manager.connection.get_session() as session:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
                
                # Get recent execution history with errors
                error_query = session.query(ExecutionHistoryModel).filter(
                    and_(
                        ExecutionHistoryModel.status.in_(['failure', 'partial']),
                        ExecutionHistoryModel.start_time >= cutoff_time
                    )
                )
                
                # Filter by network if specified
                if network_filter:
                    error_query = error_query.filter(
                        ExecutionHistoryModel.collector_type.like(f"%{network_filter}%")
                    )
                
                error_executions = error_query.order_by(desc(ExecutionHistoryModel.start_time)).all()
                
                # Categorize errors
                rate_limiting_errors = 0
                validation_errors = 0
                database_errors = 0
                api_errors = 0
                recent_errors = []
                
                for execution in error_executions[:20]:  # Limit to recent 20 errors
                    error_msg = execution.error_message or ""
                    error_lower = error_msg.lower()
                    
                    # Categorize error types
                    if "rate limit" in error_lower or "429" in error_lower:
                        rate_limiting_errors += 1
                        error_type = "Rate Limiting"
                    elif "validation" in error_lower or "invalid" in error_lower:
                        validation_errors += 1
                        error_type = "Validation"
                    elif "database" in error_lower or "sql" in error_lower or "connection" in error_lower:
                        database_errors += 1
                        error_type = "Database"
                    else:
                        api_errors += 1
                        error_type = "API"
                    
                    recent_errors.append({
                        'timestamp': execution.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'collector_type': execution.collector_type,
                        'error_type': error_type,
                        'error_message': error_msg[:200] + "..." if len(error_msg) > 200 else error_msg,
                        'execution_time': float(execution.execution_time) if execution.execution_time else None,
                        'records_collected': execution.records_collected
                    })
                
                # Generate recovery suggestions
                recovery_suggestions = self._generate_recovery_suggestions(
                    rate_limiting_errors, validation_errors, database_errors, api_errors
                )
                
                return ErrorContext(
                    error_count=len(error_executions),
                    recent_errors=recent_errors,
                    rate_limiting_errors=rate_limiting_errors,
                    validation_errors=validation_errors,
                    database_errors=database_errors,
                    api_errors=api_errors,
                    recovery_suggestions=recovery_suggestions
                )
                
            except Exception as e:
                self.logger.error(f"Error analyzing errors: {e}")
                raise
    
    async def _get_total_pools_count(self, session: Session, network_filter: Optional[str]) -> int:
        """Get total pools count with optional network filtering."""
        query = session.query(func.count(PoolModel.id))
        
        if network_filter:
            # Filter pools by network (assuming pool IDs contain network prefix)
            query = query.filter(PoolModel.id.like(f"{network_filter}_%"))
        
        return query.scalar() or 0
    
    async def _get_total_history_count(self, session: Session, network_filter: Optional[str]) -> int:
        """Get total history records count with optional network filtering."""
        query = session.query(func.count(NewPoolsHistoryModel.id))
        
        if network_filter:
            query = query.filter(NewPoolsHistoryModel.network_id == network_filter)
        
        return query.scalar() or 0
    
    async def _get_network_distribution(
        self,
        session: Session,
        network_filter: Optional[str]
    ) -> Dict[str, int]:
        """Get network distribution analysis."""
        query = session.query(
            NewPoolsHistoryModel.network_id,
            func.count(NewPoolsHistoryModel.id).label('count')
        ).group_by(NewPoolsHistoryModel.network_id)
        
        if network_filter:
            query = query.filter(NewPoolsHistoryModel.network_id == network_filter)
        
        distribution = {}
        for network_name, count in query.all():
            if network_name:  # Skip null network names
                distribution[network_name] = count
        
        return distribution
    
    async def _get_dex_distribution(
        self,
        session: Session,
        network_filter: Optional[str]
    ) -> Dict[str, int]:
        """Get DEX distribution analysis."""
        query = session.query(
            NewPoolsHistoryModel.dex_id,
            func.count(NewPoolsHistoryModel.id).label('count')
        ).group_by(NewPoolsHistoryModel.dex_id)
        
        if network_filter:
            query = query.filter(NewPoolsHistoryModel.network_id == network_filter)
        
        distribution = {}
        for dex_name, count in query.all():
            if dex_name:  # Skip null DEX names
                distribution[dex_name] = count
        
        return distribution
    
    async def _get_collection_activity(
        self,
        session: Session,
        network_filter: Optional[str],
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Get collection activity timeline for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Group by hour for activity timeline
        activity_query = session.query(
            func.strftime('%Y-%m-%d %H:00', NewPoolsHistoryModel.collected_at).label('hour'),
            func.count(NewPoolsHistoryModel.id).label('records'),
            func.count(func.distinct(NewPoolsHistoryModel.pool_id)).label('unique_pools'),
            func.avg(NewPoolsHistoryModel.reserve_in_usd).label('avg_reserve_usd'),
            func.sum(NewPoolsHistoryModel.volume_usd_h24).label('total_volume_h24')
        ).filter(
            NewPoolsHistoryModel.collected_at >= cutoff_time
        ).group_by(
            func.strftime('%Y-%m-%d %H:00', NewPoolsHistoryModel.collected_at)
        ).order_by('hour')
        
        if network_filter:
            activity_query = activity_query.filter(NewPoolsHistoryModel.network_id == network_filter)
        
        activity = []
        for hour, records, unique_pools, avg_reserve, total_volume in activity_query.all():
            activity.append({
                'hour': hour,
                'records': records,
                'unique_pools': unique_pools,
                'avg_reserve_usd': float(avg_reserve) if avg_reserve else None,
                'total_volume_h24': float(total_volume) if total_volume else None
            })
        
        return activity
    
    async def _get_recent_records(
        self,
        session: Session,
        network_filter: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get recent records with comprehensive information and formatting."""
        query = session.query(NewPoolsHistoryModel).order_by(desc(NewPoolsHistoryModel.collected_at))
        
        if network_filter:
            query = query.filter(NewPoolsHistoryModel.network_id == network_filter)
        
        query = query.limit(limit)
        
        recent_records = []
        for record in query.all():
            recent_records.append({
                'pool_id': record.pool_id,
                'name': record.name,
                'address': record.address,
                'network_id': record.network_id,
                'dex_id': record.dex_id,
                'reserve_in_usd': float(record.reserve_in_usd) if record.reserve_in_usd else None,
                'volume_usd_h24': float(record.volume_usd_h24) if record.volume_usd_h24 else None,
                'price_change_percentage_h1': float(record.price_change_percentage_h1) if record.price_change_percentage_h1 else None,
                'price_change_percentage_h24': float(record.price_change_percentage_h24) if record.price_change_percentage_h24 else None,
                'transactions_h24_buys': record.transactions_h24_buys,
                'transactions_h24_sells': record.transactions_h24_sells,
                'pool_created_at': record.pool_created_at.strftime('%Y-%m-%d %H:%M:%S') if record.pool_created_at else None,
                'collected_at': record.collected_at.strftime('%Y-%m-%d %H:%M:%S') if record.collected_at else None,
                'fdv_usd': float(record.fdv_usd) if record.fdv_usd else None,
                'market_cap_usd': float(record.market_cap_usd) if record.market_cap_usd else None,
                'base_token_price_usd': float(record.base_token_price_usd) if record.base_token_price_usd else None,
                'quote_token_price_usd': float(record.quote_token_price_usd) if record.quote_token_price_usd else None
            })
        
        return recent_records
    
    async def _get_error_summary(
        self,
        session: Session,
        network_filter: Optional[str],
        hours_back: int
    ) -> Dict[str, Any]:
        """Get error summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Get execution history for new pools collectors
        error_query = session.query(ExecutionHistoryModel).filter(
            and_(
                ExecutionHistoryModel.collector_type.like('%new_pools%'),
                ExecutionHistoryModel.start_time >= cutoff_time
            )
        )
        
        if network_filter:
            error_query = error_query.filter(
                ExecutionHistoryModel.collector_type.like(f"%{network_filter}%")
            )
        
        executions = error_query.all()
        
        total_executions = len(executions)
        failed_executions = len([e for e in executions if e.status == 'failure'])
        partial_executions = len([e for e in executions if e.status == 'partial'])
        successful_executions = len([e for e in executions if e.status == 'success'])
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'partial_executions': partial_executions,
            'success_rate': round(success_rate, 2),
            'time_period_hours': hours_back
        }
    
    async def _get_rate_limiting_context(
        self,
        session: Session,
        hours_back: int
    ) -> Dict[str, Any]:
        """Get rate limiting context from recent executions."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Look for rate limiting related errors in execution history
        rate_limit_query = session.query(ExecutionHistoryModel).filter(
            and_(
                ExecutionHistoryModel.start_time >= cutoff_time,
                ExecutionHistoryModel.error_message.like('%rate limit%')
            )
        )
        
        rate_limit_errors = rate_limit_query.all()
        
        # Get system alerts related to rate limiting
        alert_query = session.query(SystemAlertsModel).filter(
            and_(
                SystemAlertsModel.timestamp >= cutoff_time,
                SystemAlertsModel.message.like('%rate%')
            )
        )
        
        rate_limit_alerts = alert_query.all()
        
        return {
            'rate_limit_errors_count': len(rate_limit_errors),
            'rate_limit_alerts_count': len(rate_limit_alerts),
            'recent_rate_limit_errors': [
                {
                    'timestamp': error.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'collector_type': error.collector_type,
                    'error_message': error.error_message[:100] + "..." if len(error.error_message) > 100 else error.error_message
                }
                for error in rate_limit_errors[:5]  # Last 5 rate limit errors
            ]
        }
    
    def _generate_recovery_suggestions(
        self,
        rate_limiting_errors: int,
        validation_errors: int,
        database_errors: int,
        api_errors: int
    ) -> List[str]:
        """Generate recovery suggestions based on error patterns."""
        suggestions = []
        
        if rate_limiting_errors > 0:
            suggestions.extend([
                "Check rate limiter status with 'rate-limit-status' command",
                "Consider increasing intervals between collection runs",
                "Reset rate limiters if needed with 'reset-rate-limiter' command",
                "Monitor daily API usage to stay within limits"
            ])
        
        if validation_errors > 0:
            suggestions.extend([
                "Review data validation rules for new pools collection",
                "Check API response format changes from GeckoTerminal",
                "Verify network configuration in config.yaml"
            ])
        
        if database_errors > 0:
            suggestions.extend([
                "Check database connection and disk space",
                "Review database schema migrations",
                "Consider database maintenance and optimization"
            ])
        
        if api_errors > 0:
            suggestions.extend([
                "Check GeckoTerminal API status and availability",
                "Verify network connectivity and DNS resolution",
                "Review API authentication and credentials"
            ])
        
        if not suggestions:
            suggestions.append("No specific issues detected. System appears healthy.")
        
        return suggestions
    
    async def get_collection_performance_metrics(
        self,
        network_filter: Optional[str] = None,
        hours_back: int = 24
    ) -> Dict[str, Any]:
        """
        Get performance metrics for collection operations.
        
        Args:
            network_filter: Optional network to filter by
            hours_back: Hours to look back for metrics
        
        Returns:
            Dictionary containing performance metrics
        """
        with self.db_manager.connection.get_session() as session:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
                
                # Get execution performance metrics
                perf_query = session.query(ExecutionHistoryModel).filter(
                    and_(
                        ExecutionHistoryModel.collector_type.like('%new_pools%'),
                        ExecutionHistoryModel.start_time >= cutoff_time,
                        ExecutionHistoryModel.execution_time.isnot(None)
                    )
                )
                
                if network_filter:
                    perf_query = perf_query.filter(
                        ExecutionHistoryModel.collector_type.like(f"%{network_filter}%")
                    )
                
                executions = perf_query.all()
                
                if not executions:
                    return {
                        'total_executions': 0,
                        'avg_execution_time': 0,
                        'min_execution_time': 0,
                        'max_execution_time': 0,
                        'total_records_collected': 0,
                        'avg_records_per_execution': 0,
                        'records_per_second': 0
                    }
                
                execution_times = [float(e.execution_time) for e in executions if e.execution_time]
                records_collected = [e.records_collected for e in executions if e.records_collected]
                
                total_records = sum(records_collected)
                total_time = sum(execution_times)
                
                return {
                    'total_executions': len(executions),
                    'avg_execution_time': round(sum(execution_times) / len(execution_times), 2) if execution_times else 0,
                    'min_execution_time': round(min(execution_times), 2) if execution_times else 0,
                    'max_execution_time': round(max(execution_times), 2) if execution_times else 0,
                    'total_records_collected': total_records,
                    'avg_records_per_execution': round(total_records / len(executions), 2) if executions else 0,
                    'records_per_second': round(total_records / total_time, 2) if total_time > 0 else 0,
                    'time_period_hours': hours_back
                }
                
            except Exception as e:
                self.logger.error(f"Error collecting performance metrics: {e}")
                raise