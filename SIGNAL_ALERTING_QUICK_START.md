# 🚀 Signal Alerting - Quick Start

## The Problem
Too much noise in logs → Can't spot strong trading signals quickly → Miss opportunities

## The Solution
Multi-level alerting system with visual, audio, file, and webhook notifications

---

## ⚡ Quick Setup (30 seconds)

### Step 1: Add to your `config.yaml`
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true      # Bright green + bold
    use_emojis: true      # 🚀💰 indicators
    enable_file_alerts: true  # Creates alerts/ folder
```

### Step 2: Run your collector
```bash
python your_collector_script.py
```

### Step 3: Watch for signals
Look for this in your terminal:
```
================================================================================
🚀💰 TRADE_SIGNAL - STRONG SIGNAL DETECTED: Pool solana_abc123
Signal Score: 85.2/100 | Volume: spike | Liquidity: growing
================================================================================
```

**That's it!** Signals now stand out visually.

---

## 📁 File-Based Monitoring (Recommended)

Signals are automatically saved to `alerts/LATEST_SIGNAL.txt`

**Monitor in real-time:**
```bash
python monitor_signals.py
```

**Or watch the file:**
```bash
# Windows
powershell -Command "Get-Content alerts\LATEST_SIGNAL.txt -Wait"

# Linux/Mac
tail -f alerts/LATEST_SIGNAL.txt
```

---

## 🔔 Optional Enhancements

### Sound Alerts (Beep on signal)
```yaml
enable_sound_alerts: true
```

### Desktop Notifications (Popup)
```yaml
enable_desktop_notifications: true
```
Requires: `pip install plyer` or `pip install win10toast`

### Discord/Slack/Telegram Webhook
```yaml
enable_webhook: true
webhook_url: "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
```

---

## 🛠️ Helper Tools

### 1. Real-time Monitor
```bash
python monitor_signals.py
```
Shows latest signal, auto-refreshes, beeps on new signals

### 2. Filter Logs
```bash
# Extract all signals
python filter_logs.py logs/collector.log

# Only high-quality signals (≥80)
python filter_logs.py logs/collector.log --min-score 80

# Save to file
python filter_logs.py logs/collector.log --output signals.log

# Analyze statistics
python filter_logs.py logs/collector.log --analyze
```

### 3. List Recent Signals
```bash
python monitor_signals.py --list
```

---

## 📊 Configuration Examples

### Minimal (Visual Only)
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
```

### Recommended (Visual + Files)
```yaml
new_pools:
  signal_detection:
    enabled: true
    use_colors: true
    use_emojis: true
    enable_file_alerts: true
    min_signal_score: 60.0
```

### Full Featured (Everything)
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
    min_signal_score: 70.0
```

---

## 🎯 Quick Action Workflows

### Manual Trading
1. Run collector with visual alerts
2. Watch for 🚀💰 in terminal
3. Check `alerts/LATEST_SIGNAL.txt` for details
4. Execute trade

### Mobile Trading
1. Setup Discord webhook
2. Get notification on phone
3. Review signal
4. Trade via mobile app

### Automated Trading
1. Setup webhook to trading bot
2. Bot receives signal
3. Bot validates & executes

---

## 📚 Full Documentation

- `docs/SIGNAL_ALERTING_GUIDE.md` - Complete guide
- `config_signal_alerts.yaml` - Configuration examples
- `gecko_terminal_collector/utils/signal_alerting.py` - Source code

---

## 💡 Pro Tips

1. Start with `min_signal_score: 60`, increase to 70-80 for quality
2. Use file alerts + webhook for redundancy
3. Monitor `alerts/LATEST_SIGNAL.txt` - easiest way to check
4. Set up Discord webhook for mobile notifications
5. Use `filter_logs.py --analyze` to review signal quality

---

## 🚀 Next Steps

1. ✅ Add config to `config.yaml`
2. ✅ Run collector
3. ✅ Watch for 🚀💰 signals
4. ✅ (Optional) Setup webhook for mobile alerts
5. ✅ (Optional) Run `python monitor_signals.py` in separate terminal

**You're ready to catch signals quickly!**
