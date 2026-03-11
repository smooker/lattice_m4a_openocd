#!/usr/bin/env python3
"""
Bit-bang ISP probe for Lattice ispLSI 2032 via FT2232H MPSSE.

This script bypasses OpenOCD and directly controls the FTDI pins
to probe the legacy ISP protocol. OpenOCD must be STOPPED first.

Pin mapping (FT2232H Channel A, ADBUS):
  ADBUS0 = SCLK/TCK  (output)  -> chip pin 27
  ADBUS1 = SDI/TDI   (output)  -> chip pin 8
  ADBUS2 = SDO/TDO   (input)   -> chip pin 18
  ADBUS3 = MODE/TMS  (output)  -> chip pin 30
  ADBUS4 = nSRST     (output)  -> chip pin 29 (RESET/Y1)

ispEN (chip pin 7) is hardwired to GND = ISP mode always active.
"""

import sys
import time
from pyftdi.ftdi import Ftdi

# --- Configuration ---
FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000  # 100 kHz (safe start)

# Pin bit positions on ADBUS
SCLK  = 0x01  # bit 0
SDI   = 0x02  # bit 1
SDO   = 0x04  # bit 2 (input)
MODE  = 0x08  # bit 3
nSRST = 0x10  # bit 4

# Direction: 1=output, 0=input; TDO is input
DIR = SCLK | SDI | MODE | nSRST  # 0x1B


class ISPBitBang:
    def __init__(self):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST)
        # Current output state
        self.state = nSRST  # RESET high, everything else low
        self._set_pins(self.state)

    def close(self):
        self.ftdi.close()

    def _set_pins(self, value):
        """Set ADBUS low byte."""
        self.state = value
        self.ftdi.write_data(bytes([0x80, value & 0xFF, DIR]))

    def _read_pins(self):
        """Read ADBUS low byte (for SDO/TDO)."""
        self.ftdi.write_data(bytes([0x81]))
        data = self.ftdi.read_data_bytes(1, attempt=10)
        return data[0] if data else 0

    def clock_bit(self, sdi_val, mode_val):
        """
        Clock one bit: set SDI and MODE, pulse SCLK, read SDO.
        Returns the SDO value (0 or 1).
        """
        # Set up: SCLK=0, SDI=x, MODE=x, nSRST=1
        val = nSRST
        if sdi_val: val |= SDI
        if mode_val: val |= MODE
        self._set_pins(val)

        # Rising edge: SCLK=1
        self._set_pins(val | SCLK)

        # Read SDO on or after rising edge
        pins = self._read_pins()
        sdo = 1 if (pins & SDO) else 0

        # Falling edge: SCLK=0
        self._set_pins(val)

        return sdo

    def shift_bits(self, data_bits, nbits, mode_val):
        """
        Shift nbits through SDI/SDO with MODE held at mode_val.
        data_bits: integer, LSB shifted first.
        Returns: integer read from SDO, LSB first.
        """
        result = 0
        for i in range(nbits):
            sdi = (data_bits >> i) & 1
            sdo = self.clock_bit(sdi, mode_val)
            result |= (sdo << i)
        return result

    def mode_pulse(self, n=1):
        """Pulse MODE high for n clock cycles, SDI=0."""
        for _ in range(n):
            self.clock_bit(0, 1)

    def jtag_reset(self):
        """Standard JTAG reset: 5 clocks with TMS/MODE=1."""
        for _ in range(5):
            self.clock_bit(0, 1)
        # Go to IDLE: 1 clock with MODE=0
        self.clock_bit(0, 0)

    # --- JTAG operations ---

    def jtag_shift_ir(self, ir_data, ir_len):
        """JTAG: navigate to SHIFT-IR, shift data, return to IDLE."""
        # From IDLE: MODE=1,1,0,0 -> DR-SELECT, IR-SELECT, IR-CAPTURE, IR-SHIFT
        self.clock_bit(0, 1)  # IDLE -> DR-SELECT
        self.clock_bit(0, 1)  # DR-SELECT -> IR-SELECT
        self.clock_bit(0, 0)  # IR-SELECT -> IR-CAPTURE
        self.clock_bit(0, 0)  # IR-CAPTURE -> IR-SHIFT

        # Shift ir_len-1 bits with MODE=0, last bit with MODE=1 (exit)
        result = 0
        for i in range(ir_len - 1):
            sdi = (ir_data >> i) & 1
            sdo = self.clock_bit(sdi, 0)
            result |= (sdo << i)

        # Last bit: MODE=1 -> EXIT1-IR
        sdi = (ir_data >> (ir_len - 1)) & 1
        sdo = self.clock_bit(sdi, 1)
        result |= (sdo << (ir_len - 1))

        # EXIT1-IR -> UPDATE-IR -> IDLE
        self.clock_bit(0, 1)  # -> UPDATE-IR
        self.clock_bit(0, 0)  # -> IDLE

        return result

    def jtag_shift_dr(self, dr_data, dr_len):
        """JTAG: navigate to SHIFT-DR, shift data, return to IDLE."""
        # From IDLE: MODE=1,0,0 -> DR-SELECT, DR-CAPTURE, DR-SHIFT
        self.clock_bit(0, 1)  # IDLE -> DR-SELECT
        self.clock_bit(0, 0)  # DR-SELECT -> DR-CAPTURE
        self.clock_bit(0, 0)  # DR-CAPTURE -> DR-SHIFT

        # Shift dr_len-1 bits with MODE=0, last bit with MODE=1
        result = 0
        for i in range(dr_len - 1):
            sdi = (dr_data >> i) & 1
            sdo = self.clock_bit(sdi, 0)
            result |= (sdo << i)

        # Last bit: MODE=1 -> EXIT1-DR
        sdi = (dr_data >> (dr_len - 1)) & 1
        sdo = self.clock_bit(sdi, 1)
        result |= (sdo << (dr_len - 1))

        # EXIT1-DR -> UPDATE-DR -> IDLE
        self.clock_bit(0, 1)  # -> UPDATE-DR
        self.clock_bit(0, 0)  # -> IDLE

        return result

    # --- Legacy ISP protocol variants ---

    def legacy_reset(self):
        """Reset the ISP state machine: MODE=1 for 8 clocks."""
        for _ in range(8):
            self.clock_bit(0, 1)

    def legacy_shift(self, data, nbits):
        """Shift data with MODE=0 (data phase)."""
        return self.shift_bits(data, nbits, mode_val=0)

    def legacy_command(self, cmd, cmd_bits=8):
        """
        Legacy ISP command: MODE=1 pulse, then shift command with MODE=0,
        then MODE=1 pulse to execute.
        """
        self.clock_bit(0, 1)  # MODE=1: start command frame
        result = self.shift_bits(cmd, cmd_bits, mode_val=0)
        self.clock_bit(0, 1)  # MODE=1: end command frame
        return result

    def legacy_cmd_data(self, cmd, cmd_bits, data, data_bits):
        """
        Legacy ISP: send command, then send/receive data.
        Returns (cmd_response, data_response).
        """
        # Command phase
        self.clock_bit(0, 1)  # Start
        cmd_r = self.shift_bits(cmd, cmd_bits, mode_val=0)
        self.clock_bit(0, 1)  # Delimiter

        # Data phase
        data_r = self.shift_bits(data, data_bits, mode_val=0)
        self.clock_bit(0, 1)  # End

        return cmd_r, data_r


