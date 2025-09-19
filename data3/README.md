# Q50 Data Directory

This directory should contain the Q50 signal data files:

## Required Files:
- `macro_features.pkl`: Q50 quantile predictions with required columns:
  - q10, q50, q90: Quantile predictions
  - vol_raw, vol_risk: Volatility measures
  - prob_up: Probability of upward movement
  - economically_significant: Economic significance flag
  - high_quality: Signal quality flag
  - tradeable: Tradeable status flag

## Data Format:
The macro_features.pkl file should be a pandas DataFrame with timestamp index
and the required columns listed above.

## Integration:
Place your existing Q50 signal data file here to integrate with the
NautilusTrader POC system.
