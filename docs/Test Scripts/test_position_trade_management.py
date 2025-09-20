"""
Test suite for Position and Trade Management components.

Tests the PositionManager and TradeExecutionRecorder implementations
to ensure they meet the requirements for position tracking, P&L calculation,
and comprehensive trade logging.
"""

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pandas as pd

# Import the components we're testing
from nautilus_poc.position_manager import PositionManager, Position
from nautilus_poc.trade_execution_recorder import TradeExecutionRecorder, TradeExecutionRecord


class TestPositionManager(unittest.TestCase):
    """Test cases for PositionManager."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = {
            'database': {
                'type': 'sqlite',
                'path': self.temp_db.name
            }
        }
        
        self.position_manager = PositionManager(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close and remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    async def test_position_creation_and_retrieval(self):
        """Test creating and retrieving positions."""
        await self.position_manager.initialize()
        
        mint_address = "test_mint_123"
        
        # Initially no position should exist
        position = await self.position_manager.get_position(mint_address)
        self.assertIsNone(position)
        
        # Create a position through a buy operation
        execution_result = {
            'actual_price': 0.001,
            'tokens_received': 1000,
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=1.0,  # 1 SOL
            action='buy',
            execution_result=execution_result,
            current_price=0.001
        )
        
        # Now position should exist
        position = await self.position_manager.get_position(mint_address)
        self.assertIsNotNone(position)
        self.assertEqual(position.mint_address, mint_address)
        self.assertEqual(position.token_amount, 1000)
        self.assertEqual(position.total_sol_invested, 1.0)
        self.assertTrue(position.is_active)
    
    async def test_buy_position_updates(self):
        """Test position updates for buy operations."""
        await self.position_manager.initialize()
        
        mint_address = "test_mint_buy"
        
        # First buy
        execution_result_1 = {
            'actual_price': 0.001,
            'tokens_received': 1000,
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=1.0,
            action='buy',
            execution_result=execution_result_1,
            current_price=0.001
        )
        
        position = await self.position_manager.get_position(mint_address)
        self.assertEqual(position.token_amount, 1000)
        self.assertEqual(position.total_sol_invested, 1.0)
        self.assertEqual(position.average_buy_price, 0.001)
        
        # Second buy at different price
        execution_result_2 = {
            'actual_price': 0.002,
            'tokens_received': 500,
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=1.0,
            action='buy',
            execution_result=execution_result_2,
            current_price=0.002
        )
        
        position = await self.position_manager.get_position(mint_address)
        self.assertEqual(position.token_amount, 1500)
        self.assertEqual(position.total_sol_invested, 2.0)
        # Average price should be (1000*0.001 + 500*0.002) / 1500 = 0.00133...
        self.assertAlmostEqual(position.average_buy_price, 2.0/1500, places=6)
    
    async def test_sell_position_updates(self):
        """Test position updates for sell operations."""
        await self.position_manager.initialize()
        
        mint_address = "test_mint_sell"
        
        # Create initial position
        execution_result_buy = {
            'actual_price': 0.001,
            'tokens_received': 1000,
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=1.0,
            action='buy',
            execution_result=execution_result_buy
        )
        
        # Sell half the position
        execution_result_sell = {
            'sol_received': 0.75,  # Profit on the sale
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=500,  # Sell 500 tokens
            action='sell',
            execution_result=execution_result_sell
        )
        
        position = await self.position_manager.get_position(mint_address)
        self.assertEqual(position.token_amount, 500)
        self.assertTrue(position.is_active)
        
        # Sell remaining tokens
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=500,
            action='sell',
            execution_result=execution_result_sell
        )
        
        position = await self.position_manager.get_position(mint_address)
        self.assertEqual(position.token_amount, 0)
        self.assertFalse(position.is_active)
    
    async def test_unrealized_pnl_calculation(self):
        """Test unrealized P&L calculation with current prices."""
        await self.position_manager.initialize()
        
        mint_address = "test_mint_pnl"
        
        # Create position
        execution_result = {
            'actual_price': 0.001,
            'tokens_received': 1000,
            'status': 'confirmed'
        }
        
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=1.0,
            action='buy',
            execution_result=execution_result,
            current_price=0.002  # Price doubled
        )
        
        position = await self.position_manager.get_position(mint_address)
        self.assertEqual(position.current_value_sol, 2.0)  # 1000 * 0.002
        self.assertEqual(position.unrealized_pnl_sol, 1.0)  # 2.0 - 1.0
        self.assertEqual(position.unrealized_pnl_percent, 100.0)  # 100% gain
    
    async def test_portfolio_summary(self):
        """Test portfolio summary functionality."""
        # Create a fresh position manager for this test
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        config = {
            'database': {
                'type': 'sqlite',
                'path': temp_db.name
            }
        }
        
        pm = PositionManager(config)
        await pm.initialize()
        
        try:
            # Create multiple positions
            positions_data = [
                ("mint_1", 1.0, 0.001, 1000),
                ("mint_2", 2.0, 0.002, 1000),
                ("mint_3", 0.5, 0.0005, 1000)
            ]
            
            for mint_address, sol_amount, price, tokens in positions_data:
                execution_result = {
                    'actual_price': price,
                    'tokens_received': tokens,
                    'status': 'confirmed'
                }
                
                await pm.update_position(
                    mint_address=mint_address,
                    amount=sol_amount,
                    action='buy',
                    execution_result=execution_result,
                    current_price=price * 1.1  # 10% gain on all
                )
            
            summary = await pm.get_portfolio_summary()
            
            self.assertEqual(summary['active_positions'], 3)
            self.assertEqual(summary['total_invested_sol'], 3.5)  # 1.0 + 2.0 + 0.5
            self.assertAlmostEqual(summary['total_current_value_sol'], 3.85, places=2)  # 10% gain
            self.assertAlmostEqual(summary['portfolio_pnl_percent'], 10.0, places=1)
            
        finally:
            await pm.close()
            try:
                os.unlink(temp_db.name)
            except:
                pass


class TestTradeExecutionRecorder(unittest.TestCase):
    """Test cases for TradeExecutionRecorder."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = {
            'database': {
                'type': 'sqlite',
                'path': self.temp_db.name
            }
        }
        
        self.recorder = TradeExecutionRecorder(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close and remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    async def test_trade_recording_lifecycle(self):
        """Test complete trade recording lifecycle."""
        await self.recorder.initialize()
        
        mint_address = "test_mint_trade"
        signal_data = {
            'q50': 0.75,
            'regime': 'high_variance',
            'tradeable': True,
            'economically_significant': True
        }
        
        # Record trade attempt
        trade_id = await self.recorder.record_trade_attempt(
            mint_address=mint_address,
            action='buy',
            signal_data=signal_data,
            expected_price=0.001,
            sol_amount=1.0,
            pair_address="pair_123"
        )
        
        self.assertIsNotNone(trade_id)
        self.assertTrue(trade_id.startswith('buy_'))
        
        # Update with execution result
        execution_result = {
            'transaction_hash': 'tx_hash_123',
            'actual_price': 0.00105,  # Slight slippage
            'status': 'pending',
            'gas_used': 50000,
            'price_impact_percent': 2.5
        }
        
        await self.recorder.update_trade_execution(
            trade_id=trade_id,
            execution_result=execution_result,
            execution_latency_ms=250
        )
        
        # Confirm transaction
        confirmation_data = {
            'gas_used': 48000,  # Final gas amount
            'actual_price': 0.00105
        }
        
        await self.recorder.confirm_transaction(
            trade_id=trade_id,
            transaction_hash='tx_hash_123',
            confirmation_data=confirmation_data
        )
        
        # Retrieve and verify trade record
        trade_record = await self.recorder.get_trade_record(trade_id)
        
        self.assertIsNotNone(trade_record)
        self.assertEqual(trade_record.mint_address, mint_address)
        self.assertEqual(trade_record.action, 'buy')
        self.assertEqual(trade_record.execution_status, 'confirmed')
        self.assertEqual(trade_record.transaction_hash, 'tx_hash_123')
        self.assertEqual(trade_record.gas_used, 48000)
        self.assertEqual(trade_record.execution_latency_ms, 250)
        self.assertAlmostEqual(trade_record.slippage_percent, 5.0, places=1)  # (0.00105-0.001)/0.001 * 100
        self.assertEqual(trade_record.regime_at_execution, 'high_variance')
    
    async def test_failed_trade_recording(self):
        """Test recording of failed trades."""
        await self.recorder.initialize()
        
        mint_address = "test_mint_fail"
        signal_data = {'q50': 0.5, 'regime': 'low_variance'}
        
        # Record trade attempt
        trade_id = await self.recorder.record_trade_attempt(
            mint_address=mint_address,
            action='sell',
            signal_data=signal_data,
            expected_price=0.002,
            token_amount=500
        )
        
        # Mark as failed
        await self.recorder.mark_trade_failed(
            trade_id=trade_id,
            error_message="Insufficient liquidity",
            retry_count=3
        )
        
        # Verify failure recording
        trade_record = await self.recorder.get_trade_record(trade_id)
        
        self.assertIsNotNone(trade_record)
        self.assertEqual(trade_record.execution_status, 'failed')
        self.assertEqual(trade_record.error_message, "Insufficient liquidity")
        self.assertEqual(trade_record.retry_count, 3)
    
    async def test_execution_statistics(self):
        """Test execution statistics calculation."""
        await self.recorder.initialize()
        
        # Create multiple trade records
        trades_data = [
            ('buy', 'confirmed', 100, 2.5, 45000),
            ('sell', 'confirmed', 150, 1.8, 42000),
            ('buy', 'failed', None, None, None),
            ('sell', 'confirmed', 200, 3.2, 48000)
        ]
        
        for i, (action, status, latency, slippage, gas) in enumerate(trades_data):
            signal_data = {'q50': 0.6, 'regime': 'medium_variance'}
            
            trade_id = await self.recorder.record_trade_attempt(
                mint_address=f"mint_{i}",
                action=action,
                signal_data=signal_data,
                expected_price=0.001
            )
            
            if status == 'confirmed':
                execution_result = {
                    'status': 'confirmed',
                    'actual_price': 0.001 * (1 + slippage/100),
                    'gas_used': gas
                }
                await self.recorder.update_trade_execution(
                    trade_id=trade_id,
                    execution_result=execution_result,
                    execution_latency_ms=latency
                )
            else:
                await self.recorder.mark_trade_failed(
                    trade_id=trade_id,
                    error_message="Test failure"
                )
        
        # Get statistics
        stats = await self.recorder.get_execution_statistics()
        
        self.assertEqual(stats['total_trades'], 4)
        self.assertEqual(stats['successful_trades'], 3)
        self.assertEqual(stats['failed_trades'], 1)
        self.assertEqual(stats['success_rate'], 75.0)
        self.assertAlmostEqual(stats['average_execution_latency_ms'], 150.0, places=1)  # (100+150+200)/3
        self.assertAlmostEqual(stats['average_slippage_percent'], 2.5, places=1)  # (2.5+1.8+3.2)/3
        self.assertAlmostEqual(stats['average_gas_used'], 45000.0, places=1)  # (45000+42000+48000)/3
    
    async def test_recent_trades_retrieval(self):
        """Test retrieval of recent trades with filtering."""
        await self.recorder.initialize()
        
        mint_addresses = ["mint_a", "mint_b", "mint_a"]
        
        # Create trades
        for i, mint_address in enumerate(mint_addresses):
            signal_data = {'q50': 0.5, 'regime': 'test_regime'}
            
            await self.recorder.record_trade_attempt(
                mint_address=mint_address,
                action='buy',
                signal_data=signal_data,
                expected_price=0.001
            )
        
        # Get all recent trades
        all_trades = await self.recorder.get_recent_trades(limit=10)
        self.assertEqual(len(all_trades), 3)
        
        # Filter by mint address
        mint_a_trades = await self.recorder.get_recent_trades(
            limit=10,
            mint_address="mint_a"
        )
        self.assertEqual(len(mint_a_trades), 2)
        
        # Filter by status
        pending_trades = await self.recorder.get_recent_trades(
            limit=10,
            status_filter="pending"
        )
        self.assertEqual(len(pending_trades), 3)  # All should be pending


class TestIntegration(unittest.TestCase):
    """Integration tests for Position and Trade Management."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = {
            'database': {
                'type': 'sqlite',
                'path': self.temp_db.name
            }
        }
        
        self.position_manager = PositionManager(self.config)
        self.recorder = TradeExecutionRecorder(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close and remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    async def test_integrated_trading_workflow(self):
        """Test integrated workflow of recording trades and updating positions."""
        await self.position_manager.initialize()
        await self.recorder.initialize()
        
        mint_address = "integrated_test_mint"
        signal_data = {
            'q50': 0.8,
            'regime': 'high_variance',
            'tradeable': True,
            'economically_significant': True,
            'vol_risk': 0.15
        }
        
        # Step 1: Record trade attempt
        trade_id = await self.recorder.record_trade_attempt(
            mint_address=mint_address,
            action='buy',
            signal_data=signal_data,
            expected_price=0.001,
            sol_amount=2.0
        )
        
        # Step 2: Execute trade and update both systems
        execution_result = {
            'transaction_hash': 'integrated_tx_123',
            'actual_price': 0.00102,
            'tokens_received': 1960,  # Slightly less due to slippage
            'status': 'confirmed',
            'gas_used': 47000
        }
        
        # Update trade record
        await self.recorder.update_trade_execution(
            trade_id=trade_id,
            execution_result=execution_result,
            execution_latency_ms=180
        )
        
        # Update position
        await self.position_manager.update_position(
            mint_address=mint_address,
            amount=2.0,
            action='buy',
            execution_result=execution_result,
            current_price=0.00115  # Price increased after buy
        )
        
        # Step 3: Verify both systems are updated correctly
        trade_record = await self.recorder.get_trade_record(trade_id)
        position = await self.position_manager.get_position(mint_address)
        
        # Verify trade record
        self.assertEqual(trade_record.execution_status, 'confirmed')
        self.assertEqual(trade_record.transaction_hash, 'integrated_tx_123')
        self.assertAlmostEqual(trade_record.slippage_percent, 2.0, places=1)
        
        # Verify position
        self.assertEqual(position.token_amount, 1960)
        self.assertEqual(position.total_sol_invested, 2.0)
        self.assertAlmostEqual(position.current_value_sol, 2.254, places=2)  # 1960 * 0.00115
        self.assertAlmostEqual(position.unrealized_pnl_percent, 12.7, places=1)  # Profit from price increase


async def run_async_tests():
    """Run all async tests."""
    # Position Manager tests
    tests = [
        ("Position creation and retrieval", "test_position_creation_and_retrieval"),
        ("Buy position updates", "test_buy_position_updates"),
        ("Sell position updates", "test_sell_position_updates"),
        ("Unrealized P&L calculation", "test_unrealized_pnl_calculation"),
        ("Portfolio summary", "test_portfolio_summary")
    ]
    
    for test_name, test_method in tests:
        pm_test = TestPositionManager()
        pm_test.setUp()
        try:
            await getattr(pm_test, test_method)()
            print(f"✓ {test_name} test passed")
        finally:
            pm_test.tearDown()
    
    # Trade Execution Recorder tests
    ter_tests = [
        ("Trade recording lifecycle", "test_trade_recording_lifecycle"),
        ("Failed trade recording", "test_failed_trade_recording"),
        ("Execution statistics", "test_execution_statistics"),
        ("Recent trades retrieval", "test_recent_trades_retrieval")
    ]
    
    for test_name, test_method in ter_tests:
        ter_test = TestTradeExecutionRecorder()
        ter_test.setUp()
        try:
            await getattr(ter_test, test_method)()
            print(f"✓ {test_name} test passed")
        finally:
            ter_test.tearDown()
    
    # Integration tests
    int_test = TestIntegration()
    int_test.setUp()
    
    try:
        await int_test.test_integrated_trading_workflow()
        print("✓ Integrated trading workflow test passed")
        
    finally:
        int_test.tearDown()
    
    print("\n🎉 All Position and Trade Management tests passed!")


if __name__ == "__main__":
    print("Running Position and Trade Management Tests...")
    print("=" * 50)
    
    # Run async tests
    asyncio.run(run_async_tests())
    
    print("\n📊 Test Summary:")
    print("- PositionManager: Position tracking, P&L calculation, portfolio management")
    print("- TradeExecutionRecorder: Trade logging, performance tracking, statistics")
    print("- Integration: End-to-end workflow validation")
    print("\n✅ All requirements for Task 7 have been implemented and tested!")