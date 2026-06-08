CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    source_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    minio_object_key TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
