#!/usr/bin/env python3
"""
Bit-bang ISP probe v2 for Lattice ispLSI 2032 — Legacy ISP protocol.

Key insight: the plain 2032's ISP is NOT standard JTAG.
MODE is not TMS — it's a simple command/data select signal.

Hypothesis from Lattice patents and app notes:
  - MODE=1: command/control phase (ISP controller listens for commands)
  - MODE=0: data phase (shift register active)
  - The ISP state machine advances based on MODE transitions, not JTAG states

This script tries multiple protocol interpretations systematically.
"""

import sys
import time
from pyftdi.ftdi import Ftdi

FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000  # 100 kHz

# ADBUS pins
SCLK  = 0x01  # bit 0
SDI   = 0x02  # bit 1
SDO   = 0x04  # bit 2 (input)
MODE  = 0x08  # bit 3
nSRST = 0x10  # bit 4
ispEN = 0x20  # bit 5 — ISP enable, active LOW
DIR   = SCLK | SDI | MODE | nSRST | ispEN  # 0x3B


class ISP:
    def __init__(self):
        self.ftdi = Ftdi()
        # Start with ispEN=HIGH (ISP disabled), nSRST=HIGH (no reset)
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
        """Clock one bit. Returns SDO."""
        val = nSRST
        if sdi:  val |= SDI
        if mode: val |= MODE
        self._set(val)           # setup (SCLK=0)
        self._set(val | SCLK)    # rising edge
        pins = self._read()
        sdo = 1 if (pins & SDO) else 0
        self._set(val)           # falling edge
        return sdo

    def shift(self, data, nbits, mode):
        """Shift nbits, LSB first, MODE held. Returns SDO bits as int."""
        r = 0
        for i in range(nbits):
            sdo = self.clk((data >> i) & 1, mode)
            r |= (sdo << i)
        return r

    def isp_enter(self):
        """Enter ISP mode: ispEN HIGH -> LOW transition."""
        # Start with ispEN HIGH (disabled)
        self._set(nSRST | ispEN)
        time.sleep(0.02)
        # Pull ispEN LOW = enter ISP mode
        self._set(nSRST)
        time.sleep(0.02)

    def isp_exit(self):
        """Exit ISP mode: ispEN back to HIGH."""
        self._set(nSRST | ispEN)
        time.sleep(0.02)

    def reset_hard(self):
        """Full reset: nSRST pulse + ispEN re-entry."""
        # Exit ISP, assert reset
        self._set(ispEN)  # ispEN=HIGH, nSRST=LOW
        time.sleep(0.05)
        # Release reset, ispEN still HIGH
        self._set(nSRST | ispEN)
        time.sleep(0.05)
        # Enter ISP mode (HIGH->LOW transition on ispEN)
        self._set(nSRST)
        time.sleep(0.02)

    def idle(self):
        """Set all low except nSRST (ispEN stays LOW = ISP active)."""
        self._set(nSRST)


def fmt(val, bits):
    """Format value as hex string."""
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"


def test_protocol_A(isp):
    """
    Protocol A: Lattice legacy ISP (from app notes / patent analysis)

    The ISP controller uses MODE edges for framing:
    1. MODE HIGH->LOW transition = start of frame
    2. Clock data bits with MODE=0
    3. MODE LOW->HIGH transition = end of frame / execute

    Different frame lengths might select different operations:
    - 8-bit frame = command
    - Longer frames = address + data
    """
    print("=" * 60)
    print("PROTOCOL A: MODE edge framing")
    print("  MODE 1->0 = start, shift data, MODE 0->1 = execute")
    print("=" * 60)

    isp.reset_hard()

    # Set MODE=1 (idle state)
    isp.clk(0, 1)
    isp.clk(0, 1)

    # Try different command bytes
    print("\n--- 8-bit commands (read 8-bit response) ---")
    for cmd in range(256):
        # MODE=1 idle
        isp.clk(0, 1)
        # Shift 8-bit command with MODE=0
        resp = isp.shift(cmd, 8, mode=0)
        # MODE=1 execute
        isp.clk(0, 1)
        # Read 8-bit response with MODE=0
        data = isp.shift(0, 8, mode=0)
        # MODE=1 return to idle
        isp.clk(0, 1)

        if data != 0x15 and data != 0x00:
            print(f"  CMD={fmt(cmd,8)}: resp={fmt(resp,8)} data={fmt(data,8)} *** DIFFERENT ***")

    print("  (only non-0x15/0x00 results shown)")


