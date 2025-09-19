#!/usr/bin/env python3
"""
QLib Trading Strategy Example

This script demonstrates how to use your historical OHLCV data to create
and backtest trading strategies using QLib methods.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any

from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.qlib.exporter import QLibExporter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleSignalStrategy:
    """
    Simple signal-based trading strategy using technical indicators.
    """
    
    def __init__(self, rsi_oversold=30, rsi_overbought=70, volume_threshold=1.5):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_threshold = volume_threshold
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate buy/sell signals based on technical indicators.
        
        Args:
            df: DataFrame with OHLCV data and technical indicators
            
        Returns:
            DataFrame with added signal columns
        """
        df = df.copy()
        
        # Initialize signal columns
        df['signal'] = 0  # 0 = hold, 1 = buy, -1 = sell
        df['signal_strength'] = 0.0  # Signal strength 0-1
        df['signal_reason'] = ''
        
        for symbol in df['symbol'].unique():
            mask = df['symbol'] == symbol
            symbol_data = df[mask].copy()
            
            # Calculate technical indicators if not present
            if 'rsi' not in symbol_data.columns:
                symbol_data = self._add_technical_indicators(symbol_data)
            
            # Generate signals
            signals = []
            signal_strengths = []
            signal_reasons = []
            
            for i in range(len(symbol_data)):
                signal = 0
                strength = 0.0
                reason = 'hold'
                
                if i < 20:  # Need enough data for indicators
                    signals.append(signal)
                    signal_strengths.append(strength)
                    signal_reasons.append(reason)
                    continue
                
                row = symbol_data.iloc[i]
                prev_row = symbol_data.iloc[i-1]
                
                # RSI-based signals
                rsi = row.get('rsi', 50)
                volume_ratio = row.get('volume_ratio', 1.0)
                price_change = row.get('price_change', 0)
                
                # Buy signals
                if (rsi < self.rsi_oversold and 
                    volume_ratio > self.volume_threshold and 
                    price_change > 0):
                    signal = 1
                    strength = min(1.0, (self.rsi_oversold - rsi) / 10 + volume_ratio / 3)
                    reason = f'oversold_rsi_{rsi:.1f}_vol_{volume_ratio:.1f}'
                
                # Sell signals
                elif (rsi > self.rsi_overbought and 
                      volume_ratio > self.volume_threshold and 
                      price_change < 0):
                    signal = -1
                    strength = min(1.0, (rsi - self.rsi_overbought) / 10 + volume_ratio / 3)
                    reason = f'overbought_rsi_{rsi:.1f}_vol_{volume_ratio:.1f}'
                
                # Momentum signals
                elif (row.get('sma_20', 0) > 0 and 
                      row['close'] > row.get('sma_20', 0) * 1.02 and
                      prev_row['close'] <= prev_row.get('sma_20', 0) and
                      volume_ratio > 1.2):
                    signal = 1
                    strength = 0.7
                    reason = 'momentum_breakout'
                
                signals.append(signal)
                signal_strengths.append(strength)
                signal_reasons.append(reason)
            
            # Update the main DataFrame
            df.loc[mask, 'signal'] = signals
            df.loc[mask, 'signal_strength'] = signal_strengths
            df.loc[mask, 'signal_reason'] = signal_reasons
        
        return df
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to DataFrame."""
        df = df.sort_values('datetime')
        
        # RSI
        df['rsi'] = self._calculate_rsi(df['close'])
        
        # Moving averages
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        # Volume indicators
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        
        # Price change
        df['price_change'] = df['close'].pct_change()
        
        return df
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

class SimpleBacktester:
    """
    Simple backtesting engine for strategy evaluation.
    """
    
    def __init__(self, initial_capital=10000, transaction_cost=0.001):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
    
    def backtest_strategy(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Backtest a strategy with signals.
        
        Args:
            df: DataFrame with OHLCV data and signals
            
        Returns:
            Dictionary with backtest results
        """
        results = {
            'trades': [],
            'portfolio_value': [],
            'returns': [],
            'metrics': {}
        }
        
        # Initialize portfolio
        cash = self.initial_capital
        positions = {}  # symbol -> quantity
        portfolio_values = []
        trades = []
        
        # Sort by datetime
        df = df.sort_values(['datetime', 'symbol'])
        
        for _, row in df.iterrows():
            symbol = row['symbol']
            price = row['close']
            signal = row['signal']
            signal_strength = row['signal_strength']
            datetime_val = row['datetime']
            
            # Initialize position if not exists
            if symbol not in positions:
                positions[symbol] = 0
            
            # Execute trades based on signals
            if signal == 1 and signal_strength > 0.5:  # Strong buy signal
                # Buy with portion of available cash
                position_size = min(cash * 0.1 * signal_strength, cash * 0.2)  # Max 20% per position
                if position_size > 100:  # Minimum trade size
                    quantity = position_size / price
                    cost = quantity * price * (1 + self.transaction_cost)
                    
                    if cost <= cash:
                        cash -= cost
                        positions[symbol] += quantity
                        
                        trades.append({
                            'datetime': datetime_val,
                            'symbol': symbol,
                            'action': 'buy',
                            'quantity': quantity,
                            'price': price,
                            'cost': cost,
                            'signal_strength': signal_strength,
                            'reason': row.get('signal_reason', '')
                        })
            
            elif signal == -1 and positions[symbol] > 0:  # Sell signal
                # Sell portion or all of position
                sell_quantity = positions[symbol] * min(signal_strength, 1.0)
                if sell_quantity > 0:
                    proceeds = sell_quantity * price * (1 - self.transaction_cost)
                    cash += proceeds
                    positions[symbol] -= sell_quantity
                    
                    trades.append({
                        'datetime': datetime_val,
                        'symbol': symbol,
                        'action': 'sell',
                        'quantity': sell_quantity,
                        'price': price,
                        'proceeds': proceeds,
                        'signal_strength': signal_strength,
                        'reason': row.get('signal_reason', '')
                    })
            
            # Calculate portfolio value
            portfolio_value = cash
            for pos_symbol, quantity in positions.items():
                if quantity > 0:
                    # Use current price for this symbol
                    current_price = df[(df['symbol'] == pos_symbol) & 
                                     (df['datetime'] <= datetime_val)]['close'].iloc[-1] if len(df[(df['symbol'] == pos_symbol) & (df['datetime'] <= datetime_val)]) > 0 else price
                    portfolio_value += quantity * current_price
            
            portfolio_values.append({
                'datetime': datetime_val,
                'portfolio_value': portfolio_value,
                'cash': cash,
                'positions_value': portfolio_value - cash
            })
        
        # Calculate performance metrics
        if portfolio_values:
            final_value = portfolio_values[-1]['portfolio_value']
            total_return = (final_value - self.initial_capital) / self.initial_capital * 100
            
            # Calculate daily returns
            portfolio_df = pd.DataFrame(portfolio_values)
            portfolio_df['daily_return'] = portfolio_df['portfolio_value'].pct_change()
            
            # Risk metrics
            volatility = portfolio_df['daily_return'].std() * np.sqrt(365) * 100  # Annualized
            max_drawdown = self._calculate_max_drawdown(portfolio_df['portfolio_value'])
            
            # Trade metrics
            winning_trades = [t for t in trades if t['action'] == 'sell' and 
                            any(buy['symbol'] == t['symbol'] and buy['datetime'] < t['datetime'] 
                                and buy['price'] < t['price'] for buy in trades if buy['action'] == 'buy')]
            
            results['metrics'] = {
                'initial_capital': self.initial_capital,
                'final_value': final_value,
                'total_return_pct': total_return,
                'volatility_pct': volatility,
                'max_drawdown_pct': max_drawdown,
                'total_trades': len(trades),
                'buy_trades': len([t for t in trades if t['action'] == 'buy']),
                'sell_trades': len([t for t in trades if t['action'] == 'sell']),
                'winning_trades': len(winning_trades),
                'win_rate': len(winning_trades) / len([t for t in trades if t['action'] == 'sell']) * 100 if trades else 0
            }
        
        results['trades'] = trades
        results['portfolio_value'] = portfolio_values
        
        return results
    
    def _calculate_max_drawdown(self, portfolio_values: pd.Series) -> float:
        """Calculate maximum drawdown percentage."""
        peak = portfolio_values.expanding().max()
        drawdown = (portfolio_values - peak) / peak
        return float(drawdown.min() * 100)

