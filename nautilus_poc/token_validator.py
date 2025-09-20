"""
Token address validation and security checks for NautilusTrader POC
"""

import json
import re
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    """Token validation results"""
    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    BLACKLISTED = "blacklisted"
    NOT_WHITELISTED = "not_whitelisted"
    METADATA_INVALID = "metadata_invalid"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class TokenValidationReport:
    """Token validation report"""
    token_address: str
    result: ValidationResult
    reason: str
    metadata: Optional[Dict[str, Any]] = None
    validation_time: float = 0.0
    
    def is_valid(self) -> bool:
        """Check if token passed validation"""
        return self.result == ValidationResult.VALID

class TokenValidator:
    """Token address validator with security features"""
    
    def __init__(self, config):
        self.config = config
        self.security_config = config.security
        
        # Load blacklist and whitelist
        self.blacklist = self._load_address_list(self.security_config.token_blacklist_path)
        self.whitelist = self._load_address_list(self.security_config.token_whitelist_path)
        
        # Cache for validation results
        self.validation_cache = {}
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Known good tokens (Solana native tokens)
        self.known_good_tokens = {
            "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        }
        
        logger.info(f"Token validator initialized - Blacklist: {len(self.blacklist)}, Whitelist: {len(self.whitelist)}")
    
    def _load_address_list(self, file_path: str) -> Set[str]:
        """Load address list from JSON file"""
        if not file_path or not Path(file_path).exists():
            return set()
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            addresses = set(data.get('addresses', []))
            logger.info(f"Loaded {len(addresses)} addresses from {file_path}")
            return addresses
            
        except Exception as e:
            logger.error(f"Failed to load address list from {file_path}: {e}")
            return set()
    
    def validate_token_address(self, token_address: str) -> TokenValidationReport:
        """Validate token address with comprehensive checks"""
        start_time = time.time()
        
        # Check cache first
        cache_key = f"{token_address}_{self.config.environment}"
        if cache_key in self.validation_cache:
            cached_result, cache_time = self.validation_cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                cached_result.validation_time = time.time() - start_time
                return cached_result
        
        # Perform validation
        report = self._perform_validation(token_address)
        report.validation_time = time.time() - start_time
        
        # Cache result
        self.validation_cache[cache_key] = (report, time.time())
        
        # Clean old cache entries
        self._clean_cache()
        
        return report
    
    def _perform_validation(self, token_address: str) -> TokenValidationReport:
        """Perform comprehensive token validation"""
        # Step 1: Format validation
        format_result = self._validate_format(token_address)
        if format_result.result != ValidationResult.VALID:
            return format_result
        
        # Step 2: Blacklist check
        blacklist_result = self._check_blacklist(token_address)
        if blacklist_result.result != ValidationResult.VALID:
            return blacklist_result
        
        # Step 3: Whitelist check (if whitelist exists and is not empty)
        if self.whitelist:
            whitelist_result = self._check_whitelist(token_address)
            if whitelist_result.result != ValidationResult.VALID:
                return whitelist_result
        
        # Step 4: Metadata validation (if enabled)
        if self.security_config.enable_token_metadata_validation:
            metadata_result = self._validate_metadata(token_address)
            if metadata_result.result != ValidationResult.VALID:
                return metadata_result
        
        # All checks passed
        return TokenValidationReport(
            token_address=token_address,
            result=ValidationResult.VALID,
            reason="All validation checks passed"
        )
    
    def _validate_format(self, token_address: str) -> TokenValidationReport:
        """Validate token address format"""
        if not token_address:
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.INVALID_FORMAT,
                reason="Empty token address"
            )
        
        # Solana address format validation
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', token_address):
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.INVALID_FORMAT,
                reason="Invalid Solana address format"
            )
        
        # Length check
        if len(token_address) < 32 or len(token_address) > 44:
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.INVALID_FORMAT,
                reason=f"Invalid address length: {len(token_address)}"
            )
        
        return TokenValidationReport(
            token_address=token_address,
            result=ValidationResult.VALID,
            reason="Format validation passed"
        )
    
    def _check_blacklist(self, token_address: str) -> TokenValidationReport:
        """Check token against blacklist"""
        if token_address in self.blacklist:
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.BLACKLISTED,
                reason="Token address is blacklisted"
            )
        
        # Check against pattern blacklist (if implemented)
        # This would check for known scam patterns, etc.
        
        return TokenValidationReport(
            token_address=token_address,
            result=ValidationResult.VALID,
            reason="Blacklist check passed"
        )
    
    def _check_whitelist(self, token_address: str) -> TokenValidationReport:
        """Check token against whitelist"""
        if not self.whitelist:
            # No whitelist configured, allow all
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.VALID,
                reason="No whitelist configured"
            )
        
        if token_address in self.whitelist or token_address in self.known_good_tokens:
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.VALID,
                reason="Token is whitelisted"
            )
        
        return TokenValidationReport(
            token_address=token_address,
            result=ValidationResult.NOT_WHITELISTED,
            reason="Token not in whitelist"
        )
    
    def _validate_metadata(self, token_address: str) -> TokenValidationReport:
        """Validate token metadata (simplified for POC)"""
        try:
            # In production, this would query Solana RPC for token metadata
            # For POC, we'll simulate metadata validation
            
            # Check if it's a known good token
            if token_address in self.known_good_tokens:
                return TokenValidationReport(
                    token_address=token_address,
                    result=ValidationResult.VALID,
                    reason="Known good token",
                    metadata={"verified": True, "source": "known_good"}
                )
            
            # Simulate metadata check
            metadata = self._simulate_metadata_check(token_address)
            
            if not metadata:
                return TokenValidationReport(
                    token_address=token_address,
                    result=ValidationResult.METADATA_INVALID,
                    reason="No metadata found"
                )
            
            # Basic metadata validation
            if metadata.get('suspicious', False):
                return TokenValidationReport(
                    token_address=token_address,
                    result=ValidationResult.METADATA_INVALID,
                    reason="Suspicious metadata detected",
                    metadata=metadata
                )
            
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.VALID,
                reason="Metadata validation passed",
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Metadata validation error for {token_address}: {e}")
            return TokenValidationReport(
                token_address=token_address,
                result=ValidationResult.NETWORK_ERROR,
                reason=f"Metadata validation error: {str(e)}"
            )
    
    def _simulate_metadata_check(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Simulate metadata check for POC"""
        # In production, this would make actual RPC calls
        return {
            "name": f"Token_{token_address[:8]}",
            "symbol": f"TK{token_address[:4]}",
            "decimals": 9,
            "supply": 1000000,
            "verified": False,
            "suspicious": False,
            "creation_time": time.time() - 86400,  # 1 day ago
            "source": "simulated"
        }
    
    def batch_validate_tokens(self, token_addresses: List[str]) -> Dict[str, TokenValidationReport]:
        """Validate multiple token addresses"""
        results = {}
        
        for token_address in token_addresses:
            try:
                results[token_address] = self.validate_token_address(token_address)
            except Exception as e:
                logger.error(f"Batch validation error for {token_address}: {e}")
                results[token_address] = TokenValidationReport(
                    token_address=token_address,
                    result=ValidationResult.UNKNOWN_ERROR,
                    reason=f"Validation error: {str(e)}"
                )
        
        return results
    
    def add_to_blacklist(self, token_address: str, reason: str = "") -> bool:
        """Add token to blacklist"""
        try:
            self.blacklist.add(token_address)
            
            # Update blacklist file
            blacklist_path = Path(self.security_config.token_blacklist_path)
            if blacklist_path.exists():
                with open(blacklist_path, 'r') as f:
                    data = json.load(f)
            else:
                data = {"addresses": [], "metadata": {}}
            
            if token_address not in data.get('addresses', []):
                data['addresses'].append(token_address)
                data['metadata'][token_address] = {
                    'added_time': time.time(),
                    'reason': reason,
                    'added_by': 'system'
                }
                
                with open(blacklist_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.info(f"Added {token_address} to blacklist: {reason}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to add {token_address} to blacklist: {e}")
        
        return False
    
    def remove_from_blacklist(self, token_address: str) -> bool:
        """Remove token from blacklist"""
        try:
            if token_address in self.blacklist:
                self.blacklist.remove(token_address)
                
                # Update blacklist file
                blacklist_path = Path(self.security_config.token_blacklist_path)
                if blacklist_path.exists():
                    with open(blacklist_path, 'r') as f:
                        data = json.load(f)
                    
                    if token_address in data.get('addresses', []):
                        data['addresses'].remove(token_address)
                        if token_address in data.get('metadata', {}):
                            del data['metadata'][token_address]
                        
                        with open(blacklist_path, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        logger.info(f"Removed {token_address} from blacklist")
                        return True
            
        except Exception as e:
            logger.error(f"Failed to remove {token_address} from blacklist: {e}")
        
        return False
    
    def _clean_cache(self) -> None:
        """Clean expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, cache_time) in self.validation_cache.items()
            if current_time - cache_time > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.validation_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        return {
            'blacklist_size': len(self.blacklist),
            'whitelist_size': len(self.whitelist),
            'cache_size': len(self.validation_cache),
            'known_good_tokens': len(self.known_good_tokens),
            'validation_enabled': self.security_config.validate_token_addresses,
            'metadata_validation_enabled': self.security_config.enable_token_metadata_validation
        }
    
    def export_validation_report(self, output_path: str) -> bool:
        """Export validation configuration and stats"""
        try:
            report = {
                'timestamp': time.time(),
                'environment': self.config.environment,
                'configuration': {
                    'validate_token_addresses': self.security_config.validate_token_addresses,
                    'enable_token_metadata_validation': self.security_config.enable_token_metadata_validation,
                    'blacklist_path': self.security_config.token_blacklist_path,
                    'whitelist_path': self.security_config.token_whitelist_path
                },
                'statistics': self.get_validation_stats(),
                'blacklist_addresses': list(self.blacklist),
                'whitelist_addresses': list(self.whitelist) if self.whitelist else [],
                'known_good_tokens': list(self.known_good_tokens)
            }
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Validation report exported to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export validation report: {e}")
            return False