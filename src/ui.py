"""Shared rendering helpers: summary bar, result tables, detail panels.

Keeping these here (instead of inline in each page) is what lets the
Journals and Conferences pages share one visual language without copy-pasted
Streamlit boilerplate.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

PAGE_SIZE_OPTIONS = [25, 50, 100, 200, "All"]

# Green -> red mirrors "best to weakest", per the user's SJR request (Q1 green ... Q4 red).
SJR_QUARTILE_COLORS = {
    "Q1": "#2E7D32",
    "Q2": "#F9A825",
    "Q3": "#EF6C00",
    "Q4": "#C62828",
}
# ICORE letter-grade rank uses the same green->red quality gradient. "Unranked" is
# deliberately neutral gray, not red — it means ICORE reviewed the venue and chose not
# to grade it, which is not the same as a low grade or "not found".
ICORE_RANK_COLORS = {
    "A*": "#1B5E20",
    "A": "#2E7D32",
    "B": "#F9A825",
    "C": "#EF6C00",
    "Unranked": "#757575",
}

def _badge_style(color_map: dict[str, str]):
    def _style(value: object) -> str:
        color = color_map.get(value)
        if not color:
            return ""
        return f"background-color: {color}22; color: {color}; font-weight: 600; border-radius: 4px;"

    return _style


# pandas Styler builds a render entry for every cell in the dataframe (not just the
# styled column), so it has a hard cap (`styler.render.max_elements`, default 262144)
# on rows*cols. That's easy to blow past with "All" on an unfiltered ~49k-row table.
# Above the cap we just skip coloring rather than raising the limit — Styler's
# per-cell Python pass genuinely gets slow at that scale, and this is cosmetic, not
# a data-correctness concern.
_STYLER_MAX_ELEMENTS = pd.get_option("styler.render.max_elements")


def _style_if_small_enough(df: pd.DataFrame, column: str, color_map: dict[str, str]):
    if df.shape[0] * df.shape[1] > _STYLER_MAX_ELEMENTS:
        return df, False
    return df.style.map(_badge_style(color_map), subset=[column]), True


def inject_base_style() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1240px; }
        .vinuni-title { color: #681824; font-weight: 760; letter-spacing: -0.035em; }
        .vinuni-kicker {
            color: #8E2636; font-size: .80rem; font-weight: 700; letter-spacing: .08em;
            text-transform: uppercase; margin-bottom: .35rem;
        }
        .vinuni-hero {
            padding: 2rem 2.1rem; border: 1px solid #E8DCDD; border-radius: 20px;
            background: linear-gradient(135deg, #FFFDFD 0%, #FAF3F4 100%);
            margin-bottom: 1.1rem;
        }
        .vinuni-hero h1 {
            color: #681824; font-size: clamp(2rem, 4vw, 3.25rem); margin: 0 0 .65rem 0;
            line-height: 1.05; letter-spacing: -.045em;
        }
        .vinuni-hero p { color: #5C5153; font-size: 1.05rem; max-width: 820px; margin: 0; }
        .vinuni-card {
            border: 1px solid #E9E1E2; border-radius: 16px; padding: 1.2rem 1.25rem;
            background: #FFFFFF; box-shadow: 0 5px 18px rgba(69, 26, 35, .035);
        }
        .recommend-card {
            border: 1px solid #E8DFE1; border-radius: 18px; padding: 1.15rem 1.25rem;
            background: #FFFFFF; margin: .7rem 0; box-shadow: 0 5px 18px rgba(69,26,35,.035);
        }
        .recommend-rank { color:#9B8B8E; font-size:.78rem; font-weight:700; letter-spacing:.08em; }
        .recommend-title { color:#3A262A; font-size:1.12rem; font-weight:750; margin:.2rem 0 .5rem 0; }
        .recommend-meta { color:#6B6062; font-size:.88rem; margin-top:.55rem; }
        .source-links { display:flex; flex-wrap:wrap; gap:.45rem; margin-top:.8rem; }
        .source-link {
            display:inline-block; text-decoration:none !important; background:#FFFFFF; color:#681824 !important;
            border:1px solid #DCC9CD; border-radius:9px; padding:.34rem .68rem; font-size:.80rem; font-weight:700;
        }
        .source-link:hover { background:#F8EEF0; border-color:#CBAEB4; }
        .qs-chip {
            display:inline-block; background:#F8EEF0; color:#7A1E2B; border:1px solid #E9D4D8;
            border-radius:999px; padding:.18rem .6rem; margin:.15rem .2rem .15rem 0;
            font-size:.78rem; font-weight:600;
        }
        .qs-chip-selected {
            background:#681824; color:#FFFFFF; border-color:#681824; font-weight:700;
        }
        .faculty-chip {
            display:inline-block; background:#F4F1F2; color:#4F4547; border:1px solid #DED7D9;
            border-radius:999px; padding:.18rem .6rem; margin:.15rem .2rem .15rem 0;
            font-size:.78rem; font-weight:600;
        }
        .mapping-label {
            color:#6B6062; font-size:.77rem; font-weight:750; letter-spacing:.025em;
            text-transform:uppercase; margin-top:.75rem; margin-bottom:.15rem;
        }
        .mapping-note { color:#8B7F82; font-size:.76rem; margin-top:.18rem; }
        .quality-badge {
            display:inline-block; border-radius:999px; padding:.18rem .58rem;
            font-size:.76rem; font-weight:750; margin-left:.3rem;
        }
        .q1-badge { background:#E9F5EC; color:#226B34; border:1px solid #CDE7D3; }
        .neutral-badge { background:#F4F1F2; color:#62575A; border:1px solid #E4DEE0; }
        .filter-chip-row { display:flex; flex-wrap:wrap; gap:.4rem; margin:.25rem 0 .75rem 0; }
        .filter-chip {
            background:#FBEFF0; color:#7A1E2B; border:1px solid #EAD3D6;
            border-radius:999px; padding:.15rem .7rem; font-size:.82rem; white-space:nowrap;
        }
        div[data-testid="stMetricValue"] { color:#681824; }
        div[data-testid="stButton"] button[kind="primary"] { border-radius: 10px; }
        div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_summary_bar(items: list[tuple[str, object]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.metric(label, value)


def render_active_filters(chips: list[str]) -> None:
    if not chips:
        st.caption("No filters applied — showing the full universe.")
        return
    html = "".join(f"<span class='filter-chip'>{chip}</span>" for chip in chips)
    st.markdown(f"<div class='filter-chip-row'>{html}</div>", unsafe_allow_html=True)


def render_pagination(total: int, page_key: str, page_size_key: str) -> tuple[int, int | None]:
    left, mid, right = st.columns([2, 3, 2])
    with left:
        page_size_label = st.selectbox(
            "Rows per page", PAGE_SIZE_OPTIONS, index=1, key=page_size_key,
            help="'All' shows every matching result at once — fine for filtered/searched results, "
            "slower for the full unfiltered universe.",
        )
    page_size = None if page_size_label == "All" else int(page_size_label)
    with mid:
        st.caption(f"{total:,} result(s)")
    if page_size is None:
        return 1, None
    total_pages = max(1, (total - 1) // page_size + 1) if total else 1
    with right:
        page = st.number_input(
            "Page", min_value=1, max_value=total_pages, value=1, step=1, key=page_key
        )
    return int(page), page_size


def _clean_identifier(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def scopus_source_url(source_id: object) -> str:
    sid = _clean_identifier(source_id)
    return f"https://www.scopus.com/sourceid/{sid}" if sid else ""


def scimago_source_url(sjr_sourceid: object) -> str:
    sid = _clean_identifier(sjr_sourceid)
    return f"https://www.scimagojr.com/journalsearch.php?q={sid}&tip=sid" if sid else ""


def _with_source_links(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    display["scopus_url"] = display["source_id"].map(scopus_source_url)
    if "sjr_sourceid" in display.columns:
        display["scimago_url"] = display["sjr_sourceid"].map(scimago_source_url)
    else:
        display["scimago_url"] = ""
    return display


def render_journals_table(df: pd.DataFrame, key: str) -> str | None:
    """Renders the table; returns the selected row's source_id, if any."""
    if df.empty:
        st.info("No journals/other sources match the current search and filters.")
        return None
    df = _with_source_links(df)
    df["sjr_best_quartile"] = df["sjr_best_quartile"].fillna("")
    styled, colored = _style_if_small_enough(df, "sjr_best_quartile", SJR_QUARTILE_COLORS)
    if not colored:
        st.caption(
            f"Showing {len(df):,} rows — too many to color-code SJR Quartile at once. "
            "Narrow your filters or pick a smaller \"Rows per page\" to see the colors."
        )
    event = st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        row_height=88,
        height=min(720, 80 + 88 * len(df)),
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_order=[
            "source_title",
            "scimago_url",
            "scopus_url",
            "issn_normalized",
            "eissn_normalized",
            "sjr_best_quartile",
            "qs_faculty_area_count",
            "qs_faculty_area_names",
            "qs_subject_names",
            "active_status",
            "publisher",
            "coverage",
            "source_type",
            "sjr",
        ],
        column_config={
            "source_title": st.column_config.TextColumn("Title", width="large"),
            "scimago_url": st.column_config.LinkColumn("SCImago", display_text="SCImago ↗", width="small"),
            "scopus_url": st.column_config.LinkColumn("Scopus", display_text="Scopus ↗", width="small"),
            "issn_normalized": st.column_config.TextColumn("ISSN"),
            "eissn_normalized": st.column_config.TextColumn("EISSN"),
            "sjr_best_quartile": st.column_config.TextColumn(
                "SJR Quartile", help="SCImago's own quartile — not the CiteScore quartile."
            ),
            "qs_faculty_area_count": st.column_config.NumberColumn(
                "QS Faculty #", help="Number of distinct QS Broad Faculty Areas — not the QS Subject count."
            ),
            "qs_faculty_area_names": st.column_config.TextColumn("QS Faculty Areas", width="medium"),
            "qs_subject_names": st.column_config.TextColumn("QS Subjects", width="medium"),
            "active_status": st.column_config.TextColumn("Status"),
            "publisher": st.column_config.TextColumn("Publisher"),
            "coverage": st.column_config.TextColumn("Coverage"),
            "source_type": st.column_config.TextColumn("Type"),
            "sjr": st.column_config.NumberColumn("SJR", format="%.3f"),
        },
    )
    rows = event.selection.rows if event and event.selection else []
    return str(df.iloc[rows[0]]["source_id"]) if rows else None


