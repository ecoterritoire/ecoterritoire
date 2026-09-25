import unittest
from unittest.mock import patch

from app.db import hash_token


class TestAuthMiddleware(unittest.TestCase):
    def test_hash_token_sha256(self):
        """Verifie que le hachage d'un token produit bien une chaine hexadecimale SHA-256 de 64 caracteres."""
        token = "eco_test_secret_token_123"
        hashed = hash_token(token)
        self.assertEqual(len(hashed), 64)
        self.assertEqual(hash_token(token), hashed)
        self.assertNotEqual(hash_token("different_token"), hashed)

    def test_routes_with_client(self):
        """Teste les comportements de requete avec TestClient."""
        try:
            from fastapi.testclient import TestClient
            from app.main import app
        except ImportError:
            self.skipTest("fastapi ou psycopg2 n'est pas installe dans l'environnement local")

        client = TestClient(app)

        # 1. Route publique /health
        res_health = client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json(), {"status": "ok"})

        # 2. Route protegee sans header Authorization
        res_missing = client.get("/measurements")
        self.assertEqual(res_missing.status_code, 401)
        self.assertEqual(res_missing.json(), {"detail": "Missing Authorization header"})

        # 3. Route protegee avec mauvais format d'en-tete
        res_bad_format = client.get(
            "/measurements", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        self.assertEqual(res_bad_format.status_code, 401)
        self.assertIn("Invalid Authorization header format", res_bad_format.json()["detail"])

        # 4. Route protegee avec token inexistant / invalide
        with patch("lib.middleware.verify_token_hash", return_value=None):
            res_invalid = client.get(
                "/measurements", headers={"Authorization": "Bearer invalid_token"}
            )
            self.assertEqual(res_invalid.status_code, 401)
            self.assertEqual(
                res_invalid.json(),
                {"detail": "Invalid or inactive authentication token"},
            )

        # 5. Route protegee avec token valide
        raw_token = "eco_valid_token_abc"
        expected_hash = hash_token(raw_token)
        mock_record = {
            "id": 1,
            "token_hash": expected_hash,
            "description": "Test Token",
            "created_at": "2026-09-25T10:00:00Z",
            "last_used_at": None,
            "is_active": True,
        }
        with patch("lib.middleware.verify_token_hash", return_value=mock_record):
            res_valid = client.get(
                "/measurements", headers={"Authorization": f"Bearer {raw_token}"}
            )
            self.assertEqual(res_valid.status_code, 200)
            self.assertIn("data", res_valid.json())


if __name__ == "__main__":
    unittest.main()
