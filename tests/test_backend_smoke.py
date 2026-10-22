"""Manual smoke check for the current authenticated FixFlow API."""

import os
import secrets
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        os.environ["JWT_SECRET"] = "smoke-test-secret-for-fixflow-at-least-32-characters"
        os.environ["FIXFLOW_DATABASE_PATH"] = str(Path(temporary_directory) / "fixflow-smoke.db")
        from fastapi.testclient import TestClient
        from backend.app import main

        main.initialize_database()
        client = TestClient(main.app)
        password = secrets.token_urlsafe(18)
        registered = client.post("/api/v1/auth/register", json={"email": "smoke@fixflow.test", "display_name": "Smoke Resident", "password": password})
        assert registered.status_code == 201, registered.text
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        guidance = client.post("/api/v1/tickets/recommendation", headers=headers, json={"category": "Other", "description": "Paani leak ho raha hai below the washroom sink."})
        assert guidance.status_code == 200, guidance.text
        assert guidance.json()["category"]["recommended_category"] == "Plumbing"

        created = client.post("/api/v1/tickets", headers=headers, json={"category": "Plumbing", "block": "A", "room": "211", "description": "Paani leak ho raha hai below the washroom sink."})
        assert created.status_code == 201, created.text
        ticket = created.json()
        assert ticket["status"] == "Open"
        assert ticket["priority"] == "Medium"
        assert ticket["duplicate_suggestions"]
        assert ticket["classification_recommendation"]["recommended_category"] == "Plumbing"

    print("FixFlow backend smoke test: PASS")


if __name__ == "__main__":
    run()
