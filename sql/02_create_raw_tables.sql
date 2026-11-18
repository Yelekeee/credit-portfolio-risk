-- ============================================================
-- 02_create_raw_tables.sql
-- Credit Portfolio Risk Analytics
-- Creates raw tables to hold ingested CSV data.
-- Idempotent: safe to run multiple times.
-- ============================================================

BEGIN;

-- ----------------------------------------------------------
-- raw.portfolio
-- One row per (report_date, loan_id) snapshot from portfolio.csv.
-- Note: 60 exact duplicate rows exist in the source file;
--       they are removed at the reporting layer via DISTINCT.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.portfolio (
    report_date            DATE           NOT NULL,
    loan_id                VARCHAR(10)    NOT NULL,
    borrower_id            VARCHAR(10)    NOT NULL,
    group_id               VARCHAR(10)    NOT NULL,
    sector                 VARCHAR(100)   NOT NULL,
    program                VARCHAR(200)   NOT NULL,
    currency               CHAR(3)        NOT NULL,
    issue_date             DATE           NOT NULL,
    maturity_date          DATE           NOT NULL,
    -- NUMERIC(20,2) avoids floating-point rounding errors for financial amounts.
    principal_outstanding  NUMERIC(20, 2) NOT NULL,
    days_past_due          INTEGER        NOT NULL DEFAULT 0,
    restructured           SMALLINT       NOT NULL DEFAULT 0,  -- 0 = no, 1 = yes
    written_off            SMALLINT       NOT NULL DEFAULT 0   -- 0 = no, 1 = yes
);

COMMENT ON TABLE raw.portfolio IS
    'Raw loan-level portfolio snapshots. Contains exact duplicates from the '
    'source file; use reporting.v_portfolio_clean for deduplicated data.';

-- ----------------------------------------------------------
-- raw.fx_rates
-- Daily USD/KZT exchange rates from fx.csv.
-- Only USD currency is present in the source file.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.fx_rates (
    rate_date   DATE           NOT NULL,
    currency    CHAR(3)        NOT NULL,
    rate_kzt    NUMERIC(10, 4) NOT NULL,
    PRIMARY KEY (rate_date, currency)
);

COMMENT ON TABLE raw.fx_rates IS
    'Daily foreign exchange rates in KZT. Currently only USD is present.';

-- ----------------------------------------------------------
-- Indexes
-- ----------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_portfolio_report_date
    ON raw.portfolio (report_date);

CREATE INDEX IF NOT EXISTS idx_portfolio_loan_id
    ON raw.portfolio (loan_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_written_off
    ON raw.portfolio (written_off);

CREATE INDEX IF NOT EXISTS idx_portfolio_group_id
    ON raw.portfolio (group_id);

COMMIT;