def render_conferences_table(df: pd.DataFrame, key: str) -> str | None:
    """Renders the table; returns the selected row's source_id, if any."""
    if df.empty:
        st.info("No conferences match the current search and filters.")
        return None
    display = df.copy()
    display["icore_rank_display"] = display["icore_rank_group"].fillna("—")
    styled, colored = _style_if_small_enough(display, "icore_rank_display", ICORE_RANK_COLORS)
    if not colored:
        st.caption(
            f"Showing {len(display):,} rows — too many to color-code ICORE Rank at once. "
            "Narrow your filters or pick a smaller \"Rows per page\" to see the colors."
        )
    event = st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        row_height=88,
        height=min(720, 80 + 88 * len(display)),
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_order=[
            "source_title",
            "issn_normalized",
            "eissn_normalized",
            "icore_rank_display",
            "qs_faculty_area_count",
            "qs_faculty_area_names",
            "qs_subject_names",
            "official_series_website",
            "latest_event_website",
            "icore_profile_url",
            "icore_acronym",
            "source_type",
            "active_status",
        ],
        column_config={
            "source_title": st.column_config.TextColumn("Conference Title", width="large"),
            "issn_normalized": st.column_config.TextColumn("ISSN"),
            "eissn_normalized": st.column_config.TextColumn("EISSN"),
            "icore_rank_display": st.column_config.TextColumn(
                "ICORE Rank",
                help="'Unranked' = ICORE matched a venue but explicitly rates it Unranked. Blank = no ICORE match.",
            ),
            "qs_faculty_area_count": st.column_config.NumberColumn(
                "QS Faculty #", help="Number of distinct QS Broad Faculty Areas — not the QS Subject count."
            ),
            "qs_faculty_area_names": st.column_config.TextColumn("QS Faculty Areas", width="medium"),
            "qs_subject_names": st.column_config.TextColumn("QS Subjects", width="medium"),
            "official_series_website": st.column_config.LinkColumn("Official Website", display_text="Official ↗"),
            "latest_event_website": st.column_config.LinkColumn("Latest Event", display_text="Latest ↗"),
            "icore_profile_url": st.column_config.LinkColumn("ICORE Profile", display_text="ICORE ↗"),
            "icore_acronym": st.column_config.TextColumn("Acronym"),
            "source_type": st.column_config.TextColumn("Type"),
            "active_status": st.column_config.TextColumn("Status"),
        },
    )
    rows = event.selection.rows if event and event.selection else []
    return str(display.iloc[rows[0]]["source_id"]) if rows else None


