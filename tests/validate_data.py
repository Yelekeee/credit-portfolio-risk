"""
validate_data.py
Credit Portfolio Risk Analytics

Independent Python-based validation of financial metrics.
Runs entirely from CSV files — no database dependency.
Compare these results against the SQL reporting views.

Usage:
    python tests/validate_data.py

All amounts are in KZT unless stated otherwise.
"""

import csv
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
INFO = "\033[34mINFO\033[0m"

# ── Tolerance for floating-point comparisons (0.01 KZT) ──────────────────────
TOLERANCE = Decimal("0.01")

# ── Reference values computed by independent Python script ───────────────────
# These are the gold-standard values against which SQL output is compared.
REFERENCE = {
    "2026-09-01": {
        "total_kzt":        Decimal("498153228694.57"),
        "par30_kzt":        Decimal("60024505068.78"),
        "par90_kzt":        Decimal("31097834606.34"),
        "npl_kzt":          Decimal("59035360077.01"),
        "provision_kzt":    Decimal("32737008526.96"),
        "top10_kzt":        Decimal("84898785647.82"),
        "par30_pct":        Decimal("12.05"),
        "par90_pct":        Decimal("6.24"),
        "npl_pct":          Decimal("11.85"),
        "top10_pct":        Decimal("17.04"),
    },
    "2026-10-01": {
        "total_kzt":        Decimal("484674770832.76"),
        "par30_kzt":        Decimal("50049378217.78"),
        "par90_kzt":        Decimal("21639248455.09"),
        "npl_kzt":          Decimal("48533283502.04"),
        "provision_kzt":    Decimal("27272294750.79"),
        "top10_kzt":        Decimal("82476133191.34"),
        "par30_pct":        Decimal("10.33"),
        "par90_pct":        Decimal("4.46"),
        "npl_pct":          Decimal("10.01"),
        "top10_pct":        Decimal("17.02"),
    },
}


