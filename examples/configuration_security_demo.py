"""
Configuration and Security Management Demo for NautilusTrader POC

This example demonstrates the comprehensive configuration and security features
implemented for the NautilusTrader POC, including:

1. Multi-environment configuration management
2. Secure wallet management
3. Token validation and security
4. Security audit logging
5. Environment switching and validation

Usage:
    python examples/configuration_security_demo.py
"""

import os
import sys
import json
import time
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from nautilus_poc.config import ConfigManager
from nautilus_poc.environment_manager import EnvironmentManager
from nautilus_poc.wallet_manager import WalletManager
from nautilus_poc.security_audit import SecurityAuditor
from nautilus_poc.token_validator import TokenValidator

def demo_configuration_management():
    """Demonstrate configuration management features"""
    print("=" * 60)
    print("CONFIGURATION MANAGEMENT DEMO")
    print("=" * 60)
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    print(f"✓ Configuration loaded from: {config_manager.config_path}")
    print(f"✓ Current environment: {config_manager.environment}")
    
    # Get configuration
    config = config_manager.get_nautilus_config()
    print(f"✓ Configuration validation: {'PASSED' if config_manager.validate_config(config) else 'FAILED'}")
    
    # Show available environments
    environments = config_manager.get_available_environments()
    print(f"✓ Available environments: {', '.join(environments)}")
    
    # Show current environment configuration
    current_env_config = config.get_current_env_config()
    print(f"✓ Current network: {current_env_config.solana.network}")
    print(f"✓ RPC endpoint: {current_env_config.solana.rpc_endpoint}")
    print(f"✓ Max position size: {current_env_config.pumpswap.max_position_size}")
    print(f"✓ Max slippage: {current_env_config.pumpswap.max_slippage_percent}%")
    
    return config_manager, config

