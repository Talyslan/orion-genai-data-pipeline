from pathlib import Path

from pipeline.ingestion.persistence import save_pdf_document
from pipeline.shared.schemas.pdf_document import PdfDocument


def test_save_pdf_document_writes_manifest_with_metadata(tmp_output_dir: Path) -> None:
    doc = PdfDocument(
        source_path="/data/pdfs/microservices-on-aws.pdf",
        file_name="microservices-on-aws.pdf",
        title="microservices-on-aws",
        page_count=35,
    )

    saved_path = save_pdf_document(doc, tmp_output_dir)
    content = saved_path.read_text(encoding="utf-8")

    assert saved_path.exists()
    assert saved_path.suffix == ".md"
    assert "source_format: pdf" in content
    assert "page_count: 35" in content
    assert "microservices-on-aws" in content
