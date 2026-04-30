"""Fuzzy product name matching against the backend catalog."""
from __future__ import annotations

import re


def _tokenize(name: str) -> set[str]:
    """Lowercase, strip punctuation, split into tokens."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    return set(name.split())


def _score(query_tokens: set[str], candidate_name: str) -> float:
    """
    Return a match score 0–1 between a query token set and a catalog product name.
    Score = fraction of query tokens found in candidate tokens.
    A perfect match on all tokens scores 1.0.
    """
    candidate_tokens = _tokenize(candidate_name)
    if not query_tokens or not candidate_tokens:
        return 0.0
    matches = query_tokens & candidate_tokens
    return len(matches) / len(query_tokens)


def find_best_match(
    name: str,
    products: list[dict],
    threshold: float = 0.5,
) -> dict | None:
    """
    Return the best-matching product from the catalog, or None if score < threshold.

    Args:
        name: raw product name from voice/NLP
        products: list of product dicts from GET /products
        threshold: minimum score to accept a match (0.5 = half the words must match)
    """
    query_tokens = _tokenize(name)
    best_score = 0.0
    best_product = None

    for product in products:
        score = _score(query_tokens, product["name"])
        if score > best_score:
            best_score = score
            best_product = product

    if best_score >= threshold:
        return best_product
    return None


def rank_matches(
    name: str,
    products: list[dict],
    threshold: float = 0.4,
    top_n: int = 3,
) -> list[dict]:
    """Return top_n products sorted by match score, filtered by threshold."""
    query_tokens = _tokenize(name)
    scored = [
        (product, _score(query_tokens, product["name"]))
        for product in products
    ]
    scored = [(p, s) for p, s in scored if s >= threshold]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:top_n]]
