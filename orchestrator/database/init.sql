-- ============================================================
-- SourceGraph Vector Database Schema
-- PostgreSQL 17 + pgvector
-- ============================================================

-- 1. Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Source Packets — raw ingested data from worker nodes
CREATE TABLE IF NOT EXISTS source_packets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_name      TEXT        NOT NULL,
    timestamp       FLOAT8      NOT NULL,
    visual_vector   vector(512),
    text_vector     vector(384),
    metadata        JSONB       DEFAULT '{}'::jsonb,
    source_node     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Golden Sources — protected original content
CREATE TABLE IF NOT EXISTS golden_sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT        NOT NULL UNIQUE,
    visual_vector   vector(512) NOT NULL,
    text_vector     vector(384) NOT NULL,
    metadata        JSONB       DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Match Results — detected piracy events
CREATE TABLE IF NOT EXISTS match_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       UUID        REFERENCES golden_sources(id),
    suspect_id      UUID        REFERENCES source_packets(id),
    visual_score    FLOAT8      NOT NULL,
    text_score      FLOAT8      NOT NULL,
    temporal_score  FLOAT8      NOT NULL DEFAULT 0.0,
    fused_score     FLOAT8      NOT NULL,
    confidence      FLOAT8      NOT NULL,
    verdict         TEXT        NOT NULL CHECK (verdict IN ('PIRATE', 'CLEAN', 'SUSPICIOUS')),
    graph_data      JSONB       DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- IVFFlat Indexes for Approximate Nearest Neighbor search
-- lists = sqrt(n) is a good starting point; 100 lists works
-- well for up to ~100k vectors.  ANALYZE after bulk loads.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_source_visual_ivfflat
    ON source_packets
    USING ivfflat (visual_vector vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_source_text_ivfflat
    ON source_packets
    USING ivfflat (text_vector vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_golden_visual_ivfflat
    ON golden_sources
    USING ivfflat (visual_vector vector_cosine_ops)
    WITH (lists = 20);

CREATE INDEX IF NOT EXISTS idx_golden_text_ivfflat
    ON golden_sources
    USING ivfflat (text_vector vector_cosine_ops)
    WITH (lists = 20);

-- Run ANALYZE so the query planner picks up index statistics
ANALYZE source_packets;
ANALYZE golden_sources;
ANALYZE match_results;
