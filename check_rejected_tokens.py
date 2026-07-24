"""
Check if missing tokens exist in enhanced_watchlist_history table.

This helps determine if tokens were collected but rejected from watchlist,
or never collected at all.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Set, Dict, List

from gecko_terminal_collector.config.config_loader import load_config
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from sqlalchemy import text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_rejected_tokens(
    json_path: str = "watchlist_state.json",
    config_path: str = "config.yaml",
    token_addresses: List[str] = None
):
    """
    Check if tokens exist in enhanced_watchlist_history and analyze rejection reasons.
    
    Args:
        json_path: Path to watchlist_state.json
        config_path: Path to config file
        token_addresses: Optional list of specific addresses to check
    """
    logger.info("=" * 80)
    logger.info("REJECTED TOKENS INVESTIGATION")
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
        # Get missing tokens if not provided
        if not token_addresses:
            # Load from JSON
            with open(json_path, 'r') as f:
                state_data = json.load(f)
            
            json_addresses = set(state_data.get('tokens', {}).keys())
            
            # Get DB addresses
            with db_manager.connection.get_session() as session:
                result = session.execute(
                    text("SELECT network_address FROM watchlist WHERE network_address IS NOT NULL")
                )
                db_addresses = {row[0] for row in result}
            
            token_addresses = list(json_addresses - db_addresses)
            logger.info(f"Found {len(token_addresses)} missing tokens to investigate")
        
        if not token_addresses:
            print("\n✅ No missing tokens to investigate!")
            return
        
        print(f"\n{'=' * 80}")
        print(f"INVESTIGATING {len(token_addresses)} MISSING TOKENS")
        print(f"{'=' * 80}")
        
        # Check each token in enhanced_watchlist_history
        found_in_history = []
        not_in_history = []
        
        with db_manager.connection.get_session() as session:
            for address in token_addresses:
                # Try to find in enhanced_watchlist_history
                result = session.execute(
                    text("""
                        SELECT 
                            base_token_address,
                            token_symbol,
                            token_name,
                            source,
                            ranking,
                            liquidity,
                            market_cap,
                            price,
                            dex,
                            network,
                            collected_at
                        FROM enhanced_watchlist_history
                        WHERE base_token_address = :address
                        ORDER BY collected_at DESC
                        LIMIT 5
                    """),
                    {"address": address}
                )
                rows = result.fetchall()
                
                if rows:
                    found_in_history.append((address, rows))
                else:
                    not_in_history.append(address)
        
        # Report findings
        print(f"\n{'=' * 80}")
        print("RESULTS")
        print(f"{'=' * 80}")
        print(f"Found in enhanced_watchlist_history: {len(found_in_history)}")
        print(f"NOT in enhanced_watchlist_history: {len(not_in_history)}")
        
        # Show tokens found in history (were collected but not added to watchlist)
        if found_in_history:
            print(f"\n{'=' * 80}")
            print(f"TOKENS COLLECTED BUT NOT ADDED TO WATCHLIST ({len(found_in_history)})")
            print(f"{'=' * 80}")
            print("\nThese tokens were collected by enhanced_watchlist_collector")
            print("but were NOT added to the watchlist table.")
            print("\nPossible reasons:")
            print("• Score too low (below minimum threshold)")
            print("• Liquidity too low")
            print("• Failed duplicate check")
            print("• Address resolution failed")
            print("• Filtered by DEX or other criteria")
            
            for i, (address, rows) in enumerate(found_in_history[:10], 1):
                row = rows[0]  # Most recent
                print(f"\n{i}. TOKEN: {address}")
                print(f"   Symbol: {row[1]}")
                print(f"   Name: {row[2]}")
                print(f"   Source: {row[3]} (ranking #{row[4]})")
                print(f"   Liquidity: ${row[5]:,.2f}" if row[5] else "   Liquidity: N/A")
                print(f"   Market Cap: ${row[6]:,.2f}" if row[6] else "   Market Cap: N/A")
                print(f"   Price: ${row[7]}" if row[7] else "   Price: N/A")
                print(f"   DEX: {row[8]}")
                print(f"   Network: {row[9]}")
                print(f"   Last collected: {row[10]}")
                print(f"   Times collected: {len(rows)}")
                
                # Analysis
                liquidity = row[5] or 0
                if liquidity < 5000:
                    print(f"   ⚠️  LIKELY REASON: Liquidity too low (${liquidity:,.2f} < $5,000)")
                elif row[3] not in ['reference', 'micro', 'lowcap']:
                    print(f"   ⚠️  LIKELY REASON: Source '{row[3]}' might not be monitored")
                else:
                    print(f"   ℹ️  Possible: Score calculation or other criteria")
            
            if len(found_in_history) > 10:
                print(f"\n... and {len(found_in_history) - 10} more")
                print("\nFull list of addresses found in history:")
                for address, _ in found_in_history[10:]:
                    print(f"   {address}")
        
        # Show tokens NOT in history (never collected)
        if not_in_history:
            print(f"\n{'=' * 80}")
            print(f"TOKENS NEVER COLLECTED ({len(not_in_history)})")
            print(f"{'=' * 80}")
            print("\nThese tokens are in watchlist_state.json but were NEVER")
            print("collected by enhanced_watchlist_collector.")
            print("\nPossible reasons:")
            print("• Appeared in a different collector's monitoring")
            print("• Added manually to watchlist_state.json")
            print("• From a disabled watchlist source")
            print("• Timing: appeared and disappeared between collection cycles")
            
            print(f"\nFull list of addresses NOT in history:")
            for address in not_in_history:
                print(f"   {address}")
        
        # Check watchlist_state.json for additional context
        print(f"\n{'=' * 80}")
        print("CROSS-REFERENCE WITH WATCHLIST_STATE.JSON")
        print(f"{'=' * 80}")
        
        with open(json_path, 'r') as f:
            state_data = json.load(f)
        
        tokens_data = state_data.get('tokens', {})
        
        print("\nToken details from watchlist_state.json:")
        for address in token_addresses[:10]:
            if address in tokens_data:
                data = tokens_data[address]
                print(f"\n{address}:")
                print(f"  Active: {data.get('active', False)}")
                print(f"  Peak score: {data.get('peak_score', 'N/A')}")
                print(f"  First seen: {data.get('first_seen', 'N/A')[:19]}")
                print(f"  Last seen: {data.get('last_seen', 'N/A')[:19]}")
                print(f"  Deactivation reason: {data.get('deactivation_reason', 'N/A')}")
                
                metrics = data.get('prev_metrics', {})
                print(f"  Liquidity: ${metrics.get('liquidity', 0):,.2f}")
                print(f"  Smart degen count: {metrics.get('smart_degen_count', 0)}")
                print(f"  Holder count: {metrics.get('holder_count', 0)}")
        
        # Recommendations
        print(f"\n{'=' * 80}")
        print("NEXT STEPS FOR INVESTIGATION")
        print(f"{'=' * 80}")
        
        if found_in_history:
            print("""
