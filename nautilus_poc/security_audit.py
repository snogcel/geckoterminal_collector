"""
Security audit logging and monitoring for NautilusTrader POC
"""

import os
import json
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class SecurityEventType(Enum):
    """Security event types"""
    WALLET_ACCESS = "wallet_access"
    TRANSACTION_SIGNED = "transaction_signed"
    PRIVATE_KEY_LOADED = "private_key_loaded"
    TOKEN_VALIDATION = "token_validation"
    BALANCE_CHECK = "balance_check"
    CONFIGURATION_CHANGE = "configuration_change"
    AUTHENTICATION_ATTEMPT = "authentication_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

class SecurityLevel(Enum):
    """Security event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class SecurityEvent:
    """Security audit event"""
    event_type: SecurityEventType
    level: SecurityLevel
    message: str
    timestamp: float
    wallet_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    token_address: Optional[str] = None
    amount: Optional[float] = None
    environment: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['level'] = self.level.value
        return data

class SecurityAuditor:
    """Security audit logging and monitoring"""
    
    def __init__(self, config):
        self.config = config
        self.security_config = config.security
        self.audit_log_path = Path(self.security_config.audit_log_path)
        self.events = []
        self.rate_limits = {}
        
        # Ensure audit log directory exists
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize audit logging
        self._setup_audit_logger()
    
    def _setup_audit_logger(self) -> None:
        """Setup dedicated audit logger"""
        self.audit_logger = logging.getLogger('security_audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # Create file handler for audit log
        if self.security_config.enable_audit_logging:
            handler = logging.FileHandler(self.audit_log_path)
            formatter = logging.Formatter(
                '%(asctime)s - SECURITY_AUDIT - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
    
    def log_security_event(self, event: SecurityEvent) -> None:
        """Log security event"""
        if not self.security_config.enable_audit_logging:
            return
        
        # Add to in-memory events
        self.events.append(event)
        
        # Keep only recent events (last 1000)
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
        
        # Log to audit file
        event_data = event.to_dict()
        
        # Mask sensitive data if enabled
        if self.security_config.sensitive_data_masking:
            event_data = self._mask_sensitive_data(event_data)
        
        self.audit_logger.info(json.dumps(event_data))
        
        # Log to main logger based on severity
        log_method = getattr(logger, event.level.value, logger.info)
        log_method(f"Security Event [{event.event_type.value}]: {event.message}")
    
    def log_wallet_access(self, wallet_address: str, operation: str, success: bool) -> None:
        """Log wallet access event"""
        event = SecurityEvent(
            event_type=SecurityEventType.WALLET_ACCESS,
            level=SecurityLevel.INFO if success else SecurityLevel.WARNING,
            message=f"Wallet {operation}: {'success' if success else 'failed'}",
            timestamp=time.time(),
            wallet_address=wallet_address,
            environment=self.config.environment,
            additional_data={'operation': operation, 'success': success}
        )
        self.log_security_event(event)
    
    def log_transaction_signed(self, wallet_address: str, transaction_hash: str, 
                             token_address: str, amount: float) -> None:
        """Log transaction signing event"""
        event = SecurityEvent(
            event_type=SecurityEventType.TRANSACTION_SIGNED,
            level=SecurityLevel.INFO,
            message=f"Transaction signed for {amount} tokens",
            timestamp=time.time(),
            wallet_address=wallet_address,
            transaction_hash=transaction_hash,
            token_address=token_address,
            amount=amount,
            environment=self.config.environment
        )
        self.log_security_event(event)
    
    def log_private_key_loaded(self, source: str, success: bool) -> None:
        """Log private key loading event"""
        event = SecurityEvent(
            event_type=SecurityEventType.PRIVATE_KEY_LOADED,
            level=SecurityLevel.INFO if success else SecurityLevel.ERROR,
            message=f"Private key loaded from {source}: {'success' if success else 'failed'}",
            timestamp=time.time(),
            environment=self.config.environment,
            additional_data={'source': source, 'success': success}
        )
        self.log_security_event(event)
    
    def log_token_validation(self, token_address: str, validation_result: bool, 
                           reason: Optional[str] = None) -> None:
        """Log token validation event"""
        level = SecurityLevel.INFO if validation_result else SecurityLevel.WARNING
        message = f"Token validation: {'passed' if validation_result else 'failed'}"
        if reason:
            message += f" - {reason}"
        
        event = SecurityEvent(
            event_type=SecurityEventType.TOKEN_VALIDATION,
            level=level,
            message=message,
            timestamp=time.time(),
            token_address=token_address,
            environment=self.config.environment,
            additional_data={'validation_result': validation_result, 'reason': reason}
        )
        self.log_security_event(event)
    
    def log_suspicious_activity(self, activity_type: str, details: str, 
                              wallet_address: Optional[str] = None) -> None:
        """Log suspicious activity"""
        event = SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            level=SecurityLevel.CRITICAL,
            message=f"Suspicious activity detected: {activity_type} - {details}",
            timestamp=time.time(),
            wallet_address=wallet_address,
            environment=self.config.environment,
            additional_data={'activity_type': activity_type, 'details': details}
        )
        self.log_security_event(event)
    
    def log_circuit_breaker_triggered(self, reason: str, failure_count: int) -> None:
        """Log circuit breaker activation"""
        event = SecurityEvent(
            event_type=SecurityEventType.CIRCUIT_BREAKER_TRIGGERED,
            level=SecurityLevel.ERROR,
            message=f"Circuit breaker triggered: {reason} (failures: {failure_count})",
            timestamp=time.time(),
            environment=self.config.environment,
            additional_data={'reason': reason, 'failure_count': failure_count}
        )
        self.log_security_event(event)
    
    def log_rate_limit_exceeded(self, limit_type: str, current_count: int, limit: int) -> None:
        """Log rate limit exceeded"""
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            level=SecurityLevel.WARNING,
            message=f"Rate limit exceeded: {limit_type} ({current_count}/{limit})",
            timestamp=time.time(),
            environment=self.config.environment,
            additional_data={'limit_type': limit_type, 'current_count': current_count, 'limit': limit}
        )
        self.log_security_event(event)
    
    def check_rate_limits(self, operation: str) -> bool:
        """Check if operation is within rate limits"""
        current_time = time.time()
        
        # Initialize rate limit tracking for operation
        if operation not in self.rate_limits:
            self.rate_limits[operation] = {
                'minute_count': 0,
                'hour_count': 0,
                'day_count': 0,
                'last_minute': current_time,
                'last_hour': current_time,
                'last_day': current_time
            }
        
        limits = self.rate_limits[operation]
        
        # Reset counters if time windows have passed
        if current_time - limits['last_minute'] >= 60:
            limits['minute_count'] = 0
            limits['last_minute'] = current_time
        
        if current_time - limits['last_hour'] >= 3600:
            limits['hour_count'] = 0
            limits['last_hour'] = current_time
        
        if current_time - limits['last_day'] >= 86400:
            limits['day_count'] = 0
            limits['last_day'] = current_time
        
        # Check limits
        if limits['minute_count'] >= self.security_config.max_trades_per_minute:
            self.log_rate_limit_exceeded('per_minute', limits['minute_count'], 
                                       self.security_config.max_trades_per_minute)
            return False
        
        if limits['hour_count'] >= self.security_config.max_trades_per_hour:
            self.log_rate_limit_exceeded('per_hour', limits['hour_count'], 
                                       self.security_config.max_trades_per_hour)
            return False
        
        if limits['day_count'] >= self.security_config.max_trades_per_day:
            self.log_rate_limit_exceeded('per_day', limits['day_count'], 
                                       self.security_config.max_trades_per_day)
            return False
        
        # Increment counters
        limits['minute_count'] += 1
        limits['hour_count'] += 1
        limits['day_count'] += 1
        
        return True
    
    def detect_suspicious_patterns(self) -> List[Dict[str, Any]]:
        """Detect suspicious activity patterns"""
        suspicious_patterns = []
        
        if len(self.events) < 10:
            return suspicious_patterns
        
        recent_events = self.events[-100:]  # Check last 100 events
        
        # Pattern 1: Too many failed wallet access attempts
        failed_wallet_access = [
            e for e in recent_events 
            if e.event_type == SecurityEventType.WALLET_ACCESS 
            and e.additional_data 
            and not e.additional_data.get('success', True)
        ]
        
        if len(failed_wallet_access) > 5:
            suspicious_patterns.append({
                'pattern': 'multiple_failed_wallet_access',
                'count': len(failed_wallet_access),
                'severity': 'high',
                'description': f'{len(failed_wallet_access)} failed wallet access attempts'
            })
        
        # Pattern 2: Rapid transaction signing
        transaction_events = [
            e for e in recent_events 
            if e.event_type == SecurityEventType.TRANSACTION_SIGNED
        ]
        
        if len(transaction_events) > 20:
            time_span = transaction_events[-1].timestamp - transaction_events[0].timestamp
            if time_span < 300:  # 5 minutes
                suspicious_patterns.append({
                    'pattern': 'rapid_transaction_signing',
                    'count': len(transaction_events),
                    'time_span': time_span,
                    'severity': 'medium',
                    'description': f'{len(transaction_events)} transactions in {time_span:.1f} seconds'
                })
        
        # Pattern 3: Multiple token validation failures
        failed_validations = [
            e for e in recent_events 
            if e.event_type == SecurityEventType.TOKEN_VALIDATION 
            and e.additional_data 
            and not e.additional_data.get('validation_result', True)
        ]
        
        if len(failed_validations) > 10:
            suspicious_patterns.append({
                'pattern': 'multiple_token_validation_failures',
                'count': len(failed_validations),
                'severity': 'medium',
                'description': f'{len(failed_validations)} token validation failures'
            })
        
        return suspicious_patterns
    
    def _mask_sensitive_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data in event logs"""
        masked_data = event_data.copy()
        
        # Mask wallet addresses
        if 'wallet_address' in masked_data and masked_data['wallet_address']:
            masked_data['wallet_address'] = self._mask_address(masked_data['wallet_address'])
        
        # Mask transaction hashes
        if 'transaction_hash' in masked_data and masked_data['transaction_hash']:
            masked_data['transaction_hash'] = self._mask_hash(masked_data['transaction_hash'])
        
        # Mask token addresses
        if 'token_address' in masked_data and masked_data['token_address']:
            masked_data['token_address'] = self._mask_address(masked_data['token_address'])
        
        return masked_data
    
    def _mask_address(self, address: str) -> str:
        """Mask address for logging"""
        if not address or len(address) < 8:
            return "****"
        return f"{address[:4]}...{address[-4:]}"
    
    def _mask_hash(self, hash_value: str) -> str:
        """Mask hash for logging"""
        if not hash_value or len(hash_value) < 16:
            return "****"
        return f"{hash_value[:8]}...{hash_value[-8:]}"
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security audit summary"""
        if not self.events:
            return {'total_events': 0, 'summary': 'No security events recorded'}
        
        # Count events by type
        event_counts = {}
        level_counts = {}
        
        for event in self.events:
            event_type = event.event_type.value
            level = event.level.value
            
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Get recent suspicious patterns
        suspicious_patterns = self.detect_suspicious_patterns()
        
        return {
            'total_events': len(self.events),
            'event_counts': event_counts,
            'level_counts': level_counts,
            'suspicious_patterns': len(suspicious_patterns),
            'recent_patterns': suspicious_patterns,
            'audit_log_path': str(self.audit_log_path),
            'audit_logging_enabled': self.security_config.enable_audit_logging
        }
    
    def export_security_report(self, output_path: str, hours: int = 24) -> bool:
        """Export security report for specified time period"""
        try:
            cutoff_time = time.time() - (hours * 3600)
            recent_events = [e for e in self.events if e.timestamp >= cutoff_time]
            
            report = {
                'report_generated': time.time(),
                'time_period_hours': hours,
                'total_events': len(recent_events),
                'events': [e.to_dict() for e in recent_events],
                'summary': self.get_security_summary(),
                'suspicious_patterns': self.detect_suspicious_patterns()
            }
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Security report exported to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export security report: {e}")
            return False