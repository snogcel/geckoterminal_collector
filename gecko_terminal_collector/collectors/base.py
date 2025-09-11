"""
Base collector interface and common functionality.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from gecko_terminal_collector.models.core import CollectionResult, ValidationResult
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.clients import BaseGeckoClient, create_gecko_client
from gecko_terminal_collector.utils.error_handling import ErrorHandler, RetryConfig
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.utils.structured_logging import get_logger, LogContext
from gecko_terminal_collector.utils.resilience import HealthChecker, HealthStatus
from gecko_terminal_collector.utils.enhanced_rate_limiter import EnhancedRateLimiter
from gecko_terminal_collector.utils.data_normalizer import DataTypeNormalizer

logger = logging.getLogger(__name__)

# Import symbol mapper with fallback for compatibility
try:
    from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
    from gecko_terminal_collector.qlib.integrated_symbol_mapper import IntegratedSymbolMapper
    SYMBOL_MAPPER_AVAILABLE = True
except ImportError:
    SYMBOL_MAPPER_AVAILABLE = False


class BaseDataCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Defines the common interface and shared functionality for collecting
    different types of data from the GeckoTerminal API with robust error
    handling, retry logic, and metadata tracking.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        metadata_tracker: Optional[MetadataTracker] = None,
        use_mock: bool = False,
        rate_limiter: Optional[EnhancedRateLimiter] = None
    ):
        """
        Initialize the collector with configuration and database manager.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            metadata_tracker: Optional metadata tracker for collection statistics
            use_mock: Whether to use mock client for testing
            rate_limiter: Optional enhanced rate limiter instance
        """
        self.config = config
        self.db_manager = db_manager
        self.use_mock = use_mock
        self.metadata_tracker = metadata_tracker or MetadataTracker()
        
        # Initialize enhanced rate limiter
        self.rate_limiter = rate_limiter or EnhancedRateLimiter()
        
        # Initialize data normalizer
        self.data_normalizer = DataTypeNormalizer()
        
        # Initialize error handler with configuration
        retry_config = RetryConfig(
            max_retries=config.error_handling.max_retries,
            base_delay=1.0,
            backoff_factor=config.error_handling.backoff_factor,
            jitter=True
        )
        self.error_handler = ErrorHandler(retry_config)
        
        # Initialize symbol mapper if enhanced database manager is available
        self.symbol_mapper = None
        self._initialize_symbol_mapper()
        
        self._client: Optional[BaseGeckoClient] = None
        
        # Initialize structured logger (done after other initialization)
        self._initialize_logger()
    
    def _initialize_symbol_mapper(self) -> None:
        """Initialize symbol mapper if enhanced database manager is available."""
        if (SYMBOL_MAPPER_AVAILABLE and 
            hasattr(self, 'db_manager') and 
            isinstance(self.db_manager, EnhancedDatabaseManager)):
            try:
                self.symbol_mapper = IntegratedSymbolMapper(self.db_manager)
                logger.debug(f"Initialized integrated symbol mapper for {self.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to initialize symbol mapper: {e}")
                self.symbol_mapper = None
        else:
            logger.debug(f"Symbol mapper not available for {self.__class__.__name__}")
    
    def _initialize_logger(self) -> None:
        """Initialize structured logger with context."""
        try:
            log_context = LogContext(
                collector_type=self.get_collection_key(),
                additional_fields={"use_mock": self.use_mock}
            )
            self.logger = get_logger(f"{__name__}.{self.__class__.__name__}", log_context)
        except Exception as e:
            # Fallback to basic logger if structured logging fails
            self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
            self.logger.warning(f"Failed to initialize structured logger: {e}")
    
    def generate_symbol(self, pool) -> str:
        """
        Generate consistent symbol for a pool across all collectors.
        
        Args:
            pool: Pool object or pool data
            
        Returns:
            Generated symbol string
        """
        if self.symbol_mapper and hasattr(pool, 'id'):
            try:
                return self.symbol_mapper.generate_symbol(pool)
            except Exception as e:
                logger.warning(f"Symbol mapper failed for {self.__class__.__name__}: {e}. Falling back to basic generation.")
                # Fall through to basic symbol generation
        
        # Fallback symbol generation for compatibility
        if hasattr(pool, 'id'):
            pool_id = pool.id
        elif isinstance(pool, dict):
            pool_id = pool.get('id', '')
        else:
            pool_id = str(pool)
        
        # Basic symbol generation logic
        symbol = pool_id
        symbol = ''.join(c if c.isalnum() or c == '_' else '_' for c in symbol)
        while '__' in symbol:
            symbol = symbol.replace('__', '_')
        symbol = symbol.strip('_')
        
        return symbol
    
    async def lookup_pool_by_symbol(self, symbol: str):
        """
        Look up pool by symbol using integrated symbol mapper.
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            Pool object if found, None otherwise
        """
        if self.symbol_mapper:
            return await self.symbol_mapper.lookup_pool_with_fallback(symbol)
        return None
        
        # Initialize error handler with configuration
        retry_config = RetryConfig(
            max_retries=config.error_handling.max_retries,
            base_delay=1.0,
            backoff_factor=config.error_handling.backoff_factor,
            jitter=True
        )
        self.error_handler = ErrorHandler(retry_config)
        
        # Initialize structured logger with context
        log_context = LogContext(
            collector_type=self.get_collection_key(),
            additional_fields={"use_mock": use_mock}
        )
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}", log_context)
        
        self._client: Optional[BaseGeckoClient] = None
    
    @property
    def client(self) -> BaseGeckoClient:
        """Get or create the GeckoTerminal API client."""
        if self._client is None:
            self._client = create_gecko_client(
                self.config.api,
                self.config.error_handling,
                use_mock=self.use_mock
            )
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
    
    async def collect_with_error_handling(self) -> CollectionResult:
        """
        Execute collection with comprehensive error handling and metadata tracking.
        
        This method wraps the collect() method with retry logic, circuit breaker
        protection, and automatic metadata tracking.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors: List[str] = []
        records_collected = 0
        
        try:
            # Execute collection with retry and circuit breaker
            result = await self.error_handler.with_retry(
                self.collect,
                context=f"{self.get_collection_key()} collection",
                circuit_breaker_name=self.get_collection_key(),
                collector_type=self.get_collection_key()
            )
            
            # Store collection metadata if using enhanced database manager
            if hasattr(self.db_manager, 'store_collection_run'):
                try:
                    await self.db_manager.store_collection_run(
                        self.get_collection_key(), 
                        result
                    )
                except Exception as e:
                    logger.warning(f"Failed to store collection metadata: {e}")
            
            # Update metadata tracker
            if self.metadata_tracker:
                self.metadata_tracker.update_metadata(result)
            
            return result
            
        except Exception as e:
            # Handle collection failure
            error_msg = f"Collection failed: {str(e)}"
            errors.append(error_msg)
            
            self.handle_error(e, "collection execution")
            
            # Create failure result
            result = CollectionResult(
                success=False,
                records_collected=records_collected,
                errors=errors,
                collection_time=start_time,
                collector_type=self.get_collection_key()
            )
            
            # Update metadata tracker with failure
            if self.metadata_tracker:
                self.metadata_tracker.update_metadata(result)
            
            return result
    
    async def validate_data(self, data: Any) -> ValidationResult:
        """
        Validate collected data before storage.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        # Base validation
        if data is None:
            errors.append("Data cannot be None")
        elif isinstance(data, (list, tuple)) and len(data) == 0:
            warnings.append("Data collection returned empty results")
        
        # Allow subclasses to add specific validation
        try:
            additional_validation = await self._validate_specific_data(data)
            if additional_validation:
                errors.extend(additional_validation.errors)
                warnings.extend(additional_validation.warnings)
        except NotImplementedError:
            # Subclass doesn't implement specific validation
            pass
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def _validate_specific_data(self, data: Any) -> Optional[ValidationResult]:
        """
        Subclass-specific data validation.
        
        Override this method to implement collector-specific validation logic.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult or None if no specific validation needed
        """
        raise NotImplementedError("Subclasses should implement specific validation")
    
    def handle_error(self, error: Exception, context: str) -> None:
        """
        Handle errors that occur during collection.
        
        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
        """
        self.error_handler.handle_error(
            error=error,
            context=context,
            collector_type=self.get_collection_key()
        )
    
    async def make_api_request(self, request_func, *args, **kwargs) -> Any:
        """
        Make an API request with rate limiting and error handling.
        
        Args:
            request_func: The API request function to call
            *args: Arguments to pass to the request function
            **kwargs: Keyword arguments to pass to the request function
            
        Returns:
            API response data
        """
        # Acquire rate limit permission
        await self.rate_limiter.acquire()
        
        try:
            # Make the API request
            response = await request_func(*args, **kwargs)
            return response
        except Exception as e:
            # Handle rate limit responses
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                if e.response.status_code == 429:
                    # Extract retry-after header if available
                    retry_after = e.response.headers.get('Retry-After', '60')
                    self.rate_limiter.handle_rate_limit_response({'Retry-After': retry_after})
            raise
    
    def normalize_response_data(self, data: Any) -> List[Dict]:
        """
        Normalize API response data to consistent format.
        
        Args:
            data: Raw API response data
            
        Returns:
            Normalized data as List[Dict]
        """
        return self.data_normalizer.normalize_response_data(data)
    
    def validate_data_structure(self, data: Any) -> ValidationResult:
        """
        Validate data structure for this collector type.
        
        Args:
            data: Data to validate
            
        Returns:
            ValidationResult with validation status
        """
        return self.data_normalizer.validate_expected_structure(
            data, 
            self.get_collection_key()
        )
    
    def create_failure_result(
        self, 
        errors: List[str], 
        records_collected: int, 
        start_time: datetime
    ) -> CollectionResult:
        """
        Create a failure result with consistent format.
        
        Args:
            errors: List of error messages
            records_collected: Number of records collected before failure
            start_time: Collection start time
            
        Returns:
            CollectionResult indicating failure
        """
        return CollectionResult(
            success=False,
            records_collected=records_collected,
            errors=errors,
            collection_time=start_time,
            collector_type=self.get_collection_key()
        )
    
    async def execute_with_retry(
        self,
        operation,
        context: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Function to execute
            context: Context description for logging
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Operation result
        """
        return await self.error_handler.with_retry(
            operation,
            context=f"{self.get_collection_key()} - {context}",
            circuit_breaker_name=f"{self.get_collection_key()}_operations",
            collector_type=self.get_collection_key(),
            *args,
            **kwargs
        )
    
    def get_circuit_breaker_status(self) -> dict:
        """Get status of circuit breakers for this collector."""
        return self.error_handler.get_circuit_breaker_status()
    
    def get_metadata(self):
        """Get collection metadata for this collector."""
        return self.metadata_tracker.get_metadata(self.get_collection_key())
    
    def create_success_result(
        self,
        records_collected: int,
        collection_time: Optional[datetime] = None
    ) -> CollectionResult:
        """
        Create a successful collection result.
        
        Args:
            records_collected: Number of records collected
            collection_time: Time of collection (defaults to now)
            
        Returns:
            CollectionResult indicating success
        """
        return CollectionResult(
            success=True,
            records_collected=records_collected,
            errors=[],
            collection_time=collection_time or datetime.now(),
            collector_type=self.get_collection_key()
        )
    
    def create_failure_result(
        self,
        errors: List[str],
        records_collected: int = 0,
        collection_time: Optional[datetime] = None
    ) -> CollectionResult:
        """
        Create a failed collection result.
        
        Args:
            errors: List of error messages
            records_collected: Number of records collected before failure
            collection_time: Time of collection (defaults to now)
            
        Returns:
            CollectionResult indicating failure
        """
        return CollectionResult(
            success=False,
            records_collected=records_collected,
            errors=errors,
            collection_time=collection_time or datetime.now(),
            collector_type=self.get_collection_key()
        )


