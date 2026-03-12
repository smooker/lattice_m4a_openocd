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
import io
import json
import os
import sys
import time
from isp import (ISP2032, NUM_ROWS, DATA_SR_HIGH, DATA_SR_LOW,
                 ERASED_HIGH, ERASED_LOW, FREQ, DIR, nSRST, ispEN, fmt_hex)


class TeeWriter:
    """Write to both stdout and a log file simultaneously."""
    def __init__(self, logfile):
        self.terminal = sys.__stdout__
        self.log = open(logfile, 'w')

    def write(self, msg):
        self.terminal.write(msg)
        self.log.write(msg)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()

RESULTS_DIR = "re_results"
FUSE_BITS_PER_HALF = 38  # top 2 of 40 bits are always 0


def scan_all_rows(isp):
    """Scan all 102 rows with pattern 0x0000000001 (nearly all programmed).
    Single bulk erase, then write+read each row sequentially.
    No erase between rows — fuses only go 1→0, and we're programming almost all to 0.

    Identifies which rows have stuck-at-1 bits (non-programmable positions).
    Groups of failing rows likely correspond to GRP/GLB/ARCH fuse map sections.
    """
    pat_h, pat_l = 0x0000000001, 0x0000000001

    print("=" * 60)
    print("SCAN: All 102 rows with pattern 0x0000000001")
    print("=" * 60)
    print("  One bulk erase, then write+read each row.")
    print("  Failing bits = non-programmable (architecture/config).")
    print()

    isp.bulk_erase()

    fail_rows = []
    pass_count = 0

    for row in range(NUM_ROWS):
        isp.write_row(row, pat_h, pat_l)
        rd_h, rd_l = isp.read_row_fast(row)

        if rd_h == pat_h and rd_l == pat_l:
            pass_count += 1
        else:
            xor_h = pat_h ^ rd_h
            xor_l = pat_l ^ rd_l
            stuck_bits_h = []
            stuck_bits_l = []
            for b in range(40):
                if xor_h & (1 << b):
                    stuck_bits_h.append(b)
                if xor_l & (1 << b):
                    stuck_bits_l.append(b)

            print(f"  Row {row:3d}: FAIL")
            print(f"    read H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)}")
            print(f"    XOR  H={fmt_hex(xor_h,40)} L={fmt_hex(xor_l,40)}")
            if stuck_bits_h:
                print(f"    stuck H bits: {stuck_bits_h}")
            if stuck_bits_l:
                print(f"    stuck L bits: {stuck_bits_l}")
            fail_rows.append({
                "row": row,
                "rd_h": rd_h, "rd_l": rd_l,
                "xor_h": xor_h, "xor_l": xor_l,
                "stuck_h": stuck_bits_h, "stuck_l": stuck_bits_l,
            })

    # Cleanup
    isp.bulk_erase()

    # Summary
    print()
    print("=" * 60)
    print(f"SCAN COMPLETE: {pass_count} PASS, {len(fail_rows)} FAIL out of {NUM_ROWS}")
    print("=" * 60)

    if fail_rows:
        print(f"\nFailing rows: {[f['row'] for f in fail_rows]}")

        # Look for patterns in failing row numbers
        if len(fail_rows) >= 2:
            rows_list = [f['row'] for f in fail_rows]
            diffs = [rows_list[i+1] - rows_list[i] for i in range(len(rows_list)-1)]
            print(f"Row gaps:     {diffs}")

        # Collect all unique stuck bit positions
        all_stuck_h = set()
        all_stuck_l = set()
        for f in fail_rows:
            all_stuck_h.update(f['stuck_h'])
            all_stuck_l.update(f['stuck_l'])
        if all_stuck_h:
            print(f"All stuck H positions: {sorted(all_stuck_h)}")
        if all_stuck_l:
            print(f"All stuck L positions: {sorted(all_stuck_l)}")

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    result_file = os.path.join(RESULTS_DIR, "scan_all_rows.json")
    # Convert for JSON serialization
    save_data = []
    for f in fail_rows:
        save_data.append({
            "row": f["row"],
            "rd_h": f"0x{f['rd_h']:010X}",
            "rd_l": f"0x{f['rd_l']:010X}",
            "stuck_h": f["stuck_h"],
            "stuck_l": f["stuck_l"],
        })
    with open(result_file, 'w') as fp:
        json.dump({"pass": pass_count, "fail": len(fail_rows),
                    "total": NUM_ROWS, "failures": save_data}, fp, indent=2)
    print(f"\nResults saved to {result_file}")


