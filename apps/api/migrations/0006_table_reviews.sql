CREATE TABLE IF NOT EXISTS table_reviews (
  id VARCHAR(200) PRIMARY KEY,
  document_id VARCHAR(100) NOT NULL,
  draft_payload JSONB NOT NULL,
  published_payload JSONB,
  status VARCHAR(20) NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
