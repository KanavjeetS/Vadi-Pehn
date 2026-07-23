"""
Startup Synthetic Data Seeding for Vadi-Pehn Platform.
Implements: PRD §3.1-3.4, SD §3.1-3.4 (Requirement R4).

Seeds PRD-compliant synthetic test data:
  - Default Tenant:    00000000-0000-0000-0000-000000000001
  - Default Guardian:  00000000-0000-0000-0000-000000000002
  - Default Learner:   00000000-0000-0000-0000-000000000003 ('Aria', age_band=2)
  - Synthetic 1536-dim vector memories & interest profile
  - Active consent records (conversation_storage, document_ingestion, voice_recording, career_introductions)
  - Safety incident queue with 15-minute SLA tracking (sla_deadline)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg

# Resolve root service paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.config import settings

logger = logging.getLogger("seed_synthetic_data")

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_GUARDIAN_ID = UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_LEARNER_ID = UUID("00000000-0000-0000-0000-000000000003")


def generate_synthetic_embedding(dim: int = 1536, seed_val: float = 0.01) -> list[float]:
    """Generates synthetic 1536-dimensional normalized vector embedding."""
    raw = [(seed_val + (i % 100) * 0.001) for i in range(dim)]
    norm = sum(x * x for x in raw) ** 0.5
    return [x / norm for x in raw]


async def seed_memory_db() -> bool:
    """Seeds Memory DB tables: tenants, guardians, learners, learner_memories, learner_interest_profile."""
    dsn = settings.memory_db.dsn
    logger.info("Connecting to Memory DB for synthetic seeding...")
    try:
        conn = await asyncpg.connect(dsn, timeout=5.0)
    except Exception as exc:
        logger.warning(f"Memory DB connection failed ({exc}). Skipping Postgres memory seeding.")
        return False

    try:
        async with conn.transaction():
            # Set transaction tenant RLS context
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(DEFAULT_TENANT_ID))

            # 1. Tenant
            await conn.execute(
                """
                INSERT INTO tenants (id, name, region, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """,
                DEFAULT_TENANT_ID,
                "Pratham NGO Partner Tenant",
                "in",
            )

            # 2. Guardian
            await conn.execute(
                """
                INSERT INTO guardians (id, tenant_id, phone_number, email, verification_method, verified_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                DEFAULT_GUARDIAN_ID,
                DEFAULT_TENANT_ID,
                "+919876543210",
                "guardian@vadipehn.org",
                "ngo_cosign",
            )

            # 3. Learner ('Aria')
            await conn.execute(
                """
                INSERT INTO learners (id, tenant_id, guardian_id, first_name, age_band, preferred_language, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name, age_band = EXCLUDED.age_band
                """,
                DEFAULT_LEARNER_ID,
                DEFAULT_TENANT_ID,
                DEFAULT_GUARDIAN_ID,
                "Aria",
                2,
                "hi",
                "active",
            )

            # 4. Synthetic 1536-dim vector memories
            embedding_1 = str(generate_synthetic_embedding(1536, 0.01))
            embedding_2 = str(generate_synthetic_embedding(1536, 0.02))

            # Check if memory already exists
            existing_mem = await conn.fetchval(
                "SELECT COUNT(*) FROM learner_memories WHERE tenant_id = $1 AND learner_id = $2",
                DEFAULT_TENANT_ID,
                DEFAULT_LEARNER_ID,
            )
            if existing_mem == 0:
                await conn.execute(
                    """
                    INSERT INTO learner_memories
                    (tenant_id, learner_id, conversation_session_id, embedding, content, metadata, created_at, expires_at)
                    VALUES
                    ($1, $2, $3, $4::vector, $5, $6::jsonb, NOW() - INTERVAL '2 days', NOW() + INTERVAL '18 months'),
                    ($1, $2, $7, $8::vector, $9, $10::jsonb, NOW() - INTERVAL '1 day', NOW() + INTERVAL '18 months')
                    """,
                    DEFAULT_TENANT_ID,
                    DEFAULT_LEARNER_ID,
                    UUID("11111111-1111-1111-1111-111111111111"),
                    embedding_1,
                    "Aria expressed high curiosity about drone robotics, sensors, and flight stability.",
                    json.dumps({"source": "voice", "sentiment_tag": "curious"}),
                    UUID("22222222-2222-2222-2222-222222222222"),
                    embedding_2,
                    "Aria discussed ocean ecosystems and marine biology pathways with Dr. Maya.",
                    json.dumps({"source": "voice", "sentiment_tag": "enthusiastic"}),
                )

            # 5. Learner interest profile
            interest_emb = str(generate_synthetic_embedding(1536, 0.05))
            await conn.execute(
                """
                INSERT INTO learner_interest_profile
                (learner_id, tenant_id, interest_embedding, top_interests, updated_at)
                VALUES ($1, $2, $3::vector, $4, NOW())
                ON CONFLICT (learner_id) DO UPDATE SET top_interests = EXCLUDED.top_interests, updated_at = NOW()
                """,
                DEFAULT_LEARNER_ID,
                DEFAULT_TENANT_ID,
                interest_emb,
                ["robotics_engineering", "marine_biology", "mathematics"],
            )

        logger.info("Successfully seeded Memory DB with synthetic tenant, guardian, learner, and 1536-dim vector memories.")
        return True
    except Exception as exc:
        logger.error(f"Error during Memory DB seeding: {exc}")
        return False
    finally:
        await conn.close()


async def seed_governance_db() -> bool:
    """Seeds Governance DB tables: consent_records, safety_incidents."""
    dsn = settings.governance_db.dsn
    logger.info("Connecting to Governance DB for synthetic seeding...")
    try:
        conn = await asyncpg.connect(dsn, timeout=5.0)
    except Exception as exc:
        logger.warning(f"Governance DB connection failed ({exc}). Skipping Postgres governance seeding.")
        return False

    try:
        async with conn.transaction():
            # Set transaction tenant RLS context
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(DEFAULT_TENANT_ID))

            # 1. Active consent records
            consent_types = [
                "conversation_storage",
                "document_ingestion",
                "voice_recording",
                "career_introductions",
            ]
            for c_type in consent_types:
                await conn.execute(
                    """
                    INSERT INTO consent_records
                    (tenant_id, learner_id, guardian_id, consent_type, granted, granted_at, verification_method)
                    VALUES ($1, $2, $3, $4, TRUE, NOW(), 'ngo_cosign')
                    ON CONFLICT (learner_id, consent_type) DO UPDATE SET granted = TRUE, granted_at = NOW()
                    """,
                    DEFAULT_TENANT_ID,
                    DEFAULT_LEARNER_ID,
                    DEFAULT_GUARDIAN_ID,
                    c_type,
                )

            # 2. Safety incident with 15-minute SLA tracking
            now = datetime.now(timezone.utc)
            sla_deadline = now + timedelta(minutes=15)
            existing_inc = await conn.fetchval(
                "SELECT COUNT(*) FROM safety_incidents WHERE tenant_id = $1 AND learner_id = $2",
                DEFAULT_TENANT_ID,
                DEFAULT_LEARNER_ID,
            )
            if existing_inc == 0:
                await conn.execute(
                    """
                    INSERT INTO safety_incidents
                    (tenant_id, learner_id, severity, transcript_excerpt, created_at, sla_deadline)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    DEFAULT_TENANT_ID,
                    DEFAULT_LEARNER_ID,
                    "classifier_unavailable",
                    "Synthetic safety proxy health check excerpt for SLA triage monitoring.",
                    now,
                    sla_deadline,
                )

        logger.info("Successfully seeded Governance DB with active consent records and 15-min SLA safety incident.")
        return True
    except Exception as exc:
        logger.error(f"Error during Governance DB seeding: {exc}")
        return False
    finally:
        await conn.close()


async def seed_all() -> None:
    """Executes full synthetic database seeding sequence."""
    logger.info("Starting Vadi-Pehn Synthetic Data Seeding...")
    mem_ok = await seed_memory_db()
    gov_ok = await seed_governance_db()
    logger.info(f"Synthetic Data Seeding Completed (Memory DB: {mem_ok}, Governance DB: {gov_ok}).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_all())
