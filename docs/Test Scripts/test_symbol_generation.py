#!/usr/bin/env python3

from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.models.core import Pool
from decimal import Decimal
from datetime import datetime

# Create a mock pool to test symbol generation
pool = Pool(
    id='solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP',
    address='7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP',
    dex_id='pumpswap',
    name='Test Pool',
    base_token_id='solana_5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump',
    quote_token_id='solana_So11111111111111111111111111111111111111112',
    reserve_usd=Decimal('1000.0'),
    created_at=datetime.now()
)

exporter = QLibExporter(None)
symbol = exporter._generate_symbol_name(pool)
print(f'Pool ID: {pool.id}')
print(f'Generated Symbol: {symbol}')
print(f'Symbol Length: {len(symbol)}')
print(f'Lowercase Symbol: {symbol.lower()}')

# Test reverse lookup
print(f'Reverse lookup: {symbol.lower() == pool.id}')