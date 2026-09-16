"""Filtered/sorted/paginated reads for the Journals and Conferences pages.

All SQL lives here (and in database.py's fixed helper queries) so the
Streamlit page files stay thin UI code, per the project's data-access-layer
convention. Column names are never taken from user input directly — sort
keys are resolved through a small allowlist below.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from . import search
from .database import get_connection

NO_SJR_DATA_LABEL = "No SJR data"
UNKNOWN_STATUS_LABEL = "Unknown"

# Best -> worst domain order. A generic spreadsheet-style "click a column
# header to sort" only ever does alphabetical/lexicographic comparison — it
# has no way to know "A* is better than Unranked" (true of Excel/Sheets too
# without a custom sort list). So these two orderings are offered as an
# explicit, guaranteed-correct "Order by" choice instead, applied server-side.
SJR_QUARTILE_ORDER = ["Q1", "Q2", "Q3", "Q4", "-"]  # blank/no SJR record sorts worst
ICORE_RANK_ORDER = [
    "A*",
    "A",
    "B",
    "C",
    "Unranked",
    "National/Regional",
    "Australasian",
    "Journal Published",
    "Other",
]  # no ICORE match sorts worst


def _rank_case_sql(column: str, order_best_to_worst: list[str]) -> str:
    whens = "".join(f" WHEN {column} = '{value}' THEN {i + 1}" for i, value in enumerate(order_best_to_worst))
    worst_known = len(order_best_to_worst) + 1
    worst_overall = len(order_best_to_worst) + 2
    return f"(CASE{whens} WHEN {column} IS NULL THEN {worst_overall} ELSE {worst_known} END)"


def _rank_key_fn(column: str, order_best_to_worst: list[str]) -> Callable[[pd.DataFrame], pd.Series]:
    mapping = {value: i + 1 for i, value in enumerate(order_best_to_worst)}
    worst_known = len(order_best_to_worst) + 1
    worst_overall = len(order_best_to_worst) + 2

    def _key(df: pd.DataFrame) -> pd.Series:
        return df[column].map(lambda v: worst_overall if pd.isna(v) else mapping.get(v, worst_known))

    return _key


JOURNAL_SORT_OPTIONS: dict[str, dict] = {
    "Title (A–Z)": {
        "sql": "source_title COLLATE NOCASE",
        "key": lambda df: df["source_title"].str.lower(),
    },
    "SJR Quartile (best first)": {
        "sql": _rank_case_sql("sjr_best_quartile", SJR_QUARTILE_ORDER),
        "key": _rank_key_fn("sjr_best_quartile", SJR_QUARTILE_ORDER),
    },
}

CONFERENCE_SORT_OPTIONS: dict[str, dict] = {
    "Title (A–Z)": {
        "sql": "source_title COLLATE NOCASE",
        "key": lambda df: df["source_title"].str.lower(),
    },
    "ICORE Rank (best first)": {
        "sql": _rank_case_sql("icore_rank_group", ICORE_RANK_ORDER),
        "key": _rank_key_fn("icore_rank_group", ICORE_RANK_ORDER),
    },
}


def _in_clause(column: str, values: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join("?" * len(values))
    return f"{column} IN ({placeholders})", list(values)


def _status_clause(column: str, statuses: list[str]) -> tuple[str, list[str]]:
    parts = []
    params: list[str] = []
    plain = [s for s in statuses if s != UNKNOWN_STATUS_LABEL]
    if UNKNOWN_STATUS_LABEL in statuses:
        parts.append(f"{column} IS NULL")
    if plain:
        clause, values = _in_clause(column, plain)
        parts.append(clause)
        params.extend(values)
    return "(" + " OR ".join(parts) + ")", params


def _sjr_quartile_clause(quartiles: list[str]) -> tuple[str, list[str]]:
    parts = []
    params: list[str] = []
    plain = [q for q in quartiles if q != NO_SJR_DATA_LABEL]
    if NO_SJR_DATA_LABEL in quartiles:
        parts.append("(sjr_best_quartile IS NULL OR sjr_best_quartile = '-')")
    if plain:
        clause, values = _in_clause("sjr_best_quartile", plain)
        parts.append(clause)
        params.extend(values)
    return "(" + " OR ".join(parts) + ")", params


def _faculty_area_clause(codes: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join("?" * len(codes))
    return (
        f"source_id IN (SELECT source_id FROM source_qs_faculty_area WHERE qs_faculty_area_code IN ({placeholders}))",
        list(codes),
    )


def _qs_subject_clause(codes: list[str]) -> tuple[str, list[str]]:
    placeholders = ",".join("?" * len(codes))
    return (
        f"source_id IN (SELECT source_id FROM source_qs_subject WHERE qs_subject_code IN ({placeholders}))",
        list(codes),
    )


def _for_names_clause(names: list[str]) -> tuple[str, list[str]]:
    parts = ["icore_for_names LIKE ?" for _ in names]
    params = [f"%{name}%" for name in names]
    return "(" + " OR ".join(parts) + ")", params


def _journal_where(filters: dict, search_term: str) -> tuple[list[str], list, dict[str, int] | None]:
    where: list[str] = []
    params: list = []

    if filters.get("qs_faculty_area_codes"):
        clause, values = _faculty_area_clause(filters["qs_faculty_area_codes"])
        where.append(clause)
        params.extend(values)
    if filters.get("qs_faculty_count_exact"):
        where.append("qs_faculty_area_count = ?")
        params.append(filters["qs_faculty_count_exact"])
    elif filters.get("qs_faculty_count_min"):
        where.append("qs_faculty_area_count >= ?")
        params.append(filters["qs_faculty_count_min"])
    if filters.get("qs_subject_codes"):
        clause, values = _qs_subject_clause(filters["qs_subject_codes"])
        where.append(clause)
        params.extend(values)
    if filters.get("sjr_quartiles"):
        clause, values = _sjr_quartile_clause(filters["sjr_quartiles"])
        where.append(clause)
        params.extend(values)
    if filters.get("source_types"):
        clause, values = _in_clause("source_type", filters["source_types"])
        where.append(clause)
        params.extend(values)
    if filters.get("status"):
        clause, values = _status_clause("active_status", filters["status"])
        where.append(clause)
        params.extend(values)
    if filters.get("publisher_contains"):
        where.append("publisher LIKE ?")
        params.append(f"%{filters['publisher_contains']}%")

    tiers = None
    if search_term and search_term.strip():
        tiers = search.search_journals(get_connection(), search_term)
        placeholders = ",".join("?" * max(len(tiers), 1))
        where.append(f"source_id IN ({placeholders})")
        params.extend(tiers.keys() if tiers else ["__no_match__"])

    return where, params, tiers


def _conference_where(filters: dict, search_term: str) -> tuple[list[str], list, dict[str, int] | None]:
    where: list[str] = []
    params: list = []

    if filters.get("qs_faculty_area_codes"):
        clause, values = _faculty_area_clause(filters["qs_faculty_area_codes"])
        where.append(clause)
        params.extend(values)
    if filters.get("qs_faculty_count_exact"):
        where.append("qs_faculty_area_count = ?")
        params.append(filters["qs_faculty_count_exact"])
    elif filters.get("qs_faculty_count_min"):
        where.append("qs_faculty_area_count >= ?")
        params.append(filters["qs_faculty_count_min"])
    if filters.get("qs_subject_codes"):
        clause, values = _qs_subject_clause(filters["qs_subject_codes"])
        where.append(clause)
        params.extend(values)
    if filters.get("icore_ranks"):
        clause, values = _in_clause("icore_rank_group", filters["icore_ranks"])
        where.append(clause)
        params.extend(values)
    if filters.get("for_names"):
        clause, values = _for_names_clause(filters["for_names"])
        where.append(clause)
        params.extend(values)
    if filters.get("status"):
        clause, values = _status_clause("active_status", filters["status"])
        where.append(clause)
        params.extend(values)
    if filters.get("website_availability") == "official":
        where.append("official_series_website IS NOT NULL")
    elif filters.get("website_availability") == "latest_event":
        where.append("latest_event_website IS NOT NULL")
    if filters.get("icore_status_advanced"):
        clause, values = _in_clause("icore_match_status", filters["icore_status_advanced"])
        where.append(clause)
        params.extend(values)

    tiers = None
    if search_term and search_term.strip():
        tiers = search.search_conferences(get_connection(), search_term)
        placeholders = ",".join("?" * max(len(tiers), 1))
        where.append(f"source_id IN ({placeholders})")
        params.extend(tiers.keys() if tiers else ["__no_match__"])

    return where, params, tiers


def _count(view: str, where: list[str], params: list) -> int:
    conn = get_connection()
    where_sql = " AND ".join(where) if where else "1=1"
    return conn.execute(f"SELECT COUNT(*) FROM {view} WHERE {where_sql}", params).fetchone()[0]


def _fetch_page(
    view: str,
    where: list[str],
    params: list,
    tiers: dict[str, int] | None,
    sort_option: dict,
    page: int,
    page_size: int | None,
) -> tuple[pd.DataFrame, int]:
    """page_size=None means "no limit" — return every matching row.

    `sort_option` is one of JOURNAL_SORT_OPTIONS/CONFERENCE_SORT_OPTIONS's
    values: {"sql": <ORDER BY expression>, "key": <df -> Series for the
    equivalent pandas sort, used on the search/tiers path>}. Both always sort
    ascending — "best/A first" is baked into how each key is built.
    """
    conn = get_connection()
    where_sql = " AND ".join(where) if where else "1=1"

    if tiers is not None:
        # A search term already narrows the candidate set to something small (capped);
        # pull it all in and rank/paginate in pandas rather than a second round trip.
        df = pd.read_sql_query(f"SELECT * FROM {view} WHERE {where_sql}", conn, params=params)
        if df.empty:
            return df, 0
        df["_rank_tier"] = df["source_id"].map(tiers).fillna(9)
        df["_secondary"] = sort_option["key"](df)
        df = df.sort_values(by=["_rank_tier", "_secondary"], kind="stable")
        total = len(df)
        df = df.drop(columns=["_rank_tier", "_secondary"])
        if page_size is None:
            return df.reset_index(drop=True), total
        start = (page - 1) * page_size
        return df.iloc[start : start + page_size].reset_index(drop=True), total

    total = _count(view, where, params)
    order_sql = sort_option["sql"]
    if page_size is None:
        data_sql = f"SELECT * FROM {view} WHERE {where_sql} ORDER BY {order_sql} ASC"
        page_df = pd.read_sql_query(data_sql, conn, params=params)
        return page_df, total
    start = (page - 1) * page_size
    data_sql = f"SELECT * FROM {view} WHERE {where_sql} ORDER BY {order_sql} ASC LIMIT ? OFFSET ?"
    page_df = pd.read_sql_query(data_sql, conn, params=[*params, page_size, start])
    return page_df, total




def _attach_sjr_source_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Attach SCImago/SJR Source IDs without changing the canonical DB view.

    The SJR/SCImago Source ID is usually the same numeric identifier as the
    Scopus Source ID, but the source_sjr table is kept authoritative because
    a small number of records were matched by ISSN fallback and differ.
    """
    if df.empty or "source_id" not in df.columns:
        result = df.copy()
        if "sjr_sourceid" not in result.columns:
            result["sjr_sourceid"] = pd.Series(dtype="object")
        return result

    source_ids = [str(v) for v in df["source_id"].dropna().unique()]
    if not source_ids:
        result = df.copy()
        result["sjr_sourceid"] = None
        return result

    placeholders = ",".join("?" for _ in source_ids)
    conn = get_connection()
    mapping = pd.read_sql_query(
        f"SELECT source_id, sjr_sourceid FROM source_sjr WHERE source_id IN ({placeholders})",
        conn,
        params=source_ids,
    )
    result = df.copy()
    if "sjr_sourceid" in result.columns:
        result = result.drop(columns=["sjr_sourceid"])
    return result.merge(mapping, on="source_id", how="left")