def _field(label: str, value) -> None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        value = "—"
    st.markdown(f"**{label}:** {value}")


def render_journal_detail(row: pd.Series) -> None:
    st.markdown(f"### {row.get('source_title', '')}")
    c1, c2 = st.columns(2)
    with c1:
        _field("Scopus Source ID", row.get("source_id"))
        _field("Type", row.get("source_type"))
        _field("Status", row.get("active_status"))
        _field("ISSN", row.get("issn_normalized"))
        _field("EISSN", row.get("eissn_normalized"))
        _field("Publisher", row.get("publisher"))
        _field("Coverage", row.get("coverage"))
    with c2:
        st.markdown("**SJR**")
        _field("Year", row.get("sjr_year"))
        _field("SJR", row.get("sjr"))
        _field("SJR Best Quartile", row.get("sjr_best_quartile"))
        _field("H-index", row.get("sjr_h_index"))
        st.markdown("**QS**")
        _field("QS Faculty Count", row.get("qs_faculty_area_count"))
        _field("QS Faculty Areas", row.get("qs_faculty_area_names"))
        _field("QS Subjects", row.get("qs_subject_names"))

    st.markdown("**External links**")
    link_cols = st.columns(2)
    scopus_url = scopus_source_url(row.get("source_id"))
    scimago_url = scimago_source_url(row.get("sjr_sourceid"))
    with link_cols[0]:
        if scimago_url:
            st.link_button("SCImago ↗", scimago_url, use_container_width=True)
        else:
            st.caption("No SCImago/SJR record available.")
    with link_cols[1]:
        if scopus_url:
            st.link_button("Scopus ↗", scopus_url, use_container_width=True)

    st.markdown("**Scopus classification (ASJC)**")
    _field("ASJC codes", row.get("asjc_codes"))
    _field("ASJC names", row.get("asjc_names"))

    with st.expander("Data details"):
        _field("SJR match status/method", f"{row.get('sjr_match_status')} / {row.get('sjr_match_method')}")
        _field("QS specific mapping status", row.get("specific_qs_mapping_status"))
        _field("QS faculty-area mapping status", row.get("faculty_area_mapping_status"))
        _field("Scopus snapshot", row.get("source_snapshot"))


