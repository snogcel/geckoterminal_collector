"""
Integration tests for base collector functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from gecko_terminal_collector.collectors.base import BaseDataCollector, CollectorRegistry
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.config.models import CollectionConfig, ErrorConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker


class IntegrationTestCollector(BaseDataCollector):
    """Integration test collector."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collection_count = 0
    
    async def collect(self) -> CollectionResult:
        """Simulate collection with some business logic."""
        self.collection_count += 1
        
        # Simulate some data processing
        await self.execute_with_retry(
            self._fetch_data,
            "fetch data from API"
        )
        
        # Validate data
        validation_result = await self.validate_data({"test": "data"})
        if not validation_result.is_valid:
            return self.create_failure_result(validation_result.errors)
        
        return self.create_success_result(
            records_collected=self.collection_count * 5
        )
    
    async def _fetch_data(self):
        """Simulate API data fetching."""
        return {"test": "data"}
    
    def get_collection_key(self) -> str:
        return "integration_test_collector"


@pytest.fixture
def integration_config():
    """Create integration test configuration."""
    return CollectionConfig(
        error_handling=ErrorConfig(
            max_retries=2,
            backoff_factor=1.5,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )
    )


@pytest.fixture
def integration_db_manager():
    """Create mock database manager for integration tests."""
    return MagicMock(spec=DatabaseManager)


class TestBaseCollectorIntegration:
    """Integration tests for base collector functionality."""
    
    @pytest.mark.asyncio
    async def test_full_collection_workflow(self, integration_config, integration_db_manager):
        """Test complete collection workflow with error handling and metadata."""
        metadata_tracker = MetadataTracker()
        
        collector = IntegrationTestCollector(
            config=integration_config,
            db_manager=integration_db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Execute collection
        result = await collector.collect_with_error_handling()
        
        # Verify result
        assert result.success is True
        assert result.records_collected == 5
        assert result.collector_type == "integration_test_collector"
        
        # Verify metadata was updated
        metadata = metadata_tracker.get_metadata("integration_test_collector")
        assert metadata.total_runs == 1
        assert metadata.successful_runs == 1
        assert metadata.total_records_collected == 5
        assert metadata.success_rate == 100.0
    
    @pytest.mark.asyncio
    async def test_registry_with_multiple_collectors(self, integration_config, integration_db_manager):
        """Test registry with multiple collectors."""
        registry = CollectorRegistry()
        
        # Create multiple collectors
        collector1 = IntegrationTestCollector(
            config=integration_config,
            db_manager=integration_db_manager,
            use_mock=True
        )
        
        class SecondTestCollector(IntegrationTestCollector):
            def get_collection_key(self):
                return "second_test_collector"
        
        collector2 = SecondTestCollector(
            config=integration_config,
            db_manager=integration_db_manager,
            use_mock=True
        )
        
        # Register collectors
        registry.register(collector1)
        registry.register(collector2)
        
        # Execute all collections
        results = await registry.collect_all()
        
        # Verify results
        assert len(results) == 2
        assert "integration_test_collector" in results
        assert "second_test_collector" in results
        
        for result in results.values():
            assert result.success is True
            assert result.records_collected > 0
        
        # Verify registry summary
        summary = registry.get_registry_summary()
        assert summary["total_collectors"] == 2
        assert len(summary["registered_collectors"]) == 2
        
        # Verify health status
        health_status = registry.get_health_status()
        assert all(health_status.values())  # All should be healthy
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, integration_config, integration_db_manager):
        """Test error handling and recovery mechanisms."""
        
        class FlakyCollector(BaseDataCollector):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.attempt_count = 0
            
            async def collect(self) -> CollectionResult:
                self.attempt_count += 1
                
                # Fail first two attempts, succeed on third
                if self.attempt_count <= 2:
                    raise ConnectionError(f"Network error #{self.attempt_count}")
                
                return self.create_success_result(records_collected=1)
            
            def get_collection_key(self) -> str:
                return "flaky_collector"
        
        collector = FlakyCollector(
            config=integration_config,
            db_manager=integration_db_manager,
            use_mock=True
        )
        
        # Execute collection (should succeed after retries)
        result = await collector.collect_with_error_handling()
        
        # Verify eventual success
        assert result.success is True
        assert result.records_collected == 1
        assert collector.attempt_count == 3  # 2 failures + 1 success
        
        # Verify circuit breaker status
        cb_status = collector.get_circuit_breaker_status()
        assert isinstance(cb_status, dict)
    
    @pytest.mark.asyncio
    async def test_metadata_tracking_across_collections(self, integration_config, integration_db_manager):
        """Test metadata tracking across multiple collection runs."""
        metadata_tracker = MetadataTracker()
        
        collector = IntegrationTestCollector(
            config=integration_config,
            db_manager=integration_db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Execute multiple collections
        for i in range(5):
            result = await collector.collect_with_error_handling()
            assert result.success is True
        
        # Verify accumulated metadata
        metadata = metadata_tracker.get_metadata("integration_test_collector")
        assert metadata.total_runs == 5
        assert metadata.successful_runs == 5
        assert metadata.failed_runs == 0
        assert metadata.success_rate == 100.0
        assert metadata.total_records_collected == 75  # 5+10+15+20+25
        assert metadata.is_healthy is True
        
        # Export summary
        summary = metadata_tracker.export_summary()
        assert summary["total_collectors"] == 1
        assert summary["healthy_collectors"] == 1
        assert len(summary["unhealthy_collectors"]) == 0