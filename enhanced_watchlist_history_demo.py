#!/usr/bin/env python3
"""
Enhanced Watchlist Historical Data Collection Demo.

This script demonstrates the enhanced watchlist collector's historical data capabilities:
1. Multiple source segments (lowcap, micro, midcap, oldlowcap, oldmicro, reference)
2. Hourly data collection with rate limiting
3. Historical data storage and retrieval
4. Source-based analysis and reporting
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_historical_data(db_manager):
    """Analyze historical enhanced watchlist data."""
    
    logger.info("=== Enhanced Watchlist Historical Data Analysis ===")
    
    try:
        # 1. Overall statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_entries,
            COUNT(DISTINCT source) as unique_sources,
            COUNT(DISTINCT token_symbol) as unique_tokens,
            MIN(collected_at) as earliest_data,
            MAX(collected_at) as latest_data
        FROM enhanced_watchlist_history
        """
        
        stats = await db_manager.execute_query(stats_query)
        if stats:
            row = stats[0]
            logger.info(f"Total Entries: {row[0]:,}")
            logger.info(f"Unique Sources: {row[1]}")
            logger.info(f"Unique Tokens: {row[2]:,}")
            logger.info(f"Data Range: {row[3]} to {row[4]}")
        
        # 2. Entries by source
        source_query = """
        SELECT 
            source,
            COUNT(*) as entry_count,
            COUNT(DISTINCT token_symbol) as unique_tokens,
            AVG(CAST(market_cap AS FLOAT)) as avg_market_cap,
            AVG(CAST(liquidity AS FLOAT)) as avg_liquidity
        FROM enhanced_watchlist_history 
        WHERE market_cap IS NOT NULL AND liquidity IS NOT NULL
        GROUP BY source
        ORDER BY entry_count DESC
        """
        
        sources = await db_manager.execute_query(source_query)
        
        logger.info("\n=== Data by Source ===")
        for row in sources:
            logger.info(f"Source: {row[0]}")
            logger.info(f"  Entries: {row[1]:,}")
            logger.info(f"  Unique Tokens: {row[2]:,}")
            logger.info(f"  Avg Market Cap: ${row[3]:,.2f}" if row[3] else "  Avg Market Cap: N/A")
            logger.info(f"  Avg Liquidity: ${row[4]:,.2f}" if row[4] else "  Avg Liquidity: N/A")
        
        # 3. Top tokens by frequency across sources
        frequency_query = """
        SELECT 
            token_symbol,
            token_name,
            COUNT(*) as appearances,
            COUNT(DISTINCT source) as sources_count,
            STRING_AGG(DISTINCT source, ', ') as sources
        FROM enhanced_watchlist_history
        GROUP BY token_symbol, token_name
        HAVING COUNT(*) > 1
        ORDER BY appearances DESC, sources_count DESC
        LIMIT 10
        """
        
        frequent_tokens = await db_manager.execute_query(frequency_query)
        
        logger.info("\n=== Most Frequent Tokens Across Sources ===")
        for i, row in enumerate(frequent_tokens, 1):
            logger.info(f"{i}. {row[0]} ({row[1]})")
            logger.info(f"   Appearances: {row[2]}, Sources: {row[3]} ({row[4]})")
        
        # 4. Recent ranking changes
        ranking_query = """
        WITH ranked_data AS (
            SELECT 
                token_symbol,
                source,
                ranking,
                collected_at,
                LAG(ranking) OVER (PARTITION BY token_symbol, source ORDER BY collected_at) as prev_ranking
            FROM enhanced_watchlist_history
            WHERE collected_at >= NOW() - INTERVAL '24 hours'
        )
        SELECT 
            token_symbol,
            source,
            ranking as current_ranking,
            prev_ranking,
            (prev_ranking - ranking) as ranking_change,
            collected_at
        FROM ranked_data
        WHERE prev_ranking IS NOT NULL 
        AND ABS(prev_ranking - ranking) > 5
        ORDER BY ABS(prev_ranking - ranking) DESC
        LIMIT 10
        """
        
        try:
            ranking_changes = await db_manager.execute_query(ranking_query)
            
            if ranking_changes:
                logger.info("\n=== Significant Ranking Changes (Last 24h) ===")
                for row in ranking_changes:
                    change = row[4]
                    direction = "↑" if change > 0 else "↓"
                    logger.info(f"{row[0]} ({row[1]}): {row[3]} → {row[2]} ({direction}{abs(change)})")
            else:
                logger.info("\n=== No significant ranking changes in last 24h ===")
        except Exception as e:
            logger.warning(f"Could not analyze ranking changes: {e}")
        
        # 5. Price change analysis
        price_change_query = """
        SELECT 
            source,
            AVG(CAST(price_change_5m AS FLOAT)) as avg_5m_change,
            AVG(CAST(price_change_1h AS FLOAT)) as avg_1h_change,
            AVG(CAST(price_change_6h AS FLOAT)) as avg_6h_change,
            AVG(CAST(price_change_24h AS FLOAT)) as avg_24h_change
        FROM enhanced_watchlist_history
        WHERE price_change_5m IS NOT NULL 
        AND price_change_1h IS NOT NULL
        AND price_change_6h IS NOT NULL
        AND price_change_24h IS NOT NULL
        GROUP BY source
        ORDER BY source
        """
        
        price_changes = await db_manager.execute_query(price_change_query)
        
        logger.info("\n=== Average Price Changes by Source ===")
        for row in price_changes:
            logger.info(f"Source: {row[0]}")
            logger.info(f"  5m: {row[1]:.2f}%" if row[1] else "  5m: N/A")
            logger.info(f"  1h: {row[2]:.2f}%" if row[2] else "  1h: N/A")
            logger.info(f"  6h: {row[3]:.2f}%" if row[3] else "  6h: N/A")
            logger.info(f"  24h: {row[4]:.2f}%" if row[4] else "  24h: N/A")
        
        # 6. Data collection timeline
        timeline_query = """
        SELECT 
            DATE_TRUNC('hour', collected_at) as collection_hour,
            COUNT(*) as entries_collected,
            COUNT(DISTINCT source) as sources_active
        FROM enhanced_watchlist_history
        WHERE collected_at >= NOW() - INTERVAL '7 days'
        GROUP BY DATE_TRUNC('hour', collected_at)
        ORDER BY collection_hour DESC
        LIMIT 24
        """
        
        try:
            timeline = await db_manager.execute_query(timeline_query)
            
            logger.info("\n=== Collection Timeline (Last 24 Hours) ===")
            for row in timeline:
                logger.info(f"{row[0]}: {row[1]} entries from {row[2]} sources")
        except Exception as e:
            logger.warning(f"Could not analyze collection timeline: {e}")
            
    except Exception as e:
        logger.error(f"Historical data analysis failed: {e}", exc_info=True)


