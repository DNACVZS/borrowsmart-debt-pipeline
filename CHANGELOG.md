# Changelog

## v1 -> v2 Changes

| Area | What Changed |
|------|-------------|
| **Setup / data loading** | Replaced Colab file upload with auto-clone from GitHub repo -- users just hit Runtime -> Run All, no manual upload needed. Added REPO_URL, REPO_DIR, DATA_DIR constants and git clone logic. resolve_input_path() rewritten to check cloned repo first, then local paths, then Colab upload as a last resort |
| **Error handling** | Wrapped each dataset loader (FSA, ACS, CFPB) in try/except with descriptive failure messages (e.g., "PIPELINE HALTED -- FSA load failed: ...") instead of bare function calls |
| **Docstrings** | Added docstrings to all helper and loader functions: as_numeric(), is_empty_cell(), non_empty_tokens(), find_fsa_sheet_and_header(), extract_fsa_reporting_period(), find_header_col_index(), load_fsa_state_level(), load_acs_state_level(), load_cfpb_state_level() |
| **Error messages** | Improved error messages in find_fsa_sheet_and_header() and load_fsa_state_level() to give more context on what went wrong |
| **Risk thresholds** | Extracted hardcoded 0.45 / 0.60 into named constants (RISK_LOW_THRESHOLD, RISK_HIGH_THRESHOLD). Added block comment explaining the rationale -- quartile boundaries of the observed DTI distribution |
| **Visualization** | Switched from plt.figure() to fig, ax = plt.subplots(). Added color-coding by risk tier (red = High, orange = Medium, blue = Low). Added value labels on each bar. Added PNG export (fig.savefig()) |
| **README** | Updated to point to v2 as the primary notebook, documented all outputs and pipeline steps |

**Sections unchanged from v1 -> v2:** Success metrics, Standardize (Section 3), Join (Section 4), Validation (Section 6), Outputs (Section 7), Documentation (Section 9)

## v2 -> v3 Changes

| Area | What Changed |
|------|-------------|
| **Storage layer (new Section 8)** | Added SQLite database -- typed CREATE TABLE schema, loads merged data with to_sql(), verifies 51 rows written. 3 sample advisor queries: high-risk states for priority outreach, high-burden states with growing originations, summary stats by risk tier. All queries timed to show < 1 second |
| **Success metrics** | Strengthened the bullet list into a table with specific, measurable thresholds (e.g., "51 rows after merge," "all SQL queries < 1 second," "end-to-end under 10 seconds"). Addresses Prof. Firrincieli's proposal feedback about being more concrete |
| **Data lineage summary (new Section 11)** | Print-based overview: sources with row counts, join key, computed fields, storage location, export files, pipeline version |
| **Code cleanup** | Removed duplicate pipeline_start assignment from imports cell (it was being set again after repo clone anyway) |
| **Section renumbering** | Visualization moved from Section 8 -> 9, Documentation from Section 9 -> 10 |
| **README** | Points to v3, SQLite added to architecture diagram, borrowsmart_prototype.db added to outputs table, updated repo structure tree, version notes updated |
| **.gitignore** | Added *.db to exclude generated SQLite files |

**Sections unchanged from v2 -> v3:** All loader functions, joins, standardization, metric computation, validation checks, visualization, documentation
