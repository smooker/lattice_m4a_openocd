#!/usr/bin/env python3
"""
Bit-bang ISP v6 — Correct 3-state ISP protocol from 1996 Lattice Data Book.

KEY INSIGHT: The plain ispLSI 2032 does NOT use IEEE 1149.1 JTAG!
It uses Lattice's proprietary 3-state ISP state machine:

    IDLE/ID  --HH-->  SHIFT  --HH-->  EXECUTE
       ^  HL↺         LX↺              LX↺
       └----HL---------┘         └--HL--┘

State transitions happen on SCLK rising edge:
  H=HIGH, L=LOW, X=don't care. First=MODE, second=SDI.
  HH = advance to next state
  HL = return to IDLE
  LX = stay in current state (shift data / continue execution)

Protocol (from Data Book pp.8-2, 8-3, 8-32, 8-33):
  - Device ID is read in IDLE state, no command needed (8 clocks, MODE=H, SDI=L)
  - Commands are 5-bit, shifted in SHIFT state (MODE=L), LSB first
  - ADDSHFT/DATASHFT execute with data clocking (MODE=L in EXECUTE)
  - PRGM/ERASE execute with wait time (single clock then wait)

Previous scripts (v1-v5) were wrong:
  - Tried JTAG TAP (wrong protocol entirely)
  - Used MODE=HIGH as execute state (wrong: MODE=HIGH is for transitions)
  - The "8-bit IR" measured was the device ID, not an IR length

Run on HOST (needs pyftdi + libusb):
  sudo rmmod ftdi_sio
  python3 bitbang_isp6.py
"""

import sys
import time
from pyftdi.ftdi import Ftdi

FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000  # 100 kHz

# ADBUS pins
SCLK  = 0x01  # bit 0 — serial clock (-> chip pin 27)
SDI   = 0x02  # bit 1 — serial data in (-> chip pin 8)
SDO   = 0x04  # bit 2 — serial data out, INPUT (-> chip pin 18)
MODE  = 0x08  # bit 3 — state machine control (-> chip pin 30)
nSRST = 0x10  # bit 4 — active low reset (-> chip pin 29)
ispEN = 0x20  # bit 5 — active low ISP enable (-> chip pin 7)
DIR   = SCLK | SDI | MODE | nSRST | ispEN  # 0x3B

# ISP Instructions (5-bit, Table 4, p.8-11)
NOP      = 0b00000
ADDSHFT  = 0b00001
DATASHFT = 0b00010
UBE      = 0b00011  # User Bulk Erase (clears security!)
ERALL    = 0b10000  # Erase All (incl. UES)
GRPBE    = 0b00100
GLBBE    = 0b00101
ARCHBE   = 0b00110
PRGMH    = 0b00111  # Program High Order
PRGML    = 0b01000  # Program Low Order
PRGMSC   = 0b01001  # Program Security Cell (one-way!)
VERLDH   = 0b01010  # Verify/Load High Order
VERLDL   = 0b01011  # Verify/Load Low Order
FLOWTHRU = 0b01110  # Bypass (SDI -> SDO)
VELDH    = 0b10010  # Verify Erase High
VELDL    = 0b10011  # Verify Erase Low
PROGUES  = 0b01111  # Program UES
VERUES   = 0b10001  # Verify UES

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
T_CLKH  = 0.000002 # tclkh: 0.5 us min (we use 2 us)
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


