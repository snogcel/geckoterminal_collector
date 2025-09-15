# Developer Guide

This guide provides comprehensive information for developers who want to extend, customize, or contribute to the GeckoTerminal Data Collector system.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Creating Custom Collectors](#creating-custom-collectors)
- [Extending Data Models](#extending-data-models)
- [Database Schema Extensions](#database-schema-extensions)
- [Configuration Extensions](#configuration-extensions)
- [Testing Guidelines](#testing-guidelines)
- [Performance Optimization](#performance-optimization)
- [Contributing Guidelines](#contributing-guidelines)

## Architecture Overview

### System Components

The system follows a modular architecture with clear separation of concerns:

```
gecko_terminal_collector/
├── config/           # Configuration management
├── collectors/       # Data collection modules
├── database/         # Database abstraction layer
├── models/          # Data models and schemas
├── scheduling/      # Task scheduling system
├── qlib/           # QLib integration
├── monitoring/     # System monitoring and database health
├── utils/          # Utility functions and activity scoring
└── cli.py          # Enhanced command-line interface
```

### Design Principles

1. **Modularity**: Each component has a single responsibility
2. **Extensibility**: Easy to add new collectors and data types
3. **Testability**: Comprehensive test coverage with mocking
4. **Configuration-Driven**: Behavior controlled via configuration
5. **Error Resilience**: Robust error handling and recovery
6. **Performance**: Async operations and efficient data processing

### Key Patterns

- **Abstract Base Classes**: For collectors and data models
- **Factory Pattern**: For creating collectors and database connections
- **Observer Pattern**: For configuration change notifications
- **Circuit Breaker**: For API failure protection
- **Repository Pattern**: For data access abstraction

## Development Setup

### Prerequisites

```bash
# Python 3.8+
python --version

# Git
git --version

# Optional: Docker for containerized development
docker --version
```

### Development Environment

1. **Clone Repository**
```bash
git clone <repository-url>
cd gecko-terminal-collector
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Development Dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

4. **Install Pre-commit Hooks**
```bash
pre-commit install
```

5. **Setup Development Database**
```bash
cp config.yaml.example config-dev.yaml
python -m gecko_terminal_collector.cli init-db --config config-dev.yaml
```

### Development Tools

#### Code Quality Tools
```bash
# Linting
flake8 gecko_terminal_collector/
pylint gecko_terminal_collector/

# Type checking
mypy gecko_terminal_collector/

# Code formatting
black gecko_terminal_collector/
isort gecko_terminal_collector/

# Security scanning
bandit -r gecko_terminal_collector/
```

#### Testing Tools
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=gecko_terminal_collector --cov-report=html

# Performance tests
pytest tests/performance/
```

## Code Structure

### Core Modules

#### Configuration Module (`config/`)

```python
# config/manager.py
class ConfigManager:
    """Central configuration management."""
    
# config/schema.py
class ConfigSchema:
    """Configuration validation schemas."""
    
# config/environment.py
class EnvironmentConfig:
    """Environment variable integration."""
```

#### Collectors Module (`collectors/`)

```python
# collectors/base.py
class BaseDataCollector(ABC):
    """Abstract base class for all collectors."""
    
# collectors/dex_monitoring.py
class DEXMonitoringCollector(BaseDataCollector):
    """DEX availability monitoring."""
    
# collectors/ohlcv.py
class OHLCVCollector(BaseDataCollector):
    """OHLCV data collection."""
```

#### Database Module (`database/`)

```python
# database/manager.py
class DatabaseManager:
    """Database operations and connection management."""
    
# database/models.py
# SQLAlchemy model definitions
    
# database/migrations.py
class MigrationManager:
    """Database schema migrations."""
```

#### Models Module (`models/`)

```python
# models/data.py
@dataclass
class Pool:
    """Pool data model."""
    
@dataclass
class OHLCVRecord:
    """OHLCV data model."""
```

### File Organization

```
gecko_terminal_collector/
├── __init__.py
├── cli.py                    # Command-line interface
├── config/
│   ├── __init__.py
│   ├── manager.py           # Configuration management
│   ├── schema.py            # Configuration validation
│   └── environment.py       # Environment integration
├── collectors/
│   ├── __init__.py
│   ├── base.py             # Base collector class
│   ├── dex_monitoring.py   # DEX monitoring collector
│   ├── top_pools.py        # Top pools collector
│   ├── ohlcv.py           # OHLCV collector
│   ├── trades.py          # Trade collector
│   └── watchlist.py       # Watchlist collector
├── database/
│   ├── __init__.py
│   ├── manager.py         # Database manager
│   ├── models.py          # SQLAlchemy models
│   ├── migrations.py      # Migration utilities
│   └── query.py           # Query interface
├── models/
│   ├── __init__.py
│   ├── data.py           # Data models
│   ├── results.py        # Result models
│   └── validation.py     # Validation models
├── scheduling/
│   ├── __init__.py
│   ├── scheduler.py      # Collection scheduler
│   └── tasks.py          # Task definitions
├── qlib/
│   ├── __init__.py
│   ├── exporter.py       # QLib data exporter
│   └── formatter.py      # Data format conversion
├── monitoring/
│   ├── __init__.py
│   ├── database_monitor.py  # Real-time database health monitoring
│   ├── metrics.py          # Performance metrics collection
│   └── alerts.py           # Multi-level alert system
└── utils/
    ├── __init__.py
    ├── api_client.py     # API client utilities
    ├── error_handling.py # Error handling utilities
    ├── validation.py     # Data validation utilities
    └── activity_scorer.py # Pool activity scoring algorithms
```

## Creating Custom Collectors

### Basic Collector Structure

```python
from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.models.results import CollectionResult
from typing import List, Any

class CustomCollector(BaseDataCollector):
    """Custom data collector implementation."""
    
    def __init__(self, config: CollectionConfig, db_manager: DatabaseManager):
        super().__init__(config, db_manager)
        self.custom_setting = config.get("custom_setting", "default_value")
    
    async def collect(self) -> CollectionResult:
        """Main collection method."""
        try:
            # Step 1: Fetch data from source
            raw_data = await self._fetch_data()
            
            # Step 2: Process and validate data
            processed_data = await self._process_data(raw_data)
            validation_result = await self.validate_data(processed_data)
            
            if not validation_result.is_valid:
                return CollectionResult(
                    collector_type=self.get_collection_key(),
                    success=False,
                    errors=validation_result.errors,
                    records_collected=0,
                    records_stored=0
                )
            
            # Step 3: Store data
            stored_count = await self._store_data(processed_data)
            
            # Step 4: Update metadata
            await self._update_collection_metadata(len(processed_data), stored_count)
            
            return CollectionResult(
                collector_type=self.get_collection_key(),
                success=True,
                records_collected=len(processed_data),
                records_stored=stored_count,
                errors=[],
                duration=time.time() - start_time,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            await self.handle_error(e, "custom_collection")
            return CollectionResult(
                collector_type=self.get_collection_key(),
                success=False,
                errors=[str(e)],
                records_collected=0,
                records_stored=0
            )
    
    def get_collection_key(self) -> str:
        """Return unique collector identifier."""
        return "custom_collector"
    
    async def _fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from external source."""
        # Implement data fetching logic
        # Use self.client for API calls
        # Apply rate limiting and error handling
        pass
    
    async def _process_data(self, raw_data: List[Dict[str, Any]]) -> List[CustomDataModel]:
        """Process raw data into structured models."""
        processed = []
        for item in raw_data:
            try:
                model = CustomDataModel.from_api_response(item)
                processed.append(model)
            except Exception as e:
                self.logger.warning(f"Failed to process item: {e}")
                continue
        return processed
    
    async def _store_data(self, data: List[CustomDataModel]) -> int:
        """Store processed data in database."""
        return await self.db_manager.store_custom_data(data)
    
    async def _update_collection_metadata(self, collected: int, stored: int) -> None:
        """Update collection execution metadata."""
        metadata = CollectionMetadata(
            collector_type=self.get_collection_key(),
            last_run=datetime.now(),
            last_success=datetime.now(),
            run_count=1,  # Increment existing count
            records_collected=collected,
            records_stored=stored
        )
        await self.db_manager.update_collection_metadata(
            self.get_collection_key(), metadata
        )
```

### Advanced Collector Features

#### Rate Limiting and Retry Logic

```python
class AdvancedCollector(BaseDataCollector):
    async def _fetch_with_retry(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch data with retry logic and rate limiting."""
        max_retries = self.config.get("max_retries", 3)
        base_delay = self.config.get("rate_limit_delay", 1.0)
        
        for attempt in range(max_retries + 1):
            try:
                # Apply rate limiting
                await asyncio.sleep(self.get_retry_delay(attempt, base_delay))
                
                # Make API call
                response = await self.client.get(url, params=params)
                
                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    await asyncio.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                if attempt == max_retries:
                    raise
                
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self.get_retry_delay(attempt + 1, base_delay))
```

#### Batch Processing

```python
class BatchCollector(BaseDataCollector):
    async def _process_in_batches(self, items: List[Any], batch_size: int = 100) -> List[Any]:
        """Process items in batches for memory efficiency."""
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)
            
            # Optional: Add delay between batches
            if i + batch_size < len(items):
                await asyncio.sleep(0.1)
        
        return results
    
    async def _process_batch(self, batch: List[Any]) -> List[Any]:
        """Process a single batch of items."""
        tasks = [self._process_item(item) for item in batch]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### Registering Custom Collectors

```python
# In your configuration or initialization code
from gecko_terminal_collector.scheduling import CollectionScheduler
from your_module import CustomCollector

# Register collector with scheduler
scheduler = CollectionScheduler(config)
custom_collector = CustomCollector(config.collection, db_manager)
scheduler.register_collector(custom_collector, interval="30m")
```

## Extending Data Models

### Creating New Data Models

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from gecko_terminal_collector.models.validation import ValidationResult

@dataclass
class CustomDataModel:
    """Custom data model for new data type."""
    
    id: str
    name: str
    value: Decimal
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def validate(self) -> ValidationResult:
        """Validate model data."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate required fields
        if not self.id:
            result.add_error("ID is required")
        
        if not self.name:
            result.add_error("Name is required")
        
        # Validate data types and ranges
        if self.value < 0:
            result.add_warning("Negative value detected")
        
        # Validate timestamp
        if self.timestamp > datetime.now():
            result.add_error("Timestamp cannot be in the future")
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "value": float(self.value),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomDataModel':
        """Create instance from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            value=Decimal(str(data["value"])),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata")
        )
    
    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> 'CustomDataModel':
        """Create instance from API response."""
        return cls(
            id=response["id"],
            name=response["attributes"]["name"],
            value=Decimal(str(response["attributes"]["value"])),
            timestamp=datetime.fromisoformat(response["attributes"]["timestamp"]),
            metadata=response.get("metadata")
        )
```

### Database Model Integration

```python
# In database/models.py
from sqlalchemy import Column, String, DECIMAL, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CustomDataTable(Base):
    """SQLAlchemy model for custom data."""
    
    __tablename__ = "custom_data"
    
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    value = Column(DECIMAL(30, 18), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_model(self) -> CustomDataModel:
        """Convert to domain model."""
        return CustomDataModel(
            id=self.id,
            name=self.name,
            value=self.value,
            timestamp=self.timestamp,
            metadata=self.metadata
        )
    
    @classmethod
    def from_model(cls, model: CustomDataModel) -> 'CustomDataTable':
        """Create from domain model."""
        return cls(
            id=model.id,
            name=model.name,
            value=model.value,
            timestamp=model.timestamp,
            metadata=model.metadata
        )
```

## Database Schema Extensions

### Adding New Tables

1. **Create Migration Script**

```python
# migrations/versions/add_custom_data_table.py
"""Add custom data table

Revision ID: 001_custom_data
Revises: base
Create Date: 2024-08-30 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_custom_data'
down_revision = 'base'
branch_labels = None
depends_on = None

def upgrade():
    """Create custom_data table."""
    op.create_table(
        'custom_data',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('value', sa.DECIMAL(30, 18), nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('idx_custom_data_timestamp', 'custom_data', ['timestamp'])
    op.create_index('idx_custom_data_name', 'custom_data', ['name'])

def downgrade():
    """Drop custom_data table."""
    op.drop_table('custom_data')
```

2. **Run Migration**

```bash
python -m gecko_terminal_collector.cli migrate --revision 001_custom_data
```

### Database Manager Extensions

```python
# In database/manager.py
class DatabaseManager:
    async def store_custom_data(self, data: List[CustomDataModel]) -> int:
        """Store custom data with duplicate prevention."""
        if not data:
            return 0
        
        async with self.get_session() as session:
            stored_count = 0
            
            for item in data:
                # Check for existing record
                existing = await session.get(CustomDataTable, item.id)
                if existing:
                    continue
                
                # Create new record
                db_item = CustomDataTable.from_model(item)
                session.add(db_item)
                stored_count += 1
            
            await session.commit()
            return stored_count
    
    async def get_custom_data(self, start: datetime, end: datetime) -> List[CustomDataModel]:
        """Retrieve custom data for date range."""
        async with self.get_session() as session:
            query = select(CustomDataTable).where(
                CustomDataTable.timestamp >= start,
                CustomDataTable.timestamp <= end
            ).order_by(CustomDataTable.timestamp)
            
            result = await session.execute(query)
            db_items = result.scalars().all()
            
            return [item.to_model() for item in db_items]
```

## Configuration Extensions

### Adding New Configuration Sections

```python
# In config/schema.py
class CustomConfig:
    """Configuration for custom functionality."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.enabled = config_dict.get("enabled", True)
        self.batch_size = config_dict.get("batch_size", 100)
        self.timeout = config_dict.get("timeout", 30)
        self.custom_settings = config_dict.get("custom_settings", {})
    
    def validate(self) -> ValidationResult:
        """Validate custom configuration."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if self.batch_size <= 0:
            result.add_error("batch_size must be positive")
        
        if self.timeout <= 0:
            result.add_error("timeout must be positive")
        
        result.is_valid = len(result.errors) == 0
        return result

# In config/manager.py
class ConfigManager:
    def get_custom_config(self) -> CustomConfig:
        """Get custom configuration section."""
        custom_dict = self.config.get("custom", {})
        return CustomConfig(custom_dict)
```

### Configuration File Updates

```yaml
# config.yaml
custom:
  enabled: true
  batch_size: 100
  timeout: 30
  custom_settings:
    feature_flag: true
    max_items: 1000
```

## Testing Guidelines

### Unit Testing

```python
# tests/unit/test_custom_collector.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from gecko_terminal_collector.collectors.custom import CustomCollector
from gecko_terminal_collector.models.results import CollectionResult

class TestCustomCollector:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get.return_value = "test_value"
        return config
    
    @pytest.fixture
    def mock_db_manager(self):
        db_manager = AsyncMock()
        db_manager.store_custom_data.return_value = 5
        return db_manager
    
    @pytest.fixture
    def collector(self, mock_config, mock_db_manager):
        return CustomCollector(mock_config, mock_db_manager)
    
    @pytest.mark.asyncio
    async def test_collect_success(self, collector, mock_db_manager):
        """Test successful data collection."""
        # Mock data fetching
        collector._fetch_data = AsyncMock(return_value=[
            {"id": "1", "name": "test1", "value": "100.0"},
            {"id": "2", "name": "test2", "value": "200.0"}
        ])
        
        # Execute collection
        result = await collector.collect()
        
        # Verify results
        assert result.success is True
        assert result.records_collected == 2
        assert result.records_stored == 5
        mock_db_manager.store_custom_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_api_error(self, collector):
        """Test collection with API error."""
        # Mock API error
        collector._fetch_data = AsyncMock(side_effect=Exception("API Error"))
        
        # Execute collection
        result = await collector.collect()
        
        # Verify error handling
        assert result.success is False
        assert "API Error" in result.errors
```

### Integration Testing

```python
# tests/integration/test_custom_integration.py
import pytest
from gecko_terminal_collector.config import ConfigManager
from gecko_terminal_collector.database import DatabaseManager
from gecko_terminal_collector.collectors.custom import CustomCollector

class TestCustomIntegration:
    @pytest.fixture
    async def setup_system(self):
        """Setup test system with real components."""
        config = ConfigManager("config-test.yaml")
        db_manager = DatabaseManager(config.get("database"))
        
        # Initialize test database
        await db_manager.init_database()
        
        yield config, db_manager
        
        # Cleanup
        await db_manager.cleanup_test_data()
    
    @pytest.mark.asyncio
    async def test_end_to_end_collection(self, setup_system):
        """Test complete collection workflow."""
        config, db_manager = setup_system
        
        collector = CustomCollector(config.get("collection"), db_manager)
        
        # Execute collection
        result = await collector.collect()
        
        # Verify data was stored
        assert result.success is True
        
        # Verify data in database
        stored_data = await db_manager.get_custom_data(
            start=datetime.now() - timedelta(hours=1),
            end=datetime.now()
        )
        assert len(stored_data) > 0
```

### Performance Testing

```python
# tests/performance/test_custom_performance.py
import pytest
import time
from gecko_terminal_collector.collectors.custom import CustomCollector

class TestCustomPerformance:
    @pytest.mark.asyncio
    async def test_collection_performance(self, collector):
        """Test collection performance under load."""
        # Generate large dataset
        large_dataset = [
            {"id": f"test_{i}", "name": f"item_{i}", "value": str(i * 10)}
            for i in range(10000)
        ]
        
        collector._fetch_data = AsyncMock(return_value=large_dataset)
        
        # Measure collection time
        start_time = time.time()
        result = await collector.collect()
        duration = time.time() - start_time
        
        # Performance assertions
        assert result.success is True
        assert duration < 30.0  # Should complete within 30 seconds
        assert result.records_collected == 10000
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, collector):
        """Test memory usage during collection."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Execute collection
        await collector.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase by more than 100MB
        assert memory_increase < 100 * 1024 * 1024
```

## Performance Optimization

### Async Operations

```python
class OptimizedCollector(BaseDataCollector):
    async def collect_concurrent(self, pool_ids: List[str]) -> CollectionResult:
        """Collect data for multiple pools concurrently."""
        semaphore = asyncio.Semaphore(self.config.get("max_concurrent", 5))
        
        async def collect_pool(pool_id: str):
            async with semaphore:
                return await self._collect_pool_data(pool_id)
        
        # Execute concurrent collections
        tasks = [collect_pool(pool_id) for pool_id in pool_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        return self._aggregate_results(successful_results)
```

### Database Optimization

```python
class OptimizedDatabaseManager(DatabaseManager):
    async def bulk_insert_ohlcv(self, records: List[OHLCVRecord]) -> int:
        """Optimized bulk insert for OHLCV data."""
        if not records:
            return 0
        
        # Convert to dictionaries for bulk insert
        data_dicts = [record.to_dict() for record in records]
        
        async with self.get_session() as session:
            # Use bulk insert for better performance
            await session.execute(
                insert(OHLCVTable).values(data_dicts)
                .on_conflict_do_nothing()  # PostgreSQL
                # .prefix_with("OR IGNORE")  # SQLite
            )
            await session.commit()
            
            return len(data_dicts)
    
    async def batch_process_data(self, data: List[Any], batch_size: int = 1000) -> int:
        """Process data in batches for memory efficiency."""
        total_processed = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            processed = await self._process_batch(batch)
            total_processed += processed
            
            # Optional: Add small delay to prevent overwhelming the database
            if i + batch_size < len(data):
                await asyncio.sleep(0.01)
        
        return total_processed
```

### Caching Strategies

```python
from functools import lru_cache
import asyncio
from typing import Dict, Any

class CachedCollector(BaseDataCollector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
    
    async def get_cached_data(self, key: str, fetch_func, ttl: int = 300) -> Any:
        """Get data from cache or fetch if expired."""
        current_time = time.time()
        
        # Check if data is cached and not expired
        if key in self._cache and current_time - self._cache_ttl.get(key, 0) < ttl:
            return self._cache[key]
        
        # Fetch fresh data
        data = await fetch_func()
        
        # Update cache
        self._cache[key] = data
        self._cache_ttl[key] = current_time
        
        return data
    
    @lru_cache(maxsize=1000)
    def get_pool_info(self, pool_id: str) -> Dict[str, Any]:
        """Cached pool information lookup."""
        # This would be called frequently, so caching helps
        return self._fetch_pool_info_sync(pool_id)
```

## Contributing Guidelines

### Code Style

1. **Follow PEP 8**: Use black and isort for formatting
2. **Type Hints**: Add type hints to all functions and methods
3. **Docstrings**: Use Google-style docstrings
4. **Error Handling**: Always handle exceptions appropriately
5. **Logging**: Use structured logging with appropriate levels

### Example Code Style

```python
from typing import List, Optional, Dict, Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExampleClass:
    """Example class demonstrating code style.
    
    Args:
        name: The name of the example
        value: Optional numeric value
        
    Attributes:
        name: The name of the example
        value: Optional numeric value
        processed: Whether the example has been processed
    """
    
    name: str
    value: Optional[float] = None
    processed: bool = False
    
    def process_data(self, input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process input data and return results.
        
        Args:
            input_data: List of dictionaries containing raw data
            
        Returns:
            List of processed data dictionaries
            
        Raises:
            ValueError: If input_data is empty or invalid
        """
        if not input_data:
            raise ValueError("Input data cannot be empty")
        
        try:
            processed_data = []
            for item in input_data:
                processed_item = self._process_item(item)
                if processed_item:
                    processed_data.append(processed_item)
            
            self.processed = True
            logger.info(f"Processed {len(processed_data)} items successfully")
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to process data: {e}")
            raise
    
    def _process_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single data item.
        
        Args:
            item: Dictionary containing item data
            
        Returns:
            Processed item dictionary or None if invalid
        """
        # Implementation details...
        pass
```

### Pull Request Process

1. **Fork Repository**: Create a fork of the main repository
2. **Create Branch**: Create a feature branch from main
3. **Implement Changes**: Follow coding standards and add tests
4. **Run Tests**: Ensure all tests pass
5. **Update Documentation**: Update relevant documentation
6. **Submit PR**: Create pull request with clear description

### Testing Requirements

- **Unit Tests**: All new code must have unit tests
- **Integration Tests**: Add integration tests for new features
- **Performance Tests**: Add performance tests for critical paths
- **Coverage**: Maintain >90% test coverage

### Documentation Requirements

- **API Documentation**: Update API docs for new interfaces
- **User Guide**: Update user guide for new features
- **Developer Guide**: Update developer guide for new patterns
- **Configuration**: Document new configuration options

### Release Process

1. **Version Bump**: Update version in setup.py and __init__.py
2. **Changelog**: Update CHANGELOG.md with new features and fixes
3. **Documentation**: Ensure all documentation is up to date
4. **Testing**: Run full test suite including performance tests
5. **Tag Release**: Create git tag with version number
6. **Deploy**: Deploy to package repository

For more information on contributing, see the project's CONTRIBUTING.md file.