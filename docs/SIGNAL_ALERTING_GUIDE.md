## Signal Alerting System - Quick Action Guide

### Problem
You need to spot strong trading signals quickly in noisy logs and act on them immediately.

### Solutions (Choose Your Level)

## 🟢 Level 1: Visual Enhancement (Easiest - No Setup)

**What it does:** Makes signals stand out visually in your terminal

**Features:**
- 🚀💰 Emoji indicators for signals
- Bright green + bold text
- Visual separators (======)
- Custom TRADE_SIGNAL log level

**Setup:**
```yaml
# Add to config.yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
    min_signal_score: 60.0
```

**Result:**
```
2025-11-26 10:30:15 - INFO - Processing pool...
2025-11-26 10:30:16 - INFO - Analyzing signals...

================================================================================
🚀💰 TRADE_SIGNAL - STRONG SIGNAL DETECTED: Pool solana_abc123
Signal Score: 85.2/100 | Volume: spike | Liquidity: growing
================================================================================

2025-11-26 10:30:17 - INFO - Continuing collection...
```

---

## 🟡 Level 2: File-Based Alerts (Recommended)

**What it does:** Creates alert files you can monitor externally

**Features:**
- Creates timestamped alert files
- Maintains `LATEST_SIGNAL.txt` for easy monitoring
- Can be monitored by external scripts/tools
- No dependencies required

**Setup:**
```yaml
new_pools:
  signal_detection:
    enabled: true
    enable_file_alerts: true
    alerts_dir: "alerts"  # Creates this folder
    min_signal_score: 60.0
```

**Result:**
```
alerts/
├── LATEST_SIGNAL.txt                    # Always shows latest signal
├── signal_20251126_103015_solana_abc.txt
├── signal_20251126_104522_solana_xyz.txt
└── signal_20251126_105833_solana_def.txt
```

**Monitor with:**
```bash
# Windows - watch for new signals
powershell -Command "Get-Content alerts\LATEST_SIGNAL.txt -Wait"

# Or use a simple script
python monitor_signals.py
```

---

## 🟠 Level 3: Sound Alerts (Optional)

**What it does:** Plays a beep when strong signals are detected

**Features:**
- Different frequencies for different signal strengths
- High frequency (1000Hz) for signals ≥80
- Medium frequency (800Hz) for signals 60-79
- Works on Windows (built-in) and Linux (requires `sox`)

**Setup:**
```yaml
new_pools:
  signal_detection:
    enabled: true
    enable_sound_alerts: true
    min_signal_score: 60.0
```

**Requirements:**
- Windows: Built-in (winsound)
- Linux: `sudo apt-get install sox`

---

## 🔴 Level 4: Desktop Notifications (Optional)

**What it does:** Shows popup notifications on your desktop

**Features:**
- Native OS notifications
- Shows pool ID and signal score
- Clickable notifications
- 10-second display duration

**Setup:**
```yaml
new_pools:
  signal_detection:
    enabled: true
    enable_desktop_notifications: true
    min_signal_score: 60.0
```

**Requirements:**
```bash
pip install plyer
# OR for Windows 10+
pip install win10toast
```

---

## 🟣 Level 5: Webhook Integration (Advanced)

**What it does:** Sends signals to Discord/Slack/Telegram

**Features:**
- Real-time notifications to your phone/desktop
- Full signal data in JSON format
- Can trigger automated trading bots
- Supports any webhook-compatible service

**Setup:**

### Discord Example:
1. Create a Discord webhook in your server settings
2. Add to config:
```yaml
new_pools:
  signal_detection:
    enabled: true
    enable_webhook: true
    webhook_url: "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
    min_signal_score: 60.0
```

### Slack Example:
```yaml
webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Telegram Example:
```yaml
webhook_url: "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage?chat_id=YOUR_CHAT_ID"
```

---

## 📊 Recommended Configurations

### For Active Trading (Quick Action Required)
```yaml
new_pools:
  signal_detection:
    enabled: true
    min_signal_score: 70.0  # Higher threshold for quality
    use_colors: true
    use_emojis: true
    enable_file_alerts: true
    enable_sound_alerts: true
    enable_desktop_notifications: true
    enable_webhook: true
    webhook_url: "YOUR_DISCORD_WEBHOOK"
    alerts_dir: "trading_alerts"
