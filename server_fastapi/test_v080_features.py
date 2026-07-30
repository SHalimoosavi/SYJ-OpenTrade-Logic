"""
SYJ OpenTrade Logic - v0.8.0 integration tests (audit trails, webhooks, reports)
==================================================================================
Run on your machine:
    python3 -m unittest server_fastapi.test_v080_features -v
"""

import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _TestWebhookReceiver(BaseHTTPRequestHandler):
    """A real local HTTP server that receives and records webhook deliveries
    fired by the actual FastAPI app during these tests."""
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.received.append({
            "body": body,
            "signature": self.headers.get("X-SYJ-Signature", ""),
            "event": self.headers.get("X-SYJ-Event", ""),
        })
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


class TestV080Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".test_tmp")
        os.makedirs(local_tmp_dir, exist_ok=True)
        cls.tmp_db_fd, cls.tmp_db_path = tempfile.mkstemp(suffix=".db", dir=local_tmp_dir)
        os.close(cls.tmp_db_fd)
        os.remove(cls.tmp_db_path)
        os.environ["SYJ_DATABASE_URL"] = f"sqlite:///{cls.tmp_db_path}"
        os.environ["SYJ_SECRET_KEY"] = "test-secret-key-not-for-production"

        sample_data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json"
        )
        os.environ["SYJ_HTS_DATA_PATH"] = sample_data_path

        from fastapi.testclient import TestClient
        from server_fastapi.database import init_db
        from server_fastapi.main import app

        init_db()
        cls.client = TestClient(app)

        # Real local webhook receiver
        cls.receiver_server = HTTPServer(("127.0.0.1", 0), _TestWebhookReceiver)
        cls.receiver_port = cls.receiver_server.server_address[1]
        cls.receiver_thread = threading.Thread(target=cls.receiver_server.serve_forever, daemon=True)
        cls.receiver_thread.start()
        cls.receiver_url = f"http://127.0.0.1:{cls.receiver_port}/webhook"

    @classmethod
    def tearDownClass(cls):
        cls.receiver_server.shutdown()
        if os.path.exists(cls.tmp_db_path):
            os.remove(cls.tmp_db_path)

    def _register_owner(self, org_name, email):
        resp = self.client.post("/auth/register", json={
            "organization_name": org_name, "email": email,
            "password": "Sup3rSecret!", "full_name": "Test Owner",
        })
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    # --- Audit trail tests ---

    def test_product_creation_is_audit_logged(self):
        tokens = self._register_owner("AuditCo", "owner@auditco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/products", json={"sku": "A-1", "name": "Widget"}, headers=headers)

        log = self.client.get("/audit-log", headers=headers)
        self.assertEqual(log.status_code, 200)
        actions = [entry["action"] for entry in log.json()["results"]]
        self.assertIn("product.created", actions)

    def test_role_change_is_audit_logged(self):
        tokens = self._register_owner("RoleAuditCo", "owner@roleaudit.test")
        headers = self._headers(tokens["access_token"])
        invited = self.client.post("/organizations/members", json={
            "email": "member@roleaudit.test", "password": "MemberPass123!",
            "full_name": "Member", "role": "member",
        }, headers=headers).json()

        self.client.put(f"/organizations/members/{invited['id']}/role", json={"role": "admin"}, headers=headers)

        log = self.client.get("/audit-log", headers=headers)
        actions = [entry["action"] for entry in log.json()["results"]]
        self.assertIn("member.role_changed", actions)
        self.assertIn("member.invited", actions)

    def test_authenticated_classify_is_audit_logged_and_org_scoped(self):
        tokens = self._register_owner("ClassifyAuditCo", "owner@classifyaudit.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/classify", json={"description": "cordless electric drill"}, headers=headers)

        log = self.client.get("/audit-log", headers=headers)
        actions = [entry["action"] for entry in log.json()["results"]]
        self.assertIn("classification.created", actions)

    def test_viewer_cannot_access_audit_log(self):
        tokens = self._register_owner("ViewerAuditCo", "owner@viewerauditco.test")
        owner_headers = self._headers(tokens["access_token"])
        self.client.post("/organizations/members", json={
            "email": "viewer@viewerauditco.test", "password": "ViewerPass123!",
            "full_name": "Viewer", "role": "viewer",
        }, headers=owner_headers)
        viewer_login = self.client.post("/auth/login", json={"email": "viewer@viewerauditco.test", "password": "ViewerPass123!"})
        viewer_headers = self._headers(viewer_login.json()["access_token"])

        resp = self.client.get("/audit-log", headers=viewer_headers)
        self.assertEqual(resp.status_code, 403)

    # --- Webhook tests ---

    def test_create_webhook_returns_secret_once(self):
        tokens = self._register_owner("WebhookCo", "owner@webhookco.test")
        headers = self._headers(tokens["access_token"])
        resp = self.client.post("/webhooks", json={
            "url": self.receiver_url, "event_types": ["product.created"],
        }, headers=headers)
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertIsNotNone(resp.json()["secret"])

    def test_listing_webhooks_does_not_expose_secret(self):
        tokens = self._register_owner("WebhookListCo", "owner@webhooklistco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["product.created"]}, headers=headers)

        listing = self.client.get("/webhooks", headers=headers)
        self.assertEqual(listing.status_code, 200)
        self.assertIsNone(listing.json()["results"][0]["secret"])

    def test_product_creation_fires_real_webhook_delivery(self):
        _TestWebhookReceiver.received = []
        tokens = self._register_owner("WebhookFireCo", "owner@webhookfireco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["product.created"]}, headers=headers)

        self.client.post("/products", json={"sku": "WH-1", "name": "Webhook Test Product"}, headers=headers)

        self.assertEqual(len(_TestWebhookReceiver.received), 1)
        delivery = _TestWebhookReceiver.received[0]
        self.assertEqual(delivery["event"], "product.created")
        self.assertTrue(delivery["signature"].startswith("sha256="))

    def test_webhook_only_fires_for_subscribed_event_types(self):
        _TestWebhookReceiver.received = []
        tokens = self._register_owner("WebhookFilterCo", "owner@webhookfilterco.test")
        headers = self._headers(tokens["access_token"])
        # Subscribe ONLY to product.deleted -- product.created should NOT fire
        self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["product.deleted"]}, headers=headers)

        self.client.post("/products", json={"sku": "WH-2", "name": "Should Not Trigger"}, headers=headers)
        self.assertEqual(len(_TestWebhookReceiver.received), 0)

    def test_webhook_test_endpoint_delivers_real_request(self):
        tokens = self._register_owner("WebhookTestCo", "owner@webhooktestco.test")
        headers = self._headers(tokens["access_token"])
        created = self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["webhook.test"]}, headers=headers).json()

        resp = self.client.post(f"/webhooks/{created['id']}/test", json={"event_type": "webhook.test"}, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

    def test_delivery_history_is_retrievable(self):
        tokens = self._register_owner("WebhookHistoryCo", "owner@webhookhistoryco.test")
        headers = self._headers(tokens["access_token"])
        created = self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["webhook.test"]}, headers=headers).json()
        self.client.post(f"/webhooks/{created['id']}/test", json={"event_type": "webhook.test"}, headers=headers)

        deliveries = self.client.get(f"/webhooks/{created['id']}/deliveries", headers=headers)
        self.assertEqual(deliveries.status_code, 200)
        self.assertGreater(len(deliveries.json()), 0)

    def test_viewer_cannot_create_webhooks(self):
        tokens = self._register_owner("WebhookRBACCo", "owner@webhookrbacco.test")
        owner_headers = self._headers(tokens["access_token"])
        self.client.post("/organizations/members", json={
            "email": "viewer@webhookrbacco.test", "password": "ViewerPass123!",
            "full_name": "Viewer", "role": "viewer",
        }, headers=owner_headers)
        viewer_login = self.client.post("/auth/login", json={"email": "viewer@webhookrbacco.test", "password": "ViewerPass123!"})
        viewer_headers = self._headers(viewer_login.json()["access_token"])

        resp = self.client.post("/webhooks", json={"url": self.receiver_url, "event_types": ["product.created"]}, headers=viewer_headers)
        self.assertEqual(resp.status_code, 403)

    # --- Reports tests ---

    def test_export_classifications_csv(self):
        tokens = self._register_owner("ReportCsvCo", "owner@reportcsvco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/classify", json={"description": "cordless electric drill"}, headers=headers)

        resp = self.client.get("/reports/classifications/csv", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("cordless electric drill", resp.text)
        self.assertEqual(resp.headers["content-type"], "text/csv; charset=utf-8")

    def test_export_classifications_excel(self):
        tokens = self._register_owner("ReportXlsxCo", "owner@reportxlsxco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/classify", json={"description": "cordless electric drill"}, headers=headers)

        resp = self.client.get("/reports/classifications/excel", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content[:2] == b"PK")  # xlsx is a zip archive

    def test_export_products_csv(self):
        tokens = self._register_owner("ReportProductsCo", "owner@reportproductsco.test")
        headers = self._headers(tokens["access_token"])
        self.client.post("/products", json={"sku": "RP-1", "name": "Report Product"}, headers=headers)

        resp = self.client.get("/reports/products/csv", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("RP-1", resp.text)

    def test_export_classification_pdf(self):
        tokens = self._register_owner("ReportPdfCo", "owner@reportpdfco.test")
        headers = self._headers(tokens["access_token"])
        created = self.client.post("/classify", json={"description": "cordless electric drill"}, headers=headers).json()

        resp = self.client.get(f"/reports/classifications/{created['id']}/pdf", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content[:4] == b"%PDF")

    def test_pdf_report_404_for_other_organizations_classification(self):
        tokens_a = self._register_owner("ReportOrgACo", "owner@reportorgaco.test")
        tokens_b = self._register_owner("ReportOrgBCo", "owner@reportorgbco.test")
        created = self.client.post(
            "/classify", json={"description": "cordless electric drill"}, headers=self._headers(tokens_a["access_token"])
        ).json()

        resp = self.client.get(
            f"/reports/classifications/{created['id']}/pdf", headers=self._headers(tokens_b["access_token"])
        )
        self.assertEqual(resp.status_code, 404)

    def test_reports_require_authentication(self):
        resp = self.client.get("/reports/products/csv")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
