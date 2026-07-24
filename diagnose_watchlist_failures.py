"""
Diagnose why entries in enhanced watchlist CSV fail to populate the pools table.

This helps identify:
1. Invalid detailUrl format
2. Addresses not found in database
3. Missing token/pool data
"""

import asyncio
import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from gecko_terminal_collector.config.config_loader import load_config
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from sqlalchemy import text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
    
    return address.lower()


async def diagnose_watchlist_csv(
    csv_path: str = "enhanced_watchlist.csv",
    config_path: str = "config.yaml"
):
    """
    Diagnose why entries in enhanced watchlist CSV fail to create pool records.
    """
    logger.info("=" * 80)
    logger.info("WATCHLIST CSV DIAGNOSTIC")
    logger.info("=" * 80)
    
    # Initialize database
    try:
        config = load_config(config_path)
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return
    
    try:
        # Read CSV
        csv_file = Path(csv_path)
        if not csv_file.exists():
            print(f"❌ CSV file not found: {csv_path}")
            return
        
        print(f"\n{'=' * 80}")
        print(f"ANALYZING: {csv_path}")
        print(f"{'=' * 80}")
        
        total_rows = 0
        invalid_urls = []
        not_in_database = []
        valid_entries = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, 1):
                total_rows += 1
                
                detail_url = row.get('detailUrl', '')
                token_symbol = row.get('tokenSymbol', 'UNKNOWN')
                
                # Step 1: Extract address from URL
                address = extract_address_from_url(detail_url)
                
                if not address:
                    invalid_urls.append({
                        'row': row_num,
                        'symbol': token_symbol,
                        'detailUrl': detail_url,
                        'reason': 'Invalid or empty detailUrl format'
                    })
                    continue
                
                # Step 2: Check if address exists in database
                with db_manager.connection.get_session() as session:
                    # Check pools table
                    result = session.execute(
                        text("SELECT id FROM pools WHERE LOWER(address) = :address LIMIT 1"),
                        {"address": address}
                    )
                    pool_found = result.fetchone()
                    
                    # Check tokens table
                    result = session.execute(
                        text("SELECT id FROM tokens WHERE LOWER(address) = :address LIMIT 1"),
                        {"address": address}
                    )
                    token_found = result.fetchone()
                    
                    # Check enhanced_watchlist_history table
                    result = session.execute(
                        text("""
                            SELECT base_token_address 
                            FROM enhanced_watchlist_history 
                            WHERE LOWER(base_token_address) = :address 
                            LIMIT 1
                        """),
                        {"address": address}
                    )
                    history_found = result.fetchone()
                
                if not (pool_found or token_found or history_found):
                    not_in_database.append({
                        'row': row_num,
                        'symbol': token_symbol,
                        'address': address,
                        'detailUrl': detail_url,
                        'liquidity': row.get('liquidity', 'N/A'),
                        'score': row.get('score', 'N/A'),
                        'is_active': row.get('is_active', 'N/A')
                    })
                else:
                    valid_entries.append({
                        'row': row_num,
                        'symbol': token_symbol,
                        'address': address,
                        'found_in': {
                            'pools': bool(pool_found),
                            'tokens': bool(token_found),
                            'history': bool(history_found)
                        }
                    })
        
        # Report results
        print(f"\n{'=' * 80}")
        print("RESULTS")
        print(f"{'=' * 80}")
        print(f"Total rows in CSV: {total_rows}")
        print(f"✅ Valid entries (can be resolved): {len(valid_entries)}")
        print(f"❌ Invalid detailUrl format: {len(invalid_urls)}")
        print(f"⚠️  Not found in database: {len(not_in_database)}")
        
        # Show invalid URLs
        if invalid_urls:
            print(f"\n{'=' * 80}")
            print(f"INVALID detailUrl FORMAT ({len(invalid_urls)} entries)")
            print(f"{'=' * 80}")
            print("\nThese entries have malformed or empty detailUrl fields:")
            
            for entry in invalid_urls[:10]:
                print(f"\nRow {entry['row']}: {entry['symbol']}")
                print(f"  detailUrl: '{entry['detailUrl']}'")
                print(f"  Reason: {entry['reason']}")
            
            if len(invalid_urls) > 10:
                print(f"\n... and {len(invalid_urls) - 10} more")
        
        # Show not in database
        if not_in_database:
            print(f"\n{'=' * 80}")
            print(f"NOT FOUND IN DATABASE ({len(not_in_database)} entries)")
            print(f"{'=' * 80}")
            print("\nThese entries have valid addresses but aren't in any database table:")
            print("(pools, tokens, or enhanced_watchlist_history)")
            
            # Group by active status
            active_missing = [e for e in not_in_database if e['is_active'] == 'True']
            inactive_missing = [e for e in not_in_database if e['is_active'] != 'True']
            
            if active_missing:
                print(f"\n🔴 ACTIVE ENTRIES NOT IN DATABASE ({len(active_missing)}):")
                for entry in active_missing[:5]:
                    print(f"\nRow {entry['row']}: {entry['symbol']}")
                    print(f"  Address: {entry['address']}")
                    print(f"  Detail URL: {entry['detailUrl']}")
                    print(f"  Liquidity: ${entry['liquidity']}")
                    print(f"  Score: {entry['score']}")
                
                if len(active_missing) > 5:
                    print(f"\n... and {len(active_missing) - 5} more active entries")
            
            if inactive_missing:
                print(f"\n⚪ INACTIVE ENTRIES NOT IN DATABASE ({len(inactive_missing)}):")
                for entry in inactive_missing[:5]:
                    print(f"\nRow {entry['row']}: {entry['symbol']}")
                    print(f"  Address: {entry['address']}")
                    print(f"  Liquidity: ${entry['liquidity']}")
                    print(f"  Score: {entry['score']}")
                
                if len(inactive_missing) > 5:
                    print(f"\n... and {len(inactive_missing) - 5} more inactive entries")
        
        # Show validation sample
        if valid_entries:
            print(f"\n{'=' * 80}")
            print(f"VALID ENTRIES SAMPLE ({len(valid_entries)} total)")
            print(f"{'=' * 80}")
            print("\nSample of entries that CAN be resolved from database:")
            
            for entry in valid_entries[:3]:
                found_tables = [k for k, v in entry['found_in'].items() if v]
                print(f"\nRow {entry['row']}: {entry['symbol']}")
                print(f"  Address: {entry['address']}")
                print(f"  Found in: {', '.join(found_tables)}")
        
        # Analysis and recommendations
        print(f"\n{'=' * 80}")
        print("ANALYSIS & RECOMMENDATIONS")
        print(f"{'=' * 80}")
        
        success_rate = (len(valid_entries) / total_rows * 100) if total_rows > 0 else 0
        print(f"\nResolution success rate: {success_rate:.1f}%")
        
        if invalid_urls:
            print(f"""
⚠️  ISSUE: Invalid detailUrl Format

{len(invalid_urls)} entries have malformed detailUrl fields.

Expected format: /solana/ADDRESS
Example: /solana/HRRSE1CiePMwfjTA5tr3tA1wVSX4KqhsB1CeFg4jAtHu

Action:
1. Check CSV generation logic in gmgn_watchlist_export.py
2. Verify detailUrl is being set correctly
3. Look for empty or null detailUrl values
            """)
        
        if not_in_database:
            print(f"""
⚠️  ISSUE: Addresses Not in Database

{len(not_in_database)} entries have valid addresses but aren't in database.

This means:
• Address extracted successfully from detailUrl
• But NOT found in pools, tokens, or enhanced_watchlist_history tables
• Database resolver will skip these entries (silent failure)

Causes:
1. TIMING: Tokens appeared after last collection cycle
2. NEW TOKENS: Never been collected before
3. FILTERED OUT: Rejected by other collectors' criteria
4. DATA GAP: Database not fully populated

Actions:
1. Run data collectors to populate database:
   python -m examples.cli_with_scheduler run-once --collector new_pools_solana
   
2. Check if these are new tokens:
   • Compare first_seen dates in watchlist_state.json
   • Check if tokens appeared very recently
   
3. Review collector logs for rejections:
   grep "ADDRESS" /var/log/collector.log
            """)
            
            if active_missing:
                print(f"""
🔴 CRITICAL: {len(active_missing)} ACTIVE entries not in database!

These are currently active in monitoring but can't be resolved.
This will cause silent failures - they won't be added to watchlist.

Immediate actions:
1. Run new pools collector for these addresses
2. Check if they're very new tokens
3. Consider manual addition if high-priority
                """)
        
        if success_rate >= 90:
            print("""
✅ HIGH SUCCESS RATE

Most entries can be resolved successfully.
The failures are likely expected (new/filtered tokens).
            """)
        elif success_rate >= 70:
            print("""
⚠️  MODERATE SUCCESS RATE

Some entries failing resolution.
Review the failures to see if action is needed.
            """)
        else:
            print("""
🔴 LOW SUCCESS RATE

Significant number of entries failing.
This indicates a data pipeline issue that needs investigation.
            """)
        
        # Export full list of problematic addresses
        if not_in_database:
            print(f"\n{'=' * 80}")
            print("FULL LIST OF UNRESOLVABLE ADDRESSES")
            print(f"{'=' * 80}")
            print("\nCopy these addresses to investigate further:")
            for entry in not_in_database:
                print(f"  {entry['address']}  # {entry['symbol']} (row {entry['row']})")
    
    except Exception as e:
        logger.error(f"Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()


async def main():
    """Main entry point."""
    import sys
    
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "enhanced_watchlist.csv"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    
    await diagnose_watchlist_csv(csv_path, config_path)


if __name__ == "__main__":
    asyncio.run(main())
