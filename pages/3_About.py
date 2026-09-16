from __future__ import annotations

import streamlit as st

from src.database import get_snapshot_info
from src.ui import inject_base_style

st.set_page_config(page_title="About — VinUni QS Journal Finder", layout="wide", page_icon="ℹ️")
inject_base_style()

st.markdown("## ℹ️ About / Methodology")
st.markdown(
    """
This version focuses on **multidisciplinary journal discovery through QS mappings**. It is a read-only application over the canonical source-intelligence SQLite database; it does not recompute upstream Scopus/SJR/QS mappings.
"""
)

st.markdown("### Recommendation logic")
st.write(
    "Users choose the QS Subjects relevant to their research. The app retrieves only real journals from the database "
    "and ranks them using transparent signals: selected-subject overlap, relevant QS Broad Faculty coverage, "
    "cross-faculty status, Q1 preference, total QS Subject coverage, SJR and H-index."
)
st.info(
    "A journal with many QS Subjects does not automatically rank first. Matching the user's selected QS Subjects "
    "takes priority over simply being broadly classified."
)

st.markdown("### Multidisciplinary terminology")
st.write(
    "**Multi-subject** means a source maps to at least two QS Subjects. **Cross-faculty** means it maps to at least "
    "two distinct QS Broad Faculty Areas. Cross-faculty is the stronger multidisciplinary signal used by the default recommender."
)

st.markdown("### SJR / Q1")
st.write("SJR and SJR Best Quartile come from SCImago's annual source data.")
st.warning(
    "**Q1 is used here as a journal-quality signal; it is not itself a QS ranking indicator and the app does not claim a journal will add a specific number of QS points.**"
)

st.markdown("### AI-ready, but AI-independent")
st.write(
    "The core recommendation engine does not require an LLM. A future AI module can translate a title/abstract or free-text question "
    "into existing QS Subject codes, after which the same deterministic recommendation engine runs. The user will remain able to "
    "review/edit AI-suggested subjects, and manual selection will always remain available."
)
st.code(
    "Research text → optional AI subject classifier → confirmed QS Subjects → deterministic recommender → SQLite → journals",
    language="text",
)

st.markdown("### Data snapshot")
info = get_snapshot_info()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Scopus snapshot", info["scopus_snapshot"])
c2.metric("SJR year", info["sjr_year"])
c3.metric("ICORE year (retained)", info["icore_year"])
c4.metric("QS mapping version", info["qs_mapping_version"])

with st.expander("Future extension hooks"):
    st.markdown(
        """
- `src/subject_classifier.py`: provider-neutral AI/free-text → QS Subject interface.
- `src/recommender.py`: stable deterministic recommendation engine that should not depend on the AI provider.
- Conference code is retained under `legacy_pages/` for later reactivation.
- A future comparison or conversational follow-up feature should consume the same recommendation output rather than create a second ranking path.
"""
    )
