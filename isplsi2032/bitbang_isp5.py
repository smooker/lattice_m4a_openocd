#!/usr/bin/env python3
"""
Bit-bang ISP probe v5 — UBE (User Bulk Erase) attempt.

Based on 1996 Lattice Data Book, Section 8 "ISP Architecture and Programming":
  - 5-bit ISP state machine instructions (Table 4, p.8-11)
  - UBE (00011) erases entire device INCLUDING security fuse
  - Legacy ISP state machine: IDLE -> SHIFT -> EXECUTE cycle
  - MODE controls state: MODE=0 for shift, MODE=1 for execute
  - tbew (bulk erase pulse) = 200ms minimum

The plain ispLSI 2032 has 8-bit IR (measured), but the Data Book says
5-bit instructions.  We try UBE at various bit widths and paddings.

After each UBE attempt, we check if the chip responds differently
(indicating security fuse was cleared).

Run on HOST (needs pyftdi + libusb):
  sudo rmmod ftdi_sio
  python3 bitbang_isp5.py
"""

import sys
import time
from pyftdi.ftdi import Ftdi

FTDI_URL = 'ftdi://ftdi:2232h/1'
FREQ = 100000

# ADBUS pins
SCLK  = 0x01  # bit 0 — serial clock
SDI   = 0x02  # bit 1 — serial data in
SDO   = 0x04  # bit 2 — serial data out (input)
MODE  = 0x08  # bit 3 — state machine control
nSRST = 0x10  # bit 4 — active low reset
ispEN = 0x20  # bit 5 — active low ISP enable
DIR   = SCLK | SDI | MODE | nSRST | ispEN  # 0x3B

# ISP Instructions (5-bit, from 1996 Data Book Table 4, p.8-11)
ISP_NOP      = 0b00000
ISP_ADDSHFT  = 0b00001
ISP_DATASHFT = 0b00010
ISP_UBE      = 0b00011   # User Bulk Erase (clears security!)
ISP_ERALL    = 0b10000   # Erase All (incl. UES)
ISP_GRPBE    = 0b00100   # GRP Bulk Erase
ISP_GLBBE    = 0b00101   # GLB Bulk Erase
ISP_ARCHBE   = 0b00110   # Architecture Bulk Erase
ISP_PRGMH    = 0b00111   # Program High Order
ISP_PRGML    = 0b01000   # Program Low Order
ISP_PRGMSC   = 0b01001   # Program Security Cell
ISP_VERLDH   = 0b01010   # Verify/Load High
ISP_VERLDL   = 0b01011   # Verify/Load Low
ISP_FLOWTHRU = 0b01110   # Bypass (SDI->SDO)
ISP_VELDH    = 0b10010   # Verify Erase High
ISP_VELDL    = 0b10011   # Verify Erase Low
ISP_PROGUES  = 0b01111   # Program UES
ISP_VERUES   = 0b10001   # Verify UES

# Erase timing from Data Book Table 5 (p.8-12)
T_BEW  = 0.300   # Bulk erase pulse width: 200ms min, we use 300ms
T_PWP  = 0.200   # Programming pulse: 80-160ms, we use 200ms
T_PWV  = 0.001   # Verify pulse: 20us min, we use 1ms
T_SU2  = 0.001   # Setup time for program/erase: 200us min
T_RST  = 0.001   # Reset time from valid Vcc: 45us min


