"""
Tests for DataTypeNormalizer utility class.
"""

import pytest
import pandas as pd
from unittest.mock import Mock

from gecko_terminal_collector.utils.data_normalizer import DataTypeNormalizer
from gecko_terminal_collector.models.core import ValidationResult


class TestDataTypeNormalizer:
    """Test cases for DataTypeNormalizer class."""
    
    def test_normalize_response_data_none(self):
        """Test normalization of None data."""
        result = DataTypeNormalizer.normalize_response_data(None)
        assert result == []
    
    def test_normalize_response_data_dataframe(self):
        """Test normalization of pandas DataFrame."""
        # Create test DataFrame
        df = pd.DataFrame({
            'id': ['dex1', 'dex2'],
            'name': ['DEX One', 'DEX Two'],
            'type': ['dex', 'dex']
        })
        
        result = DataTypeNormalizer.normalize_response_data(df)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {'id': 'dex1', 'name': 'DEX One', 'type': 'dex'}
        assert result[1] == {'id': 'dex2', 'name': 'DEX Two', 'type': 'dex'}
    
    def test_normalize_response_data_list(self):
        """Test normalization of list data (already normalized)."""
        test_data = [
            {'id': 'dex1', 'name': 'DEX One'},
            {'id': 'dex2', 'name': 'DEX Two'}
        ]
        
        result = DataTypeNormalizer.normalize_response_data(test_data)
        
        assert result == test_data
        assert isinstance(result, list)
    
    def test_normalize_response_data_dict(self):
        """Test normalization of single dictionary."""
        test_data = {'id': 'dex1', 'name': 'DEX One'}
        
        result = DataTypeNormalizer.normalize_response_data(test_data)
        
        assert result == [test_data]
        assert isinstance(result, list)
        assert len(result) == 1
    
    def test_normalize_response_data_api_format(self):
        """Test normalization of API response format with 'data' field."""
        test_data = {
            'data': [
                {'id': 'dex1', 'name': 'DEX One'},
                {'id': 'dex2', 'name': 'DEX Two'}
            ],
            'meta': {'page': {'current': 1, 'total': 1}}
        }
        
        result = DataTypeNormalizer.normalize_response_data(test_data)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {'id': 'dex1', 'name': 'DEX One'}
        assert result[1] == {'id': 'dex2', 'name': 'DEX Two'}
    
    def test_normalize_response_data_empty_api_format(self):
        """Test normalization of empty API response format."""
        test_data = {
            'meta': {'page': {'current': 1, 'total': 0}}
        }
        
        result = DataTypeNormalizer.normalize_response_data(test_data)
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_normalize_response_data_tuple(self):
        """Test normalization of tuple data."""
        test_data = ({'id': 'dex1'}, {'id': 'dex2'})
        
        result = DataTypeNormalizer.normalize_response_data(test_data)
        
        assert result == [{'id': 'dex1'}, {'id': 'dex2'}]
        assert isinstance(result, list)
    
    def test_normalize_response_data_invalid_type(self):
        """Test normalization of unsupported data type."""
        with pytest.raises(ValueError, match="Unsupported data type"):
            DataTypeNormalizer.normalize_response_data(42)
    
    def test_validate_expected_structure_dex_monitoring_valid(self):
        """Test validation of valid DEX monitoring data."""
        test_data = [
            {
                'id': 'heaven',
                'type': 'dex',
                'attributes': {'name': 'Heaven DEX'}
            },
            {
                'id': 'pumpswap',
                'type': 'dex',
                'name': 'PumpSwap'  # name can be in root or attributes
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "dex_monitoring")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_dex_monitoring_invalid(self):
        """Test validation of invalid DEX monitoring data."""
        test_data = [
            {
                'type': 'dex',
                'attributes': {'name': 'Heaven DEX'}
                # Missing 'id' field
            },
            {
                'id': 'pumpswap',
                # Missing 'type' field
                'name': 'PumpSwap'
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "dex_monitoring")
        
        assert not result.is_valid
        assert "missing required 'id' field" in str(result.errors)
        assert "missing required 'type' field" in str(result.errors)
    
    def test_validate_expected_structure_top_pools_valid(self):
        """Test validation of valid top pools data."""
        test_data = [
            {
                'id': 'pool1',
                'type': 'pool',
                'attributes': {
                    'name': 'Pool One',
                    'address': '0x123'
                },
                'relationships': {
                    'dex_id': 'heaven',
                    'base_token_id': 'token1',
                    'quote_token_id': 'token2'
                }
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "top_pools")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_top_pools_invalid(self):
        """Test validation of invalid top pools data."""
        test_data = [
            {
                'type': 'pool',
                'attributes': {
                    'name': 'Pool One'
                    # Missing 'address'
                },
                'relationships': {
                    'dex_id': 'heaven'
                    # Missing token relationships
                }
                # Missing 'id' field
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "top_pools")
        
        assert not result.is_valid
        assert "missing required 'id' field" in str(result.errors)
        assert "missing required attribute: address" in str(result.errors)
    
    def test_validate_expected_structure_ohlcv_valid(self):
        """Test validation of valid OHLCV data."""
        test_data = [
            {
                'timestamp': 1640995200,
                'open': 100.0,
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume_usd': 50000.0
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "ohlcv")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_ohlcv_invalid(self):
        """Test validation of invalid OHLCV data."""
        test_data = [
            {
                'timestamp': 1640995200,
                'open': 100.0,
                'high': 110.0,
                # Missing 'low', 'close', 'volume_usd'
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "ohlcv")
        
        assert not result.is_valid
        assert "missing required field: low" in str(result.errors)
        assert "missing required field: close" in str(result.errors)
        assert "missing required field: volume_usd" in str(result.errors)
    
    def test_validate_expected_structure_trade_valid(self):
        """Test validation of valid trade data."""
        test_data = [
            {
                'id': 'trade1',
                'attributes': {
                    'block_timestamp': '2024-01-01T00:00:00Z',
                    'tx_hash': '0xabc123',
                    'volume_in_usd': 1000.0
                }
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "trade")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_trade_invalid(self):
        """Test validation of invalid trade data."""
        test_data = [
            {
                'attributes': {
                    'block_timestamp': '2024-01-01T00:00:00Z'
                    # Missing 'tx_hash', 'volume_in_usd'
                }
                # Missing 'id' field
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "trade")
        
        assert not result.is_valid
        assert "missing required 'id' field" in str(result.errors)
        assert "missing required attribute: tx_hash" in str(result.errors)
        assert "missing required attribute: volume_in_usd" in str(result.errors)
    
    def test_validate_expected_structure_watchlist_valid(self):
        """Test validation of valid watchlist data."""
        test_data = [
            {
                'pool_id': 'pool1',
                'symbol': 'TOKEN/USDC'
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "watchlist")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_watchlist_invalid(self):
        """Test validation of invalid watchlist data."""
        test_data = [
            {
                'pool_id': 'pool1'
                # Missing 'symbol'
            }
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "watchlist")
        
        assert not result.is_valid
        assert "missing required field: symbol" in str(result.errors)
    
    def test_validate_expected_structure_generic(self):
        """Test validation of generic/unknown collector type."""
        test_data = [
            {'field1': 'value1'},
            {'field2': 'value2'}
        ]
        
        result = DataTypeNormalizer.validate_expected_structure(test_data, "unknown_type")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_expected_structure_empty_data(self):
        """Test validation of empty data."""
        result = DataTypeNormalizer.validate_expected_structure([], "dex_monitoring")
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert "No DEXes found in response" in str(result.warnings)
    
    def test_validate_expected_structure_normalization_failure(self):
        """Test validation when data normalization fails."""
        # Use an unsupported data type
        result = DataTypeNormalizer.validate_expected_structure(42, "dex_monitoring")
        
        assert not result.is_valid
        assert "Data normalization failed" in str(result.errors)
    
    def test_convert_dataframe_to_records(self):
        """Test DataFrame to records conversion."""
        df = pd.DataFrame({
            'id': ['1', '2'],
            'name': ['Item 1', 'Item 2']
        })
        
        result = DataTypeNormalizer.convert_dataframe_to_records(df)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {'id': '1', 'name': 'Item 1'}
        assert result[1] == {'id': '2', 'name': 'Item 2'}
    
    def test_convert_dataframe_to_records_invalid_input(self):
        """Test DataFrame conversion with invalid input."""
        with pytest.raises(ValueError, match="Expected pandas DataFrame"):
            DataTypeNormalizer.convert_dataframe_to_records([1, 2, 3])
    
    def test_ensure_list_format(self):
        """Test ensure_list_format method."""
        # Test None
        assert DataTypeNormalizer.ensure_list_format(None) == []
        
        # Test list (no change)
        test_list = [1, 2, 3]
        assert DataTypeNormalizer.ensure_list_format(test_list) == test_list
        
        # Test tuple
        assert DataTypeNormalizer.ensure_list_format((1, 2, 3)) == [1, 2, 3]
        
        # Test set
        result = DataTypeNormalizer.ensure_list_format({1, 2, 3})
        assert isinstance(result, list)
        assert set(result) == {1, 2, 3}
        
        # Test single item
        assert DataTypeNormalizer.ensure_list_format(42) == [42]
        
        # Test string (should not be converted to list of chars)
        assert DataTypeNormalizer.ensure_list_format("hello") == ["hello"]
    
    def test_get_data_type_info_dataframe(self):
        """Test get_data_type_info for DataFrame."""
        df = pd.DataFrame({
            'col1': [1, 2],
            'col2': ['a', 'b']
        })
        
        info = DataTypeNormalizer.get_data_type_info(df)
        
        assert info['type'] == 'DataFrame'
        assert info['is_dataframe'] is True
        assert info['is_list'] is False
        assert info['is_dict'] is False
        assert info['is_none'] is False
        assert info['length'] == 2
        assert info['columns'] == ['col1', 'col2']
        assert info['shape'] == (2, 2)
    
    def test_get_data_type_info_list(self):
        """Test get_data_type_info for list."""
        test_data = [
            {'id': '1', 'name': 'Item 1'},
            {'id': '2', 'name': 'Item 2'}
        ]
        
        info = DataTypeNormalizer.get_data_type_info(test_data)
        
        assert info['type'] == 'list'
        assert info['is_dataframe'] is False
        assert info['is_list'] is True
        assert info['is_dict'] is False
        assert info['is_none'] is False
        assert info['length'] == 2
        assert info['first_item_type'] == 'dict'
        assert info['first_item_keys'] == ['id', 'name']
    
    def test_get_data_type_info_dict(self):
        """Test get_data_type_info for dictionary."""
        test_data = {'id': '1', 'name': 'Item 1'}
        
        info = DataTypeNormalizer.get_data_type_info(test_data)
        
        assert info['type'] == 'dict'
        assert info['is_dataframe'] is False
        assert info['is_list'] is False
        assert info['is_dict'] is True
        assert info['is_none'] is False
        assert info['length'] == 2
    
    def test_get_data_type_info_none(self):
        """Test get_data_type_info for None."""
        info = DataTypeNormalizer.get_data_type_info(None)
        
        assert info['type'] == 'NoneType'
        assert info['is_dataframe'] is False
        assert info['is_list'] is False
        assert info['is_dict'] is False
        assert info['is_none'] is True
        assert info['length'] is None


class TestDataTypeNormalizerIntegration:
    """Integration tests for DataTypeNormalizer with real collector scenarios."""
    
    def test_dex_monitoring_dataframe_scenario(self):
        """Test DEX monitoring scenario with DataFrame input."""
        # Simulate DataFrame response from geckoterminal-py
        df = pd.DataFrame({
            'id': ['heaven', 'pumpswap'],
            'type': ['dex', 'dex'],
            'name': ['Heaven DEX', 'PumpSwap'],
            'attributes': [
                {'name': 'Heaven DEX'},
                {'name': 'PumpSwap'}
            ]
        })
        
        # Normalize data
        normalized = DataTypeNormalizer.normalize_response_data(df)
        
        # Validate normalized data
        validation = DataTypeNormalizer.validate_expected_structure(normalized, "dex_monitoring")
        
        assert isinstance(normalized, list)
        assert len(normalized) == 2
        assert validation.is_valid
        assert normalized[0]['id'] == 'heaven'
        assert normalized[1]['id'] == 'pumpswap'
    
    def test_top_pools_dataframe_scenario(self):
        """Test top pools scenario with DataFrame input."""
        # Simulate DataFrame response from geckoterminal-py
        df = pd.DataFrame({
            'id': ['pool1', 'pool2'],
            'type': ['pool', 'pool'],
            'name': ['Pool One', 'Pool Two'],
            'address': ['0x123', '0x456'],
            'dex_id': ['heaven', 'pumpswap'],
            'base_token_id': ['token1', 'token3'],
            'quote_token_id': ['token2', 'token4']
        })
        
        # Normalize data
        normalized = DataTypeNormalizer.normalize_response_data(df)
        
        # Validate normalized data
        validation = DataTypeNormalizer.validate_expected_structure(normalized, "top_pools")
        
        assert isinstance(normalized, list)
        assert len(normalized) == 2
        assert validation.is_valid
        assert normalized[0]['id'] == 'pool1'
        assert normalized[0]['address'] == '0x123'
    
    def test_mixed_data_structure_scenario(self):
        """Test scenario with mixed data structures (some fields in attributes, some in root)."""
        test_data = [
            {
                'id': 'dex1',
                'type': 'dex',
                'name': 'Root Name'  # name in root
            },
            {
                'id': 'dex2',
                'type': 'dex',
                'attributes': {
                    'name': 'Attribute Name'  # name in attributes
                }
            }
        ]
        
        validation = DataTypeNormalizer.validate_expected_structure(test_data, "dex_monitoring")
        
        assert validation.is_valid
        assert len(validation.errors) == 0
    
    def test_error_recovery_scenario(self):
        """Test error recovery when some data is invalid but some is valid."""
        test_data = [
            {
                'id': 'valid_dex',
                'type': 'dex',
                'name': 'Valid DEX'
            },
            {
                # Missing id and type
                'name': 'Invalid DEX'
            },
            "invalid_entry"  # Not a dict
        ]
        
        validation = DataTypeNormalizer.validate_expected_structure(test_data, "dex_monitoring")
        
        assert not validation.is_valid
        assert len(validation.errors) > 0
        # Should have errors for missing fields and invalid entry type
        assert any("missing required 'id' field" in error for error in validation.errors)
        assert any("must be a dictionary" in error for error in validation.errors)