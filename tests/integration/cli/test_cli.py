from __future__ import annotations

from pathlib import Path

import pytest

from skillscope.cli import main


@pytest.mark.integration
def test_version_option_reports_installed_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert capsys.readouterr().out == "skillscope 0.1.0\n"


@pytest.mark.integration
def test_serve_when_store_is_missing_fails_without_creating_database(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "missing.sqlite"

    exit_code = main(["serve", "--db", str(db_path)])

    assert exit_code == 1
    assert not db_path.exists()
    assert "store_missing" in capsys.readouterr().err