def test_jtag(isp):
    """Test standard JTAG with different IR lengths."""
    print("=" * 60)
    print("TEST 1: Standard JTAG — IR length detection")
    print("=" * 60)

    isp.jtag_reset()

    # Detect IR length: shift ones, then shift zeros and count
    # Go to SHIFT-IR
    isp.clock_bit(0, 1)  # IDLE -> DR-SELECT
    isp.clock_bit(0, 1)  # DR-SELECT -> IR-SELECT
    isp.clock_bit(0, 0)  # IR-SELECT -> IR-CAPTURE
    isp.clock_bit(0, 0)  # IR-CAPTURE -> IR-SHIFT

    # Shift 32 ones (fill IR)
    for _ in range(32):
        isp.clock_bit(1, 0)

    # Shift 32 zeros and capture TDO
    bits = []
    for _ in range(32):
        sdo = isp.clock_bit(0, 0)
        bits.append(sdo)

    # Exit SHIFT-IR
    isp.clock_bit(0, 1)  # EXIT1-IR
    isp.clock_bit(0, 1)  # UPDATE-IR
    isp.clock_bit(0, 0)  # IDLE

    # Count leading 1s = IR length
    ir_len = 0
    for b in bits:
        if b == 1:
            ir_len += 1
        else:
            break

    print(f"  TDO after ones->zeros: {bits[:16]}")
    print(f"  Detected IR length: {ir_len}")
    print()
    return ir_len