class ISP:
    def __init__(self):
        self.ftdi = Ftdi()
        self.ftdi.open_mpsse_from_url(FTDI_URL, frequency=FREQ,
                                       direction=DIR, initial=nSRST | ispEN)
        self._set(nSRST | ispEN)  # ispEN HIGH, nSRST HIGH (inactive)

    def close(self):
        # Leave chip in safe state: ispEN HIGH (ISP disabled)
        self._set(nSRST | ispEN)
        time.sleep(0.01)
        self.ftdi.close()

    def _set(self, val):
        self.ftdi.write_data(bytes([0x80, val & 0xFF, DIR]))

    def _read(self):
        self.ftdi.write_data(bytes([0x81]))
        d = self.ftdi.read_data_bytes(1, attempt=10)
        return d[0] if d else 0

    def clk(self, sdi, mode):
        """One clock cycle: set SDI/MODE, pulse SCLK, read SDO."""
        val = nSRST
        if sdi:  val |= SDI
        if mode: val |= MODE
        # Setup: SDI and MODE valid before rising SCLK
        self._set(val)
        # Rising edge of SCLK
        self._set(val | SCLK)
        # Read SDO after rising edge
        pins = self._read()
        sdo = 1 if (pins & SDO) else 0
        # Falling edge of SCLK
        self._set(val)
        return sdo

    def shift(self, data, nbits, mode):
        """Shift nbits of data (LSB first), return captured SDO bits."""
        r = 0
        for i in range(nbits):
            sdo = self.clk((data >> i) & 1, mode)
            r |= (sdo << i)
        return r

    def enter_isp(self):
        """Enter ISP mode with proper sequence.

        From Data Book (p.8-13, Figure 9):
        1. Power up with ispEN HIGH
        2. Wait trst (45us min)
        3. Pull ispEN LOW -> enters ISP mode
        4. Wait tispen (10us)
        """
        # Start with everything HIGH (ISP disabled)
        self._set(nSRST | ispEN)
        time.sleep(0.01)

        # Toggle RESET for clean state
        self._set(ispEN)           # nSRST LOW = reset active
        time.sleep(0.05)
        self._set(nSRST | ispEN)   # nSRST HIGH = reset released
        time.sleep(0.05)           # Wait for chip to stabilize

        # Enter ISP: pull ispEN LOW
        self._set(nSRST)           # ispEN LOW = ISP mode active
        time.sleep(0.01)           # Wait tispen (10us min)

    def exit_isp(self):
        """Exit ISP mode: pull ispEN HIGH."""
        self._set(nSRST | ispEN)
        time.sleep(0.01)

    def isp_shift_cmd(self, cmd, nbits, mode=0):
        """Shift a command into the ISP state machine (MODE=0 = SHIFT state)."""
        return self.shift(cmd, nbits, mode=mode)

    def isp_execute(self, duration):
        """Enter EXECUTE state: pulse MODE HIGH for given duration.

        From Data Book (p.8-13, Figure 10):
        MODE goes HIGH, SDI must be valid (don't care for erase).
        SCLK rising edge starts the operation.
        Wait for the required pulse width, then return to SHIFT state.
        """
        # MODE HIGH = EXECUTE state
        val = nSRST | MODE
        self._set(val)
        # Rising edge of SCLK to start execution
        self._set(val | SCLK)
        time.sleep(T_SU2)          # Setup time
        self._set(val)             # SCLK low, MODE still HIGH
        # Wait for the operation to complete
        time.sleep(duration)
        # Return to SHIFT state: MODE LOW
        self._set(nSRST)
        time.sleep(T_SU2)

    def isp_execute_multi_clk(self, duration, nclk=1):
        """Execute with multiple clock edges during MODE=HIGH."""
        val = nSRST | MODE
        self._set(val)
        for _ in range(nclk):
            self._set(val | SCLK)
            time.sleep(0.0001)
            self._set(val)
            time.sleep(0.0001)
        time.sleep(duration)
        self._set(nSRST)
        time.sleep(T_SU2)

    def read_sdo_pattern(self, nbits=16):
        """Read SDO with MODE=0, SDI=0 — check if chip responds."""
        return self.shift(0, nbits, mode=0)


