-- ============================================================
-- 01_create_schemas.sql
-- Credit Portfolio Risk Analytics
-- Creates the raw and reporting schemas.
-- Idempotent: safe to run multiple times.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;
COMMENT ON SCHEMA raw IS 'Holds the original source data imported verbatim from CSV files.';

CREATE SCHEMA IF NOT EXISTS reporting;
COMMENT ON SCHEMA reporting IS 'Holds clean reporting views and metric calculations.';

COMMIT;
