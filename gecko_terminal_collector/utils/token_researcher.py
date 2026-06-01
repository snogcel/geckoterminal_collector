"""
Token Researcher — Enriches Solana token alerts with data from
DexScreener, GeckoTerminal, and RugCheck APIs.

All APIs used are free and require no authentication.

Usage (standalone):
    python token_researcher.py <token_address>

Usage (as module):
    from token_researcher import TokenResearcher
    researcher = TokenResearcher()
    report = researcher.research("3rKbpPjTZeaJrnacWnnvx6AXSvL4Jh4pWZDGqxx8SAKd")
    print(report.to_telegram_html())
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit helper (GeckoTerminal: 30 req/min free tier)
# ---------------------------------------------------------------------------
_last_gecko_call = 0.0
GECKO_MIN_INTERVAL = 3.5  # seconds between GeckoTerminal calls (30 req/min = 2s min, leave headroom)
GECKO_WINDOW = 60.0  # rate limit window in seconds
_gecko_call_timestamps: list = []  # track recent calls for window-aware limiting


def _rate_limit_gecko():
    global _last_gecko_call, _gecko_call_timestamps
    now = time.time()
    # Prune timestamps outside the current window
    _gecko_call_timestamps = [t for t in _gecko_call_timestamps if now - t < GECKO_WINDOW]
    # If we've hit 28 calls in the last 60s (leave 2 buffer), wait until oldest expires
    if len(_gecko_call_timestamps) >= 28:
        wait_until = _gecko_call_timestamps[0] + GECKO_WINDOW
        sleep_time = wait_until - now
        if sleep_time > 0:
            logger.debug(f"GeckoTerminal near rate limit ({len(_gecko_call_timestamps)} calls in window), sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
            now = time.time()
            _gecko_call_timestamps = [t for t in _gecko_call_timestamps if now - t < GECKO_WINDOW]
    # Also enforce minimum interval between consecutive calls
    elapsed = now - _last_gecko_call
    if elapsed < GECKO_MIN_INTERVAL:
        time.sleep(GECKO_MIN_INTERVAL - elapsed)
    _last_gecko_call = time.time()
    _gecko_call_timestamps.append(_last_gecko_call)


def _gecko_get(url: str, params: dict = None, timeout: int = 10, retries: int = 5) -> Optional[dict]:
    """GET with rate limiting and 429 retry."""
    for attempt in range(retries + 1):
        _rate_limit_gecko()
        data = _get(url, params=params, timeout=timeout)
        if data is not None:
            return data
        # Exponential backoff on failure
        if attempt < retries:
            wait = (attempt + 1) * 5  # 5s, 10s
            logger.debug(f"GeckoTerminal request failed, retrying in {wait}s...")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SafetyReport:
    rugcheck_score: Optional[int] = None  # 0-100 normalised
    rugcheck_raw_score: Optional[int] = None
    risk_flags: List[Dict[str, str]] = field(default_factory=list)
    lp_locked_pct: Optional[float] = None
    mint_authority: Optional[str] = None  # "yes" / "no" / None
    freeze_authority: Optional[str] = None
    creator_address: Optional[str] = None
    creator_balance: Optional[int] = None
    insider_holders: int = 0
    top_holder_pct: Optional[float] = None  # top 10 combined %

    @property
    def danger_level(self) -> str:
        if self.rugcheck_score is None:
            return "unknown"
        if self.rugcheck_score >= 70:
            return "low"
        if self.rugcheck_score >= 40:
            return "moderate"
        return "high"

    @property
    def danger_emoji(self) -> str:
        return {"low": "🟢", "moderate": "🟡", "high": "🔴", "unknown": "⚪"}.get(
            self.danger_level, "⚪"
        )


@dataclass
class HolderReport:
    count: Optional[int] = None
    top_10_pct: Optional[float] = None
    top_20_pct: Optional[float] = None
    distribution: Dict[str, str] = field(default_factory=dict)


@dataclass
class MomentumReport:
    # Buy/sell counts
    buys_5m: int = 0
    sells_5m: int = 0
    buys_1h: int = 0
    sells_1h: int = 0
    buys_6h: int = 0
    sells_6h: int = 0
    # Unique wallets (GeckoTerminal)
    unique_buyers_1h: int = 0
    unique_sellers_1h: int = 0
    # Price changes
    change_5m: Optional[float] = None
    change_1h: Optional[float] = None
    change_6h: Optional[float] = None
    change_24h: Optional[float] = None
    # Volume
    volume_5m: Optional[float] = None
    volume_1h: Optional[float] = None
    volume_6h: Optional[float] = None
    volume_24h: Optional[float] = None

    @property
    def buy_ratio_1h(self) -> Optional[float]:
        total = self.buys_1h + self.sells_1h
        if total == 0:
            return None
        return self.buys_1h / total

    @property
    def buy_pressure_emoji(self) -> str:
        ratio = self.buy_ratio_1h
        if ratio is None:
            return "⚪"
        if ratio >= 0.6:
            return "🟢"
        if ratio >= 0.45:
            return "🟡"
        return "🔴"


@dataclass
class QualityReport:
    gt_score: Optional[float] = None
    gt_score_details: Dict[str, float] = field(default_factory=dict)
    gt_verified: bool = False


@dataclass
class NarrativeReport:
    description: str = ""
    website: str = ""
    twitter: str = ""
    telegram: str = ""
    image_url: str = ""
    has_socials: bool = False


@dataclass
class TokenReport:
    # Identity
    symbol: str = ""
    name: str = ""
    address: str = ""
    chain: str = "solana"
    dex: str = ""
    pool_address: str = ""
    # Price / market
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    liquidity_usd: Optional[float] = None
    # Timestamps
    pool_created_at: Optional[str] = None
    pool_age_seconds: Optional[int] = None
    # Derived
    volume_to_liquidity: Optional[float] = None
    # Sub-reports
    safety: SafetyReport = field(default_factory=SafetyReport)
    holders: HolderReport = field(default_factory=HolderReport)
    momentum: MomentumReport = field(default_factory=MomentumReport)
    quality: QualityReport = field(default_factory=QualityReport)
    narrative: NarrativeReport = field(default_factory=NarrativeReport)
    # Metadata
    fetched_at: str = ""
    errors: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    def to_telegram_html(self) -> str:
        """Render a Telegram-ready HTML research card."""
        lines = []

        # Header
        lines.append(f"📊 <b>Research Report: ${self.symbol}</b>")
        if self.name:
            lines.append(f"<i>{self.name}</i>")
        lines.append("")

        # Identity
        lines.append(f"<b>CA:</b> <code>{self.address}</code>")
        if self.pool_address:
            lines.append(f"<b>Pool:</b> <code>{self.pool_address}</code>")
        lines.append(f"<b>DEX:</b> {self.dex} | <b>Chain:</b> {self.chain}")
        if self.pool_age_seconds is not None:
            age_str = _format_age(self.pool_age_seconds)
            lines.append(f"<b>Token Age:</b> {age_str}")
        lines.append("")

        # Price & Market
        if self.price_usd is not None:
            lines.append(f"<b>Price:</b> ${self.price_usd:.10f}")
        if self.market_cap is not None:
            lines.append(f"<b>Market Cap:</b> ${self.market_cap:,.0f}")
        if self.liquidity_usd is not None:
            lines.append(f"<b>Liquidity:</b> ${self.liquidity_usd:,.0f}")
        if self.volume_to_liquidity is not None:
            vlr_emoji = "🔴" if self.volume_to_liquidity > 50 else "🟡" if self.volume_to_liquidity > 20 else "🟢"
            lines.append(f"<b>V/L Ratio:</b> {vlr_emoji} {self.volume_to_liquidity:.1f}x")
        lines.append("")

        # Safety
        s = self.safety
        lines.append(f"{s.danger_emoji} <b>Safety</b>")
        if s.rugcheck_score is not None:
            lines.append(f"  Risk Score: {s.rugcheck_score}/100 ({s.danger_level})")
        if s.lp_locked_pct is not None:
            lp_emoji = "🔴" if s.lp_locked_pct < 50 else "🟡" if s.lp_locked_pct < 90 else "🟢"
            lines.append(f"  {lp_emoji} LP Locked: {s.lp_locked_pct:.1f}%")
        if s.mint_authority is not None:
            mint_emoji = "🟢" if s.mint_authority == "no" else "🔴"
            lines.append(f"  {mint_emoji} Mint Authority: {s.mint_authority}")
        if s.freeze_authority is not None:
            freeze_emoji = "🟢" if s.freeze_authority == "no" else "🔴"
            lines.append(f"  {freeze_emoji} Freeze Authority: {s.freeze_authority}")
        if s.insider_holders > 0:
            lines.append(f"  ⚠️ Insider Holders in Top 10: {s.insider_holders}")
        for flag in s.risk_flags:
            level_emoji = {"danger": "🔴", "warn": "🟡", "info": "ℹ️"}.get(
                flag.get("level", ""), "⚪"
            )
            lines.append(f"  {level_emoji} {flag.get('name', 'Unknown')}")
        lines.append("")

        # Holders
        h = self.holders
        if h.count is not None:
            lines.append(f"👥 <b>Holders:</b> {h.count:,}")
            if h.top_10_pct is not None:
                conc_emoji = "🔴" if h.top_10_pct > 70 else "🟡" if h.top_10_pct > 50 else "🟢"
                lines.append(f"  {conc_emoji} Top 10 Hold: {h.top_10_pct:.1f}%")
            lines.append("")

        # Quality
        q = self.quality
        if q.gt_score is not None:
            gt_emoji = "🟢" if q.gt_score >= 70 else "🟡" if q.gt_score >= 40 else "🔴"
            lines.append(f"⭐ <b>GT Score:</b> {gt_emoji} {q.gt_score:.0f}/100")
            lines.append("")

        # Momentum
        m = self.momentum
        lines.append(f"📈 <b>Momentum</b>")
        if m.change_1h is not None:
            lines.append(f"  1h: {m.change_1h:+.1f}%  |  6h: {m.change_6h or 0:+.1f}%  |  24h: {m.change_24h or 0:+.1f}%")
        if m.buys_1h or m.sells_1h:
            lines.append(
                f"  {m.buy_pressure_emoji} Buy/Sell (1h): {m.buys_1h:,} / {m.sells_1h:,}"
            )
        if m.unique_buyers_1h or m.unique_sellers_1h:
            lines.append(
                f"  🔄 Unique Wallets (1h): {m.unique_buyers_1h:,} buyers / {m.unique_sellers_1h:,} sellers"
            )
        if m.volume_1h is not None:
            lines.append(f"  Vol 1h: ${m.volume_1h:,.0f}  |  Vol 24h: ${(m.volume_24h or 0):,.0f}")
        lines.append("")

        # Narrative
        n = self.narrative
        if n.description:
            # Truncate long descriptions
            desc = n.description[:200]
            if len(n.description) > 200:
                desc += "..."
            lines.append(f"📝 <b>Description:</b>")
            lines.append(f"  <i>{desc}</i>")
            lines.append("")
        if n.has_socials:
            social_parts = []
            if n.website:
                social_parts.append(f'<a href="{n.website}">🌐 Website</a>')
            if n.twitter:
                social_parts.append(f'<a href="https://x.com/{n.twitter}">🐦 @{n.twitter}</a>')
            if n.telegram:
                social_parts.append(f'<a href="https://t.me/{n.telegram}">💬 @{n.telegram}</a>')
            if social_parts:
                lines.append(" | ".join(social_parts))
                lines.append("")

        # DexScreener link
        if self.pool_address:
            lines.append(
                f'<a href="https://dexscreener.com/solana/{self.pool_address}">View on DexScreener</a>'
            )

        if self.errors:
            lines.append("")
            lines.append(f"⚠️ <i>Fetch errors: {'; '.join(self.errors)}</i>")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    return f"{d}d {h}h"


def _get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    """GET with error handling. Returns None on failure."""
    try:
        resp = requests.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"HTTP {resp.status_code} from {url}")
        return None
    except Exception as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Main researcher class
# ---------------------------------------------------------------------------
class TokenResearcher:
    """Fetches and aggregates token research data from multiple free APIs."""

    DEXSCREENER_BASE = "https://api.dexscreener.com"
    GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"
    RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"

    def __init__(self, chain: str = "solana", timeout: int = 10):
        self.chain = chain
        self.timeout = timeout

    def research(self, token_address: str) -> TokenReport:
        """
        Research a token by its contract address.
        Returns a populated TokenReport.
        """
        report = TokenReport(address=token_address, chain=self.chain)
        now = time.time()

        # Run all API calls concurrently
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self._fetch_dexscreener, token_address): "dexscreener",
                pool.submit(self._fetch_dexscreener_profile, token_address): "profile",
                pool.submit(self._fetch_rugcheck_summary, token_address): "rugcheck_summary",
                pool.submit(self._fetch_rugcheck_full, token_address): "rugcheck_full",
            }

            # GeckoTerminal calls are sequential due to rate limiting
            # We'll do them after the concurrent batch
            gecko_data = self._fetch_geckoterminal(token_address)

        # Process results
        for future in as_completed(futures):
            key = futures[future]
            try:
                data = future.result()
                if data is None:
                    continue
                if key == "dexscreener":
                    self._process_dexscreener(data, report)
                elif key == "profile":
                    self._process_profile(data, token_address, report)
                elif key == "rugcheck_summary":
                    self._process_rugcheck_summary(data, report)
                elif key == "rugcheck_full":
                    self._process_rugcheck_full(data, report)
            except Exception as e:
                report.errors.append(f"{key}: {e}")
                logger.error(f"Error processing {key}: {e}")

        # Process GeckoTerminal data
        if gecko_data:
            self._process_geckoterminal(gecko_data, report)

        # Compute derived metrics
        self._compute_derived(report, now)

        report.fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return report

    # ------------------------------------------------------------------
    # DexScreener
    # ------------------------------------------------------------------
    def _fetch_dexscreener(self, token_address: str) -> Optional[dict]:
        return _get(
            f"{self.DEXSCREENER_BASE}/latest/dex/tokens/{token_address}",
            timeout=self.timeout,
        )

    def _fetch_dexscreener_profile(self, token_address: str) -> Optional[dict]:
        data = _get(f"{self.DEXSCREENER_BASE}/token-profiles/latest/v1", timeout=self.timeout)
        if not data or not isinstance(data, list):
            return None
        for item in data:
            if item.get("tokenAddress") == token_address:
                return item
        return None

    def _process_dexscreener(self, data: dict, report: TokenReport):
        pairs = data.get("pairs", [])
        if not pairs:
            report.errors.append("DexScreener: no pairs found")
            return

        # Use the first (most relevant) pair
        pair = pairs[0]
        report.pool_address = pair.get("pairAddress", "")
        report.dex = pair.get("dexId", "")
        report.symbol = pair.get("baseToken", {}).get("symbol", "")
        report.name = pair.get("baseToken", {}).get("name", "")

        # Price & market
        report.price_usd = _safe_float(pair.get("priceUsd"))
        report.market_cap = _safe_float(pair.get("marketCap")) or _safe_float(pair.get("fdv"))
        report.liquidity_usd = _safe_float(pair.get("liquidity", {}).get("usd"))
        report.pool_created_at = pair.get("pairCreatedAt")

        # Volume
        vol = pair.get("volume", {})
        report.momentum.volume_5m = _safe_float(vol.get("m5"))
        report.momentum.volume_1h = _safe_float(vol.get("h1"))
        report.momentum.volume_6h = _safe_float(vol.get("h6"))
        report.momentum.volume_24h = _safe_float(vol.get("h24"))

        # Transactions
        txns = pair.get("txns", {})
        report.momentum.buys_5m = txns.get("m5", {}).get("buys", 0)
        report.momentum.sells_5m = txns.get("m5", {}).get("sells", 0)
        report.momentum.buys_1h = txns.get("h1", {}).get("buys", 0)
        report.momentum.sells_1h = txns.get("h1", {}).get("sells", 0)
        report.momentum.buys_6h = txns.get("h6", {}).get("buys", 0)
        report.momentum.sells_6h = txns.get("h6", {}).get("sells", 0)

        # Price changes
        pc = pair.get("priceChange", {})
        report.momentum.change_5m = _safe_float(pc.get("m5"))
        report.momentum.change_1h = _safe_float(pc.get("h1"))
        report.momentum.change_6h = _safe_float(pc.get("h6"))
        report.momentum.change_24h = _safe_float(pc.get("h24"))

    def _process_profile(self, data: dict, token_address: str, report: TokenReport):
        report.narrative.description = data.get("description", "")
        report.narrative.image_url = data.get("icon", "")

        links = data.get("links", [])
        for link in links:
            link_type = link.get("type", "")
            url = link.get("url", "")
            if link_type == "twitter":
                # Extract handle from URL
                handle = url.split("x.com/")[-1].split("/")[-1].split("?")[0] if "x.com" in url else url
                report.narrative.twitter = handle
            elif link_type == "telegram":
                handle = url.split("t.me/")[-1].split("/")[-1].split("?")[0] if "t.me" in url else url
                report.narrative.telegram = handle
            elif link.get("label", "").lower() == "website" or link_type == "website":
                report.narrative.website = url

        report.narrative.has_socials = bool(
            report.narrative.website or report.narrative.twitter or report.narrative.telegram
        )

    # ------------------------------------------------------------------
    # GeckoTerminal
    # ------------------------------------------------------------------
    def _fetch_geckoterminal(self, token_address: str) -> Optional[dict]:
        """Fetch from GeckoTerminal: search pools + token info."""
        # Search for pools
        pool_data = _gecko_get(
            f"{self.GECKOTERMINAL_BASE}/search/pools",
            params={"query": token_address, "network": self.chain},
            timeout=self.timeout,
        )

        # Token info
        info_data = _gecko_get(
            f"{self.GECKOTERMINAL_BASE}/networks/{self.chain}/tokens/{token_address}/info",
            timeout=self.timeout,
        )

        return {"pools": pool_data, "info": info_data}

    def _process_geckoterminal(self, data: dict, report: TokenReport):
        # Token info
        info = data.get("info")
        if info and "data" in info:
            attrs = info["data"].get("attributes", {})

            # GT Score
            report.quality.gt_score = _safe_float(attrs.get("gt_score"))
            report.quality.gt_score_details = attrs.get("gt_score_details", {})
            report.quality.gt_verified = attrs.get("gt_verified", False)

            # Holders
            holders = attrs.get("holders", {})
            if holders:
                report.holders.count = holders.get("count")
                dist = holders.get("distribution_percentage") or {}
                report.holders.top_10_pct = _safe_float(dist.get("top_10"))
                report.holders.top_20_pct = _safe_float(dist.get("11_20"))
                report.holders.distribution = dist

            # Mint/freeze (override DexScreener if not set)
            if not report.safety.mint_authority:
                ma = attrs.get("mint_authority")
                if ma is not None:
                    report.safety.mint_authority = "no" if ma is False or ma == "no" else "yes"
            if not report.safety.freeze_authority:
                fa = attrs.get("freeze_authority")
                if fa is not None:
                    report.safety.freeze_authority = "no" if fa is False or fa == "no" else "yes"

            # Socials from GeckoTerminal (usually richer than DexScreener profiles)
            if attrs.get("twitter_handle"):
                report.narrative.twitter = attrs["twitter_handle"]
            if attrs.get("telegram_handle"):
                report.narrative.telegram = attrs["telegram_handle"]
            if attrs.get("websites"):
                report.narrative.website = attrs["websites"][0]
            if attrs.get("description"):
                report.narrative.description = attrs["description"]
            if attrs.get("image_url"):
                report.narrative.image_url = attrs["image_url"]

            report.narrative.has_socials = bool(
                report.narrative.website or report.narrative.twitter or report.narrative.telegram
            )

        # Pool data — find the matching pool and get unique buyer/seller counts
        pools = data.get("pools")
        if pools and "data" in pools:
            for pool in pools["data"]:
                pool_attrs = pool.get("attributes", {})
                pool_name = pool_attrs.get("name", "")
                # Match by pool name containing our symbol or by address
                if report.pool_address and pool_attrs.get("address") == report.pool_address:
                    # Get unique buyer/seller counts from GeckoTerminal
                    txns = pool_attrs.get("transactions", {})
                    h1 = txns.get("h1", {})
                    report.momentum.unique_buyers_1h = h1.get("buyers", 0)
                    report.momentum.unique_sellers_1h = h1.get("sellers", 0)

                    # Override liquidity if GeckoTerminal has better data
                    gecko_liq = _safe_float(pool_attrs.get("reserve_in_usd"))
                    if gecko_liq and gecko_liq > 0:
                        report.liquidity_usd = gecko_liq
                    break

    # ------------------------------------------------------------------
    # RugCheck
    # ------------------------------------------------------------------
    def _fetch_rugcheck_summary(self, token_address: str) -> Optional[dict]:
        return _get(
            f"{self.RUGCHECK_BASE}/tokens/{token_address}/report/summary",
            timeout=self.timeout,
        )

    def _fetch_rugcheck_full(self, token_address: str) -> Optional[dict]:
        return _get(
            f"{self.RUGCHECK_BASE}/tokens/{token_address}/report",
            timeout=self.timeout,
        )

    def _process_rugcheck_summary(self, data: dict, report: TokenReport):
        report.safety.rugcheck_score = data.get("score_normalised")
        report.safety.rugcheck_raw_score = data.get("score")
        report.safety.lp_locked_pct = data.get("lpLockedPct")

        risks = data.get("risks", [])
        report.safety.risk_flags = [
            {"name": r.get("name", ""), "level": r.get("level", ""), "value": r.get("value", "")}
            for r in risks
        ]

    def _process_rugcheck_full(self, data: dict, report: TokenReport):
        report.safety.creator_address = data.get("creator")
        report.safety.creator_balance = data.get("creatorBalance")

        # Count insider holders in top 10
        top_holders = data.get("topHolders", [])
        report.safety.insider_holders = sum(
            1 for h in top_holders[:10] if h.get("insider", False)
        )

        # Top holder concentration from RugCheck data
        if top_holders:
            top_10_pct = sum(h.get("pct", 0) for h in top_holders[:10])
            report.safety.top_holder_pct = top_10_pct
            # Override holder distribution if GeckoTerminal didn't provide it
            if not report.holders.top_10_pct:
                report.holders.top_10_pct = top_10_pct

        # Mint/freeze authority from RugCheck (most reliable)
        token_info = data.get("token", {})
        if token_info:
            report.safety.mint_authority = (
                "no" if token_info.get("mintAuthority") is None else "yes"
            )
            report.safety.freeze_authority = (
                "no" if token_info.get("freezeAuthority") is None else "yes"
            )

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------
    def _compute_derived(self, report: TokenReport, now: float):
        # Volume-to-liquidity ratio
        vol_24h = report.momentum.volume_24h
        if vol_24h and report.liquidity_usd and report.liquidity_usd > 0:
            report.volume_to_liquidity = vol_24h / report.liquidity_usd

        # Pool age
        if report.pool_created_at:
            try:
                # DexScreener returns epoch ms
                created = float(report.pool_created_at) / 1000
                report.pool_age_seconds = int(now - created)
            except (ValueError, TypeError):
                pass


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python token_researcher.py <token_address>")
        print("Example: python token_researcher.py 3rKbpPjTZeaJrnacWnnvx6AXSvL4Jh4pWZDGqxx8SAKd")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    token_address = sys.argv[1]
    researcher = TokenResearcher()
    report = researcher.research(token_address)

    print("\n" + "=" * 60)
    print(report.to_telegram_html())
    print("=" * 60)
    print(f"\nFetched at: {report.fetched_at}")
    if report.errors:
        print(f"Errors: {report.errors}")
