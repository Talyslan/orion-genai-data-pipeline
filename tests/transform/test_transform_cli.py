from unittest.mock import Mock, patch
from uuid import uuid4

from pipeline.transform.cli import main


@patch("pipeline.transform.cli.PostgresStore")
def test_cli_migrate_success(mock_store_cls, capsys) -> None:
    exit_code = main(["migrate"])

    assert exit_code == 0
    mock_store_cls.return_value.ensure_schema.assert_called_once()
    assert "PostgreSQL migration completed" in capsys.readouterr().out


@patch("pipeline.transform.cli.run_transform")
def test_cli_run_success(mock_run: Mock, capsys) -> None:
    mock_run.return_value = Mock(
        total=1,
        processed=1,
        skipped=0,
        failed=0,
        results=[
            Mock(
                skipped=False,
                object_key="source/a.md",
                chunks_count=2,
                embeddings_count=2,
            )
        ],
        errors=[],
    )

    exit_code = main(["run"])

    assert exit_code == 0
    assert "Transform completed" in capsys.readouterr().out


@patch("pipeline.transform.cli.run_transform")
def test_cli_run_returns_error_on_partial_failure(mock_run: Mock) -> None:
    mock_run.return_value = Mock(
        total=2,
        processed=1,
        skipped=0,
        failed=1,
        results=[
            Mock(
                skipped=False,
                object_key="source/2026/06/15/good.pdf",
                chunks_count=2,
                embeddings_count=2,
            )
        ],
        errors=[
            Mock(object_key="source/2026/06/15/bad.pdf", error="extraction failed")
        ],
    )

    exit_code = main(["run"])

    assert exit_code == 1


@patch("pipeline.transform.cli.trace_vector")
def test_cli_trace_success(mock_trace: Mock, capsys) -> None:
    chunk_id = uuid4()
    mock_trace.return_value = Mock(
        chunk_id=chunk_id,
        chunk_index=0,
        chunk_content="conteúdo de teste",
        document_id=uuid4(),
        file_name="wellarchitected-framework.pdf",
        source_format="pdf",
        source_path="./pdfs/wellarchitected-framework.pdf",
        minio_object_key="source/2026/06/08/wellarchitected-framework.pdf",
    )

    exit_code = main(["trace", str(chunk_id)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Trace result" in output
    assert "source_format:     pdf" in output
