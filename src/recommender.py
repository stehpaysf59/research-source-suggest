"""Deterministic QS-aware journal recommendation engine.

The recommender is intentionally LLM-free.  It accepts QS Subject codes that
have already been selected (manually today; AI-assisted later), queries only
the canonical SQLite database, and returns auditable ranking signals.

Future AI integrations should map free text -> existing QS Subject codes, then
call ``recommend_journals``.  They must not generate journal recommendations
from model memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .database import get_connection

QUALITY_PRIORITIZE_Q1 = "prioritize_q1"
QUALITY_Q1_ONLY = "q1_only"
QUALITY_ALL = "all"
QUALITY_OPTIONS = {QUALITY_PRIORITIZE_Q1, QUALITY_Q1_ONLY, QUALITY_ALL}

MULTI_CROSS_FACULTY = "cross_faculty"
MULTI_MULTI_SUBJECT = "multi_subject"
MULTI_ANY = "any"
MULTI_OPTIONS = {MULTI_CROSS_FACULTY, MULTI_MULTI_SUBJECT, MULTI_ANY}


@dataclass(frozen=True)
class RecommendationRequest:
    subject_codes: tuple[str, ...]
    quality_preference: str = QUALITY_PRIORITIZE_Q1
    multidisciplinary_preference: str = MULTI_CROSS_FACULTY
    active_only: bool = True
    limit: int = 20


def _normalize_codes(values: Iterable[str]) -> list[str]:
    # Preserve user order while removing blanks/duplicates.
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        code = str(value or "").strip()
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def validate_request(request: RecommendationRequest) -> RecommendationRequest:
    codes = tuple(_normalize_codes(request.subject_codes))
    if not codes:
        raise ValueError("Select at least one QS Subject.")
    if request.quality_preference not in QUALITY_OPTIONS:
        raise ValueError(f"Unsupported quality preference: {request.quality_preference}")
    if request.multidisciplinary_preference not in MULTI_OPTIONS:
        raise ValueError(
            f"Unsupported multidisciplinary preference: {request.multidisciplinary_preference}"
        )
    limit = max(1, min(int(request.limit), 200))
    return RecommendationRequest(
        subject_codes=codes,
        quality_preference=request.quality_preference,
        multidisciplinary_preference=request.multidisciplinary_preference,
        active_only=bool(request.active_only),
        limit=limit,
    )


def recommend_journals(request: RecommendationRequest) -> pd.DataFrame:
    """Return ranked journal recommendations from the canonical SQLite DB.

    Ranking is transparent and deterministic:
      1. Q1 priority when requested;
      2. total QS Broad Faculty Areas covered (5 -> 1);
      3. H-index;
      4. number of selected QS Subjects matched;
      5. total QS Subject count;
      6. SJR;
      7. title for stable ordering.

    The selected QS Subject(s) are the eligibility condition: every returned
    journal must match at least one selected subject.  Breadth across the five
    QS Broad Faculty Areas is then rewarded strongly so a single selected
    subject can still surface highly interdisciplinary journals.

    ``q1_only`` is a hard filter. ``prioritize_q1`` is a ranking signal.
    ``all`` does not give Q1 an explicit ordering bonus.
    """
    request = validate_request(request)
    codes = list(request.subject_codes)
    placeholders = ",".join("?" for _ in codes)

    conn = get_connection()
    known_rows = conn.execute(
        f"SELECT qs_subject_code FROM qs_subjects WHERE qs_subject_code IN ({placeholders})",
        codes,
    ).fetchall()
    known_codes = {row[0] for row in known_rows}
    unknown_codes = [code for code in codes if code not in known_codes]
    if unknown_codes:
        raise ValueError(f"Unknown QS Subject code(s): {', '.join(unknown_codes)}")

    where = ["1=1"]
    params: list[object] = [*codes, *codes]

    if request.active_only:
        where.append("j.active_status = 'Active'")
    if request.quality_preference == QUALITY_Q1_ONLY:
        where.append("j.sjr_best_quartile = 'Q1'")
    if request.multidisciplinary_preference == MULTI_CROSS_FACULTY:
        where.append("CAST(COALESCE(j.qs_faculty_area_count, 0) AS INTEGER) >= 2")
    elif request.multidisciplinary_preference == MULTI_MULTI_SUBJECT:
        where.append("CAST(COALESCE(j.qs_subject_count, 0) AS INTEGER) >= 2")

    q1_order = (
        "CASE WHEN j.sjr_best_quartile = 'Q1' THEN 1 ELSE 0 END DESC,"
        if request.quality_preference == QUALITY_PRIORITIZE_Q1
        else ""
    )

    sql = f"""
    WITH
    selected_subjects AS (
        SELECT qs_subject_code, qs_subject_name
        FROM qs_subjects
        WHERE qs_subject_code IN ({placeholders})
    ),
    selected_faculties AS (
        SELECT DISTINCT qf.qs_faculty_area_code
        FROM asjc_qs_subject qs
        JOIN asjc_qs_faculty_area qf ON qf.asjc_code = qs.asjc_code
        WHERE qs.qs_subject_code IN ({placeholders})
    ),
    subject_matches AS (
        SELECT
            sqs.source_id,
            COUNT(DISTINCT sqs.qs_subject_code) AS matched_subject_count,
            REPLACE(GROUP_CONCAT(DISTINCT q.qs_subject_name), ',', '; ') AS matched_subject_names
        FROM source_qs_subject sqs
        JOIN selected_subjects q ON q.qs_subject_code = sqs.qs_subject_code
        GROUP BY sqs.source_id
    ),
    faculty_matches AS (
        SELECT
            sfa.source_id,
            COUNT(DISTINCT sfa.qs_faculty_area_code) AS matched_faculty_count
        FROM source_qs_faculty_area sfa
        JOIN selected_faculties sf
          ON sf.qs_faculty_area_code = sfa.qs_faculty_area_code
        GROUP BY sfa.source_id
    )
    SELECT
        j.source_id,
        j.source_title,
        j.source_type,
        j.publisher,
        j.issn_normalized,
        j.eissn_normalized,
        j.coverage,
        j.active_status,
        j.sjr_best_quartile,
        j.sjr,
        j.sjr_h_index,
        ss.sjr_sourceid,
        CAST(COALESCE(j.qs_subject_count, 0) AS INTEGER) AS qs_subject_count,
        j.qs_subject_names,
        CAST(COALESCE(j.qs_faculty_area_count, 0) AS INTEGER) AS qs_faculty_area_count,
        j.qs_faculty_area_names,
        sm.matched_subject_count,
        ? AS selected_subject_count,
        sm.matched_subject_names,
        COALESCE(fm.matched_faculty_count, 0) AS matched_faculty_count,
        CASE
            WHEN CAST(COALESCE(j.qs_faculty_area_count, 0) AS INTEGER) >= 2 THEN 1
            ELSE 0
        END AS is_cross_faculty,
        CASE WHEN j.sjr_best_quartile = 'Q1' THEN 1 ELSE 0 END AS is_q1
    FROM vw_journals_other_sources j
    LEFT JOIN source_sjr ss ON ss.source_id = j.source_id
    JOIN subject_matches sm ON sm.source_id = j.source_id
    LEFT JOIN faculty_matches fm ON fm.source_id = j.source_id
    WHERE {' AND '.join(where)}
    ORDER BY
        {q1_order}
        CAST(COALESCE(j.qs_faculty_area_count, 0) AS INTEGER) DESC,
        COALESCE(j.sjr_h_index, -1) DESC,
        sm.matched_subject_count DESC,
        CAST(COALESCE(j.qs_subject_count, 0) AS INTEGER) DESC,
        COALESCE(j.sjr, -1) DESC,
        j.source_title COLLATE NOCASE ASC
    LIMIT ?
    """

    params.extend([len(codes), request.limit])
    return pd.read_sql_query(sql, conn, params=params)


def recommendation_summary(df: pd.DataFrame) -> dict[str, int]:
    """Small summary for UI cards without another database query."""
    if df.empty:
        return {"results": 0, "q1": 0, "cross_faculty": 0, "full_match": 0}
    return {
        "results": int(len(df)),
        "q1": int(df["is_q1"].fillna(0).astype(int).sum()),
        "cross_faculty": int(df["is_cross_faculty"].fillna(0).astype(int).sum()),
        "full_match": int(
            (df["matched_subject_count"] == df["selected_subject_count"]).sum()
        ),
    }
