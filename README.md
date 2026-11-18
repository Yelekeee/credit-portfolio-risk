# Credit Portfolio Risk Analytics Dashboard

A production-quality mini BI project for credit portfolio risk monitoring.
Covers two reporting dates: **September 1, 2026** and **October 1, 2026**.

---

## 1. Project Overview

This system ingests synthetic loan portfolio data, calculates standard credit risk metrics (PAR30, PAR90, NPL, provisions, borrower concentration), stores results in a PostgreSQL data warehouse, and presents them in a static HTML dashboard powered by Vega-Lite.

---

## 2. Business Objectives

- Monitor the credit health of a ~500 billion KZT loan portfolio.
- Track month-over-month changes in key risk indicators.
- Identify sector and program concentrations.
- Highlight the ten largest borrower groups by outstanding balance.
- Provide a risk committee with a reproducible, auditable reporting pipeline.

---

## 3. Architecture

```
CSV Source Files
      │
      ▼
raw.portfolio + raw.fx_rates         (PostgreSQL: raw schema)
      │
      ▼
reporting.v_portfolio_clean          (deduplication + KZT conversion)
      ├── reporting.v_portfolio_active (risk classification + provisions)
      │       ├── reporting.v_portfolio_by_industry
      │       ├── reporting.v_portfolio_by_program
      │       └── reporting.v_top_borrower_groups
      └── reporting.v_portfolio_metrics + reporting.v_monthly_changes
                   │
                   ▼
            Vega-Lite Dashboard (index.html)
```

---

## 4. Technology Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Database        | PostgreSQL 16                     |
| Data ingestion  | Python 3 / psycopg2               |
| SQL             | ANSI SQL with PostgreSQL features |
| Validation      | Python 3 (Decimal arithmetic)     |
| Semantic model  | YAML                              |
| Dashboard       | Vega-Lite v5 / vega-embed         |
| Frontend        | Static HTML + CSS (no framework)  |

---

## 5. Repository Structure

```
credit-portfolio-risk/
│
├── data/
│   ├── portfolio.csv         Raw loan snapshots (4,060 rows, 2 dates)
│   └── fx.csv                Daily USD/KZT rates (42 rows)
│
├── sql/
│   ├── 01_create_schemas.sql     Create raw + reporting schemas
│   ├── 02_create_raw_tables.sql  Create raw.portfolio, raw.fx_rates
│   ├── 03_create_reporting_views.sql  Clean & classification views
│   └── 04_create_metrics_views.sql   KPI and monthly-change views
│
├── semantic/
│   └── portfolio_risk.yml    YAML semantic model
│
├── dashboard/
│   ├── index.html            Static dashboard (open in browser)
│   ├── data.json             Pre-computed dashboard data
│   ├── portfolio_kpis.json   KPI reference values
│   ├── portfolio_dynamics.json
│   ├── industry_analysis.json
│   ├── program_analysis.json
│   └── borrower_concentration.json
│
├── tests/
│   ├── validate_data.py      CSV-based independent validation
│   └── test_metrics.py       Unit tests for calculation logic
│
├── scripts/
│   └── load_data.py          CSV → PostgreSQL ingestion
│
├── README.md
├── CLAUDE.md
└── .gitignore
```

---

## 6. Database Setup

### Prerequisites

- PostgreSQL 16 running locally
- Python 3.9+ with `psycopg2` (`pip install psycopg2-binary`)

### Create the database

On macOS with Homebrew PostgreSQL the superuser is your macOS login name, not `postgres`.

```bash
psql -d postgres -c "CREATE DATABASE credit_portfolio;"
```

### Run SQL scripts in order

```bash
psql -d credit_portfolio -f sql/01_create_schemas.sql
psql -d credit_portfolio -f sql/02_create_raw_tables.sql
```

---

## 7. Data Ingestion

```bash
# Replace <your_mac_username> with the output of `whoami`
python3 scripts/load_data.py --dsn "postgresql://<your_mac_username>@localhost:5432/credit_portfolio"

# Example (Homebrew default — no password required):
python3 scripts/load_data.py --dsn "postgresql://nurdaulettauekel@localhost:5432/credit_portfolio"
```

Install `psycopg2` if not present:
```bash
pip3 install psycopg2-binary --break-system-packages
```

Expected output:
```
Loading data/fx.csv ...
  Inserted 42 FX rate rows.
Loading data/portfolio.csv ...
  Inserted 4060 portfolio rows (includes source duplicates).
Data load complete.
  raw.fx_rates:  42 rows
  raw.portfolio: 4060 rows
```

---

## 8. SQL Execution (Reporting Views)

After ingestion, create the reporting layer:

```bash
psql -d credit_portfolio -f sql/03_create_reporting_views.sql
psql -d credit_portfolio -f sql/04_create_metrics_views.sql
```

Verify results:
```sql
psql -d credit_portfolio -c "SELECT * FROM reporting.v_portfolio_metrics;"
psql -d credit_portfolio -c "SELECT * FROM reporting.v_monthly_changes;"
```

---

## 9. Dashboard

Open in any modern browser — no server required:

```bash
open dashboard/index.html
# or on Linux:
xdg-open dashboard/index.html
```

The dashboard loads Vega-Lite from CDN. An internet connection is required for the CDN scripts.

