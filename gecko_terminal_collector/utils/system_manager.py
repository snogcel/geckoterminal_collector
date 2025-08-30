"""
System initialization and graceful shutdown management.
"""

import asyncio
import logging
import signal
import sys
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from contextlib import asynccontextmanager

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler
from gecko_terminal_collector.monitoring.health_endpoints import SystemHealthEndpoints
from gecko_terminal_collector.utils.resilience import GracefulShutdownHandler, SystemMonitor
from gecko_terminal_collector.utils.structured_logging import logging_manager, get_logger, LogContext
from gecko_terminal_collector.utils.error_handling import ErrorHandler

logger = get_logger(__name__)


class SystemManager:
    """
    Comprehensive system manager for initialization, monitoring, and shutdown.
    
    Coordinates all system components including configuration, database,
    scheduling, monitoring, and provides graceful shutdown capabilities
    with proper resource cleanup.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config_manager: Optional[ConfigManager] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.scheduler: Optional[CollectionScheduler] = None
        self.health_endpoints: Optional[SystemHealthEndpoints] = None
        self.system_monitor: Optional[SystemMonitor] = None
        self.shutdown_handler = GracefulShutdownHandler()
        self.error_handler: Optional[ErrorHandler] = None
        
        self._initialized = False
        self._startup_time: Optional[datetime] = None
        self._shutdown_callbacks: List[Callable] = []
        
        # Register shutdown callback
        self.shutdown_handler.register_shutdown_callback(self._cleanup_resources)
    
    async def initialize(self) -> None:
        """
        Initialize all system components in proper order.
        
        Raises:
            Exception: If initialization fails
        """
        if self._initialized:
            logger.warning("System already initialized")
            return
        
        self._startup_time = datetime.now()
        logger.info("Starting system initialization...")
        
        try:
            # 1. Initialize logging
            await self._initialize_logging()
            
            # 2. Load configuration
            await self._initialize_configuration()
            
            # 3. Initialize error handling
            await self._initialize_error_handling()
            
            # 4. Initialize database
            await self._initialize_database()
            
            # 5. Initialize scheduler
            await self._initialize_scheduler()
            
            # 6. Initialize monitoring and health checks
            await self._initialize_monitoring()
            
            # 7. Start background services
            await self._start_background_services()
            
            self._initialized = True
            
            startup_duration = (datetime.now() - self._startup_time).total_seconds()
            logger.info(
                f"System initialization completed successfully in {startup_duration:.2f} seconds",
                extra={"startup_duration_seconds": startup_duration}
            )
            
        except Exception as e:
            logger.critical("System initialization failed", exc_info=True)
            await self._cleanup_resources()
            raise
    
    async def _initialize_logging(self) -> None:
        """Initialize structured logging system."""
        try:
            # Set up logging with default configuration
            # This can be enhanced to read from config file
            logging_manager.setup_logging(
                log_level="INFO",
                log_file="logs/gecko_collector.log",
                console_output=True,
                structured_format=True
            )
            
            logger.info("Logging system initialized")
            
        except Exception as e:
            print(f"Failed to initialize logging: {e}")
            raise
    
    async def _initialize_configuration(self) -> None:
        """Initialize configuration management."""
        try:
            self.config_manager = ConfigManager(self.config_path)
            await self.config_manager.load_config()
            
            # Start hot-reloading if enabled
            if hasattr(self.config_manager, 'start_hot_reload'):
                await self.config_manager.start_hot_reload()
            
            logger.info("Configuration management initialized")
            
        except Exception as e:
            logger.error("Failed to initialize configuration", exc_info=True)
            raise
    
    async def _initialize_error_handling(self) -> None:
        """Initialize error handling system."""
        try:
            from gecko_terminal_collector.utils.error_handling import RetryConfig
            
            config = self.config_manager.get_config()
            retry_config = RetryConfig(
                max_retries=config.error_handling.max_retries,
                base_delay=1.0,
                backoff_factor=config.error_handling.backoff_factor,
                jitter=True
            )
            
            self.error_handler = ErrorHandler(retry_config)
            
            logger.info("Error handling system initialized")
            
        except Exception as e:
            logger.error("Failed to initialize error handling", exc_info=True)
            raise
    
    async def _initialize_database(self) -> None:
        """Initialize database connection and management."""
        try:
            config = self.config_manager.get_config()
            self.db_manager = DatabaseManager(config.database)
            
            # Test database connection
            await self.db_manager.initialize()
            
            # Register shutdown callback for database cleanup
            self.shutdown_handler.register_shutdown_callback(
                self.db_manager.close_all_connections
            )
            
            logger.info("Database management initialized")
            
        except Exception as e:
            logger.error("Failed to initialize database", exc_info=True)
            raise
    
    async def _initialize_scheduler(self) -> None:
        """Initialize collection scheduler."""
        try:
            config = self.config_manager.get_config()
            self.scheduler = CollectionScheduler(
                config=config,
                db_manager=self.db_manager,
                error_handler=self.error_handler
            )
            
            # Register shutdown callback for scheduler
            self.shutdown_handler.register_shutdown_callback(
                self.scheduler.shutdown
            )
            
            logger.info("Collection scheduler initialized")
            
        except Exception as e:
            logger.error("Failed to initialize scheduler", exc_info=True)
            raise
    
    async def _initialize_monitoring(self) -> None:
        """Initialize monitoring and health check systems."""
        try:
            # Initialize health endpoints
            self.health_endpoints = SystemHealthEndpoints(
                db_manager=self.db_manager,
                error_handler=self.error_handler
            )
            
            # Initialize system monitor
            self.system_monitor = SystemMonitor(
                health_checker=self.health_endpoints.health_checker,
                monitoring_interval=60  # 1 minute
            )
            
            # Register alert callback
            self.system_monitor.register_alert_callback(self._handle_system_alert)
            
            # Register shutdown callbacks
            self.shutdown_handler.register_shutdown_callback(
                self.health_endpoints.stop_monitoring
            )
            self.shutdown_handler.register_shutdown_callback(
                self.system_monitor.stop_monitoring
            )
            
            logger.info("Monitoring and health check systems initialized")
            
        except Exception as e:
            logger.error("Failed to initialize monitoring", exc_info=True)
            raise
    
    async def _start_background_services(self) -> None:
        """Start background monitoring and maintenance services."""
        try:
            # Start system monitoring
            if self.system_monitor:
                await self.system_monitor.start_monitoring()
            
            # Start health monitoring
            if self.health_endpoints:
                await self.health_endpoints.start_monitoring()
            
            logger.info("Background services started")
            
        except Exception as e:
            logger.error("Failed to start background services", exc_info=True)
            raise
    
    async def _handle_system_alert(
        self, 
        alerts: List[str], 
        metrics: Any, 
        health_results: Dict[str, Any]
    ) -> None:
        """Handle system alerts from monitoring."""
        try:
            logger.warning(
                f"System alerts triggered: {'; '.join(alerts)}",
                extra={
                    "alert_count": len(alerts),
                    "alerts": alerts,
                    "cpu_percent": getattr(metrics, 'cpu_percent', 0),
                    "memory_percent": getattr(metrics, 'memory_percent', 0),
                    "disk_usage_percent": getattr(metrics, 'disk_usage_percent', 0)
                }
            )
            
            # Additional alert handling logic can be added here
            # e.g., sending notifications, triggering recovery actions, etc.
            
        except Exception as e:
            logger.error("Failed to handle system alert", exc_info=True)
    
    async def start_scheduler(self) -> None:
        """Start the collection scheduler."""
        if not self._initialized:
            raise RuntimeError("System not initialized")
        
        if self.scheduler:
            await self.scheduler.start()
            logger.info("Collection scheduler started")
        else:
            logger.error("Scheduler not initialized")
    
    async def stop_scheduler(self) -> None:
        """Stop the collection scheduler."""
        if self.scheduler:
            await self.scheduler.shutdown()
            logger.info("Collection scheduler stopped")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "initialized": self._initialized,
                "startup_time": self._startup_time.isoformat() if self._startup_time else None,
                "uptime_seconds": (
                    (datetime.now() - self._startup_time).total_seconds() 
                    if self._startup_time else 0
                ),
                "components": {
                    "config_manager": self.config_manager is not None,
                    "database_manager": self.db_manager is not None,
                    "scheduler": self.scheduler is not None,
                    "health_endpoints": self.health_endpoints is not None,
                    "system_monitor": self.system_monitor is not None,
                    "error_handler": self.error_handler is not None
                }
            }
            
            # Add health status if available
            if self.health_endpoints:
                health_status = await self.health_endpoints.get_health_status()
                status["health"] = health_status
            
            # Add scheduler status if available
            if self.scheduler:
                status["scheduler_status"] = {
                    "running": getattr(self.scheduler, '_running', False),
                    "registered_collectors": len(getattr(self.scheduler, '_collectors', {}))
                }
            
            return status
            
        except Exception as e:
            logger.error("Failed to get system status", exc_info=True)
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "initialized": self._initialized
            }
    
    async def shutdown(self) -> None:
        """Perform graceful system shutdown."""
        logger.info("Initiating system shutdown...")
        
        try:
            await self.shutdown_handler.shutdown()
            logger.info("System shutdown completed")
            
        except Exception as e:
            logger.error("Error during system shutdown", exc_info=True)
            raise
    
    async def _cleanup_resources(self) -> None:
        """Clean up system resources during shutdown."""
        try:
            logger.info("Cleaning up system resources...")
            
            # Stop scheduler
            if self.scheduler:
                try:
                    await self.scheduler.shutdown()
                except Exception as e:
                    logger.error("Error stopping scheduler", exc_info=True)
            
            # Stop monitoring
            if self.system_monitor:
                try:
                    await self.system_monitor.stop_monitoring()
                except Exception as e:
                    logger.error("Error stopping system monitor", exc_info=True)
            
            if self.health_endpoints:
                try:
                    await self.health_endpoints.stop_monitoring()
                except Exception as e:
                    logger.error("Error stopping health monitoring", exc_info=True)
            
            # Close database connections
            if self.db_manager:
                try:
                    await self.db_manager.close_all_connections()
                except Exception as e:
                    logger.error("Error closing database connections", exc_info=True)
            
            # Stop configuration hot-reloading
            if self.config_manager and hasattr(self.config_manager, 'stop_hot_reload'):
                try:
                    await self.config_manager.stop_hot_reload()
                except Exception as e:
                    logger.error("Error stopping config hot-reload", exc_info=True)
            
            logger.info("Resource cleanup completed")
            
        except Exception as e:
            logger.error("Error during resource cleanup", exc_info=True)
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self.shutdown_handler.wait_for_shutdown()
    
    @property
    def is_initialized(self) -> bool:
        """Check if system is initialized."""
        return self._initialized
    
    @property
    def is_shutting_down(self) -> bool:
        """Check if system is shutting down."""
        return self.shutdown_handler.is_shutting_down
    
    @asynccontextmanager
    async def managed_system(self):
        """Context manager for automatic system lifecycle management."""
        try:
            await self.initialize()
            yield self
        finally:
            await self.shutdown()


async def run_system(config_path: Optional[str] = None) -> None:
    """
    Run the complete system with proper initialization and shutdown.
    
    Args:
        config_path: Path to configuration file
    """
    system_manager = SystemManager(config_path)
    
    try:
        # Initialize system
        await system_manager.initialize()
        
        # Start scheduler
        await system_manager.start_scheduler()
        
        logger.info("System is running. Press Ctrl+C to shutdown.")
        
        # Wait for shutdown signal
        await system_manager.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.critical("System error", exc_info=True)
        raise
    finally:
        await system_manager.shutdown()


if __name__ == "__main__":
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_system(config_path))