"""PostgreSQL persistence for documents and chunks."""

import logging
from pathlib import Path
from uuid import UUID

import psycopg

from pipeline.shared.config import settings
from pipeline.shared.schemas.processed_document import ProcessedDocument
from pipeline.shared.schemas.text_chunk import TextChunk
from pipeline.shared.schemas.trace_result import TraceResult

logger = logging.getLogger(__name__)

SERVICE = "postgres"

_SCHEMA_SQL = """
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
"""


class PostgresStore:
    """Stores documents and chunks in PostgreSQL."""

    def __init__(self, conninfo: str | None = None) -> None:
        self._conninfo = conninfo or settings.postgres_url

    def ensure_schema(self) -> None:
        """Create tables when they do not exist."""
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(_SCHEMA_SQL)
            conn.commit()
        logger.info("PostgreSQL schema ensured", extra={"service": SERVICE})

    def get_document_id_by_hash(self, file_hash: str) -> UUID | None:
        """Return an existing document id for a content hash."""
        with psycopg.connect(self._conninfo) as conn:
            row = conn.execute(
                "SELECT id FROM documents WHERE file_hash = %s",
                (file_hash,),
            ).fetchone()
        return row[0] if row else None

    def insert_document(self, doc: ProcessedDocument) -> UUID:
        """Insert a document and return its id."""
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, source_url, file_name, file_hash,
                    minio_object_key, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    doc.id,
                    doc.source_path,
                    doc.file_name,
                    doc.file_hash,
                    doc.minio_object_key,
                    doc.created_at,
                ),
            )
            conn.commit()
        logger.info(
            "Document inserted",
            extra={"service": SERVICE, "document_id": str(doc.id)},
        )
        return doc.id

    def insert_chunks(self, document_id: UUID, chunks: list[TextChunk]) -> None:
        """Insert chunks for a document."""
        if not chunks:
            return

        with psycopg.connect(self._conninfo) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_index, content, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            chunk.id,
                            document_id,
                            chunk.chunk_index,
                            chunk.content,
                            chunk.created_at,
                        )
                        for chunk in chunks
                    ],
                )
            conn.commit()

        logger.info(
            "Chunks inserted",
            extra={
                "service": SERVICE,
                "document_id": str(document_id),
                "count": len(chunks),
            },
        )

    def save_document_and_chunks(
        self,
        doc: ProcessedDocument,
        chunks: list[TextChunk],
    ) -> UUID:
        """Atomically persist a document and its chunks."""
        with psycopg.connect(self._conninfo) as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, source_url, file_name, file_hash,
                    minio_object_key, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    doc.id,
                    doc.source_path,
                    doc.file_name,
                    doc.file_hash,
                    doc.minio_object_key,
                    doc.created_at,
                ),
            )
            if chunks:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO chunks (
                            id, document_id, chunk_index, content, created_at
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            (
                                chunk.id,
                                doc.id,
                                chunk.chunk_index,
                                chunk.content,
                                chunk.created_at,
                            )
                            for chunk in chunks
                        ],
                    )
            conn.commit()
        return doc.id

    def trace_vector(self, chunk_id: UUID) -> TraceResult:
        """Resolve the full trace chain for a chunk id."""
        with psycopg.connect(self._conninfo) as conn:
            row = conn.execute(
                """
                SELECT
                    c.id,
                    c.chunk_index,
                    c.content,
                    d.id,
                    d.file_name,
                    d.source_url,
                    d.minio_object_key
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.id = %s
                """,
                (chunk_id,),
            ).fetchone()

        if row is None:
            msg = f"Chunk not found: {chunk_id}"
            raise LookupError(msg)

        return TraceResult(
            chunk_id=row[0],
            chunk_index=row[1],
            chunk_content=row[2],
            document_id=row[3],
            file_name=row[4],
            source_path=row[5],
            minio_object_key=row[6],
            source_format="pdf" if str(row[4]).lower().endswith(".pdf") else None,
        )


def run_migration(sql_path: Path | None = None) -> None:
    """Execute the initial SQL migration file."""
    path = sql_path or Path("scripts/migrations/001_initial.sql")
    sql = path.read_text(encoding="utf-8")
    with psycopg.connect(settings.postgres_url) as conn:
        conn.execute(sql)
        conn.commit()