def diag_row_isolate(isp):
    """Diagnostic: is the row 2 failure caused by the row itself or by prior writes?

    Test A: write 0x0000000001 to rows 0-5 individually (fresh erase each time, no prior writes)
    Test B: write rows 0,1 with alternating patterns, then write row 2 with 0x0000000001
            (reproduces the phase1 sequence)
    """
    pat_h, pat_l = 0x0000000001, 0x0000000001

    print("=" * 60)
    print("DIAGNOSTIC: Row isolation — row 2 failure analysis")
    print("=" * 60)

    # Test A: each row individually, clean erase, no prior writes
    print("\n--- Test A: single-bit-low on rows 0-5 (isolated, fresh erase each) ---")
    for row in range(6):
        isp.bulk_erase()
        isp.write_row(row, pat_h, pat_l)
        rd_h, rd_l = isp.read_row_fast(row)
        match = (rd_h == pat_h and rd_l == pat_l)
        print(f"  Row {row}: {'PASS' if match else 'FAIL'}", end="")
        if not match:
            print(f"  read H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)}")
        else:
            print()

    # Test B: reproduce phase1 sequence (rows 0,1 then row 2)
    print("\n--- Test B: phase1 sequence (row0 alt, erase, row1 alt, erase, row2 single-bit) ---")
    # Row 0: alternating
    isp.bulk_erase()
    isp.write_row(0, 0x2AAAAAAAAA, 0x1555555555)
    rd_h, rd_l = isp.read_row_fast(0)
    match = (rd_h == 0x2AAAAAAAAA and rd_l == 0x1555555555)
    print(f"  Row 0 alternating 10/01: {'PASS' if match else 'FAIL'}")

    # Row 1: alternating (inverse)
    isp.bulk_erase()
    isp.write_row(1, 0x1555555555, 0x2AAAAAAAAA)
    rd_h, rd_l = isp.read_row_fast(1)
    match = (rd_h == 0x1555555555 and rd_l == 0x2AAAAAAAAA)
    print(f"  Row 1 alternating 01/10: {'PASS' if match else 'FAIL'}")

    # Row 2: single bit low (the failing one)
    isp.bulk_erase()
    isp.write_row(2, pat_h, pat_l)
    rd_h, rd_l = isp.read_row_fast(2)
    match = (rd_h == pat_h and rd_l == pat_l)
    print(f"  Row 2 single-bit-low:    {'PASS' if match else 'FAIL'}", end="")
    if not match:
        print(f"  read H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)}")
    else:
        print()

    # Test C: write row 2 WITHOUT erasing after row 1 write
    print("\n--- Test C: row0 alt + row1 alt (NO erase between) then erase + row2 ---")
    isp.bulk_erase()
    isp.write_row(0, 0x2AAAAAAAAA, 0x1555555555)
    isp.write_row(1, 0x1555555555, 0x2AAAAAAAAA)
    # Now erase and write row 2
    isp.bulk_erase()
    isp.write_row(2, pat_h, pat_l)
    rd_h, rd_l = isp.read_row_fast(2)
    match = (rd_h == pat_h and rd_l == pat_l)
    print(f"  Row 2 single-bit-low:    {'PASS' if match else 'FAIL'}", end="")
    if not match:
        print(f"  read H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)}")
    else:
        print()

    # Cleanup
    isp.bulk_erase()
    print()
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


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


