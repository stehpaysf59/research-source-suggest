from __future__ import annotations

import streamlit as st

from src.filters import render_conference_filters
from src.queries import count_conferences, fetch_conference_detail, fetch_conferences
from src.ui import (
    inject_base_style,
    render_active_filters,
    render_conference_detail,
    render_conferences_table,
    render_pagination,
    render_summary_bar,
)

st.set_page_config(page_title="Conferences — VinUni Research Source Explorer", layout="wide", page_icon="🎤")
inject_base_style()

st.markdown("## 🎤 Conferences")
st.caption(
    "Scopus conference-proceedings sources enriched with the curated ICORE conference ranking. "
    "This page only reads final, already-matched database results — no live ICORE matching "
    "happens here. Click any column header in the table to sort by it."
)

search_term = st.text_input(
    "🔍 Search by conference title, ICORE acronym, ISSN, EISSN, or Scopus Source ID",
    key="c_search",
    placeholder="e.g. ICML, HRI, 21100236214...",
)

filters, chips = render_conference_filters()
if search_term.strip():
    chips = [f"Search: “{search_term.strip()}”", *chips]
render_active_filters(chips)

# Fixed default order; the "ICORE Rank (best first)" server-side ordering was
# removed for now per user request. Click a column header for a native re-sort.
sort_label = "Title (A–Z)"

page = st.session_state.get("c_page", 1)
page_size = st.session_state.get("c_page_size", 50)
page_size = None if page_size == "All" else page_size
df, total = fetch_conferences(filters, search_term, sort_label, page, page_size)

render_summary_bar(
    [
        ("Results", f"{total:,}"),
        (
            "ICORE matched",
            f"{count_conferences({**filters, 'icore_status_advanced': ['matched', 'matched_other_icore_status', 'explicitly_unranked_in_icore']}, search_term):,}",
        ),
        ("A*", f"{count_conferences({**filters, 'icore_ranks': ['A*']}, search_term):,}"),
        ("A", f"{count_conferences({**filters, 'icore_ranks': ['A']}, search_term):,}"),
        (
            "2+ QS Faculty Areas",
            f"{count_conferences({**filters, 'qs_faculty_count_min': 2, 'qs_faculty_count_exact': None}, search_term):,}",
        ),
    ]
)

st.divider()
new_page, new_page_size = render_pagination(total, "c_page", "c_page_size")
if (new_page, new_page_size) != (page, page_size):
    df, total = fetch_conferences(filters, search_term, sort_label, new_page, new_page_size)

selected_id = render_conferences_table(df, key="c_table")

if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Download current results as CSV", csv, "conferences_filtered.csv", "text/csv")

st.divider()
st.markdown("#### Source detail")
if selected_id:
    detail_row = fetch_conference_detail(selected_id)
    if detail_row is not None:
        render_conference_detail(detail_row)
else:
    st.caption("Select a row in the table above to see its full detail here.")
