-- Database indexes for optimized address resolution
-- These indexes dramatically improve lazy loading performance

-- Pool addresses (case-insensitive lookup)
CREATE INDEX IF NOT EXISTS idx_pools_address_lower 
ON pools (LOWER(address));

-- New pools history addresses (case-insensitive lookup)
CREATE INDEX IF NOT EXISTS idx_new_pools_history_address_lower 
ON new_pools_history (LOWER(address));

-- Token addresses (case-insensitive lookup)
CREATE INDEX IF NOT EXISTS idx_tokens_address_lower 
ON tokens (LOWER(address));

-- Additional useful indexes for filtered queries

-- Pool last_updated for date filtering
CREATE INDEX IF NOT EXISTS idx_pools_last_updated 
ON pools (last_updated);

-- Token last_updated for date filtering
CREATE INDEX IF NOT EXISTS idx_tokens_last_updated 
ON tokens (last_updated);

-- New pools history collected_at for date filtering
CREATE INDEX IF NOT EXISTS idx_new_pools_history_collected_at 
ON new_pools_history (collected_at);

-- New pools history network_id for network filtering
CREATE INDEX IF NOT EXISTS idx_new_pools_history_network_id 
ON new_pools_history (network_id);

-- Token network for network filtering
CREATE INDEX IF NOT EXISTS idx_tokens_network 
ON tokens (network);

-- Verify indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename IN ('pools', 'new_pools_history', 'tokens')
    AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;