def test_dr_length(isp):
    """Measure DR register length."""
    print("=" * 60)
    print("TEST 2: DR length detection")
    print("=" * 60)

    isp.jtag_reset()

    # Load BYPASS (all ones) into IR with irlen=5
    isp.jtag_shift_ir(0x1F, 5)

    # Go to SHIFT-DR
    isp.clock_bit(0, 1)  # IDLE -> DR-SELECT
    isp.clock_bit(0, 0)  # DR-SELECT -> DR-CAPTURE
    isp.clock_bit(0, 0)  # DR-CAPTURE -> DR-SHIFT

    # Shift 32 ones
    for _ in range(32):
        isp.clock_bit(1, 0)

    # Shift 32 zeros and capture
    bits = []
    for _ in range(32):
        sdo = isp.clock_bit(0, 0)
        bits.append(sdo)

    # Exit
    isp.clock_bit(0, 1)
    isp.clock_bit(0, 1)
    isp.clock_bit(0, 0)

    dr_len = 0
    for b in bits:
        if b == 1:
            dr_len += 1
        else:
            break

    print(f"  TDO after ones->zeros: {bits[:16]}")
    print(f"  Detected DR length: {dr_len}")
    print()
    return dr_len


def test_legacy_protocol(isp):
    """Try various legacy ISP protocol sequences."""
    print("=" * 60)
    print("TEST 3: Legacy ISP protocol probing")
    print("=" * 60)

    # Protocol variant A: MODE controls command/data framing
    print("\n--- Variant A: MODE=1 frame, MODE=0 shift ---")
    isp.legacy_reset()

    # Try reading with different command bytes
    for cmd in [0x00, 0x01, 0x02, 0x03, 0x0A, 0x15, 0x1E, 0x1F,
                0x55, 0xAA, 0xFF, 0x80, 0xC0, 0xE0]:
        isp.legacy_reset()
        cmd_r, data_r = isp.legacy_cmd_data(cmd, 8, 0x00, 32)
        if data_r != 0:
            print(f"  CMD=0x{cmd:02X}: cmd_resp=0x{cmd_r:02X} "
                  f"data_resp=0x{data_r:08X} ***")
        else:
            print(f"  CMD=0x{cmd:02X}: cmd_resp=0x{cmd_r:02X} "
                  f"data_resp=0x{data_r:08X}")

    # Protocol variant B: 5-bit command like JTAG IR
    print("\n--- Variant B: 5-bit command framing ---")
    for cmd in range(32):
        isp.legacy_reset()
        cmd_r, data_r = isp.legacy_cmd_data(cmd, 5, 0x00, 32)
        if data_r != 0:
            print(f"  CMD5=0x{cmd:02X}: cmd_resp=0x{cmd_r:02X} "
                  f"data_resp=0x{data_r:08X} ***")

    # Protocol variant C: no framing, just MODE=0 continuous shift
    print("\n--- Variant C: Continuous shift (MODE=0), various lengths ---")
    isp.legacy_reset()
    for nbits in [8, 16, 32, 40, 64, 80, 102, 128]:
        isp.legacy_reset()
        # Shift zeros
        result = isp.legacy_shift(0, nbits)
        if result != 0:
            print(f"  {nbits:3d} bits: 0x{result:0{nbits//4}X} ***")
        else:
            print(f"  {nbits:3d} bits: 0x{result:0{max(nbits//4,1)}X}")

    # Protocol variant D: MODE=1 continuous (command mode)
    print("\n--- Variant D: Continuous shift (MODE=1), various lengths ---")
    for nbits in [8, 16, 32]:
        isp.legacy_reset()
        result = isp.shift_bits(0, nbits, mode_val=1)
        if result != 0:
            print(f"  {nbits:3d} bits (MODE=1): 0x{result:0{max(nbits//4,1)}X} ***")
        else:
            print(f"  {nbits:3d} bits (MODE=1): 0x{result:0{max(nbits//4,1)}X}")

    print()