async def generate_source_report(db_manager, source: str):
    """Generate a detailed report for a specific source."""
    
    logger.info(f"\n=== Detailed Report for Source: {source.upper()} ===")
    
    try:
        # Source-specific statistics
        source_stats_query = """
        SELECT 
            COUNT(*) as total_entries,
            COUNT(DISTINCT token_symbol) as unique_tokens,
            MIN(collected_at) as earliest_data,
            MAX(collected_at) as latest_data,
            AVG(CAST(market_cap AS FLOAT)) as avg_market_cap,
            AVG(CAST(liquidity AS FLOAT)) as avg_liquidity,
            AVG(CAST(volume AS FLOAT)) as avg_volume
        FROM enhanced_watchlist_history
        WHERE source = %s
        """
        
        stats = await db_manager.execute_query(source_stats_query, (source,))
        
        if stats and stats[0][0] > 0:
            row = stats[0]
            logger.info(f"Total Entries: {row[0]:,}")
            logger.info(f"Unique Tokens: {row[1]:,}")
            logger.info(f"Data Range: {row[2]} to {row[3]}")
            logger.info(f"Avg Market Cap: ${row[4]:,.2f}" if row[4] else "Avg Market Cap: N/A")
            logger.info(f"Avg Liquidity: ${row[5]:,.2f}" if row[5] else "Avg Liquidity: N/A")
            logger.info(f"Avg Volume: ${row[6]:,.2f}" if row[6] else "Avg Volume: N/A")
            
            # Top tokens in this source
            top_tokens_query = """
            SELECT 
                token_symbol,
                token_name,
                AVG(ranking) as avg_ranking,
                COUNT(*) as appearances,
                MAX(CAST(market_cap AS FLOAT)) as max_market_cap
            FROM enhanced_watchlist_history
            WHERE source = %s
            GROUP BY token_symbol, token_name
            ORDER BY avg_ranking ASC
            LIMIT 10
            """
            
            top_tokens = await db_manager.execute_query(top_tokens_query, (source,))
            
            logger.info(f"\nTop 10 Tokens in {source.upper()} (by avg ranking):")
            for i, row in enumerate(top_tokens, 1):
                logger.info(f"{i}. {row[0]} ({row[1]})")
                logger.info(f"   Avg Ranking: {row[2]:.1f}, Appearances: {row[3]}")
                logger.info(f"   Max Market Cap: ${row[4]:,.2f}" if row[4] else "   Max Market Cap: N/A")
        else:
            logger.info(f"No data found for source: {source}")
            
    except Exception as e:
        logger.error(f"Source report generation failed for {source}: {e}")


async def main():
    """Main demo function."""
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Run historical data analysis
        await analyze_historical_data(db_manager)
        
        # Generate reports for specific sources
        sources = ['reference', 'lowcap', 'micro', 'midcap']
        for source in sources:
            await generate_source_report(db_manager, source)
        
        logger.info("\n=== Enhanced Watchlist Historical Data Demo Completed ===")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())