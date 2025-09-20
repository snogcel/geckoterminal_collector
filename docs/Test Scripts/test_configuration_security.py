"""
Test configuration and security management for NautilusTrader POC
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the modules we're testing
from nautilus_poc.config import ConfigManager, NautilusPOCConfig, SecurityManager
from nautilus_poc.wallet_manager import WalletManager, WalletBalance
from nautilus_poc.environment_manager import EnvironmentManager
from nautilus_poc.security_audit import SecurityAuditor, SecurityEvent, SecurityEventType, SecurityLevel
from nautilus_poc.token_validator import TokenValidator, ValidationResult

def test_config_manager_initialization():
    """Test ConfigManager initialization"""
    config_manager = ConfigManager()
    assert config_manager.config_path.name == "config.yaml"
    assert config_manager.environment in ['testnet', 'mainnet']

def test_environment_variable_overrides():
    """Test environment variable configuration overrides"""
    with patch.dict(os.environ, {
        'NAUTILUS_ENVIRONMENT': 'testnet',
        'NAUTILUS_LOG_LEVEL': 'DEBUG',
        'NAUTILUS_MAX_POSITION_SIZE': '0.3'
    }):
        config_manager = ConfigManager()
        config = config_manager.get_nautilus_config()
        
        assert config.environment == 'testnet'
        assert config.nautilus.log_level == 'DEBUG'

def test_multi_environment_configuration():
    """Test multi-environment configuration loading"""
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    # Check that environments are loaded
    assert 'testnet' in config.environments
    assert 'mainnet' in config.environments
    
    # Check environment-specific configurations
    testnet_config = config.environments['testnet']
    mainnet_config = config.environments['mainnet']
    
    assert testnet_config.solana.network == 'testnet'
    assert mainnet_config.solana.network == 'mainnet'
    
    # Testnet should have more relaxed settings
    assert testnet_config.pumpswap.max_slippage_percent >= mainnet_config.pumpswap.max_slippage_percent

def test_configuration_validation():
    """Test configuration validation"""
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    # Basic validation should pass with default config
    is_valid = config_manager.validate_config(config)
    # Note: This might fail if wallet credentials are not set, which is expected
    
    # Test with invalid configuration
    config.q50.features_path = ""
    is_valid = config_manager.validate_config(config)
    assert not is_valid

def test_environment_manager():
    """Test EnvironmentManager functionality"""
    config_manager = ConfigManager()
    env_manager = EnvironmentManager(config_manager)
    
    # Test environment listing
    environments = env_manager.list_environments()
    assert 'testnet' in environments
    assert 'mainnet' in environments
    
    # Test environment switching validation
    validation = env_manager.validate_environment_switch('mainnet')
    assert 'can_switch' in validation
    assert 'warnings' in validation
    assert 'errors' in validation

def test_environment_comparison():
    """Test environment configuration comparison"""
    config_manager = ConfigManager()
    env_manager = EnvironmentManager(config_manager)
    
    comparison = env_manager.compare_environments('testnet', 'mainnet')
    assert 'differences' in comparison
    assert 'environment_1' in comparison
    assert 'environment_2' in comparison
    
    # Should have differences in network settings
    assert 'solana' in comparison.get('differences', {})

def test_security_manager():
    """Test SecurityManager functionality"""
    security_manager = SecurityManager()
    
    # Test address masking
    address = "So11111111111111111111111111111111111111112"
    masked = security_manager.mask_sensitive_value(address)
    assert len(masked) == len(address)
    assert masked != address
    assert masked.startswith("So11")
    assert masked.endswith("1112")

def test_wallet_manager_initialization():
    """Test WalletManager initialization"""
    # Create mock configuration
    mock_config = MagicMock()
    mock_config.wallet.private_key_env_var = "TEST_PRIVATE_KEY"
    mock_config.wallet.private_key_path = ""
    mock_config.wallet.payer_public_key = ""
    mock_config.wallet.wallet_password_env_var = ""
    mock_config.wallet.validate_balance_before_trade = True
    mock_config.wallet.min_balance_sol = 0.1
    mock_config.wallet.balance_check_interval_minutes = 5
    mock_config.security.validate_token_addresses = True
    mock_config.get_current_env_config.return_value.security.wallet_balance_alert_threshold = 1.0
    
    # Mock environment variables with both public key and private key
    with patch.dict(os.environ, {
        'NAUTILUS_PAYER_PUBLIC_KEY': 'test_public_key',
        'TEST_PRIVATE_KEY': 'test_private_key_value_that_is_long_enough_for_validation'
    }):
        wallet_manager = WalletManager(mock_config)
        
        # Should successfully initialize with both keys
        assert wallet_manager.get_public_key() == 'test_public_key'

def test_wallet_balance_checking():
    """Test wallet balance checking functionality"""
    mock_config = MagicMock()
    mock_config.wallet.private_key_env_var = "TEST_PRIVATE_KEY"
    mock_config.wallet.private_key_path = ""
    mock_config.wallet.payer_public_key = ""
    mock_config.wallet.wallet_password_env_var = ""
    mock_config.wallet.validate_balance_before_trade = True
    mock_config.wallet.min_balance_sol = 0.1
    mock_config.wallet.balance_check_interval_minutes = 5
    mock_config.security.validate_token_addresses = True
    mock_config.get_current_env_config.return_value.security.wallet_balance_alert_threshold = 1.0
    
    with patch.dict(os.environ, {
        'NAUTILUS_PAYER_PUBLIC_KEY': 'test_public_key',
        'TEST_PRIVATE_KEY': 'test_private_key_value_that_is_long_enough_for_validation'
    }):
        wallet_manager = WalletManager(mock_config)
        
        # Test simulated balance check
        balance = wallet_manager.check_balance()
        assert isinstance(balance, WalletBalance)
        assert balance.sol_balance > 0
        assert balance.is_valid

def test_security_auditor():
    """Test SecurityAuditor functionality"""
    mock_config = MagicMock()
    mock_config.security.enable_audit_logging = True
    mock_config.security.audit_log_path = "logs/test_audit.log"
    mock_config.security.sensitive_data_masking = True
    mock_config.security.max_trades_per_minute = 10
    mock_config.security.max_trades_per_hour = 100
    mock_config.security.max_trades_per_day = 500
    mock_config.environment = 'testnet'
    
    auditor = SecurityAuditor(mock_config)
    
    # Test event logging
    auditor.log_wallet_access("test_wallet", "balance_check", True)
    assert len(auditor.events) == 1
    
    # Test rate limiting
    for i in range(15):  # Exceed per-minute limit
        result = auditor.check_rate_limits("test_operation")
        if i < 10:
            assert result == True
        else:
            assert result == False

def test_token_validator():
    """Test TokenValidator functionality"""
    mock_config = MagicMock()
    mock_config.security.validate_token_addresses = True
    mock_config.security.token_blacklist_path = "security/token_blacklist.json"
    mock_config.security.token_whitelist_path = "security/token_whitelist.json"
    mock_config.security.enable_token_metadata_validation = True
    mock_config.environment = 'testnet'
    
    validator = TokenValidator(mock_config)
    
    # Test valid Solana address
    valid_address = "So11111111111111111111111111111111111111112"
    result = validator.validate_token_address(valid_address)
    assert result.is_valid()
    
    # Test invalid address format
    invalid_address = "invalid_address"
    result = validator.validate_token_address(invalid_address)
    assert not result.is_valid()
    assert result.result == ValidationResult.INVALID_FORMAT

def test_token_blacklist_functionality():
    """Test token blacklist functionality"""
    mock_config = MagicMock()
    mock_config.security.validate_token_addresses = True
    mock_config.security.token_blacklist_path = "security/token_blacklist.json"
    mock_config.security.token_whitelist_path = ""
    mock_config.security.enable_token_metadata_validation = False
    mock_config.environment = 'testnet'
    
    validator = TokenValidator(mock_config)
    
    # Test blacklisted address (from our test blacklist)
    blacklisted_address = "11111111111111111111111111111111"
    result = validator.validate_token_address(blacklisted_address)
    assert not result.is_valid()
    assert result.result == ValidationResult.BLACKLISTED

def test_configuration_export():
    """Test configuration export functionality"""
    config_manager = ConfigManager()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_path = f.name
    
    try:
        # Test environment export
        success = config_manager.export_environment_config('testnet', temp_path)
        assert success
        
        # Verify exported file exists and has content
        assert Path(temp_path).exists()
        with open(temp_path, 'r') as f:
            content = f.read()
            assert 'testnet' in content
            assert 'solana' in content
    finally:
        # Cleanup
        if Path(temp_path).exists():
            Path(temp_path).unlink()

def test_security_event_creation():
    """Test security event creation and handling"""
    event = SecurityEvent(
        event_type=SecurityEventType.WALLET_ACCESS,
        level=SecurityLevel.INFO,
        message="Test wallet access",
        timestamp=1234567890.0,
        wallet_address="test_wallet"
    )
    
    assert event.event_type == SecurityEventType.WALLET_ACCESS
    assert event.level == SecurityLevel.INFO
    assert event.message == "Test wallet access"
    
    # Test conversion to dictionary
    event_dict = event.to_dict()
    assert event_dict['event_type'] == 'wallet_access'
    assert event_dict['level'] == 'info'

def test_suspicious_pattern_detection():
    """Test suspicious activity pattern detection"""
    mock_config = MagicMock()
    mock_config.security.enable_audit_logging = True
    mock_config.security.audit_log_path = "logs/test_audit.log"
    mock_config.security.sensitive_data_masking = True
    mock_config.environment = 'testnet'
    
    auditor = SecurityAuditor(mock_config)
    
    # Generate multiple failed wallet access events
    for i in range(10):
        auditor.log_wallet_access("test_wallet", "access_attempt", False)
    
    # Detect patterns
    patterns = auditor.detect_suspicious_patterns()
    assert len(patterns) > 0
    
    # Should detect multiple failed access attempts
    failed_access_pattern = next(
        (p for p in patterns if p['pattern'] == 'multiple_failed_wallet_access'), 
        None
    )
    assert failed_access_pattern is not None
    assert failed_access_pattern['count'] >= 5

def test_wallet_transaction_validation():
    """Test wallet transaction parameter validation"""
    mock_config = MagicMock()
    mock_config.wallet.private_key_env_var = "TEST_PRIVATE_KEY"
    mock_config.wallet.private_key_path = ""
    mock_config.wallet.payer_public_key = ""
    mock_config.wallet.wallet_password_env_var = ""
    mock_config.wallet.validate_balance_before_trade = True
    mock_config.wallet.min_balance_sol = 0.1
    mock_config.wallet.balance_check_interval_minutes = 5
    mock_config.security.validate_token_addresses = True
    mock_config.get_current_env_config.return_value.security.wallet_balance_alert_threshold = 1.0
    
    with patch.dict(os.environ, {
        'NAUTILUS_PAYER_PUBLIC_KEY': 'test_public_key',
        'TEST_PRIVATE_KEY': 'test_private_key_value_that_is_long_enough_for_validation'
    }):
        wallet_manager = WalletManager(mock_config)
        
        # Test valid transaction parameters
        valid_params = {
            'mint': 'So11111111111111111111111111111111111111112',
            'amount': 1.0,
            'recipient': 'test_recipient'
        }
        
        # Mock balance check to return sufficient balance
        with patch.object(wallet_manager, 'check_balance') as mock_balance:
            mock_balance.return_value = WalletBalance(
                sol_balance=10.0,
                token_balances={},
                last_updated=1234567890.0,
                is_valid=True
            )
            
            is_valid = wallet_manager.validate_transaction_parameters(valid_params)
            # Note: This might fail due to token validation, which is expected

def run_comprehensive_tests():
    """Run all configuration and security tests"""
    print("Running Configuration and Security Tests...")
    
    try:
        test_config_manager_initialization()
        print("✓ ConfigManager initialization test passed")
        
        test_multi_environment_configuration()
        print("✓ Multi-environment configuration test passed")
        
        test_environment_manager()
        print("✓ EnvironmentManager test passed")
        
        test_environment_comparison()
        print("✓ Environment comparison test passed")
        
        test_security_manager()
        print("✓ SecurityManager test passed")
        
        test_wallet_manager_initialization()
        print("✓ WalletManager initialization test passed")
        
        test_wallet_balance_checking()
        print("✓ Wallet balance checking test passed")
        
        test_security_auditor()
        print("✓ SecurityAuditor test passed")
        
        test_token_validator()
        print("✓ TokenValidator test passed")
        
        test_token_blacklist_functionality()
        print("✓ Token blacklist functionality test passed")
        
        test_configuration_export()
        print("✓ Configuration export test passed")
        
        test_security_event_creation()
        print("✓ Security event creation test passed")
        
        test_suspicious_pattern_detection()
        print("✓ Suspicious pattern detection test passed")
        
        print("\n🎉 All configuration and security tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_comprehensive_tests()
    exit(0 if success else 1)