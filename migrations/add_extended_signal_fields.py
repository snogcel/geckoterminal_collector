"""
Migration: add extended signal fields to new_pools_history.

New columns
-----------
rf_score        NUMERIC(6,2)   RF win-probability * 100 (0-100)
rf_tier         SMALLINT       0=FILTER, 1=HIGH, 2=MEDIUM, 3=LOW
fdv_liq_ratio   NUMERIC(10,4)  FDV / liquidity ratio
vol_velocity    NUMERIC(10,4)  Volume growth multiplier vs first observation
sell_authentic  BOOLEAN        False = zero-sell / bot pattern detected
buy_ratio_1h    NUMERIC(6,4)   Fraction of 1h transactions that are buys
signals_json    TEXT / JSONB   Full signals dict for debugging / retraining

Run against PostgreSQL
----------------------
    python migrations/add_extended_signal_fields.py

Run against SQLite (pass db path as argument)
---------------------------------------------
    python migrations/add_extended_signal_fields.py gecko_data.db
"""

import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is on sys.path so gecko_terminal_collector is importable
# when running the script directly (e.g. python migrations/add_extended_signal_fields.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLite migration (no asyncio needed)
# ---------------------------------------------------------------------------

SQLITE_COLUMNS = [
    ("rf_score",       "NUMERIC(6,2)"),
    ("rf_tier",        "INTEGER"),
    ("fdv_liq_ratio",  "NUMERIC(10,4)"),
    ("vol_velocity",   "NUMERIC(10,4)"),
    ("sell_authentic", "BOOLEAN"),
    ("buy_ratio_1h",   "NUMERIC(6,4)"),
    ("signals_json",   "TEXT"),
]

SQLITE_INDEXES = [
    ("idx_new_pools_history_rf_tier",  "rf_tier"),
    ("idx_new_pools_history_rf_score", "rf_score"),
]


def migrate_sqlite(db_path: str) -> bool:
    print(f"Migrating SQLite database: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='new_pools_history'"
        )
        if not cur.fetchone():
            print("Table 'new_pools_history' does not exist — nothing to migrate.")
            conn.close()
            return False

        cur.execute("PRAGMA table_info(new_pools_history)")
        existing = {row[1] for row in cur.fetchall()}

        added = 0
        for col, col_type in SQLITE_COLUMNS:
            if col not in existing:
                cur.execute(f"ALTER TABLE new_pools_history ADD COLUMN {col} {col_type}")
                print(f"  + {col} {col_type}")
                added += 1
            else:
                print(f"  ✓ {col} already exists")

        for idx_name, col in SQLITE_INDEXES:
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON new_pools_history ({col})"
            )
            print(f"  ✓ index {idx_name}")

        conn.commit()
        conn.close()
        print(f"Done — {added} column(s) added.")
        return True

    except sqlite3.Error as exc:
        print(f"SQLite migration failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# PostgreSQL migration
# ---------------------------------------------------------------------------

PG_COLUMNS = [
    ("rf_score",       "NUMERIC(6,2)"),
    ("rf_tier",        "SMALLINT"),
    ("fdv_liq_ratio",  "NUMERIC(10,4)"),
    ("vol_velocity",   "NUMERIC(10,4)"),
    ("sell_authentic", "BOOLEAN"),
    ("buy_ratio_1h",   "NUMERIC(6,4)"),
    ("signals_json",   "JSONB"),
]

PG_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_new_pools_history_rf_tier ON new_pools_history (rf_tier);",
    "CREATE INDEX IF NOT EXISTS idx_new_pools_history_rf_score ON new_pools_history (rf_score DESC NULLS LAST);",
]


async def migrate_postgresql() -> bool:
    try:
        from sqlalchemy import text
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

        config = ConfigManager("config.yaml").load_config()
        db = SQLAlchemyDatabaseManager(config.database)
        await db.initialize()

        print("Migrating PostgreSQL database…")

        statements = []
        for col, col_type in PG_COLUMNS:
            statements.append(
                f"ALTER TABLE new_pools_history ADD COLUMN IF NOT EXISTS {col} {col_type};"
            )
        statements.extend(PG_INDEXES)

        with db.connection.get_session() as session:
            for stmt in statements:
                print(f"  {stmt.strip()}")
                session.execute(text(stmt))
            session.commit()

        await db.close()
        print("PostgreSQL migration complete.")
        return True

    except Exception as exc:
        print(f"PostgreSQL migration failed: {exc}")
        logger.exception("PostgreSQL migration error")
        return False


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
        # Treat first argument as SQLite db path
        success = migrate_sqlite(sys.argv[1])
    else:
        # Auto-detect SQLite databases in common locations, else try PostgreSQL
        candidates = ["gecko_data.db", "data/gecko_data.db"]
        db_found = next((p for p in candidates if Path(p).exists()), None)

        if db_found:
            success = migrate_sqlite(db_found)
        else:
            success = asyncio.run(migrate_postgresql())

    sys.exit(0 if success else 1)
