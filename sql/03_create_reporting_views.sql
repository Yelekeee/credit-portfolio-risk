-- ============================================================
-- 03_create_reporting_views.sql
-- Credit Portfolio Risk Analytics
-- Clean reporting views on top of raw data.
-- All views are CREATE OR REPLACE — idempotent.
-- ============================================================

-- ----------------------------------------------------------
-- reporting.v_portfolio_clean
-- Deduplicated loan snapshots with KZT-converted balances.
--
-- Design decisions:
--   * Deduplication: 60 exact-duplicate source rows are removed
--     using DISTINCT ON (report_date, loan_id).
--   * FX conversion: KZT loans use rate 1.0; USD loans use the
--     rate from raw.fx_rates for the matching report_date.
--   * Written-off flag is preserved; exclusion happens in
--     downstream views.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_portfolio_clean AS
WITH deduped AS (
    SELECT DISTINCT ON (report_date, loan_id)
        report_date,
        loan_id,
        borrower_id,
        group_id,
        sector,
        program,
        currency,
        issue_date,
        maturity_date,
        principal_outstanding,
        days_past_due,
        restructured,
        written_off
    FROM raw.portfolio
    ORDER BY report_date, loan_id
),
fx AS (
    -- Build a lookup with KZT implicitly = 1
    SELECT
        rate_date,
        currency,
        rate_kzt
    FROM raw.fx_rates
    UNION ALL
    -- Inject KZT identity rate for all reporting dates present in portfolio
    SELECT DISTINCT
        report_date AS rate_date,
        'KZT'       AS currency,
        1.0         AS rate_kzt
    FROM raw.portfolio
)
SELECT
    d.report_date,
    d.loan_id,
    d.borrower_id,
    d.group_id,
    d.sector,
    d.program,
    d.currency,
    d.issue_date,
    d.maturity_date,
    d.principal_outstanding,
    d.days_past_due,
    d.restructured,
    d.written_off,
    -- KZT-converted outstanding balance.
    -- Use NUMERIC(30, 6) to preserve full precision internally;
    -- rounding to 2 decimal places only happens at display/aggregation time.
    -- Casting directly to NUMERIC(24,2) here would accumulate per-loan
    -- rounding errors of up to 0.005 KZT each across ~300 USD loans.
    (d.principal_outstanding * f.rate_kzt)::NUMERIC(30, 6) AS outstanding_kzt
FROM deduped d
JOIN fx f
    ON f.rate_date = d.report_date
    AND f.currency = d.currency;

COMMENT ON VIEW reporting.v_portfolio_clean IS
    'Deduplicated loan snapshots with outstanding balance converted to KZT. '
    'Written-off loans are retained; exclude them (written_off = 0) in downstream queries.';


-- ----------------------------------------------------------
-- reporting.v_portfolio_active
-- Only active (non-written-off) loans with risk classifications.
--
-- Classification rules (mutually exclusive, applied in priority order):
--   1. NPL:    days_past_due > 90 OR restructured = 1
--   2. PAR90:  days_past_due > 90 (subset of NPL via DPD condition)
--   3. PAR30:  days_past_due > 30
--   4. PAR1:   days_past_due BETWEEN 1 AND 30
--   5. CURRENT: days_past_due = 0 (and not restructured)
--
-- Provision rates (mutually exclusive, NPL takes priority):
--   NPL           → 50%
--   DPD 31–90     → 10%
--   DPD 1–30      → 1%
--   DPD 0 current → 0%
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_portfolio_active AS
SELECT
    report_date,
    loan_id,
    borrower_id,
    group_id,
    sector,
    program,
    currency,
    issue_date,
    maturity_date,
    principal_outstanding,
    days_past_due,
    restructured,
    outstanding_kzt,

    -- NPL flag: DPD > 90 OR restructured (no double counting via boolean OR)
    CASE
        WHEN days_past_due > 90 OR restructured = 1 THEN 1
        ELSE 0
    END AS is_npl,

    -- PAR30 flag: DPD > 30 (includes DPD > 90)
    CASE WHEN days_past_due > 30 THEN 1 ELSE 0 END AS is_par30,

    -- PAR90 flag: DPD > 90
    CASE WHEN days_past_due > 90 THEN 1 ELSE 0 END AS is_par90,

    -- Provision rate — mutually exclusive, NPL takes highest priority
    CASE
        WHEN days_past_due > 90 OR restructured = 1 THEN NUMERIC '0.50'
        WHEN days_past_due > 30                      THEN NUMERIC '0.10'
        WHEN days_past_due > 0                       THEN NUMERIC '0.01'
        ELSE                                              NUMERIC '0.00'
    END AS provision_rate,

    -- Provision amount in KZT — keep full precision; round at aggregation layer
    (outstanding_kzt * CASE
        WHEN days_past_due > 90 OR restructured = 1 THEN NUMERIC '0.50'
        WHEN days_past_due > 30                      THEN NUMERIC '0.10'
        WHEN days_past_due > 0                       THEN NUMERIC '0.01'
        ELSE                                              NUMERIC '0.00'
    END) AS provision_kzt

