import os
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
os.environ["JWT_SECRET"] = "test-secret-for-fixflow-auth-suite-at-least-32-characters"
_directory = tempfile.TemporaryDirectory()
os.environ["FIXFLOW_DATABASE_PATH"] = str(Path(_directory.name) / "fixflow-test.db")

from fastapi.testclient import TestClient
from backend.app import main


class AuthenticationAndRbacTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.initialize_database()
        cls.client = TestClient(main.app)
        cls.resident_password = secrets.token_urlsafe(18)
        cls.staff_password = secrets.token_urlsafe(18)
        cls.resident_one = cls.register("resident-one@fixflow.com", "Resident One")
        cls.resident_two = cls.register("resident-two@fixflow.com", "Resident Two")
        cls.technician = main.create_user_record("tech@fixflow.com", "Tech User", cls.staff_password, "technician")
        cls.warden = main.create_user_record("warden@fixflow.com", "Warden User", cls.staff_password, "warden")

    @classmethod
    def register(cls, email, display_name):
        response = cls.client.post("/api/v1/auth/register", json={"email": email, "display_name": display_name, "password": cls.resident_password})
        assert response.status_code == 201, response.text
        return response.json()

    @staticmethod
    def authorization(token):
        return {"Authorization": f"Bearer {token}"}

    def test_public_registration_is_resident_and_argon2_hashed(self):
        user = self.resident_one["user"]
        self.assertEqual(user["role"], "resident")
        with main.connection() as database:
            row = database.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.assertTrue(row["password_hash"].startswith("$argon2"))

    def test_login_and_invalid_token(self):
        login = self.client.post("/api/v1/auth/login", json={"email": "resident-one@fixflow.com", "password": self.resident_password})
        self.assertEqual(login.status_code, 200)
        invalid = self.client.get("/api/v1/auth/me", headers=self.authorization("not-a-token"))
        self.assertEqual(invalid.status_code, 401)
        expired = jwt.encode({"sub": str(self.resident_one["user"]["id"]), "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, main.JWT_SECRET, algorithm=main.JWT_ALGORITHM)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.authorization(expired)).status_code, 401)

    def test_resident_ticket_is_private_and_staff_manage(self):
        one_headers = self.authorization(self.resident_one["access_token"])
        two_headers = self.authorization(self.resident_two["access_token"])
        created = self.client.post("/api/v1/tickets", headers=one_headers, json={"category": "Plumbing", "block": "A", "room": "212", "description": "Sink leaks after using tap."})
        self.assertEqual(created.status_code, 201)
        ticket = created.json()
        self.assertEqual(ticket["resident"], "Resident One")
        self.assertFalse(any(item["id"] == ticket["id"] for item in self.client.get("/api/v1/tickets", headers=two_headers).json()))
        self.assertEqual(self.client.patch(f"/api/v1/tickets/{ticket['id']}", headers=one_headers, json={"status": "Resolved"}).status_code, 403)

        warden_token = main.create_access_token(self.warden)[0]
        warden_headers = self.authorization(warden_token)
        assigned = self.client.patch(f"/api/v1/tickets/{ticket['id']}", headers=warden_headers, json={"assignee_id": self.technician["id"], "status": "In progress"})
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["assignee"], "Tech User")

        tech_token = main.create_access_token(self.technician)[0]
        tech_headers = self.authorization(tech_token)
        self.assertEqual(self.client.get("/api/v1/analytics/service-health", headers=tech_headers).status_code, 403)
        self.assertEqual(self.client.patch("/api/v1/tickets/FF-1041", headers=tech_headers, json={"status": "Resolved"}).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/tickets/{ticket['id']}", headers=tech_headers, json={"status": "Resolved"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/tickets/{ticket['id']}", headers=tech_headers, json={"assignee_id": self.technician["id"]}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
