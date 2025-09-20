"""
NautilusTrader POC Package

This package provides the core components for integrating Q50 quantile trading
signals with NautilusTrader and PumpSwap DEX execution.
"""

from .config import ConfigManager, NautilusPOCConfig
from .signal_loader import Q50SignalLoader
from .regime_detector import RegimeDetector
from .pumpswap_executor import PumpSwapExecutor, TradeExecutionRecord
from .liquidity_validator import LiquidityValidator, LiquidityValidationResult, LiquidityStatus
from .position_sizer import KellyPositionSizer, PositionSizeResult
from .risk_manager import RiskManager, TradeValidationResult, CircuitBreakerStatus, PositionRisk, RiskLevel

__version__ = "0.1.0"

__all__ = [
    "ConfigManager",
    "NautilusPOCConfig", 
    "Q50SignalLoader",
    "RegimeDetector",
    "PumpSwapExecutor",
    "TradeExecutionRecord",
    "LiquidityValidator",
    "LiquidityValidationResult",
    "LiquidityStatus",
    "KellyPositionSizer",
    "PositionSizeResult",
    "RiskManager",
    "TradeValidationResult",
    "CircuitBreakerStatus",
    "PositionRisk",
    "RiskLevel"
]