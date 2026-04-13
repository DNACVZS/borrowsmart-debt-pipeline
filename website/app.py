from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from flask import Flask, abort, render_template, request

app = Flask(__name__)

FSA_PATH = Path("data/raw/portfolio-by-location.xls")
ACS_PATH = Path("data/raw/ACSDT5Y2024.B19013-Data.csv")
CFPB_PATH = Path("data/raw/map_data_STU.csv")
PROCESSED_PATH = Path("data/processed/state_dashboard.csv")
LOGO_CANDIDATES = ["logo.png", "logo.svg", "logo.jpg", "logo.jpeg", "logo.webp"]

# 50 states + DC for this application (territories excluded)
STATE_FIPS_50_PLUS_DC = {
    1,
    2,
    4,
    5,
    6,
    8,
    9,
    10,
    11,
    12,
    13,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39,
    40,
    41,
    42,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    53,
    54,
    55,
    56,
}

RISK_THRESHOLDS = {
    "low_max": 0.45,
    "medium_max": 0.60,
}


def _as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _fail(msg: str) -> None:
    raise RuntimeError(msg)


def _is_empty_cell(value: object) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text.lower() == "nan"


def _non_empty_tokens(values: list[object]) -> list[str]:
    return [str(v).strip() for v in values if not _is_empty_cell(v)]


def _find_fsa_sheet_and_header(xls: pd.ExcelFile) -> tuple[str, pd.DataFrame, int]:
    for sheet_name in xls.sheet_names:
        raw = pd.read_excel(FSA_PATH, sheet_name=sheet_name, header=None)
        for i in range(min(150, len(raw))):
            row_text = " ".join(_non_empty_tokens(raw.iloc[i].tolist())).lower()
            if "location" in row_text and "balance" in row_text and "borrower" in row_text:
                return sheet_name, raw, i
    _fail("FSA header row not found on any sheet; expected Location/Balance/Borrowers labels")


