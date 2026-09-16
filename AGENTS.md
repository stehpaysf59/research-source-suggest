# Project purpose

This is a Streamlit application for discovering and recommending research journals using QS subject mappings.

Primary goal: help researchers identify multidisciplinary journals aligned with selected QS Subjects, while exposing transparent source-quality signals such as SJR quartile, SJR and H-index.

## Architecture

Current stack:
- Python
- Streamlit
- SQLite
- Pandas
- SQLite FTS5

Do not introduce Supabase, PostgreSQL, FastAPI, React/Next.js, vector databases, LangChain, or agent frameworks unless explicitly requested.

## Recommendation rules

Journal recommendations must come only from the existing SQLite database. Never invent journal titles or metadata.

For selected QS Subjects, the deterministic recommender ranks by:
1. selected QS Subjects matched;
2. relevant QS Broad Faculty Areas matched;
3. cross-faculty status;
4. Q1 priority when the user chooses it;
5. total QS Subject count;
6. SJR;
7. H-index.

Relevance to the selected subjects is more important than simply having many QS Subjects.

## AI boundary

AI is optional and must only help translate research text into existing QS Subject codes and/or explain already retrieved results. AI must not invent or select journals from model memory. All journal recommendations and metadata come from the database via `src/recommender.py`.

## Scope control

Do not modify conference functionality unless explicitly requested. Avoid unrelated refactoring. Before changing code, inspect only relevant files and reuse existing data-access functions where practical.
