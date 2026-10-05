-- PostgreSQL üretim şeması. CI/test ortamı eşdeğer şemayı SQLAlchemy ile SQLite'ta oluşturur.
CREATE TABLE IF NOT EXISTS processing_jobs (
  id VARCHAR(36) PRIMARY KEY,
  source_checksum VARCHAR(64) NOT NULL,
  pipeline_version VARCHAR(80) NOT NULL,
  status VARCHAR(20) NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  last_error_code VARCHAR(80),
  CONSTRAINT uq_job_source_pipeline UNIQUE (source_checksum, pipeline_version)
);
