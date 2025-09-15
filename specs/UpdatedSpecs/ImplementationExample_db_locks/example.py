

## Database Lock Issue

""" 2025-09-15 07:11:35,409 - __main__ - INFO - Received signal 2, initiating shutdown...

2025-09-15 07:11:35,409 - gecko_terminal_collector.database.sqlalchemy_manager - ERROR - Error storing pool solana_5cNNQs6GVERLJHMHNNDEqhogGBNdz9u26RKTL3gmJBwX: (sqlite3.OperationalError) database is locked
[SQL: INSERT INTO pools (id, address, name, dex_id, base_token_id, quote_token_id, reserve_usd, created_at, last_updated, activity_score, discovery_source, collection_priority, auto_discovered_at, last_activity_check) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)]
[parameters: ('solana_5cNNQs6GVERLJHMHNNDEqhogGBNdz9u26RKTL3gmJBwX', '', '', '', '', '', 0.0, None, '2025-09-15 07:11:01.593261', None, 'auto', 'normal', None, None)]
(Background on this error at: https://sqlalche.me/e/20/e3q8)

2025-09-15 07:11:35,409 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error ensuring pool exists for solana_5cNNQs6GVERLJHMHNNDEqhogGBNdz9u26RKTL3gmJBwX: (sqlite3.OperationalError) database is locked
[SQL: INSERT INTO pools (id, address, name, dex_id, base_token_id, quote_token_id, reserve_usd, created_at, last_updated, activity_score, discovery_source, collection_priority, auto_discovered_at, last_activity_check) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)]
[parameters: ('solana_5cNNQs6GVERLJHMHNNDEqhogGBNdz9u26RKTL3gmJBwX', '', '', '', '', '', 0.0, None, '2025-09-15 07:11:01.593261', None, 'auto', 'normal', None, None)] """

# Example implementation of bulk storage method implemented to Trade Operation storage:

# Trade operations
async def store_trade_data(self, data: List[TradeRecord]) -> int:
    """
    Store trade data with enhanced duplicate prevention.
    
    Uses primary key constraints and additional validation to prevent
    duplicate trades while handling edge cases gracefully.
    """
    if not data:
        return 0
    
    stored_count = 0
    duplicate_count = 0

    print("-store_trade_data--")

    with self.connection.get_session() as session:
        try:
            # Validate and deduplicate input data
            validated_data = []
            seen_ids = set()

            # optimized method
            
            
            ids_to_check = []                

            #existing_ids = session.query(TradeModel.id).filter(TradeModel.id.in_(ids_to_check)).all()
            #existing_ids_set = {id_tuple[0] for id_tuple in existing_ids}
            
            for record in data:
                ids_to_check.append(record.id)
            
            existing_ids = session.query(TradeModel.id).filter(TradeModel.id.in_(ids_to_check)).all()
            existing_ids_set = {id_tuple[0] for id_tuple in existing_ids}
            non_existent_ids = [id_val for id_val in ids_to_check if id_val not in existing_ids_set]

            unique_records = []
            for record in data:
                if record.id in non_existent_ids:
                    unique_records.append(record)
            
            print("-unique_records:")
            for record in unique_records:
                print(record.id)
                
                # Validate trade data
                validation_errors = self._validate_trade_record(record)
                if validation_errors:
                    logger.warning(f"Skipping invalid trade record {record.id}: {validation_errors}")
                    continue
                
                # append network prefix to record.pool_id -- this fun pattern is everywhere!
                prefix, _, _ = record.id.partition('_')                    
                pool_id_with_prefix = prefix + '_' + record.pool_id

                #print("---")
                #print(pool_id_with_prefix)
                #print("---")

                new_trade = TradeModel(
                            id=record.id,
                            pool_id=pool_id_with_prefix,
                            block_number=record.block_number,
                            tx_hash=record.tx_hash,
                            tx_from_address=record.tx_from_address,
                            from_token_amount=record.from_token_amount,
                            to_token_amount=record.to_token_amount,
                            price_usd=record.price_usd,
                            volume_usd=record.volume_usd,
                            side=record.side,
                            block_timestamp=record.block_timestamp,
                        )

                validated_data.append(new_trade)

            stored_count = len(validated_data) #non_existent_ids
            duplicate_count = len(existing_ids) #existing_ids

            session.bulk_save_objects(validated_data)
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing trade data: {e}")
            raise
            
    return stored_count
