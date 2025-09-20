"""
Configuration management for NautilusTrader POC with multi-environment support
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging
import base64

# Optional cryptography import for encryption (not required for POC)
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    Fernet = None

logger = logging.getLogger(__name__)

@dataclass
class Q50Config:
    """Q50 signal configuration"""
    features_path: str
    signal_tolerance_minutes: int
    required_columns: List[str]
    backup_features_path: str = ""
    signal_cache_ttl_minutes: int = 60

@dataclass
class WalletConfig:
    """Wallet configuration with security features"""
    payer_public_key: str = ""
    private_key_path: str = ""
    private_key_env_var: str = ""
    wallet_password_env_var: str = ""
    validate_balance_before_trade: bool = True
    min_balance_sol: float = 0.1
    balance_check_interval_minutes: int = 5

@dataclass
class TradingConfig:
    """Trading parameters configuration"""
    kelly_multiplier: float = 1.0
    max_portfolio_risk: float = 0.2
    position_concentration_limit: float = 0.1
    order_timeout_seconds: int = 30
    confirmation_timeout_seconds: int = 60
    max_gas_price_lamports: int = 5000
    stop_loss_percent: float = 20.0
    take_profit_percent: float = 50.0
    position_timeout_hours: int = 24
    max_consecutive_losses: int = 5

@dataclass
class PumpSwapConfig:
    """PumpSwap trading configuration"""
    max_slippage_percent: float
    base_position_size: float
    max_position_size: float
    min_liquidity_sol: float
    max_price_impact_percent: float
    realistic_transaction_cost: float

@dataclass
class SolanaConfig:
    """Solana blockchain configuration"""
    network: str
    rpc_endpoint: str
    commitment: str
    cluster: str

@dataclass
class SecurityConfig:
    """Security configuration"""
    validate_token_addresses: bool = True
    require_transaction_confirmation: bool = True
    enable_circuit_breaker: bool = True
    max_daily_trades: int = 500
    wallet_balance_alert_threshold: float = 1.0
    token_blacklist_path: str = "security/token_blacklist.json"
    token_whitelist_path: str = "security/token_whitelist.json"
    enable_token_metadata_validation: bool = True
    max_transaction_retries: int = 3
    transaction_signature_validation: bool = True
    enable_audit_logging: bool = True
    audit_log_path: str = "logs/security_audit.log"
    sensitive_data_masking: bool = True
    max_trades_per_minute: int = 10
    max_trades_per_hour: int = 100
    max_trades_per_day: int = 500

@dataclass
class NautilusConfig:
    """NautilusTrader configuration"""
    instance_id: str
    log_level: str
    cache_database_path: str
    strategy_config: Dict[str, Any] = field(default_factory=dict)
    data_engine_config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EnvironmentConfig:
    """Environment-specific configuration"""
    solana: SolanaConfig
    pumpswap: PumpSwapConfig
    security: SecurityConfig

@dataclass
class NautilusPOCConfig:
    """Complete NautilusTrader POC configuration"""
    environment: str
    environments: Dict[str, EnvironmentConfig]
    q50: Q50Config
    wallet: WalletConfig
    trading: TradingConfig
    nautilus: NautilusConfig
    monitoring: Dict[str, Any]
    error_handling: Dict[str, Any]
    security: SecurityConfig
    regime_detection: Dict[str, Any]
    
    def get_current_env_config(self) -> EnvironmentConfig:
        """Get configuration for current environment"""
        return self.environments.get(self.environment, self.environments.get('testnet'))

class ConfigManager:
    """Enhanced configuration manager for NautilusTrader POC with multi-environment support"""
    
    def __init__(self, config_path: Optional[str] = None, environment: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config.yaml")
        self.environment = environment or os.getenv('NAUTILUS_ENVIRONMENT', 'testnet')
        self.config_data = {}
        self.security_manager = SecurityManager()
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            
            # Validate environment exists
            nautilus_data = self.config_data.get('nautilus_poc', {})
            environments = nautilus_data.get('environments', {})
            if self.environment not in environments:
                logger.warning(f"Environment '{self.environment}' not found in config, falling back to 'testnet'")
                self.environment = 'testnet'
                
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.config_data = {}
    
    def get_nautilus_config(self) -> NautilusPOCConfig:
        """Get NautilusTrader POC configuration with environment-specific settings"""
        nautilus_data = self.config_data.get('nautilus_poc', {})
        
        # Apply environment variable overrides
        self._apply_env_overrides(nautilus_data)
        
        # Get environment-specific configuration
        current_env = self.environment
        env_configs = {}
        
        for env_name, env_data in nautilus_data.get('environments', {}).items():
            solana_config = SolanaConfig(
                network=env_data.get('solana', {}).get('network', 'testnet'),
                rpc_endpoint=env_data.get('solana', {}).get('rpc_endpoint', 'https://api.testnet.solana.com'),
                commitment=env_data.get('solana', {}).get('commitment', 'confirmed'),
                cluster=env_data.get('solana', {}).get('cluster', 'testnet')
            )
            
            pumpswap_config = PumpSwapConfig(
                max_slippage_percent=env_data.get('pumpswap', {}).get('max_slippage_percent', 5.0),
                base_position_size=env_data.get('pumpswap', {}).get('base_position_size', 0.1),
                max_position_size=env_data.get('pumpswap', {}).get('max_position_size', 0.5),
                min_liquidity_sol=env_data.get('pumpswap', {}).get('min_liquidity_sol', 10.0),
                max_price_impact_percent=env_data.get('pumpswap', {}).get('max_price_impact_percent', 10.0),
                realistic_transaction_cost=env_data.get('pumpswap', {}).get('realistic_transaction_cost', 0.0005)
            )
            
            security_config = SecurityConfig(
                validate_token_addresses=env_data.get('security', {}).get('validate_token_addresses', True),
                require_transaction_confirmation=env_data.get('security', {}).get('require_transaction_confirmation', True),
                enable_circuit_breaker=env_data.get('security', {}).get('enable_circuit_breaker', True),
                max_daily_trades=env_data.get('security', {}).get('max_daily_trades', 500),
                wallet_balance_alert_threshold=env_data.get('security', {}).get('wallet_balance_alert_threshold', 1.0)
            )
            
            env_configs[env_name] = EnvironmentConfig(
                solana=solana_config,
                pumpswap=pumpswap_config,
                security=security_config
            )
        
        # Create configuration objects
        q50_config = Q50Config(
            features_path=nautilus_data.get('q50', {}).get('features_path', 'data3/macro_features.pkl'),
            signal_tolerance_minutes=nautilus_data.get('q50', {}).get('signal_tolerance_minutes', 5),
            required_columns=nautilus_data.get('q50', {}).get('required_columns', []),
            backup_features_path=nautilus_data.get('q50', {}).get('backup_features_path', ''),
            signal_cache_ttl_minutes=nautilus_data.get('q50', {}).get('signal_cache_ttl_minutes', 60)
        )
        
        wallet_config = WalletConfig(
            payer_public_key=nautilus_data.get('wallet', {}).get('payer_public_key', ''),
            private_key_path=nautilus_data.get('wallet', {}).get('private_key_path', ''),
            private_key_env_var=nautilus_data.get('wallet', {}).get('private_key_env_var', ''),
            wallet_password_env_var=nautilus_data.get('wallet', {}).get('wallet_password_env_var', ''),
            validate_balance_before_trade=nautilus_data.get('wallet', {}).get('validate_balance_before_trade', True),
            min_balance_sol=nautilus_data.get('wallet', {}).get('min_balance_sol', 0.1),
            balance_check_interval_minutes=nautilus_data.get('wallet', {}).get('balance_check_interval_minutes', 5)
        )
        
        trading_config = TradingConfig(
            kelly_multiplier=nautilus_data.get('trading', {}).get('kelly_multiplier', 1.0),
            max_portfolio_risk=nautilus_data.get('trading', {}).get('max_portfolio_risk', 0.2),
            position_concentration_limit=nautilus_data.get('trading', {}).get('position_concentration_limit', 0.1),
            order_timeout_seconds=nautilus_data.get('trading', {}).get('order_timeout_seconds', 30),
            confirmation_timeout_seconds=nautilus_data.get('trading', {}).get('confirmation_timeout_seconds', 60),
            max_gas_price_lamports=nautilus_data.get('trading', {}).get('max_gas_price_lamports', 5000),
            stop_loss_percent=nautilus_data.get('trading', {}).get('stop_loss_percent', 20.0),
            take_profit_percent=nautilus_data.get('trading', {}).get('take_profit_percent', 50.0),
            position_timeout_hours=nautilus_data.get('trading', {}).get('position_timeout_hours', 24),
            max_consecutive_losses=nautilus_data.get('trading', {}).get('max_consecutive_losses', 5)
        )
        
        nautilus_config = NautilusConfig(
            instance_id=nautilus_data.get('nautilus', {}).get('instance_id', 'NAUTILUS-001'),
            log_level=nautilus_data.get('nautilus', {}).get('log_level', 'INFO'),
            cache_database_path=nautilus_data.get('nautilus', {}).get('cache_database_path', 'cache.db'),
            strategy_config=nautilus_data.get('nautilus', {}).get('strategy_config', {}),
            data_engine_config=nautilus_data.get('nautilus', {}).get('data_engine_config', {})
        )
        
        # Global security config (merged with environment-specific)
        global_security = nautilus_data.get('security', {})
        security_config = SecurityConfig(
            validate_token_addresses=global_security.get('validate_token_addresses', True),
            token_blacklist_path=global_security.get('token_blacklist_path', 'security/token_blacklist.json'),
            token_whitelist_path=global_security.get('token_whitelist_path', 'security/token_whitelist.json'),
            enable_token_metadata_validation=global_security.get('enable_token_metadata_validation', True),
            require_transaction_confirmation=global_security.get('require_transaction_confirmation', True),
            max_transaction_retries=global_security.get('max_transaction_retries', 3),
            transaction_signature_validation=global_security.get('transaction_signature_validation', True),
            enable_audit_logging=global_security.get('enable_audit_logging', True),
            audit_log_path=global_security.get('audit_log_path', 'logs/security_audit.log'),
            sensitive_data_masking=global_security.get('sensitive_data_masking', True),
            max_trades_per_minute=global_security.get('max_trades_per_minute', 10),
            max_trades_per_hour=global_security.get('max_trades_per_hour', 100),
            max_trades_per_day=global_security.get('max_trades_per_day', 500)
        )
        
        return NautilusPOCConfig(
            environment=current_env,
            environments=env_configs,
            q50=q50_config,
            wallet=wallet_config,
            trading=trading_config,
            nautilus=nautilus_config,
            monitoring=nautilus_data.get('monitoring', {}),
            error_handling=nautilus_data.get('error_handling', {}),
            security=security_config,
            regime_detection=nautilus_data.get('regime_detection', {})
        )
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> None:
        """Apply environment variable overrides with enhanced security"""
        env_mappings = {
            # Wallet configuration (security-sensitive)
            'NAUTILUS_PAYER_PUBLIC_KEY': ['wallet', 'payer_public_key'],
            'NAUTILUS_PRIVATE_KEY_PATH': ['wallet', 'private_key_path'],
            'NAUTILUS_PRIVATE_KEY_ENV_VAR': ['wallet', 'private_key_env_var'],
            'NAUTILUS_WALLET_PASSWORD_ENV_VAR': ['wallet', 'wallet_password_env_var'],
            
            # Environment selection
            'NAUTILUS_ENVIRONMENT': ['environment'],
            
            # Trading parameters
            'NAUTILUS_MAX_POSITION_SIZE': ['trading', 'max_portfolio_risk'],
            'NAUTILUS_KELLY_MULTIPLIER': ['trading', 'kelly_multiplier'],
            'NAUTILUS_STOP_LOSS_PERCENT': ['trading', 'stop_loss_percent'],
            'NAUTILUS_TAKE_PROFIT_PERCENT': ['trading', 'take_profit_percent'],
            
            # NautilusTrader configuration
            'NAUTILUS_LOG_LEVEL': ['nautilus', 'log_level'],
            'NAUTILUS_INSTANCE_ID': ['nautilus', 'instance_id'],
            'NAUTILUS_CACHE_DB_PATH': ['nautilus', 'cache_database_path'],
            
            # Monitoring
            'NAUTILUS_ENABLE_PERFORMANCE_TRACKING': ['monitoring', 'enable_performance_tracking'],
            'NAUTILUS_LOG_SIGNAL_PROCESSING': ['monitoring', 'log_signal_processing'],
            'NAUTILUS_LOG_TRADE_EXECUTION': ['monitoring', 'log_trade_execution'],
            
            # Security
            'NAUTILUS_VALIDATE_TOKEN_ADDRESSES': ['security', 'validate_token_addresses'],
            'NAUTILUS_ENABLE_CIRCUIT_BREAKER': ['security', 'enable_circuit_breaker'],
            'NAUTILUS_MAX_DAILY_TRADES': ['security', 'max_daily_trades'],
            'NAUTILUS_ENABLE_AUDIT_LOGGING': ['security', 'enable_audit_logging'],
            
            # Q50 configuration
            'NAUTILUS_Q50_FEATURES_PATH': ['q50', 'features_path'],
            'NAUTILUS_Q50_BACKUP_PATH': ['q50', 'backup_features_path'],
            'NAUTILUS_Q50_SIGNAL_TOLERANCE': ['q50', 'signal_tolerance_minutes'],
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value:
                # Navigate to the nested config location
                current = config_data
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Convert value to appropriate type
                if env_var in [
                    'NAUTILUS_MAX_POSITION_SIZE', 'NAUTILUS_KELLY_MULTIPLIER', 
                    'NAUTILUS_STOP_LOSS_PERCENT', 'NAUTILUS_TAKE_PROFIT_PERCENT'
                ]:
                    env_value = float(env_value)
                elif env_var in [
                    'NAUTILUS_Q50_SIGNAL_TOLERANCE', 'NAUTILUS_MAX_DAILY_TRADES'
                ]:
                    env_value = int(env_value)
                elif env_var in [
                    'NAUTILUS_ENABLE_PERFORMANCE_TRACKING', 'NAUTILUS_LOG_SIGNAL_PROCESSING',
                    'NAUTILUS_LOG_TRADE_EXECUTION', 'NAUTILUS_VALIDATE_TOKEN_ADDRESSES',
                    'NAUTILUS_ENABLE_CIRCUIT_BREAKER', 'NAUTILUS_ENABLE_AUDIT_LOGGING'
                ]:
                    env_value = env_value.lower() in ('true', '1', 'yes')
                
                # Handle special case for top-level environment setting
                if len(config_path) == 1:
                    config_data[config_path[0]] = env_value
                else:
                    current[config_path[-1]] = env_value
                
                # Log override (mask sensitive values)
                if 'KEY' in env_var or 'PASSWORD' in env_var:
                    logger.info(f"Applied environment override: {env_var} = [MASKED]")
                else:
                    logger.info(f"Applied environment override: {env_var} = {env_value}")
    
    def switch_environment(self, new_environment: str) -> bool:
        """Switch to a different environment configuration"""
        nautilus_data = self.config_data.get('nautilus_poc', {})
        environments = nautilus_data.get('environments', {})
        
        if new_environment not in environments:
            logger.error(f"Environment '{new_environment}' not found in configuration")
            return False
        
        self.environment = new_environment
        logger.info(f"Switched to environment: {new_environment}")
        return True
    
    def get_available_environments(self) -> List[str]:
        """Get list of available environments"""
        nautilus_data = self.config_data.get('nautilus_poc', {})
        return list(nautilus_data.get('environments', {}).keys())
    
    def export_environment_config(self, environment: str, output_path: str) -> bool:
        """Export environment-specific configuration to file"""
        try:
            config = self.get_nautilus_config()
            env_config = config.environments.get(environment)
            
            if not env_config:
                logger.error(f"Environment '{environment}' not found")
                return False
            
            # Convert to dictionary for export
            export_data = {
                'environment': environment,
                'solana': {
                    'network': env_config.solana.network,
                    'rpc_endpoint': env_config.solana.rpc_endpoint,
                    'commitment': env_config.solana.commitment,
                    'cluster': env_config.solana.cluster
                },
                'pumpswap': {
                    'max_slippage_percent': env_config.pumpswap.max_slippage_percent,
                    'base_position_size': env_config.pumpswap.base_position_size,
                    'max_position_size': env_config.pumpswap.max_position_size,
                    'min_liquidity_sol': env_config.pumpswap.min_liquidity_sol,
                    'max_price_impact_percent': env_config.pumpswap.max_price_impact_percent,
                    'realistic_transaction_cost': env_config.pumpswap.realistic_transaction_cost
                },
                'security': {
                    'validate_token_addresses': env_config.security.validate_token_addresses,
                    'require_transaction_confirmation': env_config.security.require_transaction_confirmation,
                    'enable_circuit_breaker': env_config.security.enable_circuit_breaker,
                    'max_daily_trades': env_config.security.max_daily_trades,
                    'wallet_balance_alert_threshold': env_config.security.wallet_balance_alert_threshold
                }
            }
            
            with open(output_path, 'w') as f:
                yaml.dump(export_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"Environment configuration exported to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export environment configuration: {e}")
            return False
    
    def validate_config(self, config: NautilusPOCConfig) -> bool:
        """Validate configuration completeness and security"""
        errors = []
        warnings = []
        
        # Validate Q50 configuration
        if not config.q50.features_path:
            errors.append("Q50 features_path is required")
        elif not Path(config.q50.features_path).exists():
            warnings.append(f"Q50 features file not found: {config.q50.features_path}")
        
        if not config.q50.required_columns:
            errors.append("Q50 required_columns list is empty")
        
        # Validate wallet configuration
        wallet_config_sources = 0
        if config.wallet.payer_public_key:
            warnings.append("Wallet public key should be set via environment variable for security")
        if config.wallet.private_key_path:
            warnings.append("Private key path should be set via environment variable for security")
        if config.wallet.private_key_env_var:
            wallet_config_sources += 1
        if config.wallet.private_key_path:
            wallet_config_sources += 1
            
        if wallet_config_sources == 0:
            errors.append("No wallet configuration found - set NAUTILUS_PRIVATE_KEY_PATH or NAUTILUS_PRIVATE_KEY_ENV_VAR")
        elif wallet_config_sources > 1:
            warnings.append("Multiple wallet configuration sources found - private key path takes precedence")
        
        # Validate environment configuration
        current_env_config = config.get_current_env_config()
        if not current_env_config:
            errors.append(f"Environment configuration not found for: {config.environment}")
        else:
            # Validate Solana configuration
            if not current_env_config.solana.rpc_endpoint:
                errors.append("Solana rpc_endpoint is required")
            
            # Validate PumpSwap configuration
            if current_env_config.pumpswap.max_position_size > 1.0:
                warnings.append("Max position size > 100% of capital - this may be risky")
            
            if current_env_config.pumpswap.max_slippage_percent > 20.0:
                warnings.append("Max slippage > 20% - this may result in poor execution")
        
        # Validate security configuration
        if not config.security.validate_token_addresses:
            warnings.append("Token address validation is disabled - this may be risky")
        
        if not config.security.enable_audit_logging:
            warnings.append("Audit logging is disabled - this reduces security monitoring")
        
        # Validate trading configuration
        if config.trading.max_portfolio_risk > 0.5:
            warnings.append("Max portfolio risk > 50% - this may be very risky")
        
        if config.trading.position_concentration_limit > 0.2:
            warnings.append("Position concentration limit > 20% - this may increase risk")
        
        # Validate NautilusTrader configuration
        if not config.nautilus.instance_id:
            errors.append("NautilusTrader instance_id is required")
        
        # Log results
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  ERROR: {error}")
        
        if warnings:
            logger.warning("Configuration validation warnings:")
            for warning in warnings:
                logger.warning(f"  WARNING: {warning}")
        
        if not errors:
            logger.info("Configuration validation passed")
            if warnings:
                logger.info(f"Configuration loaded with {len(warnings)} warnings")
        
        return len(errors) == 0


class SecurityManager:
    """Security manager for handling sensitive configuration data"""
    
    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key) if self.encryption_key else None
    
    def _get_or_create_encryption_key(self) -> Optional[bytes]:
        """Get or create encryption key for sensitive data"""
        if not ENCRYPTION_AVAILABLE:
            logger.info("Cryptography library not available - encryption disabled for POC")
            return None
            
        key_env = os.getenv('NAUTILUS_ENCRYPTION_KEY')
        if key_env:
            try:
                return base64.urlsafe_b64decode(key_env.encode())
            except Exception as e:
                logger.warning(f"Invalid encryption key in environment: {e}")
        
        # For POC, we'll skip encryption but log the recommendation
        logger.info("No encryption key found - sensitive data will not be encrypted")
        logger.info("Set NAUTILUS_ENCRYPTION_KEY environment variable for production use")
        return None
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data if encryption is available"""
        if not self.fernet:
            return data
        
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt sensitive data: {e}")
            return data
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data if encryption is available"""
        if not self.fernet:
            return encrypted_data
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt sensitive data: {e}")
            return encrypted_data
    
    def load_private_key_from_env(self, env_var_name: str) -> Optional[str]:
        """Safely load private key from environment variable"""
        if not env_var_name:
            return None
        
        private_key = os.getenv(env_var_name)
        if not private_key:
            logger.warning(f"Private key environment variable '{env_var_name}' not found")
            return None
        
        # Basic validation - check if it looks like a private key
        if len(private_key) < 32:
            logger.error(f"Private key from '{env_var_name}' appears to be too short")
            return None
        
        logger.info(f"Private key loaded from environment variable: {env_var_name}")
        return private_key
    
    def load_private_key_from_file(self, file_path: str, password_env_var: Optional[str] = None) -> Optional[str]:
        """Safely load private key from file"""
        if not file_path or not Path(file_path).exists():
            logger.error(f"Private key file not found: {file_path}")
            return None
        
        try:
            with open(file_path, 'r') as f:
                private_key_data = f.read().strip()
            
            # If password is required, get it from environment
            if password_env_var:
                password = os.getenv(password_env_var)
                if not password:
                    logger.error(f"Password environment variable '{password_env_var}' not found")
                    return None
                # In a real implementation, you would decrypt the private key here
                logger.info("Password-protected private key loading not implemented in POC")
            
            logger.info(f"Private key loaded from file: {file_path}")
            return private_key_data
            
        except Exception as e:
            logger.error(f"Failed to load private key from file '{file_path}': {e}")
            return None
    
    def validate_token_address(self, token_address: str, whitelist_path: Optional[str] = None, 
                             blacklist_path: Optional[str] = None) -> bool:
        """Validate token address against whitelist/blacklist"""
        if not token_address:
            return False
        
        # Basic format validation for Solana addresses
        if len(token_address) < 32 or len(token_address) > 44:
            logger.warning(f"Token address has invalid length: {token_address}")
            return False
        
        # Check blacklist
        if blacklist_path and Path(blacklist_path).exists():
            try:
                with open(blacklist_path, 'r') as f:
                    blacklist = json.load(f)
                if token_address in blacklist.get('addresses', []):
                    logger.error(f"Token address is blacklisted: {token_address}")
                    return False
            except Exception as e:
                logger.warning(f"Failed to load blacklist: {e}")
        
        # Check whitelist (if exists, only allow whitelisted addresses)
        if whitelist_path and Path(whitelist_path).exists():
            try:
                with open(whitelist_path, 'r') as f:
                    whitelist = json.load(f)
                if token_address not in whitelist.get('addresses', []):
                    logger.warning(f"Token address not in whitelist: {token_address}")
                    return False
            except Exception as e:
                logger.warning(f"Failed to load whitelist: {e}")
        
        return True
    
    def mask_sensitive_value(self, value: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Mask sensitive values for logging"""
        if not value or len(value) <= visible_chars * 2:
            return mask_char * 8
        
        return value[:visible_chars] + mask_char * (len(value) - visible_chars * 2) + value[-visible_chars:]


# Global configuration instance
config_manager = ConfigManager()