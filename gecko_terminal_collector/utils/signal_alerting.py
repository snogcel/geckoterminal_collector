"""
Signal alerting utilities for quick visual identification and action.

Provides multiple methods to highlight strong trading signals:
1. Custom log level (TRADE_SIGNAL)
2. Visual formatting with colors/emojis
3. Sound alerts (optional)
4. File-based alerts for external monitoring
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


# Define custom log level for trading signals (between WARNING and ERROR)
TRADE_SIGNAL = 35
logging.addLevelName(TRADE_SIGNAL, "TRADE_SIGNAL")


class SignalFormatter(logging.Formatter):
    """
    Custom formatter that adds visual emphasis to trading signals.
    
    Features:
    - Color coding (if terminal supports it)
    - Emoji indicators
    - Clear visual separation
    """
    
    # ANSI color codes
    COLORS = {
        'CRITICAL': '\033[91m',  # Red
        'ERROR': '\033[91m',     # Red
        'TRADE_SIGNAL': '\033[92m\033[1m',  # Bright Green + Bold
        'WARNING': '\033[93m',   # Yellow
        'INFO': '\033[94m',      # Blue
        'DEBUG': '\033[90m',     # Gray
        'RESET': '\033[0m'
    }
    
    # Emoji indicators
    EMOJIS = {
        'CRITICAL': '🔴',
        'ERROR': '❌',
        'TRADE_SIGNAL': '🚀💰',  # Rocket + Money bag
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'DEBUG': '🔍'
    }
    
    def __init__(self, use_colors=True, use_emojis=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_colors = use_colors and self._supports_color()
        self.use_emojis = use_emojis
    
    def _supports_color(self):
        """Check if terminal supports color."""
        # Windows 10+ supports ANSI colors
        if os.name == 'nt':
            return True
        # Unix-like systems
        return hasattr(os.sys.stdout, 'isatty') and os.sys.stdout.isatty()
    
    def format(self, record):
        """Format log record with visual enhancements."""
        # Add emoji
        if self.use_emojis and record.levelname in self.EMOJIS:
            emoji = self.EMOJIS[record.levelname]
            record.msg = f"{emoji} {record.msg}"
        
        # Format the message
        formatted = super().format(record)
        
        # Add color
        if self.use_colors and record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            
            # For TRADE_SIGNAL, add extra visual separation
            if record.levelname == 'TRADE_SIGNAL':
                separator = "=" * 80
                formatted = f"\n{color}{separator}\n{formatted}\n{separator}{reset}\n"
            else:
                formatted = f"{color}{formatted}{reset}"
        
        return formatted


class SignalAlerter:
    """
    Handles various types of signal alerts for quick action.
    
    Features:
    - File-based alerts (for external monitoring)
    - Sound alerts (optional)
    - Desktop notifications (optional)
    - Webhook notifications (optional)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize signal alerter.
        
        Args:
            config: Configuration dictionary with alert settings
        """
        self.config = config or {}
        self.alerts_dir = Path(self.config.get('alerts_dir', 'alerts'))
        self.alerts_dir.mkdir(exist_ok=True)
        
        # Alert settings
        self.enable_file_alerts = self.config.get('enable_file_alerts', True)
        self.enable_sound_alerts = self.config.get('enable_sound_alerts', False)
        self.enable_desktop_notifications = self.config.get('enable_desktop_notifications', False)
        self.enable_webhook = self.config.get('enable_webhook', False)
        
        self.webhook_url = self.config.get('webhook_url')
        self.min_signal_score = self.config.get('min_signal_score', 60.0)
    
    def alert(self, pool_id: str, signal_data: Dict[str, Any], message: str):
        """
        Send alert through configured channels.
        
        Args:
            pool_id: Pool identifier
            signal_data: Signal analysis data
            message: Alert message
        """
        signal_score = signal_data.get('signal_score', 0)
        
        # Only alert if score meets threshold
        if signal_score < self.min_signal_score:
            return
        
        # File-based alert (always enabled for external monitoring)
        if self.enable_file_alerts:
            self._write_file_alert(pool_id, signal_data, message)
        
        # Sound alert
        if self.enable_sound_alerts:
            self._play_sound_alert(signal_score)
        
        # Desktop notification
        if self.enable_desktop_notifications:
            self._send_desktop_notification(pool_id, message, signal_score)
        
        # Webhook notification
        if self.enable_webhook and self.webhook_url:
            self._send_webhook(pool_id, signal_data, message)
    
    def _write_file_alert(self, pool_id: str, signal_data: Dict[str, Any], message: str):
        """Write alert to file for external monitoring."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        signal_score = signal_data.get('signal_score', 0)
        
        # Create alert file with timestamp
        alert_file = self.alerts_dir / f"signal_{timestamp}_{pool_id.replace('/', '_')}.txt"
        
        with open(alert_file, 'w', encoding='utf-8') as f:
            f.write(f"TRADING SIGNAL ALERT\n")
            f.write(f"{'=' * 80}\n\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Pool ID: {pool_id}\n")
            f.write(f"Signal Score: {signal_score:.2f}\n\n")
            f.write(f"Message:\n{message}\n\n")
            f.write(f"Signal Data:\n")
            for key, value in signal_data.items():
                f.write(f"  {key}: {value}\n")
        
        # Also maintain a "latest" file for easy monitoring
        latest_file = self.alerts_dir / "LATEST_SIGNAL.txt"
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(f"🚀 LATEST TRADING SIGNAL 🚀\n")
            f.write(f"{'=' * 80}\n\n")
            f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Pool: {pool_id}\n")
            f.write(f"Score: {signal_score:.2f}/100\n\n")
            f.write(message)
    
    def _play_sound_alert(self, signal_score: float):
        """Play sound alert (platform-specific)."""
        try:
            # Different sounds for different signal strengths
            if signal_score >= 80:
                frequency = 1000  # High frequency for strong signals
                duration = 500
            else:
                frequency = 800
                duration = 300
            
            if os.name == 'nt':  # Windows
                import winsound
                winsound.Beep(frequency, duration)
            else:  # Unix-like
                os.system(f'play -nq -t alsa synth {duration/1000} sine {frequency}')
        except Exception:
            pass  # Silently fail if sound not available
    
    def _send_desktop_notification(self, pool_id: str, message: str, signal_score: float):
        """Send desktop notification."""
        try:
            # Try using plyer (cross-platform)
            from plyer import notification
            notification.notify(
                title=f"🚀 Trading Signal: {signal_score:.1f}/100",
                message=f"{pool_id}\n{message[:200]}",
                app_name="Gecko Terminal Collector",
                timeout=10
            )
        except ImportError:
            # Fallback to platform-specific methods
            if os.name == 'nt':  # Windows
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(
                        f"Trading Signal: {signal_score:.1f}/100",
                        f"{pool_id}\n{message[:200]}",
                        duration=10,
                        threaded=True
                    )
                except ImportError:
                    pass
    
    def _send_webhook(self, pool_id: str, signal_data: Dict[str, Any], message: str):
        """Send webhook notification (e.g., to Discord, Slack, Telegram)."""
        try:
            import requests
            
            payload = {
                'pool_id': pool_id,
                'signal_score': signal_data.get('signal_score'),
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'data': signal_data
            }
            
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception:
            pass  # Silently fail if webhook not available


