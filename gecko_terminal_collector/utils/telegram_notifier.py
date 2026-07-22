"""
Telegram notification utility for watchlist alerts.

Sends a message to a Telegram channel/chat when a new token
is added to the watchlist for the first time.
"""

import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends Telegram notifications for new watchlist entries.

    Credentials are read from environment variables:
        TELEGRAM_BOT_TOKEN  - Bot token from BotFather
        TELEGRAM_CHAT_ID    - Channel username (e.g. @MyChannel) or numeric chat ID

    Both must be set for notifications to be sent. If either is missing the
    notifier silently no-ops so the collector continues without interruption.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 10,
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout
        self.enabled = bool(self.bot_token and self.chat_id)

        if self.enabled:
            logger.info(
                f"TelegramNotifier: enabled — chat_id={self.chat_id}, "
                f"token={self.bot_token[:10]}..."
            )
        else:
            missing = []
            if not self.bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.chat_id:
                missing.append("TELEGRAM_CHAT_ID")
            logger.error(
                f"TelegramNotifier: disabled — missing env vars: {', '.join(missing)}. "
                "Notifications will NOT be sent."
            )

    def notify_new_watchlist_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Send a Telegram message for a newly added watchlist token.

        Args:
            entry: Dict with token metadata (keys used: tokenSymbol, tokenName,
                   poolAddress, baseTokenAddress, dex, source, price,
                   liquidity, volume, marketCap, ranking)

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.error(
                "TelegramNotifier.notify_new_watchlist_entry called but notifier is disabled "
                "(missing credentials) — skipping notification"
            )
            return False

        message = self._build_message(entry)
        return self._send(message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_message(self, entry: Dict[str, Any]) -> str:
        symbol = entry.get("tokenSymbol", "UNKNOWN")
        name = entry.get("tokenName", "")
        pool = entry.get("poolAddress", "")
        token_addr = entry.get("baseTokenAddress", "")
        dex = entry.get("dex", "")
        source = entry.get("source", "")
        price = entry.get("price")
        liquidity = entry.get("liquidity")
        volume = entry.get("volume")
        market_cap = entry.get("marketCap")
        ranking = entry.get("ranking")

        lines = [
            "🆕 <b>New Watchlist Token</b>",
            "",
            f"<b>Token:</b> {symbol}" + (f" ({name})" if name else ""),
            f"<b>CA:</b> <code>{token_addr or pool}</code>",
            f"<b>DEX:</b> {dex}  |  <b>Source:</b> {source}",
        ]

        if ranking is not None:
            lines.append(f"<b>Ranking:</b> #{ranking}")

        if price is not None:
            lines.append(f"<b>Price:</b> {float(price):.10f}")

        if market_cap is not None:
            lines.append(f"<b>Market Cap:</b> ${float(market_cap):,.0f}")

        if liquidity is not None:
            lines.append(f"<b>Liquidity:</b> ${float(liquidity):,.0f}")

        if volume is not None:
            lines.append(f"<b>Volume 24h:</b> ${float(volume):,.0f}")

        # DexScreener link
        if pool:
            lines.append(
                f'<a href="https://dexscreener.com/solana/{pool}">View on DexScreener</a>'
            )

        return "\n".join(lines)

    def _send(self, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                logger.info(
                    f"Telegram notification sent successfully "
                    f"(chat_id={self.chat_id}): {message[:80]}..."
                )
                return True
            else:
                logger.error(
                    f"Telegram API returned HTTP {response.status_code} "
                    f"(chat_id={self.chat_id}): {response.text}"
                )
                return False
        except requests.exceptions.Timeout:
            logger.error(
                f"Telegram notification timed out after {self.timeout}s "
                f"(chat_id={self.chat_id})"
            )
            return False
        except requests.exceptions.ConnectionError as exc:
            logger.error(f"Telegram notification connection error: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Telegram notification unexpected error: {exc}", exc_info=True)
            return False
