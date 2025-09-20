"""
Wallet management for NautilusTrader POC with security features
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import time
from decimal import Decimal

logger = logging.getLogger(__name__)

@dataclass
class WalletBalance:
    """Wallet balance information"""
    sol_balance: float
    token_balances: Dict[str, float]
    last_updated: float
    is_valid: bool = True

@dataclass
class WalletAlert:
    """Wallet alert information"""
    alert_type: str
    message: str
    timestamp: float
    severity: str  # 'info', 'warning', 'error', 'critical'
    wallet_address: str

class WalletManager:
    """Secure wallet management for NautilusTrader POC"""
    
    def __init__(self, config):
        self.config = config
        self.wallet_config = config.wallet
        self.security_config = config.security
        self.current_env = config.get_current_env_config()
        
        self._private_key = None
        self._public_key = None
        self._last_balance_check = 0
        self._cached_balance = None
        self._alerts = []
        
        # Initialize wallet
        self._initialize_wallet()
    
    def _initialize_wallet(self) -> bool:
        """Initialize wallet with secure key loading"""
        try:
            # Load private key from environment variable or file
            if self.wallet_config.private_key_env_var:
                self._private_key = self._load_private_key_from_env(
                    self.wallet_config.private_key_env_var
                )
            elif self.wallet_config.private_key_path:
                self._private_key = self._load_private_key_from_file(
                    self.wallet_config.private_key_path,
                    self.wallet_config.wallet_password_env_var
                )
            
            if not self._private_key:
                logger.error("Failed to load private key - wallet initialization failed")
                return False
            
            # Load public key
            self._public_key = self.wallet_config.payer_public_key or os.getenv('NAUTILUS_PAYER_PUBLIC_KEY')
            
            if not self._public_key:
                logger.error("Public key not found - set NAUTILUS_PAYER_PUBLIC_KEY environment variable")
                return False
            
            logger.info(f"Wallet initialized successfully: {self._mask_address(self._public_key)}")
            return True
            
        except Exception as e:
            logger.error(f"Wallet initialization failed: {e}")
            return False
    
    def _load_private_key_from_env(self, env_var_name: str) -> Optional[str]:
        """Load private key from environment variable"""
        private_key = os.getenv(env_var_name)
        if not private_key:
            logger.error(f"Private key environment variable '{env_var_name}' not found")
            return None
        
        # Basic validation
        if len(private_key) < 32:
            logger.error(f"Private key from '{env_var_name}' appears to be too short")
            return None
        
        logger.info(f"Private key loaded from environment: {env_var_name}")
        return private_key
    
    def _load_private_key_from_file(self, file_path: str, password_env_var: Optional[str] = None) -> Optional[str]:
        """Load private key from file with optional password"""
        if not Path(file_path).exists():
            logger.error(f"Private key file not found: {file_path}")
            return None
        
        try:
            with open(file_path, 'r') as f:
                key_data = f.read().strip()
            
            # Handle password-protected keys
            if password_env_var:
                password = os.getenv(password_env_var)
                if not password:
                    logger.error(f"Password environment variable '{password_env_var}' not found")
                    return None
                # In production, implement actual key decryption here
                logger.info("Password-protected key loading (decryption not implemented in POC)")
            
            logger.info(f"Private key loaded from file: {file_path}")
            return key_data
            
        except Exception as e:
            logger.error(f"Failed to load private key from file: {e}")
            return None
    
    def get_public_key(self) -> Optional[str]:
        """Get wallet public key"""
        return self._public_key
    
    def get_private_key(self) -> Optional[str]:
        """Get wallet private key (use with caution)"""
        if not self._private_key:
            logger.error("Private key not available")
            return None
        return self._private_key
    
    def validate_wallet_setup(self) -> bool:
        """Validate wallet is properly configured"""
        if not self._private_key or not self._public_key:
            logger.error("Wallet not properly initialized")
            return False
        
        # Additional validation could include:
        # - Key pair validation
        # - Network connectivity test
        # - Balance check
        
        return True
    
    def check_balance(self, force_refresh: bool = False) -> Optional[WalletBalance]:
        """Check wallet balance with caching"""
        current_time = time.time()
        cache_ttl = self.wallet_config.balance_check_interval_minutes * 60
        
        # Use cached balance if available and not expired
        if (not force_refresh and 
            self._cached_balance and 
            current_time - self._last_balance_check < cache_ttl):
            return self._cached_balance
        
        try:
            # In a real implementation, this would query the Solana RPC
            # For POC, we'll simulate balance checking
            balance = self._simulate_balance_check()
            
            self._cached_balance = balance
            self._last_balance_check = current_time
            
            # Check for balance alerts
            self._check_balance_alerts(balance)
            
            return balance
            
        except Exception as e:
            logger.error(f"Failed to check wallet balance: {e}")
            return None
    
    def _simulate_balance_check(self) -> WalletBalance:
        """Simulate balance check for POC"""
        # In production, this would make actual RPC calls
        return WalletBalance(
            sol_balance=10.5,  # Simulated SOL balance
            token_balances={
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 1000.0  # Simulated USDC
            },
            last_updated=time.time(),
            is_valid=True
        )
    
    def _check_balance_alerts(self, balance: WalletBalance) -> None:
        """Check for balance-related alerts"""
        if not balance.is_valid:
            self._add_alert("balance_check_failed", "Failed to retrieve wallet balance", "error")
            return
        
        # Check minimum balance threshold
        threshold = self.current_env.security.wallet_balance_alert_threshold
        if balance.sol_balance < threshold:
            self._add_alert(
                "low_balance",
                f"Wallet balance ({balance.sol_balance} SOL) below threshold ({threshold} SOL)",
                "warning"
            )
        
        # Check if balance is critically low
        min_balance = self.wallet_config.min_balance_sol
        if balance.sol_balance < min_balance:
            self._add_alert(
                "critical_low_balance",
                f"Wallet balance ({balance.sol_balance} SOL) below minimum ({min_balance} SOL)",
                "critical"
            )
    
    def _add_alert(self, alert_type: str, message: str, severity: str) -> None:
        """Add wallet alert"""
        alert = WalletAlert(
            alert_type=alert_type,
            message=message,
            timestamp=time.time(),
            severity=severity,
            wallet_address=self._mask_address(self._public_key or "unknown")
        )
        
        self._alerts.append(alert)
        
        # Log alert
        log_method = getattr(logger, severity, logger.info)
        log_method(f"Wallet Alert [{alert_type}]: {message}")
        
        # Keep only recent alerts (last 100)
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]
    
    def get_recent_alerts(self, max_alerts: int = 10) -> list:
        """Get recent wallet alerts"""
        return self._alerts[-max_alerts:] if self._alerts else []
    
    def clear_alerts(self) -> None:
        """Clear all wallet alerts"""
        self._alerts.clear()
        logger.info("Wallet alerts cleared")
    
    def validate_transaction_parameters(self, transaction_params: Dict[str, Any]) -> bool:
        """Validate transaction parameters before signing"""
        try:
            # Basic parameter validation
            required_params = ['mint', 'amount', 'recipient']
            for param in required_params:
                if param not in transaction_params:
                    logger.error(f"Missing required transaction parameter: {param}")
                    return False
            
            # Validate token address if security is enabled
            if self.security_config.validate_token_addresses:
                mint_address = transaction_params.get('mint')
                if not self._validate_token_address(mint_address):
                    logger.error(f"Token address validation failed: {mint_address}")
                    return False
            
            # Validate amount
            amount = transaction_params.get('amount', 0)
            if amount <= 0:
                logger.error(f"Invalid transaction amount: {amount}")
                return False
            
            # Check if we have sufficient balance
            balance = self.check_balance()
            if balance and balance.sol_balance < amount:
                logger.error(f"Insufficient balance: {balance.sol_balance} < {amount}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Transaction parameter validation failed: {e}")
            return False
    
    def _validate_token_address(self, token_address: str) -> bool:
        """Validate token address against security policies"""
        if not token_address:
            return False
        
        # Basic format validation for Solana addresses
        if len(token_address) < 32 or len(token_address) > 44:
            return False
        
        # Check against blacklist/whitelist (simplified for POC)
        blacklist_path = self.security_config.token_blacklist_path
        if blacklist_path and Path(blacklist_path).exists():
            try:
                with open(blacklist_path, 'r') as f:
                    blacklist_data = json.load(f)
                if token_address in blacklist_data.get('addresses', []):
                    return False
            except Exception as e:
                logger.warning(f"Failed to check token blacklist: {e}")
        
        return True
    
    def sign_transaction(self, transaction_data: Dict[str, Any]) -> Optional[str]:
        """Sign transaction with security validation"""
        if not self.validate_transaction_parameters(transaction_data):
            logger.error("Transaction validation failed - refusing to sign")
            return None
        
        if not self._private_key:
            logger.error("Private key not available for signing")
            return None
        
        try:
            # In production, this would use actual Solana transaction signing
            # For POC, we'll simulate the signing process
            signature = self._simulate_transaction_signing(transaction_data)
            
            if signature:
                logger.info(f"Transaction signed successfully: {signature[:16]}...")
                
                # Log transaction for audit
                if self.security_config.enable_audit_logging:
                    self._log_transaction_audit(transaction_data, signature)
            
            return signature
            
        except Exception as e:
            logger.error(f"Transaction signing failed: {e}")
            return None
    
    def _simulate_transaction_signing(self, transaction_data: Dict[str, Any]) -> str:
        """Simulate transaction signing for POC"""
        # In production, this would use actual cryptographic signing
        import hashlib
        import time
        
        # Create a simulated signature
        data_str = json.dumps(transaction_data, sort_keys=True)
        timestamp = str(int(time.time()))
        signature_input = f"{data_str}{timestamp}{self._public_key}"
        
        signature = hashlib.sha256(signature_input.encode()).hexdigest()
        return signature
    
    def _log_transaction_audit(self, transaction_data: Dict[str, Any], signature: str) -> None:
        """Log transaction for security audit"""
        audit_entry = {
            'timestamp': time.time(),
            'wallet_address': self._mask_address(self._public_key),
            'transaction_type': transaction_data.get('type', 'unknown'),
            'mint_address': transaction_data.get('mint', 'unknown'),
            'amount': transaction_data.get('amount', 0),
            'signature': signature[:16] + '...',  # Truncated signature
            'environment': self.config.environment
        }
        
        # In production, this would write to a secure audit log
        logger.info(f"Transaction audit: {audit_entry}")
    
    def _mask_address(self, address: str) -> str:
        """Mask address for logging"""
        if not address or len(address) < 8:
            return "****"
        return f"{address[:4]}...{address[-4:]}"
    
    def get_wallet_info(self) -> Dict[str, Any]:
        """Get wallet information for monitoring"""
        balance = self.check_balance()
        
        return {
            'public_key': self._mask_address(self._public_key or "unknown"),
            'network': self.current_env.solana.network,
            'balance_sol': balance.sol_balance if balance else 0,
            'balance_valid': balance.is_valid if balance else False,
            'last_balance_check': self._last_balance_check,
            'alert_count': len(self._alerts),
            'recent_alerts': [alert.alert_type for alert in self.get_recent_alerts(5)]
        }