1. CHECK ENHANCED WATCHLIST COLLECTOR LOGIC
   File: gecko_terminal_collector/collectors/enhanced_watchlist_collector.py
   
   Look for these rejection points:
   • Minimum score threshold
   • Liquidity filtering
   • Duplicate detection in _process_entry()
   • Address resolution in _resolve_token_address()

2. CHECK COLLECTOR LOGS
   Search for token addresses in logs:
   
   grep "TOKEN_ADDRESS" /var/log/collector.log | tail -20
   grep "rejected\\|filtered\\|failed" /var/log/collector.log | grep "TOKEN_ADDRESS"

3. REVIEW SCORING CALCULATION
   Check how scores are calculated in enhanced_watchlist_collector.py
   Look at _calculate_score() or similar methods
            """)
        
        if not_in_history:
            print("""
1. VERIFY WATCHLIST SOURCES
   Check config.yaml for enabled sources:
   
   enhanced_watchlist:
     enabled: true
     sources: [reference, micro, lowcap]  # Make sure needed sources are listed

2. CHECK IF TOKENS FROM OTHER COLLECTORS
   These might be from:
   • new_pools_collector (different tracking)
   • Manual additions
   • Deprecated collectors

3. TIMING INVESTIGATION
   Check when tokens appeared vs collection schedule:
   • Enhanced watchlist collector interval
   • Token first_seen vs collection timestamps
            """)
        
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        
        if found_in_history and not not_in_history:
            print("""
✅ All missing tokens WERE collected but not added to watchlist.
   This indicates filtering/rejection logic is working.
   Review rejection criteria if you want these tokens included.
            """)
        elif not_in_history and not found_in_history:
            print("""
⚠️  None of the missing tokens were ever collected.
   Check watchlist source configuration and collector status.
            """)
        else:
            print(f"""
Mixed results:
• {len(found_in_history)} collected but filtered out
• {len(not_in_history)} never collected

Review both collector logic and source configuration.
            """)
    
    except Exception as e:
        logger.error(f"Error during investigation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()


async def main():
    """Main entry point."""
    import sys
    
    json_path = sys.argv[1] if len(sys.argv) > 1 else "watchlist_state.json"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    
    # Check for specific token addresses
    token_addresses = None
    if len(sys.argv) > 3:
        # Remaining args are token addresses
        token_addresses = sys.argv[3:]
        logger.info(f"Checking specific tokens: {len(token_addresses)}")
    
    await check_rejected_tokens(json_path, config_path, token_addresses)


if __name__ == "__main__":
    asyncio.run(main())