class ISP:
    """Low-level 3-state ISP state machine controller."""

    def __init__(self):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST | ispEN)
        self._pins(nSRST | ispEN)  # Safe: ISP disabled, reset inactive
        self.verbose = True

    def close(self):
        self._pins(nSRST | ispEN)
        time.sleep(0.01)
        self.ftdi.close()

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
        Returns SDO value read after falling edge.

        Per Data Book timing (p.8-13, Figure 9):
          1. Set MODE and SDI (setup time tsu before SCLK rising)
          2. SCLK rising edge (state machine samples MODE+SDI)
          3. SCLK high for tclkh
          4. SCLK falling edge
          5. SDO valid after tco from falling edge
          6. Read SDO
        """
        val = nSRST
        if mode_h: val |= MODE
        if sdi_h:  val |= SDI
        # Setup: MODE + SDI stable, SCLK low
        self._pins(val)
        # Rising edge
        self._pins(val | SCLK)
        # Hold high (tclkh)
        # Falling edge
        self._pins(val)
        # Read SDO after falling edge (tco)
        pins = self._read()
        return 1 if (pins & SDO) else 0

    # ---- ISP State Machine Operations ----

    def enter_isp(self):
        """Enter ISP Edit Mode.

        From Data Book p.8-2, p.8-13 (Figure 9):
        1. Power with ispEN HIGH (normal operation)
        2. Toggle RESET for clean state
        3. Pull ispEN LOW -> Edit Mode
        4. I/O pins go high-impedance
        """
        # Start safe
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

        From Data Book p.8-32 (Goto_IDLE Procedure):
          MODE=H, SDI=L + clock -> always goes to IDLE
        """
        self._clock(mode_h=True, sdi_h=False)  # HL -> IDLE
        if self.verbose:
            print("  [ISP] -> IDLE")

    def get_id(self):
        """Read 8-bit device ID in IDLE state.

        From Data Book p.8-37 (Load_ID + Shift_ID Procedures):
          Phase 1: MODE=H, SDI=L + 1 clock -> LOADS ID into shift register
          Phase 2: MODE=L, SDI=H + 7 clocks -> SHIFTS ID out on SDO (LSB first)
          (MODE=H makes SDO=SDI bypass; MODE=L routes shift register to SDO)

          "Only seven clock cycles are required, since the first bit is
           available on SDO after the ID is loaded." (p.8-3)
        """
        # Phase 1: Load ID (one clock, MODE=H, SDI=L)
        self._clock(mode_h=True, sdi_h=False)

        # Phase 2: Shift out 8 bits (MODE=L to route SR to SDO)
        # SDI=H fills chain with 1s for end-of-chain detection
        bits = []
        for i in range(DEVICE_ID_BITS):
            sdo = self._clock(mode_h=False, sdi_h=True)  # MODE=L shifts out
            bits.append(sdo)

        # Reconstruct byte (LSB first)
        dev_id = 0
        for i, b in enumerate(bits):
            dev_id |= (b << i)
        return dev_id

    def change_state(self):
        """Advance to next state: IDLE->SHIFT or SHIFT->EXECUTE.

        From Data Book p.8-32 (Change_State Procedure):
          MODE=H, SDI=H + clock  (HH = advance)
          Then MODE=L, SDI=L + clock (settle into new state)
        """
        self._clock(mode_h=True, sdi_h=True)    # HH -> advance
        self._clock(mode_h=False, sdi_h=False)   # LX -> settle
        # Note: the second clock isn't in the Data Book procedure explicitly
        # but is needed to settle the state (we enter with MODE=L ready to shift)

    def shift_command(self, cmd):
        """Shift a 5-bit ISP command in SHIFT state. LSB first.

        From Data Book p.8-33 (Shift_Command Procedure):
          MODE=L, clock 5 bits of command via SDI
        """
        name = CMD_NAMES.get(cmd, f"0b{cmd:05b}")
        if self.verbose:
            print(f"  [ISP] Shift cmd: {name} ({cmd:05b})")
        for i in range(CMD_BITS):
            bit = (cmd >> i) & 1
            self._clock(mode_h=False, sdi_h=bool(bit))  # LX = stay in SHIFT

    def shift_data_in(self, data, nbits):
        """Shift data INTO the device (in EXECUTE state for ADDSHFT/DATASHFT).

        From Data Book p.8-33 (Shift_Data_In Procedure):
          MODE=L, clock N bits of data via SDI. LSB first.
        """
        if self.verbose:
            print(f"  [ISP] Shift {nbits} bits IN")
        for i in range(nbits):
            bit = (data >> i) & 1
            self._clock(mode_h=False, sdi_h=bool(bit))

    def shift_data_out(self, nbits):
        """Shift data OUT of the device. Returns integer, LSB first.

        From Data Book p.8-33 (Shift_Data_Out Procedure):
          MODE=L, clock N times, read SDO each time.
        """
        if self.verbose:
            print(f"  [ISP] Shift {nbits} bits OUT")
        result = 0
        for i in range(nbits):
            sdo = self._clock(mode_h=False, sdi_h=False)
            result |= (sdo << i)
        return result

    def execute_command(self, wait_time=0):
        """Start execution of loaded command. Optionally wait for completion.

        From Data Book p.8-33 (Execute_Command Procedure):
          MODE=L, SDI=L + clock -> starts operation in EXECUTE state
          Wait for required time (tpwp, tbew, tpwv)
        """
        self._clock(mode_h=False, sdi_h=False)
        if wait_time > 0:
            time.sleep(wait_time)

    # ---- High-level ISP Operations ----

    def isp_read_id(self):
        """Full ID read sequence: goto IDLE, read ID."""
        self.goto_idle()
        dev_id = self.get_id()
        return dev_id

    def isp_bulk_erase(self):
        """Bulk erase (UBE) — clears everything including security fuse.

        Sequence:
          IDLE -> SHIFT: Change_State
          SHIFT: load UBE (00011)
          SHIFT -> EXECUTE: Change_State
          EXECUTE: start + wait tbew
          EXECUTE -> IDLE: HL clock
        """
        print("\n  --- BULK ERASE (UBE) ---")
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(UBE)                  # Load UBE command
        self.change_state()                      # SHIFT -> EXECUTE
        self.execute_command(wait_time=T_BEW)    # Execute + wait 300ms
        self.goto_idle()                         # Back to IDLE
        print("  --- BULK ERASE DONE ---\n")

    def isp_verify_row(self, row, high=True):
        """Read back one half of a row via VER/LDH or VER/LDL.

        Sequence:
          1. ADDSHFT: load 102-bit row address (walking 1)
          2. VER/LDH or VER/LDL: execute (loads data into shift register)
          3. DATASHFT: shift out 40 bits
        """
        # Build 102-bit address with bit 'row' set
        addr = 1 << row

        # ADDSHFT
        self.goto_idle()
        self.change_state()                      # -> SHIFT
        self.shift_command(ADDSHFT)
        self.change_state()                      # -> EXECUTE
        self.shift_data_in(addr, ADDR_SR_BITS)   # 102 bits

        # VER/LDH or VER/LDL
        self.change_state()                      # -> back? We need SHIFT
        # Actually: from EXECUTE, HH stays in EXECUTE or goes back...
        # Let's go EXECUTE -> IDLE -> SHIFT instead
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        cmd = VERLDH if high else VERLDL
        self.shift_command(cmd)
        self.change_state()                      # SHIFT -> EXECUTE
        self.execute_command(wait_time=T_PWV)    # Load data, wait tpwv

        # DATASHFT to read out
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(DATASHFT)
        self.change_state()                      # SHIFT -> EXECUTE
        nbits = DATA_SR_HIGH if high else DATA_SR_LOW
        data = self.shift_data_out(nbits)

        return data

    def isp_flowthru_test(self):
        """Test FLOWTHRU (bypass) — should pass SDI directly to SDO.

        If this works, the ISP state machine is responding to commands.
        """
        self.goto_idle()
        self.change_state()                      # IDLE -> SHIFT
        self.shift_command(FLOWTHRU)
        self.change_state()                      # SHIFT -> EXECUTE
        # In EXECUTE with FLOWTHRU: SDI should appear on SDO
        # Shift a test pattern and read back
        test_val = 0xA5
        result = 0
        for i in range(8):
            bit = (test_val >> i) & 1
            sdo = self._clock(mode_h=False, sdi_h=bool(bit))
            result |= (sdo << i)
        self.goto_idle()
        return result


