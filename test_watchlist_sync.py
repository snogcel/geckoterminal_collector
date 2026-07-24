"""
Test script for watchlist active status synchronization.

This script tests the synchronization functionality without modifying
the actual database.
"""

import asyncio
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_watchlist_state(json_path: str = "watchlist_state.json"):
    """Analyze watchlist state file and show statistics."""
    logger.info("=" * 70)
    logger.info("WATCHLIST STATE ANALYSIS")
    logger.info("=" * 70)
    
    try:
        path = Path(json_path)
        if not path.exists():
            logger.error(f"❌ File not found: {json_path}")
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        tokens = data.get('tokens', {})
        meta = data.get('meta', {})
        
        # Count active/inactive
        active_count = 0
        inactive_count = 0
        deactivation_reasons = {}
        
        active_tokens = []
        inactive_tokens = []
        
        for token_address, token_data in tokens.items():
            is_active = token_data.get('active', False)
            
            if is_active:
                active_count += 1
                active_tokens.append({
                    'address': token_address,
                    'peak_score': token_data.get('peak_score', 0),
                    'liquidity': token_data.get('prev_metrics', {}).get('liquidity', 0),
                    'first_seen': token_data.get('first_seen', 'N/A')
                })
            else:
                inactive_count += 1
                reason = token_data.get('deactivation_reason', 'unknown')
                deactivation_reasons[reason] = deactivation_reasons.get(reason, 0) + 1
                inactive_tokens.append({
                    'address': token_address,
                    'peak_score': token_data.get('peak_score', 0),
                    'deactivation_reason': reason,
                    'deactivated_at': token_data.get('deactivated_at', 'N/A')
                })
        
        # Print statistics
        logger.info(f"\n📊 OVERALL STATISTICS")
        logger.info(f"   Total tokens: {len(tokens)}")
        logger.info(f"   ✅ Active: {active_count} ({active_count/len(tokens)*100:.1f}%)")
        logger.info(f"   ❌ Inactive: {inactive_count} ({inactive_count/len(tokens)*100:.1f}%)")
        logger.info(f"   📅 Total cycles: {meta.get('total_cycles', 'N/A')}")
        logger.info(f"   🕐 Last run: {meta.get('last_run', 'N/A')}")
        
        # Deactivation reasons
        if deactivation_reasons:
            logger.info(f"\n📋 DEACTIVATION REASONS")
            for reason, count in sorted(deactivation_reasons.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"   {reason}: {count}")
        
        # Show sample active tokens
        if active_tokens:
            logger.info(f"\n✅ SAMPLE ACTIVE TOKENS (Top 5 by peak score)")
            active_tokens.sort(key=lambda x: x['peak_score'], reverse=True)
            for i, token in enumerate(active_tokens[:5], 1):
                logger.info(f"   {i}. {token['address'][:10]}...")
                logger.info(f"      Peak Score: {token['peak_score']}")
                logger.info(f"      Liquidity: ${token['liquidity']:,.2f}")
                logger.info(f"      First Seen: {token['first_seen'][:19]}")
        
        # Show sample inactive tokens
        if inactive_tokens:
            logger.info(f"\n❌ SAMPLE INACTIVE TOKENS (Most recent 5)")
            inactive_tokens.sort(key=lambda x: x['deactivated_at'], reverse=True)
            for i, token in enumerate(inactive_tokens[:5], 1):
                logger.info(f"   {i}. {token['address'][:10]}...")
                logger.info(f"      Peak Score: {token['peak_score']}")
                logger.info(f"      Reason: {token['deactivation_reason']}")
                logger.info(f"      Deactivated: {token['deactivated_at'][:19]}")
        
        # Show what would be updated
        logger.info(f"\n🔄 SYNC PREVIEW")
        logger.info(f"   Addresses to set ACTIVE: {active_count}")
        logger.info(f"   Addresses to set INACTIVE: {inactive_count}")
        logger.info(f"   Total database updates: {len(tokens)}")
        
        logger.info("=" * 70)
        logger.info("✅ Analysis completed!")
        logger.info("=" * 70)
        
        # Return data for further use
        return {
            'total': len(tokens),
            'active': active_count,
            'inactive': inactive_count,
            'deactivation_reasons': deactivation_reasons,
            'active_addresses': [t['address'] for t in active_tokens],
            'inactive_addresses': [t['address'] for t in inactive_tokens]
        }
        
    except Exception as e:
        logger.error(f"❌ Error analyzing watchlist state: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point."""
    import sys
    
    json_path = sys.argv[1] if len(sys.argv) > 1 else "watchlist_state.json"
    
    logger.info(f"📄 Analyzing file: {json_path}\n")
    
    await analyze_watchlist_state(json_path)


if __name__ == "__main__":
    asyncio.run(main())
