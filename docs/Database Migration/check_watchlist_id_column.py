#!/usr/bin/env python3

import psycopg2

def check_watchlist_id_column():
    # Database connection details from config.yaml
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="gecko_terminal_collector",
        user="gecko_collector",
        password="12345678!"
    )
    
    cur = conn.cursor()
    
    # Check if the id column has a sequence
    cur.execute("""
        SELECT column_name, column_default, is_nullable, data_type
        FROM information_schema.columns 
        WHERE table_name = 'watchlist' AND column_name = 'id';
    """)
    id_info = cur.fetchone()
    print(f"ID column info: {id_info}")
    
    # Check for sequences
    cur.execute("""
        SELECT sequence_name, data_type, start_value, increment
        FROM information_schema.sequences 
        WHERE sequence_name LIKE '%watchlist%';
    """)
    sequences = cur.fetchall()
    print(f"Watchlist sequences: {sequences}")
    
    # Check table constraints
    cur.execute("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints 
        WHERE table_name = 'watchlist';
    """)
    constraints = cur.fetchall()
    print(f"Watchlist constraints: {constraints}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_watchlist_id_column()