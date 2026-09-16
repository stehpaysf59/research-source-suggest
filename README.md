# VinUni QS Multidisciplinary Journal Finder — V2

A read-only Streamlit application for discovering journals through QS Subject and QS Broad Faculty mappings. V2 focuses the product experience on **multidisciplinary journal discovery** while preserving the full manual Journal Explorer.

## What V2 does

- Lets users select one or more QS Subjects from the canonical database.
- Recommends real journals from `vinuni_source_intelligence.db` using transparent, deterministic ranking.
- Supports three quality modes: **Prioritize Q1**, **Q1 only**, and **All quartiles**.
- Supports three multidisciplinary modes: **Cross-faculty**, **Multiple QS Subjects**, and **Any**.
- Shows why a journal was recommended: selected QS Subject overlap, QS Faculty coverage, total QS Subject count, SJR quartile, SJR and H-index.
- Keeps the existing advanced Journal Explorer for manual searching/filtering.
- Keeps conference code/data in the repository under `legacy_pages/`, but removes it from the primary navigation for this journal-focused phase.
- Is **AI-ready but AI-independent**: V2 needs no API key and no LLM to function.

## Recommendation order

For journals that meet the selected filters, the recommender ranks by:

1. selected QS Subjects matched;
2. QS Broad Faculty Areas relevant to the selected subjects;
3. cross-faculty status;
4. Q1 priority when `Prioritize Q1` is selected;
5. total QS Subject count;
6. SJR;
7. H-index;
8. title for stable ordering.

`Q1 only` is a hard filter. `Prioritize Q1` is a ranking preference. `All quartiles` does not add a Q1 ranking bonus.

A journal with many QS Subjects does **not** automatically rank first: matching the user's selected fields takes priority.

## Pages

- **Home** — product introduction and paths into recommendation/manual exploration.
- **Find Journals** — the new QS multidisciplinary recommender.
- **Journal Explorer** — the existing advanced manual search/filter experience.
- **About** — recommendation logic, terminology and methodology notes.

## Project structure

```text
research-source-explorer/
├── app.py
├── pages/
│   ├── 1_Find_Journals.py
│   ├── 2_Journal_Explorer.py
│   └── 3_About.py
├── legacy_pages/
│   └── 2_Conferences.py          # retained for a later phase
├── src/
│   ├── database.py
│   ├── queries.py
│   ├── search.py
│   ├── filters.py
│   ├── recommender.py             # deterministic recommendation engine
│   ├── subject_classifier.py      # provider-neutral future AI hook
│   └── ui.py
├── data/
│   └── vinuni_source_intelligence.db
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── AGENTS.md                      # future Codex/project instructions
├── requirements.txt
└── README.md
```

## Local setup on Windows

From the project folder:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

Then open the local URL Streamlit prints, normally `http://localhost:8501`.

If you already have a working virtual environment, simply run:

```bash
python -m streamlit run app.py
```

## Database

The app reads:

```text
data/vinuni_source_intelligence.db
```

by default. To use another copy without changing code, set `VINUNI_DB_PATH`.

No Supabase/PostgreSQL is required. The current use case is read-only and the bundled SQLite database already provides the source mappings, indexes and FTS search needed by the app.

## AI-ready design

V2 deliberately does not require an LLM. The manual QS Subject selector is the reliable core path.

Future V2.1 flow:

```text
Research title / abstract / free text
              ↓
optional AI subject classifier
              ↓
existing QS Subject codes only
              ↓
user reviews / edits subjects
              ↓
src/recommender.py
              ↓
SQLite
              ↓
real journal recommendations
```

The stable integration point is `src/subject_classifier.py`. A future provider can be Groq, OpenRouter, OpenAI, Gemini or a local embedding model. The recommender should not depend on which provider is used.

AI must not invent journals, rankings, SJR values or QS mappings. Journal recommendations and metadata always come from the SQLite database.

V2 requires no `.streamlit/secrets.toml`. A commented example exists at `.streamlit/secrets.toml.example` for a later AI phase.

## Streamlit Community Cloud

The app remains compatible with the existing Streamlit deployment pattern:

1. Test locally.
2. Push the V2 code to GitHub.
3. Point/keep Streamlit Community Cloud at `app.py` on the deployment branch.
4. No secrets are needed for V2.
5. When AI is added later, add the provider key through **App settings → Secrets**, not GitHub.

## Important interpretation note

SJR Q1 is displayed and optionally prioritized as a **journal-quality signal**. It is not itself a QS ranking indicator, and the app does not claim that publishing in a recommended journal will add a specific number of QS points.

## V2 validation performed during build

- All Python files compile successfully.
- Recommendation SQL was smoke-tested directly against the bundled SQLite database.
- Example `Data Science + Medicine` queries returned real mapped sources and correctly enforced Q1-only / cross-faculty / multi-subject modes.
- The Streamlit server starts successfully using the Streamlit 1.62 files bundled with the original Windows environment. Full browser/session rendering was not fully reproducible inside the Linux build container because those bundled binary packages are Windows-specific; run the local command above on your Windows environment for the final visual check.
