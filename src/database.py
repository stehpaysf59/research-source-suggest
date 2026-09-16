from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = APP_ROOT / "data" / "vinuni_source_intelligence.db"


def get_db_path() -> Path:
    """Resolve the canonical database path.

    Override with the VINUNI_DB_PATH env var to point at a different copy
    (e.g. the live pipeline output) without changing code.
    """
    override = os.environ.get("VINUNI_DB_PATH")
    return Path(override).resolve() if override else DEFAULT_DB_PATH


@st.cache_resource(show_spinner=False)
def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Copy vinuni_source_intelligence.db into data/, "
            "or set the VINUNI_DB_PATH environment variable."
        )
    # Read-only: this app only ever reads the canonical database produced by the pipeline.
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    return conn


@st.cache_data(show_spinner=False, ttl=3600)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


@st.cache_data(show_spinner=False, ttl=3600)
def get_distinct(table: str, column: str, where: str = "") -> list[str]:
    conn = get_connection()
    clause = f"WHERE {where}" if where else ""
    sql = f"SELECT DISTINCT {column} FROM {table} {clause} ORDER BY {column}"
    rows = conn.execute(sql).fetchall()
    return [row[0] for row in rows if row[0] is not None]


@st.cache_data(show_spinner=False, ttl=3600)
def get_qs_faculty_areas() -> pd.DataFrame:
    return run_query("SELECT qs_faculty_area_code, qs_faculty_area_name FROM qs_faculty_areas ORDER BY qs_faculty_area_code")


@st.cache_data(show_spinner=False, ttl=3600)
def get_qs_subjects() -> pd.DataFrame:
    return run_query("SELECT qs_subject_code, qs_subject_name FROM qs_subjects ORDER BY qs_subject_name")


@st.cache_data(show_spinner=False, ttl=3600)
def get_for_names() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT for_names FROM icore_venues WHERE for_names IS NOT NULL AND for_names != ''"
    ).fetchall()
    names: set[str] = set()
    for (value,) in rows:
        for part in value.split(";"):
            part = part.strip()
            if part:
                names.add(part)
    return sorted(names)


@st.cache_data(show_spinner=False, ttl=3600)
def get_snapshot_info() -> dict:
    conn = get_connection()

    def _scalar(sql: str):
        row = conn.execute(sql).fetchone()
        return row[0] if row else None

    return {
        "scopus_snapshot": _scalar(
            "SELECT source_snapshot FROM sources WHERE source_snapshot IS NOT NULL AND source_snapshot != '' LIMIT 1"
        )
        or "unknown",
        "sjr_year": _scalar("SELECT MAX(sjr_year) FROM source_sjr") or "unknown",
        "icore_year": _scalar("SELECT MAX(icore_year) FROM source_icore") or "unknown",
        "qs_mapping_version": _scalar(
            "SELECT qs_mapping_version FROM asjc_qs_subject WHERE qs_mapping_version IS NOT NULL LIMIT 1"
        )
        or "unknown",
        "schema_version": _scalar("SELECT MAX(version) FROM schema_version") or "unknown",
    }


@st.cache_data(show_spinner=False, ttl=3600)
def get_home_totals() -> dict:
    conn = get_connection()
    journals = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE source_group = 'scopus_serial_source'"
    ).fetchone()[0]
    conferences = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE source_group = 'serial_conference_profile'"
    ).fetchone()[0]
    icore_matched = conn.execute(
        "SELECT COUNT(*) FROM source_icore "
        "WHERE icore_match_status IN ('matched', 'matched_other_icore_status', 'explicitly_unranked_in_icore')"
    ).fetchone()[0]
    return {"journals": journals, "conferences": conferences, "icore_matched": icore_matched}
