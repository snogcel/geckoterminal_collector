"""
Trade Execution Record System for comprehensive trade logging and monitoring.

This module provides comprehensive trade logging with transaction hashes,
execution performance tracking (latency, slippage, gas costs), trade status
monitoring and confirmation, and storage of signal context and regime data.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd

from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Integer, Text, desc
from sqlalchemy.orm import sessionmaker

from .position_manager import PositionBase, TradeExecutionModel, TradeExecutionRecord


class TradeExecutionRecorder:
    """
    Trade Execution Record System for comprehensive trade logging and monitoring.
    
    Provides comprehensive trade logging with transaction hashes, execution
    performance tracking, trade status monitoring, and signal context storage.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize TradeExecutionRecorder with configuration.
        
        Args:
            config: Configuration dictionary containing database settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Use the same database configuration as PositionManager
        from sqlalchemy import create_engine
        
        db_config = config.get('database', {})
        if db_config.get('type') == 'postgresql':
            db_url = f"postgresql://{db_config.get('user')}:{db_config.get('password')}@{db_config.get('host')}:{db_config.get('port')}/{db_config.get('database')}"
        else:
            # Default to SQLite
            db_path = db_config.get('path', 'nautilus_positions.db')
            db_url = f"sqlite:///{db_path}"
        
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Ensure tables exist
        PositionBase.metadata.create_all(bind=self.engine)
        
        self.logger.info(f"TradeExecutionRecorder initialized with database: {db_url}")
    
    async def initialize(self) -> None:
        """Initialize the trade execution recorder."""
        self.logger.info("TradeExecutionRecorder initialized successfully")
    
    async def record_trade_attempt(
        self,
        mint_address: str,
        action: str,
        signal_data: Dict[str, Any],
        expected_price: float,
        sol_amount: Optional[float] = None,
        token_amount: Optional[float] = None,
        pair_address: Optional[str] = None
    ) -> str:
        """
        Record a trade attempt before execution.
        
        Args:
            mint_address: The mint address of the token
            action: 'buy', 'sell', or 'hold'
            signal_data: The Q50 signal data that triggered the trade
            expected_price: Expected execution price
            sol_amount: Amount of SOL for buy orders
            token_amount: Amount of tokens for sell orders
            pair_address: PumpSwap pair address
            
        Returns:
            Trade ID for tracking the execution
        """
        try:
            import uuid
            trade_id = f"{action}_{mint_address}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
            
            with self.SessionLocal() as session:
                trade_record = TradeExecutionModel(
                    trade_id=trade_id,
                    mint_address=mint_address,
                    pair_address=pair_address,
                    timestamp=datetime.utcnow(),
                    action=action,
                    sol_amount=sol_amount,
                    token_amount=token_amount,
                    expected_price=expected_price,
                    execution_status='pending',
                    signal_data=json.dumps(signal_data),
                    regime_at_execution=signal_data.get('regime', 'unknown'),
                    retry_count=0
                )
                
                session.add(trade_record)
                session.commit()
                
                self.logger.info(f"Trade attempt recorded: {trade_id}")
                return trade_id
                
        except Exception as e:
            self.logger.error(f"Error recording trade attempt: {e}")
            return f"error_{uuid.uuid4().hex[:8]}"
    
    async def update_trade_execution(
        self,
        trade_id: str,
        execution_result: Dict[str, Any],
        execution_latency_ms: Optional[int] = None
    ) -> None:
        """
        Update trade record with execution results.
        
        Args:
            trade_id: The trade ID to update
            execution_result: Result from PumpSwap execution
            execution_latency_ms: Execution latency in milliseconds
        """
        try:
            with self.SessionLocal() as session:
                trade_record = session.query(TradeExecutionModel).filter(
                    TradeExecutionModel.trade_id == trade_id
                ).first()
                
                if not trade_record:
                    self.logger.warning(f"Trade record not found: {trade_id}")
                    return
                
                # Update execution details
                trade_record.transaction_hash = execution_result.get('transaction_hash')
                trade_record.actual_price = execution_result.get('actual_price')
                trade_record.execution_status = execution_result.get('status', 'unknown')
                trade_record.gas_used = execution_result.get('gas_used')
                trade_record.execution_latency_ms = execution_latency_ms
                
                # Calculate performance metrics
                if trade_record.expected_price and trade_record.actual_price:
                    expected = float(trade_record.expected_price)
                    actual = float(trade_record.actual_price)
                    
                    # Calculate slippage
                    slippage = abs(actual - expected) / expected * 100
                    trade_record.slippage_percent = slippage
                
                # Calculate price impact if available
                if 'price_impact_percent' in execution_result:
                    trade_record.price_impact_percent = execution_result['price_impact_percent']
                
                # Calculate P&L for sell orders
                if trade_record.action == 'sell' and 'sol_received' in execution_result:
                    sol_received = execution_result['sol_received']
                    if trade_record.token_amount and trade_record.expected_price:
                        expected_sol = float(trade_record.token_amount) * float(trade_record.expected_price)
                        trade_record.pnl_sol = sol_received - expected_sol
                
                # Handle errors
                if execution_result.get('status') == 'error':
                    trade_record.error_message = execution_result.get('error_message', 'Unknown error')
                    trade_record.retry_count += 1
                
                session.commit()
                
                self.logger.info(f"Trade execution updated: {trade_id} - {execution_result.get('status')}")
                
        except Exception as e:
            self.logger.error(f"Error updating trade execution {trade_id}: {e}")
    
    async def confirm_transaction(
        self,
        trade_id: str,
        transaction_hash: str,
        confirmation_data: Dict[str, Any]
    ) -> None:
        """
        Confirm transaction on blockchain and update final status.
        
        Args:
            trade_id: The trade ID to confirm
            transaction_hash: Blockchain transaction hash
            confirmation_data: Additional confirmation data from blockchain
        """
        try:
            with self.SessionLocal() as session:
                trade_record = session.query(TradeExecutionModel).filter(
                    TradeExecutionModel.trade_id == trade_id
                ).first()
                
                if not trade_record:
                    self.logger.warning(f"Trade record not found for confirmation: {trade_id}")
                    return
                
                # Update confirmation status
                trade_record.execution_status = 'confirmed'
                trade_record.transaction_hash = transaction_hash
                
                # Update with blockchain confirmation data
                if 'gas_used' in confirmation_data:
                    trade_record.gas_used = confirmation_data['gas_used']
                
                if 'actual_price' in confirmation_data:
                    trade_record.actual_price = confirmation_data['actual_price']
                
                # Recalculate slippage with confirmed price
                if trade_record.expected_price and trade_record.actual_price:
                    expected = float(trade_record.expected_price)
                    actual = float(trade_record.actual_price)
                    slippage = abs(actual - expected) / expected * 100
                    trade_record.slippage_percent = slippage
                
                session.commit()
                
                self.logger.info(f"Transaction confirmed: {trade_id} - {transaction_hash}")
                
        except Exception as e:
            self.logger.error(f"Error confirming transaction {trade_id}: {e}")
    
    async def mark_trade_failed(
        self,
        trade_id: str,
        error_message: str,
        retry_count: Optional[int] = None
    ) -> None:
        """
        Mark a trade as failed with error details.
        
        Args:
            trade_id: The trade ID to mark as failed
            error_message: Error message describing the failure
            retry_count: Number of retry attempts
        """
        try:
            with self.SessionLocal() as session:
                trade_record = session.query(TradeExecutionModel).filter(
                    TradeExecutionModel.trade_id == trade_id
                ).first()
                
                if not trade_record:
                    self.logger.warning(f"Trade record not found for failure: {trade_id}")
                    return
                
                trade_record.execution_status = 'failed'
                trade_record.error_message = error_message
                
                if retry_count is not None:
                    trade_record.retry_count = retry_count
                else:
                    trade_record.retry_count += 1
                
                session.commit()
                
                self.logger.warning(f"Trade marked as failed: {trade_id} - {error_message}")
                
        except Exception as e:
            self.logger.error(f"Error marking trade as failed {trade_id}: {e}")
    
    async def get_trade_record(self, trade_id: str) -> Optional[TradeExecutionRecord]:
        """
        Get a trade execution record by ID.
        
        Args:
            trade_id: The trade ID to retrieve
            
        Returns:
            TradeExecutionRecord if found, None otherwise
        """
        try:
            with self.SessionLocal() as session:
                trade_model = session.query(TradeExecutionModel).filter(
                    TradeExecutionModel.trade_id == trade_id
                ).first()
                
                if not trade_model:
                    return None
                
                # Parse signal data
                signal_data = {}
                if trade_model.signal_data:
                    try:
                        signal_data = json.loads(trade_model.signal_data)
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid signal data JSON for trade {trade_id}")
                
                return TradeExecutionRecord(
                    trade_id=trade_model.trade_id,
                    mint_address=trade_model.mint_address,
                    pair_address=trade_model.pair_address or "",
                    timestamp=pd.Timestamp(trade_model.timestamp),
                    action=trade_model.action,
                    sol_amount=float(trade_model.sol_amount) if trade_model.sol_amount else None,
                    token_amount=float(trade_model.token_amount) if trade_model.token_amount else None,
                    expected_price=float(trade_model.expected_price),
                    actual_price=float(trade_model.actual_price) if trade_model.actual_price else None,
                    transaction_hash=trade_model.transaction_hash,
                    execution_status=trade_model.execution_status,
                    gas_used=trade_model.gas_used,
                    execution_latency_ms=trade_model.execution_latency_ms,
                    slippage_percent=float(trade_model.slippage_percent) if trade_model.slippage_percent else None,
                    price_impact_percent=float(trade_model.price_impact_percent) if trade_model.price_impact_percent else None,
                    pnl_sol=float(trade_model.pnl_sol) if trade_model.pnl_sol else None,
                    signal_data=signal_data,
                    regime_at_execution=trade_model.regime_at_execution or "unknown",
                    error_message=trade_model.error_message,
                    retry_count=trade_model.retry_count
                )
                
        except Exception as e:
            self.logger.error(f"Error getting trade record {trade_id}: {e}")
            return None
    
    async def get_recent_trades(
        self,
        limit: int = 100,
        mint_address: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[TradeExecutionRecord]:
        """
        Get recent trade execution records.
        
        Args:
            limit: Maximum number of records to return
            mint_address: Filter by specific mint address
            status_filter: Filter by execution status
            
        Returns:
            List of TradeExecutionRecord objects
        """
        try:
            with self.SessionLocal() as session:
                query = session.query(TradeExecutionModel)
                
                if mint_address:
                    query = query.filter(TradeExecutionModel.mint_address == mint_address)
                
                if status_filter:
                    query = query.filter(TradeExecutionModel.execution_status == status_filter)
                
                trade_models = query.order_by(desc(TradeExecutionModel.timestamp)).limit(limit).all()
                
                trades = []
                for model in trade_models:
                    # Parse signal data
                    signal_data = {}
                    if model.signal_data:
                        try:
                            signal_data = json.loads(model.signal_data)
                        except json.JSONDecodeError:
                            pass
                    
                    trade = TradeExecutionRecord(
                        trade_id=model.trade_id,
                        mint_address=model.mint_address,
                        pair_address=model.pair_address or "",
                        timestamp=pd.Timestamp(model.timestamp),
                        action=model.action,
                        sol_amount=float(model.sol_amount) if model.sol_amount else None,
                        token_amount=float(model.token_amount) if model.token_amount else None,
                        expected_price=float(model.expected_price),
                        actual_price=float(model.actual_price) if model.actual_price else None,
                        transaction_hash=model.transaction_hash,
                        execution_status=model.execution_status,
                        gas_used=model.gas_used,
                        execution_latency_ms=model.execution_latency_ms,
                        slippage_percent=float(model.slippage_percent) if model.slippage_percent else None,
                        price_impact_percent=float(model.price_impact_percent) if model.price_impact_percent else None,
                        pnl_sol=float(model.pnl_sol) if model.pnl_sol else None,
                        signal_data=signal_data,
                        regime_at_execution=model.regime_at_execution or "unknown",
                        error_message=model.error_message,
                        retry_count=model.retry_count
                    )
                    trades.append(trade)
                
                return trades
                
        except Exception as e:
            self.logger.error(f"Error getting recent trades: {e}")
            return []
    
    async def get_execution_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get execution performance statistics.
        
        Args:
            start_date: Start date for statistics (optional)
            end_date: End date for statistics (optional)
            
        Returns:
            Dictionary with execution statistics
        """
        try:
            with self.SessionLocal() as session:
                query = session.query(TradeExecutionModel)
                
                if start_date:
                    query = query.filter(TradeExecutionModel.timestamp >= start_date)
                
                if end_date:
                    query = query.filter(TradeExecutionModel.timestamp <= end_date)
                
                all_trades = query.all()
                
                if not all_trades:
                    return {
                        'total_trades': 0,
                        'successful_trades': 0,
                        'failed_trades': 0,
                        'success_rate': 0,
                        'average_execution_latency_ms': 0,
                        'average_slippage_percent': 0,
                        'average_gas_used': 0,
                        'total_pnl_sol': 0
                    }
                
                # Calculate statistics
                total_trades = len(all_trades)
                successful_trades = len([t for t in all_trades if t.execution_status == 'confirmed'])
                failed_trades = len([t for t in all_trades if t.execution_status == 'failed'])
                success_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0
                
                # Latency statistics
                latencies = [t.execution_latency_ms for t in all_trades if t.execution_latency_ms is not None]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                
                # Slippage statistics
                slippages = [float(t.slippage_percent) for t in all_trades if t.slippage_percent is not None]
                avg_slippage = sum(slippages) / len(slippages) if slippages else 0
                
                # Gas statistics
                gas_amounts = [t.gas_used for t in all_trades if t.gas_used is not None]
                avg_gas = sum(gas_amounts) / len(gas_amounts) if gas_amounts else 0
                
                # P&L statistics
                pnls = [float(t.pnl_sol) for t in all_trades if t.pnl_sol is not None]
                total_pnl = sum(pnls) if pnls else 0
                
                return {
                    'total_trades': total_trades,
                    'successful_trades': successful_trades,
                    'failed_trades': failed_trades,
                    'success_rate': success_rate,
                    'average_execution_latency_ms': avg_latency,
                    'average_slippage_percent': avg_slippage,
                    'average_gas_used': avg_gas,
                    'total_pnl_sol': total_pnl,
                    'regime_breakdown': self._get_regime_breakdown(all_trades)
                }
                
        except Exception as e:
            self.logger.error(f"Error getting execution statistics: {e}")
            return {}
    
    def _get_regime_breakdown(self, trades: List[TradeExecutionModel]) -> Dict[str, int]:
        """Get breakdown of trades by regime."""
        regime_counts = {}
        for trade in trades:
            regime = trade.regime_at_execution or 'unknown'
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        return regime_counts
    
    async def cleanup_old_records(self, days_to_keep: int = 30) -> int:
        """
        Clean up old trade execution records.
        
        Args:
            days_to_keep: Number of days of records to keep
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.utcnow() - pd.Timedelta(days=days_to_keep)
            
            with self.SessionLocal() as session:
                deleted_count = session.query(TradeExecutionModel).filter(
                    TradeExecutionModel.timestamp < cutoff_date
                ).delete()
                
                session.commit()
                
                self.logger.info(f"Cleaned up {deleted_count} old trade records")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        try:
            self.engine.dispose()
            self.logger.info("TradeExecutionRecorder closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing TradeExecutionRecorder: {e}")