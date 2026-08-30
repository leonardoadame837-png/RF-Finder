import tempfile
import unittest
from pathlib import Path

from app.auth.persistent import PersistentAuthService
from app.database.sqlite import Database


class PersistentAuthTests(unittest.TestCase):
    def test_user_and_session_survive_service_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "rf.db")
            db = Database(path)
            first = PersistentAuthService(db)
            user = first.register("Operator", "Correct-Horse-Battery-Staple")
            access, refresh = first.login("operator", "Correct-Horse-Battery-Staple")
            self.assertTrue(refresh)

            restarted = PersistentAuthService(Database(path))
            restored = restarted.authenticate(access)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.id, user.id)

    def test_bad_password_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = PersistentAuthService(Database(str(Path(tmp) / "rf.db")))
            auth.register("user", "Correct-Horse-Battery-Staple")
            with self.assertRaises(ValueError):
                auth.login("user", "wrong-password")


if __name__ == "__main__":
    unittest.main()
