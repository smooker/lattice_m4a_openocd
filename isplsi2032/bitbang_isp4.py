#!/usr/bin/env python3
"""
Bit-bang ISP probe v4 — try MODE=1 for commands.

Hypothesis: MODE selects which register is connected to SDI/SDO:
  MODE=1: command/instruction register
  MODE=0: data register
No MODE "pulse" needed — just hold MODE at the right level.
"""

import sys
import time
from pyftdi.ftdi import Ftdi

FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000

SCLK  = 0x01
SDI   = 0x02
SDO   = 0x04
MODE  = 0x08
nSRST = 0x10
ispEN = 0x20
DIR   = SCLK | SDI | MODE | nSRST | ispEN


class ISP:
    def __init__(self):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST | ispEN)
        self._set(nSRST | ispEN)

    def close(self):
        self.ftdi.close()

    def _set(self, val):
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
        self._set(ispEN)
        time.sleep(0.05)
        self._set(nSRST | ispEN)
        time.sleep(0.05)
        self._set(nSRST)
        time.sleep(0.02)


def fmt(val, bits):
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"


def main():
    print("ispLSI 2032 — ISP Probe v4 (MODE=1 commands)")
    print("=" * 60)

    isp = ISP()
    print("Connected.\n")

    try:
        # === TEST 1: MODE=1 shift — what comes out? ===
        print("=" * 60)
        print("TEST 1: Read with MODE=1 after fresh ISP entry")
        print("=" * 60)

        isp.reset_enter()
        data_m1 = isp.shift(0, 8, mode=1)
        data_m0 = isp.shift(0, 8, mode=0)
        print(f"  MODE=1 read: {fmt(data_m1, 8)}")
        print(f"  MODE=0 read: {fmt(data_m0, 8)}")

        isp.reset_enter()
        data_m1_32 = isp.shift(0, 32, mode=1)
        data_m0_32 = isp.shift(0, 32, mode=0)
        print(f"  MODE=1 32-bit: {fmt(data_m1_32, 32)}")
        print(f"  MODE=0 32-bit: {fmt(data_m0_32, 32)}")

        # === TEST 2: Shift cmd with MODE=1, then read with MODE=0 ===
        print("\n" + "=" * 60)
        print("TEST 2: 8-bit cmd (MODE=1) -> 8-bit read (MODE=0)")
        print("  All 256 opcodes")
        print("=" * 60)

        results = {}
        for cmd in range(256):
            isp.reset_enter()
            isp.shift(cmd, 8, mode=1)
            resp = isp.shift(0, 8, mode=0)
            if resp not in results:
                results[resp] = []
            results[resp].append(cmd)

        for resp_val, cmds in sorted(results.items()):
            if len(cmds) <= 10:
                cmd_str = ", ".join(fmt(c, 8) for c in cmds)
            else:
                cmd_str = f"{len(cmds)} opcodes"
            print(f"  Response {fmt(resp_val, 8)}: [{cmd_str}]")

        # === TEST 3: Cmd MODE=1, read 32 bits MODE=0 ===
        print("\n" + "=" * 60)
        print("TEST 3: 8-bit cmd (MODE=1) -> 32-bit read (MODE=0)")
        print("=" * 60)

        found_different = False
        for cmd in range(256):
            isp.reset_enter()
            isp.shift(cmd, 8, mode=1)
            resp = isp.shift(0, 32, mode=0)
            if resp != 0x00000000 and resp != 0x000000FF:
                print(f"  CMD={fmt(cmd,8)}: {fmt(resp,32)} ***")
                found_different = True

        if not found_different:
            # Show what the common value is
            isp.reset_enter()
            isp.shift(0x0A, 8, mode=1)
            resp = isp.shift(0, 32, mode=0)
            print(f"  All same: {fmt(resp,32)}")

        # === TEST 4: Different bit widths for command ===
        print("\n" + "=" * 60)
        print("TEST 4: Vary command width (MODE=1) -> 32-bit read (MODE=0)")
        print("=" * 60)

        for cmd_bits in [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16]:
            isp.reset_enter()
            # Send ISC_READ-like command
            isp.shift(0x0A, cmd_bits, mode=1)
            resp = isp.shift(0, 32, mode=0)
            print(f"  {cmd_bits:2d}-bit cmd 0x0A: read={fmt(resp,32)}")

        # === TEST 5: MODE=1 cmd, MODE pulse, MODE=0 read ===
        print("\n" + "=" * 60)
        print("TEST 5: CMD(MODE=1) -> 1 MODE transition -> read(MODE=0)")
        print("  (combined: command via MODE=1, then single 1->0 transition)")
        print("=" * 60)

        for cmd in [0x00, 0x01, 0x02, 0x03, 0x0A, 0x15, 0x1E, 0x1F,
                    0x55, 0x68, 0x80, 0xAA, 0xC0, 0xFF]:
            isp.reset_enter()
            isp.shift(cmd, 8, mode=1)
            # MODE transitions: 1->0 happens naturally when we start MODE=0 read
            resp = isp.shift(0, 32, mode=0)
            # Also try: extra MODE=1 clock after command
            isp.reset_enter()
            isp.shift(cmd, 8, mode=1)
            isp.clk(0, 1)  # extra MODE=1 clock
            resp2 = isp.shift(0, 32, mode=0)
            print(f"  CMD={fmt(cmd,8)}: direct={fmt(resp,32)} +1clk={fmt(resp2,32)}")

        # === TEST 6: Interleaved MODE ===
        print("\n" + "=" * 60)
        print("TEST 6: Alternate MODE per bit (like JTAG state machine)")
        print("  Maybe: odd bits = command, even bits = 0?")
        print("=" * 60)

        isp.reset_enter()
        # Try: clock 16 bits alternating MODE=1/0
        result = 0
        for i in range(16):
            sdo = isp.clk(0, i % 2)
            result |= (sdo << i)
        print(f"  16 bits alternating MODE: {fmt(result, 16)}")

        isp.reset_enter()
        # JTAG-like: MODE=1,0,0 (enter shift), shift 8 bits MODE=0, MODE=1 (exit)
        isp.clk(0, 1)
        isp.clk(0, 0)
        isp.clk(0, 0)
        data = isp.shift(0, 8, mode=0)
        isp.clk(0, 1)
        print(f"  JTAG-like (1,0,0,shift8,1): {fmt(data, 8)}")

        # === TEST 7: Raw SDO observation with MODE transitions ===
        print("\n" + "=" * 60)
        print("TEST 7: SDO state during MODE transitions")
        print("=" * 60)

        isp.reset_enter()
        print("  Clocking with SDI=0, observing SDO:")
        for i in range(32):
            # Alternate: 4 clocks MODE=0, 4 clocks MODE=1
            mode_val = (i // 4) % 2
            sdo = isp.clk(0, mode_val)
            print(f"    clk{i:2d}: MODE={mode_val} SDO={sdo}")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE")
        print("=" * 60)

    finally:
        isp.close()


if __name__ == '__main__':
    main()
