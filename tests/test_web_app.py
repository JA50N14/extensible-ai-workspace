from fastapi.testclient import TestClient

from extensible_ai_workspace.web import create_app


def test_application_page_is_available() -> None:
    client = TestClient(create_app())

    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>Extensible AI Workspace</h1>" in response.text
    assert "<p>The web runtime is running.</p>" in response.text


def test_liveness_reports_process_is_alive() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_runtime_is_ready() -> None:
    client = TestClient(create_app(readiness_check=lambda: True))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_reports_runtime_is_not_ready() -> None:
    client = TestClient(create_app(readiness_check=lambda: False))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
