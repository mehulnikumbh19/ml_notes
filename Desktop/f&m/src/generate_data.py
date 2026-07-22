"""Synthetic budget vs. actual data generator (FY2026).

Produces a monthly budget/actual dataset for a fictional community bank at
cost center x GL account group grain. Actuals equal budget plus modest noise,
with a small number of deliberately planted variances so the downstream
report has realistic findings. All figures are synthetic; in production this
module would be replaced by a GL extract and a budget-system export.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026  # fixed seed: demo output must be reproducible run-to-run

FISCAL_YEAR = 2026
MONTHS = range(1, 13)

# Approximate annual operating budget per cost center, sized to a community
# bank's non-interest expense base (roughly $25M total across 15 centers).
COST_CENTERS = {
    "Retail Banking Operations": 3_600_000,
    "Commercial Lending": 2_900_000,
    "IT & Information Security": 2_400_000,
    "Compliance & BSA": 1_500_000,
    "Treasury": 900_000,
    "Facilities": 1_100_000,
    "Human Resources": 800_000,
    "Marketing": 700_000,
    "Finance & Accounting": 1_200_000,
    "Branch Network": 4_200_000,
    "Loan Servicing": 1_600_000,
    "Wealth Management": 1_000_000,
    "Internal Audit": 600_000,
    "Deposit Operations": 1_300_000,
    "Executive Administration": 950_000,
}

# Budget mix by GL account group. Salaries dominate, as they do in any
# bank's operating expense base.
ACCOUNT_GROUPS = {
    "Salaries & Benefits": 0.58,
    "Occupancy": 0.12,
    "Technology/Software": 0.13,
    "Professional Services": 0.07,
    "Other Operating Expense": 0.10,
}

# Planted variances: (cost center, account group, months, multiplier, reason).
# Mix of sustained vs. single-month and favorable vs. unfavorable, sized so
# each clears the dual materiality threshold (>=10% AND >=$5,000) at monthly
# or YTD grain, and the report exercises every severity tier plus the
# consecutive-month trend flag.
PLANTED_VARIANCES = [
    ("Marketing", "Professional Services", range(2, 12), 1.45,
     "sustained agency/vendor overrun"),
    ("IT & Information Security", "Technology/Software", range(5, 13), 1.30,
     "unbudgeted software licensing"),
    ("Commercial Lending", "Salaries & Benefits", [3], 1.18,
     "one-time incentive payout"),
    ("Facilities", "Occupancy", [7], 1.80,
     "emergency building repair"),
    ("Branch Network", "Other Operating Expense", range(1, 13), 0.82,
     "sustained under-spend (favorable)"),
    ("Human Resources", "Salaries & Benefits", [8, 9, 10], 0.85,
     "open positions / vacancy savings (favorable)"),
    ("Wealth Management", "Technology/Software", [10, 11, 12], 1.60,
     "platform migration overrun"),
]


def generate(out_path: Path) -> pd.DataFrame:
    """Build the FY2026 budget/actual dataset and write it to CSV."""
    rng = np.random.default_rng(SEED)
    planted = {
        (cc, ag, m): mult
        for cc, ag, months, mult, _ in PLANTED_VARIANCES
        for m in months
    }

    rows = []
    for cc, annual in COST_CENTERS.items():
        for ag, share in ACCOUNT_GROUPS.items():
            # Budgets spread evenly across months, rounded to the nearest
            # $100 so figures look like planning-system output, not noise.
            budget = round(annual * share / 12 / 100) * 100
            for month in MONTHS:
                # Baseline actuals: budget +/- ~3% operational noise.
                actual = budget * (1 + rng.normal(0, 0.03))
                actual *= planted.get((cc, ag, month), 1.0)
                rows.append(
                    (FISCAL_YEAR, month, cc, ag, budget, round(actual))
                )

    df = pd.DataFrame(
        rows,
        columns=["fiscal_year", "month", "cost_center",
                 "account_group", "budget", "actual"],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    generate(root / "data" / "budget_actuals_fy2026.csv")
