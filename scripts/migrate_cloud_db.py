#!/usr/bin/env python3
"""
Vadi-Pehn Cloud Database Migration Runner
Connects to Supabase Cloud PostgreSQL instances (`vadi_memory` & `vadi_governance`)
and applies all initial schemas, RLS policies, vector extensions, and governance tables.
"""

import asyncio
import os
import sys
import asyncpg

# Ensure root dir is in path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from services.config import settings

MEMORY_MIGRATIONS = [
    "001_identity_and_tenancy.sql",
    "002_learner_memory_rls.sql",
    "003_rapport_and_panel.sql",
    "005_ingestion_schema.sql",
    "006_identity_rls.sql",
]

GOVERNANCE_MIGRATIONS = [
    "004_governance_schema.sql",
]


async def run_migrations() -> None:
    print("=" * 70)
    print("VADI-PEHN CLOUD DATABASE MIGRATION EXECUTION")
    print("=" * 70)

    # 1. Memory DB Migration
    mem_dsn = settings.memory_db.dsn
    print(f"\n[1/2] Connecting to Memory DB: {settings.memory_db.name}...")
    try:
        mem_conn = await asyncpg.connect(mem_dsn)
        print("  Connected successfully! Enabling vector and crypto extensions...")
        await mem_conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
            """
        )
        for migration in MEMORY_MIGRATIONS:
            m_path = os.path.join(ROOT_DIR, "db", "migrations", migration)
            print(f"  Executing {migration}...")
            sql_content = open(m_path, "r", encoding="utf-8").read()
            # Execute inside transaction
            async with mem_conn.transaction():
                await mem_conn.execute(sql_content)

        # Check created tables
        tables = await mem_conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
        )
        t_list = [t["tablename"] for t in tables]
        print(f"  -> Memory DB Tables created: {t_list}")
        await mem_conn.close()
    except Exception as e:
        print(f"  [ERROR] Memory DB migration failed: {e}")
        raise

    # 2. Governance DB Migration
    gov_dsn = settings.governance_db.dsn
    print(f"\n[2/2] Connecting to Governance DB: {settings.governance_db.name}...")
    try:
        gov_conn = await asyncpg.connect(gov_dsn)
        print("  Connected successfully! Enabling crypto extensions...")
        await gov_conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
            """
        )
        for migration in GOVERNANCE_MIGRATIONS:
            m_path = os.path.join(ROOT_DIR, "db", "migrations", migration)
            print(f"  Executing {migration}...")
            sql_content = open(m_path, "r", encoding="utf-8").read()
            async with gov_conn.transaction():
                await gov_conn.execute(sql_content)

        tables = await gov_conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
        )
        t_list = [t["tablename"] for t in tables]
        print(f"  -> Governance DB Tables created: {t_list}")
        await gov_conn.close()
    except Exception as e:
        print(f"  [ERROR] Governance DB migration failed: {e}")
        raise

    print("\n" + "=" * 70)
    print("ALL CLOUD DATABASE MIGRATIONS COMPLETED SUCCESSFULLY! [SUCCESS]")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_migrations())
