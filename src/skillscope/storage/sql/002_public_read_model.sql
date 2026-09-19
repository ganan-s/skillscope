ALTER TABLE conversations ADD COLUMN public_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_public_id
ON conversations(public_id)
WHERE public_id IS NOT NULL;

INSERT INTO schema_meta (version) VALUES (2);
