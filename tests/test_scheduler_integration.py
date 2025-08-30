"""
Integration tests for the collection scheduler with real collectors.
"""

import asyncio
import pytest
from unittest.mock import Mock

from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler, SchedulerConfig
from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker


@pytest.fixture
def config():
    """Create test configuration."""
    return CollectionConfig()


@pytest.fixture
def scheduler_config():
    """Create test scheduler configuration."""
    return SchedulerConfig(
        max_workers=3,
        shutdown_timeout=5,
        error_recovery_delay=0.1,
        max_consecutive_errors=2,
        health_check_interval=0.5
    )


@pytest.fixture
def db_manager():
    """Create mock database manager."""
    mock_db = Mock(spec=DatabaseManager)
    mock_db.initialize = Mock(return_value=asyncio.Future())
    mock_db.initialize.return_value.set_result(None)
    mock_db.close = Mock(return_value=asyncio.Future())
    mock_db.close.return_value.set_result(None)
    return mock_db


@pytest.fixture
def metadata_tracker():
    """Create test metadata tracker."""
    return MetadataTracker()


@pytest.fixture
def scheduler(config, scheduler_config, metadata_tracker):
    """Create test scheduler."""
    return CollectionScheduler(
        config=config,
        scheduler_config=scheduler_config,
        metadata_tracker=metadata_tracker
    )


