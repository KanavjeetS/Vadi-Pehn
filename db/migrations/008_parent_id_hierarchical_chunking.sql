-- db/migrations/008_parent_id_hierarchical_chunking.sql
-- Implements parent_id column for Hierarchical Chunking in memory storage

BEGIN;

ALTER TABLE learner_memories
ADD COLUMN IF NOT EXISTS parent_id UUID DEFAULT NULL REFERENCES learner_memories(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_learner_memories_parent_id ON learner_memories(parent_id);

COMMIT;
