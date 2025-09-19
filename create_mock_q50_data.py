#!/usr/bin/env python3
"""
Create mock Q50 data for testing NautilusTrader POC
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mock_q50_data():
    """Create mock Q50 signal data for testing"""
    
    # Create date range for the last 30 days with 5-minute intervals
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Generate timestamps every 5 minutes
    timestamps = pd.date_range(start=start_date, end=end_date, freq='5T')
    
    logger.info(f"Creating mock Q50 data with {len(timestamps)} timestamps")
    
    # Set random seed for reproducible results
    np.random.seed(42)
    
    # Generate mock Q50 data
    data = []
    for ts in timestamps:
        # Generate correlated quantile values (q10 < q50 < q90)
        base_signal = np.random.normal(0, 1)
        
        q10 = base_signal - abs(np.random.normal(0.5, 0.2))
        q50 = base_signal + np.random.normal(0, 0.1)
        q90 = base_signal + abs(np.random.normal(0.5, 0.2))
        
        # Ensure proper ordering
        q10 = min(q10, q50 - 0.1)
        q90 = max(q90, q50 + 0.1)
        
        # Generate volatility measures
        vol_raw = abs(np.random.normal(0.2, 0.1))
        vol_risk = abs(np.random.normal(0.15, 0.05))
        
        # Generate probability (should be between 0 and 1)
        prob_up = 1 / (1 + np.exp(-q50))  # Sigmoid transformation
        
        # Generate flags based on signal strength
        signal_strength = abs(q50)
        economically_significant = signal_strength > 0.3
        high_quality = signal_strength > 0.2 and vol_risk < 0.25
        tradeable = economically_significant and high_quality and vol_risk < 0.3
        
        data.append({
            'timestamp': ts,
            'q10': q10,
            'q50': q50,
            'q90': q90,
            'vol_raw': vol_raw,
            'vol_risk': vol_risk,
            'prob_up': prob_up,
            'economically_significant': economically_significant,
            'high_quality': high_quality,
            'tradeable': tradeable
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    
    # Add some statistics
    logger.info(f"Mock data statistics:")
    logger.info(f"  Tradeable signals: {df['tradeable'].sum()} ({df['tradeable'].mean():.1%})")
    logger.info(f"  Economically significant: {df['economically_significant'].sum()} ({df['economically_significant'].mean():.1%})")
    logger.info(f"  High quality: {df['high_quality'].sum()} ({df['high_quality'].mean():.1%})")
    logger.info(f"  Q50 range: [{df['q50'].min():.3f}, {df['q50'].max():.3f}]")
    logger.info(f"  Vol risk range: [{df['vol_risk'].min():.3f}, {df['vol_risk'].max():.3f}]")
    
    return df

def main():
    """Create and save mock Q50 data"""
    # Create data directory if it doesn't exist
    data_dir = Path("data3")
    data_dir.mkdir(exist_ok=True)
    
    # Create mock data
    df = create_mock_q50_data()
    
    # Save to pickle file
    output_path = data_dir / "macro_features.pkl"
    df.to_pickle(output_path)
    
    logger.info(f"✓ Mock Q50 data saved to {output_path}")
    logger.info(f"Data shape: {df.shape}")
    logger.info("Ready for NautilusTrader POC testing!")

if __name__ == "__main__":
    main()