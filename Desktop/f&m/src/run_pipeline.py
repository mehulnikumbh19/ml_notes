"""Pipeline entry point: (generate) -> validate -> analyze -> report.

Fail-closed by design: if any input control fails, the pipeline halts and
reports — it never produces an Excel report from unvalidated data. A wrong
report that looks authoritative is worse than no report.

Usage:
    python src/run_pipeline.py             # run against existing data file
    python src/run_pipeline.py --generate  # regenerate synthetic data first
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import generate_data
import report
import validate
import variance

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "budget_actuals_fy2026.csv"
VALIDATION_LOG = ROOT / "output" / "validation_log.txt"
REPORT_FILE = ROOT / "output" / "variance_report_fy2026.xlsx"


def log(stage: str, message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {stage:<10} {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true",
                        help="regenerate the synthetic dataset first")
    args = parser.parse_args()

    if args.generate:
        df = generate_data.generate(DATA_FILE)
        log("GENERATE", f"wrote {len(df)} rows -> {DATA_FILE.name}")
    elif not DATA_FILE.exists():
        log("ERROR", f"{DATA_FILE} not found; run with --generate")
        return 1

    df = pd.read_csv(DATA_FILE)
    log("LOAD", f"read {len(df)} rows from {DATA_FILE.name}")

    passed, results = validate.run_validation(df, VALIDATION_LOG)
    log("VALIDATE", f"{sum(r.passed for r in results)}/{len(results)} "
        f"input controls passed -> {VALIDATION_LOG.name}")
    if not passed:
        # Fail closed: surface the failing controls and stop before any
        # analysis. The validation log is the evidence of why.
        for r in results:
            if not r.passed:
                log("FAIL", f"{r.name} ({r.objective}): {r.detail}")
        log("HALT", "validation failed — no report produced")
        return 1

    detail = variance.monthly_detail(df)
    ytd_cc = variance.ytd_by_cost_center(df)
    ytd_ag = variance.ytd_by_account_group(df)
    trends = variance.trend_flags(df)
    n_flags = int((detail["severity"] != "").sum())
    log("ANALYZE", f"{n_flags} monthly flags; "
        f"{len(trends)} cost centers on trend watch")

    report.write_report(REPORT_FILE, detail, ytd_cc, ytd_ag, trends, results)
    log("REPORT", f"workbook written -> {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
