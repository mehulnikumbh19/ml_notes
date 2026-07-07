"""Input validation controls for the budget/actual dataset.

This layer applies ITGC-style input controls to financial data before any
analysis runs. Each check maps to a stated control objective (completeness,
accuracy, uniqueness, validity/referential integrity), and results are
written to a timestamped log so the final report can evidence its own
controls. The pipeline fails closed: any FAIL halts processing upstream of
the variance engine, so a report is never produced from unvalidated data.
"""

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from generate_data import ACCOUNT_GROUPS, COST_CENTERS, MONTHS

EXPECTED_COLUMNS = ["fiscal_year", "month", "cost_center",
                    "account_group", "budget", "actual"]

# Reasonableness ceiling: no single cost center / account group / month cell
# should exceed $5M at community-bank scale. Catches unit errors (e.g., a
# feed delivering cents or annual figures in a monthly field).
MAX_MONTHLY_AMOUNT = 5_000_000


class CheckResult(NamedTuple):
    name: str
    objective: str  # control objective, in audit language
    passed: bool
    detail: str


def _check_schema(df: pd.DataFrame) -> CheckResult:
    # Accuracy control: the file must arrive with the agreed layout and
    # numeric amount fields, or every downstream calculation is suspect.
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        return CheckResult("schema", "Accuracy", False,
                           f"missing columns: {missing}")
    non_numeric = [c for c in ("budget", "actual")
                   if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        return CheckResult("schema", "Accuracy", False,
                           f"non-numeric amount columns: {non_numeric}")
    return CheckResult("schema", "Accuracy", True,
                       f"all {len(EXPECTED_COLUMNS)} expected columns "
                       "present; amount fields numeric")


def _check_nulls(df: pd.DataFrame) -> CheckResult:
    # Completeness control: null amounts silently understate variances.
    nulls = int(df[EXPECTED_COLUMNS].isna().sum().sum())
    return CheckResult("no_nulls", "Completeness", nulls == 0,
                       f"{nulls} null values in required fields")


def _check_grid(df: pd.DataFrame) -> CheckResult:
    # Completeness control: every cost center / account group / month cell
    # must be present. A dropped extract page or truncated feed shows up
    # here, not as a mysteriously favorable variance.
    expected = len(COST_CENTERS) * len(ACCOUNT_GROUPS) * len(MONTHS)
    actual = len(df[["cost_center", "account_group", "month"]]
                 .drop_duplicates())
    return CheckResult("full_grid", "Completeness", actual == expected,
                       f"{actual}/{expected} cost-center/account/month "
                       "combinations present")


def _check_uniqueness(df: pd.DataFrame) -> CheckResult:
    # Uniqueness control: duplicate rows double-count expense and overstate
    # variances (the classic double-posted journal).
    dupes = int(df.duplicated(
        subset=["cost_center", "account_group", "month"]).sum())
    return CheckResult("uniqueness", "Uniqueness", dupes == 0,
                       f"{dupes} duplicate cost-center/account/month rows")


def _check_referential(df: pd.DataFrame) -> CheckResult:
    # Referential integrity / validity control: values must resolve to the
    # master cost-center and account-group lists — the equivalent of a GL
    # feed reconciling to the chart of accounts.
    bad_cc = set(df["cost_center"]) - set(COST_CENTERS)
    bad_ag = set(df["account_group"]) - set(ACCOUNT_GROUPS)
    bad_month = set(df["month"]) - set(MONTHS)
    problems = [f"unknown {k}: {sorted(v)}" for k, v in
                (("cost centers", bad_cc), ("account groups", bad_ag),
                 ("months", bad_month)) if v]
    return CheckResult("referential_integrity", "Validity", not problems,
                       "; ".join(problems) or
                       "all keys resolve to master lists")


def _check_reasonableness(df: pd.DataFrame) -> CheckResult:
    # Reasonableness control: negative expense budgets and out-of-scale
    # amounts indicate extract or unit errors, not real activity.
    neg = int((df["budget"] <= 0).sum())
    oversize = int((df[["budget", "actual"]].abs()
                    > MAX_MONTHLY_AMOUNT).sum().sum())
    ok = neg == 0 and oversize == 0
    return CheckResult("reasonableness", "Accuracy", ok,
                       f"{neg} non-positive budgets; {oversize} amounts "
                       f"beyond ${MAX_MONTHLY_AMOUNT:,} ceiling")


def run_validation(df: pd.DataFrame, log_path: Path
                   ) -> tuple[bool, list[CheckResult]]:
    """Run all input controls, write the evidence log, return results."""
    results = [check(df) for check in (
        _check_schema, _check_nulls, _check_grid,
        _check_uniqueness, _check_referential, _check_reasonableness)]
    all_passed = all(r.passed for r in results)

    ts = datetime.now().isoformat(timespec="seconds")
    lines = [f"=== Input Validation Log — run {ts} ===",
             f"Source rows: {len(df)}", ""]
    lines += [f"[{'PASS' if r.passed else 'FAIL'}] {r.name} "
              f"({r.objective}) — {r.detail}" for r in results]
    lines += ["", f"Overall: {'PASS' if all_passed else 'FAIL'} "
              f"({sum(r.passed for r in results)}/{len(results)} "
              "checks passed)"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_passed, results
