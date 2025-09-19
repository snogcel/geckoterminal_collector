#!/usr/bin/env python3
"""
PumpSwap Integration Example

This example demonstrates how to use the PumpSwapExecutor and LiquidityValidator
components for executing Q50-based trades on Solana DEX via PumpSwap SDK.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nautilus_poc import (
    ConfigManager,
    PumpSwapExecutor,
    LiquidityValidator,
    LiquidityStatus
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def example_trading_workflow():
    """Example of a complete trading workflow"""
    logger.info("Starting PumpSwap trading workflow example...")
    
    # 1. Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    
    # 2. Initialize components
    liquidity_validator = LiquidityValidator(config)
    pumpswap_executor = PumpSwapExecutor(config)
    
    # Set dependencies (in real implementation, you'd have proper position and risk managers)
    pumpswap_executor.set_dependencies(liquidity_validator, None, None)
    
    # 3. Example Q50 signal (this would come from your signal generation system)
    q50_signal = {
        'q50': 0.65,  # Strong positive signal
        'q10': 0.45,
        'q90': 0.85,
        'vol_risk': 0.18,  # Medium volatility
        'prob_up': 0.72,
        'economically_significant': True,
        'high_quality': True,
        'tradeable': True,
        'regime': 'medium_variance',
        'regime_multiplier': 1.1,
        'mint_address': 'So11111111111111111111111111111111111111112'  # Wrapped SOL
    }
    
    logger.info(f"Processing Q50 signal: q50={q50_signal['q50']}, tradeable={q50_signal['tradeable']}")
    
    # 4. Validate liquidity before trading
    logger.info("Validating pool liquidity...")
    
    # Mock pool data (in real implementation, this comes from PumpSwap SDK)
    pool_data = {
        'mint_address': q50_signal['mint_address'],
        'reserve_sol': 750.0,
        'reserve_in_usd': 75000,
        'price': 0.001,
        'volume_24h': 25000
    }
    
    validation_result = liquidity_validator.validate_liquidity_detailed(
        pool_data, q50_signal, 'buy'
    )
    
    logger.info(f"Liquidity validation: {validation_result.status.value}")
    logger.info(f"Pool liquidity: {validation_result.pool_liquidity_sol:.2f} SOL")
    logger.info(f"Estimated price impact: {validation_result.estimated_price_impact:.2f}%")
    logger.info(f"Recommended trade size: {validation_result.recommended_trade_size_sol:.4f} SOL")
    
    if not validation_result.is_valid:
        logger.warning(f"Liquidity validation failed: {validation_result.error_message}")
        return
    
    # 5. Execute buy order if signal is positive and tradeable
    if q50_signal['tradeable'] and q50_signal['q50'] > 0:
        logger.info("Executing buy order...")
        
        buy_result = await pumpswap_executor.execute_buy_signal(q50_signal)
        
        if buy_result['status'] == 'executed':
            logger.info("✅ Buy order executed successfully!")
            logger.info(f"   Transaction hash: {buy_result['transaction_hash']}")
            logger.info(f"   SOL amount: {buy_result['sol_amount']}")
            logger.info(f"   Token amount: {buy_result['token_amount']}")
            logger.info(f"   Execution latency: {buy_result['execution_latency_ms']}ms")
            
            # Monitor transaction confirmation
            if buy_result.get('transaction_hash'):
                logger.info("Monitoring transaction confirmation...")
                monitor_result = await pumpswap_executor.monitor_transaction(
                    buy_result['transaction_hash'], timeout_seconds=30
                )
                logger.info(f"Transaction status: {monitor_result['status']}")
        else:
            logger.warning(f"Buy order failed or skipped: {buy_result.get('reason', 'Unknown')}")
    
    # 6. Simulate a sell signal later
    logger.info("\n--- Simulating sell signal ---")
    
    sell_signal = {
        **q50_signal,
        'q50': -0.45,  # Negative signal indicates sell
        'prob_up': 0.35,
        'regime': 'high_variance',
        'regime_multiplier': 1.3
    }
    
    if sell_signal['tradeable'] and sell_signal['q50'] < 0:
        logger.info("Executing sell order...")
        
        sell_result = await pumpswap_executor.execute_sell_signal(sell_signal)
        
        if sell_result['status'] == 'executed':
            logger.info("✅ Sell order executed successfully!")
            logger.info(f"   Transaction hash: {sell_result['transaction_hash']}")
            logger.info(f"   Token amount sold: {sell_result['token_amount']}")
            logger.info(f"   SOL received: {sell_result['sol_amount']}")
            logger.info(f"   P&L: {sell_result.get('pnl_sol', 'N/A')} SOL")
        else:
            logger.warning(f"Sell order failed or skipped: {sell_result.get('reason', 'Unknown')}")
    
    # 7. Display performance metrics
    logger.info("\n--- Performance Summary ---")
    metrics = pumpswap_executor.get_performance_metrics()
    
    logger.info(f"Total trades: {metrics['total_trades']}")
    logger.info(f"Success rate: {metrics['success_rate_percent']:.1f}%")
    logger.info(f"Total volume: {metrics['total_volume_sol']:.4f} SOL")
    logger.info(f"Average execution latency: {metrics['average_execution_latency_ms']:.1f}ms")
    logger.info(f"Average slippage: {metrics['average_slippage_percent']:.2f}%")
    
    # 8. Show execution history
    logger.info("\n--- Execution History ---")
    history = pumpswap_executor.get_execution_history(limit=5)
    
    for i, record in enumerate(history, 1):
        logger.info(f"Trade {i}: {record['action']} - {record['execution_status']} - "
                   f"{record['mint_address'][:8]}... - {record['regime_at_execution']}")

async def example_liquidity_analysis():
    """Example of detailed liquidity analysis"""
    logger.info("\n=== Liquidity Analysis Example ===")
    
    config_manager = ConfigManager()
    config = config_manager.get_nautilus_config()
    validator = LiquidityValidator(config)
    
    # Test different pool scenarios
    scenarios = [
        {
            'name': 'High Liquidity Pool',
            'data': {
                'reserve_sol': 2000.0,
                'reserve_in_usd': 200000,
                'price': 0.001,
                'volume_24h': 50000
            }
        },
        {
            'name': 'Medium Liquidity Pool',
            'data': {
                'reserve_sol': 100.0,
                'reserve_in_usd': 10000,
                'price': 0.001,
                'volume_24h': 5000
            }
        },
        {
            'name': 'Low Liquidity Pool',
            'data': {
                'reserve_sol': 5.0,
                'reserve_in_usd': 500,
                'price': 0.001,
                'volume_24h': 200
            }
        }
    ]
    
    test_signal = {
        'q50': 0.6,
        'vol_risk': 0.2,
        'estimated_position_size': 1.0
    }
    
    for scenario in scenarios:
        logger.info(f"\n--- {scenario['name']} ---")
        
        result = validator.validate_liquidity_detailed(
            scenario['data'], test_signal, 'buy'
        )
        
        logger.info(f"Status: {result.status.value}")
        logger.info(f"Valid for trading: {result.is_valid}")
        logger.info(f"Pool liquidity: {result.pool_liquidity_sol:.2f} SOL")
        logger.info(f"Price impact: {result.estimated_price_impact:.2f}%")
        logger.info(f"Max trade size: {result.max_trade_size_sol:.4f} SOL")
        logger.info(f"Recommended size: {result.recommended_trade_size_sol:.4f} SOL")
        
        if not result.is_valid:
            logger.info(f"Reason: {result.error_message}")

async def main():
    """Main example function"""
    try:
        await example_trading_workflow()
        await example_liquidity_analysis()
        
        logger.info("\n🎉 Example completed successfully!")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())