from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.ingestion.cli import main
from pipeline.ingestion.corpus import CorpusDocument, CorpusFileStatus, CorpusStatus


def _corpus_status(corpus_dir: Path, *, ready: bool) -> CorpusStatus:
    required_doc = CorpusDocument(
        id="required",
        title="Required",
        filename="required.pdf",
    )
    file_status = CorpusFileStatus(
        document=required_doc,
        path=corpus_dir / "required.pdf",
        present=ready,
        valid_pdf=ready,
        error=None if ready else "missing",
    )
    return CorpusStatus(
        corpus_dir=corpus_dir,
        manifest_path=corpus_dir / "manifest.yaml",
        documents=(required_doc,),
        files=(file_status,),
    )


@patch("pipeline.ingestion.cli.check_corpus")
def test_cli_corpus_status_success(mock_check: Mock, tmp_path: Path) -> None:
    mock_check.return_value = _corpus_status(tmp_path, ready=True)

    exit_code = main(["corpus-status", "--dir", str(tmp_path)])

    assert exit_code == 0
    mock_check.assert_called_once_with(None, tmp_path)


@patch("pipeline.ingestion.cli.check_corpus")
def test_cli_corpus_status_fails_when_incomplete(
    mock_check: Mock,
    tmp_path: Path,
) -> None:
    mock_check.return_value = _corpus_status(tmp_path, ready=False)

    exit_code = main(["corpus-status"])

    assert exit_code == 1
