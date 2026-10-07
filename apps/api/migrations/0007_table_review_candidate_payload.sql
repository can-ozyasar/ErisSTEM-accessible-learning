ALTER TABLE table_reviews ADD COLUMN IF NOT EXISTS candidate_payload JSONB;
UPDATE table_reviews SET candidate_payload = draft_payload WHERE candidate_payload IS NULL;
ALTER TABLE table_reviews ALTER COLUMN candidate_payload SET NOT NULL;
