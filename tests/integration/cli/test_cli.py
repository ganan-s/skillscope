from __future__ import annotations

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