def test_protocol_B(isp):
    """
    Protocol B: SDI is command when MODE=1, data when MODE=0.

    Some Lattice ISP uses:
    - Clock bits with MODE=1 to send command
    - Clock bits with MODE=0 to shift data
    """
    print("\n" + "=" * 60)
    print("PROTOCOL B: MODE=1 for command bits, MODE=0 for data bits")
    print("=" * 60)

    isp.reset_hard()

    print("\n--- 8-bit cmd (MODE=1), then 8-bit data read (MODE=0) ---")
    for cmd in range(256):
        isp.reset_hard()
        # Send command with MODE=1
        resp_cmd = isp.shift(cmd, 8, mode=1)
        # Read data with MODE=0
        resp_data = isp.shift(0, 8, mode=0)

        if resp_data != 0x15 and resp_data != 0x00:
            print(f"  CMD={fmt(cmd,8)}: cmd_out={fmt(resp_cmd,8)} data={fmt(resp_data,8)} *** DIFFERENT ***")

    print("  (only non-0x15/0x00 results shown)")

    # Also try: command + longer data reads
    print("\n--- Selected cmds (MODE=1), then 32-bit data read (MODE=0) ---")
    for cmd in [0x00, 0x01, 0x02, 0x03, 0x0A, 0x15, 0x1F, 0x55,
                0x68, 0x69, 0x6A, 0x6E, 0x70, 0x7E, 0x80, 0xAA,
                0xC0, 0xE0, 0xFE, 0xFF]:
        isp.reset_hard()
        isp.shift(cmd, 8, mode=1)
        data = isp.shift(0, 32, mode=0)
        print(f"  CMD={fmt(cmd,8)}: data32={fmt(data,32)}")


def test_protocol_C(isp):
    """
    Protocol C: Specific MODE sequences from Lattice patent.

    Patent US5412260A describes:
    "a series of clock signals are applied to the SCLK input while
     the MODE input is held at a logic low level to shift data into
     the device, and then the MODE input is pulsed high to cause
     the data to be processed"

    So: shift data with MODE=0, pulse MODE=1 to "process".
    The first N bits might be a command, followed by address/data.
    """
    print("\n" + "=" * 60)
    print("PROTOCOL C: Shift everything MODE=0, pulse MODE=1 to process")
    print("  (from patent description)")
    print("=" * 60)

    # Try: 8-bit command, MODE pulse, read response
    print("\n--- 8-bit shift, MODE pulse, 8-bit read ---")
    for cmd in range(256):
        isp.reset_hard()
        isp.shift(cmd, 8, mode=0)    # shift command
        isp.clk(0, 1)                 # MODE pulse (process)
        data = isp.shift(0, 8, mode=0)  # read response

        if data != 0x15 and data != 0x00:
            print(f"  CMD={fmt(cmd,8)}: data={fmt(data,8)} *** DIFFERENT ***")

    print("  (only non-0x15/0x00 results shown)")

    # Try: longer command words
    print("\n--- 16-bit shift, MODE pulse, 16-bit read ---")
    # Try some potentially meaningful 16-bit values
    for hi in [0x00, 0x01, 0x02, 0x03, 0x0A, 0x15, 0x55, 0x68,
               0x80, 0xAA, 0xC0, 0xE0, 0xFE, 0xFF]:
        for lo in [0x00, 0x01, 0xFF]:
            val = (hi << 8) | lo
            isp.reset_hard()
            isp.shift(val, 16, mode=0)
            isp.clk(0, 1)
            data = isp.shift(0, 16, mode=0)
            if data != 0x0015 and data != 0x0000:
                print(f"  {fmt(val,16)}: data={fmt(data,16)} *** DIFFERENT ***")

    print("  (only non-0x0015/0x0000 results shown)")


def test_protocol_D(isp):
    """
    Protocol D: Multiple MODE pulses between operations.

    Maybe the ISP state machine requires a specific number of
    MODE=1 clock cycles to advance to different states.
    """
    print("\n" + "=" * 60)
    print("PROTOCOL D: Variable MODE=1 pulse count")
    print("=" * 60)

    for n_pre in [0, 1, 2, 3, 4, 5, 8, 16]:
        for n_mid in [0, 1, 2, 3]:
            isp.reset_hard()
            # Pre-pulse MODE=1
            for _ in range(n_pre):
                isp.clk(0, 1)
            # Shift command 0x0A (ISC_READ from V/VE) with MODE=0
            isp.shift(0x0A, 8, mode=0)
            # Mid-pulse MODE=1
            for _ in range(n_mid):
                isp.clk(0, 1)
            # Read 32 bits with MODE=0
            data = isp.shift(0, 32, mode=0)

            if data != 0x00000015 and data != 0x00000000:
                print(f"  pre={n_pre:2d} mid={n_mid}: data={fmt(data,32)} *** DIFFERENT ***")

    print("  (only non-standard results shown, or nothing if all same)")


