"""
SYJ OpenTrade Logic - CROSS Rulings Semantic(ish) Search (v0.6.0)
===================================================================
The original spec called for embedding-based semantic search over CBP
CROSS rulings via Pinecone/Milvus. Per an explicit decision on this
project, that was replaced with a free, local, zero-dependency lexical
search instead: Okapi BM25, a well-established ranking function (the
same family of algorithm underlying classic search engines before dense
embeddings existed). No API key, no network call, no vector database
server -- runs anywhere Python runs, including Termux.

Honesty note on data: unlike USITC's HTS (which has an official bulk
REST export), CBP's CROSS database has no public bulk-export API --
only a search UI and individual ruling pages. `data/cross_rulings_sample.json`
is therefore a small, hand-curated sample of REAL rulings (not
fabricated), chosen to overlap with the existing HTS demo dataset's
product categories (drills, t-shirts, phones/electronics), each with its
real ruling ID, date, and a faithful excerpt of the actual ruling text.
Expanding this to more rulings means adding more real entries in the
same shape -- there's no "run one importer script" shortcut here the way
there was for HTS, because CBP simply doesn't publish one.

Usage:
    index = RulingsSearchIndex("data/cross_rulings_sample.json")
    results = index.search("cordless drill classification", top_k=3)
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional


def _tokenize(text: str) -> List[str]:
    """
    Same tokenization + lightweight stemming approach as
    core/gri_engine.py, kept as an independent copy here rather than a
    cross-import so this module has zero dependency on the classification
    engine -- rulings search is a standalone capability that could be
    used even without the GRI engine present.
    """
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(t) for t in raw if t]


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


@dataclass
class Ruling:
    id: str
    url: str
    date: str
    title: str
    hts_codes: List[str]
    gri_rules_cited: List[str]
    full_text: str
    _tokens: List[str] = field(default_factory=list, repr=False)


@dataclass
class RulingSearchResult:
    ruling: Ruling
    score: float
    matched_terms: List[str]

    def to_dict(self) -> dict:
        return {
            "id": self.ruling.id,
            "url": self.ruling.url,
            "date": self.ruling.date,
            "title": self.ruling.title,
            "hts_codes": self.ruling.hts_codes,
            "gri_rules_cited": self.ruling.gri_rules_cited,
            "excerpt": self.ruling.full_text,
            "score": round(self.score, 4),
            "matched_terms": self.matched_terms,
        }


class RulingsSearchIndex:
    """
    Okapi BM25 over a small, in-memory ruling corpus. BM25 parameters
    (k1=1.5, b=0.75) are the standard defaults used by most search
    engines (e.g. Elasticsearch's default similarity) -- not tuned
    specifically for this corpus, but a sound, well-understood starting
    point.
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, data_path: str):
        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.rulings: List[Ruling] = []
        for r in raw["rulings"]:
            searchable_text = f"{r['title']} {r['full_text']} {' '.join(r['hts_codes'])}"
            ruling = Ruling(
                id=r["id"],
                url=r["url"],
                date=r["date"],
                title=r["title"],
                hts_codes=r["hts_codes"],
                gri_rules_cited=r.get("gri_rules_cited", []),
                full_text=r["full_text"],
                _tokens=_tokenize(searchable_text),
            )
            self.rulings.append(ruling)

        self._doc_freqs: List[Counter] = [Counter(r._tokens) for r in self.rulings]
        self._doc_lengths: List[int] = [len(r._tokens) for r in self.rulings]
        self._avg_doc_length: float = (
            sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0.0
        )
        self._idf = self._compute_idf()

    def _compute_idf(self) -> dict:
        n_docs = len(self.rulings)
        df = Counter()
        for freqs in self._doc_freqs:
            for term in freqs:
                df[term] += 1

        idf = {}
        for term, freq in df.items():
            # standard BM25 IDF, floored at a small positive value so
            # very common terms never go negative and start subtracting
            idf[term] = max(math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1), 0.01)
        return idf

    def _bm25_score(self, query_tokens: List[str], doc_index: int) -> float:
        score = 0.0
        doc_freqs = self._doc_freqs[doc_index]
        doc_len = self._doc_lengths[doc_index]

        for term in query_tokens:
            if term not in doc_freqs:
                continue
            idf = self._idf.get(term, 0.0)
            freq = doc_freqs[term]
            numerator = freq * (self.K1 + 1)
            denominator = freq + self.K1 * (1 - self.B + self.B * doc_len / max(self._avg_doc_length, 1))
            score += idf * (numerator / denominator)
        return score

    def search(self, query: str, top_k: int = 5, min_score: float = 0.01) -> List[RulingSearchResult]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self.rulings:
            return []

        scored = []
        for i, ruling in enumerate(self.rulings):
            score = self._bm25_score(query_tokens, i)
            if score >= min_score:
                matched = sorted(set(query_tokens) & set(self._doc_freqs[i].keys()))
                scored.append(RulingSearchResult(ruling=ruling, score=score, matched_terms=matched))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def search_by_hts_prefix(self, hts_code: Optional[str], top_k: int = 3) -> List[Ruling]:
        """Find rulings whose hts_codes share a prefix with the given code --
        useful for surfacing precedent related to a specific classification
        result, independent of lexical query matching."""
        if not hts_code:
            return []
        prefix = hts_code.split(".")[0]  # e.g. "8467" from "8467.21.00.10"
        matches = [r for r in self.rulings if any(c.split(".")[0] == prefix for c in r.hts_codes)]
        return matches[:top_k]