def fmt(val, bits):
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"


def fmt_bin(val, bits):
    return f"{val:0{bits}b}"


def main():
    print("=" * 70)
    print("ispLSI 2032 — ISP Probe v6")
    print("Correct 3-state ISP protocol from 1996 Lattice Data Book")
    print("=" * 70)
    print()
    print("Protocol: IDLE --HH--> SHIFT --HH--> EXECUTE")
    print("  HH = MODE=H, SDI=H (advance state)")
    print("  HL = MODE=H, SDI=L (go to IDLE)")
    print("  LX = MODE=L (shift data / stay)")
    print()

    isp = ISP()
    print("FT2232H connected.\n")

    try:
        # ============================================================
        # TEST 1: Read Device ID
        # ============================================================
        print("=" * 70)
        print("TEST 1: Read Device ID (in IDLE state, MODE=H SDI=L)")
        print("  Expected: 0x15 (00010101) for ispLSI 2032")
        print("=" * 70)

        isp.enter_isp()

        dev_id = isp.isp_read_id()
        print(f"\n  Device ID = {fmt(dev_id, 8)} = {fmt_bin(dev_id, 8)}")
        if dev_id == 0x15:
            print("  *** MATCH! ispLSI 2032 confirmed! ***")
        else:
            print(f"  WARNING: expected 0x15, got {fmt(dev_id, 8)}")

        # Read it again to make sure it's consistent
        dev_id2 = isp.isp_read_id()
        print(f"  Re-read:  {fmt(dev_id2, 8)} = {fmt_bin(dev_id2, 8)}"
              f" {'(consistent)' if dev_id == dev_id2 else '*** INCONSISTENT ***'}")

        isp.exit_isp()

        # ============================================================
        # TEST 2: FLOWTHRU (bypass) test
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 2: FLOWTHRU command — test if ISP accepts commands")
        print("  Send 0xA5 through bypass, expect 0xA5 back on SDO")
        print("=" * 70)

        isp.enter_isp()
        isp.goto_idle()

        result = isp.isp_flowthru_test()
        print(f"\n  FLOWTHRU: sent 0xA5, got {fmt(result, 8)}")
        if result == 0xA5:
            print("  *** FLOWTHRU WORKS! ISP state machine accepts commands! ***")
        else:
            print(f"  FLOWTHRU mismatch (got {fmt(result, 8)} instead of 0xA5)")
            print("  Note: may need 1-bit pipeline delay, trying shifted...")
            # Try with 1-bit delay (common in shift registers)
            if (result & 0xFF) == 0x4A or (result & 0xFF) == 0xD2:
                print(f"  Shifted by 1 bit? 0xA5>>1=0x52, 0xA5<<1=0x4A")

        isp.exit_isp()

        # ============================================================
        # TEST 3: Bulk Erase (UBE)
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 3: UBE (User Bulk Erase)")
        print("  'The only way to erase the security cell is UBE'")
        print("  Erases entire device including security fuse.")
        print("  Wait 300ms (tbew=200ms min)")
        print("=" * 70)

        isp.enter_isp()

        # Read ID before
        id_before = isp.isp_read_id()
        print(f"\n  ID before UBE: {fmt(id_before, 8)}")

        # Do bulk erase
        isp.isp_bulk_erase()

        # Read ID after
        id_after = isp.isp_read_id()
        print(f"  ID after UBE:  {fmt(id_after, 8)}")

        if id_before != id_after:
            print("  *** ID CHANGED after UBE! ***")
        else:
            print("  ID unchanged (expected if chip was already erased)")

        # Test FLOWTHRU again after erase
        ft_after = isp.isp_flowthru_test()
        print(f"  FLOWTHRU after UBE: {fmt(ft_after, 8)}")

        isp.exit_isp()

        # ============================================================
        # TEST 4: Try to read fuse data (VER/LDH + VER/LDL)
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 4: Read fuse data — row 0 (VER/LDH + VER/LDL)")
        print("  If erased, all bits should be 1 (open connections)")
        print("=" * 70)

        isp.enter_isp()

        print("\n  Reading row 0, high order (40 bits)...")
        data_h = isp.isp_verify_row(0, high=True)
        print(f"  Row 0 HIGH: {fmt(data_h, 40)}")
        print(f"             = {fmt_bin(data_h, 40)}")

        print("\n  Reading row 0, low order (40 bits)...")
        data_l = isp.isp_verify_row(0, high=False)
        print(f"  Row 0 LOW:  {fmt(data_l, 40)}")
        print(f"             = {fmt_bin(data_l, 40)}")

        if data_h == 0 and data_l == 0:
            print("\n  All zeros — chip may still be locked (no data returned)")
        elif data_h == (1 << 40) - 1 and data_l == (1 << 40) - 1:
            print("\n  *** ALL ONES — chip is erased and readable! ***")
        else:
            print(f"\n  Non-trivial data — chip IS responding with fuse content!")

        # Also try a few more rows
        print("\n  Quick scan of rows 0, 1, 50, 101:")
        for row in [0, 1, 50, 101]:
            isp.verbose = False
            dh = isp.isp_verify_row(row, high=True)
            dl = isp.isp_verify_row(row, high=False)
            isp.verbose = True
            h_str = "all-1" if dh == (1<<40)-1 else "all-0" if dh == 0 else fmt(dh, 40)
            l_str = "all-1" if dl == (1<<40)-1 else "all-0" if dl == 0 else fmt(dl, 40)
            print(f"  Row {row:3d}: H={h_str}  L={l_str}")

        isp.exit_isp()

        # ============================================================
        # TEST 5: Also try ERALL (erases UES too) as fallback
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 5: ERALL (Erase All including UES)")
        print("  Fallback in case UBE alone isn't enough")
        print("=" * 70)

        isp.enter_isp()

        # ERALL
        print("\n  --- ERALL ---")
        isp.goto_idle()
        isp.change_state()                       # -> SHIFT
        isp.shift_command(ERALL)
        isp.change_state()                       # -> EXECUTE
        isp.execute_command(wait_time=T_BEW)
        isp.goto_idle()
        print("  --- ERALL DONE ---")

        # Check
        dev_id = isp.isp_read_id()
        print(f"\n  ID after ERALL: {fmt(dev_id, 8)}")
        ft = isp.isp_flowthru_test()
        print(f"  FLOWTHRU after ERALL: {fmt(ft, 8)}")

        isp.exit_isp()

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Device ID:     {fmt(dev_id, 8)} {'(0x15 = ispLSI 2032)' if dev_id == 0x15 else ''}")
        print(f"  FLOWTHRU test: {'PASS' if ft == 0xA5 else 'FAIL'} (got {fmt(ft, 8)})")
        print()
        print("If FLOWTHRU returns 0xA5 — ISP state machine works!")
        print("If fuse reads return non-zero — we can read/write the chip!")
        print("If everything is zeros — security fuse may still be active,")
        print("  or the 3-state transition timing needs adjustment.")

    finally:
        isp.close()
        print("\nDone.")


if __name__ == '__main__':
    main()