def test_protocol_E(isp):
    """
    Protocol E: ispEN toggle via RESET.

    Maybe the ISP controller needs ispEN to transition HIGH->LOW
    to properly initialize. Since ispEN is hardwired to GND,
    the chip might power up in an undefined ISP state.

    We can't control ispEN, but we CAN try toggling RESET
    with different MODE states to see if it changes behavior.
    """
    print("\n" + "=" * 60)
    print("PROTOCOL E: RESET with MODE in different states")
    print("=" * 60)

    for mode_during_reset in [0, 1]:
        for mode_after_reset in [0, 1]:
            isp._set(nSRST)
            time.sleep(0.01)

            # Assert RESET with MODE at specific level
            val = MODE if mode_during_reset else 0
            isp._set(val)  # nSRST=0 (reset), MODE=x
            time.sleep(0.05)

            # Release RESET with MODE at specific level
            val = nSRST | (MODE if mode_after_reset else 0)
            isp._set(val)
            time.sleep(0.05)

            # Clock a few times in current MODE state
            for _ in range(4):
                isp.clk(0, mode_after_reset)

            # Now read with MODE=0
            data = isp.shift(0, 8, mode=0)
            pat = isp.shift(0xA5, 8, mode=0)
            readback = isp.shift(0, 8, mode=0)

            print(f"  RESET(MODE={mode_during_reset})->release(MODE={mode_after_reset}): "
                  f"capture={fmt(data,8)} shift_A5={fmt(pat,8)} readback={fmt(readback,8)}")


def test_ispEN_transition(isp):
    """
    KEY TEST: Does ispEN HIGH->LOW transition change behavior?
    Compare: chip powered with ispEN=LOW (old setup)
    vs: proper ispEN HIGH->LOW entry sequence.
    """
    print("=" * 60)
    print("TEST 0: ispEN transition effect")
    print("=" * 60)

    # Test A: ispEN HIGH (ISP disabled) — read SDO
    isp.isp_exit()  # ispEN=HIGH
    time.sleep(0.02)
    data_off = isp.shift(0, 8, mode=0)
    pat_off = isp.shift(0xA5, 8, mode=0)
    rb_off = isp.shift(0, 8, mode=0)
    print(f"  ispEN=HIGH (disabled): capture={fmt(data_off,8)} "
          f"shift_A5={fmt(pat_off,8)} readback={fmt(rb_off,8)}")

    # Test B: ispEN HIGH->LOW (proper ISP entry)
    isp.isp_enter()  # HIGH->LOW transition
    data_on = isp.shift(0, 8, mode=0)
    pat_on = isp.shift(0xA5, 8, mode=0)
    rb_on = isp.shift(0, 8, mode=0)
    print(f"  ispEN=LOW  (enabled):  capture={fmt(data_on,8)} "
          f"shift_A5={fmt(pat_on,8)} readback={fmt(rb_on,8)}")

    # Test C: full reset + ISP entry
    isp.reset_hard()
    data_rst = isp.shift(0, 8, mode=0)
    pat_rst = isp.shift(0xA5, 8, mode=0)
    rb_rst = isp.shift(0, 8, mode=0)
    print(f"  After RESET+enter:     capture={fmt(data_rst,8)} "
          f"shift_A5={fmt(pat_rst,8)} readback={fmt(rb_rst,8)}")

    # Test D: ispEN toggle multiple times
    for i in range(3):
        isp.isp_exit()
        time.sleep(0.01)
        isp.isp_enter()
        time.sleep(0.01)
    data_tog = isp.shift(0, 8, mode=0)
    print(f"  After 3x toggle:       capture={fmt(data_tog,8)}")

    # Compare
    if data_off != data_on:
        print(f"\n  *** ispEN transition CHANGES capture: "
              f"OFF={fmt(data_off,8)} ON={fmt(data_on,8)} ***")
    else:
        print(f"\n  ispEN transition has no effect on capture value.")

    print()


def test_clock_edges(isp):
    """
    Test: Does the chip sample on rising or falling edge?
    """
    print("=" * 60)
    print("TEST: Clock edge sensitivity")
    print("=" * 60)

    isp.reset_hard()

    isp.shift(0xA5, 8, mode=0)

    result_setup = 0
    for i in range(8):
        val = nSRST
        isp._set(val)
        pins = isp._read()
        sdo = 1 if (pins & SDO) else 0
        result_setup |= (sdo << i)
        isp._set(val | SCLK)
        isp._set(val)

    result_fall = 0
    for i in range(8):
        val = nSRST
        isp._set(val | SCLK)
        isp._set(val)
        pins = isp._read()
        sdo = 1 if (pins & SDO) else 0
        result_fall |= (sdo << i)

    print(f"  SDO captured before rising edge:  {fmt(result_setup, 8)}")
    print(f"  SDO captured after falling edge:  {fmt(result_fall, 8)}")


def main():
    print("ispLSI 2032 — Legacy ISP Protocol Probe v2")
    print("=" * 60)

    isp = ISP()
    print("Connected.\n")

    try:
        test_ispEN_transition(isp)  # KEY: does ispEN toggle help?
        test_clock_edges(isp)
        test_protocol_E(isp)    # RESET combos first (quick)
        test_protocol_D(isp)    # MODE pulse count (quick)
        test_protocol_C(isp)    # Patent-based (256 + extras)
        test_protocol_A(isp)    # Edge framing (256)
        test_protocol_B(isp)    # MODE=1 cmd / MODE=0 data (256 + extras)

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETE")
        print("=" * 60)
    finally:
        isp.close()


if __name__ == '__main__':
    main()