async def run_trading_strategy_example():
    """
    Main example: Run a complete trading strategy backtest.
    """
    print("🎯 Trading Strategy Backtest Example")
    print("=" * 60)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Get historical data for backtesting
        print("📊 Loading historical data...")
        df = await qlib_exporter.export_ohlcv_data(
            symbols=None,  # All watchlist symbols
            start_date="2025-09-01",
            end_date="2025-09-19",
            timeframe="1h",
            include_volume=True
        )
        
        if df.empty:
            print("❌ No historical data available")
            return
        
        print(f"✅ Loaded {len(df)} records for {len(df['symbol'].unique())} symbols")
        
        # Initialize strategy
        strategy = SimpleSignalStrategy(
            rsi_oversold=30,
            rsi_overbought=70,
            volume_threshold=1.5
        )
        
        # Calculate signals
        print("🧮 Calculating trading signals...")
        df_with_signals = strategy.calculate_signals(df)
        
        # Show signal summary
        buy_signals = len(df_with_signals[df_with_signals['signal'] == 1])
        sell_signals = len(df_with_signals[df_with_signals['signal'] == -1])
        
        print(f"📈 Generated {buy_signals} buy signals and {sell_signals} sell signals")
        
        # Show some example signals
        strong_signals = df_with_signals[df_with_signals['signal_strength'] > 0.7]
        if not strong_signals.empty:
            print("\n🔥 Strong Signals (strength > 0.7):")
            for _, signal in strong_signals.head(5).iterrows():
                action = "BUY" if signal['signal'] == 1 else "SELL"
                print(f"  {signal['datetime']} | {signal['symbol']} | {action} | "
                      f"Strength: {signal['signal_strength']:.2f} | {signal['signal_reason']}")
        
        # Run backtest
        print("\n💰 Running backtest...")
        backtester = SimpleBacktester(initial_capital=10000, transaction_cost=0.001)
        results = backtester.backtest_strategy(df_with_signals)
        
        # Display results
        metrics = results['metrics']
        print(f"\n📊 Backtest Results:")
        print(f"  Initial Capital: ${metrics['initial_capital']:,.2f}")
        print(f"  Final Value: ${metrics['final_value']:,.2f}")
        print(f"  Total Return: {metrics['total_return_pct']:+.2f}%")
        print(f"  Volatility: {metrics['volatility_pct']:.2f}%")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        
        # Show recent trades
        trades = results['trades']
        if trades:
            print(f"\n📋 Recent Trades (last 5):")
            for trade in trades[-5:]:
                action = trade['action'].upper()
                symbol = trade['symbol']
                price = trade['price']
                quantity = trade['quantity']
                datetime_val = trade['datetime']
                reason = trade.get('reason', '')
                
                print(f"  {datetime_val} | {action} {quantity:.4f} {symbol} @ ${price:.6f} | {reason}")
        
        # Performance visualization data
        portfolio_values = results['portfolio_value']
        if portfolio_values:
            print(f"\n📈 Portfolio Performance:")
            print(f"  Start: ${portfolio_values[0]['portfolio_value']:,.2f}")
            print(f"  End: ${portfolio_values[-1]['portfolio_value']:,.2f}")
            print(f"  Peak: ${max(pv['portfolio_value'] for pv in portfolio_values):,.2f}")
            print(f"  Trough: ${min(pv['portfolio_value'] for pv in portfolio_values):,.2f}")
        
        # Strategy recommendations
        print(f"\n💡 Strategy Insights:")
        if metrics['total_return_pct'] > 0:
            print(f"  ✅ Strategy was profitable ({metrics['total_return_pct']:+.2f}%)")
        else:
            print(f"  ❌ Strategy lost money ({metrics['total_return_pct']:+.2f}%)")
        
        if metrics['win_rate'] > 50:
            print(f"  ✅ Good win rate ({metrics['win_rate']:.1f}%)")
        else:
            print(f"  ⚠️  Low win rate ({metrics['win_rate']:.1f}%) - consider adjusting signals")
        
        if metrics['max_drawdown_pct'] < -20:
            print(f"  ⚠️  High drawdown ({metrics['max_drawdown_pct']:.1f}%) - consider risk management")
        
        return results
        
    finally:
        await db_manager.close()

