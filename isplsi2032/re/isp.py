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

import os
import sys
import time
from pyftdi.ftdi import Ftdi


def check_ftdi_drivers():
    """Check if kernel ftdi_sio/usbserial modules are loaded.
    These grab the FT2232H before pyftdi (libusb) can use it.
    Exits with clear message if found."""
    blockers = []
    try:
        with open('/proc/modules', 'r') as f:
            for line in f:
                mod = line.split()[0]
                if mod in ('ftdi_sio', 'usbserial'):
                    blockers.append(mod)
    except (FileNotFoundError, PermissionError):
        return  # not Linux or can't check — skip silently
    if blockers:
        print(f"ERROR: Kernel module(s) loaded: {', '.join(blockers)}")
        print(f"  These grab the FTDI device before libusb/pyftdi can.")
        print(f"  Fix:  sudo rmmod {' '.join(blockers)}")
        print(f"  Or blacklist in /etc/modprobe.d/ftdi.conf:")
        print(f"    blacklist ftdi_sio")
        print(f"    blacklist usbserial")
        sys.exit(1)

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
        check_ftdi_drivers()
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

    def _buf_change_state(self, buf, read_sdo=False):
        """Append change_state (2 clocks: HH + LX) to buffer.

        If read_sdo=True, captures SDO from the LX clock (bit 0 of data).
        """
        self._buf_clock(buf, mode_h=True, sdi_h=True)             # HH -> advance
        self._buf_clock(buf, mode_h=False, sdi_h=False, read_sdo=read_sdo)  # LX -> settle

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

        DATASHFT execute just selects the data SR for shifting — it doesn't
        shift. All 40 bits come from subsequent MODE=L clocks.
        """
        results = []
        for cmd in (VERLDH, VERLDL):
            buf = bytearray()
            # 1. ADDSHFT + address
            self._buf_goto_idle(buf)
            self._buf_change_state(buf)
            self._buf_shift_command(buf, ADDSHFT)
            self._buf_change_state(buf)        # SHIFT -> EXECUTE
            addr = 1 << row
            self._buf_shift_data_in(buf, addr, ADDR_SR_BITS)
            # 2. VER/LDH or VER/LDL
            self._buf_goto_idle(buf)
            self._buf_change_state(buf)
            self._buf_shift_command(buf, cmd)
            self._buf_change_state(buf)        # SHIFT -> EXECUTE (triggers verify)
            # Flush address + verify command, wait for E²CMOS load
            self.ftdi.write_data(bytes(buf))
            time.sleep(T_PWV)
            # 3. DATASHFT + read out 40 bits
            #    DATASHFT execute selects data SR; all 40 bits from MODE=L clocks
            buf2 = bytearray()
            self._buf_goto_idle(buf2)
            self._buf_change_state(buf2)
            self._buf_shift_command(buf2, DATASHFT)
            self._buf_change_state(buf2)  # -> EXECUTE (no shift, just selects SR)
            self._buf_shift_data_out(buf2, DATA_SR_HIGH)  # all 40 bits
            bits = self._flush_and_read(buf2, DATA_SR_HIGH)  # 40 reads
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

        Two clocks: HH (advance state) + LX (settle into new state).
        The LX clock returns SDO — important for data readout!
        In EXECUTE state, this LX clock also triggers command execution
        and shifts the data register by 1 position.
        """
        self._clock(mode_h=True, sdi_h=True)    # HH -> advance state
        return self._clock(mode_h=False, sdi_h=False)  # LX -> settle; returns SDO

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

        Protocol:
          1. HL clock — goes to IDLE, loads ID, bit 0 shifts to SR output
             (but MODE=H bypasses SDO to SDI, so we can't read it yet)
          2. Switch MODE=L without clocking — SDO mux flips to register output
             Now we can read bit 0 without shifting the register further.
          3. 7 MODE=L clocks — shift out bits 1-7
        """
        # HL clock: load ID register, bit 0 at SR output (bypassed by MODE=H)
        val = nSRST | MODE                      # MODE=H, SDI=L
        self._pins(val)                          # setup
        self._pins(val | SCLK)                   # rising edge (loads ID)
        self._pins(val)                          # falling edge
        # Switch MODE=L without clocking — read bit 0 from register output
        self._pins(nSRST)                        # MODE=L, SCLK stays low
        pins = self._read()
        bit0 = 1 if (pins & SDO) else 0
        bits = [bit0]
        # Shift out bits 1-7 with MODE=L clocks
        for i in range(DEVICE_ID_BITS - 1):
            sdo = self._clock(mode_h=False, sdi_h=False)
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
        self.change_state()                      # -> EXECUTE (triggers verify)
        time.sleep(T_PWV)                        # wait for E²CMOS load

        # 3. DATASHFT — shift out HIGH (40 bits)
        #    DATASHFT execute just selects the data SR — no shift happens.
        #    All 40 bits come from subsequent MODE=L clocks.
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE (selects data SR)
        data_h = self._shift_data_out(DATA_SR_HIGH)  # all 40 bits

        # 4. VER/LDL — load low order data
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(VERLDL)
        self.change_state()                      # -> EXECUTE (triggers verify)
        time.sleep(T_PWV)                        # wait for E²CMOS load

        # 5. DATASHFT — shift out LOW (40 bits)
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE (selects data SR)
        data_l = self._shift_data_out(DATA_SR_LOW)  # all 40 bits

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
        #    The SR has 2 positions for dedicated input pins (I0, I1) at the
        #    LSB end — not programmable fuses. Shift data left by 2 to align
        #    fuse bits with their correct SR positions.
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        self._shift_data_in((high_40bits << 2) & 0xFFFFFFFFFF, DATA_SR_HIGH)

        # 3. PRGMH — program high order
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(PRGMH)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWP)           # trigger program + wait 200ms

        # 4. DATASHFT — shift in LOW order data (same 2-bit alignment)
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # -> EXECUTE
        self._shift_data_in((low_40bits << 2) & 0xFFFFFFFFFF, DATA_SR_LOW)

        # 5. PRGML — program low order
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(PRGML)
        self.change_state()                      # -> EXECUTE
        self._execute(wait_time=T_PWP)           # trigger program + wait 200ms

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
        self.change_state()                      # -> EXECUTE
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


# ---- CLI ----

def cmd_test(args):
    """Self-test: ID + FLOWTHRU + erased read spot-check."""
    isp = ISP2032(verbose=args.verbose)
    try:
        isp.enter_isp()
        errors = 0

        # 1. Device ID
        dev_id = isp.get_id()
        id_ok = (dev_id == 0x15)
        print(f"Device ID: {fmt_hex(dev_id, 8)} {'OK' if id_ok else 'FAIL (expected 0x15)'}")
        if not id_ok:
            # Read again to check consistency
            dev_id2 = isp.get_id()
            print(f"  Re-read:  {fmt_hex(dev_id2, 8)}")
            errors += 1

        # 2. FLOWTHRU
        ft = isp.flowthru_test()
        ft_ok = (ft == 0xA5)
        print(f"FLOWTHRU:  {fmt_hex(ft, 8)} {'OK' if ft_ok else 'FAIL (expected 0xA5)'}")
        if not ft_ok:
            errors += 1

        # 3. Read rows 0, 50, 101 — report what we see
        print(f"Spot-read rows 0, 50, 101:")
        for r in [0, 50, 101]:
            h, l = isp.read_row_fast(r)
            h_str = "ERASED" if h == ERASED_HIGH else fmt_hex(h, 40)
            l_str = "ERASED" if l == ERASED_LOW else fmt_hex(l, 40)
            print(f"  Row {r:3d}: H={h_str}  L={l_str}")

        # 4. Read row 0 with slow (unbuffered) path and compare
        h_fast, l_fast = isp.read_row_fast(0)
        h_slow, l_slow = isp.read_row(0)
        match = (h_fast == h_slow and l_fast == l_slow)
        print(f"Fast vs slow read row 0: {'MATCH' if match else 'MISMATCH!'}")
        if not match:
            print(f"  Fast: H={fmt_hex(h_fast,40)} L={fmt_hex(l_fast,40)}")
            print(f"  Slow: H={fmt_hex(h_slow,40)} L={fmt_hex(l_slow,40)}")
            errors += 1

        isp.exit_isp()
        print(f"\nResult: {'PASS' if errors == 0 else f'FAIL ({errors} errors)'}")
        return 0 if errors == 0 else 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        isp.close()


def cmd_erase(args):
    """Bulk erase (UBE) + verify erased."""
    isp = ISP2032(verbose=args.verbose)
    try:
        isp.enter_isp()

        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}")

        print("Erasing (UBE)...")
        isp.bulk_erase()
        print("Done. Verifying...")

        errors = 0
        for r in range(NUM_ROWS):
            h, l = isp.read_row_fast(r)
            if h != ERASED_HIGH or l != ERASED_LOW:
                print(f"  Row {r:3d} NOT erased: H={fmt_hex(h,40)} L={fmt_hex(l,40)}")
                errors += 1

        isp.exit_isp()
        if errors == 0:
            print(f"All {NUM_ROWS} rows erased. OK")
        else:
            print(f"FAIL: {errors} rows not erased!")
        return 0 if errors == 0 else 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        isp.close()


def cmd_read(args):
    """Read all fuses, save to .fuse + .txt files."""
    isp = ISP2032(verbose=args.verbose)
    try:
        isp.enter_isp()

        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}")

        print(f"Reading {NUM_ROWS} rows...")
        t0 = time.time()
        rows = []
        programmed = 0
        for r in range(NUM_ROWS):
            h, l = isp.read_row_fast(r)
            rows.append((h, l))
            if h != ERASED_HIGH or l != ERASED_LOW:
                programmed += 1
            if (r + 1) % 20 == 0 or r == NUM_ROWS - 1:
                print(f"  {r+1:3d}/{NUM_ROWS}", end="\r")
        elapsed = time.time() - t0
        print(f"\nDone in {elapsed:.1f}s  ({programmed} programmed rows)")

        isp.exit_isp()

        # Save files
        fuse_file = args.output
        txt_file = fuse_file.rsplit('.', 1)[0] + '.txt'

        # Binary: 102 rows x 10 bytes
        buf = bytearray()
        for h, l in rows:
            buf.extend(h.to_bytes(5, byteorder='big'))
            buf.extend(l.to_bytes(5, byteorder='big'))
        with open(fuse_file, 'wb') as f:
            f.write(bytes(buf))

        # Text
        with open(txt_file, 'w') as f:
            f.write(f"# ispLSI 2032 fuse dump — {NUM_ROWS} rows x 80 bits\n")
            f.write(f"# Format: ROW  HIGH_40bit  LOW_40bit\n")
            f.write(f"# Erased = 0x3FFFFFFFFF, Programmed fuse = 0\n#\n")
            for r, (h, l) in enumerate(rows):
                marker = "  *" if (h != ERASED_HIGH or l != ERASED_LOW) else ""
                f.write(f"{r:3d}  0x{h:010X}  0x{l:010X}{marker}\n")

        print(f"Saved: {fuse_file} ({len(buf)} bytes), {txt_file}")

        if programmed > 0:
            print(f"\nProgrammed rows:")
            for r, (h, l) in enumerate(rows):
                if h != ERASED_HIGH or l != ERASED_LOW:
                    print(f"  Row {r:3d}: H=0x{h:010X} L=0x{l:010X}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        isp.close()


def cmd_write_test(args):
    """Write a test pattern to row 0, read back, verify, then erase."""
    isp = ISP2032(verbose=args.verbose)
    try:
        isp.enter_isp()

        dev_id = isp.get_id()
        print(f"Device ID: {fmt_hex(dev_id, 8)}")

        # Patterns to test (38-bit values — top 2 bits must be 0)
        patterns = [
            (0x2AAAAAAAAA, 0x1555555555, "alternating 10/01"),
            (0x1555555555, 0x2AAAAAAAAA, "alternating 01/10"),
            (0x0000000001, 0x0000000001, "single bit low"),
            (0x2000000000, 0x2000000000, "single bit high"),
            (0x0000000000, 0x0000000000, "all programmed"),
        ]

        errors = 0
        for pat_h, pat_l, desc in patterns:
            print(f"\nTest: {desc}")
            print(f"  Erase...")
            isp.bulk_erase()

            print(f"  Write row 0: H={fmt_hex(pat_h,40)} L={fmt_hex(pat_l,40)}")
            isp.write_row(0, pat_h, pat_l)

            h, l = isp.read_row_fast(0)
            ok = (h == pat_h and l == pat_l)
            print(f"  Read back:   H={fmt_hex(h,40)} L={fmt_hex(l,40)}  {'PASS' if ok else 'FAIL'}")
            if not ok:
                errors += 1

        # Multi-row test
        print(f"\nMulti-row test (rows 10-19)...")
        isp.bulk_erase()
        for r in range(10, 20):
            pat = r & 0x3FFFFFFFFF
            isp.write_row(r, pat, ~pat & 0x3FFFFFFFFF)
        multi_err = 0
        for r in range(10, 20):
            pat = r & 0x3FFFFFFFFF
            exp_l = ~pat & 0x3FFFFFFFFF
            h, l = isp.read_row_fast(r)
            if h != pat or l != exp_l:
                print(f"  Row {r}: FAIL (H={fmt_hex(h,40)} L={fmt_hex(l,40)})")
                multi_err += 1
        if multi_err == 0:
            print(f"  All 10 rows: PASS")
        errors += multi_err

        # Cleanup
        print(f"\nFinal erase...")
        isp.bulk_erase()

        isp.exit_isp()
        print(f"\nResult: {'PASS' if errors == 0 else f'FAIL ({errors} errors)'}")
        return 0 if errors == 0 else 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        isp.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='ispLSI 2032 ISP tool — run on HOST with FT2232H',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python3 isp.py --test          # ID + FLOWTHRU + spot read
  python3 isp.py --erase         # bulk erase + verify
  python3 isp.py --read          # dump all fuses to file
  python3 isp.py --write-test    # write/read pattern test
""")
    parser.add_argument('--test', action='store_true',
                        help='Self-test: ID, FLOWTHRU, spot-read')
    parser.add_argument('--erase', action='store_true',
                        help='Bulk erase + verify all rows erased')
    parser.add_argument('--read', action='store_true',
                        help='Read all fuses to file')
    parser.add_argument('--write-test', action='store_true',
                        help='Write/read pattern test (erases chip!)')
    parser.add_argument('-o', '--output', default='dump.fuse',
                        help='Output file for --read (default: dump.fuse)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose ISP output')
    args = parser.parse_args()

    if not any([args.test, args.erase, args.read, args.write_test]):
        parser.print_help()
        return 1

    if args.test:
        return cmd_test(args)
    elif args.erase:
        return cmd_erase(args)
    elif args.read:
        return cmd_read(args)
    elif args.write_test:
        return cmd_write_test(args)


if __name__ == '__main__':
    sys.exit(main())
