from __future__ import annotations

import streamlit as st

from src.database import get_home_totals, get_snapshot_info
from src.ui import inject_base_style

st.set_page_config(
    page_title="VinUni QS Journal Finder",
    layout="wide",
    page_icon="🎓",
    initial_sidebar_state="expanded",
)
inject_base_style()

st.markdown(
    """
    <div class="vinuni-hero">
      <div class="vinuni-kicker">VinUni Research Source Intelligence</div>
      <h1>Discover multidisciplinary journals through QS subject mappings</h1>
      <p>Start with the QS Subjects that describe your research, then identify journals that bridge those areas. Recommendations are transparent, database-driven, and can prioritize Q1 sources without making AI mandatory.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2 = st.columns([1.15, 1])
with c1:
    with st.container(border=True):
        st.markdown("### ✨ Find journals")
        st.write(
            "Select one or more QS Subjects and get a ranked list of journals based on subject overlap, "
            "cross-faculty coverage, Q1 preference, SJR and H-index."
        )
        st.page_link("pages/1_Find_Journals.py", label="Start a recommendation", icon="✨")
with c2:
    with st.container(border=True):
        st.markdown("### 🔎 Explore manually")
        st.write(
            "Search the full source universe by title, ISSN, publisher, QS mapping, SJR quartile and other fields."
        )
        st.page_link("pages/2_Journal_Explorer.py", label="Open Journal Explorer", icon="🔎")

st.markdown("### How it works")
step1, step2, step3 = st.columns(3)
with step1:
    st.markdown("**1 · Define the research areas**")
    st.caption("Choose QS Subjects manually. AI-assisted subject suggestions can plug into the same selector later.")
with step2:
    st.markdown("**2 · Rank real journals**")
    st.caption("The deterministic engine queries the existing SQLite database; the model never invents journal metadata.")
with step3:
    st.markdown("**3 · Inspect and refine**")
    st.caption("See why a source matched, review QS faculty/subject coverage, and continue in the advanced Explorer.")

st.divider()
totals = get_home_totals()
t1, t2, t3 = st.columns(3)
t1.metric("Journal / serial sources", f"{totals['journals']:,}")
t2.metric("Conference sources retained in data", f"{totals['conferences']:,}")
t3.metric("AI dependency", "None")

st.divider()
st.markdown("##### Data snapshot")
info = get_snapshot_info()
s1, s2, s3 = st.columns(3)
s1.metric("Scopus snapshot", info["scopus_snapshot"])
s2.metric("SJR year", info["sjr_year"])
s3.metric("QS mapping version", info["qs_mapping_version"])

st.caption(
    "Conference code/data is retained in the repository for future phases, but V2 focuses the user experience on journal discovery."
)
