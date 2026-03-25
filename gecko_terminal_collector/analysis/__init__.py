"""
Analysis module for signal detection and pattern recognition.
"""

from .pool_scorer import PoolScorer
from .signal_analyzer import NewPoolsSignalAnalyzer, SignalResult

__all__ = ['NewPoolsSignalAnalyzer', 'SignalResult', 'PoolScorer']