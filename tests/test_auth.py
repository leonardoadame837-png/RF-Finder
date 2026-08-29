import unittest

from app.auth.password import hash_password, verify_password
from app.auth.permissions import has_permission
from app.auth.service import AuthService


class AuthTests(unittest.TestCase):
    def test_password_hash_is_not_plaintext(self):
        password = "Correct-Horse-Battery-Staple"
        encoded = hash_password(password)
        self.assertNotEqual(encoded, password)
        self.assertTrue(verify_password(password, encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_login_and_authentication(self):
        auth = AuthService()
        user = auth.register("TestUser", "Correct-Horse-Battery-Staple")
        access, refresh = auth.login("testuser", "Correct-Horse-Battery-Staple")
        self.assertTrue(access)
        self.assertTrue(refresh)
        self.assertEqual(auth.authenticate(access).id, user.id)
        auth.logout(access)
        self.assertIsNone(auth.authenticate(access))

    def test_role_permissions(self):
        self.assertTrue(has_permission("viewer", "measurements:read"))
        self.assertFalse(has_permission("viewer", "devices:control"))
        self.assertTrue(has_permission("operator", "devices:control"))
        self.assertTrue(has_permission("owner", "anything"))

    def test_duplicate_users_rejected(self):
        auth = AuthService()
        auth.register("user", "Correct-Horse-Battery-Staple")
        with self.assertRaises(ValueError):
            auth.register("USER", "Another-Correct-Password")


if __name__ == "__main__":
    unittest.main()
