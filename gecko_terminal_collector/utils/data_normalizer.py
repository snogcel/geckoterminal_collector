"""
Data type normalization utilities for consistent data handling across collectors.

This module provides utilities to normalize API response data types, ensuring
consistent handling of DataFrame/List conversions and data structure validation.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from gecko_terminal_collector.models.core import ValidationResult

logger = logging.getLogger(__name__)


class DataTypeNormalizer:
    """
    Utility class for normalizing data types across collectors.
    
    Handles conversion between pandas DataFrames and Lists, provides
    validation for expected data structures, and ensures consistent
    data handling across all collectors.
    """
    
    @staticmethod
    def remove_prefix(pool_id: str) -> str:        
        # Split the string by the first underscore
        parts = pool_id.split("_", 1)

        # Assign the results
        prefix = parts[0]
        address_body = parts[1]

        return address_body

    @staticmethod
    def normalize_response_data(data: Any) -> List[Dict]:
        """
        Convert API response data to consistent List[Dict] format.
        
        Args:
            data: API response data (can be DataFrame, List, Dict, or None)
            
        Returns:
            List[Dict] representation of the data
            
        Raises:
            ValueError: If data type cannot be normalized
        """
        if data is None:
            logger.debug("Received None data, returning empty list")
            return []
        
        # Handle pandas DataFrame
        if isinstance(data, pd.DataFrame):
            logger.debug(f"Converting DataFrame with {len(data)} rows to list of dicts")
            return data.to_dict('records')
        
        # Handle list (already in correct format)
        elif isinstance(data, list):
            logger.debug(f"Data is already a list with {len(data)} items")
            return data
        
        # Handle API response format with 'data' field
        elif isinstance(data, dict):
            # Check if it's an API response with 'data' field
            if 'data' in data:
                logger.debug("Extracting data from API response format")
                return DataTypeNormalizer.normalize_response_data(data['data'])
            # Check if it's an empty API response (no data field, just meta)
            elif 'meta' in data and len(data) == 1:
                logger.debug("Empty API response detected, returning empty list")
                return []
            else:
                # Single dictionary (convert to list with one item)
                logger.debug("Converting single dict to list with one item")
                return [data]
        
        # Handle other iterable types
        elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
            try:
                result = list(data)
                logger.debug(f"Converted iterable to list with {len(result)} items")
                return result
            except Exception as e:
                logger.error(f"Failed to convert iterable to list: {e}")
                raise ValueError(f"Cannot convert iterable data to list: {type(data)}")
        
        # Unsupported data type
        else:
            logger.error(f"Unsupported data type for normalization: {type(data)}")
            raise ValueError(f"Unsupported data type: {type(data)}")
    
    @staticmethod
    def validate_expected_structure(data: Any, collector_type: str) -> ValidationResult:
        """
        Validate data structure matches collector expectations.
        
        Args:
            data: Data to validate
            collector_type: Type of collector (for specific validation rules)
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        # Normalize data first
        try:
            normalized_data = DataTypeNormalizer.normalize_response_data(data)
        except ValueError as e:
            errors.append(f"Data normalization failed: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        # Collector-specific validation
        if collector_type == "dex_monitoring":
            validation_result = DataTypeNormalizer._validate_dex_data(normalized_data)
        elif collector_type == "top_pools":
            validation_result = DataTypeNormalizer._validate_pools_data(normalized_data)
        elif collector_type == "ohlcv":
            validation_result = DataTypeNormalizer._validate_ohlcv_data(normalized_data)
        elif collector_type == "trade":
            validation_result = DataTypeNormalizer._validate_trade_data(normalized_data)
        elif collector_type == "watchlist":
            validation_result = DataTypeNormalizer._validate_watchlist_data(normalized_data)
        else:
            # Generic validation for unknown collector types
            validation_result = DataTypeNormalizer._validate_generic_data(normalized_data)
        
        return validation_result
    
    @staticmethod
    def _validate_dex_data(data: List[Dict]) -> ValidationResult:
        """Validate DEX monitoring data structure."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No DEXes found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each DEX entry
        for i, dex in enumerate(data):
            if not isinstance(dex, dict):
                errors.append(f"DEX entry {i} must be a dictionary")
                continue
            
            # Check required fields
            if "id" not in dex:
                errors.append(f"DEX entry {i} missing required 'id' field")
            
            if "type" not in dex:
                errors.append(f"DEX entry {i} missing required 'type' field")
            elif dex["type"] != "dex":
                warnings.append(f"DEX entry {i} has unexpected type: {dex['type']}")
            
            # Check attributes (can be in root or nested)
            attributes = dex.get("attributes", dex)
            if "name" not in attributes:
                errors.append(f"DEX entry {i} missing required 'name' field")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def _validate_pools_data(data: List[Dict]) -> ValidationResult:
        """Validate top pools data structure."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No pools found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each pool entry
        for i, pool in enumerate(data):
            if not isinstance(pool, dict):
                errors.append(f"Pool entry {i} must be a dictionary")
                continue
            
            # Check required fields
            if "id" not in pool:
                errors.append(f"Pool entry {i} missing required 'id' field")
            
            if "type" not in pool:
                errors.append(f"Pool entry {i} missing required 'type' field")
            elif pool["type"] != "pool":
                warnings.append(f"Pool entry {i} has unexpected type: {pool['type']}")
            
            # Check attributes (can be in root or nested)
            attributes = pool.get("attributes", pool)
            required_attrs = ["name", "address"]
            for attr in required_attrs:
                if attr not in attributes:
                    errors.append(f"Pool entry {i} missing required attribute: {attr}")
            
            # Check relationships (can be in root or nested)
            relationships = pool.get("relationships", pool)
            if "dex_id" not in relationships and "dex" not in relationships:
                warnings.append(f"Pool entry {i} missing DEX relationship")
            
            if "base_token_id" not in relationships and "base_token" not in relationships:
                warnings.append(f"Pool entry {i} missing base_token relationship")
            
            if "quote_token_id" not in relationships and "quote_token" not in relationships:
                warnings.append(f"Pool entry {i} missing quote_token relationship")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def _validate_ohlcv_data(data: List[Dict]) -> ValidationResult:
        """Validate OHLCV data structure."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No OHLCV data found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each OHLCV entry
        for i, ohlcv in enumerate(data):
            if not isinstance(ohlcv, dict):
                errors.append(f"OHLCV entry {i} must be a dictionary")
                continue
            
            # Check for required OHLCV fields
            required_fields = ["timestamp", "open", "high", "low", "close", "volume_usd"]
            for field in required_fields:
                if field not in ohlcv:
                    errors.append(f"OHLCV entry {i} missing required field: {field}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def _validate_trade_data(data: List[Dict]) -> ValidationResult:
        """Validate trade data structure."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No trade data found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each trade entry
        for i, trade in enumerate(data):
            if not isinstance(trade, dict):
                errors.append(f"Trade entry {i} must be a dictionary")
                continue
            
            # Check required fields
            if "id" not in trade:
                errors.append(f"Trade entry {i} missing required 'id' field")
            
            # Check attributes (can be in root or nested)
            attributes = trade.get("attributes", trade)
            required_attrs = ["block_timestamp", "tx_hash", "volume_in_usd"]
            for attr in required_attrs:
                if attr not in attributes:
                    errors.append(f"Trade entry {i} missing required attribute: {attr}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def _validate_watchlist_data(data: List[Dict]) -> ValidationResult:
        """Validate watchlist data structure."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No watchlist data found in response")
            return ValidationResult(True, errors, warnings)
        
        # Validate each watchlist entry
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                errors.append(f"Watchlist entry {i} must be a dictionary")
                continue
            
            # Check required fields
            required_fields = ["pool_id", "symbol"]
            for field in required_fields:
                if field not in entry:
                    errors.append(f"Watchlist entry {i} missing required field: {field}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def _validate_generic_data(data: List[Dict]) -> ValidationResult:
        """Generic validation for unknown collector types."""
        errors = []
        warnings = []
        
        if len(data) == 0:
            warnings.append("No data found in response")
            return ValidationResult(True, errors, warnings)
        
        # Basic validation - ensure all items are dictionaries
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                errors.append(f"Data entry {i} must be a dictionary")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def convert_dataframe_to_records(df: pd.DataFrame) -> List[Dict]:
        """
        Convert pandas DataFrame to list of dictionaries.
        
        Args:
            df: pandas DataFrame to convert
            
        Returns:
            List of dictionaries representing DataFrame rows
        """
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Expected pandas DataFrame, got {type(df)}")
        
        logger.debug(f"Converting DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return df.to_dict('records')
    
    @staticmethod
    def ensure_list_format(data: Any) -> List:
        """
        Ensure data is in list format, converting if necessary.
        
        Args:
            data: Data to convert to list format
            
        Returns:
            Data in list format
        """
        if data is None:
            return []
        elif isinstance(data, list):
            return data
        elif isinstance(data, (tuple, set)):
            return list(data)
        elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes, dict)):
            return list(data)
        else:
            return [data]
    
    @staticmethod
    def get_data_type_info(data: Any) -> Dict[str, Any]:
        """
        Get detailed information about data type and structure.
        
        Args:
            data: Data to analyze
            
        Returns:
            Dictionary with data type information
        """
        info = {
            "type": type(data).__name__,
            "is_dataframe": isinstance(data, pd.DataFrame),
            "is_list": isinstance(data, list),
            "is_dict": isinstance(data, dict),
            "is_none": data is None,
            "length": None,
            "columns": None
        }
        
        try:
            if hasattr(data, '__len__'):
                info["length"] = len(data)
            
            if isinstance(data, pd.DataFrame):
                info["columns"] = list(data.columns)
                info["shape"] = data.shape
            elif isinstance(data, list) and len(data) > 0:
                info["first_item_type"] = type(data[0]).__name__
                if isinstance(data[0], dict):
                    info["first_item_keys"] = list(data[0].keys())
        except Exception as e:
            info["analysis_error"] = str(e)
        
        return info