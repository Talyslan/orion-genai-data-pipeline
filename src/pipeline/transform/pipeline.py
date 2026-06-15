"""Orchestration of Bronze → clean → chunk → embed → Ouro."""

import hashlib
import logging
from pathlib import Path
from uuid import UUID

from pipeline.shared.config import settings
from pipeline.shared.schemas.processed_document import ProcessedDocument
from pipeline.shared.schemas.trace_result import TraceResult
from pipeline.shared.schemas.transform_result import (
    BatchTransformError,
    BatchTransformResult,
    TransformResult,
)
from pipeline.storage.postgres import PostgresStore
from pipeline.storage.qdrant_store import QdrantStore
from pipeline.transform.bronze_reader import BronzeObject, BronzeReader
from pipeline.transform.chunker import chunk_text
from pipeline.transform.cleaner import clean_content
from pipeline.transform.embedder import Embedder
from pipeline.transform.pdf_extractor import extract_pdf_content
from pipeline.transform.pdf_post_clean import post_clean_pdf_text

logger = logging.getLogger(__name__)


class TransformPipeline:
    """Runs the transformation flow for Bronze objects."""

    def __init__(
        self,
        reader: BronzeReader | None = None,
        embedder: Embedder | None = None,
        postgres: PostgresStore | None = None,
        qdrant: QdrantStore | None = None,
    ) -> None:
        self._reader = reader or BronzeReader()
        self._embedder = embedder or Embedder()
        self._postgres = postgres or PostgresStore()
        self._qdrant = qdrant or QdrantStore()

    def _resolve_metadata(self, bronze_obj: BronzeObject) -> tuple[str, str]:
        file_name = bronze_obj.file_name or Path(bronze_obj.object_key).stem
        source_path = bronze_obj.source_path or bronze_obj.object_key
        return source_path, file_name

    def _content_hash(self, cleaned: str) -> str:
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def _extract_raw_text(self, bronze_obj: BronzeObject) -> tuple[str, dict | None]:
        if not bronze_obj.is_pdf:
            return bronze_obj.body, None

        if bronze_obj.raw_bytes is None:
            msg = f"PDF object missing binary body: {bronze_obj.object_key}"
            raise ValueError(msg)

        file_name = bronze_obj.file_name or Path(bronze_obj.object_key).name
        extracted = extract_pdf_content(
            bronze_obj.raw_bytes,
            mode=settings.pdf_extraction_mode,
            max_pages=settings.pdf_max_pages,
            file_name=file_name,
        )
        logger.info(
            "PDF extracted",
            extra={
                "object_key": bronze_obj.object_key,
                "tables_count": extracted.tables_count,
                "pages_ocr": extracted.pages_ocr,
                "methods_used": extracted.methods_used,
            },
        )
        metadata = {
            "source_format": "pdf",
            "extraction_mode": settings.pdf_extraction_mode,
            "tables_count": extracted.tables_count,
            "pages_ocr": extracted.pages_ocr,
            "figures_count": extracted.figures_count,
            "methods_used": extracted.methods_used,
        }
        return post_clean_pdf_text(extracted.markdown), metadata

    def process_object(self, object_key: str) -> TransformResult:
        """Transform a single Bronze object."""
        logger.info("Starting transformation for %s", object_key)

        self._postgres.ensure_schema()

        bronze_obj = self._reader.fetch_object(object_key)
        raw_text, extraction_metadata = self._extract_raw_text(bronze_obj)
        cleaned = clean_content(raw_text)
        file_hash = self._content_hash(cleaned)

        existing_id = self._postgres.get_document_id_by_hash(file_hash)
        if existing_id is not None:
            logger.info(
                "Document already processed | object_key=%s document_id=%s",
                object_key,
                existing_id,
            )
            return TransformResult(
                object_key=object_key,
                document_id=existing_id,
                skipped=True,
            )

        source_path, file_name = self._resolve_metadata(bronze_obj)
        source_format = (
            extraction_metadata.get("source_format") if extraction_metadata else None
        )
        document = ProcessedDocument(
            source_path=source_path,
            file_name=file_name,
            file_hash=file_hash,
            minio_object_key=object_key,
            cleaned_content=cleaned,
            source_format=source_format,
            extraction_metadata=extraction_metadata,
        )

        chunks = chunk_text(cleaned, document.id)
        embeddings = self._embedder.embed_chunks(chunks)

        self._postgres.save_document_and_chunks(document, chunks)

        payloads = [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(document.id),
                "chunk_index": chunk.chunk_index,
                "source_path": source_path,
                "file_name": file_name,
                "minio_object_key": object_key,
                "source_format": source_format,
                "extraction_metadata": extraction_metadata,
            }
            for chunk in chunks
            if chunk.content.strip()
        ]
        self._qdrant.upsert_embeddings(embeddings, payloads)

        result = TransformResult(
            object_key=object_key,
            document_id=document.id,
            chunks_count=len(chunks),
            embeddings_count=len(embeddings),
        )
        logger.info(
            "Transformation completed | object_key=%s chunks=%s embeddings=%s",
            object_key,
            result.chunks_count,
            result.embeddings_count,
        )
        return result

    def run(
        self,
        object_key: str | None = None,
        prefix: str = "source/",
    ) -> BatchTransformResult:
        """Process one object or all objects under a Bronze prefix."""
        keys = [object_key] if object_key else self._reader.list_objects(prefix)

        results: list[TransformResult] = []
        errors: list[BatchTransformError] = []
        processed = 0
        skipped = 0

        for index, key in enumerate(keys, start=1):
            print(f"[{index}/{len(keys)}] Processing {key}...", flush=True)
            try:
                result = self.process_object(key)
                results.append(result)
                if result.skipped:
                    skipped += 1
                    print("  -> skipped (already processed)", flush=True)
                else:
                    processed += 1
                    print(
                        f"  -> done (chunks={result.chunks_count}, "
                        f"embeddings={result.embeddings_count})",
                        flush=True,
                    )
            except Exception as exc:
                logger.exception("Failed to transform %s", key)
                errors.append(BatchTransformError(object_key=key, error=str(exc)))

        batch = BatchTransformResult(
            total=len(keys),
            processed=processed,
            skipped=skipped,
            failed=len(errors),
            results=results,
            errors=errors,
        )
        logger.info(
            "Batch transformation completed | total=%s processed=%s "
            "skipped=%s failed=%s",
            batch.total,
            batch.processed,
            batch.skipped,
            batch.failed,
        )
        return batch


def run_transform(
    object_key: str | None = None,
    prefix: str = "source/",
) -> BatchTransformResult:
    """Run transformation with default dependencies."""
    return TransformPipeline().run(object_key=object_key, prefix=prefix)


def trace_vector(chunk_id: UUID) -> TraceResult:
    """Resolve traceability chain for a chunk id."""
    return PostgresStore().trace_vector(chunk_id)
