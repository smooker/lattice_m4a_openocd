#!/usr/bin/env python3
"""
isp.py — Reusable ISP library for ispLSI 2032.

Implements the Lattice proprietary 3-state ISP protocol (NOT JTAG):

    IDLE/ID  --HH-->  SHIFT  --HH-->  EXECUTE
       ^  HL/          LX/              LX/
       +----HL----------+        +--HL--+

State transitions on SCLK rising edge:
  HH (MODE=H, SDI=H) = advance to next state
  HL (MODE=H, SDI=L) = go to IDLE
  LX (MODE=L)        = shift data / stay in current state

Extracted from bitbang_isp6.py for use as a library.

Run on HOST (needs pyftdi + libusb):
  sudo rmmod ftdi_sio
"""

import sys
import time
from pyftdi.ftdi import Ftdi

# FT2232H configuration
FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000  # 100 kHz

# ADBUS pin mapping
SCLK  = 0x01  # bit 0 — serial clock (-> chip pin 27)
SDI   = 0x02  # bit 1 — serial data in (-> chip pin 8)
SDO   = 0x04  # bit 2 — serial data out, INPUT (-> chip pin 18)
MODE  = 0x08  # bit 3 — state machine control (-> chip pin 30)
nSRST = 0x10  # bit 4 — active low reset (-> chip pin 29)
ispEN = 0x20  # bit 5 — active low ISP enable (-> chip pin 7)
DIR   = SCLK | SDI | MODE | nSRST | ispEN  # 0x3B — output bits

# ISP Instructions (5-bit, Table 4, p.8-11)
NOP      = 0b00000
ADDSHFT  = 0b00001
DATASHFT = 0b00010
UBE      = 0b00011  # User Bulk Erase (clears security!)
GRPBE    = 0b00100
GLBBE    = 0b00101
ARCHBE   = 0b00110
PRGMH    = 0b00111  # Program High Order
PRGML    = 0b01000  # Program Low Order
PRGMSC   = 0b01001  # Program Security Cell (one-way!)
VERLDH   = 0b01010  # Verify/Load High Order
VERLDL   = 0b01011  # Verify/Load Low Order
FLOWTHRU = 0b01110  # Bypass (SDI -> SDO)
PROGUES  = 0b01111  # Program UES
ERALL    = 0b10000  # Erase All (incl. UES)
VERUES   = 0b10001  # Verify UES
VELDH    = 0b10010  # Verify Erase High
VELDL    = 0b10011  # Verify Erase Low

CMD_NAMES = {
    NOP: "NOP", ADDSHFT: "ADDSHFT", DATASHFT: "DATASHFT", UBE: "UBE",
    ERALL: "ERALL", GRPBE: "GRPBE", GLBBE: "GLBBE", ARCHBE: "ARCHBE",
    PRGMH: "PRGMH", PRGML: "PRGML", PRGMSC: "PRGMSC",
    VERLDH: "VER/LDH", VERLDL: "VER/LDL", FLOWTHRU: "FLOWTHRU",
    VELDH: "VE/LDH", VELDL: "VE/LDL", PROGUES: "PROGUES", VERUES: "VERUES",
}

# Timing (Table 5, p.8-12 — ispLSI 2000 family)
T_RST   = 0.001    # trst: 45 us min (we use 1 ms)
T_ISPEN = 0.001    # tispen: 10 us min
T_SU    = 0.000002 # tsu1: 0.1 us min (we use 2 us)
T_CLKH  = 0.000002 # tclkh: 0.5 us min
T_CLKL  = 0.000002 # tclkl: 0.5 us min
T_SU2   = 0.001    # tsu2: 200 us min (we use 1 ms)
T_PWP   = 0.200    # tpwp: 80-160 ms (we use 200 ms)
T_BEW   = 0.300    # tbew: 200 ms min (we use 300 ms)
T_PWV   = 0.001    # tpwv: 20 us min (we use 1 ms)

# ispLSI 2032 register sizes (Table 8, p.8-19)
ADDR_SR_BITS = 102
DATA_SR_HIGH = 40
DATA_SR_LOW  = 40
DEVICE_ID_BITS = 8
CMD_BITS = 5
NUM_ROWS = 102

# Erased state: top 2 bits always 0, lower 38 bits = 1
# Chip reads 0x3FFFFFFFFF (not 0xFFFFFFFFFF) — only 38 of 40 SR bits are fuses
ERASED_HIGH = 0x3FFFFFFFFF
ERASED_LOW  = 0x3FFFFFFFFF


