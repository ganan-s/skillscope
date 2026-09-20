from __future__ import annotations

import json
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


@pytest.mark.e2e
@pytest.mark.docker
def test_installed_service_ingests_then_serves_snapshot_without_native_sources(
    built_wheel: Path,
) -> None:
    fixtures = PROJECT_ROOT / "tests" / "fixtures" / "cursor"
    container_wheel = f"/wheels/{built_wheel.name}"
    probe = """
import json
import time
import urllib.error
import urllib.request

for _ in range(100):
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/v1/conversations", timeout=1
        ) as response:
            listing = json.load(response)
        break
    except Exception:
        time.sleep(0.1)
else:
    raise SystemExit("service did not become ready")

item = listing["items"][0]
with urllib.request.urlopen(
    "http://127.0.0.1:8000/api/v1/meta", timeout=1
) as response:
    metadata = json.load(response)
with urllib.request.urlopen(
    "http://127.0.0.1:8000/api/v1/conversations/" + item["id"], timeout=1
) as response:
    detail = json.load(response)
try:
    urllib.request.urlopen(
        "http://127.0.0.1:8000/api/v1/conversations/conv_missing", timeout=1
    )
except urllib.error.HTTPError as error:
    not_found = error.code
try:
    urllib.request.urlopen(
        "http://127.0.0.1:8000/api/v1/conversations?limit=101", timeout=1
    )
except urllib.error.HTTPError as error:
    invalid_page = error.code
print(json.dumps({
    "listing": listing,
    "metadata": metadata,
    "detail": detail,
    "not_found": not_found,
    "invalid_page": invalid_page,
}))
"""
    setup = " && ".join(
        [
            f"uv pip install --system {shlex.quote(container_wheel)} >/dev/null",
            "cp -R /fixtures /native",
            (
                "skillscope ingest --harness cursor --grace-seconds 0 "
                "--db /data/skillscope.sqlite "
                "--transcripts /native/transcripts --spool /native/hooks.jsonl"
            ),
            "rm -rf /native",
        ]
    )
    command = (
        f"{setup}\n"
        "skillscope serve --db /data/skillscope.sqlite "
        "--host 127.0.0.1 --port 8000 >/tmp/skillscope.log 2>&1 &\n"
        f"python -c {shlex.quote(probe)}"
    )

    with tempfile.TemporaryDirectory() as data_dir:
        container = (
            DockerContainer(RUNTIME_IMAGE)
            .with_volume_mapping(str(built_wheel.parent), "/wheels", mode="ro")
            .with_volume_mapping(str(fixtures), "/fixtures", mode="ro")
            .with_volume_mapping(data_dir, "/data", mode="rw")
            .with_command(["sh", "-c", command])
        )
        with container:
            wrapped = container.get_wrapped_container()
            status = wrapped.wait(timeout=180)
            stdout = wrapped.logs(stdout=True, stderr=False).decode()
            stderr = wrapped.logs(stdout=False, stderr=True).decode()

    assert status["StatusCode"] == 0, (
        f"installed service failed\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    result = json.loads(stdout.strip().splitlines()[-1])
    assert result["metadata"]["harnesses"] == ["cursor"]
    assert result["listing"]["items"]
    assert result["detail"]["tasks"]
    assert result["not_found"] == 404
    assert result["invalid_page"] == 400


@pytest.mark.e2e
@pytest.mark.docker
def test_installed_evaluate_without_agent_evidence_preserves_sources_and_uncertainty(
    built_wheel: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "pilot"
    skill_path = ".cursor/skills/backend-unit-testing/SKILL.md"
    skill_file = project / skill_path
    skill_file.parent.mkdir(parents=True)
    skill_content = "Unit tests use in-memory inputs.\n"
    skill_file.write_text(skill_content, encoding="utf-8")
    (project / "AGENTS.md").write_text(
        "Use uv for Python environments, dependencies, and commands.\n",
        encoding="utf-8",
    )
    source_ref = {"path": skill_path, "quote": skill_content.strip()}
    case_set = {
        "schema_version": 1,
        "id": "synthetic-installed-cli-pilot",
        "version": "1.0.0",
        "provenance": {
            "kind": "project_specification",
            "note": "Synthetic E2E fixture; no agent run or behavior claim.",
        },
        "skills": [{"id": "backend-unit-testing", "path": skill_path}],
        "cases": [
            {
                "id": "pure-parser",
                "title": "Pure parser input",
                "task": "Test a parser using in-memory records.",
                "required_skills": ["backend-unit-testing"],
                "allowed_skills": [],
                "forbidden_skills": [],
                "selection_rationale": "This task exercises pure parsing.",
                "source_refs": [source_ref],
                "requirements": [
                    {
                        "id": "in-memory-inputs",
                        "description": "Keep parser inputs in memory.",
                        "source_refs": [source_ref],
                    }
                ],
            }
        ],
    }
    (project / "cases.json").write_text(json.dumps(case_set), encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    container_wheel = f"/wheels/{built_wheel.name}"
    command = (
        f"uv pip install --system {shlex.quote(container_wheel)} >/dev/null"
        " && skillscope evaluate --project /pilot --cases /pilot/cases.json"
        " --output /data/report"
    )
    container = (
        DockerContainer(RUNTIME_IMAGE)
        .with_volume_mapping(str(built_wheel.parent), "/wheels", mode="ro")
        .with_volume_mapping(str(project), "/pilot", mode="ro")
        .with_volume_mapping(str(data), "/data", mode="rw")
        .with_command(["sh", "-c", command])
    )

    with container:
        wrapped = container.get_wrapped_container()
        status = wrapped.wait(timeout=120)
        stdout = wrapped.logs(stdout=True, stderr=False).decode()
        stderr = wrapped.logs(stdout=False, stderr=True).decode()

    assert status["StatusCode"] == 0, (
        f"installed evaluator failed\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    report = json.loads((data / "report" / "report.json").read_text())
    assert report["cases"][0]["selection"]["status"] == "missing_evidence"
    assert report["cases"][0]["behavior"][0]["status"] == "missing_evidence"
    source = next(s for s in report["inputs"]["sources"] if s["path"] == skill_path)
    assert source["content"] == skill_content
    assert report["inputs"]["evidence"] is None
    assert "behavior remains unverified" in (data / "report" / "report.md").read_text()
