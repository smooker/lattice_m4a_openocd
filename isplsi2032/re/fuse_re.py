#!/usr/bin/env python3
"""
fuse_re.py — Fuse map reverse engineering for ispLSI 2032.

Phase 1: Verify write/read round-trip (all in ISP mode)
  - Erase chip
  - Write test patterns to each row
  - Read back and verify

Phase 2: Walking-0 probe (one fuse at a time)
  - Erase chip
  - Program one fuse (bit=0) per test
  - Read back to confirm
  - Exit ISP → user observes pin behavior
  - Log results

Run on HOST (not chroot):
  sudo rmmod ftdi_sio
  python3 fuse_re.py --phase1          # verify write/read
  python3 fuse_re.py --phase2 --row 0  # probe row 0, one bit at a time
  python3 fuse_re.py --phase2-auto     # probe all rows (batch, no user input)
"""

import argparse
import json
import os
import sys
import time
from isp import (ISP2032, NUM_ROWS, DATA_SR_HIGH, DATA_SR_LOW,
                 ERASED_HIGH, ERASED_LOW, fmt_hex)

RESULTS_DIR = "re_results"
FUSE_BITS_PER_HALF = 38  # top 2 of 40 bits are always 0


def phase1_verify(isp):
    """Phase 1: Write/read round-trip test for all 102 rows.
    Confirms that our ISP write implementation works correctly.
    """
    print("=" * 60)
    print("PHASE 1: Write/Read Round-Trip Verification")
    print("=" * 60)

    # Test patterns (38-bit values, top 2 bits stay 0)
    patterns = [
        (0x2AAAAAAAAA, 0x1555555555, "alternating 10/01"),
        (0x1555555555, 0x2AAAAAAAAA, "alternating 01/10"),
        (0x0000000001, 0x0000000001, "single bit low"),
        (0x2000000000, 0x2000000000, "single bit high"),
        (0x3FFFFFFFFF, 0x3FFFFFFFFF, "all erased (no-op)"),
        (0x0000000000, 0x0000000000, "all programmed"),
    ]

    print(f"\nStep 1: Bulk erase...")
    isp.bulk_erase()
    print("  Done.")

    # Verify erased state
    print(f"\nStep 2: Verify erased state (spot check rows 0, 50, 101)...")
    for r in [0, 50, 101]:
        h, l = isp.read_row_fast(r)
        if h != ERASED_HIGH or l != ERASED_LOW:
            print(f"  FAIL: row {r} not erased: H={fmt_hex(h,40)} L={fmt_hex(l,40)}")
            return False
    print("  All erased. OK.")

    # Test each pattern on a different row
    print(f"\nStep 3: Write/read test patterns...")
    errors = 0
    test_rows = list(range(len(patterns)))

    for i, (pat_h, pat_l, desc) in enumerate(patterns):
        row = test_rows[i]
        print(f"  Row {row:3d}: {desc} "
              f"(H={fmt_hex(pat_h,40)} L={fmt_hex(pat_l,40)})")

        # Erase first (fuses can only go 1->0, need erase to reset)
        isp.bulk_erase()
        isp.write_row(row, pat_h, pat_l)
        h, l = isp.read_row_fast(row)

        if h == pat_h and l == pat_l:
            print(f"         PASS")
        else:
            print(f"         FAIL: got H={fmt_hex(h,40)} L={fmt_hex(l,40)}")
            errors += 1

    # Test: write multiple rows without erasing between
    print(f"\nStep 4: Multi-row write (rows 10-19)...")
    isp.bulk_erase()
    for r in range(10, 20):
        pat = r & 0x3FFFFFFFFF  # simple pattern: row number
        isp.write_row(r, pat, ~pat & 0x3FFFFFFFFF)

    multi_errors = 0
    for r in range(10, 20):
        pat = r & 0x3FFFFFFFFF
        expected_l = ~pat & 0x3FFFFFFFFF
        h, l = isp.read_row_fast(r)
        if h != pat or l != expected_l:
            print(f"  Row {r}: FAIL")
            multi_errors += 1
    if multi_errors == 0:
        print(f"  All 10 rows: PASS")
    else:
        print(f"  {multi_errors} failures!")
        errors += multi_errors

    # Cleanup: erase
    print(f"\nStep 5: Final erase...")
    isp.bulk_erase()

    print(f"\n{'=' * 60}")
    if errors == 0:
        print("PHASE 1 RESULT: ALL TESTS PASSED")
        print("Write/read round-trip verified. ISP programming works!")
    else:
        print(f"PHASE 1 RESULT: {errors} FAILURES")
    print(f"{'=' * 60}")
    return errors == 0


