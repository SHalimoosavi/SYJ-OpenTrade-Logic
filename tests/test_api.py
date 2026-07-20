"""
SYJ OpenTrade Logic - API integration tests
=============================================
These tests start a REAL server (server/app.py) on a background thread
bound to a real TCP port, and make REAL HTTP requests against it using
urllib (stdlib -- no `requests` package available). Nothing here is a
mock. Each test run uses a fresh temp SQLite file so tests are isolated
and repeatable.
"""

import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app import build_server  # noqa: E402

HOST = "127.0.0.1"


class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.db_fd)
        os.remove(cls.db_path)  # let ClassificationStore create it fresh

        cls.httpd, _ = build_server(port=0, db_path=cls.db_path)  # port=0 -> OS picks a free port
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://{HOST}:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.server_thread.join(timeout=5)
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def _request(self, method: str, path: str, body: dict = None):
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health_endpoint_is_live(self):
        status, payload = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_classify_laptop_over_http(self):
        status, payload = self._request("POST", "/classify", {"description": "portable laptop notebook computer"})
        self.assertEqual(status, 201)
        self.assertEqual(payload["final_code"], "8471.30")
        self.assertIn("id", payload)
        self.assertGreater(len(payload["decision_path"]), 0)

    def test_classify_missing_description_returns_422(self):
        status, payload = self._request("POST", "/classify", {})
        self.assertEqual(status, 422)
        self.assertIn("error", payload)

    def test_classify_persists_and_is_retrievable(self):
        status, created = self._request("POST", "/classify", {"description": "cordless electric drill"})
        self.assertEqual(status, 201)
        record_id = created["id"]

        status, fetched = self._request("GET", f"/classifications/{record_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["final_code"], "8467.21")
        self.assertEqual(fetched["id"], record_id)

    def test_get_nonexistent_record_returns_404(self):
        status, payload = self._request("GET", "/classifications/999999")
        self.assertEqual(status, 404)

    def test_list_classifications_reflects_persisted_data(self):
        self._request("POST", "/classify", {"description": "android smartphone"})
        status, payload = self._request("GET", "/classifications?limit=100")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertTrue(any(r["final_code"] == "8517.13" for r in payload["results"]))

    def test_delete_classification_removes_it(self):
        status, created = self._request("POST", "/classify", {"description": "wifi router modem"})
        record_id = created["id"]

        status, payload = self._request("DELETE", f"/classifications/{record_id}")
        self.assertEqual(status, 200)
        self.assertTrue(payload["deleted"])

        status, payload = self._request("GET", f"/classifications/{record_id}")
        self.assertEqual(status, 404)

    def test_delete_nonexistent_record_returns_404(self):
        status, payload = self._request("DELETE", "/classifications/999999")
        self.assertEqual(status, 404)

    def test_openapi_spec_is_served_and_valid_json(self):
        status, payload = self._request("GET", "/openapi.json")
        self.assertEqual(status, 200)
        self.assertEqual(payload["openapi"], "3.0.3")
        self.assertIn("/classify", payload["paths"])

    def test_data_actually_persisted_to_sqlite_file_on_disk(self):
        """Belt-and-braces: bypass the API entirely and read the SQLite file
        directly to prove this isn't an in-memory mock."""
        self._request("POST", "/classify", {"description": "cotton knitted t-shirt"})
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
        conn.close()
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
