"""
Workflow validation utilities for testing end-to-end data collection workflows.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a workflow validation step."""
    success: bool
    message: str
    details: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class WorkflowValidator:
    """
    Utility class for validating end-to-end data collection workflows.
    
    Provides methods to test the complete pipeline from watchlist processing
    through data collection to QLib export.
    """
    
    def __init__(self, config: CollectionConfig, db_manager: DatabaseManager):
        """
        Initialize workflow validator.
        
        Args:
            config: System configuration
            db_manager: Database manager instance
        """
        self.config = config
        self.db_manager = db_manager
        
    async def validate_api_connectivity(self) -> ValidationResult:
        """
        Validate GeckoTerminal API connectivity and basic functionality.
        
        Returns:
            ValidationResult with API connectivity status
        """
        try:
            from gecko_terminal_collector.clients.gecko_client import GeckoTerminalAsyncClient
            
            client = GeckoTerminalAsyncClient()
            errors = []
            warnings = []
            details = {}
            
            # Test basic API connectivity
            try:
                networks = await client.get_networks()
                if networks:
                    details['networks_available'] = len(networks)
                    details['solana_available'] = any(
                        network.get('id') == 'solana' for network in networks
                    )
                else:
                    errors.append("API returned no networks")
                    
            except Exception as e:
                errors.append(f"Failed to get networks: {e}")
            
            # Test DEX availability
            try:
                if details.get('solana_available'):
                    dexes = await client.get_dexes_by_network('solana')
                    if dexes:
                        available_dex_ids = [dex.get('id') for dex in dexes]
                        details['dexes_available'] = len(dexes)
                        details['target_dexes_available'] = []
                        
                        for target_dex in self.config.dexes.targets:
                            if target_dex in available_dex_ids:
                                details['target_dexes_available'].append(target_dex)
                            else:
                                warnings.append(f"Target DEX '{target_dex}' not found in API")
                    else:
                        errors.append("No DEXes available for Solana network")
                        
            except Exception as e:
                errors.append(f"Failed to get DEXes: {e}")
            
            success = len(errors) == 0
            message = "API connectivity validated successfully" if success else "API connectivity validation failed"
            
            return ValidationResult(
                success=success,
                message=message,
                details=details,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"API validation error: {e}",
                details={},
                errors=[str(e)],
                warnings=[]
            )
    
    async def validate_database_schema(self) -> ValidationResult:
        """
        Validate database schema and connectivity.
        
        Returns:
            ValidationResult with database validation status
        """
        try:
            errors = []
            warnings = []
            details = {}
            
            # Test basic connectivity
            try:
                await self.db_manager.initialize()
                details['connection_status'] = 'connected'
            except Exception as e:
                errors.append(f"Database connection failed: {e}")
                return ValidationResult(
                    success=False,
                    message="Database connection failed",
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            # Test table existence
            required_tables = ['pools', 'tokens', 'ohlcv_data', 'trades', 'watchlist', 'dexes']
            existing_tables = await self.db_manager.get_table_names()
            
            details['existing_tables'] = existing_tables
            details['required_tables'] = required_tables
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            if missing_tables:
                errors.extend([f"Missing table: {table}" for table in missing_tables])
            
            # Test basic operations
            try:
                # Test a simple query
                pools_count = await self.db_manager.count_records('pools')
                details['pools_count'] = pools_count
                
                ohlcv_count = await self.db_manager.count_records('ohlcv_data')
                details['ohlcv_count'] = ohlcv_count
                
            except Exception as e:
                warnings.append(f"Could not query table counts: {e}")
            
            success = len(errors) == 0
            message = "Database schema validated successfully" if success else "Database schema validation failed"
            
            return ValidationResult(
                success=success,
                message=message,
                details=details,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Database validation error: {e}",
                details={},
                errors=[str(e)],
                warnings=[]
            )
    
    async def validate_data_quality(self, 
                                   pool_id: str, 
                                   timeframe: str = "1h",
                                   days_back: int = 7) -> ValidationResult:
        """
        Validate data quality for a specific pool.
        
        Args:
            pool_id: Pool ID to validate
            timeframe: Timeframe to check
            days_back: Number of days to look back
            
        Returns:
            ValidationResult with data quality assessment
        """
        try:
            errors = []
            warnings = []
            details = {}
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # Get OHLCV data for the pool
            ohlcv_records = await self.db_manager.get_ohlcv_data(
                pool_id=pool_id,
                timeframe=timeframe,
                start_time=start_date,
                end_time=end_date
            )
            
            if not ohlcv_records:
                errors.append(f"No OHLCV data found for pool {pool_id}")
                return ValidationResult(
                    success=False,
                    message="No data available for quality validation",
                    details=details,
                    errors=errors,
                    warnings=warnings
                )
            
            details['total_records'] = len(ohlcv_records)
            details['date_range'] = {
                'start': min(record.datetime for record in ohlcv_records).isoformat(),
                'end': max(record.datetime for record in ohlcv_records).isoformat()
            }
            
            # Check for data consistency
            price_issues = 0
            volume_issues = 0
            
            for record in ohlcv_records:
                # Check price relationships
                if not (record.low_price <= record.open_price <= record.high_price and
                        record.low_price <= record.close_price <= record.high_price):
                    price_issues += 1
                
                # Check for zero or negative values
                if (record.open_price <= 0 or record.high_price <= 0 or 
                    record.low_price <= 0 or record.close_price <= 0):
                    price_issues += 1
                
                if record.volume_usd < 0:
                    volume_issues += 1
            
            details['price_issues'] = price_issues
            details['volume_issues'] = volume_issues
            
            if price_issues > 0:
                warnings.append(f"Found {price_issues} records with price inconsistencies")
            
            if volume_issues > 0:
                warnings.append(f"Found {volume_issues} records with volume issues")
            
            # Calculate data quality score
            total_issues = price_issues + volume_issues
            quality_score = max(0, 1 - (total_issues / len(ohlcv_records)))
            details['quality_score'] = quality_score
            
            # Check data continuity
            try:
                continuity_report = await self.db_manager.check_data_continuity(
                    pool_id, timeframe
                )
                details['continuity'] = {
                    'total_gaps': continuity_report.total_gaps,
                    'data_quality_score': continuity_report.data_quality_score
                }
                
                if continuity_report.total_gaps > 0:
                    warnings.append(f"Found {continuity_report.total_gaps} data gaps")
                    
            except Exception as e:
                warnings.append(f"Could not check data continuity: {e}")
            
            success = len(errors) == 0 and quality_score >= 0.8
            message = f"Data quality validation completed (score: {quality_score:.2f})"
            
            return ValidationResult(
                success=success,
                message=message,
                details=details,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Data quality validation error: {e}",
                details={},
                errors=[str(e)],
                warnings=[]
            )
    
    async def validate_qlib_export(self, 
                                  symbols: List[str],
                                  timeframe: str = "1h",
                                  days_back: int = 7) -> ValidationResult:
        """
        Validate QLib export functionality.
        
        Args:
            symbols: List of symbols to test export for
            timeframe: Timeframe to export
            days_back: Number of days to export
            
        Returns:
            ValidationResult with export validation status
        """
        try:
            from gecko_terminal_collector.qlib.exporter import QLibExporter
            
            errors = []
            warnings = []
            details = {}
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            exporter = QLibExporter(self.db_manager)
            
            # Test symbol list generation
            try:
                available_symbols = await exporter.get_symbol_list()
                details['available_symbols'] = len(available_symbols)
                
                # Check if requested symbols are available
                missing_symbols = [s for s in symbols if s not in available_symbols]
                if missing_symbols:
                    warnings.extend([f"Symbol not available: {s}" for s in missing_symbols])
                
                valid_symbols = [s for s in symbols if s in available_symbols]
                details['valid_symbols'] = len(valid_symbols)
                
            except Exception as e:
                errors.append(f"Failed to get symbol list: {e}")
                valid_symbols = symbols  # Try anyway
            
            # Test data export
            if valid_symbols:
                try:
                    df = await exporter.export_ohlcv_data(
                        symbols=valid_symbols,
                        start_date=start_date,
                        end_date=end_date,
                        timeframe=timeframe
                    )
                    
                    if df.empty:
                        warnings.append("Export returned empty DataFrame")
                        details['exported_records'] = 0
                    else:
                        details['exported_records'] = len(df)
                        details['exported_symbols'] = df['symbol'].nunique()
                        
                        # Validate DataFrame structure
                        required_columns = ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume']
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        
                        if missing_columns:
                            errors.extend([f"Missing column: {col}" for col in missing_columns])
                        else:
                            details['qlib_format_valid'] = True
                            
                            # Check for data types
                            if 'datetime' in df.columns:
                                details['datetime_type'] = str(df['datetime'].dtype)
                            
                            # Check for null values
                            null_counts = df.isnull().sum()
                            if null_counts.any():
                                details['null_values'] = null_counts.to_dict()
                                warnings.append("Found null values in exported data")
                        
                except Exception as e:
                    errors.append(f"Failed to export data: {e}")
            else:
                errors.append("No valid symbols available for export")
            
            success = len(errors) == 0
            message = "QLib export validation completed successfully" if success else "QLib export validation failed"
            
            return ValidationResult(
                success=success,
                message=message,
                details=details,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"QLib export validation error: {e}",
                details={},
                errors=[str(e)],
                warnings=[]
            )
    
    async def run_comprehensive_validation(self) -> Dict[str, ValidationResult]:
        """
        Run comprehensive validation of all workflow components.
        
        Returns:
            Dictionary of validation results by component
        """
        results = {}
        
        # API connectivity
        logger.info("Validating API connectivity...")
        results['api'] = await self.validate_api_connectivity()
        
        # Database schema
        logger.info("Validating database schema...")
        results['database'] = await self.validate_database_schema()
        
        # QLib export (with empty symbol list to test basic functionality)
        logger.info("Validating QLib export...")
        results['qlib_export'] = await self.validate_qlib_export([])
        
        return results