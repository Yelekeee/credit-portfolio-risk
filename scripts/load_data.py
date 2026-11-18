"""
load_data.py
Credit Portfolio Risk Analytics

Loads portfolio.csv and fx.csv into PostgreSQL raw schema tables.

Usage:
    python scripts/load_data.py [--dsn DSN]

Default DSN: postgresql://localhost:5432/credit_portfolio

The script is idempotent: it clears existing rows before inserting,
so it can be re-run after data corrections.
"""

import csv
import sys
import argparse
import psycopg2
from pathlib import Path

DEFAULT_DSN = "postgresql://localhost:5432/credit_portfolio"
DATA_DIR = Path(__file__).parent.parent / "data"


def load_fx_rates(cur: psycopg2.extensions.cursor, csv_path: Path) -> int:
    """Load fx.csv into raw.fx_rates. Returns row count inserted."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["date"].strip():
                continue  # skip blank trailing rows
            rows.append((row["date"].strip(), row["currency"].strip(), row["rate_kzt"].strip()))

    cur.execute("TRUNCATE raw.fx_rates RESTART IDENTITY")
    cur.executemany(
        "INSERT INTO raw.fx_rates (rate_date, currency, rate_kzt) VALUES (%s, %s, %s)",
        rows,
    )
    return len(rows)


def load_portfolio(cur: psycopg2.extensions.cursor, csv_path: Path) -> int:
    """Load portfolio.csv into raw.portfolio. Returns row count inserted."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                row["report_date"],
                row["loan_id"],
                row["borrower_id"],
                row["group_id"],
                row["sector"],
                row["program"],
                row["currency"],
                row["issue_date"],
                row["maturity_date"],
                row["principal_outstanding"],
                int(row["days_past_due"]),
                int(row["restructured"]),
                int(row["written_off"]),
            ))

    cur.execute("TRUNCATE raw.portfolio RESTART IDENTITY")
    cur.executemany(
        """
        INSERT INTO raw.portfolio (
            report_date, loan_id, borrower_id, group_id, sector, program,
            currency, issue_date, maturity_date, principal_outstanding,
            days_past_due, restructured, written_off
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        rows,
    )
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Load CSV data into PostgreSQL raw schema.")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL DSN")
    args = parser.parse_args()

    print(f"Connecting to: {args.dsn}")
    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        fx_path = DATA_DIR / "fx.csv"
        portfolio_path = DATA_DIR / "portfolio.csv"

        print(f"Loading {fx_path} ...")
        fx_rows = load_fx_rates(cur, fx_path)
        print(f"  Inserted {fx_rows} FX rate rows.")

        print(f"Loading {portfolio_path} ...")
        p_rows = load_portfolio(cur, portfolio_path)
        print(f"  Inserted {p_rows} portfolio rows (includes source duplicates).")

        conn.commit()
        print("\nData load complete.")

        # Quick row count verification
        cur.execute("SELECT COUNT(*) FROM raw.fx_rates")
        print(f"  raw.fx_rates:  {cur.fetchone()[0]} rows")
        cur.execute("SELECT COUNT(*) FROM raw.portfolio")
        print(f"  raw.portfolio: {cur.fetchone()[0]} rows")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