def render_conference_detail(row: pd.Series) -> None:
    st.markdown(f"### {row.get('source_title', '')}")
    c1, c2 = st.columns(2)
    with c1:
        _field("Scopus Source ID", row.get("source_id"))
        _field("ICORE Conference Title", row.get("icore_conference_title"))
        _field("Acronym", row.get("icore_acronym"))
        _field("Status", row.get("active_status"))
        _field("ISSN", row.get("issn_normalized"))
        _field("EISSN", row.get("eissn_normalized"))
        _field("Coverage", row.get("coverage"))
    with c2:
        st.markdown("**ICORE**")
        _field("ICORE Year", row.get("icore_year"))
        _field("Rank", row.get("icore_rank_raw"))
        _field("FoR Codes", row.get("icore_for_codes"))
        _field("FoR Names", row.get("icore_for_names"))
        if row.get("icore_profile_url"):
            st.markdown(f"[ICORE Profile ↗]({row.get('icore_profile_url')})")
        st.markdown("**QS**")
        _field("QS Faculty Count", row.get("qs_faculty_area_count"))
        _field("QS Faculty Areas", row.get("qs_faculty_area_names"))
        _field("QS Subjects", row.get("qs_subject_names"))

    st.markdown("**ASJC**")
    _field("ASJC codes", row.get("asjc_codes"))
    _field("ASJC names", row.get("asjc_names"))

    st.markdown("**Links**")
    link_cols = st.columns(2)
    with link_cols[0]:
        if row.get("official_series_website"):
            st.markdown(f"[Official conference/series website ↗]({row.get('official_series_website')})")
        else:
            st.caption("No official series website curated yet.")
    with link_cols[1]:
        if row.get("latest_event_website"):
            st.markdown(f"[Latest event website ↗]({row.get('latest_event_website')})")
        else:
            st.caption("No latest-event website curated yet.")

    with st.expander("Data details"):
        _field("ICORE match method / status", f"{row.get('icore_match_method')} / {row.get('icore_match_status')}")
        _field("DBLP available", row.get("icore_dblp_available"))
        st.caption(
            "\"Not found in ICORE\" and \"Unranked\" are different: the first means no ICORE "
            "venue could be confidently matched; the second means ICORE explicitly rates the "
            "matched venue as Unranked."
        )