def load_data():
    portfolio = []
    with open(DATA_DIR / "portfolio.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            portfolio.append(row)

    fx_map = {}
    with open(DATA_DIR / "fx.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["date"].strip():
                fx_map[(row["date"], row["currency"])] = Decimal(row["rate_kzt"])

    return portfolio, fx_map


def deduplicate(portfolio):
    seen = set()
    deduped = []
    for r in portfolio:
        key = (r["report_date"], r["loan_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def to_kzt(amount, currency, report_date, fx_map):
    if currency == "KZT":
        return Decimal(amount)
    rate = fx_map.get((report_date, currency))
    if rate is None:
        raise ValueError(f"No FX rate for {currency} on {report_date}")
    return Decimal(amount) * rate


def calculate_metrics(loans, fx_map, report_date):
    active = [r for r in loans if r["written_off"] == "0"]
    for r in active:
        r["_kzt"] = to_kzt(r["principal_outstanding"], r["currency"], report_date, fx_map)

    total = sum(r["_kzt"] for r in active)
    par30_kzt = sum(r["_kzt"] for r in active if int(r["days_past_due"]) > 30)
    par90_kzt = sum(r["_kzt"] for r in active if int(r["days_past_due"]) > 90)

    npl_ids = {r["loan_id"] for r in active if int(r["days_past_due"]) > 90 or r["restructured"] == "1"}
    npl_kzt = sum(r["_kzt"] for r in active if r["loan_id"] in npl_ids)

    prov = Decimal("0")
    for r in active:
        dpd = int(r["days_past_due"])
        bal = r["_kzt"]
        if r["loan_id"] in npl_ids:
            prov += bal * Decimal("0.50")
        elif dpd > 30:
            prov += bal * Decimal("0.10")
        elif dpd > 0:
            prov += bal * Decimal("0.01")

    group_bal = defaultdict(Decimal)
    for r in active:
        group_bal[r["group_id"]] += r["_kzt"]
    top10_kzt = sum(sorted(group_bal.values(), reverse=True)[:10])

    return {
        "total_kzt": total,
        "par30_kzt": par30_kzt,
        "par90_kzt": par90_kzt,
        "npl_kzt": npl_kzt,
        "provision_kzt": prov,
        "top10_kzt": top10_kzt,
        "par30_pct": (par30_kzt / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "par90_pct": (par90_kzt / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "npl_pct":   (npl_kzt   / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "top10_pct": (top10_kzt / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


def check(label, actual, expected, tolerance=TOLERANCE):
    diff = abs(actual - expected)
    status = PASS if diff <= tolerance else FAIL
    print(f"  [{status}] {label}")
    if diff > tolerance:
        print(f"         expected={expected}, actual={actual}, diff={diff}")
    return diff <= tolerance


def run_checks():
    print("=" * 60)
    print("Credit Portfolio Risk — Independent Validation")
    print("=" * 60)

    portfolio, fx_map = load_data()
    raw_count = len(portfolio)
    deduped = deduplicate(portfolio)
    dedup_count = len(deduped)

    print(f"\n[{INFO}] Raw portfolio rows:         {raw_count}")
    print(f"[{INFO}] After deduplication:         {dedup_count}")
    print(f"[{INFO}] Duplicates removed:          {raw_count - dedup_count}")

    all_pass = True

    for report_date in ["2026-09-01", "2026-10-01"]:
        print(f"\n── {report_date} ──────────────────────────────────")
        loans = [r for r in deduped if r["report_date"] == report_date]
        metrics = calculate_metrics(loans, fx_map, report_date)
        ref = REFERENCE[report_date]

        all_pass &= check("Total portfolio KZT", metrics["total_kzt"],     ref["total_kzt"])
        all_pass &= check("PAR30 balance KZT",   metrics["par30_kzt"],     ref["par30_kzt"])
        all_pass &= check("PAR90 balance KZT",   metrics["par90_kzt"],     ref["par90_kzt"])
        all_pass &= check("NPL balance KZT",     metrics["npl_kzt"],       ref["npl_kzt"])
        all_pass &= check("Provisions KZT",      metrics["provision_kzt"], ref["provision_kzt"])
        all_pass &= check("Top-10 KZT",          metrics["top10_kzt"],     ref["top10_kzt"])

        # Ratio checks (tolerance 0.01 pp)
        ratio_tol = Decimal("0.01")
        all_pass &= check("PAR30 %", metrics["par30_pct"], ref["par30_pct"], ratio_tol)
        all_pass &= check("PAR90 %", metrics["par90_pct"], ref["par90_pct"], ratio_tol)
        all_pass &= check("NPL %",   metrics["npl_pct"],   ref["npl_pct"],   ratio_tol)
        all_pass &= check("Top-10 concentration %", metrics["top10_pct"], ref["top10_pct"], ratio_tol)

    # Additional spot checks
    print(f"\n── Additional data quality checks ───────────────────")

    # 1. Verify Sep 1 FX rate
    sep_rate = fx_map.get(("2026-09-01", "USD"))
    all_pass &= check("Sep 1 USD/KZT rate = 478.35", sep_rate, Decimal("478.35"), Decimal("0.001"))

    # 2. Verify Oct 1 FX rate
    oct_rate = fx_map.get(("2026-10-01", "USD"))
    all_pass &= check("Oct 1 USD/KZT rate = 482.10", oct_rate, Decimal("482.10"), Decimal("0.001"))

    # 3. Check written-off loans are excluded
    for rd in ["2026-09-01", "2026-10-01"]:
        loans = [r for r in deduped if r["report_date"] == rd]
        active = [r for r in loans if r["written_off"] == "0"]
        woff = [r for r in loans if r["written_off"] == "1"]
        status = PASS if len(woff) > 0 else FAIL  # there should be some written-off loans
        print(f"  [{status}] {rd}: {len(woff)} written-off loans excluded, {len(active)} active")

    # 4. No loan counted twice in NPL (verify set union logic)
    for rd in ["2026-09-01", "2026-10-01"]:
        loans = [r for r in deduped if r["report_date"] == rd and r["written_off"] == "0"]
        for r in loans:
            r["_kzt"] = to_kzt(r["principal_outstanding"], r["currency"], rd, fx_map)
        npl_ids = {r["loan_id"] for r in loans if int(r["days_past_due"]) > 90 or r["restructured"] == "1"}
        npl_rows = [r for r in loans if r["loan_id"] in npl_ids]
        unique_ids = {r["loan_id"] for r in npl_rows}
        duplicated = len(npl_rows) - len(unique_ids)
        ok = duplicated == 0
        all_pass &= ok
        status = PASS if ok else FAIL
        print(f"  [{status}] {rd}: NPL double-count check (duplicated={duplicated})")

    # 5. PAR90 is a subset of PAR30
    for rd in ["2026-09-01", "2026-10-01"]:
        loans = [r for r in deduped if r["report_date"] == rd and r["written_off"] == "0"]
        for r in loans:
            r["_kzt"] = to_kzt(r["principal_outstanding"], r["currency"], rd, fx_map)
        par30 = sum(r["_kzt"] for r in loans if int(r["days_past_due"]) > 30)
        par90 = sum(r["_kzt"] for r in loans if int(r["days_past_due"]) > 90)
        ok = par90 <= par30
        all_pass &= ok
        status = PASS if ok else FAIL
        print(f"  [{status}] {rd}: PAR90 ({par90/Decimal('1e9'):.3f}B) <= PAR30 ({par30/Decimal('1e9'):.3f}B)")

    # 6. Restructured loans are in NPL
    for rd in ["2026-09-01", "2026-10-01"]:
        loans = [r for r in deduped if r["report_date"] == rd and r["written_off"] == "0"]
        for r in loans:
            r["_kzt"] = to_kzt(r["principal_outstanding"], r["currency"], rd, fx_map)
        npl_ids = {r["loan_id"] for r in loans if int(r["days_past_due"]) > 90 or r["restructured"] == "1"}
        restructured = [r for r in loans if r["restructured"] == "1"]
        missed = [r for r in restructured if r["loan_id"] not in npl_ids]
        ok = len(missed) == 0
        all_pass &= ok
        status = PASS if ok else FAIL
        print(f"  [{status}] {rd}: All {len(restructured)} restructured loans in NPL (missed={len(missed)})")

    # 7. Verify individual USD loan conversion
    # Pick a known USD loan from Sep 1
    sample = next(
        (r for r in deduped if r["report_date"] == "2026-09-01" and r["currency"] == "USD"),
        None,
    )
    if sample:
        expected_kzt = Decimal(sample["principal_outstanding"]) * Decimal("478.35")
        actual_kzt = to_kzt(sample["principal_outstanding"], sample["currency"], "2026-09-01", fx_map)
        ok = abs(actual_kzt - expected_kzt) <= TOLERANCE
        all_pass &= ok
        status = PASS if ok else FAIL
        print(f"  [{status}] USD→KZT sample: {sample['loan_id']} "
              f"{sample['principal_outstanding']} USD × 478.35 = {float(expected_kzt):,.2f} KZT")

    print(f"\n{'='*60}")
    if all_pass:
        print(f"[{PASS}] All validation checks passed.")
    else:
        print(f"[{FAIL}] One or more validation checks FAILED. See details above.")
    print("=" * 60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_checks())
