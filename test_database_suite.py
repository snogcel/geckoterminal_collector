#!/usr/bin/env python3
"""
Comprehensive Database Test Suite for Gecko Terminal Collector

This test suite validates all database operations, models, and constraints
to ensure data integrity and proper functionality.
"""

import asyncio
import uuid
import yaml
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.models.core import Pool, Token


class DatabaseTestSuite:
    """Comprehensive database testing suite."""
    
    def __init__(self):
        self.db_manager = None
        self.test_data = {}
        self.cleanup_pools = []
        self.cleanup_watchlist = []
    
    async def setup(self):
        """Initialize database connection and create test data."""
        print("🔧 Setting up database test suite...")
        
        # Load config
        with open('config.yaml', 'r') as f:
            config_dict = yaml.safe_load(f)
        
        # Initialize database manager
        db_config = DatabaseConfig(**config_dict['database'])
        self.db_manager = SQLAlchemyDatabaseManager(db_config)
        await self.db_manager.initialize()
        
        # Generate unique test identifiers
        test_suffix = str(uuid.uuid4())[:8]
        self.test_data = {
            'dex_id': f'test_dex_{test_suffix}',
            'token_base_id': f'solana_test_base_{test_suffix}',
            'token_quote_id': f'solana_test_quote_{test_suffix}',
            'pool_id': f'test_pool_{test_suffix}',
        }
        
        print(f"✅ Database test suite initialized with suffix: {test_suffix}")
    
    async def cleanup(self):
        """Clean up test data and close database connection."""
        print("\n🧹 Cleaning up test data...")
        
        try:
            # Clean up watchlist entries
            for pool_id in self.cleanup_watchlist:
                try:
                    await self.db_manager.remove_watchlist_entry(pool_id)
                except Exception as e:
                    print(f"   Warning: Could not remove watchlist entry {pool_id}: {e}")
            
            print("✅ Test data cleaned up successfully")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
        finally:
            if self.db_manager:
                await self.db_manager.close()
    
    async def test_database_connection(self) -> bool:
        """Test basic database connectivity."""
        print("\n🔌 Testing database connection...")
        
        try:
            # Test by getting all watchlist entries (simple query)
            entries = await self.db_manager.get_all_watchlist_entries()
            assert isinstance(entries, list)
            
            print("✅ Database connection successful")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    async def test_pool_operations(self) -> bool:
        """Test Pool model operations."""
        print("\n🏊 Testing Pool operations...")
        
        try:
            # Create test pool using the core Pool model
            pool = Pool(
                id=self.test_data['pool_id'],
                address=f'pool_address_{uuid.uuid4().hex[:8]}',
                name='TBT/TQT Pool',
                dex_id=self.test_data['dex_id'],
                base_token_id=self.test_data['token_base_id'],
                quote_token_id=self.test_data['token_quote_id'],
                reserve_usd=Decimal('10000.50'),
                created_at=datetime.utcnow()
            )
            
            # Store pool
            await self.db_manager.store_pools([pool])
            self.cleanup_pools.append(pool.id)
            
            # Retrieve pool
            retrieved_pool = await self.db_manager.get_pool(pool.id)
            assert retrieved_pool is not None
            assert retrieved_pool.name == pool.name
            assert retrieved_pool.dex_id == pool.dex_id
            
            print("✅ Pool operations successful")
            return True
        except Exception as e:
            print(f"❌ Pool operations failed: {e}")
            return False
    
    async def test_token_operations(self) -> bool:
        """Test Token model operations."""
        print("\n🪙 Testing Token operations...")
        
        try:
            # Create test tokens using the core Token model
            base_token = Token(
                id=self.test_data['token_base_id'],
                address=f'base_address_{uuid.uuid4().hex[:8]}',
                name='Test Base Token',
                symbol='TBT',
                decimals=9,
                network='solana'
            )
            
            quote_token = Token(
                id=self.test_data['token_quote_id'],
                address=f'quote_address_{uuid.uuid4().hex[:8]}',
                name='Test Quote Token',
                symbol='TQT',
                decimals=6,
                network='solana'
            )
            
            # Store tokens
            await self.db_manager.store_tokens([base_token, quote_token])
            
            # Retrieve tokens (note: get_token requires pool_id and token_id)
            retrieved_base = await self.db_manager.get_token_by_id(base_token.id)
            retrieved_quote = await self.db_manager.get_token_by_id(quote_token.id)
            
            assert retrieved_base is not None
            assert retrieved_base.symbol == 'TBT'
            assert retrieved_quote is not None
            assert retrieved_quote.symbol == 'TQT'
            
            print("✅ Token operations successful")
            return True
        except Exception as e:
            print(f"❌ Token operations failed: {e}")
            return False
    
    async def test_watchlist_operations(self) -> bool:
        """Test Watchlist model operations."""
        print("\n👀 Testing Watchlist operations...")
        
        try:
            # Add to watchlist using the correct method signature
            watchlist_data = {
                'pool_id': self.test_data['pool_id'],
                'token_symbol': 'TBT',
                'token_name': 'Test Base Token',
                'network_address': f'watch_address_{uuid.uuid4().hex[:8]}',
                'is_active': True
            }
            
            # Use the correct method name and signature
            await self.db_manager.add_to_watchlist(watchlist_data)
            self.cleanup_watchlist.append(watchlist_data['pool_id'])
            
            # Check if pool is in watchlist
            is_in_watchlist = await self.db_manager.is_pool_in_watchlist(watchlist_data['pool_id'])
            assert is_in_watchlist is True
            
            # Get all watchlist entries
            all_entries = await self.db_manager.get_all_watchlist_entries()
            test_entries = [e for e in all_entries if e.pool_id == watchlist_data['pool_id']]
            assert len(test_entries) == 1
            assert test_entries[0].token_symbol == watchlist_data['token_symbol']
            
            # Get active watchlist entries
            active_entries = await self.db_manager.get_active_watchlist_entries()
            test_active = [e for e in active_entries if e.pool_id == watchlist_data['pool_id']]
            assert len(test_active) == 1
            
            # Update watchlist entry status
            await self.db_manager.update_watchlist_entry_status(
                watchlist_data['pool_id'], 
                is_active=False
            )
            
            # Verify update
            updated_entries = await self.db_manager.get_active_watchlist_entries()
            test_updated = [e for e in updated_entries if e.pool_id == watchlist_data['pool_id']]
            assert len(test_updated) == 0  # Should be empty since we deactivated it
            
            print("✅ Watchlist operations successful")
            return True
        except Exception as e:
            print(f"❌ Watchlist operations failed: {e}")
            return False
    
    async def test_data_integrity_checks(self) -> bool:
        """Test data integrity and statistics methods."""
        print("\n🔍 Testing data integrity checks...")
        
        try:
            # Test data integrity check
            integrity_report = await self.db_manager.check_data_integrity(self.test_data['pool_id'])
            assert isinstance(integrity_report, dict)
            
            # Test data statistics
            stats = await self.db_manager.get_data_statistics(self.test_data['pool_id'])
            assert isinstance(stats, dict)
            
            # Test record count for watchlist table (we know this exists)
            count = await self.db_manager.count_records('watchlist')
            assert isinstance(count, int)
            assert count >= 0
            
            print("✅ Data integrity checks successful")
            return True
        except Exception as e:
            print(f"❌ Data integrity checks failed: {e}")
            return False
    
    async def test_collection_metadata(self) -> bool:
        """Test collection metadata operations."""
        print("\n📋 Testing collection metadata...")
        
        try:
            collector_type = f'test_collector_{uuid.uuid4().hex[:8]}'
            
            # Update collection metadata with correct signature
            await self.db_manager.update_collection_metadata(
                collector_type=collector_type,
                last_run=datetime.utcnow(),
                success=True,
                error_message=None
            )
            
            # Get collection metadata
            metadata = await self.db_manager.get_collection_metadata(collector_type)
            assert metadata is not None
            assert metadata['run_count'] >= 1
            
            print("✅ Collection metadata operations successful")
            return True
        except Exception as e:
            print(f"❌ Collection metadata operations failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all database tests and return results."""
        print("🚀 Starting Comprehensive Database Test Suite")
        print("=" * 60)
        
        test_results = {}
        
        # List of all tests to run
        tests = [
            ('Database Connection', self.test_database_connection),
            ('Token Operations', self.test_token_operations),
            ('Pool Operations', self.test_pool_operations),
            ('Watchlist Operations', self.test_watchlist_operations),
            ('Data Integrity Checks', self.test_data_integrity_checks),
            ('Collection Metadata', self.test_collection_metadata),
        ]
        
        # Run each test
        for test_name, test_func in tests:
            try:
                result = await test_func()
                test_results[test_name] = result
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                test_results[test_name] = False
        
        return test_results
    
    def print_summary(self, results: Dict[str, bool]):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("📊 Database Test Suite Summary")
        print("=" * 60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:<10} {test_name}")
        
        print("-" * 60)
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Database is functioning correctly.")
        else:
            print("⚠️  Some tests failed. Please review the output above.")
        
        return passed == total


async def main():
    """Main test runner."""
    suite = DatabaseTestSuite()
    
    try:
        await suite.setup()
        results = await suite.run_all_tests()
        success = suite.print_summary(results)
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Test suite setup failed: {e}")
        return 1
    finally:
        await suite.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)