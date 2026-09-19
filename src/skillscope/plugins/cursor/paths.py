"""Platform-specific Cursor path conventions.

All knowledge of ``~/.cursor`` layout lives here.  Override via
DiscoveryContext for tests and custom setups.
"""

from __future__ import annotations

import platform
from pathlib import Path


def cursor_data_root(home: Path | None = None) -> Path:
    """Return the Cursor per-user data root for this OS."""
    h = home or Path.home()
    system = platform.system()
    if system == "Darwin":
        return h / ".cursor"
    if system == "Linux":
        return h / ".cursor"
    # Windows best-effort
    return h / ".cursor"


def transcript_roots(home: Path | None = None) -> list[Path]:
    """Return directories that may contain agent-transcripts subdirectories."""
    root = cursor_data_root(home)
    projects = root / "projects"
    if projects.is_dir():
        return [projects]
    return []


def spool_root(home: Path | None = None) -> Path:
    """Return the default hook-spool parent directory."""
    from skillscope.config import default_data_dir

    return default_data_dir()


def find_transcript_dirs(projects_root: Path) -> list[Path]:
    """Walk a Cursor projects directory for agent-transcript subdirectories.

    Cursor stores transcripts under:
      ~/.cursor/projects/<project-slug>/agent-transcripts/<conv-id>/<conv-id>.jsonl

    Returns paths to each conversation directory containing at least one JSONL.
    """
    results: list[Path] = []
    if not projects_root.is_dir():
        return results
    for project_dir in sorted(projects_root.iterdir()):
        transcripts_dir = project_dir / "agent-transcripts"
        if not transcripts_dir.is_dir():
            continue
        for conv_dir in sorted(transcripts_dir.iterdir()):
            if not conv_dir.is_dir():
                continue
            jsonl_files = list(conv_dir.glob("*.jsonl"))
            if jsonl_files:
                results.append(conv_dir)
    return results
