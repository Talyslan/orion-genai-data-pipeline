from pathlib import Path

from pipeline.shared.config.settings import Settings


def test_resolved_tesseract_cmd_uses_local_venv_install(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    tess_root = tmp_path / ".venv" / "share" / "tesseract"
    tess_root.mkdir(parents=True)
    tesseract_exe = tess_root / "tesseract.exe"
    tesseract_exe.write_text("stub", encoding="utf-8")

    settings = Settings(tesseract_cmd="")

    assert settings.resolved_tesseract_cmd == str(tesseract_exe.resolve())


def test_resolved_tesseract_cmd_prefers_explicit_env(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(tesseract_cmd="C:\\Tools\\tesseract.exe")

    assert settings.resolved_tesseract_cmd == "C:\\Tools\\tesseract.exe"