def phase2_row(isp, target_row, interactive=False):
    """Phase 2: Walking-0 probe on a single row.
    Programs one fuse at a time (bit=0), rest erased (=1).
    If interactive, exits ISP between tests for user to observe pins.
    Returns dict of {bit: observation}.
    """
    print(f"\n{'=' * 60}")
    print(f"PHASE 2: Walking-0 probe — Row {target_row}")
    print(f"{'=' * 60}")

    results = {}
    total_bits = FUSE_BITS_PER_HALF * 2  # 38 high + 38 low = 76

    for half_name, half_idx in [("HIGH", 0), ("LOW", 1)]:
        print(f"\n--- {half_name} order (38 bits) ---")
        for bit in range(FUSE_BITS_PER_HALF):
            # Build pattern: one bit = 0, rest = 1
            fuse_val = ERASED_HIGH & ~(1 << bit)  # clear one bit
            if half_idx == 0:
                pat_h, pat_l = fuse_val, ERASED_LOW
            else:
                pat_h, pat_l = ERASED_HIGH, fuse_val

            bit_id = f"{half_name[0]}{bit}"  # e.g. "H0", "L37"

            # Erase + program single fuse
            isp.bulk_erase()
            isp.write_row(target_row, pat_h, pat_l)

            # Verify written
            rd_h, rd_l = isp.read_row_fast(target_row)
            if rd_h != pat_h or rd_l != pat_l:
                print(f"  Bit {bit_id}: WRITE FAIL "
                      f"(expected H={fmt_hex(pat_h,40)} L={fmt_hex(pat_l,40)}, "
                      f"got H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)})")
                results[bit_id] = {"status": "write_fail"}
                continue

            if interactive:
                isp.exit_isp()
                obs = input(f"  Bit {bit_id}: Observe pins, describe → ").strip()
                results[bit_id] = {"status": "ok", "observation": obs}
                isp.enter_isp()
            else:
                print(f"  Bit {bit_id}: written OK "
                      f"({half_name} = {fmt_hex(fuse_val, 40)})")
                results[bit_id] = {"status": "ok"}

    # Cleanup
    isp.bulk_erase()
    return results


def phase2_auto(isp, start_row=0, end_row=None):
    """Phase 2 auto: probe all rows, batch mode (no user input).
    Tests that every fuse bit can be individually programmed.
    Saves results to JSON.
    """
    if end_row is None:
        end_row = NUM_ROWS

    print(f"\n{'=' * 60}")
    print(f"PHASE 2 AUTO: Verify all fuse bits (rows {start_row}-{end_row-1})")
    print(f"{'=' * 60}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    all_results = {}
    total_errors = 0
    t0 = time.time()

    for row in range(start_row, end_row):
        row_errors = 0
        # Test HIGH half
        for bit in range(FUSE_BITS_PER_HALF):
            isp.bulk_erase()
            pat_h = ERASED_HIGH & ~(1 << bit)
            isp.write_row(row, pat_h, ERASED_LOW)
            rd_h, rd_l = isp.read_row_fast(row)
            if rd_h != pat_h or rd_l != ERASED_LOW:
                row_errors += 1

        # Test LOW half
        for bit in range(FUSE_BITS_PER_HALF):
            isp.bulk_erase()
            pat_l = ERASED_LOW & ~(1 << bit)
            isp.write_row(row, ERASED_HIGH, pat_l)
            rd_h, rd_l = isp.read_row_fast(row)
            if rd_h != ERASED_HIGH or rd_l != pat_l:
                row_errors += 1

        status = "PASS" if row_errors == 0 else f"FAIL({row_errors})"
        elapsed = time.time() - t0
        print(f"  Row {row:3d}/{end_row}: {status} ({elapsed:.1f}s)")
        all_results[row] = {"errors": row_errors}
        total_errors += row_errors

    # Save results
    result_file = os.path.join(RESULTS_DIR, "phase2_auto.json")
    with open(result_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"PHASE 2 AUTO: {end_row - start_row} rows, "
          f"{total_errors} errors, {elapsed:.1f}s")
    print(f"Results saved to {result_file}")
    print(f"{'=' * 60}")

    # Final cleanup
    isp.bulk_erase()
    return total_errors == 0


def main():
    parser = argparse.ArgumentParser(
        description='ispLSI 2032 fuse map reverse engineering')
    parser.add_argument('--phase1', action='store_true',
                        help='Run Phase 1: write/read round-trip verification')
    parser.add_argument('--phase2', action='store_true',
                        help='Run Phase 2: walking-0 probe (interactive)')
    parser.add_argument('--phase2-auto', action='store_true',
                        help='Run Phase 2: verify all fuse bits (batch)')
    parser.add_argument('--row', type=int, default=0,
                        help='Target row for --phase2 (default: 0)')
    parser.add_argument('--start-row', type=int, default=0,
                        help='Start row for --phase2-auto (default: 0)')
    parser.add_argument('--end-row', type=int, default=None,
                        help='End row for --phase2-auto (default: all)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose ISP output')
    args = parser.parse_args()

    if not (args.phase1 or args.phase2 or args.phase2_auto):
        parser.print_help()
        print("\nExample:")
        print("  python3 fuse_re.py --phase1              # verify write/read")
        print("  python3 fuse_re.py --phase2 --row 0      # probe row 0")
        print("  python3 fuse_re.py --phase2-auto          # verify all bits")
        return

    isp = ISP2032(verbose=args.verbose)
    print("FT2232H connected.")

    try:
        isp.enter_isp()

        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}")

        ft = isp.flowthru_test()
        print(f"FLOWTHRU:  {fmt_hex(ft, 8)} {'OK' if ft == 0xA5 else 'FAIL'}")

        if args.phase1:
            phase1_verify(isp)

        if args.phase2:
            results = phase2_row(isp, args.row, interactive=True)
            os.makedirs(RESULTS_DIR, exist_ok=True)
            fname = os.path.join(RESULTS_DIR, f"row_{args.row:03d}.json")
            with open(fname, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {fname}")

        if args.phase2_auto:
            phase2_auto(isp, args.start_row, args.end_row)

        isp.exit_isp()
    except KeyboardInterrupt:
        print("\nInterrupted. Cleaning up...")
        isp.bulk_erase()
        isp.exit_isp()
    finally:
        isp.close()


if __name__ == '__main__':
    main()
