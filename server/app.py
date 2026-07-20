"""
SYJ OpenTrade Logic - REST API Server (v0.2.0)
=================================================
Built on Python's stdlib `http.server` because this environment has no
network access to install FastAPI/uvicorn/SQLAlchemy. Every route below is
written so it maps 1:1 onto a FastAPI route -- see the docstring on each
handler for the equivalent FastAPI decorator you'd use once those packages
are available. This is a real, running HTTP server, not a mock.

Endpoints
---------
GET    /health                     -> liveness check
POST   /classify                   -> classify a product description
GET    /classifications            -> list classification history (paginated)
GET    /classifications/{id}       -> fetch one classification record
DELETE /classifications/{id}       -> delete one classification record
GET    /openapi.json               -> hand-written OpenAPI 3.0 spec

Run:
    python3 server/app.py --port 8000 --db syj_opentrade.db
"""

import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gri_engine import GRIEngine  # noqa: E402
from server.db import ClassificationStore  # noqa: E402
from server.openapi_spec import OPENAPI_SPEC  # noqa: E402

DEFAULT_HTS_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json"
)

ROUTE_RECORD_BY_ID = re.compile(r"^/classifications/(\d+)$")


class Handlers:
    """Route handler logic, separated from HTTP plumbing so it's unit-testable
    directly (see tests/test_api.py) without spinning up a socket."""

    def __init__(self, engine: GRIEngine, store: ClassificationStore):
        self.engine = engine
        self.store = store

    def health(self):
        # Equivalent FastAPI: @app.get("/health")
        return 200, {"status": "ok", "service": "SYJ OpenTrade Logic", "version": "0.2.0"}

    def classify(self, body: dict):
        # Equivalent FastAPI: @app.post("/classify") def classify(req: ClassifyRequest)
        description = (body or {}).get("description")
        if not isinstance(description, str) or not description.strip():
            return 422, {"error": "Field 'description' is required and must be a non-empty string."}

        result = self.engine.classify(description)
        result_dict = result.to_dict()
        record_id = self.store.save(result_dict)
        return 201, {"id": record_id, **result_dict}

    def list_classifications(self, query: dict):
        # Equivalent FastAPI: @app.get("/classifications")
        try:
            limit = max(1, min(int(query.get("limit", ["50"])[0]), 200))
            offset = max(0, int(query.get("offset", ["0"])[0]))
        except ValueError:
            return 422, {"error": "limit and offset must be integers"}

        records = self.store.list(limit=limit, offset=offset)
        return 200, {"count": self.store.count(), "limit": limit, "offset": offset, "results": records}

    def get_classification(self, record_id: int):
        # Equivalent FastAPI: @app.get("/classifications/{record_id}")
        record = self.store.get(record_id)
        if record is None:
            return 404, {"error": f"No classification record with id {record_id}"}
        return 200, record

    def delete_classification(self, record_id: int):
        # Equivalent FastAPI: @app.delete("/classifications/{record_id}")
        deleted = self.store.delete(record_id)
        if not deleted:
            return 404, {"error": f"No classification record with id {record_id}"}
        return 200, {"deleted": True, "id": record_id}

    def openapi(self):
        return 200, OPENAPI_SPEC


def make_request_handler(handlers: Handlers):
    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "SYJOpenTradeLogic/0.2.0"

        def log_message(self, fmt, *args):
            pass  # keep test output clean; real deployments would wire real logging

        def _send_json(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON body")

        def do_GET(self):
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)

            if path == "/health":
                status, payload = handlers.health()
            elif path == "/openapi.json":
                status, payload = handlers.openapi()
            elif path == "/classifications":
                status, payload = handlers.list_classifications(query)
            else:
                m = ROUTE_RECORD_BY_ID.match(path)
                if m:
                    status, payload = handlers.get_classification(int(m.group(1)))
                else:
                    status, payload = 404, {"error": f"No route for GET {path}"}

            self._send_json(status, payload)

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/classify":
                try:
                    body = self._read_json_body()
                except ValueError as e:
                    self._send_json(400, {"error": str(e)})
                    return
                status, payload = handlers.classify(body)
            else:
                status, payload = 404, {"error": f"No route for POST {path}"}
            self._send_json(status, payload)

        def do_DELETE(self):
            path = urlparse(self.path).path
            m = ROUTE_RECORD_BY_ID.match(path)
            if m:
                status, payload = handlers.delete_classification(int(m.group(1)))
            else:
                status, payload = 404, {"error": f"No route for DELETE {path}"}
            self._send_json(status, payload)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return RequestHandler


def build_server(port: int, db_path: str, hts_data_path: str = DEFAULT_HTS_DATA):
    engine = GRIEngine(hts_data_path)
    store = ClassificationStore(db_path)
    handlers = Handlers(engine, store)
    handler_cls = make_request_handler(handlers)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
    return httpd, handlers


def main():
    parser = argparse.ArgumentParser(description="SYJ OpenTrade Logic API server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="syj_opentrade.db")
    parser.add_argument("--data", default=DEFAULT_HTS_DATA)
    args = parser.parse_args()

    httpd, _ = build_server(args.port, args.db, args.data)
    print(f"SYJ OpenTrade Logic API listening on http://0.0.0.0:{args.port}")
    print(f"  DB: {args.db}")
    print(f"  OpenAPI: http://0.0.0.0:{args.port}/openapi.json")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
