"""
Diagnose API failures when collecting enhanced watchlist entries.

This script tests each entry in your CSV to see if the API can resolve it,
showing exactly which entries fail and why.
"""

import asyncio
import csv
import logging
import re
from pathlib import Path
from typing import Optional
import aiohttp

# Setup logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_address_from_url(detail_url: str) -> Optional[str]:
    """Extract address from detailUrl."""
    if not detail_url:
        return None
    
    match = re.match(r'^/([^/]+)/([a-zA-Z0-9]+)$', detail_url.strip())
    if not match:
        return None
    
    network, address = match.groups()
    if network.lower() != 'solana':
        return None
    
    return address


async def test_api_call(address: str, session: aiohttp.ClientSession) -> dict:
    """Test a single API call for an address."""
    api_base_url = "https://api.geckoterminal.com/api/v2"
    endpoint = f"/networks/solana/pools/{address}"
    params = {
        "include": "base_token,quote_token,dex",
        "include_volume_breakdown": "false",
        "include_composition": "false",
    }
    
    try:
        async with session.get(
            f"{api_base_url}{endpoint}",
            params=params,
            headers={"Accept": "application/json"},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            status = response.status
            
            if status == 200:
                data = await response.json()
                pool_name = data.get('data', {}).get('attributes', {}).get('name', 'Unknown')
                return {
                    'success': True,
                    'status': status,
                    'pool_name': pool_name,
                    'message': f"✅ Found: {pool_name}"
                }
            elif status == 429:
                return {
                    'success': False,
                    'status': status,
                    'message': "⚠️  Rate limited (429)"
                }
            elif status == 404:
                return {
                    'success': False,
                    'status': status,
                    'message': "❌ Not found (404) - Pool doesn't exist on GeckoTerminal"
                }
            else:
                return {
                    'success': False,
                    'status': status,
                    'message': f"❌ HTTP {status}"
                }
                
    except asyncio.TimeoutError:
        return {
            'success': False,
            'status': None,
            'message': "⏱️  Timeout - API took too long to respond"
        }
    except Exception as e:
        return {
            'success': False,
            'status': None,
            'message': f"❌ Error: {str(e)[:50]}"
        }


async def diagnose_csv(csv_path: str = "enhanced_watchlist.csv"):
    """Diagnose API failures for all entries in CSV."""
    print("=" * 80)
    print("API FAILURE DIAGNOSTIC")
    print("=" * 80)
    print(f"\nAnalyzing: {csv_path}")
    print("Testing each entry with GeckoTerminal API...")
    print(f"{'=' * 80}\n")
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return
    
    # Statistics
    total_rows = 0
    invalid_urls = 0
    successful = []
    failed = []
    rate_limited = []
    not_found = []
    
    # Create session with connection pooling
    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(limit=5)  # Limit concurrent connections
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, 1):
                total_rows += 1
                detail_url = row.get('detailUrl', '')
                token_symbol = row.get('tokenSymbol', 'UNKNOWN')
                is_active = row.get('is_active', 'False')
                
                # Extract address
                address = extract_address_from_url(detail_url)
                if not address:
                    invalid_urls += 1
                    print(f"Row {row_num}: {token_symbol} - ⚠️  Invalid detailUrl: '{detail_url}'")
                    continue
                
                # Test API call
                print(f"Row {row_num}: {token_symbol} ({address[:8]}...) - ", end='', flush=True)
                result = await test_api_call(address, session)
                print(result['message'])
                
                # Categorize result
                entry_info = {
                    'row': row_num,
                    'symbol': token_symbol,
                    'address': address,
                    'is_active': is_active,
                    'liquidity': row.get('liquidity', 'N/A'),
                    'score': row.get('score', 'N/A'),
                    'result': result
                }
                
                if result['success']:
                    successful.append(entry_info)
                elif result['status'] == 429:
                    rate_limited.append(entry_info)
                    # Brief pause after rate limit
                    await asyncio.sleep(2)
                elif result['status'] == 404:
                    not_found.append(entry_info)
                else:
                    failed.append(entry_info)
                
                # Small delay between requests to be polite
                if row_num % 5 == 0:
                    await asyncio.sleep(1)
    
    # Report results
    print(f"\n{'=' * 80}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total entries tested: {total_rows}")
    print(f"✅ Successful: {len(successful)} ({len(successful)/total_rows*100:.1f}%)")
    print(f"❌ Failed: {len(failed)}")
    print(f"❌ Not found (404): {len(not_found)}")
    print(f"⚠️  Rate limited (429): {len(rate_limited)}")
    print(f"⚠️  Invalid URLs: {invalid_urls}")
    
    # Detailed breakdown
    if not_found:
        print(f"\n{'=' * 80}")
        print(f"POOLS NOT FOUND ON GECKOTERMINAL ({len(not_found)} entries)")
        print(f"{'=' * 80}")
        print("\nThese pools don't exist in GeckoTerminal's database:")
        
        active_not_found = [e for e in not_found if e['is_active'] == 'True']
        inactive_not_found = [e for e in not_found if e['is_active'] != 'True']
        
        if active_not_found:
            print(f"\n🔴 ACTIVE entries not found ({len(active_not_found)}):")
            for entry in active_not_found[:5]:
                print(f"\n  Row {entry['row']}: {entry['symbol']}")
                print(f"    Address: {entry['address']}")
                print(f"    Liquidity: ${entry['liquidity']}")
                print(f"    Score: {entry['score']}")
            if len(active_not_found) > 5:
                print(f"\n  ... and {len(active_not_found) - 5} more")
        
        if inactive_not_found:
            print(f"\n⚪ INACTIVE entries not found ({len(inactive_not_found)}):")
            print("  (First 3 shown)")
            for entry in inactive_not_found[:3]:
                print(f"  Row {entry['row']}: {entry['symbol']} - {entry['address'][:10]}...")
    
    if rate_limited:
        print(f"\n{'=' * 80}")
        print(f"RATE LIMITED ({len(rate_limited)} entries)")
        print(f"{'=' * 80}")
        print("\nThese entries hit rate limits during testing.")
        print("The collector will retry with backoff, but may eventually fail.")
        print(f"\nAffected rows: {', '.join(str(e['row']) for e in rate_limited[:10])}")
        if len(rate_limited) > 10:
            print(f"... and {len(rate_limited) - 10} more")
    
    if failed:
        print(f"\n{'=' * 80}")
        print(f"OTHER FAILURES ({len(failed)} entries)")
        print(f"{'=' * 80}")
        for entry in failed[:5]:
            print(f"\nRow {entry['row']}: {entry['symbol']}")
            print(f"  {entry['result']['message']}")
    
    # Analysis
    print(f"\n{'=' * 80}")
    print("ANALYSIS & RECOMMENDATIONS")
    print(f"{'=' * 80}")
    
    success_rate = len(successful) / total_rows * 100 if total_rows > 0 else 0
    
    if success_rate >= 90:
        print(f"""
✅ HIGH SUCCESS RATE ({success_rate:.1f}%)

Most entries can be resolved via GeckoTerminal API.
The few failures are likely:
- Very new pools not yet in GeckoTerminal
- Delisted/removed pools
- Pools from excluded DEXes

Action: None needed. System is working well.
        """)
    elif success_rate >= 70:
        print(f"""
⚠️  MODERATE SUCCESS RATE ({success_rate:.1f}%)

Some entries failing API resolution.

Possible causes:
- Rate limiting (too many requests too fast)
- New pools not yet indexed by GeckoTerminal
- Some pools removed from GeckoTerminal

Actions:
1. Reduce collection frequency to avoid rate limits
2. Add delays between API calls
3. Consider caching successfully resolved pools
        """)
    else:
        print(f"""
🔴 LOW SUCCESS RATE ({success_rate:.1f}%)

Significant API failure rate!

Likely causes:
- Heavy rate limiting from GeckoTerminal
- Network connectivity issues
- Many invalid/old pool addresses in CSV
- GeckoTerminal API issues

Actions:
1. Check your network connectivity
2. Verify GeckoTerminal API status
3. Review your CSV data quality
4. Increase delays between API calls
5. Consider implementing database caching
        """)
    
    if not_found:
        print(f"""
ℹ️  NOTE: {len(not_found)} pools returned 404 (Not Found)

This means these pools don't exist in GeckoTerminal's database:
- Very new pools (< 24 hours old)
- Pools from unsupported DEXes
- Dead/delisted pools
- Incorrect pool addresses

These entries will be skipped during collection (expected behavior).
        """)
    
    if rate_limited:
        print(f"""
⚠️  RATE LIMITING DETECTED

{len(rate_limited)} requests hit rate limits during this test.

The collector has retry logic with exponential backoff, but:
- Increases collection time significantly
- May eventually fail after max retries
- Can trigger circuit breaker protection

Recommendations:
1. Reduce collection frequency
2. Increase delays between requests
3. Process fewer entries per run
4. Monitor rate limit patterns in production logs
        """)
    
    # Export problematic addresses
    if not_found or failed:
        print(f"\n{'=' * 80}")
        print("ADDRESSES THAT WILL FAIL IN PRODUCTION")
        print(f"{'=' * 80}")
        print("\nThese addresses will be skipped with 'Skipping unresolved pool data' message:")
        
        for entry in (not_found + failed):
            status = "ACTIVE" if entry['is_active'] == 'True' else "INACTIVE"
            print(f"  {entry['address']}  # Row {entry['row']}: {entry['symbol']} ({status})")


async def main():
    """Main entry point."""
    import sys
    
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "enhanced_watchlist.csv"
    
    print("\n⚠️  NOTE: This script makes real API calls to GeckoTerminal")
    print("It will test each entry in your CSV file to see if the API can resolve it.")
    print("This may trigger rate limits if you have many entries.\n")
    
    await diagnose_csv(csv_path)
    
    print(f"\n{'=' * 80}")
    print("DIAGNOSTIC COMPLETE")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(main())
