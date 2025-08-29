"""
Tests for collector base classes and interfaces.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from gecko_terminal_collector.collectors.base import BaseDataCollector, CollectorRegistry
from gecko_terminal_collector.models.core import CollectionResult
from datetime import datetime


class MockCollector(BaseDataCollector):
    """Test implementation of BaseDataCollector."""
    
    async def collect(self) -> CollectionResult:
        return CollectionResult(
            success=True,
            records_collected=10,
            errors=[],
            collection_time=datetime.utcnow(),
            collector_type="test"
        )
    
    def get_collection_key(self) -> str:
        return "test_collector"


@pytest.mark.asyncio
async def test_base_collector_initialization(mock_collection_config, mock_database_manager):
    """Test BaseDataCollector initialization."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    assert collector.config == mock_collection_config
    assert collector.db_manager == mock_database_manager
    assert collector._client is None


@pytest.mark.asyncio
async def test_base_collector_collect(mock_collection_config, mock_database_manager):
    """Test BaseDataCollector collect method."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    result = await collector.collect()
    
    assert result.success is True
    assert result.records_collected == 10
    assert result.collector_type == "test"
    assert len(result.errors) == 0


def test_base_collector_get_collection_key(mock_collection_config, mock_database_manager):
    """Test BaseDataCollector get_collection_key method."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    key = collector.get_collection_key()
    
    assert key == "test_collector"


@pytest.mark.asyncio
async def test_base_collector_validate_data(mock_collection_config, mock_database_manager):
    """Test BaseDataCollector validate_data method."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    # Test with valid data
    assert await collector.validate_data({"test": "data"}) is True
    
    # Test with None data
    assert await collector.validate_data(None) is False


def test_base_collector_handle_error(mock_collection_config, mock_database_manager, capsys):
    """Test BaseDataCollector handle_error method."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    test_error = ValueError("Test error")
    collector.handle_error(test_error, "test context")
    
    captured = capsys.readouterr()
    assert "Error in test_collector" in captured.out
    assert "test context" in captured.out
    assert "Test error" in captured.out


def test_collector_registry():
    """Test CollectorRegistry functionality."""
    registry = CollectorRegistry()
    
    # Test empty registry
    assert len(registry.get_all_collectors()) == 0
    assert registry.get_collector("nonexistent") is None
    
    # Create mock collectors
    collector1 = Mock(spec=BaseDataCollector)
    collector1.get_collection_key.return_value = "collector1"
    
    collector2 = Mock(spec=BaseDataCollector)
    collector2.get_collection_key.return_value = "collector2"
    
    # Test registration
    registry.register(collector1)
    registry.register(collector2)
    
    assert len(registry.get_all_collectors()) == 2
    assert registry.get_collector("collector1") == collector1
    assert registry.get_collector("collector2") == collector2
    
    # Test unregistration
    registry.unregister("collector1")
    assert len(registry.get_all_collectors()) == 1
    assert registry.get_collector("collector1") is None
    assert registry.get_collector("collector2") == collector2
    
    # Test unregistering nonexistent collector
    registry.unregister("nonexistent")  # Should not raise error
    assert len(registry.get_all_collectors()) == 1


def test_collector_registry_duplicate_registration():
    """Test CollectorRegistry handles duplicate registrations."""
    registry = CollectorRegistry()
    
    collector1 = Mock(spec=BaseDataCollector)
    collector1.get_collection_key.return_value = "test_collector"
    
    collector2 = Mock(spec=BaseDataCollector)
    collector2.get_collection_key.return_value = "test_collector"
    
    # Register first collector
    registry.register(collector1)
    assert registry.get_collector("test_collector") == collector1
    
    # Register second collector with same key (should replace)
    registry.register(collector2)
    assert registry.get_collector("test_collector") == collector2
    assert len(registry.get_all_collectors()) == 1


@pytest.mark.asyncio
async def test_base_collector_client_property(mock_collection_config, mock_database_manager):
    """Test BaseDataCollector client property raises NotImplementedError."""
    collector = MockCollector(mock_collection_config, mock_database_manager)
    
    with pytest.raises(NotImplementedError, match="API client not yet implemented"):
        _ = collector.client