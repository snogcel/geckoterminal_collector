"""
Position Manager for tracking trading positions and P&L.

This module provides comprehensive position tracking with database integration,
unrealized P&L calculation, and position update logic for buy/sell operations.
"""

import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
import pandas as pd

from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Integer, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

# Create a separate base for position tracking models
PositionBase = declarative_base()


class PositionModel(PositionBase):
    """SQLAlchemy model for position tracking."""
    
    __tablename__ = "nautilus_positions"
    
    mint_address = Column(String(100), primary_key=True)
    token_amount = Column(Numeric(30, 18), nullable=False, default=0)
    average_buy_price = Column(Numeric(30, 18), nullable=False, default=0)
    total_sol_invested = Column(Numeric(30, 18), nullable=False, default=0)
    current_value_sol = Column(Numeric(30, 18), nullable=False, default=0)
    unrealized_pnl_sol = Column(Numeric(30, 18), nullable=False, default=0)
    unrealized_pnl_percent = Column(Numeric(10, 4), nullable=False, default=0)
    first_buy_timestamp = Column(DateTime, nullable=True)
    last_trade_timestamp = Column(DateTime, nullable=False, default=func.current_timestamp())
    trade_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())


class TradeExecutionModel(PositionBase):
    """SQLAlchemy model for trade execution records."""
    
    __tablename__ = "nautilus_trade_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(100), nullable=False, unique=True)
    mint_address = Column(String(100), nullable=False)
    pair_address = Column(String(100), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    
    # Trade details
    action = Column(String(10), nullable=False)  # 'buy', 'sell', 'hold'
    sol_amount = Column(Numeric(30, 18), nullable=True)
    token_amount = Column(Numeric(30, 18), nullable=True)
    expected_price = Column(Numeric(30, 18), nullable=False)
    actual_price = Column(Numeric(30, 18), nullable=True)
    
    # Execution details
    transaction_hash = Column(String(100), nullable=True)
    execution_status = Column(String(20), nullable=False, default='pending')  # 'pending', 'confirmed', 'failed'
    gas_used = Column(Integer, nullable=True)
    execution_latency_ms = Column(Integer, nullable=True)
    
    # Performance tracking
    slippage_percent = Column(Numeric(10, 4), nullable=True)
    price_impact_percent = Column(Numeric(10, 4), nullable=True)
    pnl_sol = Column(Numeric(30, 18), nullable=True)
    
    # Signal context (stored as JSON)
    signal_data = Column(Text, nullable=True)  # JSON string
    regime_at_execution = Column(String(50), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())


@dataclass
class Position:
    """Position data class matching the design specification."""
    mint_address: str
    token_amount: float
    average_buy_price: float
    total_sol_invested: float
    current_value_sol: float
    unrealized_pnl_sol: float
    unrealized_pnl_percent: float
    first_buy_timestamp: pd.Timestamp
    last_trade_timestamp: pd.Timestamp
    trade_count: int
    is_active: bool


@dataclass
class TradeExecutionRecord:
    """Trade execution record data class matching the design specification."""
    # Trade identification
    trade_id: str
    mint_address: str
    pair_address: str
    timestamp: pd.Timestamp
    
    # Trade details
    action: str  # 'buy', 'sell', 'hold'
    sol_amount: Optional[float]
    token_amount: Optional[float]
    expected_price: float
    actual_price: Optional[float]
    
    # Execution details
    transaction_hash: Optional[str]
    execution_status: str  # 'pending', 'confirmed', 'failed'
    gas_used: Optional[int]
    execution_latency_ms: Optional[int]
    
    # Performance tracking
    slippage_percent: Optional[float]
    price_impact_percent: Optional[float]
    pnl_sol: Optional[float]
    
    # Signal context
    signal_data: Dict[str, Any]
    regime_at_execution: str
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0


class PositionManager:
    """
    Position Manager for tracking trading positions and P&L.
    
    Provides comprehensive position tracking with database integration,
    unrealized P&L calculation with current prices, and position update
    logic for buy/sell operations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PositionManager with configuration.
        
        Args:
            config: Configuration dictionary containing database settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Database configuration
        db_config = config.get('database', {})
        if db_config.get('type') == 'postgresql':
            db_url = f"postgresql://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('database')}"
        else:
            # Default to SQLite
            db_path = db_config.get('path', 'nautilus_positions.db')
            db_url = f"sqlite:///{db_path}"
        
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables if they don't exist
        PositionBase.metadata.create_all(bind=self.engine)
        
        self.logger.info(f"PositionManager initialized with database: {db_url}")
    
    async def initialize(self) -> None:
        """Initialize the position manager."""
        self.logger.info("PositionManager initialized successfully")
    
    async def get_position(self, mint_address: str) -> Optional[Position]:
        """
        Get current position for a mint address.
        
        Args:
            mint_address: The mint address to get position for
            
        Returns:
            Position object if exists, None otherwise
        """
        try:
            with self.SessionLocal() as session:
                position_model = session.query(PositionModel).filter(
                    PositionModel.mint_address == mint_address
                ).first()
                
                if not position_model:
                    return None
                
                # Convert to Position dataclass
                return Position(
                    mint_address=position_model.mint_address,
                    token_amount=float(position_model.token_amount),
                    average_buy_price=float(position_model.average_buy_price),
                    total_sol_invested=float(position_model.total_sol_invested),
                    current_value_sol=float(position_model.current_value_sol),
                    unrealized_pnl_sol=float(position_model.unrealized_pnl_sol),
                    unrealized_pnl_percent=float(position_model.unrealized_pnl_percent),
                    first_buy_timestamp=pd.Timestamp(position_model.first_buy_timestamp) if position_model.first_buy_timestamp else pd.Timestamp.now(),
                    last_trade_timestamp=pd.Timestamp(position_model.last_trade_timestamp),
                    trade_count=position_model.trade_count,
                    is_active=position_model.is_active
                )
                
        except Exception as e:
            self.logger.error(f"Error getting position for {mint_address}: {e}")
            return None
    
    async def update_position(
        self, 
        mint_address: str, 
        amount: float, 
        action: str, 
        execution_result: Dict[str, Any],
        current_price: Optional[float] = None
    ) -> None:
        """
        Update position after buy/sell operations.
        
        Args:
            mint_address: The mint address of the token
            amount: Amount of SOL (for buy) or tokens (for sell)
            action: 'buy' or 'sell'
            execution_result: Result from PumpSwap execution
            current_price: Current token price for P&L calculation
        """
        try:
            with self.SessionLocal() as session:
                # Get or create position
                position = session.query(PositionModel).filter(
                    PositionModel.mint_address == mint_address
                ).first()
                
                if not position:
                    position = PositionModel(
                        mint_address=mint_address,
                        token_amount=0,
                        average_buy_price=0,
                        total_sol_invested=0,
                        current_value_sol=0,
                        unrealized_pnl_sol=0,
                        unrealized_pnl_percent=0,
                        first_buy_timestamp=None,
                        last_trade_timestamp=datetime.utcnow(),
                        trade_count=0,
                        is_active=True
                    )
                    session.add(position)
                
                # Update position based on action
                if action == 'buy':
                    await self._handle_buy_update(position, amount, execution_result)
                elif action == 'sell':
                    await self._handle_sell_update(position, amount, execution_result)
                
                # Update P&L if current price is available
                if current_price:
                    await self._update_unrealized_pnl(position, current_price)
                
                # Update timestamps and trade count
                position.last_trade_timestamp = datetime.utcnow()
                position.trade_count += 1
                
                # Commit changes
                session.commit()
                
                self.logger.info(f"Position updated for {mint_address}: {action} {amount}")
                
        except Exception as e:
            self.logger.error(f"Error updating position for {mint_address}: {e}")
            raise
    
    async def _handle_buy_update(
        self, 
        position: PositionModel, 
        sol_amount: float, 
        execution_result: Dict[str, Any]
    ) -> None:
        """Handle position update for buy operations."""
        # Extract execution details
        actual_price = execution_result.get('actual_price', 0)
        tokens_received = execution_result.get('tokens_received', 0)
        
        if tokens_received > 0 and actual_price > 0:
            # Calculate new average buy price
            total_tokens_after = float(position.token_amount) + tokens_received
            total_investment_after = float(position.total_sol_invested) + sol_amount
            
            position.average_buy_price = total_investment_after / total_tokens_after
            position.token_amount = total_tokens_after
            position.total_sol_invested = total_investment_after
            
            # Set first buy timestamp if this is the first buy
            if position.first_buy_timestamp is None:
                position.first_buy_timestamp = datetime.utcnow()
        else:
            # Fallback calculation if execution details are incomplete
            estimated_tokens = sol_amount / max(actual_price, 0.000001)  # Avoid division by zero
            
            total_tokens_after = float(position.token_amount) + estimated_tokens
            total_investment_after = float(position.total_sol_invested) + sol_amount
            
            if total_tokens_after > 0:
                position.average_buy_price = total_investment_after / total_tokens_after
                position.token_amount = total_tokens_after
                position.total_sol_invested = total_investment_after
                
                if position.first_buy_timestamp is None:
                    position.first_buy_timestamp = datetime.utcnow()
    
    async def _handle_sell_update(
        self, 
        position: PositionModel, 
        token_amount: float, 
        execution_result: Dict[str, Any]
    ) -> None:
        """Handle position update for sell operations."""
        # Extract execution details
        sol_received = execution_result.get('sol_received', 0)
        
        # Update token amount
        new_token_amount = max(0, float(position.token_amount) - token_amount)
        position.token_amount = new_token_amount
        
        # Calculate realized P&L
        if token_amount > 0 and float(position.average_buy_price) > 0:
            cost_basis = token_amount * float(position.average_buy_price)
            realized_pnl = sol_received - cost_basis
            
            # Update total investment (reduce by cost basis)
            position.total_sol_invested = max(0, float(position.total_sol_invested) - cost_basis)
            
            self.logger.info(f"Realized P&L: {realized_pnl:.6f} SOL")
        
        # Mark position as inactive if no tokens left
        if new_token_amount <= 0.000001:  # Account for floating point precision
            position.is_active = False
            position.token_amount = 0
            position.total_sol_invested = 0
    
    async def _update_unrealized_pnl(self, position: PositionModel, current_price: float) -> None:
        """Update unrealized P&L based on current price."""
        if float(position.token_amount) > 0 and current_price > 0:
            # Calculate current value
            current_value = float(position.token_amount) * current_price
            position.current_value_sol = current_value
            
            # Calculate unrealized P&L
            unrealized_pnl = current_value - float(position.total_sol_invested)
            position.unrealized_pnl_sol = unrealized_pnl
            
            # Calculate percentage P&L
            if float(position.total_sol_invested) > 0:
                position.unrealized_pnl_percent = (unrealized_pnl / float(position.total_sol_invested)) * 100
            else:
                position.unrealized_pnl_percent = 0
    
    async def update_position_prices(self, price_data: Dict[str, float]) -> None:
        """
        Update unrealized P&L for all active positions with current prices.
        
        Args:
            price_data: Dictionary mapping mint_address to current price
        """
        try:
            with self.SessionLocal() as session:
                active_positions = session.query(PositionModel).filter(
                    PositionModel.is_active == True,
                    PositionModel.token_amount > 0
                ).all()
                
                for position in active_positions:
                    current_price = price_data.get(position.mint_address)
                    if current_price:
                        await self._update_unrealized_pnl(position, current_price)
                
                session.commit()
                
                self.logger.info(f"Updated prices for {len(active_positions)} active positions")
                
        except Exception as e:
            self.logger.error(f"Error updating position prices: {e}")
    
    async def get_all_positions(self, active_only: bool = True) -> List[Position]:
        """
        Get all positions.
        
        Args:
            active_only: If True, return only active positions
            
        Returns:
            List of Position objects
        """
        try:
            with self.SessionLocal() as session:
                query = session.query(PositionModel)
                
                if active_only:
                    query = query.filter(PositionModel.is_active == True)
                
                position_models = query.all()
                
                positions = []
                for model in position_models:
                    position = Position(
                        mint_address=model.mint_address,
                        token_amount=float(model.token_amount),
                        average_buy_price=float(model.average_buy_price),
                        total_sol_invested=float(model.total_sol_invested),
                        current_value_sol=float(model.current_value_sol),
                        unrealized_pnl_sol=float(model.unrealized_pnl_sol),
                        unrealized_pnl_percent=float(model.unrealized_pnl_percent),
                        first_buy_timestamp=pd.Timestamp(model.first_buy_timestamp) if model.first_buy_timestamp else pd.Timestamp.now(),
                        last_trade_timestamp=pd.Timestamp(model.last_trade_timestamp),
                        trade_count=model.trade_count,
                        is_active=model.is_active
                    )
                    positions.append(position)
                
                return positions
                
        except Exception as e:
            self.logger.error(f"Error getting all positions: {e}")
            return []
    
    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary with total P&L and position count.
        
        Returns:
            Dictionary with portfolio summary statistics
        """
        try:
            positions = await self.get_all_positions(active_only=True)
            
            total_invested = sum(pos.total_sol_invested for pos in positions)
            total_current_value = sum(pos.current_value_sol for pos in positions)
            total_unrealized_pnl = sum(pos.unrealized_pnl_sol for pos in positions)
            
            portfolio_pnl_percent = 0
            if total_invested > 0:
                portfolio_pnl_percent = (total_unrealized_pnl / total_invested) * 100
            
            return {
                'active_positions': len(positions),
                'total_invested_sol': total_invested,
                'total_current_value_sol': total_current_value,
                'total_unrealized_pnl_sol': total_unrealized_pnl,
                'portfolio_pnl_percent': portfolio_pnl_percent,
                'positions': [asdict(pos) for pos in positions]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {
                'active_positions': 0,
                'total_invested_sol': 0,
                'total_current_value_sol': 0,
                'total_unrealized_pnl_sol': 0,
                'portfolio_pnl_percent': 0,
                'positions': []
            }
    
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            self.engine.dispose()
            self.logger.info("PositionManager closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing PositionManager: {e}")