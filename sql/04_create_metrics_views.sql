-- ============================================================
-- 04_create_metrics_views.sql
-- Credit Portfolio Risk Analytics
-- Summary KPI views for dashboard and reporting.
-- All views are CREATE OR REPLACE — idempotent.
-- ============================================================

-- ----------------------------------------------------------
-- reporting.v_portfolio_metrics
-- One row per reporting date with all headline KPIs.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_portfolio_metrics AS
WITH base AS (
    SELECT
        report_date,
        SUM(outstanding_kzt)                                        AS total_kzt,
        SUM(CASE WHEN is_par30 = 1 THEN outstanding_kzt ELSE 0 END) AS par30_kzt,
        SUM(CASE WHEN is_par90 = 1 THEN outstanding_kzt ELSE 0 END) AS par90_kzt,
        SUM(CASE WHEN is_npl   = 1 THEN outstanding_kzt ELSE 0 END) AS npl_kzt,
        SUM(provision_kzt)                                           AS provision_kzt,
        COUNT(*)                                                     AS loan_count
    FROM reporting.v_portfolio_active
    GROUP BY report_date
),
top10 AS (
    SELECT
        report_date,
        SUM(total_kzt) AS top10_kzt
    FROM reporting.v_top_borrower_groups
    WHERE is_top10 = 1
    GROUP BY report_date
)
SELECT
    b.report_date,
    b.loan_count,

    -- Raw KZT balances
    b.total_kzt,
    b.par30_kzt,
    b.par90_kzt,
    b.npl_kzt,
    b.provision_kzt,
    t.top10_kzt,

    -- KZT balances in billions (2 decimal places for display)
    ROUND(b.total_kzt     / 1e9, 2) AS total_kzt_bn,
    ROUND(b.provision_kzt / 1e9, 2) AS provision_kzt_bn,
    ROUND(t.top10_kzt     / 1e9, 2) AS top10_kzt_bn,

    -- Risk ratios (percentage, 2 decimal places)
    ROUND(b.par30_kzt / b.total_kzt * 100, 2) AS par30_pct,
    ROUND(b.par90_kzt / b.total_kzt * 100, 2) AS par90_pct,
    ROUND(b.npl_kzt   / b.total_kzt * 100, 2) AS npl_pct,
    ROUND(t.top10_kzt / b.total_kzt * 100, 2) AS top10_concentration_pct

FROM base b
JOIN top10 t USING (report_date)
ORDER BY b.report_date;

COMMENT ON VIEW reporting.v_portfolio_metrics IS
    'One row per reporting date. Contains headline KPIs: total portfolio, '
    'PAR30, PAR90, NPL, provisions, and top-10 borrower concentration.';


-- ----------------------------------------------------------
-- reporting.v_monthly_changes
-- Compares October 1 to September 1 (absolute + percentage-point).
--
-- IMPORTANT: all percentage-point differences are computed from
-- raw KZT balance ratios, NOT from pre-rounded pct display values.
-- Subtracting rounded ratios (e.g. 17.02 - 17.04 = -0.02) produces
-- a different result than rounding the raw difference
-- (17.0168 - 17.0427 = -0.0259 → -0.03).  The raw-then-round
-- method is correct.
-- ----------------------------------------------------------
CREATE OR REPLACE VIEW reporting.v_monthly_changes AS
WITH sep AS (
    SELECT * FROM reporting.v_portfolio_metrics WHERE report_date = '2026-09-01'
),
oct AS (
    SELECT * FROM reporting.v_portfolio_metrics WHERE report_date = '2026-10-01'
)
SELECT
    sep.report_date       AS base_date,
    oct.report_date       AS comparison_date,

    -- Portfolio change
    oct.total_kzt - sep.total_kzt                                                AS portfolio_change_kzt,
    ROUND((oct.total_kzt - sep.total_kzt) / sep.total_kzt * 100, 2)             AS portfolio_change_pct,

    -- Risk ratio pp changes — computed from raw KZT balances, then rounded
    ROUND((oct.par30_kzt / oct.total_kzt - sep.par30_kzt / sep.total_kzt) * 100, 2) AS par30_change_pp,
    ROUND((oct.par90_kzt / oct.total_kzt - sep.par90_kzt / sep.total_kzt) * 100, 2) AS par90_change_pp,
    ROUND((oct.npl_kzt   / oct.total_kzt - sep.npl_kzt   / sep.total_kzt) * 100, 2) AS npl_change_pp,

    -- Provision change
    oct.provision_kzt - sep.provision_kzt                                        AS provision_change_kzt,
    ROUND((oct.provision_kzt - sep.provision_kzt) / sep.provision_kzt * 100, 2) AS provision_change_pct,

    -- Concentration pp change — computed from raw KZT balances, then rounded
    ROUND((oct.top10_kzt / oct.total_kzt - sep.top10_kzt / sep.total_kzt) * 100, 2) AS top10_concentration_change_pp

FROM sep, oct;

COMMENT ON VIEW reporting.v_monthly_changes IS
    'Month-over-month change between Oct 1, 2026 and Sep 1, 2026. '
    'All pp differences computed from raw KZT balances (not from rounded display ratios).';
