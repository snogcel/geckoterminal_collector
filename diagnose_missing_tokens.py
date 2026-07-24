"""
Diagnostic tool to identify tokens in watchlist_state.json that don't exist in database.

This helps understand why some tokens are "not found" during sync operations.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Set

from gecko_terminal_collector.config.config_loader import load_config
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_watchlist_addresses_from_db(db_manager) -> Set[str]:
    """Get all network_address values from database watchlist table."""
    addresses = set()
    
    try:
        with db_manager.connection.get_session() as session:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT network_address FROM watchlist WHERE network_address IS NOT NULL")
            )
            addresses = {row[0] for row in result}
        
        logger.info(f"Found {len(addresses)} addresses in database watchlist table")
    except Exception as e:
        logger.error(f"Error querying database: {e}")
    
    return addresses


async def load_json_tokens(json_path: str) -> Dict:
    """Load tokens from watchlist_state.json."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        tokens = data.get('tokens', {})
        logger.info(f"Found {len(tokens)} tokens in JSON file")
        return tokens
    except Exception as e:
        logger.error(f"Error loading JSON: {e}")
        return {}


async def diagnose_missing_tokens(
    json_path: str = "watchlist_state.json",
    config_path: str = "config.yaml"
):
    """
    Diagnose which tokens are in JSON but not in database and why.
    """
    logger.info("=" * 70)
    logger.info("MISSING TOKENS DIAGNOSTIC")
    logger.info("=" * 70)
    
    # Load configuration and initialize database
    try:
        config = load_config(config_path)
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        return
    
    try:
        # Get tokens from JSON
        json_tokens = await load_json_tokens(json_path)
        if not json_tokens:
            logger.error("No tokens found in JSON file")
            return
        
        # Get addresses from database
        db_addresses = await get_watchlist_addresses_from_db(db_manager)
        
        # Find missing tokens
        json_addresses = set(json_tokens.keys())
        missing_addresses = json_addresses - db_addresses
        found_addresses = json_addresses & db_addresses
        
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total tokens in JSON: {len(json_addresses)}")
        print(f"Tokens found in database: {len(found_addresses)}")
        print(f"Tokens NOT found in database: {len(missing_addresses)}")
        print(f"Match rate: {len(found_addresses)/len(json_addresses)*100:.1f}%")
        
        if missing_addresses:
            print(f"\n{'=' * 70}")
            print(f"MISSING TOKENS ({len(missing_addresses)} total)")
            print(f"{'=' * 70}")
            
            # Analyze missing tokens
            active_missing = []
            inactive_missing = []
            
            for address in missing_addresses:
                token_data = json_tokens[address]
                is_active = token_data.get('active', False)
                
                if is_active:
                    active_missing.append((address, token_data))
                else:
                    inactive_missing.append((address, token_data))
            
            print(f"\nActive tokens missing: {len(active_missing)}")
            print(f"Inactive tokens missing: {len(inactive_missing)}")
            
            # Show details of missing tokens
            if active_missing:
                print(f"\n🔴 ACTIVE TOKENS NOT IN DATABASE (CRITICAL):")
                print(f"{'=' * 70}")
                for i, (address, data) in enumerate(active_missing[:10], 1):
                    print(f"\n{i}. {address}")
                    print(f"   First seen: {data.get('first_seen', 'N/A')}")
                    print(f"   Last seen: {data.get('last_seen', 'N/A')}")
                    print(f"   Peak score: {data.get('peak_score', 'N/A')}")
                    print(f"   Liquidity: ${data.get('prev_metrics', {}).get('liquidity', 0):,.2f}")
                    print(f"   Smart degen count: {data.get('prev_metrics', {}).get('smart_degen_count', 0)}")
                
                if len(active_missing) > 10:
                    print(f"\n... and {len(active_missing) - 10} more active tokens")
            
            if inactive_missing:
                print(f"\n⚪ INACTIVE TOKENS NOT IN DATABASE (Less Critical):")
                print(f"{'=' * 70}")
                
                # Group by deactivation reason
                by_reason = {}
                for address, data in inactive_missing:
                    reason = data.get('deactivation_reason', 'unknown')
                    if reason not in by_reason:
                        by_reason[reason] = []
                    by_reason[reason].append((address, data))
                
                print("\nGrouped by deactivation reason:")
                for reason, tokens in sorted(by_reason.items(), key=lambda x: len(x[1]), reverse=True):
                    print(f"\n  {reason}: {len(tokens)} tokens")
                
                # Show sample of inactive missing
                print(f"\nSample of inactive missing tokens (first 5):")
                for i, (address, data) in enumerate(inactive_missing[:5], 1):
                    print(f"\n{i}. {address}")
                    print(f"   Peak score: {data.get('peak_score', 'N/A')}")
                    print(f"   Deactivation reason: {data.get('deactivation_reason', 'N/A')}")
                    print(f"   Deactivated at: {data.get('deactivated_at', 'N/A')}")
                    print(f"   Liquidity: ${data.get('prev_metrics', {}).get('liquidity', 0):,.2f}")
                
                if len(inactive_missing) > 5:
                    print(f"\n... and {len(inactive_missing) - 5} more inactive tokens")
        
        # Analyze why tokens might be missing
        print(f"\n{'=' * 70}")
        print("POSSIBLE REASONS FOR MISSING TOKENS")
        print(f"{'=' * 70}")
        print("""
1. NEVER ADDED TO WATCHLIST TABLE
   - Token was tracked in state file but never met criteria for watchlist
   - Token appeared in monitoring but wasn't added to database watchlist
   - Enhanced watchlist collector tracks many tokens, only adds best ones

2. REMOVED FROM WATCHLIST
   - Token was previously in watchlist but was manually removed
   - Cleanup operation removed old/inactive tokens
   - Database reset or migration

3. ADDRESS MISMATCH
   - Token address in JSON doesn't match network_address in database
   - Different address format or network prefix
   - Case sensitivity issues

4. NORMAL BEHAVIOR
   - watchlist_state.json tracks ALL monitored tokens
   - Database watchlist table only contains tokens that met entry criteria
   - Missing = monitored but didn't qualify for watchlist entry
        """)
        
        # Recommendations
        print(f"\n{'=' * 70}")
        print("RECOMMENDATIONS")
        print(f"{'=' * 70}")
        
        if active_missing:
            print(f"""
⚠️  CRITICAL: {len(active_missing)} ACTIVE tokens are missing from database!

These tokens are currently active in your monitoring but not in the database
watchlist. This means:
- They won't receive notifications
- They won't be monitored by watchlist_monitor
- Database is out of sync with monitoring state

Action Required:
1. Check if these tokens should be in watchlist
2. If yes, add them manually or re-run enhanced watchlist collector
3. Verify enhanced_watchlist_collector is properly adding tokens to database
            """)
        else:
            print(f"""
✅ Good: No active tokens are missing from database.
   All currently monitored tokens are in the database watchlist.
            """)
        
        if inactive_missing:
            print(f"""
ℹ️  INFO: {len(inactive_missing)} INACTIVE tokens are missing from database.

This is usually normal behavior:
- These tokens were monitored but never qualified for watchlist entry
- They became inactive before being added to database
- They were removed from watchlist after becoming inactive

This typically doesn't require action unless you want historical completeness.
            """)
        
        # Check database integrity
        print(f"\n{'=' * 70}")
        print("DATABASE INTEGRITY CHECK")
        print(f"{'=' * 70}")
        
        # Count total entries in database
        try:
            with db_manager.connection.get_session() as session:
                from sqlalchemy import text
                result = session.execute(text("SELECT COUNT(*) FROM watchlist"))
                total_entries = result.scalar()
                
                result = session.execute(
                    text("SELECT COUNT(*) FROM watchlist WHERE is_active = :active"),
                    {"active": True}
                )
                active_entries = result.scalar()
                
                result = session.execute(
                    text("SELECT COUNT(*) FROM watchlist WHERE network_address IS NULL")
                )
                null_addresses = result.scalar()
            
            print(f"Total watchlist entries: {total_entries}")
            print(f"Active entries: {active_entries}")
            print(f"Inactive entries: {total_entries - active_entries}")
            print(f"Entries with NULL address: {null_addresses}")
            
            if null_addresses > 0:
                print(f"\n⚠️  Warning: {null_addresses} entries have NULL network_address")
                print("   These entries cannot be matched with watchlist_state.json")
        except Exception as e:
            logger.error(f"Error checking database integrity: {e}")
        
        print(f"\n{'=' * 70}")
        print("DIAGNOSTIC COMPLETE")
        print(f"{'=' * 70}")
        
    except Exception as e:
        logger.error(f"Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()


async def main():
    """Main entry point."""
    import sys
    
    json_path = sys.argv[1] if len(sys.argv) > 1 else "watchlist_state.json"
    config_path = sys.argv[2] if len(sys.argv) > 2 else "config.yaml"
    
    await diagnose_missing_tokens(json_path, config_path)


if __name__ == "__main__":
    asyncio.run(main())
