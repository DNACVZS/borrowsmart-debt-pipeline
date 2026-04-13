# BorrowSmart Debt Burden Pipeline

**DSIO 2010 -- Group 1 Final Project (Option A: Working Prototype)**

Baisden, Cavazos, Ribero, Sparks

---
## My Contributions

- **Project conception & topic selection** – Proposed the BorrowSmart analysis based on prior experience with federal student loan datasets
- **Data sourcing** – Researched and identified 2 of the 3 primary datasets (FSA Direct Loan Portfolio and Census Bureau ACS)
- **Core pipeline development** – Built the foundational notebook (v1) establishing the overall data integration framework and state-level aggregation logic
- **Real-world application design** – Developed an interactive website prototype demonstrating how financial advisors and project managers would use the debt burden data in practice, including an insights page displaying top 10 highest-burden states with key metrics and risk labels in an accessible format

---

## Project Description

This project builds a prototype data pipeline for **BorrowSmart**, a fictional national nonprofit that helps borrowers manage federal student loan debt. The pipeline integrates three publicly available government datasets to generate a **state-level debt burden indicator** -- a ratio comparing average student loan debt per borrower to median household income by state.

The resulting dataset helps BorrowSmart advisors identify regions where borrowers may face greater repayment strain, enabling more targeted outreach and better-informed advisory consultations.

## Data Sources

| Dataset | Source | Format | Frequency |
|---------|--------|--------|-----------|
| Direct Loan Portfolio by Borrower Location | U.S. Dept. of Education, Office of Federal Student Aid | XLS | Quarterly |
| Median Household Income (Table B19013) | U.S. Census Bureau, American Community Survey 5-Year Estimates (2020-2024) | CSV | Annual |
| Consumer Credit Trends -- Student Loans | Consumer Financial Protection Bureau (CFPB) | CSV | Monthly |

All three datasets report at the state level and are joined using **state FIPS codes** as the common key, which avoids issues from inconsistent state name formatting across sources.

## How to Run

### Prerequisites

- A Google account (for Google Colab)
- No local installation required -- all dependencies are available in Colab by default (the notebook installs `xlrd` for XLS support)

### Steps

