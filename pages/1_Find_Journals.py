from __future__ import annotations

import streamlit as st

from src.ai_provider import AIProviderError
from src.database import get_qs_subjects
from src.queries import fetch_journal_detail
from src.recommender import (
    MULTI_ANY,
    QUALITY_ALL,
    QUALITY_PRIORITIZE_Q1,
    QUALITY_Q1_ONLY,
    RecommendationRequest,
    recommend_journals,
    recommendation_summary,
)
from src.subject_classifier import classify_qs_subjects
from src.ui import (
    inject_base_style,
    render_journal_detail,
    render_qs_chips,
    render_recommendation_cards,
    render_recommendations_table,
    render_summary_bar,
)

st.set_page_config(
    page_title="Find Journals — VinUni Research Source Explorer",
    layout="wide",
    page_icon="✨",
)
inject_base_style()

st.markdown(
    """
    <div class="vinuni-hero">
      <div class="vinuni-kicker">QS Multidisciplinary Journal Finder</div>
      <h1>Find journals across your QS subject areas</h1>
      <p>Describe your research and let AI suggest relevant QS Subjects, or choose the subjects yourself. Recommendations come only from the Source Explorer database.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

subjects_df = get_qs_subjects()
name_to_code = dict(zip(subjects_df["qs_subject_name"], subjects_df["qs_subject_code"]))
subject_names = subjects_df["qs_subject_name"].tolist()

# Session-state defaults. AI suggestions and manual selection intentionally use
# the same state so both paths feed the same deterministic recommender.
if "recommender_subject_names" not in st.session_state:
    st.session_state["recommender_subject_names"] = []
if "research_text" not in st.session_state:
    st.session_state["research_text"] = ""
if "ai_subject_reason" not in st.session_state:
    st.session_state["ai_subject_reason"] = ""
if "ai_request_count" not in st.session_state:
    st.session_state["ai_request_count"] = 0

MAX_AI_REQUESTS_PER_SESSION = 10

st.markdown("### 1. Choose how to start")
start_mode = st.radio(
    "Input method",
    ["✨ Describe my research", "🎯 Select QS Subjects manually"],
    horizontal=True,
    label_visibility="collapsed",
)

if start_mode == "✨ Describe my research":
    with st.container(border=True):
        st.markdown("#### Describe your research")
        st.caption(
            "Paste a paper title, abstract, keywords, or a short research description. "
            "AI will only suggest QS Subjects; it does not choose or invent journals."
        )

        research_text = st.text_area(
            "Research title / abstract / keywords",
            value=st.session_state.get("research_text", ""),
            height=170,
            max_chars=10000,
            placeholder=(
                "Example: We develop machine-learning models using medical imaging "
                "and electronic health records to predict cardiovascular disease."
            ),
        )

        identify_clicked = st.button(
            "Identify QS Subjects",
            type="primary",
            use_container_width=True,
        )

        if identify_clicked:
            st.session_state["research_text"] = research_text

            if not research_text.strip():
                st.warning("Enter a research title, abstract, keywords, or description first.")
            elif st.session_state["ai_request_count"] >= MAX_AI_REQUESTS_PER_SESSION:
                st.warning(
                    "AI suggestions are limited to 10 requests per session in this demo. "
                    "You can continue by selecting QS Subjects manually below."
                )
            else:
                try:
                    with st.spinner("Identifying relevant QS Subjects..."):
                        classification = classify_qs_subjects(research_text)

                    st.session_state["ai_request_count"] += 1
                    suggested_names = [
                        name
                        for name in classification.get("subjects", [])
                        if name in name_to_code
                    ]

                    st.session_state["recommender_subject_names"] = suggested_names
                    st.session_state["ai_subject_reason"] = classification.get("reason", "")

                    if suggested_names:
                        st.success(
                            f"Identified {len(suggested_names)} QS Subject"
                            + ("s." if len(suggested_names) != 1 else ".")
                        )
                    else:
                        st.warning(
                            "AI could not confidently map this text to the current QS taxonomy. "
                            "Please choose QS Subjects manually below."
                        )

                except AIProviderError as exc:
                    cause = exc.__cause__

                    st.error("AI provider error — temporary debug mode")

                    if cause is not None:
                        st.code(
                            f"{type(cause).__name__}: {cause}"
                        )
                    else:
                        st.code(
                            f"{type(exc).__name__}: {exc}"
                        )

                    st.warning(
                        "You can still select QS Subjects manually below."
                    )
                except Exception:
                    st.warning(
                        "AI subject suggestion could not be completed. "
                        "You can still select QS Subjects manually below."
                    )

        reason = st.session_state.get("ai_subject_reason", "")
        if reason and st.session_state.get("recommender_subject_names"):
            st.caption(f"AI rationale: {reason}")

st.markdown("### 2. Review or select QS Subjects")
selected_names = st.multiselect(
    "QS Subjects",
    options=subject_names,
    key="recommender_subject_names",
    placeholder="Choose one or more QS Subjects...",
    help=(
        "AI suggestions, when used, appear here automatically. Review them before searching, "
        "and add or remove subjects as needed."
    ),
)

if selected_names:
    st.caption("Subjects that will be used by the journal recommender")
    render_qs_chips("; ".join(selected_names))

st.markdown("### 3. Set your preferences")
c1, c2 = st.columns([1.4, 0.8])
with c1:
    quality_label = st.radio(
        "Quality preference",
        ["Prioritize Q1", "Q1 only", "All quartiles"],
        index=0,
        help=(
            "Q1 refers to SJR quartile and is used here as a journal-quality signal, "
            "not as a direct QS ranking indicator."
        ),
    )
with c2:
    result_limit = st.selectbox("Results", [10, 20, 50], index=1)

st.caption(
    "Ranking priority: Q1 first (when selected), then broader QS Faculty coverage (5 → 1), "
    "higher H-index, selected-subject match, total QS Subject count, and SJR."
)

submitted = st.button("Find journals", type="primary", use_container_width=True)

if submitted:
    if not selected_names:
        st.warning("Select at least one QS Subject before searching.")
        st.session_state.pop("recommendation_results", None)
    else:
        quality_map = {
            "Prioritize Q1": QUALITY_PRIORITIZE_Q1,
            "Q1 only": QUALITY_Q1_ONLY,
            "All quartiles": QUALITY_ALL,
        }
        selected_codes = tuple(name_to_code[name] for name in selected_names)
        request = RecommendationRequest(
            subject_codes=selected_codes,
            quality_preference=quality_map[quality_label],
            multidisciplinary_preference=MULTI_ANY,
            limit=int(result_limit),
        )
        with st.spinner("Matching QS Subjects to journals..."):
            results = recommend_journals(request)

        st.session_state["recommendation_results"] = results
        st.session_state["recommendation_context"] = {
            "selected_names": list(selected_names),
            "quality": quality_label,
        }

results = st.session_state.get("recommendation_results")
context = st.session_state.get("recommendation_context", {})

if results is not None:
    st.divider()
    st.markdown("## Recommendations")
    selected_context_names = context.get("selected_names", [])

    if selected_context_names:
        st.caption("QS Subjects used for this recommendation")
        render_qs_chips("; ".join(selected_context_names))
        st.caption(
            f"Quality: {context.get('quality', '—')} · "
            "Ranking favors wider coverage across the 5 QS Broad Faculty Areas."
        )

    summary = recommendation_summary(results)
    render_summary_bar(
        [
            ("Returned", f"{summary['results']:,}"),
            ("Full subject match", f"{summary['full_match']:,}"),
            ("Q1", f"{summary['q1']:,}"),
            ("Cross-faculty", f"{summary['cross_faculty']:,}"),
        ]
    )

    if results.empty:
        st.info(
            "No journals match the current criteria. Try 'Prioritize Q1' instead of 'Q1 only', "
            "or select a broader QS Subject set."
        )
    else:
        st.markdown("### Top matches")
        render_recommendation_cards(results, max_cards=min(6, len(results)))

        st.markdown("### All returned results")
        selected_id = render_recommendations_table(results)

        csv = results.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Download recommendations as CSV",
            csv,
            "qs_journal_recommendations.csv",
            "text/csv",
        )

        if selected_id:
            st.divider()
            st.markdown("### Journal detail")
            detail = fetch_journal_detail(selected_id)
            if detail is not None:
                render_journal_detail(detail)

        st.caption(
            "Recommendations are generated from the database's QS mappings and source metrics. "
            "AI is used only to suggest QS Subjects from research text; journal ranking remains "
            "database-driven and deterministic."
        )
