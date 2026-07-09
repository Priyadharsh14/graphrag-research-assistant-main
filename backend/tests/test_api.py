from starlette.testclient import TestClient


def test_root_and_health_and_docs():
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

        r = client.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert "status" in body and "neo4j" in body and "qdrant" in body

        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        assert len(r.json()["paths"]) > 10


def test_upload_rejects_non_pdf():
    from app.main import app

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/papers/upload",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 400


def test_chat_rejects_empty_question():
    from app.main import app

    with TestClient(app) as client:
        r = client.post("/api/v1/chat", json={"question": "   "})
        assert r.status_code == 400