def test_raw_sdo(isp):
    """Read SDO with no clocking — check for stuck lines."""
    print("=" * 60)
    print("TEST 4: Raw pin state")
    print("=" * 60)

    # Read pins with all outputs low
    isp._set_pins(nSRST)  # only nSRST high
    pins = isp._read_pins()
    sdo_idle = (pins >> 2) & 1
    print(f"  SDO with SCLK=0 SDI=0 MODE=0: {sdo_idle}")

    # SDI=1
    isp._set_pins(nSRST | SDI)
    pins = isp._read_pins()
    sdo = (pins >> 2) & 1
    print(f"  SDO with SCLK=0 SDI=1 MODE=0: {sdo}")

    # MODE=1
    isp._set_pins(nSRST | MODE)
    pins = isp._read_pins()
    sdo = (pins >> 2) & 1
    print(f"  SDO with SCLK=0 SDI=0 MODE=1: {sdo}")

    # SCLK=1
    isp._set_pins(nSRST | SCLK)
    pins = isp._read_pins()
    sdo = (pins >> 2) & 1
    print(f"  SDO with SCLK=1 SDI=0 MODE=0: {sdo}")

    # All high
    isp._set_pins(nSRST | SCLK | SDI | MODE)
    pins = isp._read_pins()
    sdo = (pins >> 2) & 1
    print(f"  SDO with SCLK=1 SDI=1 MODE=1: {sdo}")

    # Reset state
    isp._set_pins(nSRST)
    print()


def test_reset_toggle(isp):
    """Try toggling RESET and see if behavior changes."""
    print("=" * 60)
    print("TEST 5: RESET toggle + re-test")
    print("=" * 60)

    # Assert RESET
    print("  Asserting RESET (nSRST=LOW)...")
    isp._set_pins(0)  # all low including nSRST
    time.sleep(0.1)

    # Release RESET
    print("  Releasing RESET (nSRST=HIGH)...")
    isp._set_pins(nSRST)
    time.sleep(0.1)

    # Try JTAG scan after reset
    isp.jtag_reset()

    # Try JTAG DR read
    ir_cap = isp.jtag_shift_ir(0x1F, 5)
    dr = isp.jtag_shift_dr(0x00000000, 32)
    print(f"  After RESET: IR capture=0x{ir_cap:02X}, DR=0x{dr:08X}")

    # Try legacy protocol after reset
    isp.legacy_reset()
    cmd_r, data_r = isp.legacy_cmd_data(0x0A, 8, 0x00, 32)
    print(f"  Legacy CMD=0x0A: cmd_resp=0x{cmd_r:02X} data=0x{data_r:08X}")
    print()


def test_ispEN_toggle(isp):
    """
    Test: toggle ispEN via RESET pin behavior.
    On the plain 2032, ispEN and RESET might interact.
    We can't control ispEN directly (hardwired to GND),
    but RESET might re-initialize the ISP controller.
    """
    print("=" * 60)
    print("TEST 6: RESET pulse then immediate ISP probe")
    print("=" * 60)

    # Pulse RESET
    isp._set_pins(0)
    time.sleep(0.01)
    isp._set_pins(nSRST)
    time.sleep(0.01)

    # Don't do JTAG reset — go straight to MODE-based ISP
    # Try: MODE=1 for 1 clock (reset ISP SM), then shift

    # Single MODE=1 clock
    isp.clock_bit(0, 1)

    # Now shift 8 bits with MODE=0 — read whatever comes out
    result = isp.shift_bits(0x00, 8, mode_val=0)
    print(f"  After RESET+1xMODE1: 8-bit read = 0x{result:02X}")

    # Try with pattern
    result = isp.shift_bits(0xA5, 8, mode_val=0)
    print(f"  Shift in 0xA5: out = 0x{result:02X}")

    result = isp.shift_bits(0x00, 8, mode_val=0)
    print(f"  Shift in 0x00: out = 0x{result:02X}")

    # More MODE=1 clocks then data
    for n_mode in [2, 3, 4, 5, 8, 16]:
        isp._set_pins(nSRST)
        time.sleep(0.01)
        for _ in range(n_mode):
            isp.clock_bit(0, 1)
        r1 = isp.shift_bits(0x00, 8, mode_val=0)
        r2 = isp.shift_bits(0xA5, 8, mode_val=0)
        r3 = isp.shift_bits(0x00, 8, mode_val=0)
        print(f"  {n_mode:2d}x MODE1 clocks: "
              f"read=0x{r1:02X} shift_A5=0x{r2:02X} read=0x{r3:02X}")

    print()


def main():
    print("Lattice ispLSI 2032 — Bit-Bang ISP Probe")
    print("=" * 60)
    print(f"Connecting to {FTDI_URL}...")

    isp = ISPBitBang()
    print("Connected!\n")

    try:
        test_raw_sdo(isp)
        test_jtag(isp)
        test_dr_length(isp)
        test_legacy_protocol(isp)
        test_reset_toggle(isp)
        test_ispEN_toggle(isp)

        print("=" * 60)
        print("ALL TESTS COMPLETE")
        print("=" * 60)
    finally:
        isp.close()


if __name__ == '__main__':
    main()
