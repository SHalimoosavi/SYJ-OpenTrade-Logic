"""
SYJ OpenTrade Logic - GRI Classification Engine
=================================================
A deterministic, explainable engine for classifying products under the
Harmonized Tariff Schedule using the General Rules of Interpretation (GRI).

Design:
    - The HTS tree (chapter -> heading -> subheading) is a Directed Acyclic
      Graph. Classification is a graph traversal, not a black-box model.
    - GRI 1: classify at the heading level using the terms of the heading
      and any relevant chapter/section legal notes.
    - GRI 6: once a heading is fixed, classify at the subheading level using
      the same principle, comparing subheadings at the same level only.
    - GRI 3(a)/(b): when two+ headings/subheadings score similarly, prefer
      the most specific description (3a) then note essential-character
      tie-breaking is required for composite goods (3b) -- flagged, not
      guessed.
    - Every step taken is recorded as a DecisionStep so the full path is
      auditable. No step is hidden.

This module has ZERO third-party dependencies -- stdlib only -- so it runs
identically in a full server deployment or on a bare Termux install.
"""

import json
import re
from typing import List, Optional, Tuple

from core.models import (
    HTSNode,
    DecisionStep,
    AlternativeCode,
    ClassificationResult,
    GRIRule,
)


def _stem(word: str) -> str:
    """
    Lightweight suffix-stripping normalizer -- NOT a real linguistic
    stemmer, just enough to match plural/singular HTS legal text against
    everyday singular product words. e.g. HTS says "Drills of all kinds";
    a user types "drill". Without this, those never match as the same
    token, which was found to cause real misclassification (see
    scripts/import_hts_data.py docstring, Chapter 99 bug).

    IMPORTANT (found via live spot-checking on real data): an earlier
    version of this function also stripped trailing "es" as a special
    case (for words like "boxes" -> "box"). That broke a much more common
    and important class of words in trade/product vocabulary: nouns that
    already end in a silent "e" before taking a plural "s" -- "phone" ->
    "phones", "case" -> "cases", "code" -> "codes", "smartphone" ->
    "smartphones". Stripping "es" from "smartphones" gave "smartphon"
    (missing the final e), which silently failed to match the query word
    "smartphone" and let a Chapter 99 phone-CASE special provision
    outrank the real heading 8517 for phones. Given how common
    silent-e-plus-s nouns are in this domain (phone, case, device,
    machine, engine, cable, tube...) versus the sibilant-plural pattern
    ("boxes", "watches") this rule was meant for, only stripping a single
    trailing "s" is the safer default here -- even though it means a
    word like "boxes" stems to "boxe" rather than "box".
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokenize(text: str) -> List[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(t) for t in raw if t]


SYNTHESIZED_HEADING_MARKER = "[Ungrouped entries under chapter"
SYNTHESIZED_HEADING_PENALTY = 0.6  # de-prioritize structurally-incomplete headings on near-ties


def _score_node(tokens: List[str], node: HTSNode) -> float:
    """
    Score how well a description's tokens match a node's keywords +
    description text. Pure lexical overlap -- deterministic, explainable,
    no ML black box. Returns a value in [0, 1].
    """
    if not tokens:
        return 0.0

    haystack_terms = set()
    for kw in node.keywords:
        haystack_terms.update(_tokenize(kw))
    haystack_terms.update(_tokenize(node.description))

    if not haystack_terms:
        return 0.0

    matches = sum(1 for t in tokens if t in haystack_terms)
    # Reward keyword-list hits more heavily than plain description overlap
    keyword_hits = sum(1 for t in tokens if t in {tk for kw in node.keywords for tk in _tokenize(kw)})

    base = matches / max(len(tokens), 1)
    bonus = 0.15 * min(keyword_hits, 3)
    return min(base + bonus, 1.0)


def _effective_heading_score(tokens: List[str], heading: HTSNode) -> float:
    """
    Score a heading for GRI 1 ranking purposes. Real HTS heading text is
    often terse legal language (e.g. "Automatic data processing machines
    and units thereof") that doesn't contain the everyday product words a
    user actually types ("laptop"). Those words usually live at the
    subheading level. So a heading's effective score is the BETTER of:
      (a) its own description/keyword match, or
      (b) the best match among its direct subheadings.
    This keeps GRI 1 meaningful (we still rank and select a heading first)
    while not penalizing headings whose subheadings are more specific than
    the heading text itself -- which is normal, not an edge case, once you
    load the real 99-chapter dataset instead of hand-curated sample data.
    """
    own_score = _score_node(tokens, heading)
    if not heading.children:
        result = own_score
    else:
        best_child_score = max((_score_node(tokens, c) for c in heading.children), default=0.0)
        result = max(own_score, best_child_score)

    if heading.description.startswith(SYNTHESIZED_HEADING_MARKER):
        result *= SYNTHESIZED_HEADING_PENALTY
    return result


class GRIEngine:
    def __init__(self, hts_data_path: str):
        with open(hts_data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.chapters: List[HTSNode] = [self._build_node(c, None) for c in raw["chapters"]]

    def _build_node(self, raw: dict, parent_code: Optional[str]) -> HTSNode:
        node = HTSNode(
            code=raw["code"],
            description=raw["description"],
            level=raw["level"],
            keywords=raw.get("keywords", []),
            legal_notes=raw.get("legal_notes", []),
            duty_rate=raw.get("duty_rate"),
            parent_code=parent_code,
        )
        node.children = [self._build_node(c, node.code) for c in raw.get("children", [])]
        return node

    def _all_headings(self) -> List[Tuple[HTSNode, HTSNode]]:
        """Return (chapter, heading) pairs across the whole DAG.
        Defensively filters to level=='heading' only -- a malformed import
        (e.g. a subheading/leaf node attached directly under a chapter due
        to missing intermediate structure) must never be scored as if it
        were a heading."""
        pairs = []
        for chapter in self.chapters:
            for heading in chapter.children:
                if heading.level == "heading":
                    pairs.append((chapter, heading))
        return pairs

    def classify(self, product_description: str) -> ClassificationResult:
        tokens = _tokenize(product_description)
        decision_path: List[DecisionStep] = []
        supporting_notes: List[str] = []

        if not tokens:
            return ClassificationResult(
                product_description=product_description,
                final_code=None,
                final_description=None,
                confidence=0.0,
                decision_path=[],
                alternatives=[],
                supporting_notes=[],
                is_classified=False,
                unresolved_reason="Empty or non-textual product description provided.",
            )

        # ---- Step 1 (GRI 1): score every heading in the DAG ----
        heading_scores: List[Tuple[float, HTSNode, HTSNode]] = []
        for chapter, heading in self._all_headings():
            score = _effective_heading_score(tokens, heading)
            heading_scores.append((score, chapter, heading))

        heading_scores.sort(key=lambda x: x[0], reverse=True)
        top_score, top_chapter, top_heading = heading_scores[0]

        if top_score <= 0.0:
            return ClassificationResult(
                product_description=product_description,
                final_code=None,
                final_description=None,
                confidence=0.0,
                decision_path=[],
                alternatives=[],
                supporting_notes=[],
                is_classified=False,
                unresolved_reason=(
                    "No heading in the loaded HTS dataset matched the product "
                    "description terms. This is a demonstration dataset with a "
                    "small sample of headings -- expand data/hts_sample.json "
                    "with the full HTS schedule for production use."
                ),
            )

        decision_path.append(
            DecisionStep(
                node_code=top_heading.code,
                node_description=top_heading.description,
                rule_applied=GRIRule.GRI_1,
                reasoning=(
                    f"Heading {top_heading.code} scored highest ({top_score:.2f}) "
                    f"against the terms of the heading, per GRI 1: classification "
                    f"is determined by the terms of the headings and relevant "
                    f"section/chapter notes."
                ),
                score=top_score,
            )
        )
        if top_chapter.legal_notes:
            supporting_notes.extend(top_chapter.legal_notes)
        if top_heading.legal_notes:
            supporting_notes.extend(top_heading.legal_notes)

        # Check for a close competing heading -> GRI 3(a) flag
        runner_up_headings = [h for h in heading_scores[1:4] if h[0] > 0]
        if runner_up_headings and (top_score - runner_up_headings[0][0]) < 0.10:
            comp_score, comp_chapter, comp_heading = runner_up_headings[0]
            decision_path.append(
                DecisionStep(
                    node_code=comp_heading.code,
                    node_description=comp_heading.description,
                    rule_applied=GRIRule.GRI_3A,
                    reasoning=(
                        f"Heading {comp_heading.code} scored closely ({comp_score:.2f} "
                        f"vs {top_score:.2f}). Per GRI 3(a), the heading providing the "
                        f"most specific description is preferred over a more general one; "
                        f"{top_heading.code} was retained as more specific to the stated terms."
                    ),
                    score=comp_score,
                )
            )

        # ---- Step 2 (GRI 6): score subheadings under the chosen heading ----
        alternatives: List[AlternativeCode] = []
        final_node = top_heading
        final_score = top_score

        if top_heading.children:
            sub_scores = [(_score_node(tokens, c), c) for c in top_heading.children]
            sub_scores.sort(key=lambda x: x[0], reverse=True)
            best_sub_score, best_sub = sub_scores[0]

            if best_sub_score > 0:
                decision_path.append(
                    DecisionStep(
                        node_code=best_sub.code,
                        node_description=best_sub.description,
                        rule_applied=GRIRule.GRI_6,
                        reasoning=(
                            f"Subheading {best_sub.code} scored highest ({best_sub_score:.2f}) "
                            f"among subheadings of {top_heading.code}, per GRI 6: subheadings "
                            f"at the same level are compared using the same GRI 1-3 principles."
                        ),
                        score=best_sub_score,
                    )
                )
                final_node = best_sub
                final_score = (top_score + best_sub_score) / 2

                for s, alt in sub_scores[1:3]:
                    if s > 0:
                        alternatives.append(
                            AlternativeCode(
                                code=alt.code,
                                description=alt.description,
                                confidence=round(s, 4),
                                reason_not_selected=(
                                    f"Lower lexical match score ({s:.2f}) against product "
                                    f"description terms than {best_sub.code} ({best_sub_score:.2f})."
                                ),
                            )
                        )
            else:
                supporting_notes.append(
                    f"No subheading under {top_heading.code} matched specifically; "
                    f"classification rests at the heading level pending fuller product detail."
                )

        for s, chapter, heading in heading_scores[1:3]:
            if s > 0 and heading.code != final_node.code:
                alternatives.append(
                    AlternativeCode(
                        code=heading.code,
                        description=heading.description,
                        confidence=round(s, 4),
                        reason_not_selected=(
                            f"Lower heading-level match score ({s:.2f}) than the selected "
                            f"heading {top_heading.code} ({top_score:.2f})."
                        ),
                    )
                )

        return ClassificationResult(
            product_description=product_description,
            final_code=final_node.code,
            final_description=final_node.description,
            confidence=final_score,
            decision_path=decision_path,
            alternatives=alternatives,
            supporting_notes=supporting_notes,
            duty_rate=getattr(final_node, "duty_rate", None),
            is_classified=True,
        )
