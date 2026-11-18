"""
test_metrics.py
Credit Portfolio Risk Analytics

Unit tests for financial metric calculation logic.
Tests pure Python functions — no database or file I/O required.

Usage:
    python -m pytest tests/test_metrics.py -v
    # or
    python tests/test_metrics.py
"""

import sys
from decimal import Decimal
from pathlib import Path

# Allow import from project root
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helper functions mirroring the SQL logic ─────────────────────────────────

def classify_loan(days_past_due: int, restructured: int, written_off: int):
    """Return (is_npl, is_par30, is_par90, provision_rate) for a loan."""
    if written_off:
        return None  # excluded

    is_npl   = int(days_past_due > 90 or restructured == 1)
    is_par90 = int(days_past_due > 90)
    is_par30 = int(days_past_due > 30)

    if is_npl:
        provision_rate = Decimal("0.50")
    elif days_past_due > 30:
        provision_rate = Decimal("0.10")
    elif days_past_due > 0:
        provision_rate = Decimal("0.01")
    else:
        provision_rate = Decimal("0.00")

    return is_npl, is_par30, is_par90, provision_rate


def total_portfolio(loans):
    return sum(Decimal(str(r["kzt"])) for r in loans if not r.get("written_off", 0))


def par_ratio(loans, par_field):
    total = total_portfolio(loans)
    if total == 0:
        return Decimal("0")
    par_bal = sum(
        Decimal(str(r["kzt"]))
        for r in loans
        if not r.get("written_off", 0) and r.get(par_field, 0)
    )
    return par_bal / total * 100


# ── Tests ─────────────────────────────────────────────────────────────────────

PASS_COUNT = 0
FAIL_COUNT = 0


def assert_eq(label, actual, expected, tolerance=Decimal("0.0001")):
    global PASS_COUNT, FAIL_COUNT
    if actual is None or expected is None:
        ok = actual is expected
        diff = None
    else:
        diff = abs(Decimal(str(actual)) - Decimal(str(expected)))
        ok = diff <= tolerance
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")
    if not ok:
        print(f"         expected={expected}, actual={actual}" +
              (f", diff={diff}" if diff is not None else ""))
        FAIL_COUNT += 1
    else:
        PASS_COUNT += 1
    return ok


def test_loan_classification():
    print("\n── test_loan_classification ──────────────────────────")

    # Current loan
    r = classify_loan(0, 0, 0)
    assert_eq("Current: is_npl=0",           r[0], 0)
    assert_eq("Current: is_par30=0",          r[1], 0)
    assert_eq("Current: provision_rate=0",    r[3], Decimal("0.00"))

    # 1-30 DPD (PAR1, not PAR30)
    r = classify_loan(15, 0, 0)
    assert_eq("DPD=15: is_npl=0",             r[0], 0)
    assert_eq("DPD=15: is_par30=0",           r[1], 0)
    assert_eq("DPD=15: provision_rate=0.01",  r[3], Decimal("0.01"))

    # 30 DPD boundary (not PAR30 — must be STRICTLY > 30)
    r = classify_loan(30, 0, 0)
    assert_eq("DPD=30: is_par30=0",           r[1], 0)
    assert_eq("DPD=30: provision_rate=0.01",  r[3], Decimal("0.01"))

    # 31 DPD boundary (PAR30, not NPL)
    r = classify_loan(31, 0, 0)
    assert_eq("DPD=31: is_par30=1",           r[1], 1)
    assert_eq("DPD=31: is_npl=0",             r[0], 0)
    assert_eq("DPD=31: provision_rate=0.10",  r[3], Decimal("0.10"))

    # 90 DPD boundary (PAR30, not NPL — must be STRICTLY > 90)
    r = classify_loan(90, 0, 0)
    assert_eq("DPD=90: is_npl=0",             r[0], 0)
    assert_eq("DPD=90: is_par30=1",           r[1], 1)
    assert_eq("DPD=90: is_par90=0",           r[2], 0)
    assert_eq("DPD=90: provision_rate=0.10",  r[3], Decimal("0.10"))

    # 91 DPD boundary (NPL)
    r = classify_loan(91, 0, 0)
    assert_eq("DPD=91: is_npl=1",             r[0], 1)
    assert_eq("DPD=91: is_par90=1",           r[2], 1)
    assert_eq("DPD=91: provision_rate=0.50",  r[3], Decimal("0.50"))

    # Restructured with DPD=0 → NPL (key business rule)
    r = classify_loan(0, 1, 0)
    assert_eq("Restructured DPD=0: is_npl=1",           r[0], 1)
    assert_eq("Restructured DPD=0: provision_rate=0.50", r[3], Decimal("0.50"))

    # Restructured with DPD=50 → NPL takes priority over 10% bucket
    r = classify_loan(50, 1, 0)
    assert_eq("Restructured DPD=50: is_npl=1",           r[0], 1)
    assert_eq("Restructured DPD=50: provision_rate=0.50", r[3], Decimal("0.50"))

    # Written-off → excluded
    r = classify_loan(200, 0, 1)
    assert_eq("Written-off: returns None", r, None)


