"""Variance engine: budget-vs-actual math, materiality flags, trend flags.

Sign convention: this dataset is expense-only, so actual UNDER budget is
Favorable and actual OVER budget is Unfavorable. (For revenue lines the
convention inverts; that extension is out of scope and noted as a
limitation in docs/methodology.md.)
"""

import numpy as np
import pandas as pd

# Dual materiality threshold: a variance is flagged only when BOTH tests
# fail. The % test alone would flag a $600 overrun on a $5,000 budget
# (noise); the $ test alone would flag a 0.4% wobble on a $2M line (also
# noise). Requiring both keeps reviewer attention on items that are large
# relative to plan AND large in absolute dollars.
PCT_THRESHOLD = 0.10
USD_THRESHOLD = 5_000

# Severity tiers on |variance %|, applied only to flagged rows.
SEVERITY_TIERS = [(0.25, "Escalate"), (0.15, "Review"), (0.10, "Watch")]

# Trend filter: a month counts toward a consecutive-unfavorable run only if
# the cost center's total variance exceeds 2% of budget. Without a floor,
# ~half of all months are trivially "unfavorable" on random noise alone and
# the trend flag loses meaning.
TREND_MIN_PCT = 0.02
TREND_MIN_RUN = 3


def _apply_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add variance $, variance %, direction, and severity to any grain."""
    df = df.copy()
    df["variance_usd"] = df["actual"] - df["budget"]
    # Guard divide-by-zero: a zero-budget line has no meaningful variance %.
    df["variance_pct"] = np.where(
        df["budget"] != 0, df["variance_usd"] / df["budget"], np.nan)
    # Expense convention: spending less than budget is Favorable.
    df["direction"] = np.select(
        [df["variance_usd"] > 0, df["variance_usd"] < 0],
        ["Unfavorable", "Favorable"], default="On Budget")

    flagged = ((df["variance_pct"].abs() >= PCT_THRESHOLD)
               & (df["variance_usd"].abs() >= USD_THRESHOLD))
    df["severity"] = ""
    for floor, label in SEVERITY_TIERS:
        hit = flagged & (df["variance_pct"].abs() >= floor) \
              & (df["severity"] == "")
        df.loc[hit, "severity"] = label
    return df


def monthly_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Full monthly detail at cost center x account group grain."""
    return _apply_flags(df).sort_values(
        ["month", "cost_center", "account_group"], ignore_index=True)


def ytd_by_cost_center(df: pd.DataFrame) -> pd.DataFrame:
    """YTD rollup by cost center, re-flagged at the aggregated grain."""
    ytd = df.groupby("cost_center", as_index=False)[["budget",
                                                     "actual"]].sum()
    return _apply_flags(ytd).sort_values(
        "variance_usd", ascending=False, ignore_index=True)


def ytd_by_account_group(df: pd.DataFrame) -> pd.DataFrame:
    """YTD rollup by cost center x GL account group (for driver analysis)."""
    ytd = df.groupby(["cost_center", "account_group"],
                     as_index=False)[["budget", "actual"]].sum()
    return _apply_flags(ytd).sort_values(
        "variance_usd", key=abs, ascending=False, ignore_index=True)


def trend_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Cost centers with 3+ consecutive materially unfavorable months.

    A persistent overrun is a different management conversation than a
    one-month spike: it usually means the budget assumption is broken.
    """
    totals = _apply_flags(
        df.groupby(["cost_center", "month"], as_index=False)
        [["budget", "actual"]].sum())
    hits = []
    for cc, grp in totals.groupby("cost_center"):
        grp = grp.sort_values("month")
        unfav = (grp["variance_pct"] >= TREND_MIN_PCT).tolist()
        months = grp["month"].tolist()
        run_start, run_len = None, 0
        best = (0, None)  # (longest run, starting month)
        for m, is_unfav in zip(months, unfav):
            if is_unfav:
                run_start = run_start if run_len else m
                run_len += 1
            else:
                run_start, run_len = None, 0
            if run_len > best[0]:
                best = (run_len, run_start)
        if best[0] >= TREND_MIN_RUN:
            hits.append((cc, best[1], best[0]))
    return pd.DataFrame(
        hits, columns=["cost_center", "run_start_month", "run_length"])
