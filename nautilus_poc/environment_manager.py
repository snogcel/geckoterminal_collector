"""
Environment management for NautilusTrader POC
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from .config import ConfigManager, NautilusPOCConfig, EnvironmentConfig

logger = logging.getLogger(__name__)

class EnvironmentManager:
    """Manage environment configurations and switching"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.current_config = None
        self.environment_history = []
    
    def list_environments(self) -> List[str]:
        """List all available environments"""
        return self.config_manager.get_available_environments()
    
    def get_current_environment(self) -> str:
        """Get current environment name"""
        return self.config_manager.environment
    
    def switch_environment(self, environment: str) -> bool:
        """Switch to a different environment"""
        if environment not in self.list_environments():
            logger.error(f"Environment '{environment}' not found")
            return False
        
        # Record environment change
        old_env = self.config_manager.environment
        if self.config_manager.switch_environment(environment):
            self.environment_history.append({
                'from': old_env,
                'to': environment,
                'timestamp': self._get_timestamp()
            })
            
            # Reload configuration
            self.current_config = self.config_manager.get_nautilus_config()
            logger.info(f"Successfully switched from '{old_env}' to '{environment}'")
            return True
        
        return False
    
    def get_environment_config(self, environment: str) -> Optional[EnvironmentConfig]:
        """Get configuration for specific environment"""
        config = self.config_manager.get_nautilus_config()
        return config.environments.get(environment)
    
    def compare_environments(self, env1: str, env2: str) -> Dict[str, Any]:
        """Compare two environment configurations"""
        config1 = self.get_environment_config(env1)
        config2 = self.get_environment_config(env2)
        
        if not config1 or not config2:
            return {'error': 'One or both environments not found'}
        
        comparison = {
            'environment_1': env1,
            'environment_2': env2,
            'differences': {},
            'similarities': {}
        }
        
        # Compare Solana configurations
        solana_diff = self._compare_configs(
            asdict(config1.solana), 
            asdict(config2.solana)
        )
        if solana_diff:
            comparison['differences']['solana'] = solana_diff
        
        # Compare PumpSwap configurations
        pumpswap_diff = self._compare_configs(
            asdict(config1.pumpswap), 
            asdict(config2.pumpswap)
        )
        if pumpswap_diff:
            comparison['differences']['pumpswap'] = pumpswap_diff
        
        # Compare Security configurations
        security_diff = self._compare_configs(
            asdict(config1.security), 
            asdict(config2.security)
        )
        if security_diff:
            comparison['differences']['security'] = security_diff
        
        return comparison
    
    def _compare_configs(self, config1: Dict, config2: Dict) -> Dict[str, Any]:
        """Compare two configuration dictionaries"""
        differences = {}
        
        all_keys = set(config1.keys()) | set(config2.keys())
        
        for key in all_keys:
            val1 = config1.get(key)
            val2 = config2.get(key)
            
            if val1 != val2:
                differences[key] = {
                    'env1_value': val1,
                    'env2_value': val2
                }
        
        return differences
    
    def validate_environment_switch(self, target_environment: str) -> Dict[str, Any]:
        """Validate if switching to target environment is safe"""
        validation_result = {
            'can_switch': True,
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        target_config = self.get_environment_config(target_environment)
        if not target_config:
            validation_result['can_switch'] = False
            validation_result['errors'].append(f"Environment '{target_environment}' not found")
            return validation_result
        
        current_env = self.get_current_environment()
        current_config = self.get_environment_config(current_env)
        
        # Check for risky configuration changes
        if current_config and target_config:
            # Check position size changes
            if target_config.pumpswap.max_position_size > current_config.pumpswap.max_position_size * 2:
                validation_result['warnings'].append(
                    f"Max position size will increase significantly: "
                    f"{current_config.pumpswap.max_position_size} -> {target_config.pumpswap.max_position_size}"
                )
            
            # Check slippage tolerance changes
            if target_config.pumpswap.max_slippage_percent > current_config.pumpswap.max_slippage_percent * 1.5:
                validation_result['warnings'].append(
                    f"Slippage tolerance will increase significantly: "
                    f"{current_config.pumpswap.max_slippage_percent}% -> {target_config.pumpswap.max_slippage_percent}%"
                )
            
            # Check network changes
            if target_config.solana.network != current_config.solana.network:
                if target_config.solana.network == 'mainnet':
                    validation_result['warnings'].append(
                        "Switching to mainnet - ensure you have real SOL and understand the risks"
                    )
                    validation_result['recommendations'].append(
                        "Verify wallet balance and private key configuration before switching to mainnet"
                    )
                elif current_config.solana.network == 'mainnet':
                    validation_result['recommendations'].append(
                        "Switching from mainnet to testnet - positions will not be accessible"
                    )
        
        return validation_result
    
    def create_environment_backup(self, environment: str, backup_path: str) -> bool:
        """Create backup of environment configuration"""
        try:
            env_config = self.get_environment_config(environment)
            if not env_config:
                logger.error(f"Environment '{environment}' not found")
                return False
            
            backup_data = {
                'environment': environment,
                'timestamp': self._get_timestamp(),
                'config': asdict(env_config)
            }
            
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(backup_file, 'w') as f:
                yaml.dump(backup_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"Environment backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create environment backup: {e}")
            return False
    
    def restore_environment_backup(self, backup_path: str) -> bool:
        """Restore environment from backup (not implemented in POC)"""
        logger.info("Environment restore functionality not implemented in POC")
        logger.info("To restore: manually update config.yaml with backup data")
        return False
    
    def get_environment_summary(self, environment: str) -> Dict[str, Any]:
        """Get summary of environment configuration"""
        env_config = self.get_environment_config(environment)
        if not env_config:
            return {'error': f"Environment '{environment}' not found"}
        
        return {
            'environment': environment,
            'network': env_config.solana.network,
            'rpc_endpoint': env_config.solana.rpc_endpoint,
            'commitment': env_config.solana.commitment,
            'max_position_size': env_config.pumpswap.max_position_size,
            'max_slippage': env_config.pumpswap.max_slippage_percent,
            'min_liquidity': env_config.pumpswap.min_liquidity_sol,
            'transaction_cost': env_config.pumpswap.realistic_transaction_cost,
            'max_daily_trades': env_config.security.max_daily_trades,
            'circuit_breaker_enabled': env_config.security.enable_circuit_breaker,
            'token_validation_enabled': env_config.security.validate_token_addresses
        }
    
    def get_environment_history(self) -> List[Dict[str, Any]]:
        """Get history of environment switches"""
        return self.environment_history.copy()
    
    def export_current_environment(self, output_path: str) -> bool:
        """Export current environment configuration"""
        current_env = self.get_current_environment()
        return self.config_manager.export_environment_config(current_env, output_path)
    
    def validate_all_environments(self) -> Dict[str, Any]:
        """Validate all environment configurations"""
        results = {}
        
        for env_name in self.list_environments():
            env_config = self.get_environment_config(env_name)
            if env_config:
                validation = self._validate_single_environment(env_name, env_config)
                results[env_name] = validation
            else:
                results[env_name] = {'valid': False, 'errors': ['Configuration not found']}
        
        return results
    
    def _validate_single_environment(self, env_name: str, env_config: EnvironmentConfig) -> Dict[str, Any]:
        """Validate a single environment configuration"""
        validation = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Validate Solana configuration
        if not env_config.solana.rpc_endpoint:
            validation['valid'] = False
            validation['errors'].append("Missing Solana RPC endpoint")
        
        if env_config.solana.network not in ['testnet', 'mainnet']:
            validation['warnings'].append(f"Unusual network: {env_config.solana.network}")
        
        # Validate PumpSwap configuration
        if env_config.pumpswap.max_position_size > 1.0:
            validation['warnings'].append("Max position size > 100% of capital")
        
        if env_config.pumpswap.max_slippage_percent > 20.0:
            validation['warnings'].append("Very high slippage tolerance")
        
        if env_config.pumpswap.min_liquidity_sol <= 0:
            validation['errors'].append("Minimum liquidity must be positive")
            validation['valid'] = False
        
        # Validate Security configuration
        if not env_config.security.validate_token_addresses:
            validation['warnings'].append("Token address validation disabled")
        
        if env_config.security.max_daily_trades <= 0:
            validation['errors'].append("Max daily trades must be positive")
            validation['valid'] = False
        
        return validation
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def get_recommended_environment(self, use_case: str) -> str:
        """Get recommended environment for specific use case"""
        recommendations = {
            'development': 'testnet',
            'testing': 'testnet',
            'staging': 'testnet',
            'production': 'mainnet',
            'demo': 'testnet'
        }
        
        return recommendations.get(use_case.lower(), 'testnet')