def demo_environment_management(config_manager):
    """Demonstrate environment management features"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT MANAGEMENT DEMO")
    print("=" * 60)
    
    # Initialize environment manager
    env_manager = EnvironmentManager(config_manager)
    
    # Show environment comparison
    print("Comparing testnet vs mainnet configurations:")
    comparison = env_manager.compare_environments('testnet', 'mainnet')
    
    if 'differences' in comparison:
        for category, diffs in comparison['differences'].items():
            print(f"\n{category.upper()} differences:")
            for key, values in diffs.items():
                print(f"  {key}: testnet={values['env1_value']}, mainnet={values['env2_value']}")
    
    # Validate environment switch
    print(f"\nValidating switch to mainnet:")
    validation = env_manager.validate_environment_switch('mainnet')
    print(f"✓ Can switch: {validation['can_switch']}")
    if validation['warnings']:
        print("⚠️  Warnings:")
        for warning in validation['warnings']:
            print(f"    - {warning}")
    
    # Get environment summaries
    for env in ['testnet', 'mainnet']:
        summary = env_manager.get_environment_summary(env)
        print(f"\n{env.upper()} Summary:")
        print(f"  Network: {summary['network']}")
        print(f"  Max Position: {summary['max_position_size']}")
        print(f"  Max Slippage: {summary['max_slippage']}%")
        print(f"  Transaction Cost: {summary['transaction_cost']}")
    
    return env_manager

def demo_wallet_management(config):
    """Demonstrate wallet management features"""
    print("\n" + "=" * 60)
    print("WALLET MANAGEMENT DEMO")
    print("=" * 60)
    
    # Set up demo environment variables
    demo_env = {
        'NAUTILUS_PAYER_PUBLIC_KEY': 'So11111111111111111111111111111111111111112',
        'DEMO_PRIVATE_KEY': 'demo_private_key_for_testing_purposes_only_not_real'
    }
    
    # Temporarily set environment variables
    original_env = {}
    for key, value in demo_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        # Update config to use demo private key
        config.wallet.private_key_env_var = 'DEMO_PRIVATE_KEY'
        
        # Initialize wallet manager
        wallet_manager = WalletManager(config)
        print(f"✓ Wallet initialized")
        print(f"✓ Public key: {wallet_manager._mask_address(wallet_manager.get_public_key() or 'unknown')}")
        
        # Check wallet balance
        balance = wallet_manager.check_balance()
        if balance:
            print(f"✓ SOL balance: {balance.sol_balance}")
            print(f"✓ Balance valid: {balance.is_valid}")
            print(f"✓ Token balances: {len(balance.token_balances)} tokens")
        
        # Test transaction validation
        test_transaction = {
            'mint': 'So11111111111111111111111111111111111111112',
            'amount': 1.0,
            'recipient': 'test_recipient'
        }
        
        is_valid = wallet_manager.validate_transaction_parameters(test_transaction)
        print(f"✓ Transaction validation: {'PASSED' if is_valid else 'FAILED'}")
        
        # Get wallet info
        wallet_info = wallet_manager.get_wallet_info()
        print(f"✓ Wallet info: {json.dumps(wallet_info, indent=2)}")
        
        # Check for alerts
        alerts = wallet_manager.get_recent_alerts()
        print(f"✓ Recent alerts: {len(alerts)}")
        
        return wallet_manager
        
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

def demo_security_audit(config):
    """Demonstrate security audit features"""
    print("\n" + "=" * 60)
    print("SECURITY AUDIT DEMO")
    print("=" * 60)
    
    # Initialize security auditor
    auditor = SecurityAuditor(config)
    print("✓ Security auditor initialized")
    
    # Log various security events
    auditor.log_wallet_access("demo_wallet", "balance_check", True)
    auditor.log_wallet_access("demo_wallet", "transaction_sign", True)
    auditor.log_private_key_loaded("environment_variable", True)
    auditor.log_token_validation("So11111111111111111111111111111111111111112", True, "Known good token")
    
    # Test rate limiting
    print("Testing rate limiting...")
    for i in range(15):
        allowed = auditor.check_rate_limits("demo_operation")
        if not allowed:
            print(f"✓ Rate limit triggered after {i} operations")
            break
    
    # Generate some suspicious activity
    print("Generating suspicious activity patterns...")
    for i in range(8):
        auditor.log_wallet_access("suspicious_wallet", "failed_access", False)
    
    # Detect suspicious patterns
    patterns = auditor.detect_suspicious_patterns()
    print(f"✓ Suspicious patterns detected: {len(patterns)}")
    for pattern in patterns:
        print(f"  - {pattern['pattern']}: {pattern['description']} (severity: {pattern['severity']})")
    
    # Get security summary
    summary = auditor.get_security_summary()
    print(f"✓ Security summary:")
    print(f"  Total events: {summary['total_events']}")
    print(f"  Event types: {list(summary['event_counts'].keys())}")
    print(f"  Security levels: {list(summary['level_counts'].keys())}")
    
    return auditor

def demo_token_validation(config):
    """Demonstrate token validation features"""
    print("\n" + "=" * 60)
    print("TOKEN VALIDATION DEMO")
    print("=" * 60)
    
    # Initialize token validator
    validator = TokenValidator(config)
    print("✓ Token validator initialized")
    
    # Get validation stats
    stats = validator.get_validation_stats()
    print(f"✓ Validation stats: {json.dumps(stats, indent=2)}")
    
    # Test various token addresses
    test_tokens = [
        "So11111111111111111111111111111111111111112",  # Valid SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Valid USDC
        "11111111111111111111111111111111",  # Blacklisted
        "invalid_address",  # Invalid format
        "22222222222222222222222222222222",  # Another blacklisted
    ]
    
    print("\nValidating test tokens:")
    for token in test_tokens:
        result = validator.validate_token_address(token)
        status = "✓ VALID" if result.is_valid() else "❌ INVALID"
        print(f"  {token[:20]}... : {status} - {result.reason}")
    
    # Batch validation
    batch_results = validator.batch_validate_tokens(test_tokens)
    valid_count = sum(1 for r in batch_results.values() if r.is_valid())
    print(f"✓ Batch validation: {valid_count}/{len(test_tokens)} tokens valid")
    
    return validator

def demo_environment_export(config_manager, env_manager):
    """Demonstrate configuration export features"""
    print("\n" + "=" * 60)
    print("CONFIGURATION EXPORT DEMO")
    print("=" * 60)
    
    # Export current environment
    export_path = "temp_env_export.yaml"
    success = env_manager.export_current_environment(export_path)
    print(f"✓ Environment export: {'SUCCESS' if success else 'FAILED'}")
    
    if success and Path(export_path).exists():
        with open(export_path, 'r') as f:
            content = f.read()
        print(f"✓ Export file size: {len(content)} characters")
        
        # Clean up
        Path(export_path).unlink()
        print("✓ Temporary export file cleaned up")

def demo_comprehensive_security_report(auditor, validator):
    """Generate comprehensive security report"""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE SECURITY REPORT")
    print("=" * 60)
    
    # Export security report
    report_path = "temp_security_report.json"
    success = auditor.export_security_report(report_path, hours=1)
    print(f"✓ Security report export: {'SUCCESS' if success else 'FAILED'}")
    
    if success and Path(report_path).exists():
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        print(f"✓ Report contains {report['total_events']} events")
        print(f"✓ Suspicious patterns: {len(report['suspicious_patterns'])}")
        
        # Clean up
        Path(report_path).unlink()
        print("✓ Temporary report file cleaned up")
    
    # Export validation report
    validation_report_path = "temp_validation_report.json"
    success = validator.export_validation_report(validation_report_path)
    print(f"✓ Validation report export: {'SUCCESS' if success else 'FAILED'}")
    
    if success and Path(validation_report_path).exists():
        with open(validation_report_path, 'r') as f:
            report = json.load(f)
        
        print(f"✓ Validation report contains {len(report['blacklist_addresses'])} blacklisted addresses")
        print(f"✓ Known good tokens: {len(report['known_good_tokens'])}")
        
        # Clean up
        Path(validation_report_path).unlink()
        print("✓ Temporary validation report cleaned up")

def main():
    """Run comprehensive configuration and security demo"""
    print("🚀 NautilusTrader POC Configuration & Security Demo")
    print("This demo showcases the comprehensive configuration and security features")
    print("implemented for Task 8: Configuration and Environment Management\n")
    
    try:
        # Demo 1: Configuration Management
        config_manager, config = demo_configuration_management()
        
        # Demo 2: Environment Management
        env_manager = demo_environment_management(config_manager)
        
        # Demo 3: Wallet Management
        wallet_manager = demo_wallet_management(config)
        
        # Demo 4: Security Audit
        auditor = demo_security_audit(config)
        
        # Demo 5: Token Validation
        validator = demo_token_validation(config)
        
        # Demo 6: Configuration Export
        demo_environment_export(config_manager, env_manager)
        
        # Demo 7: Comprehensive Security Report
        demo_comprehensive_security_report(auditor, validator)
        
        print("\n" + "=" * 60)
        print("🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Features Demonstrated:")
        print("✓ Multi-environment configuration (testnet/mainnet)")
        print("✓ Secure wallet management with environment variables")
        print("✓ Token address validation with blacklist/whitelist")
        print("✓ Comprehensive security audit logging")
        print("✓ Rate limiting and suspicious activity detection")
        print("✓ Environment switching and validation")
        print("✓ Configuration export and reporting")
        print("\nAll security and configuration features are working correctly!")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)