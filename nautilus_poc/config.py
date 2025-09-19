"""
Configuration management for NautilusTrader POC
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Q50Config:
    """Q50 signal configuration"""
    features_path: str
    signal_tolerance_minutes: int
    required_columns: list

@dataclass
class PumpSwapConfig:
    """PumpSwap trading configuration"""
    payer_public_key: str
    private_key_path: str
    max_slippage_percent: float
    base_position_size: float
    max_position_size: float
    min_liquidity_sol: float
    max_price_impact_percent: float
    stop_loss_percent: float
    position_timeout_hours: int

@dataclass
class SolanaConfig:
    """Solana blockchain configuration"""
    network: str
    rpc_endpoint: str
    commitment: str

@dataclass
class NautilusConfig:
    """NautilusTrader configuration"""
    instance_id: str
    log_level: str
    cache_database_path: str

@dataclass
class NautilusPOCConfig:
    """Complete NautilusTrader POC configuration"""
    environment: str
    q50: Q50Config
    pumpswap: PumpSwapConfig
    solana: SolanaConfig
    nautilus: NautilusConfig
    monitoring: Dict[str, Any]
    error_handling: Dict[str, Any]
    regime_detection: Dict[str, Any]

class ConfigManager:
    """Configuration manager for NautilusTrader POC"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config.yaml")
        self.config_data = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.config_data = {}
    
    def get_nautilus_config(self) -> NautilusPOCConfig:
        """Get NautilusTrader POC configuration"""
        nautilus_data = self.config_data.get('nautilus_poc', {})
        
        # Apply environment variable overrides
        self._apply_env_overrides(nautilus_data)
        
        # Create configuration objects
        q50_config = Q50Config(
            features_path=nautilus_data.get('q50', {}).get('features_path', 'data3/macro_features.pkl'),
            signal_tolerance_minutes=nautilus_data.get('q50', {}).get('signal_tolerance_minutes', 5),
            required_columns=nautilus_data.get('q50', {}).get('required_columns', [])
        )
        
        pumpswap_config = PumpSwapConfig(
            payer_public_key=nautilus_data.get('pumpswap', {}).get('payer_public_key', ''),
            private_key_path=nautilus_data.get('pumpswap', {}).get('private_key_path', ''),
            max_slippage_percent=nautilus_data.get('pumpswap', {}).get('max_slippage_percent', 5.0),
            base_position_size=nautilus_data.get('pumpswap', {}).get('base_position_size', 0.1),
            max_position_size=nautilus_data.get('pumpswap', {}).get('max_position_size', 0.5),
            min_liquidity_sol=nautilus_data.get('pumpswap', {}).get('min_liquidity_sol', 10.0),
            max_price_impact_percent=nautilus_data.get('pumpswap', {}).get('max_price_impact_percent', 10.0),
            stop_loss_percent=nautilus_data.get('pumpswap', {}).get('stop_loss_percent', 20.0),
            position_timeout_hours=nautilus_data.get('pumpswap', {}).get('position_timeout_hours', 24)
        )
        
        solana_config = SolanaConfig(
            network=nautilus_data.get('solana', {}).get('network', 'testnet'),
            rpc_endpoint=nautilus_data.get('solana', {}).get('rpc_endpoint', 'https://api.testnet.solana.com'),
            commitment=nautilus_data.get('solana', {}).get('commitment', 'confirmed')
        )
        
        nautilus_config = NautilusConfig(
            instance_id=nautilus_data.get('nautilus', {}).get('instance_id', 'NAUTILUS-001'),
            log_level=nautilus_data.get('nautilus', {}).get('log_level', 'INFO'),
            cache_database_path=nautilus_data.get('nautilus', {}).get('cache_database_path', 'cache.db')
        )
        
        return NautilusPOCConfig(
            environment=nautilus_data.get('environment', 'testnet'),
            q50=q50_config,
            pumpswap=pumpswap_config,
            solana=solana_config,
            nautilus=nautilus_config,
            monitoring=nautilus_data.get('monitoring', {}),
            error_handling=nautilus_data.get('error_handling', {}),
            regime_detection=nautilus_data.get('regime_detection', {})
        )
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> None:
        """Apply environment variable overrides"""
        env_mappings = {
            'NAUTILUS_PAYER_PUBLIC_KEY': ['pumpswap', 'payer_public_key'],
            'NAUTILUS_PRIVATE_KEY_PATH': ['pumpswap', 'private_key_path'],
            'NAUTILUS_SOLANA_RPC_ENDPOINT': ['solana', 'rpc_endpoint'],
            'NAUTILUS_SOLANA_NETWORK': ['solana', 'network'],
            'NAUTILUS_MAX_POSITION_SIZE': ['pumpswap', 'max_position_size'],
            'NAUTILUS_BASE_POSITION_SIZE': ['pumpswap', 'base_position_size'],
            'NAUTILUS_MAX_SLIPPAGE': ['pumpswap', 'max_slippage_percent'],
            'NAUTILUS_LOG_LEVEL': ['nautilus', 'log_level'],
            'NAUTILUS_ENABLE_PERFORMANCE_TRACKING': ['monitoring', 'enable_performance_tracking'],
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
                if env_var in ['NAUTILUS_MAX_POSITION_SIZE', 'NAUTILUS_BASE_POSITION_SIZE', 'NAUTILUS_MAX_SLIPPAGE']:
                    env_value = float(env_value)
                elif env_var == 'NAUTILUS_ENABLE_PERFORMANCE_TRACKING':
                    env_value = env_value.lower() in ('true', '1', 'yes')
                
                current[config_path[-1]] = env_value
                logger.info(f"Applied environment override: {env_var}")
    
    def validate_config(self, config: NautilusPOCConfig) -> bool:
        """Validate configuration completeness"""
        errors = []
        
        # Validate Q50 configuration
        if not config.q50.features_path:
            errors.append("Q50 features_path is required")
        
        if not config.q50.required_columns:
            errors.append("Q50 required_columns list is empty")
        
        # Validate PumpSwap configuration
        if not config.pumpswap.payer_public_key:
            errors.append("PumpSwap payer_public_key is required")
        
        if not config.pumpswap.private_key_path:
            errors.append("PumpSwap private_key_path is required")
        
        # Validate Solana configuration
        if not config.solana.rpc_endpoint:
            errors.append("Solana rpc_endpoint is required")
        
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("Configuration validation passed")
        return True

# Global configuration instance
config_manager = ConfigManager()