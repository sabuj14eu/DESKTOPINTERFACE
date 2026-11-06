import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def fixture_app(monkeypatch):
    monkeypatch.setenv("SMT_PROVIDER", "fixture")
    monkeypatch.setenv("SMT_ENV", "test")
    monkeypatch.setenv("SMT_ACCESS_TOKEN", "")
    monkeypatch.setenv("SMT_WEB_DIST", "/nonexistent")
    from signalmesh_terminal import routes
    routes.reset_for_tests()
    from signalmesh_terminal.main import create_app
    app = create_app()
    yield app
    routes.reset_for_tests()


@pytest.fixture
def client(fixture_app):
    from fastapi.testclient import TestClient
    return TestClient(fixture_app)
