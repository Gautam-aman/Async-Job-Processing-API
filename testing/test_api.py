import importlib
import time

from fastapi.testclient import TestClient


def test_job_lifecycle_and_events(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    import app

    app = importlib.reload(app)
    with TestClient(app.app) as client:
        response = client.post("/jobs", json={"text": "hello world"})
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert response.json()["status"] == "queued"

        # Polling verifies the HTTP contract while the worker runs separately.
        for _ in range(100):
            job = client.get(f"/jobs/{job_id}").json()
            if job["status"] == "completed":
                break
            time.sleep(0.02)
        assert job["result"] == "HELLO WORLD"
        assert client.get("/jobs").json()[0]["id"] == job_id
        events = client.get(f"/jobs/{job_id}/events")
        assert events.status_code == 200
        assert '"status": "completed"' in events.text
        assert client.get("/jobs/missing").status_code == 404
        assert client.get("/jobs/missing/events").status_code == 404
        assert client.post("/jobs", json={"text": ""}).status_code == 422