---

## 10. Final Metrics

### September 1, 2026

| Metric                    | Value           |
|---------------------------|-----------------|
| Total Portfolio (KZT)     | 498.15 Billion  |
| PAR30                     | 12.05%          |
| PAR90                     | 6.24%           |
| NPL                       | 11.85%          |
| Provisions (KZT)          | 32.74 Billion   |
| Top-10 Concentration      | 17.04%          |
| Active Loans              | 1,975           |
| Written-off (excluded)    | 25              |

### October 1, 2026

| Metric                    | Value           |
|---------------------------|-----------------|
| Total Portfolio (KZT)     | 484.67 Billion  |
| PAR30                     | 10.33%          |
| PAR90                     | 4.46%           |
| NPL                       | 10.01%          |
| Provisions (KZT)          | 27.27 Billion   |
| Top-10 Concentration      | 17.02%          |
| Active Loans              | 1,992           |
| Written-off (excluded)    | 8               |

---

## 11. Monthly Changes (Sep 1 → Oct 1)

| Metric                    | Change                        |
|---------------------------|-------------------------------|
| Portfolio balance         | −13.48 Billion KZT (−2.71%)   |
| PAR30                     | −1.72 percentage points       |
| PAR90                     | −1.78 percentage points       |
| NPL                       | −1.84 percentage points       |
| Provisions                | −5.46 Billion KZT (−16.69%)   |
| Top-10 Concentration      | −0.03 percentage points       |

---

## 12. Risk Committee Conclusions

### Conclusion 1: Broad improvement in portfolio quality, but NPL remains elevated

All risk indicators improved between September 1 and October 1. PAR30 fell by 1.72 pp, PAR90 by 1.78 pp, and NPL by 1.84 pp. However, the NPL ratio of 10.01% at October 1 remains well above a typical benchmark of 5–7% for development finance institutions. The 93 restructured loans in both periods represent approximately half of the NPL portfolio by count, indicating that workout activity is ongoing rather than resolved.

### Conclusion 2: Portfolio contraction of 2.71% requires monitoring

The portfolio shrank by approximately 13.5 billion KZT in one month. This is partly explained by a reduction in written-off loan count (25 at Sep 1 vs. 8 at Oct 1 in the active portfolio), suggesting some recovery or balance reclassification. The provision charge fell sharply (−16.69%) in line with the NPL improvement. If the portfolio contraction is due to loan repayments rather than write-offs, this is a positive signal. However, sustained contraction without new disbursements would reduce income.

### Conclusion 3: Industry concentration in Manufacturing is the largest single-sector risk

Промышленность (Manufacturing / Industry) accounts for 21.4–21.6% of the portfolio at both dates, making it the dominant sector. Construction (Строительство) and Transport (Транспорт) each contribute approximately 17%. Combined, the top three sectors represent over 55% of the total portfolio. If a systemic stress event were to affect any one of these sectors simultaneously, the portfolio impact would be material. The Top-10 borrower group concentration is relatively stable at 17.02–17.04%, indicating that individual large-name risk has not changed materially.

---

## 13. Data Validation Methodology

Independent Python validation (`tests/validate_data.py`) runs entirely from CSV files without touching the database. It:

1. Recomputes all financial metrics using Python `Decimal` arithmetic.
2. Checks computed values against hard-coded reference values (tolerance: ≤ 0.01 KZT).
3. Verifies FX rates for both reporting dates.
4. Confirms written-off loan counts match expected exclusions.
5. Verifies no double-counting in NPL (set union logic).
6. Confirms PAR90 ⊆ PAR30 (PAR90 balance ≤ PAR30 balance).
7. Confirms all restructured loans are classified as NPL.
8. Verifies a sample USD→KZT conversion for a known loan.

Unit tests (`tests/test_metrics.py`) test classification logic at boundary values (DPD=30 vs DPD=31, DPD=90 vs DPD=91, restructured with DPD=0, written-off exclusion).

Run both:
```bash
python3 tests/test_metrics.py
python3 tests/validate_data.py
```

---

## 14. Assumptions and Limitations

| # | Assumption / Limitation |
|---|-------------------------|
| 1 | Only USD and KZT currencies exist in the data. The FX file contains only USD rates; KZT is treated as 1.0 by definition. |
| 2 | 60 exact-duplicate rows exist in portfolio.csv (30 loans, each appearing twice on its respective date). These are removed via DISTINCT ON in the clean view. The duplication appears to be a source-system error. |
| 3 | The provision rate for DPD=0 current loans is 0%. The assignment specifies 1% for "up to 30 days," which is interpreted as DPD 1–30 inclusive. |
| 4 | In this dataset, no loan is simultaneously restructured AND DPD > 90. The NPL classification (OR logic) correctly handles this hypothetical case without double-counting. |
| 5 | The FX rate on the reporting date (not an average or forward rate) is used for conversion, as specified. |
| 6 | Written-off loans are excluded from all portfolio totals, PAR calculations, NPL, provisions, and concentration metrics. They are retained in the raw layer for auditability. |
| 7 | The dashboard requires an internet connection to load the Vega-Lite CDN scripts. For offline use, download and serve the vega, vega-lite, and vega-embed libraries locally. |
