import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gitpulse.api import create_app
from gitpulse.core import Store


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "api.sqlite", "example")
        self.token = "test-only-token-not-a-real-credential"
        self.client = TestClient(create_app(self.store, self.token))
        self.addCleanup(self.client.close)

    def test_authentication_required_for_read_and_sync(self) -> None:
        self.assertEqual(self.client.get("/api/state").status_code, 401)
        self.assertEqual(self.client.post("/api/sync").status_code, 401)
        self.assertEqual(self.store.revision(), 0)

    def test_authenticated_state_and_public_health(self) -> None:
        response = self.client.get("/api/state", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.token, response.text)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_failed_sync_redacted(self) -> None:
        with patch("gitpulse.api.GitHubClient") as provider:
            provider.return_value.people.side_effect = RuntimeError("private-detail")
            response = self.client.post("/api/sync", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private-detail", response.text)
        self.assertEqual(self.store.revision(), 0)

    def test_short_token_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_app(self.store, "short")

    def test_constructor_failure_releases_lock(self) -> None:
        with patch("gitpulse.api.GitHubClient", side_effect=RuntimeError("private-constructor-detail")):
            for _attempt in range(2):
                response = self.client.post("/api/sync", headers={"Authorization": f"Bearer {self.token}"})
                self.assertEqual(response.status_code, 502)
                self.assertNotIn("private-constructor-detail", response.text)

    def test_arbitrary_origin_not_permitted(self) -> None:
        response = self.client.options(
            "/api/state", headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"}
        )
        self.assertNotIn("access-control-allow-origin", response.headers)
