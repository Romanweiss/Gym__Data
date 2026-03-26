from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_root_serves_workspace_shell() -> None:
    app = create_app()
    client = TestClient(app)
    registered_paths = {route.path for route in app.routes}

    response = client.get("/ui")

    assert "/" in registered_paths
    assert "/ui" in registered_paths
    assert response.status_code == 200
    assert "Gym__Data Workspace" in response.text
    assert "Progress Workspace" in response.text
