import asyncio
from unittest.mock import AsyncMock

from gecko_terminal_collector.cli import _resolve_watchlist_item_from_database


class DummyEntry:
    def __init__(self, pool_id, token_symbol=None, token_name=None, network_address=None, is_active=True):
        self.pool_id = pool_id
        self.token_symbol = token_symbol
        self.token_name = token_name
        self.network_address = network_address
        self.is_active = is_active


def test_resolve_watchlist_item_from_database_matches_prefixed_pool_id():
    async def run_test():
        db_manager = AsyncMock()
        db_manager.get_active_watchlist_entries.return_value = [
            DummyEntry(
                pool_id="solana_abc123",
                token_symbol="TEST",
                token_name="Test Token",
                network_address="network123",
                is_active=True,
            )
        ]

        resolved = await _resolve_watchlist_item_from_database(db_manager, "solana_abc123")

        assert resolved is not None
        assert resolved["poolAddress"] == "solana_abc123"
        assert resolved["tokenSymbol"] == "TEST"

    asyncio.run(run_test())


def test_resolve_watchlist_item_from_database_falls_back_to_all_entries():
    async def run_test():
        db_manager = AsyncMock()
        db_manager.get_active_watchlist_entries.return_value = []
        db_manager.get_all_watchlist_entries.return_value = [
            DummyEntry(
                pool_id="solana_xyz789",
                token_symbol="ALT",
                token_name="Alt Token",
                network_address="network999",
                is_active=False,
            )
        ]

        resolved = await _resolve_watchlist_item_from_database(db_manager, "network999")

        assert resolved is not None
        assert resolved["networkAddress"] == "network999"
        assert resolved["poolAddress"] == "solana_xyz789"

    asyncio.run(run_test())
