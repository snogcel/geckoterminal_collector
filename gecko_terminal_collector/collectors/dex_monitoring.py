"""
DEX monitoring collector for fetching and validating available DEXes.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.core import CollectionResult, ValidationResult
from ..config.models import CollectionConfig
from ..database.manager import DatabaseManager
from ..database.models import DEX
from .base import BaseDataCollector

logger = logging.getLogger(__name__)


class DEXMonitoringCollector(BaseDataCollector):
    """
    Collector for monitoring available DEXes on a network.
    
    Fetches DEX information from the GeckoTerminal API and stores it in the database
    with change detection and validation. Specifically monitors for the presence
    of target DEXes (heaven and pumpswap) as required.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        network: str = "solana",
        target_dexes: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize the DEX monitoring collector.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            network: Network to monitor (default: solana)
            target_dexes: List of target DEX IDs to validate (default: ["heaven", "pumpswap"])
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(config, db_manager, **kwargs)
        self.network = network
        self.target_dexes = target_dexes or ["heaven", "pumpswap"]
    
    def get_collection_key(self) -> str:
        """Get unique key for this collector type."""
        network = getattr(self, 'network', 'solana')
        return f"dex_monitoring_{network}"
    
    async def collect(self) -> CollectionResult:
        """
        Collect DEX data from the API and store it in the database.
        
        Returns:
            CollectionResult with details about the collection operation
        """
        start_time = datetime.now()
        errors = []
        records_collected = 0
        
        try:
            logger.info(f"Starting DEX monitoring collection for network: {self.network}")
            
            # Fetch DEX data from API
            dex_data = await self.client.get_dexes_by_network(self.network)
            
            if dex_data is None:
                error_msg = f"No DEX data returned for network: {self.network}"
                errors.append(error_msg)
                logger.warning(error_msg)
                return self.create_failure_result(errors, records_collected, start_time)
            
            # Validate the data
            validation_result = await self.validate_data(dex_data)
            if not validation_result.is_valid:
                errors.extend(validation_result.errors)
                logger.error(f"DEX data validation failed: {validation_result.errors}")
                return self.create_failure_result(errors, records_collected, start_time)
            
            # Log any validation warnings
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    logger.warning(f"DEX data validation warning: {warning}")
            
            # Process and store DEX data
            dex_records = self._process_dex_data(dex_data)
            stored_count = await self._store_dex_data(dex_records)
            records_collected = stored_count
            
            # Validate target DEXes are available
            target_validation = await self._validate_target_dexes(dex_records)
            if target_validation.errors:
                errors.extend(target_validation.errors)
            if target_validation.warnings:
                for warning in target_validation.warnings:
                    logger.warning(warning)
            
            logger.info(
                f"DEX monitoring collection completed: {records_collected} DEXes processed, "
                f"{len(errors)} errors"
            )
            
            # Return result based on whether we had errors
            if errors:
                return self.create_failure_result(errors, records_collected, start_time)
            else:
                return self.create_success_result(records_collected, start_time)
                
        except Exception as e:
            error_msg = f"Unexpected error during DEX collection: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
            return self.create_failure_result(errors, records_collected, start_time)
    
    async def _validate_specific_data(self, data: Any) -> Optional[ValidationResult]:
        """
        Validate DEX-specific data structure.
        
        Args:
            data: DEX data to validate
            
        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        errors = []
        warnings = []
        
        if not isinstance(data, list):
            errors.append("DEX data must be a list")
            return ValidationResult(False, errors, warnings)
        
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
            
            # Check attributes
            attributes = dex.get("attributes", {})
            if not isinstance(attributes, dict):
                errors.append(f"DEX entry {i} attributes must be a dictionary")
            elif "name" not in attributes:
                errors.append(f"DEX entry {i} missing required 'name' in attributes")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def _process_dex_data(self, dex_data: List[Dict[str, Any]]) -> List[DEX]:
        """
        Process raw DEX data into database model objects.
        
        Args:
            dex_data: Raw DEX data from API
            
        Returns:
            List of DEX model objects
        """
        dex_records = []
        
        for dex in dex_data:
            try:
                # Skip None or invalid entries
                if not dex or not isinstance(dex, dict):
                    logger.error(f"Invalid DEX entry: {dex}")
                    continue
                
                # Extract DEX information
                dex_id = dex.get("id")
                if not dex_id:
                    logger.error(f"DEX entry missing ID: {dex}")
                    continue
                
                attributes = dex.get("attributes", {})
                dex_name = attributes.get("name", dex_id)
                
                # Create DEX record
                dex_record = DEX(
                    id=dex_id,
                    name=dex_name,
                    network=self.network,
                    last_updated=datetime.now()
                )
                
                dex_records.append(dex_record)
                logger.debug(f"Processed DEX: {dex_id} ({dex_name})")
                
            except Exception as e:
                logger.error(f"Error processing DEX data {dex}: {e}")
                continue
        
        return dex_records
    
    async def _store_dex_data(self, dex_records: List[DEX]) -> int:
        """
        Store DEX records in the database with change detection.
        
        Args:
            dex_records: List of DEX records to store
            
        Returns:
            Number of records stored/updated
        """
        if not dex_records:
            logger.info("No DEX records to store")
            return 0
        
        try:
            # Use database manager to store DEX data
            stored_count = await self.db_manager.store_dex_data(dex_records)
            logger.info(f"Stored/updated {stored_count} DEX records")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing DEX data: {e}")
            raise
    
    async def _validate_target_dexes(self, dex_records: List[DEX]) -> ValidationResult:
        """
        Validate that target DEXes are available.
        
        Args:
            dex_records: List of available DEX records
            
        Returns:
            ValidationResult indicating if target DEXes are available
        """
        errors = []
        warnings = []
        
        # Get list of available DEX IDs
        available_dex_ids = {dex.id for dex in dex_records}
        
        # Check each target DEX
        for target_dex in self.target_dexes:
            if target_dex not in available_dex_ids:
                errors.append(f"Target DEX '{target_dex}' not found in available DEXes")
            else:
                logger.info(f"Target DEX '{target_dex}' is available")
        
        # Log summary
        if not errors:
            logger.info(f"All target DEXes are available: {self.target_dexes}")
        else:
            logger.warning(f"Missing target DEXes: {[dex for dex in self.target_dexes if dex not in available_dex_ids]}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    async def get_available_dexes(self) -> List[str]:
        """
        Get list of currently available DEX IDs.
        
        Returns:
            List of available DEX IDs
        """
        try:
            dex_records = await self.db_manager.get_dexes_by_network(self.network)
            return [dex.id for dex in dex_records]
        except Exception as e:
            logger.error(f"Error retrieving available DEXes: {e}")
            return []
    
    async def is_target_dex_available(self, dex_id: str) -> bool:
        """
        Check if a specific DEX is available.
        
        Args:
            dex_id: DEX ID to check
            
        Returns:
            True if DEX is available, False otherwise
        """
        available_dexes = await self.get_available_dexes()
        return dex_id in available_dexes
    
    async def get_dex_info(self, dex_id: str) -> Optional[DEX]:
        """
        Get detailed information about a specific DEX.
        
        Args:
            dex_id: DEX ID to retrieve
            
        Returns:
            DEX record or None if not found
        """
        try:
            return await self.db_manager.get_dex_by_id(dex_id)
        except Exception as e:
            logger.error(f"Error retrieving DEX info for {dex_id}: {e}")
            return None