#!/usr/bin/env python3
"""
API Usage Calculator for GeckoTerminal Free API.

This script helps calculate safe API usage patterns and estimate
collection times within the free tier rate limits.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.performance_config import calculate_safe_api_usage, estimate_collection_time


def main():
    """Main entry point for the API usage calculator."""
    parser = argparse.ArgumentParser(
        description="Calculate safe API usage patterns for GeckoTerminal Free API"
    )
    
    parser.add_argument(
        '--pools', 
        type=int, 
        default=100,
        help='Number of pools to collect data for (default: 100)'
    )
    
    parser.add_argument(
        '--data-points', 
        type=int, 
        default=3,
        help='API calls needed per pool (default: 3 for OHLCV + trades + metadata)'
    )
    
    parser.add_argument(
        '--safety-margin', 
        type=float, 
        default=0.2,
        help='Safety margin as decimal (default: 0.2 for 20% buffer)'
    )
    
    parser.add_argument(
        '--rate-limit', 
        type=int, 
        default=30,
        help='API calls per minute limit (default: 30 for free tier)'
    )
    
    parser.add_argument(
        '--monthly-limit', 
        type=int, 
        default=10000,
        help='Monthly API call limit (default: 10000 for free tier)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("GECKOTERMINAL API USAGE CALCULATOR")
    print("=" * 60)
    
    # Calculate safe usage patterns
    safe_usage = calculate_safe_api_usage(
        calls_per_minute=args.rate_limit,
        monthly_limit=args.monthly_limit,
        safety_margin=args.safety_margin
    )
    
    print("\nSAFE USAGE RECOMMENDATIONS:")
    print("-" * 30)
    print(f"Safe calls per minute: {safe_usage['safe_calls_per_minute']}")
    print(f"Safe calls per hour: {safe_usage['safe_calls_per_hour']}")
    print(f"Safe calls per day: {safe_usage['safe_calls_per_day']}")
    print(f"Safe calls per month: {safe_usage['safe_calls_per_month']}")
    print(f"Recommended batch size: {safe_usage['recommended_batch_size']}")
    print(f"Delay between batches: {safe_usage['recommended_delay_between_batches']} seconds")
    
    # Estimate collection time
    collection_estimate = estimate_collection_time(
        pools_to_collect=args.pools,
        data_points_per_pool=args.data_points,
        calls_per_minute=safe_usage['safe_calls_per_minute']
    )
    
    print(f"\nCOLLECTION TIME ESTIMATE:")
    print("-" * 30)
    print(f"Pools to collect: {args.pools}")
    print(f"Data points per pool: {args.data_points}")
    print(f"Total API calls needed: {collection_estimate['total_api_calls_needed']}")
    print(f"Estimated time: {collection_estimate['estimated_minutes']:.1f} minutes ({collection_estimate['estimated_hours']:.2f} hours)")
    print(f"Batches required: {collection_estimate['batches_required']}")
    print(f"Calls per batch: {collection_estimate['calls_per_batch']}")
    
    # Monthly usage analysis
    monthly_usage_percent = (collection_estimate['total_api_calls_needed'] / safe_usage['safe_calls_per_month']) * 100
    
    print(f"\nMONTHLY USAGE ANALYSIS:")
    print("-" * 30)
    print(f"Single collection uses: {monthly_usage_percent:.1f}% of monthly quota")
    
    if monthly_usage_percent <= 100:
        max_collections_per_month = int(100 / monthly_usage_percent)
        print(f"Maximum collections per month: {max_collections_per_month}")
        
        if max_collections_per_month >= 30:
            print("✓ Can collect daily")
        elif max_collections_per_month >= 4:
            print(f"✓ Can collect weekly ({max_collections_per_month} times per month)")
        else:
            print(f"⚠ Limited to {max_collections_per_month} collections per month")
    else:
        print("❌ Single collection exceeds monthly quota!")
        print("   Consider reducing pools or upgrading to paid plan")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    print("-" * 30)
    
    if collection_estimate['estimated_hours'] > 1:
        print("⚠ Collection takes over 1 hour - consider:")
        print("  - Reducing number of pools")
        print("  - Collecting in smaller batches")
        print("  - Upgrading to paid API plan")
    
    if monthly_usage_percent > 80:
        print("⚠ High monthly usage - consider:")
        print("  - Reducing collection frequency")
        print("  - Implementing smart caching")
        print("  - Upgrading to paid API plan")
    
    if collection_estimate['batches_required'] > 10:
        print("⚠ Many batches required - consider:")
        print("  - Implementing queue-based collection")
        print("  - Adding retry logic with exponential backoff")
        print("  - Monitoring API usage in real-time")
    
    print("\nFor optimal performance:")
    print("- Implement exponential backoff for rate limiting")
    print("- Use connection pooling and keep-alive")
    print("- Cache frequently accessed data")
    print("- Monitor API usage to avoid hitting limits")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()