class CollectorRegistry:
    """
    Registry for managing collector instances with enhanced monitoring.
    
    Provides centralized management of collectors with health monitoring,
    metadata tracking, and batch operations.
    """
    
    def __init__(self, metadata_tracker: Optional[MetadataTracker] = None):
        self._collectors: dict[str, BaseDataCollector] = {}
        self.metadata_tracker = metadata_tracker or MetadataTracker()
    
    def register(self, collector: BaseDataCollector) -> None:
        """
        Register a collector instance.
        
        Args:
            collector: Collector to register
        """
        key = collector.get_collection_key()
        
        # Ensure collector uses the same metadata tracker
        if collector.metadata_tracker != self.metadata_tracker:
            collector.metadata_tracker = self.metadata_tracker
        
        self._collectors[key] = collector
        logger.info(f"Registered collector: {key}")
    
    def get_collector(self, key: str) -> Optional[BaseDataCollector]:
        """
        Get a collector by its key.
        
        Args:
            key: Collector key
            
        Returns:
            Collector instance or None if not found
        """
        return self._collectors.get(key)
    
    def get_all_collectors(self) -> List[BaseDataCollector]:
        """
        Get all registered collectors.
        
        Returns:
            List of all registered collectors
        """
        return list(self._collectors.values())
    
    def get_collector_keys(self) -> List[str]:
        """
        Get all registered collector keys.
        
        Returns:
            List of collector keys
        """
        return list(self._collectors.keys())
    
    def unregister(self, key: str) -> bool:
        """
        Unregister a collector.
        
        Args:
            key: Collector key to unregister
            
        Returns:
            True if collector was found and removed, False otherwise
        """
        if key in self._collectors:
            del self._collectors[key]
            logger.info(f"Unregistered collector: {key}")
            return True
        return False
    
    async def collect_all(self) -> dict[str, CollectionResult]:
        """
        Execute collection for all registered collectors.
        
        Returns:
            Dictionary mapping collector keys to their collection results
        """
        results = {}
        
        for key, collector in self._collectors.items():
            try:
                logger.info(f"Starting collection for {key}")
                result = await collector.collect_with_error_handling()
                results[key] = result
                
                if result.success:
                    logger.info(
                        f"Collection completed for {key}: "
                        f"{result.records_collected} records"
                    )
                else:
                    logger.warning(
                        f"Collection failed for {key}: "
                        f"{'; '.join(result.errors)}"
                    )
                    
            except Exception as e:
                logger.error(f"Unexpected error in collector {key}: {e}")
                results[key] = CollectionResult(
                    success=False,
                    records_collected=0,
                    errors=[f"Unexpected error: {str(e)}"],
                    collection_time=datetime.now(),
                    collector_type=key
                )
        
        return results
    
    def get_health_status(self) -> dict[str, bool]:
        """
        Get health status for all collectors.
        
        Returns:
            Dictionary mapping collector keys to their health status
        """
        return self.metadata_tracker.get_health_summary()
    
    def get_unhealthy_collectors(self) -> List[str]:
        """
        Get list of collectors with poor health status.
        
        Returns:
            List of collector keys that are unhealthy
        """
        return self.metadata_tracker.get_unhealthy_collectors()
    
    def get_registry_summary(self) -> dict:
        """
        Get comprehensive summary of the collector registry.
        
        Returns:
            Dictionary with registry statistics and collector information
        """
        summary = {
            "total_collectors": len(self._collectors),
            "registered_collectors": list(self._collectors.keys()),
            "health_status": self.get_health_status(),
            "unhealthy_collectors": self.get_unhealthy_collectors(),
            "metadata_summary": self.metadata_tracker.export_summary()
        }
        
        return summary