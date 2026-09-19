from __future__ import annotations

import shlex
import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"


@pytest.fixture(scope="session")
def built_wheel() -> Iterator[Path]:
    artifact_root = PROJECT_ROOT / ".e2e-artifacts"
    artifact_root.mkdir(exist_ok=True)
    output_dir = Path(tempfile.mkdtemp(prefix="wheel-", dir=artifact_root))
    try:
        result = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(output_dir)],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(
                "wheel build failed"
                f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        wheels = tuple(output_dir.glob("skillscope-*.whl"))
        assert len(wheels) == 1, f"expected one Skillscope wheel, found {wheels}"
        yield wheels[0]
    finally:
        shutil.rmtree(output_dir)
        with suppress(OSError):
            artifact_root.rmdir()


@pytest.mark.e2e
@pytest.mark.docker
def test_installed_wheel_when_invoked_reports_package_version(
    built_wheel: Path,
) -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    expected_version = pyproject["project"]["version"]
    container_wheel = f"/wheels/{built_wheel.name}"
    command = (
        "uv pip install --system "
        f"{shlex.quote(container_wheel)} >/dev/null"
        " && skillscope --version"
    )

    container = (
        DockerContainer(RUNTIME_IMAGE)
        .with_volume_mapping(str(built_wheel.parent), "/wheels", mode="ro")
        .with_command(["sh", "-c", command])
    )

    with container:
        wrapped = container.get_wrapped_container()
        status = wrapped.wait(timeout=120)
        stdout = wrapped.logs(stdout=True, stderr=False).decode()
        stderr = wrapped.logs(stdout=False, stderr=True).decode()

    assert status["StatusCode"] == 0, (
        f"installed CLI failed\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert stdout.strip() == f"skillscope {expected_version}"
