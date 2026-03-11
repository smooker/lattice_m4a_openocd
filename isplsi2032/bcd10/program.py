#!/usr/bin/env python3
"""
program.py — Erase, program, and verify ispLSI 2032 from .fuse file.

Usage:
  python3 program.py input.fuse

Steps:
  1. Read device ID (expect 0x15)
  2. Bulk erase (UBE)
  3. Program rows that differ from erased state (skip all-1s rows)
  4. Verify all programmed rows by read-back

.fuse format: 102 rows x 10 bytes (5B high + 5B low), total 1020 bytes.

Run on HOST (not chroot):
  sudo rmmod ftdi_sio
  python3 program.py input.fuse
"""

import argparse
import sys
import time
from isp import (ISP2032, NUM_ROWS, DATA_SR_HIGH, DATA_SR_LOW,
                 ERASED_HIGH, ERASED_LOW, fmt_hex)

EXPECTED_ID = 0x15
FUSE_FILE_SIZE = NUM_ROWS * 10  # 102 * 10 = 1020 bytes


def load_fuse_file(filename):
    """Load .fuse binary file. Returns list of 102 (high, low) tuples."""
    with open(filename, 'rb') as f:
        data = f.read()

    if len(data) != FUSE_FILE_SIZE:
        raise ValueError(
            f"Invalid .fuse file: expected {FUSE_FILE_SIZE} bytes, "
            f"got {len(data)}")

    rows = []
    for r in range(NUM_ROWS):
        offset = r * 10
        h = int.from_bytes(data[offset:offset+5], byteorder='big')
        l = int.from_bytes(data[offset+5:offset+10], byteorder='big')
        rows.append((h, l))
    return rows


def main():
    parser = argparse.ArgumentParser(
        description='Program ispLSI 2032 from .fuse file')
    parser.add_argument('fusefile', help='Input .fuse file (1020 bytes)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose ISP output')
    parser.add_argument('--no-verify', action='store_true',
                        help='Skip verification step')
    parser.add_argument('--no-erase', action='store_true',
                        help='Skip erase (assume chip is already erased)')
    args = parser.parse_args()

    # Load fuse file
    print("=" * 60)
    print("ispLSI 2032 — Programmer")
    print("=" * 60)

    print(f"\nLoading: {args.fusefile}")
    rows = load_fuse_file(args.fusefile)

    # Count rows to program
    to_program = []
    for r, (h, l) in enumerate(rows):
        if h != ERASED_HIGH or l != ERASED_LOW:
            to_program.append(r)

    print(f"Total rows: {NUM_ROWS}")
    print(f"Rows to program: {len(to_program)} "
          f"(skipping {NUM_ROWS - len(to_program)} erased rows)")

    if not to_program:
        print("\nNothing to program — fuse file is all erased.")
        return

    # Connect
    isp = ISP2032(verbose=args.verbose)
    print("\nFT2232H connected.")

    try:
        isp.enter_isp()

        # Step 1: Read device ID
        dev_id = isp.get_id()
        print(f"\nDevice ID: {fmt_hex(dev_id, 8)}", end="")
        if dev_id == EXPECTED_ID:
            print(" (ispLSI 2032 confirmed)")
        else:
            print(f" WARNING: expected 0x{EXPECTED_ID:02X}")
            ans = input("Continue anyway? [y/N] ").strip().lower()
            if ans != 'y':
                print("Aborted.")
                return

        # Step 2: Bulk erase
        if not args.no_erase:
            print("\nErasing chip (UBE)...", end="", flush=True)
            t0 = time.time()
            isp.bulk_erase()
            print(f" done ({time.time()-t0:.1f}s)")
        else:
            print("\nSkipping erase (--no-erase)")

        # Step 3: Program
        print(f"\nProgramming {len(to_program)} rows...")
        t0 = time.time()
        for i, r in enumerate(to_program):
            h, l = rows[r]
            isp.write_row(r, h, l)
            if (i + 1) % 5 == 0 or i == len(to_program) - 1:
                elapsed = time.time() - t0
                print(f"  {i+1:3d}/{len(to_program)} rows "
                      f"({elapsed:.1f}s)", end="\r")

        elapsed = time.time() - t0
        print(f"\nProgramming done in {elapsed:.1f}s")

        # Step 4: Verify
        if not args.no_verify:
            print(f"\nVerifying {len(to_program)} rows...")
            t0 = time.time()
            errors = 0
            for i, r in enumerate(to_program):
                h, l = rows[r]
                ok = isp.verify_row(r, h, l)
                if not ok:
                    errors += 1
                    rd_h, rd_l = isp.read_row(r)
                    print(f"\n  FAIL row {r:3d}: "
                          f"exp H=0x{h:010X} L=0x{l:010X} "
                          f"got H=0x{rd_h:010X} L=0x{rd_l:010X}")
                if (i + 1) % 10 == 0 or i == len(to_program) - 1:
                    elapsed = time.time() - t0
                    print(f"  {i+1:3d}/{len(to_program)} rows "
                          f"({elapsed:.1f}s)", end="\r")

            elapsed = time.time() - t0
            print(f"\nVerification done in {elapsed:.1f}s")

            if errors == 0:
                print("\n*** ALL ROWS VERIFIED OK ***")
            else:
                print(f"\n*** {errors} ROWS FAILED VERIFICATION ***")
                sys.exit(1)
        else:
            print("\nSkipping verification (--no-verify)")

        isp.exit_isp()
        print("\nProgramming complete.")

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
    finally:
        isp.close()


if __name__ == '__main__':
    main()