class ISP2032:
    """ispLSI 2032 ISP programmer via FT2232H bitbang."""

    def __init__(self, verbose=False):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST | ispEN)
        self._pins(nSRST | ispEN)  # Safe: ISP disabled, reset inactive
        self.verbose = verbose

    def close(self):
        """Release hardware and close FTDI connection."""
        self._pins(nSRST | ispEN)
        time.sleep(0.01)
        self.ftdi.close()

    # ---- Low-level pin operations ----

    def _pins(self, val):
        """Set ADBUS output pins."""
        self.ftdi.write_data(bytes([0x80, val & 0xFF, DIR]))

    def _read(self):
        """Read ADBUS pins (for SDO)."""
        self.ftdi.write_data(bytes([0x81]))
        d = self.ftdi.read_data_bytes(1, attempt=10)
        return d[0] if d else 0

    def _clock(self, mode_h, sdi_h):
        """One SCLK clock cycle with given MODE and SDI levels.
        Returns SDO value (0 or 1) read after falling edge.
        """
        val = nSRST
        if mode_h: val |= MODE
        if sdi_h:  val |= SDI
        # Setup: MODE + SDI stable, SCLK low
        self._pins(val)
        # Rising edge
        self._pins(val | SCLK)
        # Falling edge
        self._pins(val)
        # Read SDO after falling edge
        pins = self._read()
        return 1 if (pins & SDO) else 0

    # ---- Buffered (fast) operations ----
    # Batch all MPSSE commands into one USB write, read all SDO at once.
    # ~200x faster than one-at-a-time for USB latency-bound operations.

    def _buf_clock(self, buf, mode_h, sdi_h, read_sdo=False):
        """Append one clock cycle to MPSSE command buffer.
        If read_sdo=True, appends a read command (caller must collect response).
        """
        val = nSRST
        if mode_h: val |= MODE
        if sdi_h:  val |= SDI
        buf.extend([0x80, val & 0xFF, DIR])          # setup
        buf.extend([0x80, (val | SCLK) & 0xFF, DIR]) # rising edge
        buf.extend([0x80, val & 0xFF, DIR])           # falling edge
        if read_sdo:
            buf.append(0x81)                          # read ADBUS

    def _buf_goto_idle(self, buf):
        """Append goto_idle to buffer."""
        self._buf_clock(buf, mode_h=True, sdi_h=False)

    def _buf_change_state(self, buf):
        """Append change_state: ONE clock, HH on rise, LX on fall."""
        val_hh = nSRST | MODE | SDI
        val_lx = nSRST
        buf.extend([0x80, val_hh & 0xFF, DIR])          # setup HH
        buf.extend([0x80, (val_hh | SCLK) & 0xFF, DIR]) # rising edge
        buf.extend([0x80, (val_lx | SCLK) & 0xFF, DIR]) # switch to LX
        buf.extend([0x80, val_lx & 0xFF, DIR])           # falling edge

    def _buf_shift_command(self, buf, cmd):
        """Append 5-bit command shift to buffer."""
        for i in range(CMD_BITS):
            bit = (cmd >> i) & 1
            self._buf_clock(buf, mode_h=False, sdi_h=bool(bit))

    def _buf_shift_data_in(self, buf, data, nbits):
        """Append data shift-in to buffer."""
        for i in range(nbits):
            bit = (data >> i) & 1
            self._buf_clock(buf, mode_h=False, sdi_h=bool(bit))

    def _buf_shift_data_out(self, buf, nbits):
        """Append data shift-out to buffer (with reads)."""
        for i in range(nbits):
            self._buf_clock(buf, mode_h=False, sdi_h=False, read_sdo=True)

    def _buf_execute(self, buf):
        """Append execute clock to buffer (no wait — caller handles timing)."""
        self._buf_clock(buf, mode_h=False, sdi_h=False)

    def _flush_and_read(self, buf, num_reads):
        """Send buffered commands, read back SDO samples.
        Returns list of 0/1 values.
        """
        self.ftdi.write_data(bytes(buf))
        if num_reads == 0:
            return []
        raw = self.ftdi.read_data_bytes(num_reads, attempt=20)
        return [1 if (b & SDO) else 0 for b in raw]

    def read_row_fast(self, row):
        """Read one row using buffered MPSSE. Returns (high, low) tuple.
        Much faster than read_row() — one USB round-trip per half.
        """
        results = []
        for cmd in (VERLDH, VERLDL):
            buf = bytearray()
            # 1. ADDSHFT + address
            self._buf_goto_idle(buf)
            self._buf_change_state(buf)
            self._buf_shift_command(buf, ADDSHFT)
            self._buf_change_state(buf)
            addr = 1 << row
            self._buf_shift_data_in(buf, addr, ADDR_SR_BITS)
            # 2. VER/LDH or VER/LDL
            self._buf_goto_idle(buf)
            self._buf_change_state(buf)
            self._buf_shift_command(buf, cmd)
            self._buf_change_state(buf)
            # Flush address + verify command, wait for data load
            self.ftdi.write_data(bytes(buf))
            time.sleep(T_PWV)
            # 3. DATASHFT + read out 40 bits
            buf2 = bytearray()
            self._buf_goto_idle(buf2)
            self._buf_change_state(buf2)
            self._buf_shift_command(buf2, DATASHFT)
            self._buf_change_state(buf2)
            self._buf_shift_data_out(buf2, DATA_SR_HIGH)
            bits = self._flush_and_read(buf2, DATA_SR_HIGH)
            # Reconstruct value (LSB first)
            val = 0
            for i, b in enumerate(bits):
                val |= (b << i)
            results.append(val)
        return (results[0], results[1])

    def read_all_fast(self):
        """Read all 102 rows using buffered MPSSE. Much faster."""
        rows = []
        for r in range(NUM_ROWS):
            rows.append(self.read_row_fast(r))
        return rows

    # ---- ISP State Machine Operations ----

    def enter_isp(self):
        """Enter ISP Edit Mode: reset toggle, then ispEN LOW."""
        self._pins(nSRST | ispEN)
        time.sleep(0.01)
        # Reset toggle
        self._pins(ispEN)              # RESET active (nSRST LOW)
        time.sleep(0.05)
        self._pins(nSRST | ispEN)      # RESET released
        time.sleep(T_RST)
        # Enter ISP: ispEN LOW
        self._pins(nSRST)              # ispEN LOW = Edit Mode
        time.sleep(T_ISPEN)
        if self.verbose:
            print("  [ISP] Entered Edit Mode (ispEN LOW)")

    def exit_isp(self):
        """Exit ISP mode: ispEN HIGH."""
        self._pins(nSRST | ispEN)
        time.sleep(T_ISPEN)
        if self.verbose:
            print("  [ISP] Exited Edit Mode (ispEN HIGH)")

    def goto_idle(self):
        """Force state machine to IDLE from any state.
        MODE=H, SDI=L + clock -> always goes to IDLE.
        """
        self._clock(mode_h=True, sdi_h=False)  # HL -> IDLE

    def change_state(self):
        """Advance to next state: IDLE->SHIFT or SHIFT->EXECUTE.
        ONE clock: HH on rising edge (state advances), then switch to LX
        before falling edge. NOT two clocks — extra LX clock would shift data!

        From Data Book p.8-32:
          MODE=H, SDI=H → wait tsu → SCLK↑ (advance)
          MODE=L, SDI=L → wait tclkh → SCLK↓ (settle)
        """
        val_hh = nSRST | MODE | SDI
        val_lx = nSRST
        self._pins(val_hh)              # Setup: MODE=H, SDI=H
        self._pins(val_hh | SCLK)       # Rising edge → state advances
        self._pins(val_lx | SCLK)       # Switch to MODE=L while SCLK high
        self._pins(val_lx)              # Falling edge → settled in new state

    def shift_command(self, cmd):
        """Shift a 5-bit ISP command in SHIFT state. LSB first."""
        if self.verbose:
            name = CMD_NAMES.get(cmd, f"0b{cmd:05b}")
            print(f"  [ISP] Shift cmd: {name} ({cmd:05b})")
        for i in range(CMD_BITS):
            bit = (cmd >> i) & 1
            self._clock(mode_h=False, sdi_h=bool(bit))

    def _shift_data_in(self, data, nbits):
        """Shift data INTO the device in EXECUTE state. LSB first."""
        for i in range(nbits):
            bit = (data >> i) & 1
            self._clock(mode_h=False, sdi_h=bool(bit))

    def _shift_data_out(self, nbits):
        """Shift data OUT of the device. Returns integer, LSB first."""
        result = 0
        for i in range(nbits):
            sdo = self._clock(mode_h=False, sdi_h=False)
            result |= (sdo << i)
        return result

    def _execute(self, wait_time=0):
        """Start execution of loaded command, optionally wait."""
        self._clock(mode_h=False, sdi_h=False)
        if wait_time > 0:
            time.sleep(wait_time)

    # ---- High-level ISP Operations ----

    def get_id(self):
        """Read 8-bit device ID. Returns integer (0x15 for ispLSI 2032).

        From Data Book p.8-37:
          Phase 1: MODE=H, SDI=L, 1 clock -> loads ID into shift register
          Phase 2: MODE=L, SDI=H, 8 clocks -> shifts ID out on SDO (LSB first)
        """
        self.goto_idle()
        # Phase 1: Load ID
        self._clock(mode_h=True, sdi_h=False)
        # Phase 2: Shift out 8 bits
        bits = []
        for i in range(DEVICE_ID_BITS):
            sdo = self._clock(mode_h=False, sdi_h=True)
            bits.append(sdo)
        # Reconstruct byte (LSB first)
        dev_id = 0
        for i, b in enumerate(bits):
            dev_id |= (b << i)
        return dev_id

    def bulk_erase(self):
        """Bulk erase (UBE) — clears fuses + security cell. Waits 300ms."""
        if self.verbose:
            print("  [ISP] Bulk erase (UBE)...")
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(UBE)
        self.change_state()                      # SHIFT -> EXECUTE
        self._execute(wait_time=T_BEW)           # Execute + wait 300ms
        self.goto_idle()
        if self.verbose:
            print("  [ISP] Bulk erase done")

    def _load_address(self, row):
        """Load 102-bit row address via ADDSHFT. Walking-1 selects row."""
        addr = 1 << row
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(ADDSHFT)
        self.change_state()                      # SHIFT -> EXECUTE
        self._shift_data_in(addr, ADDR_SR_BITS)  # 102-bit address

    def read_row(self, row):
        """Read one row. Returns (high_40bits, low_40bits) tuple.

        Sequence:
          1. ADDSHFT + 102-bit address (walking-1)
          2. VER/LDH + execute + wait tpwv -> loads HIGH into shift reg
          3. DATASHFT + shift out 40-bit HIGH
          4. VER/LDL + execute + wait tpwv -> loads LOW into shift reg
          5. DATASHFT + shift out 40-bit LOW
        """
        # 1. Load address
        self._load_address(row)

        # 2. VER/LDH — load high order data
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(VERLDH)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWV)           # Load data, wait tpwv

        # 3. DATASHFT — shift out HIGH
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        data_h = self._shift_data_out(DATA_SR_HIGH)

        # 4. VER/LDL — load low order data
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(VERLDL)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWV)

        # 5. DATASHFT — shift out LOW
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        data_l = self._shift_data_out(DATA_SR_LOW)

        return (data_h, data_l)

    def read_all(self):
        """Read all 102 rows. Returns list of 102 (high, low) tuples."""
        rows = []
        for r in range(NUM_ROWS):
            rows.append(self.read_row(r))
        return rows

    def write_row(self, row, high_40bits, low_40bits):
        """Program one row (both high and low halves).

        Sequence:
          1. ADDSHFT + 102-bit address
          2. DATASHFT + shift in 40-bit HIGH data
          3. PRGMH + execute + wait tpwp (160ms)
          4. DATASHFT + shift in 40-bit LOW data
          5. PRGML + execute + wait tpwp (160ms)
        """
        # 1. Load address
        self._load_address(row)

        # 2. DATASHFT — shift in HIGH order data
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        self._shift_data_in(high_40bits, DATA_SR_HIGH)

        # 3. PRGMH — program high order
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(PRGMH)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWP)           # Wait 200ms

        # 4. DATASHFT — shift in LOW order data
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        self._shift_data_in(low_40bits, DATA_SR_LOW)

        # 5. PRGML — program low order
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(PRGML)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWP)           # Wait 200ms

    def write_all(self, rows):
        """Program all 102 rows from list of (high, low) tuples.
        Skips rows that are already erased (all 1s) for speed.
        """
        programmed = 0
        skipped = 0
        for r, (h, l) in enumerate(rows):
            if h == ERASED_HIGH and l == ERASED_LOW:
                skipped += 1
                continue
            if self.verbose:
                print(f"  [ISP] Programming row {r:3d}: "
                      f"H=0x{h:010X} L=0x{l:010X}")
            self.write_row(r, h, l)
            programmed += 1
        return programmed, skipped

    def verify_row(self, row, high_40bits, low_40bits):
        """Read back a row and compare. Returns True if match."""
        rd_h, rd_l = self.read_row(row)
        ok = (rd_h == high_40bits and rd_l == low_40bits)
        if not ok and self.verbose:
            print(f"  [ISP] VERIFY FAIL row {row:3d}:")
            print(f"    Expected H=0x{high_40bits:010X} L=0x{low_40bits:010X}")
            print(f"    Got      H=0x{rd_h:010X} L=0x{rd_l:010X}")
        return ok

    def flowthru_test(self):
        """Send 0xA5 through FLOWTHRU (bypass). Returns received byte."""
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(FLOWTHRU)
        self.change_state()                      # SHIFT -> EXECUTE
        # In EXECUTE with FLOWTHRU: SDI passes to SDO
        test_val = 0xA5
        result = 0
        for i in range(8):
            bit = (test_val >> i) & 1
            sdo = self._clock(mode_h=False, sdi_h=bool(bit))
            result |= (sdo << i)
        self.goto_idle()
        return result


def fmt_hex(val, bits):
    """Format value as hex with appropriate width."""
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"
