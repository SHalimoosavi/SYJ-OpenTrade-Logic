import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server_fastapi.security import (  # noqa: E402
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)


class TestPasswordHashing(unittest.TestCase):
    def test_correct_password_verifies(self):
        h = hash_password("correct-horse-battery-staple")
        self.assertTrue(verify_password("correct-horse-battery-staple", h))

    def test_wrong_password_fails(self):
        h = hash_password("correct-horse-battery-staple")
        self.assertFalse(verify_password("wrong-password", h))

    def test_same_password_produces_different_hashes(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        self.assertNotEqual(h1, h2)  # random salt each time
        self.assertTrue(verify_password("same-password", h1))
        self.assertTrue(verify_password("same-password", h2))

    def test_malformed_hash_does_not_crash_verification(self):
        self.assertFalse(verify_password("anything", "not-a-real-hash"))
        self.assertFalse(verify_password("anything", ""))


class TestJWTTokens(unittest.TestCase):
    def test_access_token_round_trips_correctly(self):
        token = create_access_token(user_id=42, org_id=7, role="admin")
        payload = decode_token(token, expected_type="access")
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["org_id"], 7)
        self.assertEqual(payload["role"], "admin")

    def test_refresh_token_round_trips_correctly(self):
        token = create_refresh_token(user_id=42, org_id=7)
        payload = decode_token(token, expected_type="refresh")
        self.assertEqual(payload["sub"], "42")

    def test_wrong_expected_type_is_rejected(self):
        access = create_access_token(user_id=1, org_id=1, role="member")
        with self.assertRaises(TokenError):
            decode_token(access, expected_type="refresh")

    def test_tampered_token_is_rejected(self):
        token = create_access_token(user_id=1, org_id=1, role="member")
        tampered = token[:-5] + "AAAAA"
        with self.assertRaises(TokenError):
            decode_token(tampered)


if __name__ == "__main__":
    unittest.main()
