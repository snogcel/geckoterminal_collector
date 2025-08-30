"""
Tests for the collection scheduler.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from gecko_terminal_collector.scheduling.scheduler import (
    CollectionScheduler,
    SchedulerConfig,
    ScheduledCollector,
    SchedulerState
)
from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.utils.metadata import MetadataTracker


class MockCollector(BaseDataCollector):
    """Mock collector for testing."""
    
    def __init__(self, key: str, success: bool = True, records: int = 10):
        # Mock the required dependencies
        config = Mock()
        config.error_handling = Mock()
        config.error_handling.max_retries = 3
        config.error_handling.backoff_factor = 2.0
        config.api = Mock()
        
        db_manager = Mock()
        super().__init__(config, db_manager, use_mock=True)
        
        self.key = key
        self.success = success
        self.records = records
        self.collect_called = 0
    
    async def collect(self) -> CollectionResult:
        """Mock collect method."""
        self.collect_called += 1
        
        if self.success:
            return CollectionResult(
                success=True,
                records_collected=self.records,
                errors=[],
                collection_time=datetime.now(),
                collector_type=self.key
            )
        else:
            return CollectionResult(
                success=False,
                records_collected=0,
                errors=["Mock error"],
                collection_time=datetime.now(),
                collector_type=self.key
            )
    
    def get_collection_key(self) -> str:
        """Return the collector key."""
        return self.key


@pytest.fixture
def collection_config():
    """Create a test collection configuration."""
    return CollectionConfig()


@pytest.fixture
def scheduler_config():
    """Create a test scheduler configuration."""
    return SchedulerConfig(
        max_workers=5,
        shutdown_timeout=10,
        error_recovery_delay=1,  # Short delay for testing
        max_consecutive_errors=3,
        health_check_interval=1  # Short interval for testing
    )


@pytest.fixture
def metadata_tracker():
    """Create a test metadata tracker."""
    return MetadataTracker()


@pytest.fixture
def scheduler(collection_config, scheduler_config, metadata_tracker):
    """Create a test scheduler."""
    return CollectionScheduler(
        config=collection_config,
        scheduler_config=scheduler_config,
        metadata_tracker=metadata_tracker
    )


@pytest.fixture
def mock_collector():
    """Create a mock collector."""
    return MockCollector("test_collector")


class TestCollectionScheduler:
    """Test cases for CollectionScheduler."""
    
    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler._state == SchedulerState.STOPPED
        assert len(scheduler._scheduled_collectors) == 0
        assert scheduler._scheduler is not None
        assert scheduler._collector_registry is not None
    
    def test_register_collector(self, scheduler, mock_collector):
        """Test collector registration."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        assert job_id == "collector_test_collector"
        assert job_id in scheduler._scheduled_collectors
        
        scheduled_collector = scheduler._scheduled_collectors[job_id]
        assert scheduled_collector.collector == mock_collector
        assert scheduled_collector.interval == "1h"
        assert scheduled_collector.enabled is True
    
    def test_register_collector_with_options(self, scheduler, mock_collector):
        """Test collector registration with custom options."""
        job_id = scheduler.register_collector(
            mock_collector,
            "30m",
            enabled=False,
            max_instances=2,
            coalesce=False
        )
        
        scheduled_collector = scheduler._scheduled_collectors[job_id]
        assert scheduled_collector.interval == "30m"
        assert scheduled_collector.enabled is False
        assert scheduled_collector.max_instances == 2
        assert scheduled_collector.coalesce is False
    
    def test_unregister_collector(self, scheduler, mock_collector):
        """Test collector unregistration."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        assert job_id in scheduler._scheduled_collectors
        
        result = scheduler.unregister_collector(job_id)
        assert result is True
        assert job_id not in scheduler._scheduled_collectors
        
        # Test unregistering non-existent collector
        result = scheduler.unregister_collector("non_existent")
        assert result is False
    
    def test_enable_disable_collector(self, scheduler, mock_collector):
        """Test enabling and disabling collectors."""
        job_id = scheduler.register_collector(mock_collector, "1h", enabled=False)
        
        # Test enabling
        result = scheduler.enable_collector(job_id)
        assert result is True
        assert scheduler._scheduled_collectors[job_id].enabled is True
        
        # Test disabling
        result = scheduler.disable_collector(job_id)
        assert result is True
        assert scheduler._scheduled_collectors[job_id].enabled is False
        
        # Test with non-existent collector
        assert scheduler.enable_collector("non_existent") is False
        assert scheduler.disable_collector("non_existent") is False
    
    def test_create_trigger_intervals(self, scheduler):
        """Test trigger creation for different intervals."""
        # Test minutes
        trigger = scheduler._create_trigger("30m")
        assert trigger.interval == timedelta(minutes=30)
        
        # Test hours
        trigger = scheduler._create_trigger("2h")
        assert trigger.interval == timedelta(hours=2)
        
        # Test days
        trigger = scheduler._create_trigger("1d")
        assert trigger.interval == timedelta(days=1)
        
        # Test seconds
        trigger = scheduler._create_trigger("45s")
        assert trigger.interval == timedelta(seconds=45)
    
    def test_create_trigger_invalid_format(self, scheduler):
        """Test trigger creation with invalid formats."""
        with pytest.raises(ValueError, match="Invalid interval format"):
            scheduler._create_trigger("")
        
        with pytest.raises(ValueError, match="Invalid interval format"):
            scheduler._create_trigger("abc")
        
        with pytest.raises(ValueError, match="Unsupported interval unit"):
            scheduler._create_trigger("1x")
        
        with pytest.raises(ValueError, match="Unsupported interval unit"):
            scheduler._create_trigger("1w")
    
    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self, scheduler, mock_collector):
        """Test scheduler startup and shutdown."""
        # Register a collector
        scheduler.register_collector(mock_collector, "1h")
        
        # Start scheduler
        await scheduler.start()
        assert scheduler._state == SchedulerState.RUNNING
        assert scheduler._scheduler.running is True
        
        # Stop scheduler
        await scheduler.stop()
        assert scheduler._state == SchedulerState.STOPPED
        assert scheduler._scheduler.running is False
    
    @pytest.mark.asyncio
    async def test_execute_collector_success(self, scheduler, mock_collector):
        """Test successful collector execution."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        await scheduler._execute_collector(job_id)
        
        assert mock_collector.collect_called == 1
    
    @pytest.mark.asyncio
    async def test_execute_collector_failure(self, scheduler):
        """Test collector execution failure."""
        failing_collector = MockCollector("failing_collector", success=False)
        job_id = scheduler.register_collector(failing_collector, "1h")
        
        with pytest.raises(Exception, match="Collection failed"):
            await scheduler._execute_collector(job_id)
        
        assert failing_collector.collect_called == 1
    
    @pytest.mark.asyncio
    async def test_execute_collector_now(self, scheduler, mock_collector):
        """Test on-demand collector execution."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        result = await scheduler.execute_collector_now(job_id)
        
        assert result.success is True
        assert result.records_collected == 10
        assert mock_collector.collect_called == 1
        
        # Check metadata was updated
        scheduled_collector = scheduler._scheduled_collectors[job_id]
        assert scheduled_collector.last_run is not None
        assert scheduled_collector.last_success is not None
        assert scheduled_collector.consecutive_errors == 0
    
    @pytest.mark.asyncio
    async def test_execute_collector_now_failure(self, scheduler):
        """Test on-demand collector execution with failure."""
        failing_collector = MockCollector("failing_collector", success=False)
        job_id = scheduler.register_collector(failing_collector, "1h")
        
        result = await scheduler.execute_collector_now(job_id)
        
        assert result.success is False
        assert len(result.errors) > 0
        
        # Check error metadata was updated
        scheduled_collector = scheduler._scheduled_collectors[job_id]
        assert scheduled_collector.error_count == 1
        assert scheduled_collector.consecutive_errors == 1
    
    @pytest.mark.asyncio
    async def test_execute_collector_now_invalid_job(self, scheduler):
        """Test on-demand execution with invalid job ID."""
        with pytest.raises(ValueError, match="Unknown job ID"):
            await scheduler.execute_collector_now("non_existent")
    
    def test_get_status(self, scheduler, mock_collector):
        """Test scheduler status retrieval."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        status = scheduler.get_status()
        
        assert status["state"] == SchedulerState.STOPPED.value
        assert status["total_collectors"] == 1
        assert status["enabled_collectors"] == 1
        assert job_id in status["collectors"]
        
        collector_status = status["collectors"][job_id]
        assert collector_status["collector_key"] == "test_collector"
        assert collector_status["interval"] == "1h"
        assert collector_status["enabled"] is True
    
    def test_get_collector_status(self, scheduler, mock_collector):
        """Test individual collector status retrieval."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        status = scheduler.get_collector_status(job_id)
        
        assert status is not None
        assert status["job_id"] == job_id
        assert status["collector_key"] == "test_collector"
        assert status["interval"] == "1h"
        assert status["enabled"] is True
        
        # Test non-existent collector
        assert scheduler.get_collector_status("non_existent") is None
    
    def test_list_collectors(self, scheduler, mock_collector):
        """Test listing collectors."""
        assert scheduler.list_collectors() == []
        
        job_id1 = scheduler.register_collector(mock_collector, "1h")
        mock_collector2 = MockCollector("test_collector_2")
        job_id2 = scheduler.register_collector(mock_collector2, "30m")
        
        collectors = scheduler.list_collectors()
        assert len(collectors) == 2
        assert job_id1 in collectors
        assert job_id2 in collectors
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, scheduler):
        """Test error recovery mechanism."""
        # Create a collector that will fail initially
        failing_collector = MockCollector("failing_collector", success=False)
        job_id = scheduler.register_collector(failing_collector, "1h")
        
        # Start the scheduler so error recovery can work properly
        await scheduler.start()
        
        # Simulate consecutive errors
        scheduled_collector = scheduler._scheduled_collectors[job_id]
        scheduled_collector.consecutive_errors = scheduler.scheduler_config.max_consecutive_errors
        
        # Start error recovery
        await scheduler._handle_collector_error_recovery(job_id)
        
        # Collector should be re-enabled with reset error count
        assert scheduled_collector.enabled is True
        assert scheduled_collector.consecutive_errors == 0
        
        # Stop the scheduler
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_with_real_intervals(self, scheduler, mock_collector):
        """Test scheduler with actual time intervals (short test)."""
        # Register collector with very short interval for testing
        job_id = scheduler.register_collector(mock_collector, "1s")
        
        # Start scheduler
        await scheduler.start()
        
        # Wait for a couple of executions
        await asyncio.sleep(2.5)
        
        # Stop scheduler
        await scheduler.stop()
        
        # Collector should have been called multiple times
        assert mock_collector.collect_called >= 2
    
    def test_scheduled_collector_dataclass(self):
        """Test ScheduledCollector dataclass."""
        mock_collector = MockCollector("test")
        
        scheduled = ScheduledCollector(
            collector=mock_collector,
            interval="1h",
            enabled=True,
            max_instances=2
        )
        
        assert scheduled.collector == mock_collector
        assert scheduled.interval == "1h"
        assert scheduled.enabled is True
        assert scheduled.max_instances == 2
        assert scheduled.coalesce is True  # default
        assert scheduled.job_id is None  # default
        assert scheduled.error_count == 0  # default
    
    def test_scheduler_config_dataclass(self):
        """Test SchedulerConfig dataclass."""
        config = SchedulerConfig(
            timezone="America/New_York",
            max_workers=20,
            shutdown_timeout=60
        )
        
        assert config.timezone == "America/New_York"
        assert config.max_workers == 20
        assert config.shutdown_timeout == 60
        assert config.job_defaults["coalesce"] is True  # default
        assert config.max_consecutive_errors == 5  # default
    
    @pytest.mark.asyncio
    async def test_scheduler_state_transitions(self, scheduler, mock_collector):
        """Test scheduler state transitions."""
        assert scheduler._state == SchedulerState.STOPPED
        
        # Register collector
        scheduler.register_collector(mock_collector, "1h")
        
        # Start scheduler
        await scheduler.start()
        assert scheduler._state == SchedulerState.RUNNING
        
        # Try to start again (should warn but not fail)
        await scheduler.start()
        assert scheduler._state == SchedulerState.RUNNING
        
        # Stop scheduler
        await scheduler.stop()
        assert scheduler._state == SchedulerState.STOPPED
        
        # Try to stop again (should warn but not fail)
        await scheduler.stop()
        assert scheduler._state == SchedulerState.STOPPED
    
    @pytest.mark.asyncio
    async def test_get_next_run_times(self, scheduler, mock_collector):
        """Test getting next run times for collectors."""
        job_id = scheduler.register_collector(mock_collector, "1h")
        
        # Before starting, should be None
        next_runs = scheduler.get_next_run_times()
        assert next_runs[job_id] is None
        
        # After starting, should have a scheduled time
        await scheduler.start()
        next_runs = scheduler.get_next_run_times()
        assert next_runs[job_id] is not None
        assert isinstance(next_runs[job_id], datetime)
        
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_integration_with_multiple_collectors():
    """Integration test with multiple collectors."""
    config = CollectionConfig()
    scheduler_config = SchedulerConfig(
        error_recovery_delay=0.1,
        health_check_interval=0.1
    )
    
    scheduler = CollectionScheduler(config, scheduler_config)
    
    # Create multiple collectors
    collector1 = MockCollector("collector_1", success=True, records=5)
    collector2 = MockCollector("collector_2", success=True, records=10)
    collector3 = MockCollector("collector_3", success=False)  # Failing collector
    
    # Register collectors with different intervals
    job_id1 = scheduler.register_collector(collector1, "1s")
    job_id2 = scheduler.register_collector(collector2, "2s")
    job_id3 = scheduler.register_collector(collector3, "1s", enabled=False)
    
    # Start scheduler
    await scheduler.start()
    
    # Let it run for a short time
    await asyncio.sleep(3)
    
    # Check that collectors were executed
    assert collector1.collect_called >= 2
    assert collector2.collect_called >= 1
    assert collector3.collect_called == 0  # Disabled
    
    # Enable the failing collector
    scheduler.enable_collector(job_id3)
    await asyncio.sleep(1)
    
    # Check status
    status = scheduler.get_status()
    assert status["total_collectors"] == 3
    assert status["enabled_collectors"] == 3
    
    # Stop scheduler
    await scheduler.stop()
    
    # Verify final state
    assert scheduler._state == SchedulerState.STOPPED