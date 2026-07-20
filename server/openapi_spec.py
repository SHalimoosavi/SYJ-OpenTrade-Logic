"""
Hand-authored OpenAPI 3.0 document describing server/app.py's routes.
Served live at GET /openapi.json. Once ported to FastAPI (v0.3.0+),
this becomes auto-generated instead of hand-maintained.
"""

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "SYJ OpenTrade Logic API",
        "version": "0.2.0",
        "description": "Deterministic, explainable HTS classification REST API.",
        "license": {"name": "Apache-2.0"},
    },
    "paths": {
        "/health": {
            "get": {
                "summary": "Liveness check",
                "responses": {"200": {"description": "Service is up"}},
            }
        },
        "/classify": {
            "post": {
                "summary": "Classify a product description under the HTS",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["description"],
                                "properties": {
                                    "description": {"type": "string", "example": "cordless electric drill"}
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {"description": "Classification created and persisted"},
                    "422": {"description": "Missing or invalid 'description' field"},
                },
            }
        },
        "/classifications": {
            "get": {
                "summary": "List classification history",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                ],
                "responses": {"200": {"description": "Paginated history"}},
            }
        },
        "/classifications/{id}": {
            "get": {
                "summary": "Fetch a single classification record",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Record found"}, "404": {"description": "Not found"}},
            },
            "delete": {
                "summary": "Delete a classification record",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Deleted"}, "404": {"description": "Not found"}},
            },
        },
    },
}
