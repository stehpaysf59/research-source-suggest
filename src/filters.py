"""Sidebar filter widgets for the Journals and Conferences pages.

Each render_* function draws the sidebar and returns (filters, chips):
- `filters` is a plain dict consumed by src/queries.py — the widgets never
  talk to SQL directly.
- `chips` is a list of human-readable "<Label>: value, value" strings for
  every currently-active filter, for the page to display as an "active
  filters" summary near the search box.
"""

from __future__ import annotations

import streamlit as st

from .database import get_distinct, get_for_names, get_qs_faculty_areas, get_qs_subjects
from .queries import NO_SJR_DATA_LABEL, UNKNOWN_STATUS_LABEL

FACULTY_COUNT_OPTIONS = ["Any", "1", "2+", "3+"]

_ICORE_ADVANCED_STATUS_LABELS = {
    "matched": "Matched (A*/A/B/C)",
    "matched_other_icore_status": "Matched (other ICORE status)",
    "explicitly_unranked_in_icore": "Explicitly Unranked in ICORE",
    "manual_review_required": "Needs manual review",
    "not_found_in_icore": "Not found in ICORE",
}


def _chip(label: str, values: list[str]) -> str | None:
    if not values:
        return None
    return f"{label}: {', '.join(values)}"


def _faculty_count_split(label: str) -> tuple[int | None, int | None]:
    if label == "1":
        return 1, None
    if label == "2+":
        return None, 2
    if label == "3+":
        return None, 3
    return None, None


def _faculty_area_multiselect(key: str) -> tuple[list[str], list[str]]:
    faculty_df = get_qs_faculty_areas()
    name_by_code = dict(zip(faculty_df["qs_faculty_area_code"], faculty_df["qs_faculty_area_name"]))
    selected_names = st.sidebar.multiselect("QS Faculty Area", list(name_by_code.values()), key=key)
    codes = [code for code, name in name_by_code.items() if name in selected_names]
    return codes, selected_names


def _qs_subject_multiselect(key: str) -> tuple[list[str], list[str]]:
    subjects_df = get_qs_subjects()
    name_by_code = dict(zip(subjects_df["qs_subject_code"], subjects_df["qs_subject_name"]))
    selected_names = st.sidebar.multiselect(
        "QS Subject", list(name_by_code.values()), key=key, help="Type to search across all 51 QS subjects."
    )
    codes = [code for code, name in name_by_code.items() if name in selected_names]
    return codes, selected_names


def render_journal_filters() -> tuple[dict, list[str]]:
    st.sidebar.header("Filters")

    faculty_codes, faculty_names = _faculty_area_multiselect("j_faculty_area")
    count_label = st.sidebar.selectbox(
        "QS Faculty Count",
        FACULTY_COUNT_OPTIONS,
        key="j_faculty_count",
        help="Number of distinct QS Broad Faculty Areas this source maps to — not the QS Subject count.",
    )
    exact, minimum = _faculty_count_split(count_label)
    subject_codes, subject_names = _qs_subject_multiselect("j_subject")

    quartiles = st.sidebar.multiselect(
        "SJR Quartile", ["Q1", "Q2", "Q3", "Q4", NO_SJR_DATA_LABEL], key="j_quartile"
    )
    source_types = st.sidebar.multiselect(
        "Source Type",
        get_distinct("sources", "source_type", "source_group = 'scopus_serial_source'"),
        key="j_type",
    )
    status = st.sidebar.multiselect("Status", ["Active", "Inactive", UNKNOWN_STATUS_LABEL], key="j_status")
    publisher_contains = st.sidebar.text_input("Publisher contains", key="j_publisher")

    if st.sidebar.button("Reset filters", key="j_reset"):
        for k in ["j_faculty_area", "j_faculty_count", "j_subject", "j_quartile", "j_type", "j_status", "j_publisher"]:
            st.session_state.pop(k, None)
        st.rerun()

    filters = {
        "qs_faculty_area_codes": faculty_codes,
        "qs_faculty_count_exact": exact,
        "qs_faculty_count_min": minimum,
        "qs_subject_codes": subject_codes,
        "sjr_quartiles": quartiles,
        "source_types": source_types,
        "status": status,
        "publisher_contains": publisher_contains,
    }
    chips = [
        c
        for c in [
            _chip("QS Faculty Area", faculty_names),
            _chip("QS Faculty Count", [count_label] if count_label != "Any" else []),
            _chip("QS Subject", subject_names),
            _chip("SJR Quartile", quartiles),
            _chip("Source Type", source_types),
            _chip("Status", status),
            _chip("Publisher contains", [publisher_contains] if publisher_contains else []),
        ]
        if c
    ]
    return filters, chips