1. Open `BorrowSmart_Data_Pipeline_Prototype_v3.ipynb` in [Google Colab](https://colab.research.google.com/)
2. Select **Runtime → Run All**
3. When prompted, upload the three data files from the `data/` folder:
   - `portfolio-by-location.xls`
   - `ACSDT5Y2024.B19013-Data.csv`
   - `map_data_STU.csv`
4. The pipeline will execute automatically and produce all outputs

### What the Pipeline Does

1. **Loads** each dataset and parses headers, non-data rows, and units
2. **Standardizes** state identifiers to numeric FIPS codes and converts financial units (billions to dollars, thousands to counts)
3. **Joins** all three datasets on `state_fips` (inner join)
4. **Computes** `average_debt_per_borrower` and `debt_to_income_ratio` (the primary burden indicator)
5. **Classifies** states into risk tiers: Low (< 0.45), Medium (0.45-0.60), High (> 0.60)
6. **Validates** row counts, join completeness (50 states), and zero missing values in critical fields
7. **Stores** the merged dataset in a SQLite database with a typed schema
8. **Exports** two CSV files and a bar chart visualization

### Required Python Packages

All packages are pre-installed in Google Colab:

- `pandas`
- `numpy`
- `matplotlib`
- `xlrd` (installed automatically by the notebook)
- `sqlite3` (Python standard library -- no install needed)

## Pipeline Architecture

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  FSA (XLS)      │   │  ACS (CSV)      │   │  CFPB (CSV)     │
│  Loan Portfolio │   │  Median Income  │   │  YoY Origination│
│  by Location    │   │  by State       │   │  Change by State│
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌──────────────────────────────────────────────────────────────┐
│              Data Cleaning & Standardization                  │
│  • Parse XLS headers, skip non-data rows                     │
│  • Map state names to FIPS codes                              │
│  • Convert billions to dollars, thousands to counts            │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │   Merge on state_fips  │
             │   (inner join, 51 rows)│
             └────────────┬───────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │   Metric Computation   │
             │  • avg_debt_per_borrower│
             │  • debt_to_income_ratio│
             │  • risk labels         │
             └────────────┬───────────┘
                          │
             ┌────────────┼─────────────┐
             ▼            ▼             ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────┐
    │ SQLite DB   │ │ state        │ │ bar chart│
    │ (storage)   │ │ metrics CSV  │ │  (.png)  │
    └─────────────┘ └──────┬───────┘ └──────────┘
                           │
                    ┌──────┴───────┐
                    │ top 10       │
                    │ burden CSV   │
                    └──────────────┘
```

## Outputs

| File | Description |
|------|-------------|
| `borrowsmart_prototype_state_metrics.csv` | Full state-level dataset with debt, income, ratios, risk labels, and YoY origination changes for all 51 states/DC |
| `borrowsmart_prototype_top10_burden_states.csv` | The 10 states with the highest debt-to-income burden ratio |
| `borrowsmart_prototype.db` | SQLite database with typed `state_metrics` table for ad-hoc queries |
| Bar chart (displayed in notebook) | Horizontal bar chart of top 10 burden states |

### Key Findings (as of Sept. 30, 2025 FSA data)

The top 5 highest-burden states are Mississippi (0.66), Alabama (0.59), Louisiana (0.57), Arkansas (0.56), and South Carolina (0.56). These are predominantly Southern states with lower median household incomes relative to student loan balances.

## Validation Checks

The pipeline runs two rounds of validation:

**Post-Ingestion:** Row counts for each dataset (all 51 -- 50 states + DC)

**Post-Merge / Pre-Export:**
- Join completeness -- confirms all 50 states present after merge
- Zero missing values across all critical indicator columns (`state`, `state_fips`, `total_balance`, `borrowers`, `median_income`, `average_debt_per_borrower`, `debt_to_income_ratio`)
- FSA reporting period extraction verified
- Top 10 table confirmed to have exactly 10 rows
- Total pipeline runtime: approx. 0.19 seconds

## Limitations

- State averages can mask within-state variation across income groups, age groups, and institutions
- Median household income is a household-level measure, not borrower-only income
- FSA balances are aggregate portfolio figures and do not capture repayment plan status or delinquency risk
- CFPB YoY origination change is a market trend signal, not a borrower-level distress indicator
- The debt burden indicator is intended as contextual decision support, not an automated recommendation

## Repository Structure

```
DSIO2010-Group1-BorrowSmart/
├── README.md
├── requirements.txt
├── .gitignore
├── BorrowSmart_Data_Pipeline_Prototype_v3.ipynb   ← Primary notebook (run this one)
├── BorrowSmart_Data_Pipeline_Prototype_v2.ipynb   ← Previous version
├── BorrowSmart_Data_Pipeline_Prototype.ipynb      ← Original draft
├── data/
│   ├── portfolio-by-location.xls
│   ├── ACSDT5Y2024.B19013-Data.csv
│   └── map_data_STU.csv
└── docs/
    └── DSIO2010_Group1_Proposal.pdf
```

**Note on notebook versions:** The `_v3` notebook is the current version, adding a SQLite storage layer, concrete success metrics, and a data lineage summary. The `_v2` notebook added error handling, documented risk thresholds, exported chart, and function docstrings. The original notebook is preserved for version history.

## References

- Office of Federal Student Aid. (2025). Direct loan portfolio by borrower location [Data set]. U.S. Department of Education. https://studentaid.gov/data-center/student
- U.S. Census Bureau. (2024). American Community Survey 5-year estimates (2020-2024): Median household income (Table B19013). https://data.census.gov/table/ACSDT5Y2024.B19013
- Consumer Financial Protection Bureau. (2025). Consumer credit trends: Student loans [Data set]. https://www.consumerfinance.gov/data-research/consumer-credit-trends/student-loans/

## License

This project was developed for academic purposes as part of DSIO 2010 at Brown University.
