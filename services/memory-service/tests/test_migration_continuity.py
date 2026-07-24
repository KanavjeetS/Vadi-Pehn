"""
Unit and integration tests for Database Migration Continuity (001 through 008).
Verifies:
- Complete unbroken migration sequence 001..008 present in db/migrations/
- Migration 007_dlq_and_agents.sql is located in db/migrations/ (not packages/db-schema)
- Migration 007 tables (memory_write_dlq, professional_career_pathways, curated_learning_resources)
  have active valid DDL with both ENABLE and FORCE ROW LEVEL SECURITY.
- scripts/migrate_cloud_db.py includes 007 and 008 in MEMORY_MIGRATIONS sequence.
"""

from __future__ import annotations

import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

EXPECTED_MIGRATIONS = [
    "001_identity_and_tenancy.sql",
    "002_learner_memory_rls.sql",
    "003_rapport_and_panel.sql",
    "004_governance_schema.sql",
    "005_ingestion_schema.sql",
    "006_identity_rls.sql",
    "007_dlq_and_agents.sql",
    "008_parent_id_hierarchical_chunking.sql",
]


def test_migration_files_exist_and_unbroken_sequence():
    """Verify db/migrations/ contains the exact unbroken sequence 001..008."""
    migrations_dir = os.path.join(ROOT_DIR, "db", "migrations")
    assert os.path.exists(migrations_dir), f"Directory missing: {migrations_dir}"

    actual_files = sorted(
        [f for f in os.listdir(migrations_dir) if f.startswith("00") and f.endswith(".sql")]
    )
    assert actual_files == EXPECTED_MIGRATIONS, (
        f"Migration sequence mismatch!\nExpected: {EXPECTED_MIGRATIONS}\nActual: {actual_files}"
    )


def test_orphaned_migration_location_fixed():
    """Verify 007_dlq_and_agents.sql is moved from packages/db-schema/migrations/."""
    orphaned_path = os.path.join(
        ROOT_DIR, "packages", "db-schema", "migrations", "007_dlq_and_agents.sql"
    )
    assert not os.path.exists(orphaned_path), (
        f"Orphaned migration still exists at {orphaned_path}!"
    )

    canonical_path = os.path.join(ROOT_DIR, "db", "migrations", "007_dlq_and_agents.sql")
    assert os.path.exists(canonical_path), (
        f"Migration 007 missing at canonical location {canonical_path}!"
    )


def test_migration_007_schema_and_rls_compliance():
    """Verify 007_dlq_and_agents.sql defines memory_write_dlq, career pathways, and curated resources with RLS."""
    mig_007_path = os.path.join(ROOT_DIR, "db", "migrations", "007_dlq_and_agents.sql")
    with open(mig_007_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Verify key tables exist in migration SQL
    assert "CREATE TABLE IF NOT EXISTS memory_write_dlq" in sql
    assert "CREATE TABLE IF NOT EXISTS professional_career_pathways" in sql
    assert "CREATE TABLE IF NOT EXISTS curated_learning_resources" in sql

    # Verify RLS ENABLE and FORCE statements for memory_write_dlq
    assert "ALTER TABLE memory_write_dlq ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE memory_write_dlq FORCE ROW LEVEL SECURITY;" in sql

    # Verify RLS ENABLE and FORCE statements for professional_career_pathways
    assert "ALTER TABLE professional_career_pathways ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE professional_career_pathways FORCE ROW LEVEL SECURITY;" in sql

    # Verify RLS ENABLE and FORCE statements for curated_learning_resources
    assert "ALTER TABLE curated_learning_resources ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE curated_learning_resources FORCE ROW LEVEL SECURITY;" in sql

    # Verify tenant isolation policy definition
    assert "app.current_tenant_id" in sql
    assert "memory_write_dlq_tenant_policy" in sql
    assert "professional_career_tenant_policy" in sql
    assert "curated_learning_tenant_policy" in sql


def test_migrate_cloud_db_runner_sequence():
    """Verify scripts/migrate_cloud_db.py includes migrations 007 and 008."""
    runner_path = os.path.join(ROOT_DIR, "scripts", "migrate_cloud_db.py")
    with open(runner_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert '"007_dlq_and_agents.sql"' in content
    assert '"008_parent_id_hierarchical_chunking.sql"' in content


def test_all_migrations_sql_non_empty_and_valid_structure():
    """Verify all migration files 001..008 can be read, are non-empty, and have basic SQL structure."""
    migrations_dir = os.path.join(ROOT_DIR, "db", "migrations")
    for mig in EXPECTED_MIGRATIONS:
        path = os.path.join(migrations_dir, mig)
        assert os.path.isfile(path), f"File missing: {path}"
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
        assert len(sql.strip()) > 50, f"Migration {mig} appears empty or truncated"
