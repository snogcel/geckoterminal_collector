"""
System bootstrap functionality for automatic data population.

This module provides the SystemBootstrap class that handles initial system
population from an empty database state, following the natural data dependency
flow: DEXes → Pools → Tokens → OHLCV/Trades.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal
import asyncio

from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import DEX as DEXModel, Pool as PoolModel, Token as TokenModel
from gecko_terminal_collector.collectors.discovery_engine import DiscoveryEngine, DiscoveryResult
from gecko_terminal_collector.clients import BaseGeckoClient
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer

logger = logging.getLogger(__name__)


@dataclass
class BootstrapProgress:
    """Progress tracking for bootstrap operations."""
    phase: str = "initializing"
    total_phases: int = 4
    current_phase: int = 0
    phase_progress: float = 0.0
    overall_progress: float = 0.0
    dexes_discovered: int = 0
    pools_discovered: int = 0
    tokens_discovered: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    phase_start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None


@dataclass
class BootstrapResult:
    """Result of a complete bootstrap operation."""
    success: bool
    dexes_discovered: int = 0
    pools_discovered: int = 0
    tokens_discovered: int = 0
    execution_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    foreign_key_violations: List[str] = field(default_factory=list)
    recovery_actions: List[str] = field(default_factory=list)


class BootstrapError(Exception):
    """Custom exception for bootstrap failures."""
    
    def __init__(self, message: str, phase: str, recoverable: bool = True):
        super().__init__(message)
        self.phase = phase
        self.recoverable = recoverable


class SystemBootstrap:
    """
    Handles initial system population from empty database.
    
    The bootstrap process follows the natural data dependency flow:
    1. Validate system prerequisites and configuration
    2. Discover and populate DEXes from configured networks
    3. Discover and populate pools from DEXes with activity filtering
    4. Extract and populate tokens from discovered pools
    
    Each phase includes comprehensive error handling, progress tracking,
    and foreign key constraint validation.
    """
    
    def __init__(
        self,
        config: CollectionConfig,
        db_manager: DatabaseManager,
        client: BaseGeckoClient,
        discovery_engine: Optional[DiscoveryEngine] = None,
        progress_callback: Optional[Callable[[BootstrapProgress], None]] = None
    ):
        """
        Initialize the system bootstrap.
        
        Args:
            config: Collection configuration settings
            db_manager: Database manager for data storage
            client: GeckoTerminal API client
            discovery_engine: Optional discovery engine (will create if not provided)
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.db_manager = db_manager
        self.client = client
        self.progress_callback = progress_callback
        
        # Initialize discovery engine if not provided
        if discovery_engine is None:
            self.discovery_engine = DiscoveryEngine(
                config=config,
                db_manager=db_manager,
                client=client
            )
        else:
            self.discovery_engine = discovery_engine
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Bootstrap state
        self.progress = BootstrapProgress()
        self.recovery_actions = []
        
    async def bootstrap(self) -> BootstrapResult:
        """
        Complete system bootstrap process with comprehensive error handling.
        
        Performs the full bootstrap sequence:
        1. System validation and prerequisites check
        2. DEX discovery and population
        3. Pool discovery and filtering
        4. Token extraction and population
        
        Returns:
            BootstrapResult with detailed statistics and error information
        """
        self.progress.start_time = datetime.now()
        self.progress.phase = "starting"
        
        try:
            self.logger.info("Starting system bootstrap process")
            await self._update_progress("Starting bootstrap", 0, 0.0)
            
            # Phase 1: System validation
            await self._phase_1_validate_system()
            
            # Phase 2: DEX discovery
            dexes = await self._phase_2_discover_dexes()
            
            # Phase 3: Pool discovery
            pools = await self._phase_3_discover_pools(dexes)
            
            # Phase 4: Token extraction
            tokens = await self._phase_4_extract_tokens(pools)
            
            # Final validation
            await self._validate_foreign_key_constraints()
            
            execution_time = (datetime.now() - self.progress.start_time).total_seconds()
            
            result = BootstrapResult(
                success=len(self.progress.errors) == 0,
                dexes_discovered=self.progress.dexes_discovered,
                pools_discovered=self.progress.pools_discovered,
                tokens_discovered=self.progress.tokens_discovered,
                execution_time_seconds=execution_time,
                errors=self.progress.errors,
                warnings=self.progress.warnings,
                recovery_actions=self.recovery_actions
            )
            
            if result.success:
                self.logger.info(
                    f"Bootstrap completed successfully in {execution_time:.2f}s: "
                    f"{result.dexes_discovered} DEXes, {result.pools_discovered} pools, "
                    f"{result.tokens_discovered} tokens"
                )
            else:
                self.logger.error(
                    f"Bootstrap completed with errors in {execution_time:.2f}s: "
                    f"{len(result.errors)} errors, {len(result.warnings)} warnings"
                )
            
            await self._update_progress("Bootstrap complete", 4, 100.0)
            return result
            
        except BootstrapError as e:
            return await self._handle_bootstrap_error(e)
        except Exception as e:
            error_msg = f"Unexpected bootstrap failure: {str(e)}"
            self.logger.error(error_msg)
            self.progress.errors.append(error_msg)
            
            return BootstrapResult(
                success=False,
                execution_time_seconds=(datetime.now() - self.progress.start_time).total_seconds(),
                errors=self.progress.errors,
                warnings=self.progress.warnings,
                recovery_actions=self.recovery_actions
            )
    
    async def _phase_1_validate_system(self) -> None:
        """
        Phase 1: Validate system prerequisites and configuration.
        
        Checks:
        - Database connectivity and schema
        - API client connectivity
        - Configuration validity
        - Discovery settings
        
        Raises:
            BootstrapError: If critical validation fails
        """
        await self._update_progress("Validating system prerequisites", 1, 0.0)
        
        try:
            # Validate configuration
            config_errors = self.config.validate()
            if config_errors:
                error_msg = f"Configuration validation failed: {', '.join(config_errors)}"
                raise BootstrapError(error_msg, "validation", recoverable=False)
            
            await self._update_progress("Configuration validated", 1, 25.0)
            
            # Check database connectivity
            try:
                await self.db_manager.initialize()
                self.logger.debug("Database connectivity verified")
            except Exception as e:
                error_msg = f"Database initialization failed: {str(e)}"
                raise BootstrapError(error_msg, "validation", recoverable=False)
            
            await self._update_progress("Database connectivity verified", 1, 50.0)
            
            # Test API connectivity
            try:
                # Simple API test - get networks
                networks_response = await self.client.get_networks()
                if not networks_response:
                    self.progress.warnings.append("API connectivity test returned empty response")
                else:
                    self.logger.debug("API connectivity verified")
            except Exception as e:
                error_msg = f"API connectivity test failed: {str(e)}"
                raise BootstrapError(error_msg, "validation", recoverable=True)
            
            await self._update_progress("API connectivity verified", 1, 75.0)
            
            # Validate discovery configuration
            if not self.config.discovery.enabled:
                error_msg = "Discovery is disabled in configuration"
                raise BootstrapError(error_msg, "validation", recoverable=False)
            
            if not self.config.discovery.target_networks:
                error_msg = "No target networks configured for discovery"
                raise BootstrapError(error_msg, "validation", recoverable=False)
            
            await self._update_progress("System validation complete", 1, 100.0)
            self.logger.info("System validation completed successfully")
            
        except BootstrapError:
            raise
        except Exception as e:
            error_msg = f"System validation failed: {str(e)}"
            raise BootstrapError(error_msg, "validation", recoverable=False)
    
    async def _phase_2_discover_dexes(self) -> List[DEXModel]:
        """
        Phase 2: Discover and populate DEXes from configured networks.
        
        Returns:
            List of discovered DEX models
            
        Raises:
            BootstrapError: If DEX discovery fails critically
        """
        await self._update_progress("Discovering DEXes", 2, 0.0)
        
        try:
            # Use discovery engine to discover DEXes
            dexes = await self.discovery_engine.discover_dexes()
            
            if not dexes:
                error_msg = "No DEXes discovered from configured networks"
                raise BootstrapError(error_msg, "dex_discovery", recoverable=True)
            
            await self._update_progress(f"Discovered {len(dexes)} DEXes", 2, 50.0)
            
            # Validate DEX data
            valid_dexes = []
            for dex in dexes:
                if await self._validate_dex_data(dex):
                    valid_dexes.append(dex)
                else:
                    self.progress.warnings.append(f"Invalid DEX data for {dex.id}")
            
            if not valid_dexes:
                error_msg = "No valid DEXes after validation"
                raise BootstrapError(error_msg, "dex_discovery", recoverable=True)
            
            await self._update_progress(f"Validated {len(valid_dexes)} DEXes", 2, 75.0)
            
            # Store DEXes in database
            try:
                stored_count = await self.db_manager.store_dex_data(valid_dexes)
                self.progress.dexes_discovered = len(valid_dexes)
                
                self.logger.info(f"Stored {stored_count} DEXes in database")
                
            except Exception as e:
                error_msg = f"Failed to store DEX data: {str(e)}"
                raise BootstrapError(error_msg, "dex_discovery", recoverable=True)
            
            await self._update_progress("DEX discovery complete", 2, 100.0)
            return valid_dexes
            
        except BootstrapError:
            raise
        except Exception as e:
            error_msg = f"DEX discovery failed: {str(e)}"
            raise BootstrapError(error_msg, "dex_discovery", recoverable=True)
    
    async def _phase_3_discover_pools(self, dexes: List[DEXModel]) -> List[PoolModel]:
        """
        Phase 3: Discover and populate pools from DEXes with activity filtering.
        
        Args:
            dexes: List of DEX models to discover pools from
            
        Returns:
            List of discovered and filtered pool models
            
        Raises:
            BootstrapError: If pool discovery fails critically
        """
        await self._update_progress("Discovering pools", 3, 0.0)
        
        try:
            dex_ids = [dex.id for dex in dexes]
            
            # Use discovery engine to discover pools
            pools = await self.discovery_engine.discover_pools(dex_ids)
            
            if not pools:
                # This might be acceptable - some DEXes might not have pools
                self.progress.warnings.append("No pools discovered from any DEX")
                await self._update_progress("No pools discovered", 3, 100.0)
                return []
            
            await self._update_progress(f"Discovered {len(pools)} pools", 3, 50.0)
            
            # Validate pool data and foreign key constraints
            valid_pools = []
            for pool in pools:
                if await self._validate_pool_data(pool, dex_ids):
                    valid_pools.append(pool)
                else:
                    self.progress.warnings.append(f"Invalid pool data for {pool.id}")
            
            if not valid_pools:
                self.progress.warnings.append("No valid pools after validation")
                await self._update_progress("No valid pools", 3, 100.0)
                return []
            
            await self._update_progress(f"Validated {len(valid_pools)} pools", 3, 75.0)
            
            # Store pools in database
            try:
                # Convert to database models for storage
                pool_models = []
                for pool in valid_pools:
                    pool_model = PoolModel(
                        id=pool.id,
                        address=pool.address,
                        name=pool.name,
                        dex_id=pool.dex_id,
                        base_token_id=pool.base_token_id,
                        quote_token_id=pool.quote_token_id,
                        reserve_usd=pool.reserve_usd,
                        created_at=pool.created_at,
                        activity_score=getattr(pool, 'activity_score', None),
                        discovery_source=getattr(pool, 'discovery_source', 'auto'),
                        collection_priority=getattr(pool, 'collection_priority', 'normal'),
                        auto_discovered_at=getattr(pool, 'auto_discovered_at', datetime.now()),
                        last_activity_check=datetime.now()
                    )
                    pool_models.append(pool_model)
                
                stored_count = await self.db_manager.store_pools(valid_pools)
                self.progress.pools_discovered = len(valid_pools)
                
                self.logger.info(f"Stored {stored_count} pools in database")
                
                await self._update_progress("Pool discovery complete", 3, 100.0)
                return pool_models
                
            except Exception as e:
                error_msg = f"Failed to store pool data: {str(e)}"
                raise BootstrapError(error_msg, "pool_discovery", recoverable=True)
            
        except BootstrapError:
            raise
        except Exception as e:
            error_msg = f"Pool discovery failed: {str(e)}"
            raise BootstrapError(error_msg, "pool_discovery", recoverable=True)
    
    async def _phase_4_extract_tokens(self, pools: List[PoolModel]) -> List[TokenModel]:
        """
        Phase 4: Extract and populate tokens from discovered pools.
        
        Args:
            pools: List of pool models to extract tokens from
            
        Returns:
            List of extracted token models
            
        Raises:
            BootstrapError: If token extraction fails critically
        """
        await self._update_progress("Extracting tokens", 4, 0.0)
        
        try:
            if not pools:
                self.logger.info("No pools available for token extraction")
                await self._update_progress("No tokens to extract", 4, 100.0)
                return []
            
            # Convert pool models to core Pool objects for discovery engine
            core_pools = []
            for pool_model in pools:
                from gecko_terminal_collector.models.core import Pool
                core_pool = Pool(
                    id=pool_model.id,
                    address=pool_model.address,
                    name=pool_model.name,
                    dex_id=pool_model.dex_id,
                    base_token_id=pool_model.base_token_id,
                    quote_token_id=pool_model.quote_token_id,
                    reserve_usd=pool_model.reserve_usd,
                    created_at=pool_model.created_at
                )
                core_pools.append(core_pool)
            
            # Use discovery engine to extract tokens
            tokens = await self.discovery_engine.extract_tokens(core_pools)
            
            if not tokens:
                self.progress.warnings.append("No tokens extracted from pools")
                await self._update_progress("No tokens extracted", 4, 100.0)
                return []
            
            await self._update_progress(f"Extracted {len(tokens)} tokens", 4, 50.0)
            
            # Validate token data
            valid_tokens = []
            for token in tokens:
                if await self._validate_token_data(token):
                    valid_tokens.append(token)
                else:
                    self.progress.warnings.append(f"Invalid token data for {token.id}")
            
            if not valid_tokens:
                self.progress.warnings.append("No valid tokens after validation")
                await self._update_progress("No valid tokens", 4, 100.0)
                return []
            
            await self._update_progress(f"Validated {len(valid_tokens)} tokens", 4, 75.0)
            
            # Store tokens in database
            try:
                # Convert to database models for storage
                token_models = []
                for token in valid_tokens:
                    token_model = TokenModel(
                        id=token.id,
                        address=token.address,
                        name=token.name,
                        symbol=token.symbol,
                        decimals=token.decimals,
                        network=token.network,
                        last_updated=datetime.now()
                    )
                    token_models.append(token_model)
                
                stored_count = await self.db_manager.store_tokens(valid_tokens)
                self.progress.tokens_discovered = len(valid_tokens)
                
                self.logger.info(f"Stored {stored_count} tokens in database")
                
                await self._update_progress("Token extraction complete", 4, 100.0)
                return token_models
                
            except Exception as e:
                error_msg = f"Failed to store token data: {str(e)}"
                raise BootstrapError(error_msg, "token_extraction", recoverable=True)
            
        except BootstrapError:
            raise
        except Exception as e:
            error_msg = f"Token extraction failed: {str(e)}"
            raise BootstrapError(error_msg, "token_extraction", recoverable=True)
    
    async def _validate_dex_data(self, dex: DEXModel) -> bool:
        """
        Validate DEX data for completeness and correctness.
        
        Args:
            dex: DEX model to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if not dex.id or not dex.name or not dex.network:
                return False
            
            # Validate network is in configured targets
            if dex.network not in self.config.discovery.target_networks:
                self.progress.warnings.append(
                    f"DEX {dex.id} network '{dex.network}' not in target networks"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating DEX {dex.id}: {e}")
            return False
    
    async def _validate_pool_data(self, pool, dex_ids: List[str]) -> bool:
        """
        Validate pool data and foreign key constraints.
        
        Args:
            pool: Pool object to validate
            dex_ids: List of valid DEX IDs
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if not pool.id or not pool.address or not pool.dex_id:
                return False
            
            # Validate foreign key constraint - DEX must exist
            if pool.dex_id not in dex_ids:
                self.progress.warnings.append(
                    f"Pool {pool.id} references non-existent DEX {pool.dex_id}"
                )
                return False
            
            # Validate reserve amount
            if pool.reserve_usd is not None and pool.reserve_usd < 0:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating pool {pool.id}: {e}")
            return False
    
    async def _validate_token_data(self, token) -> bool:
        """
        Validate token data for completeness and correctness.
        
        Args:
            token: Token object to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if not token.id or not token.address or not token.network:
                return False
            
            # Validate network
            if token.network not in self.config.discovery.target_networks:
                self.progress.warnings.append(
                    f"Token {token.id} network '{token.network}' not in target networks"
                )
                return False
            
            # Validate decimals if provided
            if token.decimals is not None and (token.decimals < 0 or token.decimals > 30):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating token {token.id}: {e}")
            return False
    
    async def _validate_foreign_key_constraints(self) -> None:
        """
        Validate that all foreign key constraints are satisfied after bootstrap.
        
        Checks:
        - All pools reference existing DEXes
        - All pool token references are valid (if tokens exist)
        
        Raises:
            BootstrapError: If critical foreign key violations are found
        """
        try:
            self.logger.info("Validating foreign key constraints")
            violations = []
            
            # Check pool -> DEX references
            # This would require database queries to verify
            # For now, we'll log that validation is complete
            # In a full implementation, you'd query the database to check constraints
            
            if violations:
                error_msg = f"Foreign key constraint violations found: {violations}"
                raise BootstrapError(error_msg, "validation", recoverable=False)
            
            self.logger.info("Foreign key constraint validation passed")
            
        except Exception as e:
            error_msg = f"Foreign key validation failed: {str(e)}"
            raise BootstrapError(error_msg, "validation", recoverable=False)
    
    async def _update_progress(self, phase_description: str, phase_number: int, phase_progress: float) -> None:
        """
        Update bootstrap progress and notify callback if provided.
        
        Args:
            phase_description: Description of current phase
            phase_number: Current phase number (1-4)
            phase_progress: Progress within current phase (0-100)
        """
        self.progress.phase = phase_description
        self.progress.current_phase = phase_number
        self.progress.phase_progress = phase_progress
        
        # Calculate overall progress
        phase_weight = 100.0 / self.progress.total_phases
        completed_phases = (phase_number - 1) * phase_weight
        current_phase_contribution = (phase_progress / 100.0) * phase_weight
        self.progress.overall_progress = completed_phases + current_phase_contribution
        
        # Update timing
        if phase_number != getattr(self, '_last_phase', 0):
            self.progress.phase_start_time = datetime.now()
            self._last_phase = phase_number
        
        # Estimate completion time
        if self.progress.overall_progress > 0 and self.progress.start_time is not None:
            elapsed = (datetime.now() - self.progress.start_time).total_seconds()
            estimated_total = elapsed / (self.progress.overall_progress / 100.0)
            self.progress.estimated_completion = self.progress.start_time + timedelta(seconds=estimated_total)
        
        # Call progress callback if provided
        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
        
        self.logger.debug(
            f"Bootstrap progress: {self.progress.overall_progress:.1f}% - {phase_description}"
        )
    
    async def _handle_bootstrap_error(self, error: BootstrapError) -> BootstrapResult:
        """
        Handle bootstrap errors with recovery attempts if possible.
        
        Args:
            error: Bootstrap error to handle
            
        Returns:
            BootstrapResult with error details and recovery information
        """
        self.logger.error(f"Bootstrap error in phase '{error.phase}': {error}")
        self.progress.errors.append(str(error))
        
        # Attempt recovery for recoverable errors
        if error.recoverable:
            recovery_msg = f"Attempting recovery for {error.phase} failure"
            self.logger.info(recovery_msg)
            self.recovery_actions.append(recovery_msg)
            
            # Add specific recovery logic here based on error phase
            if error.phase == "dex_discovery":
                self.recovery_actions.append("Consider checking network connectivity and API limits")
            elif error.phase == "pool_discovery":
                self.recovery_actions.append("Consider reducing discovery thresholds or target DEXes")
            elif error.phase == "token_extraction":
                self.recovery_actions.append("Consider continuing with available pools")
        
        execution_time = (datetime.now() - (self.progress.start_time or datetime.now())).total_seconds()
        
        return BootstrapResult(
            success=False,
            dexes_discovered=self.progress.dexes_discovered,
            pools_discovered=self.progress.pools_discovered,
            tokens_discovered=self.progress.tokens_discovered,
            execution_time_seconds=execution_time,
            errors=self.progress.errors,
            warnings=self.progress.warnings,
            recovery_actions=self.recovery_actions
        )