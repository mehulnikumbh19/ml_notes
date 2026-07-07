# FP&A Variance Analysis Pipeline

A small, professional-grade budget-vs-actual variance pipeline for a
community bank's operating expenses: synthetic data → input validation →
variance engine → formatted Excel report.

> **Honest note:** all data is synthetic and the bank is fictional. This is
> a demonstration of how I would automate a recurring monthly variance
> review — the controls, conventions, and documentation are the point, not
> the numbers.

## Run it

```
pip install pandas openpyxl
python src/run_pipeline.py --generate
```

Then open `output/variance_report_fy2026.xlsx` (Executive Summary, Variance
Detail, Trend View, and Data Quality tabs).

![Executive Summary screenshot placeholder](docs/screenshot_placeholder.png)

## Design decisions

- **Dual materiality threshold** — flag only when |variance| ≥ 10% **and**
  ≥ $5,000, so trivial dollars on small lines and immaterial wobble on big
  lines both stay off the reviewer's desk.
- **Fail-closed validation** — six ITGC-style input controls (completeness,
  accuracy, uniqueness, referential integrity) run before analysis; any
  failure halts the pipeline rather than publishing a wrong-but-confident
  report.
- **The report shows its own controls** — validation results ship inside
  the workbook (Data Quality tab) and as a timestamped log, audit-evidence
  style.
- **Separation of concerns** — data generation, validation, variance math,
  and presentation are separate modules; swapping synthetic data for a real
  GL extract touches one file.
- **Documented like a small model** — `docs/methodology.md` states purpose,
  data lineage, calculation definitions, threshold rationale, and
  limitations, mirroring SR 10-01 documentation principles at miniature
  scale.

## Layout

```
data/     input files (synthetic budget/actuals CSV)
src/      generate_data.py, validate.py, variance.py, report.py, run_pipeline.py
output/   generated workbook + validation log
docs/     methodology.md
```