FROM reporting.v_portfolio_clean
WHERE written_off = 0;

COMMENT ON VIEW reporting.v_portfolio_active IS
    'Active (non-written-off) loans with risk classification flags and provision amounts. '
    'Grain: one row per (report_date, loan_id).';


-- ----------------------------------------------------------
-- reporting.v_portfolio_by_industry
-- Portfolio balance and risk metrics aggregated by sector.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_portfolio_by_industry AS
SELECT
    report_date,
    sector,
    COUNT(*)                                  AS loan_count,
    SUM(outstanding_kzt)                      AS total_kzt,
    SUM(CASE WHEN is_par30 = 1 THEN outstanding_kzt ELSE 0 END) AS par30_kzt,
    SUM(CASE WHEN is_par90 = 1 THEN outstanding_kzt ELSE 0 END) AS par90_kzt,
    SUM(CASE WHEN is_npl   = 1 THEN outstanding_kzt ELSE 0 END) AS npl_kzt,
    SUM(provision_kzt)                        AS provision_kzt
FROM reporting.v_portfolio_active
GROUP BY report_date, sector;

COMMENT ON VIEW reporting.v_portfolio_by_industry IS
    'Portfolio totals and risk metrics by sector and reporting date.';


-- ----------------------------------------------------------
-- reporting.v_portfolio_by_program
-- Portfolio balance and risk metrics aggregated by program.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_portfolio_by_program AS
SELECT
    report_date,
    program,
    COUNT(*)                                  AS loan_count,
    SUM(outstanding_kzt)                      AS total_kzt,
    SUM(CASE WHEN is_par30 = 1 THEN outstanding_kzt ELSE 0 END) AS par30_kzt,
    SUM(CASE WHEN is_par90 = 1 THEN outstanding_kzt ELSE 0 END) AS par90_kzt,
    SUM(CASE WHEN is_npl   = 1 THEN outstanding_kzt ELSE 0 END) AS npl_kzt,
    SUM(provision_kzt)                        AS provision_kzt
FROM reporting.v_portfolio_active
GROUP BY report_date, program;

COMMENT ON VIEW reporting.v_portfolio_by_program IS
    'Portfolio totals and risk metrics by program and reporting date.';


-- ----------------------------------------------------------
-- reporting.v_top_borrower_groups
-- Group-level concentration for all reporting dates.
-- Top-10 flag is added per reporting date.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_top_borrower_groups AS
WITH group_totals AS (
    SELECT
        report_date,
        group_id,
        COUNT(DISTINCT loan_id)  AS loan_count,
        SUM(outstanding_kzt)     AS total_kzt
    FROM reporting.v_portfolio_active
    GROUP BY report_date, group_id
),
ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY report_date ORDER BY total_kzt DESC) AS rank_by_balance
    FROM group_totals
)
SELECT
    report_date,
    group_id,
    loan_count,
    total_kzt,
    rank_by_balance,
    CASE WHEN rank_by_balance <= 10 THEN 1 ELSE 0 END AS is_top10
FROM ranked;

COMMENT ON VIEW reporting.v_top_borrower_groups IS
    'Borrower group totals ranked by outstanding balance. is_top10 = 1 for the 10 largest groups.';
