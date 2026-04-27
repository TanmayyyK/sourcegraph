ALTER TABLE IF EXISTS assets
    ADD COLUMN IF NOT EXISTS audio_summary_completed BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS assets
    ADD COLUMN IF NOT EXISTS pipeline_summary_completed BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS assets
    ADD COLUMN IF NOT EXISTS auditor_dispatched BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS frame_vectors
    ADD COLUMN IF NOT EXISTS is_temporary BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_frame_asset_temporary
    ON frame_vectors (asset_id, is_temporary);