def test_par_ratios():
    print("\n── test_par_ratios ───────────────────────────────────")

    loans = [
        {"kzt": 1000000, "written_off": 0, "is_par30": 0, "is_par90": 0, "is_npl": 0},
        {"kzt": 2000000, "written_off": 0, "is_par30": 1, "is_par90": 0, "is_npl": 0},
        {"kzt": 3000000, "written_off": 0, "is_par30": 1, "is_par90": 1, "is_npl": 1},
        {"kzt": 500000,  "written_off": 1, "is_par30": 1, "is_par90": 1, "is_npl": 1},  # excluded
    ]

    total = total_portfolio(loans)
    assert_eq("Total excl. written-off = 6,000,000", total, Decimal("6000000"))

    par30 = par_ratio(loans, "is_par30")
    # (2M + 3M) / 6M * 100 = 83.33%
    assert_eq("PAR30 = 83.33%", par30, Decimal("83.3333"), Decimal("0.001"))

    par90 = par_ratio(loans, "is_par90")
    # 3M / 6M * 100 = 50.00%
    assert_eq("PAR90 = 50.00%", par90, Decimal("50.0000"), Decimal("0.001"))

    npl = par_ratio(loans, "is_npl")
    # 3M / 6M * 100 = 50.00%
    assert_eq("NPL = 50.00%", npl, Decimal("50.0000"), Decimal("0.001"))


def test_provision_calculation():
    print("\n── test_provision_calculation ────────────────────────")

    loans = [
        # DPD=0, current → 0% provision
        {"dpd": 0, "restructured": 0, "written_off": 0, "kzt": Decimal("1000000")},
        # DPD=15 → 1%
        {"dpd": 15, "restructured": 0, "written_off": 0, "kzt": Decimal("1000000")},
        # DPD=50 → 10%
        {"dpd": 50, "restructured": 0, "written_off": 0, "kzt": Decimal("1000000")},
        # DPD=100 → 50% (NPL via DPD)
        {"dpd": 100, "restructured": 0, "written_off": 0, "kzt": Decimal("1000000")},
        # DPD=50, restructured → 50% (NPL takes priority)
        {"dpd": 50, "restructured": 1, "written_off": 0, "kzt": Decimal("1000000")},
        # Written-off → excluded
        {"dpd": 200, "restructured": 0, "written_off": 1, "kzt": Decimal("1000000")},
    ]

    total_prov = Decimal("0")
    for r in loans:
        if r["written_off"]:
            continue
        result = classify_loan(r["dpd"], r["restructured"], r["written_off"])
        prov = r["kzt"] * result[3]
        total_prov += prov

    # Expected: 0 + 10000 + 100000 + 500000 + 500000 = 1,110,000
    assert_eq("Total provisions = 1,110,000", total_prov, Decimal("1110000"))


def test_npl_no_double_counting():
    print("\n── test_npl_no_double_counting ───────────────────────")

    # A loan with DPD>90 AND restructured should appear only once in NPL
    loans = [
        {"loan_id": "L001", "dpd": 120, "restructured": 1, "written_off": 0, "kzt": Decimal("5000000")},
        {"loan_id": "L002", "dpd": 0,   "restructured": 1, "written_off": 0, "kzt": Decimal("3000000")},
        {"loan_id": "L003", "dpd": 95,  "restructured": 0, "written_off": 0, "kzt": Decimal("2000000")},
        {"loan_id": "L004", "dpd": 0,   "restructured": 0, "written_off": 0, "kzt": Decimal("1000000")},
    ]

    npl_ids = {r["loan_id"] for r in loans if r["dpd"] > 90 or r["restructured"] == 1}
    npl_balance = sum(r["kzt"] for r in loans if r["loan_id"] in npl_ids)
    total = sum(r["kzt"] for r in loans)

    # L001, L002, L003 are NPL = 10M; total = 11M
    assert_eq("NPL IDs count = 3", len(npl_ids), 3)
    assert_eq("NPL balance = 10,000,000", npl_balance, Decimal("10000000"))
    assert_eq("NPL ratio = 90.91%", npl_balance / total * 100, Decimal("90.9091"), Decimal("0.001"))


def test_top10_concentration():
    print("\n── test_top10_concentration ──────────────────────────")

    group_balances = {f"G{i:04d}": Decimal(str(i * 1000000)) for i in range(1, 21)}  # G0001..G0020
    # Sum of top 10 = G0020+G0019+...+G0011 = (11+12+...+20) * 1M = 155M
    top10_bal = sum(sorted(group_balances.values(), reverse=True)[:10])
    total = sum(group_balances.values())

    # Total = sum(1..20)*1M = 210M
    assert_eq("Total = 210,000,000", total, Decimal("210000000"))
    assert_eq("Top-10 = 155,000,000", top10_bal, Decimal("155000000"))
    assert_eq("Top-10 concentration = 73.81%",
              top10_bal / total * 100, Decimal("73.8095"), Decimal("0.001"))


def run_all():
    test_loan_classification()
    test_par_ratios()
    test_provision_calculation()
    test_npl_no_double_counting()
    test_top10_concentration()

    print(f"\n{'='*60}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed.")
    print("=" * 60)
    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