async def analyze_signal_performance():
    """
    Analyze which signals perform best.
    """
    print("\n🔍 Signal Performance Analysis")
    print("=" * 50)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Get data
        df = await qlib_exporter.export_ohlcv_data(
            symbols=None,
            start_date="2025-09-01",
            end_date="2025-09-19",
            timeframe="1h"
        )
        
        if df.empty:
            return
        
        # Calculate signals
        strategy = SimpleSignalStrategy()
        df_with_signals = strategy.calculate_signals(df)
        
        # Analyze signal performance
        signal_analysis = []
        
        for symbol in df_with_signals['symbol'].unique():
            symbol_data = df_with_signals[df_with_signals['symbol'] == symbol].sort_values('datetime')
            
            buy_signals = symbol_data[symbol_data['signal'] == 1]
            
            for _, buy_signal in buy_signals.iterrows():
                # Look for price change in next few hours
                future_data = symbol_data[symbol_data['datetime'] > buy_signal['datetime']].head(24)  # Next 24 hours
                
                if not future_data.empty:
                    buy_price = buy_signal['close']
                    max_future_price = future_data['high'].max()
                    min_future_price = future_data['low'].min()
                    
                    max_gain = (max_future_price - buy_price) / buy_price * 100
                    max_loss = (min_future_price - buy_price) / buy_price * 100
                    
                    signal_analysis.append({
                        'symbol': symbol,
                        'datetime': buy_signal['datetime'],
                        'signal_strength': buy_signal['signal_strength'],
                        'signal_reason': buy_signal['signal_reason'],
                        'max_gain_24h': max_gain,
                        'max_loss_24h': max_loss,
                        'buy_price': buy_price
                    })
        
        if signal_analysis:
            signal_df = pd.DataFrame(signal_analysis)
            
            print(f"📊 Analyzed {len(signal_df)} buy signals")
            
            # Performance by signal reason
            print(f"\n📈 Performance by Signal Type:")
            for reason in signal_df['signal_reason'].unique():
                reason_signals = signal_df[signal_df['signal_reason'] == reason]
                avg_gain = reason_signals['max_gain_24h'].mean()
                avg_loss = reason_signals['max_loss_24h'].mean()
                success_rate = len(reason_signals[reason_signals['max_gain_24h'] > 2]) / len(reason_signals) * 100
                
                print(f"  {reason}:")
                print(f"    Count: {len(reason_signals)}")
                print(f"    Avg Max Gain: {avg_gain:+.2f}%")
                print(f"    Avg Max Loss: {avg_loss:+.2f}%")
                print(f"    Success Rate (>2% gain): {success_rate:.1f}%")
            
            # Best performing signals
            best_signals = signal_df.nlargest(5, 'max_gain_24h')
            print(f"\n🏆 Best Performing Signals:")
            for _, signal in best_signals.iterrows():
                print(f"  {signal['datetime']} | {signal['symbol']} | "
                      f"Gain: {signal['max_gain_24h']:+.2f}% | {signal['signal_reason']}")
    
    finally:
        await db_manager.close()

if __name__ == "__main__":
    async def main():
        try:
            # Run trading strategy example
            await run_trading_strategy_example()
            
            # Analyze signal performance
            await analyze_signal_performance()
            
            print("\n🎉 Trading strategy analysis completed!")
            print("\nNext steps:")
            print("1. Optimize strategy parameters")
            print("2. Add more sophisticated signals")
            print("3. Implement risk management")
            print("4. Test on different time periods")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Error in main: {e}", exc_info=True)
    
    asyncio.run(main())