def _extract_fsa_period(raw: pd.DataFrame) -> str:
    for i in range(min(50, len(raw))):
        row_tokens = _non_empty_tokens(raw.iloc[i].tolist())
        line = " ".join(row_tokens)
        m = re.search(r"Data as of\s+(.+)$", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    print("[WARN] FSA period text containing 'Data as of' was not found. Falling back to 'Unknown'.")
    return "Unknown"


def _find_header_col_index(header_cells: list[object], required_bits: list[str]) -> int | None:
    for idx, cell in enumerate(header_cells):
        text = str(cell).strip().lower()
        if all(bit in text for bit in required_bits):
            return idx
    return None


def load_fsa() -> tuple[pd.DataFrame, str, str]:
    if not FSA_PATH.exists():
        _fail(f"Missing FSA file: {FSA_PATH}")

    xls = pd.ExcelFile(FSA_PATH)
    print("[FSA] sheet names:", xls.sheet_names)

    chosen_sheet, raw, header_row = _find_fsa_sheet_and_header(xls)
    print("[FSA] chosen sheet:", chosen_sheet)
    print("[FSA] header row index:", header_row)

    period_text = _extract_fsa_period(raw)
    print(f"[FSA] detected reporting period: {period_text}")

    header_cells = raw.iloc[header_row].tolist()
    loc_idx = _find_header_col_index(header_cells, ["location"])
    bal_idx = _find_header_col_index(header_cells, ["balance", "billion"])
    bor_idx = _find_header_col_index(header_cells, ["borrower", "thousand"])

    if loc_idx is None or bal_idx is None or bor_idx is None:
        _fail(
            "[FSA] could not identify required columns from header row. "
            "Need Location, Balance (in billions), Borrowers (in thousands)."
        )

    rows = []
    for i in range(header_row + 1, len(raw)):
        row = raw.iloc[i].tolist()
        state_val = row[loc_idx] if loc_idx < len(row) else None
        balance_val = row[bal_idx] if bal_idx < len(row) else None
        borrowers_val = row[bor_idx] if bor_idx < len(row) else None

        if _is_empty_cell(state_val) and _is_empty_cell(balance_val) and _is_empty_cell(borrowers_val):
            break

        rows.append(
            {
                "state_name": state_val,
                "balance_billions": balance_val,
                "borrowers_thousands": borrowers_val,
            }
        )

    out = pd.DataFrame(rows)
    print(f"[FSA] raw table rows read: {len(out)}")

    before = len(out)
    out = out.dropna(subset=["state_name", "balance_billions", "borrowers_thousands"])
    after_na = len(out)
    print(f"[FSA] dropped {before - after_na} rows due to missing state/balance/borrowers")

    out["balance_billions"] = _as_numeric(out["balance_billions"])
    out["borrowers_thousands"] = _as_numeric(out["borrowers_thousands"])

    before_num = len(out)
    out = out.dropna(subset=["balance_billions", "borrowers_thousands"])
    print(f"[FSA] dropped {before_num - len(out)} rows due to non-numeric balance/borrowers")

    out["total_outstanding_balance_usd"] = (out["balance_billions"] * 1_000_000_000).round(0)
    out["borrower_count"] = (out["borrowers_thousands"] * 1_000).round(0)

    state_to_fips = {
        "Alabama": 1,
        "Alaska": 2,
        "Arizona": 4,
        "Arkansas": 5,
        "California": 6,
        "Colorado": 8,
        "Connecticut": 9,
        "Delaware": 10,
        "Florida": 12,
        "Georgia": 13,
        "Hawaii": 15,
        "Idaho": 16,
        "Illinois": 17,
        "Indiana": 18,
        "Iowa": 19,
        "Kansas": 20,
        "Kentucky": 21,
        "Louisiana": 22,
        "Maine": 23,
        "Maryland": 24,
        "Massachusetts": 25,
        "Michigan": 26,
        "Minnesota": 27,
        "Mississippi": 28,
        "Missouri": 29,
        "Montana": 30,
        "Nebraska": 31,
        "Nevada": 32,
        "New Hampshire": 33,
        "New Jersey": 34,
        "New Mexico": 35,
        "New York": 36,
        "North Carolina": 37,
        "North Dakota": 38,
        "Ohio": 39,
        "Oklahoma": 40,
        "Oregon": 41,
        "Pennsylvania": 42,
        "Rhode Island": 44,
        "South Carolina": 45,
        "South Dakota": 46,
        "Tennessee": 47,
        "Texas": 48,
        "Utah": 49,
        "Vermont": 50,
        "Virginia": 51,
        "Washington": 53,
        "West Virginia": 54,
        "Wisconsin": 55,
        "Wyoming": 56,
        "District of Columbia": 11,
    }

    out["state_fips"] = out["state_name"].map(state_to_fips)
    unmapped = out[out["state_fips"].isna()]["state_name"].tolist()
    if unmapped:
        print("[FSA] unmapped state/location labels:", sorted(set(unmapped)))

    before_fips = len(out)
    out = out.dropna(subset=["state_fips"])
    print(f"[FSA] dropped {before_fips - len(out)} rows due to unmapped state names")

    print(f"[FSA] row count of states loaded: {len(out)}")
    alaska_raw = out[out["state_name"] == "Alaska"]
    if not alaska_raw.empty:
        alaska_row = alaska_raw.iloc[0]
        print(
            "[FSA] Alaska example row:",
            {
                "state": alaska_row["state_name"],
                "total_outstanding_balance_usd": int(alaska_row["total_outstanding_balance_usd"]),
                "borrower_count": int(alaska_row["borrower_count"]),
            },
        )

    out["state_fips"] = out["state_fips"].astype(int)
    out = out[["state_fips", "state_name", "total_outstanding_balance_usd", "borrower_count"]]
    out = out.drop_duplicates(subset=["state_fips"], keep="first")

    return out, chosen_sheet, period_text


def load_acs() -> tuple[pd.DataFrame, str]:
    if not ACS_PATH.exists():
        _fail(f"Missing ACS file: {ACS_PATH}")

    acs = pd.read_csv(ACS_PATH)
    print("[ACS] detected columns:", list(acs.columns))

    required = ["GEO_ID", "NAME", "B19013_001E"]
    missing = [c for c in required if c not in acs.columns]
    if missing:
        _fail(f"ACS required columns missing: {missing}")

    period_text = "2019–2024 (5-Year Estimate)"

    before = len(acs)
    acs = acs[acs["GEO_ID"] != "Geography"].copy()
    print(f"[ACS] dropped {before - len(acs)} header-like rows where GEO_ID == 'Geography'")

    acs["state_fips"] = acs["GEO_ID"].astype(str).str.extract(r"(\d{2})$")
    before_fips = len(acs)
    acs = acs.dropna(subset=["state_fips"])
    print(f"[ACS] dropped {before_fips - len(acs)} rows due to missing 2-digit GEO_ID suffix")

    acs["state_fips"] = _as_numeric(acs["state_fips"]).astype("Int64")
    before_num = len(acs)
    acs = acs.dropna(subset=["state_fips"])
    print(f"[ACS] dropped {before_num - len(acs)} rows due to non-numeric state_fips")

    acs["state_fips"] = acs["state_fips"].astype(int)
    acs["median_household_income"] = _as_numeric(acs["B19013_001E"])
    before_income = len(acs)
    acs = acs.dropna(subset=["median_household_income"])
    print(f"[ACS] dropped {before_income - len(acs)} rows due to non-numeric B19013_001E")

    acs = acs[["state_fips", "NAME", "median_household_income"]].copy()
    acs = acs.rename(columns={"NAME": "state_name"})
    acs = acs.drop_duplicates(subset=["state_fips"], keep="first")

    return acs, period_text


def load_cfpb() -> pd.DataFrame:
    if not CFPB_PATH.exists():
        _fail(f"Missing CFPB file: {CFPB_PATH}")

    cfpb = pd.read_csv(CFPB_PATH)
    print("[CFPB] detected columns:", list(cfpb.columns))

    required = ["fips_code", "state_abbr", "value"]
    missing = [c for c in required if c not in cfpb.columns]
    if missing:
        _fail(f"CFPB required columns missing: {missing}")

    before = len(cfpb)
    cfpb["state_fips"] = _as_numeric(cfpb["fips_code"]).astype("Int64")
    cfpb["origination_yoy_change"] = _as_numeric(cfpb["value"])
    cfpb = cfpb.dropna(subset=["state_fips", "origination_yoy_change"])
    print(f"[CFPB] dropped {before - len(cfpb)} rows due to non-numeric fips_code/value")

    cfpb["state_fips"] = cfpb["state_fips"].astype(int)
    cfpb = cfpb[["state_fips", "state_abbr", "origination_yoy_change"]]
    cfpb = cfpb.drop_duplicates(subset=["state_fips"], keep="first")

    return cfpb


def classify_risk(dti: float) -> str:
    if dti < RISK_THRESHOLDS["low_max"]:
        return "Low"
    if dti < RISK_THRESHOLDS["medium_max"]:
        return "Medium"
    return "High"


def recommend_action(risk_label: str, yoy_change: float | None) -> str:
    if risk_label == "High":
        return "Immediate 1:1 counseling"
    if risk_label == "Medium" and yoy_change is not None and yoy_change > 0:
        return "Targeted outreach campaign"
    if risk_label == "Medium":
        return "Monthly check-in"
    return "Self-serve guidance + monitor"


def explain_priority(row: dict) -> str:
    yoy = row.get("origination_yoy_change")
    dti_pct = float(row["debt_to_income_ratio"]) * 100

    if row["risk_label"] == "High":
        return f"Debt burden is high at {dti_pct:.1f}% of median household income, so this state should be prioritized for advisor outreach."
    if pd.notna(yoy) and float(yoy) > 0:
        return (
            f"Debt burden is {dti_pct:.1f}% and origination volume is rising "
            f"({float(yoy):+.2f}% YoY), suggesting growing borrower need."
        )
    return f"Debt burden is {dti_pct:.1f}% of median household income, so this state should remain on the monitoring list."


def build_dataset() -> tuple[pd.DataFrame, dict]:
    fsa, fsa_sheet, fsa_period = load_fsa()
    acs, acs_period = load_acs()
    cfpb = load_cfpb()
    dropped_reasons: list[str] = []

    # Keep only 50 states + DC for this project output; report exclusions.
    for name, df in [("FSA", fsa), ("ACS", acs), ("CFPB", cfpb)]:
        before = len(df)
        kept = df[df["state_fips"].isin(STATE_FIPS_50_PLUS_DC)].copy()
        dropped = before - len(kept)
        if dropped:
            excluded = sorted(set(df.loc[~df["state_fips"].isin(STATE_FIPS_50_PLUS_DC), "state_fips"].tolist()))
            print(f"[{name}] excluded {dropped} non-project rows (e.g., territories): {excluded}")
            dropped_reasons.append(f"{name}: non-project FIPS excluded -> {excluded}")
        if name == "FSA":
            fsa = kept
        elif name == "ACS":
            acs = kept
        else:
            cfpb = kept

    expected_fips = set(STATE_FIPS_50_PLUS_DC)
    fsa_fips = set(fsa["state_fips"].tolist())
    acs_fips = set(acs["state_fips"].tolist())
    cfpb_fips = set(cfpb["state_fips"].tolist())

    merged = fsa.merge(acs, on="state_fips", how="inner", suffixes=("_fsa", "_acs"))
    print(f"[JOIN] count of states after join with ACS: {len(merged)}")
    merged_fips = set(merged["state_fips"].tolist())
    missing_after_acs = sorted(expected_fips - merged_fips)
    if missing_after_acs:
        for fips in missing_after_acs:
            if fips not in fsa_fips:
                dropped_reasons.append(f"FIPS {fips}: missing from FSA input after cleaning")
            elif fips not in acs_fips:
                dropped_reasons.append(f"FIPS {fips}: missing from ACS input")
            else:
                dropped_reasons.append(f"FIPS {fips}: missing after FSA+ACS join")

    merged = merged.merge(cfpb, on="state_fips", how="left")
    print(f"[JOIN] count of states after join with CFPB: {len(merged)}")
    cfpb_missing_mask = merged["origination_yoy_change"].isna()
    cfpb_missing = merged.loc[cfpb_missing_mask, ["state_fips", "state_name_fsa"]]
    if not cfpb_missing.empty:
        missing_cfpb_list = [f"{int(r.state_fips)} ({r.state_name_fsa})" for r in cfpb_missing.itertuples(index=False)]
        dropped_reasons.append("CFPB missing YoY value for states: " + ", ".join(missing_cfpb_list))
    cfpb_absent_in_source = sorted(expected_fips - cfpb_fips)
    if cfpb_absent_in_source:
        dropped_reasons.append(f"CFPB source missing FIPS values: {cfpb_absent_in_source}")

    if len(merged) < 45:
        _fail(f"Too few states after join ({len(merged)}). Check input files and state_fips mapping.")

    merged["state_name"] = merged["state_name_fsa"].fillna(merged["state_name_acs"])
    merged["median_household_income"] = _as_numeric(merged["median_household_income"])
    merged["total_outstanding_balance_usd"] = _as_numeric(merged["total_outstanding_balance_usd"])
    merged["borrower_count"] = _as_numeric(merged["borrower_count"])

    bad_rows = merged[
        (merged["borrower_count"] <= 0)
        | (merged["median_household_income"] <= 0)
        | merged["borrower_count"].isna()
        | merged["median_household_income"].isna()
    ]
    if len(bad_rows):
        print(f"[CLEAN] dropping {len(bad_rows)} rows due to invalid borrower_count or income")
        merged = merged.drop(bad_rows.index)

    merged["average_debt_per_borrower"] = merged["total_outstanding_balance_usd"] / merged["borrower_count"]
    merged["debt_to_income_ratio"] = merged["average_debt_per_borrower"] / merged["median_household_income"]
    merged["risk_label"] = merged["debt_to_income_ratio"].apply(classify_risk)

    merged = merged[
        [
            "state_fips",
            "state_name",
            "state_abbr",
            "total_outstanding_balance_usd",
            "borrower_count",
            "average_debt_per_borrower",
            "median_household_income",
            "debt_to_income_ratio",
            "origination_yoy_change",
            "risk_label",
        ]
    ].sort_values("state_name")
    merged = merged.rename(columns={"total_outstanding_balance_usd": "total_outstanding_balance"})

    total_states = merged["state_fips"].nunique()
    expected_state_count = len(expected_fips)
    if total_states != expected_state_count:
        print(
            f"[CHECK] joined unique states = {total_states}; expected {expected_state_count}. "
            "Missing/exclusions are reported above."
        )
    else:
        print(f"[CHECK] joined unique states = {expected_state_count}")

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(PROCESSED_PATH, index=False)
    print(f"[OUTPUT] wrote processed dataset to {PROCESSED_PATH}")

    if dropped_reasons:
        print("[MISSING] states dropped or missing reasons:")
        for reason in dropped_reasons:
            print(f"  - {reason}")
    else:
        print("[MISSING] no missing states or dropped records after project geography filtering.")

    alaska = merged[merged["state_name"] == "Alaska"]
    if not alaska.empty:
        alaska_row = alaska.iloc[0]
        alaska_avg_calc = alaska_row["total_outstanding_balance"] / alaska_row["borrower_count"]
        alaska_dti_calc = alaska_avg_calc / alaska_row["median_household_income"]
        print(
            "[CHECK] Alaska sanity:",
            {
                "average_debt_expected": round(float(alaska_avg_calc), 2),
                "average_debt_actual": round(float(alaska_row["average_debt_per_borrower"]), 2),
                "dti_expected": round(float(alaska_dti_calc), 6),
                "dti_actual": round(float(alaska_row["debt_to_income_ratio"]), 6),
            },
        )

    meta = {
        "fsa_period": fsa_period,
        "acs_period": acs_period,
        "fsa_sheet": fsa_sheet,
        "fsa_columns_used": ["Location", "Balance (in billions)", "Borrowers (in thousands)"],
    }
    return merged, meta


DATA_DF, META = build_dataset()
DATA_RECORDS = DATA_DF.to_dict("records")
DATA_LOOKUP = {row["state_fips"]: row for row in DATA_RECORDS}
TOP10 = sorted(DATA_RECORDS, key=lambda r: r["debt_to_income_ratio"], reverse=True)[:10]


@app.context_processor
def shared_template_context():
    static_dir = Path(app.static_folder)
    logo_filename = next((name for name in LOGO_CANDIDATES if (static_dir / name).exists()), None)
    return {"logo_filename": logo_filename}


@app.route("/")
def index():
    return render_template("index.html", page_title="BorrowSmart", active="index")


@app.route("/dashboard")
def dashboard():
    selected_fips = request.args.get("state_fips", type=int)
    risk_filter = request.args.get("risk", default="All", type=str)
    if selected_fips is None:
        selected_fips = DATA_RECORDS[0]["state_fips"]

    selected = DATA_LOOKUP.get(selected_fips)
    if not selected:
        abort(404)

    selected_action = recommend_action(
        selected["risk_label"],
        float(selected["origination_yoy_change"]) if pd.notna(selected["origination_yoy_change"]) else None,
    )
    selected_reason = explain_priority(selected)

    queue = DATA_RECORDS
    if risk_filter in {"Low", "Medium", "High"}:
        queue = [r for r in queue if r["risk_label"] == risk_filter]

    def _priority_key(row):
        risk_rank = {"High": 0, "Medium": 1, "Low": 2}.get(row["risk_label"], 3)
        yoy = row["origination_yoy_change"]
        yoy_rank = 0 if pd.notna(yoy) else 1
        yoy_val = float(yoy) if pd.notna(yoy) else -999
        return (risk_rank, -row["debt_to_income_ratio"], yoy_rank, -yoy_val)

    queue = sorted(queue, key=_priority_key)
    for row in queue:
        yoy_val = row["origination_yoy_change"]
        row["recommended_action"] = recommend_action(
            row["risk_label"],
            float(yoy_val) if pd.notna(yoy_val) else None,
        )

    high_risk = len([r for r in DATA_RECORDS if r["risk_label"] == "High"])
    medium_risk = len([r for r in DATA_RECORDS if r["risk_label"] == "Medium"])
    low_risk = len([r for r in DATA_RECORDS if r["risk_label"] == "Low"])

    return render_template(
        "dashboard.html",
        page_title="Advisor Dashboard",
        active="dashboard",
        states=DATA_RECORDS,
        selected=selected,
        selected_action=selected_action,
        selected_reason=selected_reason,
        risk_filter=risk_filter,
        advisor_queue=queue[:15],
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
    )


@app.route("/insights")
def insights():
    return render_template(
        "insights.html",
        page_title="Insights",
        active="insights",
        top10=TOP10,
        all_states=DATA_RECORDS,
    )


@app.route("/transparency")
def transparency():
    return render_template(
        "transparency.html",
        page_title="Transparency",
        active="transparency",
        meta=META,
    )


if __name__ == "__main__":
    app.run(debug=True)