def _split_semicolon(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def render_qs_chips(values: object) -> None:
    parts = _split_semicolon(values)
    if not parts:
        st.caption("No QS Subject mapping available.")
        return
    markup = "".join(f"<span class='qs-chip'>{html.escape(part)}</span>" for part in parts)
    st.markdown(markup, unsafe_allow_html=True)


def render_recommendation_cards(df: pd.DataFrame, max_cards: int = 6) -> None:
    """Render the leading recommendation results as compact, auditable cards."""
    if df.empty:
        st.info("No journals match the current criteria. Try relaxing the multidisciplinary or quality preference.")
        return

    for i, (_, row) in enumerate(df.head(max_cards).iterrows(), start=1):
        title = html.escape(str(row.get("source_title") or "Untitled source"))
        quartile = str(row.get("sjr_best_quartile") or "—")
        qclass = "q1-badge" if quartile == "Q1" else "neutral-badge"
        matched = int(row.get("matched_subject_count") or 0)
        selected = int(row.get("selected_subject_count") or 0)
        faculties = int(row.get("qs_faculty_area_count") or 0)
        matched_faculties = int(row.get("matched_faculty_count") or 0)
        total_subjects = int(row.get("qs_subject_count") or 0)
        matched_names = _split_semicolon(row.get("matched_subject_names"))
        all_subject_names = _split_semicolon(row.get("qs_subject_names"))
        all_faculty_names = _split_semicolon(row.get("qs_faculty_area_names"))
        matched_lookup = {name.casefold() for name in matched_names}

        subject_chip_html = "".join(
            (
                f"<span class='qs-chip qs-chip-selected'>{html.escape(name)}</span>"
                if name.casefold() in matched_lookup
                else f"<span class='qs-chip'>{html.escape(name)}</span>"
            )
            for name in all_subject_names
        )
        faculty_chip_html = "".join(
            f"<span class='faculty-chip'>{html.escape(name)}</span>"
            for name in all_faculty_names
        )
        publisher = html.escape(str(row.get("publisher") or "Publisher unavailable"))
        sjr = row.get("sjr")
        hindex = row.get("sjr_h_index")
        sjr_text = "—" if pd.isna(sjr) else f"{float(sjr):.3f}"
        h_text = "—" if pd.isna(hindex) else f"{float(hindex):.0f}"
        cross = "Cross-faculty" if faculties >= 2 else "Single faculty area"
        scopus_url = scopus_source_url(row.get("source_id"))
        scimago_url = scimago_source_url(row.get("sjr_sourceid"))
        links = []
        if scimago_url:
            links.append(f'<a class="source-link" href="{html.escape(scimago_url, quote=True)}" target="_blank" rel="noopener noreferrer">SCImago ↗</a>')
        if scopus_url:
            links.append(f'<a class="source-link" href="{html.escape(scopus_url, quote=True)}" target="_blank" rel="noopener noreferrer">Scopus ↗</a>')
        links_html = f'<div class="source-links">{"".join(links)}</div>' if links else ""

        st.markdown(
            f"""
            <div class="recommend-card">
              <div class="recommend-rank">RECOMMENDATION {i}</div>
              <div class="recommend-title">{title}
                <span class="quality-badge {qclass}">{html.escape(quartile)}</span>
              </div>
              <div><strong>{matched}/{selected}</strong> selected QS Subject(s) matched</div>
              <div style="margin-top:.35rem"><strong>{faculties}/5 QS Broad Faculty Areas</strong> · H-index: <strong>{h_text}</strong></div>

              <div class="mapping-label">All QS Subjects ({total_subjects})</div>
              <div>{subject_chip_html or '<span class="mapping-note">No QS Subject mapping available.</span>'}</div>
              <div class="mapping-note">Dark chip(s) = subject(s) you selected and this journal matches.</div>

              <div class="mapping-label">QS Broad Faculty Areas ({faculties}/5)</div>
              <div>{faculty_chip_html or '<span class="mapping-note">No QS Broad Faculty mapping available.</span>'}</div>

              <div class="recommend-meta">SJR: {sjr_text} · {publisher}</div>
              {links_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Why recommended", expanded=False):
            st.write(
                f"Matches {matched} of the {selected} QS Subject(s) you selected and is mapped "
                f"across {faculties} of the 5 QS Broad Faculty Areas. Its H-index is {h_text}."
            )
            if quartile == "Q1":
                st.write("It is also Q1 by SJR, which is being used here as a journal-quality signal.")
            st.caption(
                "Ranking favors Q1 first, then broader coverage across the five QS Broad Faculty Areas, "
                "followed by H-index and subject relevance. Q1/SJR is a quality signal, not itself a QS ranking indicator."
            )


def render_recommendations_table(df: pd.DataFrame, key: str = "recommendations_table") -> str | None:
    if df.empty:
        return None
    display = _with_source_links(df)
    display["match"] = display["matched_subject_count"].astype(str) + "/" + display["selected_subject_count"].astype(str)
    event = st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        row_height=88,
        height=min(720, 90 + 88 * len(display)),
        on_select="rerun",
        selection_mode="single-row",
        key=key,
        column_order=[
            "source_title",
            "scimago_url",
            "scopus_url",
            "sjr_best_quartile",
            "qs_faculty_area_count",
            "sjr_h_index",
            "match",
            "matched_subject_names",
            "qs_faculty_area_names",
            "qs_subject_count",
            "sjr",
            "publisher",
        ],
        column_config={
            "source_title": st.column_config.TextColumn("Journal", width="large"),
            "scimago_url": st.column_config.LinkColumn("SCImago", display_text="SCImago ↗", width="small"),
            "scopus_url": st.column_config.LinkColumn("Scopus", display_text="Scopus ↗", width="small"),
            "sjr_best_quartile": st.column_config.TextColumn("SJR Quartile"),
            "match": st.column_config.TextColumn("QS Match"),
            "matched_subject_names": st.column_config.TextColumn("Matched QS Subjects", width="large"),
            "qs_faculty_area_count": st.column_config.NumberColumn("QS Broad Faculties (of 5)"),
            "qs_faculty_area_names": st.column_config.TextColumn("QS Faculty Areas", width="large"),
            "qs_subject_count": st.column_config.NumberColumn("Total QS Subjects"),
            "sjr": st.column_config.NumberColumn("SJR", format="%.3f"),
            "sjr_h_index": st.column_config.NumberColumn("H-index", format="%.0f"),
            "publisher": st.column_config.TextColumn("Publisher", width="medium"),
        },
    )
    rows = event.selection.rows if event and event.selection else []
    return str(display.iloc[rows[0]]["source_id"]) if rows else None
