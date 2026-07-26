"""
SYJ OpenTrade Logic - Rulings search routes (v0.6.0)
=======================================================
GET /rulings/search?q=...&limit=... - standalone BM25 search over the
CROSS rulings sample dataset. Unauthenticated, like /classify -- this is
public-interest legal precedent search, not organization-scoped data.
"""

import os
import sys

from fastapi import APIRouter, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rulings_search import RulingsSearchIndex  # noqa: E402
from server_fastapi.schemas import RulingsSearchResponse  # noqa: E402

router = APIRouter(prefix="/rulings", tags=["rulings"])

_DEFAULT_RULINGS_DATA = os.environ.get(
    "SYJ_RULINGS_DATA_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cross_rulings_sample.json"),
)
rulings_index = RulingsSearchIndex(_DEFAULT_RULINGS_DATA)


@router.get("/search", response_model=RulingsSearchResponse)
def search_rulings(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)):
    results = rulings_index.search(q, top_k=limit)
    return {
        "query": q,
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }
