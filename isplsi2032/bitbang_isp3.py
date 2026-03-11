#!/usr/bin/env python3
"""
Bit-bang ISP probe v3 — focused on patent-based protocol.

Protocol (from US5412260A):
  1. Shift command/data with MODE=0 (data phase)
  2. Pulse MODE=1 (process/execute)
  3. Shift response with MODE=0 (read result)

ispEN on ADBUS5 — proper HIGH->LOW entry sequence.
"""

import sys
import time
from pyftdi.ftdi import Ftdi

FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000

# ADBUS pins
SCLK  = 0x01
SDI   = 0x02
SDO   = 0x04  # input
MODE  = 0x08
nSRST = 0x10
ispEN = 0x20  # active LOW
DIR   = SCLK | SDI | MODE | nSRST | ispEN  # 0x3B


class ISP:
    def __init__(self):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST | ispEN)
        self.state = nSRST | ispEN
        self._set(self.state)

    def close(self):
        self.ftdi.close()

    def _set(self, val):
        self.state = val
        self.ftdi.write_data(bytes([0x80, val & 0xFF, DIR]))

    def _read(self):
        self.ftdi.write_data(bytes([0x81]))
        d = self.ftdi.read_data_bytes(1, attempt=10)
        return d[0] if d else 0

    def clk(self, sdi, mode):
        val = nSRST
        if sdi:  val |= SDI
        if mode: val |= MODE
        self._set(val)
        self._set(val | SCLK)
        pins = self._read()
        sdo = 1 if (pins & SDO) else 0
        self._set(val)
        return sdo

    def shift(self, data, nbits, mode):
        r = 0
        for i in range(nbits):
            sdo = self.clk((data >> i) & 1, mode)
            r |= (sdo << i)
        return r

    def reset_enter(self):
        """Full reset + ISP entry."""
        self._set(ispEN)           # ispEN=HIGH, nSRST=LOW
        time.sleep(0.05)
        self._set(nSRST | ispEN)   # release reset, ispEN still HIGH
        time.sleep(0.05)
        self._set(nSRST)           # ispEN LOW = enter ISP
        time.sleep(0.02)

    def mode_pulse(self, n=1):
        """Pulse MODE=1 for n clocks."""
        for _ in range(n):
            self.clk(0, 1)

    def isp_cmd(self, cmd, cmd_bits=8, read_bits=8, mode_pulses=1):
        """
        Send ISP command and read response.
        1. Shift cmd (MODE=0)
        2. Pulse MODE=1 (process)
        3. Read response (MODE=0)
        """
        self.shift(cmd, cmd_bits, mode=0)
        self.mode_pulse(mode_pulses)
        return self.shift(0, read_bits, mode=0)


def fmt(val, bits):
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"


