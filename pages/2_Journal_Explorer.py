from __future__ import annotations

import streamlit as st

from src.filters import render_journal_filters
from src.queries import count_journals, fetch_journal_detail, fetch_journals
from src.ui import (
    inject_base_style,
    render_active_filters,
    render_journal_detail,
    render_journals_table,
    render_pagination,
    render_summary_bar,
)

st.set_page_config(page_title="Journal Explorer — VinUni Research Source Explorer", layout="wide", page_icon="📚")
inject_base_style()

st.markdown("## 🔎 Journal Explorer")
st.caption(
    "Advanced manual exploration of the full Scopus serial-source universe. Use filters when you already "
    "know the journal, QS field, publisher, identifier, or source characteristic you want to inspect."
)

search_term = st.text_input(
    "🔍 Search by title, ISSN, EISSN, publisher, or Scopus Source ID",
    key="j_search",
    placeholder="e.g. Nature, 0028-0836, Elsevier, 12345...",
)

filters, chips = render_journal_filters()
if search_term.strip():
    chips = [f"Search: “{search_term.strip()}”", *chips]
render_active_filters(chips)

# Fixed default order; the "SJR Quartile (best first)" server-side ordering was
# removed for now per user request. Click a column header for a native re-sort.
sort_label = "Title (A–Z)"

page = st.session_state.get("j_page", 1)
page_size = st.session_state.get("j_page_size", 50)
page_size = None if page_size == "All" else page_size
df, total = fetch_journals(filters, search_term, sort_label, page, page_size)

render_summary_bar(
    [
        ("Results", f"{total:,}"),
        ("Active", f"{count_journals({**filters, 'status': ['Active']}, search_term):,}"),
        ("Q1", f"{count_journals({**filters, 'sjr_quartiles': ['Q1']}, search_term):,}"),
        (
            "Cross-disciplinary (2+ areas)",
            f"{count_journals({**filters, 'qs_faculty_count_min': 2, 'qs_faculty_count_exact': None}, search_term):,}",
        ),
    ]
)

st.divider()
new_page, new_page_size = render_pagination(total, "j_page", "j_page_size")
if (new_page, new_page_size) != (page, page_size):
    df, total = fetch_journals(filters, search_term, sort_label, new_page, new_page_size)

selected_id = render_journals_table(df, key="j_table")

if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Download current results as CSV", csv, "journals_filtered.csv", "text/csv")

st.divider()
st.markdown("#### Source detail")
if selected_id:
    detail_row = fetch_journal_detail(selected_id)
    if detail_row is not None:
        render_journal_detail(detail_row)
else:
    st.caption("Select a row in the table above to see its full detail here.")
