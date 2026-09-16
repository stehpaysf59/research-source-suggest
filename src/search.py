"""Ranked search over the journals/conferences universe.

For MVP this uses SQLite FTS5 (already built into the canonical database by
the data pipeline) plus a handful of exact-match lookups for identifiers.
Ranking is resolved in Python (small result sets) rather than a single
mega-SQL statement, so the ranking rules stay easy to read and change without
touching the calling pages. If a full search engine (e.g. Meilisearch) is
ever introduced, only this module should need to change.
"""

from __future__ import annotations

import re
import sqlite3

# Hard cap on how many rows a single full-text match pulls back, so a very
# broad one-word query can't drag the whole ~50k-row universe into memory.
_FTS_RESULT_CAP = 5000

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _normalize_issn(value: str) -> str:
    text = value.strip().upper().replace("-", "")
    if len(text) == 7 and text[:-1].isdigit():
        text = "0" + text
    return text


def _fts_tokens(term: str) -> str:
    tokens = [tok for tok in _NON_ALNUM.split(term) if tok]
    if not tokens:
        return ""
    return " ".join(f"{tok}*" for tok in tokens)


def _fts_match_ids(conn: sqlite3.Connection, table: str, term: str) -> set[str]:
    query = _fts_tokens(term)
    if not query:
        return set()
    try:
        rows = conn.execute(
            f"SELECT source_id FROM {table} WHERE {table} MATCH ? LIMIT ?", (query, _FTS_RESULT_CAP)
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {row[0] for row in rows}


def search_journals(conn: sqlite3.Connection, term: str) -> dict[str, int]:
    """Return {source_id: rank_tier} for journals/other-serial-source matches.

    Lower tier = stronger match. Priority: exact Source ID (0), exact
    ISSN/EISSN (1), exact title (2), full-text/prefix (3), publisher text (4).
    """
    term = term.strip()
    if not term:
        return {}
    tiers: dict[str, int] = {}

    for (source_id,) in conn.execute(
        "SELECT source_id FROM sources WHERE source_group = 'scopus_serial_source' AND source_id = ?", (term,)
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 0)

    norm_issn = _normalize_issn(term)
    if norm_issn:
        for (source_id,) in conn.execute(
            "SELECT source_id FROM sources WHERE source_group = 'scopus_serial_source' "
            "AND (issn_normalized = ? OR eissn_normalized = ?)",
            (norm_issn, norm_issn),
        ):
            tiers[source_id] = min(tiers.get(source_id, 9), 1)

    for (source_id,) in conn.execute(
        "SELECT source_id FROM sources WHERE source_group = 'scopus_serial_source' AND lower(source_title) = ?",
        (term.lower(),),
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 2)

    for source_id in _fts_match_ids(conn, "fts_journals", term):
        tiers[source_id] = min(tiers.get(source_id, 9), 3)

    for (source_id,) in conn.execute(
        "SELECT source_id FROM sources WHERE source_group = 'scopus_serial_source' AND publisher LIKE ? LIMIT ?",
        (f"%{term}%", _FTS_RESULT_CAP),
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 4)

    return tiers


def search_conferences(conn: sqlite3.Connection, term: str) -> dict[str, int]:
    """Return {source_id: rank_tier} for conference-source matches.

    Priority: exact Source ID (0), exact ICORE acronym (1), exact ICORE title
    (2), exact Scopus source title (3), full-text/prefix (4), QS subject/FoR
    text (5).
    """
    term = term.strip()
    if not term:
        return {}
    tiers: dict[str, int] = {}

    for (source_id,) in conn.execute(
        "SELECT source_id FROM sources WHERE source_group = 'serial_conference_profile' AND source_id = ?", (term,)
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 0)

    norm_issn = _normalize_issn(term)
    if norm_issn:
        for (source_id,) in conn.execute(
            "SELECT source_id FROM sources WHERE source_group = 'serial_conference_profile' "
            "AND (issn_normalized = ? OR eissn_normalized = ?)",
            (norm_issn, norm_issn),
        ):
            tiers[source_id] = min(tiers.get(source_id, 9), 1)

    for (source_id,) in conn.execute(
        "SELECT source_id FROM source_icore WHERE lower(icore_acronym) = ?", (term.lower(),)
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 1)

    for (source_id,) in conn.execute(
        "SELECT source_id FROM source_icore WHERE lower(icore_conference_title) = ?", (term.lower(),)
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 2)

    for (source_id,) in conn.execute(
        "SELECT source_id FROM sources WHERE source_group = 'serial_conference_profile' AND lower(source_title) = ?",
        (term.lower(),),
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 3)

    for source_id in _fts_match_ids(conn, "fts_conferences", term):
        tiers[source_id] = min(tiers.get(source_id, 9), 4)

    like_term = f"%{term}%"
    for (source_id,) in conn.execute(
        """
        SELECT DISTINCT sq.source_id FROM source_qs_subject sq
        JOIN qs_subjects s ON s.qs_subject_code = sq.qs_subject_code
        WHERE s.qs_subject_name LIKE ? LIMIT ?
        """,
        (like_term, _FTS_RESULT_CAP),
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 5)
    for (source_id,) in conn.execute(
        "SELECT source_id FROM icore_venues iv JOIN source_icore si ON si.icore_internal_id = iv.icore_internal_id "
        "AND si.icore_year = iv.icore_year WHERE iv.for_names LIKE ? LIMIT ?",
        (like_term, _FTS_RESULT_CAP),
    ):
        tiers[source_id] = min(tiers.get(source_id, 9), 5)

    return tiers
