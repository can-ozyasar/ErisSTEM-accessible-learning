ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS selected_pages VARCHAR(1000);
UPDATE processing_jobs SET selected_pages = 'all' WHERE selected_pages IS NULL;
ALTER TABLE processing_jobs ALTER COLUMN selected_pages SET NOT NULL;
ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS uq_job_source_pipeline;
ALTER TABLE processing_jobs DROP CONSTRAINT IF EXISTS uq_job_source_pipeline_scope;
ALTER TABLE processing_jobs
  ADD CONSTRAINT uq_job_source_pipeline_scope
  UNIQUE (source_checksum, pipeline_version, selected_pages);