def diag_speed(isp, row=0):
    """Diagnostic: run the failing 'single bit low' pattern at different speeds.
    Tests whether the phase1 row 2 failure is speed-related (long wires, no decoupling).
    """
    print("=" * 60)
    print(f"DIAGNOSTIC: Speed sensitivity test (row {row})")
    print("=" * 60)
    print(f"  Current MPSSE freq: {FREQ} Hz")
    print(f"  Pattern: H=0x0000000001 L=0x0000000001 (nearly all programmed)")
    print()

    # The failing pattern from phase1
    pat_h, pat_l = 0x0000000001, 0x0000000001

    # Also test the dense alternating pattern as control
    patterns = [
        (pat_h, pat_l, "single bit low (FAILED in phase1)"),
        (0x2AAAAAAAAA, 0x1555555555, "alternating 10/01 (control)"),
        (0x0000000000, 0x0000000000, "all programmed"),
        (0x00000000FF, 0x00000000FF, "low byte set"),
    ]

    freqs = [100000, 50000, 20000, 10000, 5000]

    for freq in freqs:
        print(f"--- {freq/1000:.0f} kHz ---")
        # Reinit MPSSE at new frequency
        isp.ftdi.close()
        isp.ftdi.open_mpsse_from_url('ftdi://ftdi:2232h/1', frequency=freq,
                                      direction=DIR, initial=nSRST | ispEN)
        isp._pins(nSRST)  # re-enter ISP-ready state (ispEN low)
        time.sleep(0.01)
        isp.enter_isp()

        # Verify chip is alive
        dev_id = isp.get_id()
        if dev_id != 0x15:
            print(f"  ID FAIL: got {fmt_hex(dev_id, 8)}, skipping")
            continue

        for pat_h_t, pat_l_t, desc in patterns:
            isp.bulk_erase()
            isp.write_row(row, pat_h_t, pat_l_t)
            rd_h, rd_l = isp.read_row_fast(row)

            match = (rd_h == pat_h_t and rd_l == pat_l_t)
            status = "PASS" if match else "FAIL"
            print(f"  {desc}")
            print(f"    wrote H={fmt_hex(pat_h_t,40)} L={fmt_hex(pat_l_t,40)}")
            print(f"    read  H={fmt_hex(rd_h,40)} L={fmt_hex(rd_l,40)}  {status}")
            if not match:
                print(f"    XOR_H={fmt_hex(pat_h_t ^ rd_h, 40)} XOR_L={fmt_hex(pat_l_t ^ rd_l, 40)}")

        print()

    # Restore original speed
    isp.ftdi.close()
    isp.ftdi.open_mpsse_from_url('ftdi://ftdi:2232h/1', frequency=FREQ,
                                  direction=DIR, initial=nSRST | ispEN)
    isp._pins(nSRST)
    time.sleep(0.01)
    isp.enter_isp()

    isp.bulk_erase()
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


