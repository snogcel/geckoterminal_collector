"""
Database health monitoring and alerting system.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DatabaseHealthMetrics:
    """Database health metrics data structure."""
    timestamp: datetime
    connection_pool_size: int
    active_connections: int
    circuit_breaker_state: str
    circuit_breaker_failures: int
    wal_mode_enabled: bool
    lock_wait_time_ms: float
    query_performance_ms: float
    error_rate: float
    availability: float


class DatabaseHealthMonitor:
    """
    Monitors database health and provides alerting for performance issues.
    """
    
    def __init__(self, db_manager, alert_thresholds: Optional[Dict] = None):
        """
        Initialize database health monitor.
        
        Args:
            db_manager: Database manager instance to monitor
            alert_thresholds: Custom alert thresholds
        """
        self.db_manager = db_manager
        self.metrics_history: List[DatabaseHealthMetrics] = []
        self.max_history_size = 1000
        
        # Default alert thresholds
        self.thresholds = {
            'lock_wait_time_ms': 1000,  # 1 second
            'query_performance_ms': 500,  # 500ms
            'error_rate': 0.1,  # 10%
            'availability': 0.95,  # 95%
            'circuit_breaker_failures': 3
        }
        
        if alert_thresholds:
            self.thresholds.update(alert_thresholds)
        
        self.monitoring_active = False
        self.monitoring_task = None
    
    async def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous database health monitoring."""
        if self.monitoring_active:
            logger.warning("Database monitoring is already active")
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        logger.info(f"Started database health monitoring (interval: {interval_seconds}s)")
    
    async def stop_monitoring(self):
        """Stop database health monitoring."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped database health monitoring")
    
    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                metrics = await self.collect_health_metrics()
                self._store_metrics(metrics)
                await self._check_alerts(metrics)
                
            except Exception as e:
                logger.error(f"Error in database health monitoring: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    async def collect_health_metrics(self) -> DatabaseHealthMetrics:
        """Collect comprehensive database health metrics."""
        start_time = time.time()
        
        try:
            # Get basic health metrics from database manager
            if hasattr(self.db_manager, 'get_database_health_metrics'):
                basic_metrics = await self.db_manager.get_database_health_metrics()
            else:
                basic_metrics = {}
            
            # Test connectivity and measure performance
            connectivity_start = time.time()
            is_connected = await self._test_connectivity()
            query_performance_ms = (time.time() - connectivity_start) * 1000
            
            # Calculate error rate from recent history
            error_rate = self._calculate_error_rate()
            
            # Calculate availability from recent history
            availability = self._calculate_availability()
            
            metrics = DatabaseHealthMetrics(
                timestamp=datetime.now(),
                connection_pool_size=basic_metrics.get('connection_pool_size', 0),
                active_connections=basic_metrics.get('active_connections', 0),
                circuit_breaker_state=basic_metrics.get('circuit_breaker_state', 'UNKNOWN'),
                circuit_breaker_failures=basic_metrics.get('circuit_breaker_failures', 0),
                wal_mode_enabled=basic_metrics.get('wal_mode_enabled', False),
                lock_wait_time_ms=basic_metrics.get('lock_wait_time_ms', 0),
                query_performance_ms=query_performance_ms,
                error_rate=error_rate,
                availability=availability
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting database health metrics: {e}")
            # Return minimal metrics with error indication
            return DatabaseHealthMetrics(
                timestamp=datetime.now(),
                connection_pool_size=0,
                active_connections=0,
                circuit_breaker_state='ERROR',
                circuit_breaker_failures=999,
                wal_mode_enabled=False,
                lock_wait_time_ms=999999,
                query_performance_ms=999999,
                error_rate=1.0,
                availability=0.0
            )
    
    async def _test_connectivity(self) -> bool:
        """Test database connectivity."""
        try:
            if hasattr(self.db_manager, 'test_database_connectivity'):
                return await self.db_manager.test_database_connectivity()
            else:
                # Fallback connectivity test
                return await self._basic_connectivity_test()
        except Exception as e:
            logger.warning(f"Database connectivity test failed: {e}")
            return False
    
    async def _basic_connectivity_test(self) -> bool:
        """Basic connectivity test fallback."""
        try:
            # Try to get a simple count from a table
            count = await self.db_manager.count_records('pools')
            return count >= 0
        except Exception:
            return False
    
    def _store_metrics(self, metrics: DatabaseHealthMetrics):
        """Store metrics in history buffer."""
        self.metrics_history.append(metrics)
        
        # Trim history to max size
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    def _calculate_error_rate(self, window_minutes: int = 10) -> float:
        """Calculate error rate over recent time window."""
        if not self.metrics_history:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return 0.0
        
        error_count = sum(
            1 for m in recent_metrics 
            if m.circuit_breaker_state == 'OPEN' or m.availability < 0.5
        )
        
        return error_count / len(recent_metrics)
    
    def _calculate_availability(self, window_minutes: int = 30) -> float:
        """Calculate availability over recent time window."""
        if not self.metrics_history:
            return 1.0
        
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return 1.0
        
        available_count = sum(
            1 for m in recent_metrics 
            if m.circuit_breaker_state in ['CLOSED', 'HALF_OPEN'] and m.query_performance_ms < 10000
        )
        
        return available_count / len(recent_metrics)
    
    async def _check_alerts(self, metrics: DatabaseHealthMetrics):
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        
        # Check lock wait time
        if metrics.lock_wait_time_ms > self.thresholds['lock_wait_time_ms']:
            alerts.append({
                'level': 'WARNING',
                'type': 'HIGH_LOCK_WAIT_TIME',
                'message': f"High database lock wait time: {metrics.lock_wait_time_ms:.1f}ms",
                'threshold': self.thresholds['lock_wait_time_ms'],
                'actual': metrics.lock_wait_time_ms
            })
        
        # Check query performance
        if metrics.query_performance_ms > self.thresholds['query_performance_ms']:
            alerts.append({
                'level': 'WARNING',
                'type': 'SLOW_QUERY_PERFORMANCE',
                'message': f"Slow database query performance: {metrics.query_performance_ms:.1f}ms",
                'threshold': self.thresholds['query_performance_ms'],
                'actual': metrics.query_performance_ms
            })
        
        # Check error rate
        if metrics.error_rate > self.thresholds['error_rate']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'HIGH_ERROR_RATE',
                'message': f"High database error rate: {metrics.error_rate:.1%}",
                'threshold': self.thresholds['error_rate'],
                'actual': metrics.error_rate
            })
        
        # Check availability
        if metrics.availability < self.thresholds['availability']:
            alerts.append({
                'level': 'CRITICAL',
                'type': 'LOW_AVAILABILITY',
                'message': f"Low database availability: {metrics.availability:.1%}",
                'threshold': self.thresholds['availability'],
                'actual': metrics.availability
            })
        
        # Check circuit breaker state
        if metrics.circuit_breaker_state == 'OPEN':
            alerts.append({
                'level': 'CRITICAL',
                'type': 'CIRCUIT_BREAKER_OPEN',
                'message': f"Database circuit breaker is OPEN after {metrics.circuit_breaker_failures} failures",
                'threshold': self.thresholds['circuit_breaker_failures'],
                'actual': metrics.circuit_breaker_failures
            })
        
        # Check WAL mode
        if not metrics.wal_mode_enabled and 'sqlite' in str(getattr(self.db_manager, 'engine', '')):
            alerts.append({
                'level': 'INFO',
                'type': 'WAL_MODE_DISABLED',
                'message': "SQLite WAL mode is not enabled, consider enabling for better concurrency",
                'threshold': True,
                'actual': False
            })
        
        # Log alerts
        for alert in alerts:
            if alert['level'] == 'CRITICAL':
                logger.critical(f"Database Alert: {alert['message']}")
            elif alert['level'] == 'WARNING':
                logger.warning(f"Database Alert: {alert['message']}")
            else:
                logger.info(f"Database Alert: {alert['message']}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get current database health summary."""
        if not self.metrics_history:
            return {'status': 'NO_DATA', 'message': 'No metrics available'}
        
        latest = self.metrics_history[-1]
        
        # Determine overall health status
        if latest.circuit_breaker_state == 'OPEN':
            status = 'CRITICAL'
            message = 'Database circuit breaker is OPEN'
        elif latest.availability < 0.9:
            status = 'WARNING'
            message = f'Low availability: {latest.availability:.1%}'
        elif latest.error_rate > 0.05:
            status = 'WARNING'
            message = f'High error rate: {latest.error_rate:.1%}'
        elif latest.query_performance_ms > 1000:
            status = 'WARNING'
            message = f'Slow performance: {latest.query_performance_ms:.1f}ms'
        else:
            status = 'HEALTHY'
            message = 'Database is operating normally'
        
        return {
            'status': status,
            'message': message,
            'timestamp': latest.timestamp.isoformat(),
            'metrics': {
                'circuit_breaker_state': latest.circuit_breaker_state,
                'query_performance_ms': latest.query_performance_ms,
                'availability': latest.availability,
                'error_rate': latest.error_rate,
                'wal_mode_enabled': latest.wal_mode_enabled
            }
        }
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        return [
            {
                'timestamp': m.timestamp.isoformat(),
                'circuit_breaker_state': m.circuit_breaker_state,
                'query_performance_ms': m.query_performance_ms,
                'lock_wait_time_ms': m.lock_wait_time_ms,
                'availability': m.availability,
                'error_rate': m.error_rate,
                'wal_mode_enabled': m.wal_mode_enabled
            }
            for m in recent_metrics
        ]