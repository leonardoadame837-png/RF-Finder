import tempfile
import unittest
from pathlib import Path

from app.api_auth import APIAuth, ROLE_PERMISSIONS
from app.auth import AuthManager


class TestAPIAuth(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        auth = AuthManager(Path(self.temp_dir.name) / "users.json", session_ttl=60)
        auth.create_account("user", "correct horse battery")
        auth.create_account("admin", "another correct password", role="admin")
        self.api = APIAuth(auth)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_returns_session_and_permissions(self):
        session = self.api.login("user", "correct horse battery")
        principal = self.api.require("Bearer " + session.token, "rf.read")
        self.assertEqual(principal.user.username, "user")
        self.assertTrue(principal.can("rf.scan"))
        self.assertNotIn("admin.users", ROLE_PERMISSIONS["user"])

    def test_missing_token_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.api.require(None, "rf.read")

    def test_invalid_token_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.api.require("Bearer invalid-token", "rf.read")

    def test_role_permission_boundary(self):
        session = self.api.login("user", "correct horse battery")
        with self.assertRaises(PermissionError):
            self.api.require("Bearer " + session.token, "admin.users")

        admin = self.api.login("admin", "another correct password")
        principal = self.api.require("Bearer " + admin.token, "admin.users")
        self.assertEqual(principal.user.role, "admin")

    def test_logout_invalidates_api_token(self):
        session = self.api.login("user", "correct horse battery")
        self.assertTrue(self.api.logout("Bearer " + session.token))
        with self.assertRaises(PermissionError):
            self.api.require("Bearer " + session.token, "rf.read")


if __name__ == "__main__":
    unittest.main()