def diag_bit_boundary(isp, row=0):
    """Diagnostic: write single-bit patterns at positions 0-5 on both halves.
    Determines which bit positions are real fuses vs I0/I1 input pin positions.
    Tests the <<2 alignment hypothesis.
    """
    print("=" * 60)
    print(f"DIAGNOSTIC: Single-bit boundary probe (row {row})")
    print("=" * 60)
    print(f"  Testing bits 0-5 on HIGH and LOW halves.")
    print(f"  write_row() applies <<2 shift internally.")
    print(f"  Erased state = 0x3FFFFFFFFF (bits 37..0 = 1, bits 39..38 = 0)")
    print()

    for half_name in ("HIGH", "LOW"):
        print(f"--- {half_name} half ---")
        for bit in range(6):
            isp.bulk_erase()
            val = 1 << bit  # single bit set (rest = 0 = programmed)

            if half_name == "HIGH":
                isp.write_row(row, val, ERASED_LOW)
                rd_h, rd_l = isp.read_row_fast(row)
                wrote, got = val, rd_h
                other_ok = (rd_l == ERASED_LOW)
            else:
                isp.write_row(row, ERASED_HIGH, val)
                rd_h, rd_l = isp.read_row_fast(row)
                wrote, got = val, rd_l
                other_ok = (rd_h == ERASED_HIGH)

            match = (wrote == got)
            print(f"  bit {bit}: wrote {fmt_hex(wrote,40)}  "
                  f"read {fmt_hex(got,40)}  "
                  f"{'PASS' if match else 'FAIL'}  "
                  f"other_half={'OK' if other_ok else 'DIRTY'}")

            if not match:
                # Show binary diff
                xor = wrote ^ got
                print(f"         XOR = {fmt_hex(xor,40)} = 0b{xor:040b}")
                print(f"         got = 0b{got:040b}")

        print()

    # Also test walking-0 on bits 0-5 (erased = all 1, clear one bit)
    print("--- Walking-0 (clear single bit from erased) on HIGH ---")
    for bit in range(6):
        isp.bulk_erase()
        val = ERASED_HIGH & ~(1 << bit)  # clear one bit

        isp.write_row(row, val, ERASED_LOW)
        rd_h, rd_l = isp.read_row_fast(row)

        match = (rd_h == val)
        print(f"  clear bit {bit}: wrote {fmt_hex(val,40)}  "
              f"read {fmt_hex(rd_h,40)}  "
              f"{'PASS' if match else 'FAIL'}")
        if not match:
            xor = val ^ rd_h
            print(f"         XOR = {fmt_hex(xor,40)}")

    # Cleanup
    isp.bulk_erase()
    print()
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


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
    parser.add_argument('--diag-bits', action='store_true',
                        help='Diagnostic: probe bit positions 0-5 to find fuse boundary')
    parser.add_argument('--diag-speed', action='store_true',
                        help='Diagnostic: test failing pattern at 100/50/20/10/5 kHz')
    parser.add_argument('--diag-row', action='store_true',
                        help='Diagnostic: isolate row 2 failure (row vs sequence)')
    parser.add_argument('--scan', action='store_true',
                        help='Scan all 102 rows for stuck bits (1 erase + 102 writes)')
    parser.add_argument('--row', type=int, default=0,
                        help='Target row for --phase2 (default: 0)')
    parser.add_argument('--start-row', type=int, default=0,
                        help='Start row for --phase2-auto (default: 0)')
    parser.add_argument('--end-row', type=int, default=None,
                        help='End row for --phase2-auto (default: all)')
    parser.add_argument('--freq', type=int, default=None,
                        help='Override MPSSE clock frequency in Hz (default: 100000)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose ISP output')
    args = parser.parse_args()

    if not (args.phase1 or args.phase2 or args.phase2_auto or args.diag_bits or args.diag_speed or args.diag_row or args.scan):
        parser.print_help()
        print("\nExample:")
        print("  python3 fuse_re.py --phase1              # verify write/read")
        print("  python3 fuse_re.py --phase2 --row 0      # probe row 0")
        print("  python3 fuse_re.py --diag-bits             # probe bit boundary")
        print("  python3 fuse_re.py --phase2-auto          # verify all bits")
        return

    # Setup tee logging: screen + log file
    logfile = os.path.splitext(os.path.abspath(sys.argv[0]))[0] + '.log'
    tee = TeeWriter(logfile)
    sys.stdout = tee

    isp = ISP2032(verbose=args.verbose)
    print("FT2232H connected.")

    # Override clock frequency if requested
    if args.freq:
        isp.ftdi.close()
        isp.ftdi.open_mpsse_from_url('ftdi://ftdi:2232h/1', frequency=args.freq,
                                      direction=DIR, initial=nSRST | ispEN)
        isp._pins(nSRST)
        time.sleep(0.01)
        print(f"MPSSE clock overridden to {args.freq} Hz")

    try:
        isp.enter_isp()

        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}")

        ft = isp.flowthru_test()
        print(f"FLOWTHRU:  {fmt_hex(ft, 8)} {'OK' if ft == 0xA5 else 'FAIL'}")

        if args.scan:
            scan_all_rows(isp)

        if args.diag_row:
            diag_row_isolate(isp)

        if args.diag_speed:
            diag_speed(isp, row=args.row)

        if args.diag_bits:
            diag_bit_boundary(isp, row=args.row)

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
        sys.stdout = sys.__stdout__
        tee.close()
        print(f"Log saved to {logfile}")


if __name__ == '__main__':
    main()
