"""
Structured logging with correlation IDs and comprehensive error context.
"""

import json
import logging
import logging.handlers
import sys
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional, Union
from pathlib import Path

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


@dataclass
class LogContext:
    """Context information for structured logging."""
    correlation_id: Optional[str] = None
    collector_type: Optional[str] = None
    operation: Optional[str] = None
    pool_id: Optional[str] = None
    token_symbol: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_fields: Optional[Dict[str, Any]] = None


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        record.correlation_id = correlation_id.get() or "unknown"
        return True


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Provides consistent structured logging format with correlation IDs,
    timestamps, and contextual information for better log analysis.
    """
    
    def __init__(
        self,
        include_extra_fields: bool = True,
        timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    ):
        super().__init__()
        self.include_extra_fields = include_extra_fields
        self.timestamp_format = timestamp_format
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(self.timestamp_format),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": threading.current_thread().name,
            "process": record.process,
            "correlation_id": getattr(record, 'correlation_id', 'unknown')
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add extra fields if enabled
        if self.include_extra_fields:
            extra_fields = {}
            
            # Standard extra fields
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'getMessage', 'exc_info',
                    'exc_text', 'stack_info', 'correlation_id'
                }:
                    try:
                        # Ensure value is JSON serializable
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ContextualLogger:
    """
    Logger wrapper that provides contextual logging with correlation IDs.
    
    Automatically includes context information in log messages and
    manages correlation ID propagation across async operations.
    """
    
    def __init__(self, name: str, context: Optional[LogContext] = None):
        self.logger = logging.getLogger(name)
        self.context = context or LogContext()
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        *args,
        exc_info: Optional[Any] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log message with contextual information."""
        # Prepare extra fields
        extra = {}
        
        # Add context fields
        if self.context.collector_type:
            extra["collector_type"] = self.context.collector_type
        if self.context.operation:
            extra["operation"] = self.context.operation
        if self.context.pool_id:
            extra["pool_id"] = self.context.pool_id
        if self.context.token_symbol:
            extra["token_symbol"] = self.context.token_symbol
        if self.context.user_id:
            extra["user_id"] = self.context.user_id
        if self.context.session_id:
            extra["session_id"] = self.context.session_id
        if self.context.request_id:
            extra["request_id"] = self.context.request_id
        
        # Add additional context fields
        if self.context.additional_fields:
            extra.update(self.context.additional_fields)
        
        # Add extra context from call
        if extra_context:
            extra.update(extra_context)
        
        # Add any additional kwargs
        extra.update(kwargs)
        
        # Set correlation ID if provided in context
        if self.context.correlation_id:
            correlation_id.set(self.context.correlation_id)
        
        self.logger.log(level, message, *args, exc_info=exc_info, extra=extra)
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with context."""
        kwargs['exc_info'] = True
        self._log_with_context(logging.ERROR, message, *args, **kwargs)
    
    def with_context(self, **context_updates) -> 'ContextualLogger':
        """Create new logger with updated context."""
        new_context = LogContext(
            correlation_id=context_updates.get('correlation_id', self.context.correlation_id),
            collector_type=context_updates.get('collector_type', self.context.collector_type),
            operation=context_updates.get('operation', self.context.operation),
            pool_id=context_updates.get('pool_id', self.context.pool_id),
            token_symbol=context_updates.get('token_symbol', self.context.token_symbol),
            user_id=context_updates.get('user_id', self.context.user_id),
            session_id=context_updates.get('session_id', self.context.session_id),
            request_id=context_updates.get('request_id', self.context.request_id),
            additional_fields={
                **(self.context.additional_fields or {}),
                **context_updates.get('additional_fields', {})
            }
        )
        
        return ContextualLogger(self.logger.name, new_context)


class LoggingManager:
    """
    Centralized logging configuration and management.
    
    Provides structured logging setup with file rotation, correlation IDs,
    and configurable output formats for different environments.
    """
    
    def __init__(self):
        self._configured = False
        self._log_handlers: Dict[str, logging.Handler] = {}
    
    def setup_logging(
        self,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console_output: bool = True,
        structured_format: bool = True,
        include_extra_fields: bool = True
    ) -> None:
        """
        Set up comprehensive logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (optional)
            max_file_size: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            console_output: Whether to output logs to console
            structured_format: Whether to use structured JSON format
            include_extra_fields: Whether to include extra fields in structured logs
        """
        if self._configured:
            return
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Set up formatter
        if structured_format:
            formatter = StructuredFormatter(include_extra_fields=include_extra_fields)
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
            )
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.addFilter(CorrelationIdFilter())
            root_logger.addHandler(console_handler)
            self._log_handlers['console'] = console_handler
        
        # File handler with rotation
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(CorrelationIdFilter())
            root_logger.addHandler(file_handler)
            self._log_handlers['file'] = file_handler
        
        # Set specific logger levels
        self._configure_logger_levels()
        
        self._configured = True
        
        # Log configuration completion
        logger = logging.getLogger(__name__)
        logger.info(
            "Logging configuration completed",
            extra={
                "log_level": log_level,
                "log_file": log_file,
                "structured_format": structured_format,
                "console_output": console_output
            }
        )
    
    def _configure_logger_levels(self) -> None:
        """Configure specific logger levels."""
        # Reduce noise from third-party libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    
    def get_contextual_logger(
        self,
        name: str,
        context: Optional[LogContext] = None
    ) -> ContextualLogger:
        """
        Get a contextual logger instance.
        
        Args:
            name: Logger name
            context: Optional logging context
            
        Returns:
            ContextualLogger instance
        """
        return ContextualLogger(name, context)
    
    def create_correlation_id(self) -> str:
        """Create a new correlation ID."""
        return str(uuid.uuid4())
    
    def set_correlation_id(self, corr_id: Optional[str] = None) -> str:
        """
        Set correlation ID for current context.
        
        Args:
            corr_id: Correlation ID to set, or None to generate new one
            
        Returns:
            The correlation ID that was set
        """
        if corr_id is None:
            corr_id = self.create_correlation_id()
        
        correlation_id.set(corr_id)
        return corr_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return correlation_id.get()
    
    def clear_correlation_id(self) -> None:
        """Clear current correlation ID."""
        correlation_id.set(None)
    
    def add_handler(self, name: str, handler: logging.Handler) -> None:
        """Add a custom logging handler."""
        handler.addFilter(CorrelationIdFilter())
        logging.getLogger().addHandler(handler)
        self._log_handlers[name] = handler
    
    def remove_handler(self, name: str) -> None:
        """Remove a logging handler."""
        if name in self._log_handlers:
            logging.getLogger().removeHandler(self._log_handlers[name])
            del self._log_handlers[name]
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics and configuration."""
        return {
            "configured": self._configured,
            "handlers": list(self._log_handlers.keys()),
            "root_level": logging.getLogger().level,
            "correlation_id": self.get_correlation_id(),
            "handler_details": {
                name: {
                    "class": handler.__class__.__name__,
                    "level": handler.level,
                    "formatter": handler.formatter.__class__.__name__ if handler.formatter else None
                }
                for name, handler in self._log_handlers.items()
            }
        }


# Global logging manager instance
logging_manager = LoggingManager()


def get_logger(name: str, context: Optional[LogContext] = None) -> ContextualLogger:
    """
    Get a contextual logger instance.
    
    Args:
        name: Logger name
        context: Optional logging context
        
    Returns:
        ContextualLogger instance
    """
    return logging_manager.get_contextual_logger(name, context)


def with_correlation_id(corr_id: Optional[str] = None):
    """
    Decorator to set correlation ID for function execution.
    
    Args:
        corr_id: Correlation ID to use, or None to generate new one
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                old_corr_id = correlation_id.get()
                try:
                    correlation_id.set(corr_id or logging_manager.create_correlation_id())
                    return await func(*args, **kwargs)
                finally:
                    correlation_id.set(old_corr_id)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                old_corr_id = correlation_id.get()
                try:
                    correlation_id.set(corr_id or logging_manager.create_correlation_id())
                    return func(*args, **kwargs)
                finally:
                    correlation_id.set(old_corr_id)
            return sync_wrapper
    return decorator


# Import asyncio for decorator check
import asyncio