#!/usr/bin/env python3
"""
read_fuses.py — Read all 102 rows of ispLSI 2032 fuse map.

Saves output as:
  .fuse — binary (102 rows x 10 bytes = 1020 bytes)
  .txt  — human-readable hex dump

Usage:
  python3 read_fuses.py [-o output.fuse]

Run on HOST (not chroot):
  sudo rmmod ftdi_sio
  python3 read_fuses.py
"""

import argparse
import sys
import time
from isp import ISP2032, NUM_ROWS, DATA_SR_HIGH, DATA_SR_LOW, fmt_hex

EXPECTED_ID = 0x15


def rows_to_bytes(rows):
    """Convert list of (high, low) tuples to binary.
    Each row = 5 bytes HIGH (big-endian) + 5 bytes LOW (big-endian) = 10 bytes.
    Total: 102 * 10 = 1020 bytes.
    """
    buf = bytearray()
    for h, l in rows:
        buf.extend(h.to_bytes(5, byteorder='big'))
        buf.extend(l.to_bytes(5, byteorder='big'))
    return bytes(buf)


def write_txt(filename, rows):
    """Write human-readable hex dump."""
    with open(filename, 'w') as f:
        f.write(f"# ispLSI 2032 fuse dump — {NUM_ROWS} rows x 80 bits\n")
        f.write(f"# Format: ROW  HIGH_40bit  LOW_40bit\n")
        f.write(f"# Erased state = 0x3FFFFFFFFF (all 1s)\n")
        f.write(f"# Programmed fuse = 0 (makes AND connection)\n")
        f.write(f"#\n")
        for r, (h, l) in enumerate(rows):
            marker = ""
            erased_val = 0x3FFFFFFFFF
            if h != erased_val or l != erased_val:
                marker = "  *"  # Mark programmed rows
            f.write(f"{r:3d}  0x{h:010X}  0x{l:010X}{marker}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Read ispLSI 2032 fuse map via ISP')
    parser.add_argument('-o', '--output', default='dump.fuse',
                        help='Output .fuse file (default: dump.fuse)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose ISP output')
    args = parser.parse_args()

    fuse_file = args.output
    txt_file = fuse_file.rsplit('.', 1)[0] + '.txt'

    print("=" * 60)
    print("ispLSI 2032 — Fuse Map Reader")
    print("=" * 60)

    isp = ISP2032(verbose=args.verbose)
    print("FT2232H connected.")

    try:
        isp.enter_isp()

        # Read and verify device ID
        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}", end="")
        if dev_id == EXPECTED_ID:
            print(" (ispLSI 2032 confirmed)")
        else:
            print(f" WARNING: expected 0x{EXPECTED_ID:02X}")
            print("Continuing anyway...")

        # Read all rows
        print(f"\nReading {NUM_ROWS} rows...")
        t0 = time.time()
        rows = []
        erased_val = 0x3FFFFFFFFF
        programmed_count = 0

        for r in range(NUM_ROWS):
            h, l = isp.read_row(r)
            rows.append((h, l))
            if h != erased_val or l != erased_val:
                programmed_count += 1
            # Progress
            if (r + 1) % 10 == 0 or r == NUM_ROWS - 1:
                elapsed = time.time() - t0
                print(f"  Row {r+1:3d}/{NUM_ROWS} "
                      f"({elapsed:.1f}s)", end="\r")

        elapsed = time.time() - t0
        print(f"\nDone in {elapsed:.1f}s")
        print(f"Programmed rows: {programmed_count}/{NUM_ROWS}")

        isp.exit_isp()

        # Save binary .fuse file
        data = rows_to_bytes(rows)
        with open(fuse_file, 'wb') as f:
            f.write(data)
        print(f"\nBinary fuse map: {fuse_file} ({len(data)} bytes)")

        # Save text dump
        write_txt(txt_file, rows)
        print(f"Text dump:       {txt_file}")

        # Summary: show any non-erased rows
        if programmed_count > 0:
            print(f"\nProgrammed rows ({programmed_count}):")
            for r, (h, l) in enumerate(rows):
                if h != erased_val or l != erased_val:
                    print(f"  Row {r:3d}: H=0x{h:010X} L=0x{l:010X}")
        else:
            print("\nChip is fully erased (all fuses = 1).")

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise
    finally:
        isp.close()


if __name__ == '__main__':
    main()