```

### For Monitoring/Research
```yaml
new_pools:
  signal_detection:
    enabled: true
    min_signal_score: 60.0
    use_colors: true
    use_emojis: true
    enable_file_alerts: true
    alerts_dir: "alerts"
```

### For Automated Trading Bots
```yaml
new_pools:
  signal_detection:
    enabled: true
    min_signal_score: 75.0  # High quality only
    enable_file_alerts: true
    enable_webhook: true
    webhook_url: "YOUR_BOT_WEBHOOK"
    alerts_dir: "bot_signals"
```

---

## 🛠️ Helper Tools

### 1. Monitor Latest Signal (Real-time)
```bash
python monitor_signals.py
```

### 2. Extract Signal Logs from Log File
```python
from gecko_terminal_collector.utils.signal_alerting import get_signal_only_logs

# Extract all signal logs
signals = get_signal_only_logs('logs/collector.log', 'signals_only.log')
print(f"Found {len(signals)} signals")
```

### 3. Filter Logs by Level
```bash
# Show only TRADE_SIGNAL level logs
python filter_logs.py --level TRADE_SIGNAL

# Show signals with score >= 80
python filter_logs.py --min-score 80
```

---

## 🎯 Quick Action Workflow

### Workflow 1: Manual Trading
1. Run collector with visual + file alerts enabled
2. Watch terminal for 🚀💰 signals
3. Check `alerts/LATEST_SIGNAL.txt` for details
4. Execute trade manually

### Workflow 2: Semi-Automated
1. Run collector with webhook enabled
2. Receive Discord/Telegram notification on phone
3. Review signal details
4. Execute trade via mobile app

### Workflow 3: Fully Automated
1. Run collector with webhook to trading bot
2. Bot receives signal via webhook
3. Bot validates signal against additional criteria
4. Bot executes trade automatically

---

## 📝 Log Level Hierarchy

```
CRITICAL (50)  - System failures
TRADE_SIGNAL (35) - 🚀💰 TRADING SIGNALS (NEW!)
ERROR (40)     - Errors
WARNING (30)   - Warnings
INFO (20)      - General info
DEBUG (10)     - Debug info
```

**Filter to show only signals:**
```python
import logging
logging.basicConfig(level=35)  # Only TRADE_SIGNAL and above
```

---

## 🔧 Troubleshooting

### Signals not showing up?
1. Check `min_signal_score` - might be too high
2. Verify `signal_detection.enabled: true`
3. Check target dexes filter in config

### Colors not working?
- Windows: Should work by default on Windows 10+
- Set `use_colors: false` if terminal doesn't support ANSI

### Sound not working?
- Windows: Should work by default (winsound)
- Linux: Install sox: `sudo apt-get install sox`
- Set `enable_sound_alerts: false` if not needed

### Desktop notifications not working?
```bash
pip install plyer
# OR
pip install win10toast
```

### Webhook not working?
1. Test webhook URL manually with curl/Postman
2. Check webhook URL format
3. Verify network connectivity
4. Check webhook service logs

---

## 📚 Additional Resources

- `config_signal_alerts.yaml` - Configuration examples
- `monitor_signals.py` - Real-time signal monitor
- `filter_logs.py` - Log filtering utility
- `gecko_terminal_collector/utils/signal_alerting.py` - Source code

---

## 💡 Pro Tips

1. **Use multiple alert methods** - Visual + File + Webhook for redundancy
2. **Adjust min_signal_score** - Start at 60, increase to 70-80 for quality
3. **Monitor LATEST_SIGNAL.txt** - Easiest way to check current signal
4. **Set up Discord webhook** - Get signals on your phone instantly
5. **Create alert directory on SSD** - Faster file writes
6. **Use log rotation** - Prevent log files from growing too large
7. **Test with low threshold first** - Set min_signal_score to 50 to see all signals
8. **Filter by DEX** - Use target_dexes to focus on specific exchanges

---

## 🚀 Quick Start

**Minimal setup (just visual):**
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
```

**Recommended setup (visual + files):**
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
    enable_file_alerts: true
```

**Full setup (all features):**
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
    enable_file_alerts: true
    enable_sound_alerts: true
    enable_desktop_notifications: true
    enable_webhook: true
    webhook_url: "YOUR_WEBHOOK_URL"
```

Then run your collector and watch for 🚀💰 signals!