class TestSchedulerIntegration:
    """Integration tests for scheduler with real collectors."""
    
    @pytest.mark.asyncio
    async def test_scheduler_with_dex_collector(self, scheduler, config, db_manager, metadata_tracker):
        """Test scheduler with DEX monitoring collector."""
        # Create DEX collector with mock client
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Register collector
        job_id = scheduler.register_collector(dex_collector, "1s")
        
        # Start scheduler
        await scheduler.start()
        
        # Let it run for a short time
        await asyncio.sleep(2.5)
        
        # Check that collector was executed
        collector_status = scheduler.get_collector_status(job_id)
        assert collector_status is not None
        assert collector_status['last_run'] is not None
        
        # Stop scheduler
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_with_multiple_collectors(self, scheduler, config, db_manager, metadata_tracker):
        """Test scheduler with multiple real collectors."""
        # Create collectors with mock clients
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        top_pools_collector = TopPoolsCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Register collectors with different intervals
        dex_job_id = scheduler.register_collector(dex_collector, "1s")
        pools_job_id = scheduler.register_collector(top_pools_collector, "2s")
        
        # Start scheduler
        await scheduler.start()
        
        # Let it run for a short time
        await asyncio.sleep(3)
        
        # Check that both collectors were executed
        dex_status = scheduler.get_collector_status(dex_job_id)
        pools_status = scheduler.get_collector_status(pools_job_id)
        
        assert dex_status is not None
        assert dex_status['last_run'] is not None
        assert pools_status is not None
        assert pools_status['last_run'] is not None
        
        # Check scheduler status
        status = scheduler.get_status()
        assert status['total_collectors'] == 2
        assert status['enabled_collectors'] == 2
        
        # Stop scheduler
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_error_handling_with_real_collector(self, scheduler, config, db_manager, metadata_tracker):
        """Test scheduler error handling with a real collector that might fail."""
        # Create collector with mock client
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Register collector
        job_id = scheduler.register_collector(dex_collector, "1s")
        
        # Start scheduler
        await scheduler.start()
        
        # Let it run briefly
        await asyncio.sleep(1.5)
        
        # Execute collector on demand to test error handling
        result = await scheduler.execute_collector_now(job_id)
        
        # Should succeed with mock client
        assert result.success is True
        # With mock client, records_collected might be a mock object
        assert result.records_collected is not None
        
        # Check collector status
        collector_status = scheduler.get_collector_status(job_id)
        assert collector_status['consecutive_errors'] == 0
        
        # Stop scheduler
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_configuration_intervals(self, config, scheduler_config, metadata_tracker, db_manager):
        """Test scheduler with configuration-based intervals."""
        # Use actual configuration intervals
        scheduler = CollectionScheduler(
            config=config,
            scheduler_config=scheduler_config,
            metadata_tracker=metadata_tracker
        )
        
        # Create collectors
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        top_pools_collector = TopPoolsCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Register with configuration intervals
        dex_job_id = scheduler.register_collector(
            dex_collector,
            interval=config.intervals.top_pools_monitoring  # "1h"
        )
        
        pools_job_id = scheduler.register_collector(
            top_pools_collector,
            interval=config.intervals.top_pools_monitoring  # "1h"
        )
        
        # Start scheduler
        await scheduler.start()
        
        # Check that jobs are scheduled
        next_runs = scheduler.get_next_run_times()
        assert next_runs[dex_job_id] is not None
        assert next_runs[pools_job_id] is not None
        
        # Execute collectors on demand since 1h interval is too long for test
        dex_result = await scheduler.execute_collector_now(dex_job_id)
        pools_result = await scheduler.execute_collector_now(pools_job_id)
        
        assert dex_result.success is True
        assert pools_result.success is True
        
        # Stop scheduler
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_registry_integration(self, scheduler, config, db_manager, metadata_tracker):
        """Test scheduler integration with collector registry."""
        # Create multiple collectors with different keys to avoid conflicts
        from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
        from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
        
        collectors = []
        job_ids = []
        
        # Create different types of collectors to avoid key conflicts
        collector_classes = [DEXMonitoringCollector, TopPoolsCollector, OHLCVCollector]
        
        for i, collector_class in enumerate(collector_classes):
            collector = collector_class(
                config=config,
                db_manager=db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=True
            )
            collectors.append(collector)
            
            job_id = scheduler.register_collector(collector, "1s")
            job_ids.append(job_id)
        
        # Check registry - should have 3 different collectors
        registry_summary = scheduler._collector_registry.get_registry_summary()
        assert registry_summary['total_collectors'] == 3
        
        # Start scheduler
        await scheduler.start()
        
        # Let it run briefly
        await asyncio.sleep(1.5)
        
        # Check health status
        health_status = scheduler._collector_registry.get_health_status()
        assert len(health_status) == 3
        
        # All collectors should be healthy with mock clients
        unhealthy = scheduler._collector_registry.get_unhealthy_collectors()
        assert len(unhealthy) == 0
        
        # Stop scheduler
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_full_lifecycle():
    """Test complete scheduler lifecycle with real components."""
    # Create configuration
    config = CollectionConfig()
    scheduler_config = SchedulerConfig(
        max_workers=2,
        shutdown_timeout=5,
        error_recovery_delay=0.1,
        health_check_interval=0.5
    )
    
    # Create components
    metadata_tracker = MetadataTracker()
    db_manager = Mock(spec=DatabaseManager)
    db_manager.initialize = Mock(return_value=asyncio.Future())
    db_manager.initialize.return_value.set_result(None)
    db_manager.close = Mock(return_value=asyncio.Future())
    db_manager.close.return_value.set_result(None)
    
    # Create scheduler
    scheduler = CollectionScheduler(
        config=config,
        scheduler_config=scheduler_config,
        metadata_tracker=metadata_tracker
    )
    
    # Create and register collectors
    dex_collector = DEXMonitoringCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=True
    )
    
    top_pools_collector = TopPoolsCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=True
    )
    
    dex_job_id = scheduler.register_collector(dex_collector, "1s")
    pools_job_id = scheduler.register_collector(top_pools_collector, "1s")
    
    try:
        # Start scheduler
        await scheduler.start()
        assert scheduler._state.value == "running"
        
        # Let it run
        await asyncio.sleep(2)
        
        # Check execution
        status = scheduler.get_status()
        assert status['total_collectors'] == 2
        assert status['enabled_collectors'] == 2
        
        # Test on-demand execution
        result = await scheduler.execute_collector_now(dex_job_id)
        assert result.success is True
        
        # Test collector management
        scheduler.disable_collector(pools_job_id)
        status = scheduler.get_status()
        assert status['enabled_collectors'] == 1
        
        scheduler.enable_collector(pools_job_id)
        status = scheduler.get_status()
        assert status['enabled_collectors'] == 2
        
    finally:
        # Stop scheduler
        await scheduler.stop()
        assert scheduler._state.value == "stopped"