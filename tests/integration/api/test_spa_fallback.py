"""Integration tests for SPA static file hosting and fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skillscope.api.app import create_app
from skillscope.application.queries import (
    GetConversation,
    GetStoreMetadata,
    ListConversations,
)
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.readers import SQLiteReadRepository

pytestmark = pytest.mark.integration


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.sqlite"
    conn = connect_writable(path)
    migrate(conn)
    conn.commit()
    conn.close()
    return path


def _make_client(db_path: Path, static_dir: Path) -> TestClient:
    repo = SQLiteReadRepository(db_path)
    app = create_app(
        list_conversations=ListConversations(repo),
        get_conversation=GetConversation(repo),
        get_store_metadata=GetStoreMetadata(repo),
        static_dir=static_dir,
    )
    return TestClient(app, raise_server_exceptions=False)


class TestSPAFallback:
    def test_api_paths_return_404_not_html(self, db_path: Path, tmp_path: Path) -> None:
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>app</html>")
        client = _make_client(db_path, static_dir)

        resp = client.get("/api/v1/nonexistent")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "not_found"

    def test_root_returns_index_html(self, db_path: Path, tmp_path: Path) -> None:
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>Skillscope</html>")
        client = _make_client(db_path, static_dir)

        resp = client.get("/")

        assert resp.status_code == 200
        assert "Skillscope" in resp.text

    def test_static_asset_served(self, db_path: Path, tmp_path: Path) -> None:
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>app</html>")
        assets_dir = static_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "main.js").write_text("console.log('hi')")
        client = _make_client(db_path, static_dir)

        resp = client.get("/assets/main.js")

        assert resp.status_code == 200
        assert "console.log" in resp.text

    def test_symlink_outside_static_root_is_not_served(
        self,
        db_path: Path,
        tmp_path: Path,
    ) -> None:
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>app</html>")
        secret = tmp_path / "secret.txt"
        secret.write_text("do-not-serve")
        (static_dir / "leak.txt").symlink_to(secret)
        client = _make_client(db_path, static_dir)

        resp = client.get("/leak.txt")

        assert resp.status_code == 200
        assert "do-not-serve" not in resp.text
        assert "<html>app</html>" in resp.text

    def test_unknown_path_falls_back_to_index(
        self, db_path: Path, tmp_path: Path
    ) -> None:
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")
        client = _make_client(db_path, static_dir)

        resp = client.get("/conversations/some-id")

        assert resp.status_code == 200
        assert "SPA" in resp.text