def fmt(val, bits):
    nibbles = max((bits + 3) // 4, 1)
    return f"0x{val:0{nibbles}X}"


def try_ube(isp, cmd_val, cmd_bits, label, execute_dur=T_BEW):
    """Try a UBE command and check if chip state changed."""
    isp.enter_isp()

    # Read SDO before command (baseline)
    before = isp.read_sdo_pattern(16)

    # Shift command (MODE=0 = SHIFT state)
    isp.isp_shift_cmd(cmd_val, cmd_bits, mode=0)

    # Execute (MODE=1 for tbew duration)
    isp.isp_execute(execute_dur)

    # Read SDO after command
    after = isp.read_sdo_pattern(16)

    # Try a verify to see if chip now responds
    isp.isp_shift_cmd(ISP_VERLDH, cmd_bits, mode=0)
    isp.isp_execute(T_PWV)
    verify = isp.read_sdo_pattern(32)

    changed = "***CHANGED***" if before != after else ""
    verify_nz = "***VERIFY NON-ZERO***" if verify != 0 else ""

    print(f"  {label:40s}: before={fmt(before,16)} after={fmt(after,16)} "
          f"verify={fmt(verify,32)} {changed} {verify_nz}")

    isp.exit_isp()
    return before != after or verify != 0


def main():
    print("ispLSI 2032 — UBE Bulk Erase Attempt v5")
    print("Based on 1996 Lattice Data Book, Section 8")
    print("=" * 70)

    isp = ISP()
    print("Connected.\n")

    try:
        # === TEST 0: Baseline — what does the chip output now? ===
        print("=" * 70)
        print("TEST 0: Baseline read (ISP entry + SDO observation)")
        print("=" * 70)

        isp.enter_isp()
        for mode_val in [0, 1]:
            data = isp.read_sdo_pattern(16)
            print(f"  MODE={mode_val}: SDO 16-bit = {fmt(data, 16)} = {data:016b}")
        isp.exit_isp()

        # === TEST 1: UBE with 5-bit instruction (native width) ===
        print("\n" + "=" * 70)
        print("TEST 1: UBE (00011) — 5-bit instruction, 300ms execute")
        print("  This is the NATIVE instruction width from the Data Book")
        print("=" * 70)

        try_ube(isp, ISP_UBE, 5, "UBE 5-bit native")

        # Also try ERALL (10000)
        try_ube(isp, ISP_ERALL, 5, "ERALL 5-bit native")

        # === TEST 2: UBE with 8-bit, various paddings ===
        print("\n" + "=" * 70)
        print("TEST 2: UBE mapped to 8 bits — various padding schemes")
        print("=" * 70)

        paddings = [
            (ISP_UBE,             "UBE=00000011 (zero-pad MSB)"),
            (ISP_UBE << 3,        "UBE=00011000 (shifted left 3)"),
            (ISP_UBE << 1,        "UBE=00000110 (shifted left 1)"),
            (ISP_UBE << 2,        "UBE=00001100 (shifted left 2)"),
            (ISP_UBE | 0xE0,     "UBE=11100011 (high bits set)"),
            (ISP_UBE | 0x60,     "UBE=01100011 (bits 5,6 set)"),
            (0x03,                "plain 0x03"),
            (0x18,                "plain 0x18 (UBE<<3)"),
            (0xC0 | ISP_UBE,     "UBE=11000011 (bits 6,7 set)"),
        ]

        for val, label in paddings:
            try_ube(isp, val, 8, label)

        # Also try ERALL with 8-bit
        erall_pads = [
            (ISP_ERALL,           "ERALL=00010000 (zero-pad MSB)"),
            (ISP_ERALL << 3,      "ERALL=10000000 (shifted left 3)"),
            (ISP_ERALL << 1,      "ERALL=00100000 (shifted left 1)"),
        ]

        for val, label in erall_pads:
            try_ube(isp, val, 8, label)

        # === TEST 3: UBE with longer execute times ===
        print("\n" + "=" * 70)
        print("TEST 3: UBE 5-bit with extended erase times")
        print("  (maybe the chip needs longer than 200ms?)")
        print("=" * 70)

        for dur_ms in [500, 1000, 2000]:
            try_ube(isp, ISP_UBE, 5, f"UBE 5-bit, {dur_ms}ms", dur_ms / 1000.0)

        # === TEST 4: UBE with multiple SCLK edges during execute ===
        print("\n" + "=" * 70)
        print("TEST 4: UBE 5-bit with multiple clock edges during execute")
        print("=" * 70)

        for nclk in [1, 2, 4, 8]:
            isp.enter_isp()
            before = isp.read_sdo_pattern(16)
            isp.isp_shift_cmd(ISP_UBE, 5, mode=0)
            isp.isp_execute_multi_clk(T_BEW, nclk=nclk)
            after = isp.read_sdo_pattern(16)
            changed = "***CHANGED***" if before != after else ""
            print(f"  UBE 5-bit + {nclk} clk(s): before={fmt(before,16)} "
                  f"after={fmt(after,16)} {changed}")
            isp.exit_isp()

        # === TEST 5: Full programming-style sequence ===
        print("\n" + "=" * 70)
        print("TEST 5: Full sequence — NOP, then UBE, per Data Book flow")
        print("  (Some devices need NOP first to sync state machine)")
        print("=" * 70)

        for cmd_bits in [5, 8]:
            isp.enter_isp()
            before = isp.read_sdo_pattern(16)

            # Step 1: NOP to sync
            isp.isp_shift_cmd(ISP_NOP, cmd_bits, mode=0)
            isp.isp_execute(0.001)

            # Step 2: UBE
            isp.isp_shift_cmd(ISP_UBE, cmd_bits, mode=0)
            isp.isp_execute(T_BEW)

            # Step 3: NOP after erase
            isp.isp_shift_cmd(ISP_NOP, cmd_bits, mode=0)
            isp.isp_execute(0.001)

            after = isp.read_sdo_pattern(16)

            # Step 4: Try FLOWTHRU to see if bypass works now
            isp.isp_shift_cmd(ISP_FLOWTHRU, cmd_bits, mode=0)
            isp.isp_execute(0.001)
            isp.shift(0xA5, 8, mode=0)
            flowthru = isp.shift(0, 8, mode=0)

            changed = "***CHANGED***" if before != after else ""
            ft_ok = "***FLOWTHRU OK***" if flowthru == 0xA5 else ""
            print(f"  NOP+UBE+NOP ({cmd_bits}-bit): before={fmt(before,16)} "
                  f"after={fmt(after,16)} flowthru={fmt(flowthru,8)} "
                  f"{changed} {ft_ok}")
            isp.exit_isp()

        # === TEST 6: Try without reset — direct ISP entry ===
        print("\n" + "=" * 70)
        print("TEST 6: ISP entry WITHOUT reset toggle")
        print("  (Maybe reset interferes with ISP state machine?)")
        print("=" * 70)

        # Direct ispEN LOW without reset
        isp._set(nSRST | ispEN)
        time.sleep(0.05)
        isp._set(nSRST)           # ispEN LOW, no reset toggle
        time.sleep(0.01)

        before = isp.read_sdo_pattern(16)
        isp.isp_shift_cmd(ISP_UBE, 5, mode=0)
        isp.isp_execute(T_BEW)
        after = isp.read_sdo_pattern(16)
        changed = "***CHANGED***" if before != after else ""
        print(f"  UBE 5-bit (no reset): before={fmt(before,16)} "
              f"after={fmt(after,16)} {changed}")
        isp.exit_isp()

        # === TEST 7: Try with MODE=1 for command shift ===
        print("\n" + "=" * 70)
        print("TEST 7: Shift UBE with MODE=1 (command register)")
        print("  then execute with MODE transition 1->0->1")
        print("  (bitbang_isp4 showed MODE=1 accesses different register)")
        print("=" * 70)

        isp.enter_isp()
        before = isp.read_sdo_pattern(16)

        # Shift UBE via MODE=1
        isp.isp_shift_cmd(ISP_UBE, 5, mode=1)
        # Execute: drop MODE to 0 briefly, then back to 1
        isp._set(nSRST)           # MODE=0
        time.sleep(T_SU2)
        isp._set(nSRST | MODE)    # MODE=1 (execute)
        isp._set(nSRST | MODE | SCLK)  # clock edge
        time.sleep(T_BEW)
        isp._set(nSRST)           # back to MODE=0
        time.sleep(T_SU2)

        after = isp.read_sdo_pattern(16)
        changed = "***CHANGED***" if before != after else ""
        print(f"  UBE via MODE=1: before={fmt(before,16)} "
              f"after={fmt(after,16)} {changed}")

        # Also try 8-bit
        isp.isp_shift_cmd(ISP_UBE, 8, mode=1)
        isp._set(nSRST)
        time.sleep(T_SU2)
        isp._set(nSRST | MODE)
        isp._set(nSRST | MODE | SCLK)
        time.sleep(T_BEW)
        isp._set(nSRST)
        time.sleep(T_SU2)

        after2 = isp.read_sdo_pattern(16)
        changed2 = "***CHANGED***" if before != after2 else ""
        print(f"  UBE 8-bit via MODE=1: before={fmt(before,16)} "
              f"after={fmt(after2,16)} {changed2}")
        isp.exit_isp()

        # === FINAL CHECK ===
        print("\n" + "=" * 70)
        print("FINAL: Full SDO dump to see if anything changed")
        print("=" * 70)

        isp.enter_isp()
        for mode_val in [0, 1]:
            bits = []
            for i in range(32):
                sdo = isp.clk(0, mode_val)
                bits.append(sdo)
            bitstr = ''.join(str(b) for b in bits)
            print(f"  MODE={mode_val}: SDO = {bitstr}")
        isp.exit_isp()

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETE")
        print("=" * 70)
        print("\nIf any test shows ***CHANGED*** or ***VERIFY NON-ZERO***,")
        print("the security fuse may have been cleared!")
        print("If all tests show the same 0x15/0x5555 pattern,")
        print("the chip is still locked — may need elevated voltage on ispEN.")

    finally:
        isp.close()


if __name__ == '__main__':
    main()
