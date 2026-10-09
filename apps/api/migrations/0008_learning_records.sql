CREATE TABLE IF NOT EXISTS learning_records (
    id VARCHAR(80) PRIMARY KEY,
    kind VARCHAR(20) NOT NULL,
    module_id VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL,
    revision INTEGER NOT NULL
);
