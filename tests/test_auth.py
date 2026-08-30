import tempfile
import unittest
from pathlib import Path

from app.auth import AuthError, AuthManager


class TestAuthManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.users_path = Path(self.temp_dir.name) / "users.json"
        self.auth = AuthManager(self.users_path, session_ttl=60)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_authenticate(self):
        user = self.auth.create_account("alice", "correct horse battery")
        self.assertEqual(user.role, "user")
        session = self.auth.authenticate("alice", "correct horse battery")
        self.assertEqual(self.auth.validate_token(session.token).username, "alice")

    def test_wrong_password_rejected(self):
        self.auth.create_account("alice", "correct horse battery")
        with self.assertRaises(AuthError):
            self.auth.authenticate("alice", "wrong password")

    def test_password_is_not_stored_in_plaintext(self):
        self.auth.create_account("alice", "correct horse battery")
        raw = self.users_path.read_text(encoding="utf-8")
        self.assertNotIn("correct horse battery", raw)
        self.assertIn("password_hash", raw)

    def test_logout_invalidates_token(self):
        self.auth.create_account("alice", "correct horse battery")
        session = self.auth.authenticate("alice", "correct horse battery")
        self.auth.logout(session.token)
        self.assertIsNone(self.auth.validate_token(session.token))

    def test_duplicate_account_rejected(self):
        self.auth.create_account("alice", "correct horse battery")
        with self.assertRaises(AuthError):
            self.auth.create_account("alice", "another password")


if __name__ == "__main__":
    unittest.main()
