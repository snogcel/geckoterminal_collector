"""
Enriched Telegram notification utility for watchlist alerts.

Drop-in replacement for the original TelegramNotifier that adds
token research from DexScreener, GeckoTerminal, and RugCheck before
sending the notification.

Usage:
    # Same API as original — just import this instead
    from telegram_notifier_enriched import TelegramNotifier

    notifier = TelegramNotifier()
    notifier.notify_new_watchlist_entry(entry)

    # Or disable enrichment for faster (basic) alerts
    notifier = TelegramNotifier(enrich=False)
"""

import logging
import os
from typing import Any, Dict, Optional

import requests

from token_researcher import TokenResearcher, TokenReport

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends Telegram notifications for new watchlist entries.

    Extends the original notifier with optional token research enrichment.

    Credentials are read from environment variables:
    TELEGRAM_BOT_TOKEN - Bot token from BotFather
    TELEGRAM_CHAT_ID - Channel username (e.g. @MyChannel) or numeric chat ID

    Both must be set for notifications to be sent. If either is missing the
    notifier silently no-ops so the collector continues without interruption.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 10,
        enrich: bool = True,
        chain: str = "solana",
    ):
        """
        Args:
            bot_token: Telegram bot token (or env TELEGRAM_BOT_TOKEN)
            chat_id: Telegram chat/channel ID (or env TELEGRAM_CHAT_ID)
            timeout: HTTP timeout for Telegram API calls
            enrich: If True (default), research tokens before sending
            chain: Blockchain to research on (default: "solana")
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout
        self.enabled = bool(self.bot_token and self.chat_id)
        self.enrich = enrich
        self.chain = chain

        if self.enrich:
            self.researcher = TokenResearcher(chain=chain, timeout=timeout)
        else:
            self.researcher = None

        if self.enabled:
            logger.info(
                f"TelegramNotifier: enabled — chat_id={self.chat_id}, "
                f"token={self.bot_token[:10]}..., enrich={self.enrich}"
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

        If enrichment is enabled, this will research the token via
        DexScreener, GeckoTerminal, and RugCheck before sending.

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

        token_addr = entry.get("baseTokenAddress", "")

        if self.enrich and token_addr and self.researcher:
            return self._send_enriched(entry, token_addr)
        else:
            return self._send_basic(entry)

    def _send_enriched(self, entry: Dict[str, Any], token_addr: str) -> bool:
        """Research the token and send an enriched message."""
        try:
            logger.info(f"Researching token {token_addr}...")
            report = self.researcher.research(token_addr)

            # If research returned useful data, use enriched format
            if report.symbol or report.safety.rugcheck_score is not None:
                message = self._build_enriched_message(entry, report)
            else:
                # Fall back to basic if research didn't find anything
                logger.warning(f"Research returned no data for {token_addr}, using basic format")
                message = self._build_message(entry)

            return self._send(message)

        except Exception as e:
            logger.error(f"Research failed for {token_addr}: {e}", exc_info=True)
            # Fall back to basic message on error
            message = self._build_message(entry)
            return self._send(message)

    def _send_basic(self, entry: Dict[str, Any]) -> bool:
        """Send a basic (un-enriched) message — original behavior."""
        message = self._build_message(entry)
        return self._send(message)

    # ------------------------------------------------------------------
    # Message builders
    # ------------------------------------------------------------------

    def _build_enriched_message(self, entry: Dict[str, Any], report: TokenReport) -> str:
        """Build a rich research card from the TokenReport."""
        lines = []

        # Header with original signal context
        source = entry.get("source", "")
        ranking = entry.get("ranking")
        lines.append("🚨 <b>SIGNAL ALERT</b>")
        if ranking:
            lines.append(f"<i>Top 100 Rank #{ranking}</i>")
        lines.append("")

        # Use the report's formatted output
        lines.append(report.to_telegram_html())

        return "\n".join(lines)

    def _build_message(self, entry: Dict[str, Any]) -> str:
        """Original basic message format."""
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
            f"<b>DEX:</b> {dex} | <b>Source:</b> {source}",
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

        detail_url = entry.get("detailUrl")
        if detail_url:
            lines.append(f'\n<a href="{detail_url}">View on GeckoTerminal</a>')

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

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