def setup_signal_logging(logger, config: Optional[Dict] = None):
    """
    Setup enhanced logging for trading signals.
    
    Args:
        logger: Logger instance to configure (can be standard Logger or ContextualLogger)
        config: Configuration dictionary
        
    Returns:
        Configured SignalAlerter instance
    """
    config = config or {}
    
    # Add custom log level method to logging.Logger class
    def trade_signal(self, message, *args, **kwargs):
        if self.isEnabledFor(TRADE_SIGNAL):
            self._log(TRADE_SIGNAL, message, args, **kwargs)
    
    logging.Logger.trade_signal = trade_signal
    
    # Get the underlying logger if this is a ContextualLogger wrapper
    underlying_logger = logger
    if hasattr(logger, 'logger'):
        # This is a ContextualLogger, get the wrapped logger
        underlying_logger = logger.logger
        
        # Add trade_signal method to ContextualLogger as well
        def contextual_trade_signal(self, message, *args, **kwargs):
            """Trade signal method for ContextualLogger."""
            self._log_with_context(TRADE_SIGNAL, message, *args, **kwargs)
        
        # Bind the method to the logger instance
        import types
        logger.trade_signal = types.MethodType(contextual_trade_signal, logger)
    
    # Create signal-specific handler with custom formatter
    signal_handler = logging.StreamHandler()
    signal_handler.setLevel(TRADE_SIGNAL)
    signal_formatter = SignalFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        use_colors=config.get('use_colors', True),
        use_emojis=config.get('use_emojis', True)
    )
    signal_handler.setFormatter(signal_formatter)
    signal_handler.addFilter(lambda record: record.levelno == TRADE_SIGNAL)
    
    # Add handler to the underlying logger
    underlying_logger.addHandler(signal_handler)
    
    # Create and return alerter
    return SignalAlerter(config)


def get_signal_only_logs(log_file: str, output_file: Optional[str] = None) -> list:
    """
    Extract only trading signal logs from a log file.
    
    Args:
        log_file: Path to log file
        output_file: Optional output file for filtered logs
        
    Returns:
        List of signal log lines
    """
    signal_lines = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if 'TRADE_SIGNAL' in line or 'Strong signal detected' in line:
                signal_lines.append(line)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.writelines(signal_lines)
    
    return signal_lines