def fetch_journals(
    filters: dict, search_term: str, sort_label: str, page: int, page_size: int | None
) -> tuple[pd.DataFrame, int]:
    where, params, tiers = _journal_where(filters, search_term)
    sort_option = JOURNAL_SORT_OPTIONS.get(sort_label, JOURNAL_SORT_OPTIONS["Title (A–Z)"])
    df, total = _fetch_page("vw_journals_other_sources", where, params, tiers, sort_option, page, page_size)
    return _attach_sjr_source_ids(df), total


def count_journals(filters: dict, search_term: str = "") -> int:
    where, params, tiers = _journal_where(filters, search_term)
    if tiers is not None and not tiers:
        return 0
    return _count("vw_journals_other_sources", where, params)


def fetch_conferences(
    filters: dict, search_term: str, sort_label: str, page: int, page_size: int | None
) -> tuple[pd.DataFrame, int]:
    where, params, tiers = _conference_where(filters, search_term)
    sort_option = CONFERENCE_SORT_OPTIONS.get(sort_label, CONFERENCE_SORT_OPTIONS["Title (A–Z)"])
    return _fetch_page("vw_conferences", where, params, tiers, sort_option, page, page_size)


def count_conferences(filters: dict, search_term: str = "") -> int:
    where, params, tiers = _conference_where(filters, search_term)
    if tiers is not None and not tiers:
        return 0
    return _count("vw_conferences", where, params)


def fetch_journal_detail(source_id: str) -> pd.Series | None:
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT j.*, ss.sjr_sourceid
        FROM vw_journals_other_sources j
        LEFT JOIN source_sjr ss ON ss.source_id = j.source_id
        WHERE j.source_id = ?
        """,
        conn,
        params=(source_id,),
    )
    return df.iloc[0] if not df.empty else None


def fetch_conference_detail(source_id: str) -> pd.Series | None:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM vw_conferences WHERE source_id = ?", conn, params=(source_id,))
    return df.iloc[0] if not df.empty else None
