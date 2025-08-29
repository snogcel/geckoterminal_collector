"""
Base collector interface and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from gecko_terminal_collector.models.core import CollectionResult
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager


class BaseDataCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Defines the common interface and shared functionality for collecting
    different types of data from the GeckoTerminal API.
    """
    
    def __init__(self, config: CollectionConfig, db_manager: DatabaseManager):
        """
        Initialize the collector with configuration and database manager.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
        """
        self.config = config
        self.db_manager = db_manager
        self._client: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create the GeckoTerminal API client."""
        if self._client is None:
            # Will be implemented when API client is created
            raise NotImplementedError("API client not yet implemented")
        return self._client
    
    @abstractmethod
    async def collect(self) -> CollectionResult:
        """
        Collect data from the API and store it in the database.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        pass
    
    @abstractmethod
    def get_collection_key(self) -> str:
        """
        Get a unique key identifying this collector type.
        
        Returns:
            String key for this collector type
        """
        pass
    
    async def validate_data(self, data: Any) -> bool:
        """
        Validate collected data before storage.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        # Base validation - can be overridden by subclasses
        return data is not None
    
    def handle_error(self, error: Exception, context: str) -> None:
        """
        Handle errors that occur during collection.
        
        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
        """
        # Basic error handling - will be enhanced with proper logging
        print(f"Error in {self.get_collection_key()} - {context}: {error}")


class CollectorRegistry:
    """Registry for managing collector instances."""
    
    def __init__(self):
        self._collectors: dict[str, BaseDataCollector] = {}
    
    def register(self, collector: BaseDataCollector) -> None:
        """Register a collector instance."""
        key = collector.get_collection_key()
        self._collectors[key] = collector
    
    def get_collector(self, key: str) -> Optional[BaseDataCollector]:
        """Get a collector by its key."""
        return self._collectors.get(key)
    
    def get_all_collectors(self) -> list[BaseDataCollector]:
        """Get all registered collectors."""
        return list(self._collectors.values())
    
    def unregister(self, key: str) -> None:
        """Unregister a collector."""
        self._collectors.pop(key, None)