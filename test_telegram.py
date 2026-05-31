"""
Standalone test script for TelegramNotifier.

Usage:
    python test_telegram.py

Set credentials via environment variables before running:
    set TELEGRAM_BOT_TOKEN=123456:ABC-your-token
    set TELEGRAM_CHAT_ID=@YourChannel

Or create a .env file in this directory with those two keys — the script
will load it automatically if python-dotenv is available.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Optional: load a .env file so you don't have to set env vars manually
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env file")
except ImportError:
    print("python-dotenv not installed — reading env vars directly")

# ---------------------------------------------------------------------------
# Add project root to path so the import works regardless of cwd
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

#from gecko_terminal_collector.utils.telegram_notifier import TelegramNotifier
from gecko_terminal_collector.utils.telegram_notifier_enriched import TelegramNotifier

def check_config(notifier: TelegramNotifier) -> bool:
    """Print current config and return True if credentials are present."""
    token = notifier.bot_token
    chat = notifier.chat_id

    print("\n--- Credential check ---")
    print(f"  TELEGRAM_BOT_TOKEN : {'SET (' + token[:10] + '...)' if token else 'NOT SET'}")
    print(f"  TELEGRAM_CHAT_ID   : {chat if chat else 'NOT SET'}")
    print(f"  Notifier enabled   : {notifier.enabled}")

    if not notifier.enabled:
        print(
            "\n[ERROR] One or both credentials are missing.\n"
            "Set them as environment variables or add them to a .env file:\n"
            "  TELEGRAM_BOT_TOKEN=<your bot token>\n"
            "  TELEGRAM_CHAT_ID=<@YourChannel or numeric chat id>\n"
        )
        return False
    return True


def send_test_message(notifier: TelegramNotifier) -> None:
    """Send a plain text ping to verify the bot can reach the chat."""
    print("\n--- Sending plain test message ---")
    ok = notifier._send("✅ TelegramNotifier test — plain message works!")
    print("Result:", "SUCCESS" if ok else "FAILED")


def send_mock_watchlist_notification(notifier: TelegramNotifier) -> None:
    """Send a realistic mock watchlist notification."""
    mock_entry = {
        "tokenSymbol": "TESTTOKEN",
        "tokenName": "Test Token",
        "poolAddress": "3DkuxPBEeKQpa7vfJQ5XModjparDZExCDyqiSzctLASb",
        "baseTokenAddress": "dfjnr4xpceatfziu59cotird632d2ivqhb12nvygjbqb",
        "dex": "pumpswap",
        "source": "micro",
        "ranking": 7,
        "price": 0.0001240,
        "marketCap": 124000,
        "liquidity": 45000,
        "volume": 89000,
        "detailUrl": "https://www.geckoterminal.com/solana/pools/3DkuxPBEeKQpa7vfJQ5XModjparDZExCDyqiSzctLASb",
    }

    print("\n--- Sending mock watchlist notification ---")
    print("Mock entry:", mock_entry)
    ok = notifier.notify_new_watchlist_entry(mock_entry)
    print("Result:", "SUCCESS" if ok else "FAILED")


if __name__ == "__main__":
    notifier = TelegramNotifier()

    if not check_config(notifier):
        sys.exit(1)

    send_test_message(notifier)
    send_mock_watchlist_notification(notifier)

    print("\nDone. Check your Telegram channel for both messages.")
