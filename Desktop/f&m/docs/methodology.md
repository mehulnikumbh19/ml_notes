# Variance Analysis Pipeline — Methodology

## Purpose and scope

Automates the recurring monthly budget-vs-actual variance review for a
community bank's operating expense base: calculate variances, apply a
materiality screen, tier findings by severity, and publish a formatted
Excel workbook a reviewer can act on. Scope is expense cost centers only,
one fiscal year (FY2026), at cost center × GL account group × month grain.
This document consciously mirrors SR 10-01 model documentation principles —
documented assumptions, defined methodology, stated limitations — at
miniature scale.

## Data sources and lineage

All data in this repository is **synthetic**, produced by
`src/generate_data.py` with a fixed random seed for reproducibility. In
production, the two inputs would be:

- **Actuals** — a monthly general ledger extract (core banking / ERP),
  summarized to cost center × account group.
- **Budget** — an export from the planning system (e.g., Oracle PBCS) at
  the same grain.

Lineage is one hop: source file → validation → variance engine → report.
No intermediate transformations occur outside version-controlled code, so
every number in the workbook is traceable to a row in
`data/budget_actuals_fy2026.csv`.

## Methodology

- **Variance ($)** = actual − budget. **Variance (%)** = variance ($) ÷
  budget; undefined (blank) when budget is zero.
- **Favorable/unfavorable convention** — the dataset is expense-only, so
  actual under budget is *favorable*, over budget is *unfavorable*.
  Revenue lines would invert this convention and are out of scope.
- **Materiality flag (dual threshold)** — a variance is flagged only when
  |variance %| ≥ 10% **and** |variance $| ≥ $5,000. The percentage test
  alone flags trivial dollar amounts on small budget lines; the dollar test
  alone flags immaterial percentage wobble on large lines. Requiring both
  keeps the flag list at reviewable length and focused on items that matter
  both relative to plan and in absolute terms.
- **Severity tiers** on flagged items: Watch (10–15%), Review (15–25%),
  Escalate (>25%).
- **Trend flag** — a cost center is placed on trend watch after 3+
  consecutive months with total variance unfavorable by ≥2% of budget. The
  2% floor keeps random sign-flips from qualifying; a persistent overrun
  signals a broken budget assumption rather than timing noise.
- **YTD rollups** re-derive variance % and severity at the aggregated grain
  (by cost center, and by cost center × account group) rather than
  averaging monthly percentages.

## Input controls

Run before any analysis; the pipeline **fails closed** (halts, produces no
report) if any control fails. Results are logged to
`output/validation_log.txt` and reproduced on the workbook's Data Quality
tab so the report evidences its own controls.

| Check | Control objective | Why it exists |
|---|---|---|
| Schema | Accuracy | Wrong layout or non-numeric amounts corrupt every downstream calculation |
| No nulls | Completeness | Null amounts silently understate variances |
| Full grid | Completeness | A truncated extract would otherwise appear as a favorable variance |
| Uniqueness | Uniqueness | Duplicate rows double-count expense (the double-posted journal) |
| Referential integrity | Validity | Keys must resolve to the cost-center / account-group master lists |
| Reasonableness | Accuracy | Negative budgets and out-of-scale amounts indicate unit or extract errors |

## Assumptions and limitations

- Data is synthetic; planted variances are illustrative, not modeled from
  real bank behavior.
- Expense-only sign convention; revenue and net-interest lines are out of
  scope.
- Thresholds ($5,000 / 10% / 2% trend floor) are illustrative and exposed
  as constants in `src/variance.py`; a real deployment would calibrate
  them with the FP&A owner and document the rationale.
- The same dollar threshold is applied at monthly and YTD grain for
  simplicity; a production version might scale the YTD dollar threshold.
- No allocation, accrual, or timing adjustments are modeled.