def main():
    print("ispLSI 2032 — Patent-Based ISP Probe v3")
    print("=" * 60)

    isp = ISP()
    print("Connected.\n")

    try:
        # === TEST 1: Basic ISP entry ===
        print("=" * 60)
        print("TEST 1: ISP entry + basic read")
        print("=" * 60)

        isp.reset_enter()

        # Just read 8 bits to see what's there
        data = isp.shift(0, 8, mode=0)
        print(f"  Immediate read after ISP entry: {fmt(data, 8)}")

        # Shift A5, read back
        isp.shift(0xA5, 8, mode=0)
        rb = isp.shift(0, 8, mode=0)
        print(f"  Shift 0xA5, readback: {fmt(rb, 8)}")

        # === TEST 2: All 256 commands, 1 MODE pulse, 8-bit response ===
        print("\n" + "=" * 60)
        print("TEST 2: 8-bit cmd + 1 MODE pulse + 8-bit read")
        print("  (showing ALL results)")
        print("=" * 60)

        results = {}
        for cmd in range(256):
            isp.reset_enter()
            resp = isp.isp_cmd(cmd, cmd_bits=8, read_bits=8, mode_pulses=1)
            key = resp
            if key not in results:
                results[key] = []
            results[key].append(cmd)

        for resp_val, cmds in sorted(results.items()):
            if len(cmds) <= 8:
                cmd_str = ", ".join(fmt(c, 8) for c in cmds)
            else:
                cmd_str = f"{len(cmds)} opcodes: {fmt(cmds[0],8)}..{fmt(cmds[-1],8)}"
            print(f"  Response {fmt(resp_val, 8)}: [{cmd_str}]")

        # === TEST 3: Interesting commands with longer reads ===
        print("\n" + "=" * 60)
        print("TEST 3: Selected cmds + 1 MODE pulse + 32-bit read")
        print("=" * 60)

        for cmd in range(256):
            isp.reset_enter()
            resp = isp.isp_cmd(cmd, cmd_bits=8, read_bits=32, mode_pulses=1)
            if resp != 0x00000000:
                print(f"  CMD={fmt(cmd,8)}: {fmt(resp,32)} ***")

        print("  (only non-zero shown)")

        # === TEST 4: Vary MODE pulse count ===
        print("\n" + "=" * 60)
        print("TEST 4: CMD=0x0A (ISC_READ), vary MODE pulses, 32-bit read")
        print("=" * 60)

        for pulses in range(1, 17):
            isp.reset_enter()
            resp = isp.isp_cmd(0x0A, cmd_bits=8, read_bits=32, mode_pulses=pulses)
            print(f"  {pulses:2d} MODE pulses: {fmt(resp, 32)}")

        # === TEST 5: Multi-step — command, pulse, data, pulse, read ===
        print("\n" + "=" * 60)
        print("TEST 5: Two-phase: cmd + pulse + address + pulse + read")
        print("  (ISP devices often need: cmd -> address -> data)")
        print("=" * 60)

        for cmd in [0x00, 0x01, 0x02, 0x03, 0x0A, 0x0B, 0x0F,
                    0x10, 0x15, 0x1E, 0x1F, 0x55, 0x68, 0x6A,
                    0x80, 0xAA, 0xC0, 0xE0, 0xFE, 0xFF]:
            isp.reset_enter()
            # Phase 1: command
            isp.shift(cmd, 8, mode=0)
            isp.mode_pulse(1)
            # Phase 2: address = 0 (first row)
            isp.shift(0, 8, mode=0)
            isp.mode_pulse(1)
            # Phase 3: read data
            data = isp.shift(0, 32, mode=0)
            print(f"  CMD={fmt(cmd,8)}: phase3_read={fmt(data,32)}")

        # === TEST 6: Long reads after various commands ===
        print("\n" + "=" * 60)
        print("TEST 6: CMD + pulse + 128-bit read (looking for fuse data)")
        print("=" * 60)

        for cmd in [0x00, 0x0A, 0x15, 0x55, 0x68, 0x6A, 0x80, 0xFF]:
            isp.reset_enter()
            isp.shift(cmd, 8, mode=0)
            isp.mode_pulse(1)
            data = isp.shift(0, 128, mode=0)
            if data != 0:
                print(f"  CMD={fmt(cmd,8)}: {fmt(data,128)} ***")
            else:
                print(f"  CMD={fmt(cmd,8)}: all zeros")

        # === TEST 7: Try without reset between commands ===
        print("\n" + "=" * 60)
        print("TEST 7: Sequence without reset — cmd chain")
        print("=" * 60)

        isp.reset_enter()

        # ISP flow might be: enable -> address -> read
        # Try: 0x15 (ISC_ENABLE) -> pulse -> 0x01 (ADDR) -> pulse -> 0x0A (READ) -> pulse -> read
        for label, cmd in [("ISC_ENABLE", 0x15), ("ADDR_SHIFT", 0x01),
                            ("READ", 0x0A)]:
            isp.shift(cmd, 8, mode=0)
            isp.mode_pulse(1)
            data = isp.shift(0, 8, mode=0)
            print(f"  {label:12s} ({fmt(cmd,8)}): read={fmt(data,8)}")

        print("\n  --- Try ISC_ENABLE -> read 32 bits ---")
        isp.reset_enter()
        isp.shift(0x15, 8, mode=0)
        isp.mode_pulse(1)
        data = isp.shift(0, 32, mode=0)
        print(f"  After ISC_ENABLE: {fmt(data,32)}")

        # Try another sequence
        print("\n  --- Try ENABLE -> ADDR(0) -> pulse -> read 80 bits ---")
        isp.reset_enter()
        # Enable
        isp.shift(0x15, 8, mode=0)
        isp.mode_pulse(1)
        # Address row 0
        isp.shift(0x00, 8, mode=0)
        isp.mode_pulse(1)
        # Read
        data = isp.shift(0, 80, mode=0)
        print(f"  80-bit read: {fmt(data,80)}")

        # Try the V/VE ISC flow adapted for 8-bit IR
        print("\n  --- V/VE ISC flow (adapted for 8-bit) ---")
        isp.reset_enter()
        # ISC_ENABLE with config
        isp.shift(0x15, 8, mode=0)
        isp.mode_pulse(1)
        isp.shift(0x08, 8, mode=0)  # config byte
        isp.mode_pulse(1)
        # ADDRESS_SHIFT - row 0
        isp.shift(0x01, 8, mode=0)
        isp.mode_pulse(1)
        isp.shift(0x01, 8, mode=0)  # walking-1 address: row 0
        isp.mode_pulse(1)
        # READ
        isp.shift(0x0A, 8, mode=0)
        isp.mode_pulse(1)
        # Read fuse data
        data = isp.shift(0, 80, mode=0)
        print(f"  80-bit fuse data: {fmt(data,80)}")

        data = isp.shift(0, 80, mode=0)
        print(f"  next 80 bits:     {fmt(data,80)}")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE")
        print("=" * 60)

    finally:
        isp.close()


if __name__ == '__main__':
    main()
