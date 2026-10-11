"""
apps/resorts/search.py — Find a resort by typing part of its name.

There are only a couple of hundred resorts, so the search runs in Python,
which makes it accent-blind ("champery" finds Champéry) on any database.
Matches at the start of the name, or of a word in it, rank first.
"""

from __future__ import annotations

import unicodedata

from .models import Resort

SEARCH_LIMIT = 8


def fold(text: str) -> str:
    """Return ``text`` lowercased with accents removed."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _rank(name: str, code: str, query: str) -> int | None:
    """Return how well a resort matches (lower is better), or None."""
    folded = fold(name)
    if code and fold(code) == query:
        return 0
    if folded.startswith(query):
        return 1
    if any(word.startswith(query) for word in folded.replace("-", " ").split()):
        return 2
    if query in folded:
        return 3
    return None


def search_resorts(query: str, limit: int = SEARCH_LIMIT) -> list[Resort]:
    """Return up to ``limit`` resorts matching ``query``, best first."""
    query = fold(query.strip())
    if not query:
        return []
    ranked = []
    for resort in Resort.objects.prefetch_related("passes"):
        rank = _rank(resort.name, resort.code, query)
        if rank is not None:
            ranked.append((rank, resort.name.lower(), resort))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [resort for _, _, resort in ranked[:limit]]
