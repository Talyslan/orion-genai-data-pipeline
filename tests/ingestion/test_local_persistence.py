from datetime import UTC, datetime
from pathlib import Path

from pipeline.ingestion.persistence import save_local_document
from pipeline.shared.schemas.local_document import LocalDocument


def test_save_local_document_writes_front_matter(
    tmp_output_dir: Path,
) -> None:
    doc = LocalDocument(
        source_path="/abs/path/sample-prompt.txt",
        file_name="sample-prompt.txt",
        title="sample-prompt",
        content="Conteúdo de teste",
        ingested_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )

    saved_path = save_local_document(doc, tmp_output_dir)
    content = saved_path.read_text(encoding="utf-8")

    assert saved_path.suffix == ".md"
    assert "source_path: /abs/path/sample-prompt.txt" in content
    assert "file_name: sample-prompt.txt" in content
    assert "ingested_at: 2026-06-08T12:00:00+00:00" in content
    assert "# sample-prompt\n\nConteúdo de teste" in content
