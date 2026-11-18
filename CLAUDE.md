# CLAUDE.md — Credit Portfolio Risk Analytics

Development reference for AI-assisted and human engineers.

---

## Project Architecture

```
raw schema          → verbatim source data (portfolio, fx_rates)
reporting schema    → clean views and KPI aggregations
dashboard/          → static HTML + Vega-Lite JSON specs
tests/              → independent Python validation (no DB dependency)
scripts/            → CSV ingestion
semantic/           → YAML semantic model
```

The reporting layer is **entirely view-based** — no materialized tables. This keeps the pipeline simple and idempotent. If performance on large datasets becomes an issue, convert views to materialized views and add `REFRESH MATERIALIZED VIEW` to the ingestion script.

---

## Business Calculation Definitions

### Portfolio Total

```sql
SUM(principal_outstanding * fx_rate)
-- where fx_rate = 1.0 for KZT, rate_kzt for USD
-- exclude written_off = 1 loans
-- deduplicate on (report_date, loan_id) first
```

### PAR30, PAR90

```sql
PAR30 = SUM(outstanding_kzt WHERE days_past_due > 30) / SUM(outstanding_kzt) * 100
PAR90 = SUM(outstanding_kzt WHERE days_past_due > 90) / SUM(outstanding_kzt) * 100
-- Boundaries are STRICTLY greater than (not >=)
-- DPD=30 is NOT PAR30; DPD=31 IS PAR30
-- DPD=90 is NOT PAR90; DPD=91 IS PAR90
```

### NPL

```sql
NPL flag = (days_past_due > 90 OR restructured = 1)
-- Uses boolean OR — no double counting possible via set union
-- A restructured loan with DPD=0 IS NPL
-- A loan with DPD=50 AND restructured=1 IS NPL (provision = 50%)
```

### Provisions (mutually exclusive, priority order)

| Priority | Condition                          | Rate |
|----------|------------------------------------|------|
| 1 (high) | NPL (DPD > 90 OR restructured = 1) | 50%  |
| 2        | DPD 31–90                          | 10%  |
| 3        | DPD 1–30                           | 1%   |
| 4 (low)  | DPD = 0, not restructured          | 0%   |

NPL takes the highest priority bucket. A restructured loan with DPD=50 receives 50%, not 10%.

### Top-10 Borrower Concentration

```sql
-- Step 1: aggregate by group_id within each report_date
-- Step 2: RANK() OVER (PARTITION BY report_date ORDER BY total_kzt DESC)
-- Step 3: take rank <= 10, sum their balances
-- Step 4: divide by total portfolio
```

---

## Database Conventions

- Schema separation: `raw` (source) / `reporting` (views)
- Financial amounts: `NUMERIC(20,2)` for principal, `NUMERIC(24,2)` for converted KZT
- FX rates: `NUMERIC(10,4)` — four decimal places
- Boolean flags (`written_off`, `restructured`): `SMALLINT` (0/1) matching source CSV
- Idempotent DDL: `CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`
- Transactions: DDL changes wrapped in `BEGIN/COMMIT`
- Primary key on `raw.fx_rates (rate_date, currency)`
- No primary key on `raw.portfolio` (source contains duplicates)

---

## SQL Implementation Rules

1. **Never aggregate across currencies** without KZT conversion.
2. **Always exclude written_off = 1** from portfolio, PAR, NPL, provision, and concentration calculations.
3. **Deduplicate before aggregating** — use `DISTINCT ON (report_date, loan_id)` in `v_portfolio_clean`.
4. **Never sum pre-computed ratio columns** (par30_pct, npl_pct) across rows — recalculate from raw balances.
5. **NPL flag uses OR logic** — prevents double-counting without additional deduplication.
6. **Use NULLIF(denominator, 0)** for ratio calculations to handle edge cases safely.
7. **Percentage-point differences** for risk ratio comparisons (not relative % change).

---

## Data Validation Requirements

Every time the pipeline is modified, run:
```bash
python3 tests/test_metrics.py     # unit tests (no I/O)
python3 tests/validate_data.py    # end-to-end vs CSV reference values
```

If SQL and Python disagree:
1. Check deduplication — confirm 4,000 unique (report_date, loan_id) pairs post-dedup.
2. Check FX conversion — verify rates for both dates.
3. Check written-off exclusion.
4. Check NPL set union logic (OR, not AND).
5. Check provision priority (NPL takes precedence).
6. Never hide discrepancies — fix the SQL first, then update reference values.

---

## Dashboard Conventions

- All monetary values displayed in **KZT Billion** with 2 decimal places.
- Risk ratios displayed as **percent** with 2 decimal places.
- Monthly changes for risk ratios reported as **percentage points (pp)**, not relative percent.
- Color palette:
  - Blue (`#1d4ed8`): portfolio balance / Sep 1 baseline
  - Amber (`#f59e0b`): PAR30
  - Red (`#ef4444`): PAR90
  - Purple (`#7c3aed`): NPL
  - Teal (`#0d9488`): Provisions / Programs
  - Orange (`#ea580c`): Concentration
- Green badges (`▼`) indicate risk improvement; red (`▲`) indicate deterioration.
- Dashboard is offline-compatible if CDN scripts are downloaded locally.

---

## AI Development Note

### Where Claude Code accelerated development

1. **Data investigation**: Automated detection of 60 duplicate rows, currency distribution, restructured/written-off counts, and boundary verification across 4,060 rows was completed in a single script pass rather than manual inspection.
2. **SQL view architecture**: The layered view design (clean → active → aggregations → metrics) was planned holistically and executed without iteration.
3. **Dashboard HTML**: The KPI card layout, color system, and Vega-Lite spec integration were written in one pass with consistent styling.
4. **Test scaffolding**: Unit tests for boundary conditions (DPD=30 vs 31, DPD=90 vs 91, restructured priority, written-off exclusion) were generated systematically.

### Mistakes identified and corrected

1. **Incorrect reference values in validate_data.py**: The first run of the validation script used reference values computed with `float` arithmetic in a summary script, which differed from the `Decimal`-precision values by hundreds of thousands of KZT. The reference values were recalculated using Python's `Decimal` module with 50-digit precision and updated in the script. The ratios (PAR30%, PAR90%, NPL%) matched in both runs because the differences were sub-0.01 percentage-point.

2. **None comparison in assert_eq()**: The test helper `assert_eq()` attempted `Decimal(str(None))` when checking that `classify_loan(..., written_off=1)` returns `None`. This raised a `decimal.InvalidOperation` exception. Fixed by adding an explicit `None` check before the Decimal conversion.

### How mistakes were detected

- Mistake 1: Detected by the FAIL output of `validate_data.py` on first run, showing diffs of 100K–440K KZT in absolute balances while ratio checks all passed.
- Mistake 2: Detected immediately as a Python traceback on first test run.

### Validation procedures confirming final result

- `test_metrics.py`: **34 of 34 unit tests pass.**
- `validate_data.py`: **All checks pass**, including absolute balance values (tolerance 0.01 KZT), ratio values (tolerance 0.01 pp), written-off exclusion, NPL double-count check, PAR90 ⊆ PAR30, restructured-in-NPL, and USD→KZT spot conversion.
