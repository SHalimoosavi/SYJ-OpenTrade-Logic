import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server_fastapi.webhooks import (  # noqa: E402
    sign_payload,
    verify_signature,
    build_payload,
    deliver_webhook,
)


class TestSignatureLogic(unittest.TestCase):
    def test_signature_has_expected_prefix(self):
        sig = sign_payload(b"test payload", "secret")
        self.assertTrue(sig.startswith("sha256="))

    def test_correct_secret_verifies(self):
        payload = b'{"event":"test"}'
        sig = sign_payload(payload, "my-secret")
        self.assertTrue(verify_signature(payload, "my-secret", sig))

    def test_wrong_secret_fails_verification(self):
        payload = b'{"event":"test"}'
        sig = sign_payload(payload, "my-secret")
        self.assertFalse(verify_signature(payload, "wrong-secret", sig))

    def test_tampered_payload_fails_verification(self):
        payload = b'{"event":"test"}'
        sig = sign_payload(payload, "my-secret")
        self.assertFalse(verify_signature(b'{"event":"tampered"}', "my-secret", sig))

    def test_build_payload_has_required_fields(self):
        p = build_payload("product.created", {"sku": "X-1"})
        self.assertEqual(p["event"], "product.created")
        self.assertEqual(p["data"]["sku"], "X-1")
        self.assertIn("timestamp", p)


class _MockReceiver(BaseHTTPRequestHandler):
    """A real HTTP server that independently verifies incoming webhook
    signatures -- exactly what a real webhook consumer would do."""

    secret = "test-webhook-secret-123"
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        sig = self.headers.get("X-SYJ-Signature", "")
        is_valid = verify_signature(body, self.secret, sig)
        self.received.append({
            "body": json.loads(body),
            "valid_signature": is_valid,
            "event_header": self.headers.get("X-SYJ-Event", ""),
        })
        self.send_response(200 if is_valid else 401)
        self.end_headers()

    def log_message(self, *args):
        pass


class TestRealWebhookDelivery(unittest.TestCase):
    """Spins up a REAL local HTTP server and delivers REAL signed webhook
    requests to it -- this is genuine end-to-end verification, not mocked."""

    @classmethod
    def setUpClass(cls):
        _MockReceiver.received = []
        cls.server = HTTPServer(("127.0.0.1", 0), _MockReceiver)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.port}/webhook"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _MockReceiver.received = []

    def test_valid_delivery_succeeds_and_receiver_verifies_signature(self):
        result = deliver_webhook(
            url=self.url,
            secret=_MockReceiver.secret,
            event_type="product.created",
            data={"sku": "DRILL-001", "name": "Cordless Drill"},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(_MockReceiver.received), 1)
        self.assertTrue(_MockReceiver.received[0]["valid_signature"])
        self.assertEqual(_MockReceiver.received[0]["body"]["data"]["sku"], "DRILL-001")
        self.assertEqual(_MockReceiver.received[0]["event_header"], "product.created")

    def test_wrong_secret_is_rejected_by_receiver(self):
        result = deliver_webhook(
            url=self.url,
            secret="WRONG-SECRET",
            event_type="product.created",
            data={"sku": "FAKE"},
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 401)
        self.assertFalse(_MockReceiver.received[0]["valid_signature"])

    def test_delivery_to_unreachable_host_does_not_raise(self):
        # Port 1 on localhost should reliably refuse the connection
        result = deliver_webhook(
            url="http://127.0.0.1:1/webhook",
            secret="any-secret",
            event_type="product.created",
            data={"sku": "X-1"},
        )
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.status_code)

    def test_delivery_result_includes_payload_json(self):
        result = deliver_webhook(
            url=self.url,
            secret=_MockReceiver.secret,
            event_type="classification.created",
            data={"final_code": "8467.21"},
        )
        parsed = json.loads(result.payload_json)
        self.assertEqual(parsed["event"], "classification.created")


if __name__ == "__main__":
    unittest.main()