_RANK_ORDER = {"A*": 0, "A": 1, "B": 2, "C": 3, "Unranked": 4}


def render_conference_filters() -> tuple[dict, list[str]]:
    st.sidebar.header("Filters")

    faculty_codes, faculty_names = _faculty_area_multiselect("c_faculty_area")
    count_label = st.sidebar.selectbox(
        "QS Faculty Count",
        FACULTY_COUNT_OPTIONS,
        key="c_faculty_count",
        help="Number of distinct QS Broad Faculty Areas this source maps to — not the QS Subject count.",
    )
    exact, minimum = _faculty_count_split(count_label)
    subject_codes, subject_names = _qs_subject_multiselect("c_subject")

    rank_values = get_distinct("source_icore", "icore_rank_group")
    rank_values = sorted(rank_values, key=lambda v: (_RANK_ORDER.get(v, 99), v))
    icore_ranks = st.sidebar.multiselect(
        "ICORE Rank",
        rank_values,
        key="c_rank",
        help="'Unranked' means ICORE matched a venue but explicitly rates it Unranked — different from no match at all.",
    )

    for_names = st.sidebar.multiselect("FoR (Field of Research)", get_for_names(), key="c_for")
    status = st.sidebar.multiselect("Status", ["Active", "Inactive", UNKNOWN_STATUS_LABEL], key="c_status")

    website_label = st.sidebar.radio(
        "Website Availability",
        ["Any", "Official website available", "Latest event website available"],
        key="c_website",
    )
    website_map = {
        "Any": None,
        "Official website available": "official",
        "Latest event website available": "latest_event",
    }

    icore_status_advanced: list[str] = []
    with st.sidebar.expander("Advanced (QA) filters"):
        selected_labels = st.multiselect(
            "ICORE match status", list(_ICORE_ADVANCED_STATUS_LABELS.values()), key="c_icore_status_adv"
        )
        icore_status_advanced = [
            key for key, label in _ICORE_ADVANCED_STATUS_LABELS.items() if label in selected_labels
        ]

    if st.sidebar.button("Reset filters", key="c_reset"):
        for k in [
            "c_faculty_area",
            "c_faculty_count",
            "c_subject",
            "c_rank",
            "c_for",
            "c_status",
            "c_website",
            "c_icore_status_adv",
        ]:
            st.session_state.pop(k, None)
        st.rerun()

    filters = {
        "qs_faculty_area_codes": faculty_codes,
        "qs_faculty_count_exact": exact,
        "qs_faculty_count_min": minimum,
        "qs_subject_codes": subject_codes,
        "icore_ranks": icore_ranks,
        "for_names": for_names,
        "status": status,
        "website_availability": website_map[website_label],
        "icore_status_advanced": icore_status_advanced,
    }
    chips = [
        c
        for c in [
            _chip("QS Faculty Area", faculty_names),
            _chip("QS Faculty Count", [count_label] if count_label != "Any" else []),
            _chip("QS Subject", subject_names),
            _chip("ICORE Rank", icore_ranks),
            _chip("FoR", for_names),
            _chip("Status", status),
            _chip("Website", [website_label] if website_label != "Any" else []),
            _chip("ICORE status (advanced)", selected_labels),
        ]
        if c
    ]
    return filters, chips
