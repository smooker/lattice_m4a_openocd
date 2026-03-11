#!/usr/bin/env python3
"""Detect JTAG IR length by shifting patterns through SHIFT-IR state."""

from pyftdi.jtag import JtagEngine
from pyftdi.bits import BitSequence
import sys

# FT2232H on smooker's board
FTDI_URL = 'ftdi://ftdi:2232h/1'

def detect_ir_length(engine):
    """
    Method:
    1. Reset TAP (5x TMS=1)
    2. Go to SHIFT-IR: TMS=0,1,1,0,0
    3. Shift 64 ones through IR (fills any IR up to 64 bits)
    4. Shift 64 zeros and capture TDO — the position of the
       first '1' in the output = IR length
    """
    ctrl = engine.controller

    # Reset TAP: 5 clocks with TMS=1
    ctrl.write_tms(BitSequence('11111'))

    # Navigate: RESET -> IDLE -> DRSELECT -> IRSELECT -> IRCAPTURE -> IRSHIFT
    # From RESET: TMS=0 -> IDLE
    # From IDLE: TMS=1 -> DRSELECT
    # From DRSELECT: TMS=1 -> IRSELECT
    # From IRSELECT: TMS=0 -> IRCAPTURE
    # From IRCAPTURE: TMS=0 -> IRSHIFT
    ctrl.write_tms(BitSequence('00110'))

    # Now in SHIFT-IR. Shift 64 ones (TMS=0 to stay in SHIFT-IR)
    ones = BitSequence(value=0xFFFFFFFFFFFFFFFF, length=64)
    # read=True to capture TDO
    ctrl.read(64)  # dummy read to flush
    # Actually, let's use a simpler approach - shift bits one at a time

    # Better approach: shift all at once
    # Shift 64 ones, capture output (don't care about this output)
    print("Shifting 64 ones into IR...")
    tdo_ones = ctrl.shift_register(ones)
    print(f"  TDO during ones: {tdo_ones}")

    # Now shift 64 zeros, capture output
    # The first N bits will be 1 (from the IR register), rest 0
    print("Shifting 64 zeros into IR...")
    zeros = BitSequence(value=0, length=64)
    tdo_zeros = ctrl.shift_register(zeros)
    print(f"  TDO during zeros: {tdo_zeros}")

    # Count leading 1s in tdo_zeros = IR length
    ir_len = 0
    for i in range(64):
        if tdo_zeros[i]:
            ir_len += 1
        else:
            break

    return ir_len


def main():
    print(f"Connecting to {FTDI_URL}...")
    engine = JtagEngine(frequency=1E6)
    engine.configure(FTDI_URL)
    print("Connected.")

    ir_len = detect_ir_length(engine)
    print(f"\n*** Detected IR length: {ir_len} bits ***\n")

    # Also try to read IDCODE after detection
    ctrl = engine.controller

    # Reset and go to SHIFT-DR to read IDCODE
    ctrl.write_tms(BitSequence('11111'))  # Reset
    ctrl.write_tms(BitSequence('0010'))   # IDLE -> DRSELECT -> DRCAPTURE -> DRSHIFT

    # Read 32 bits from DR (IDCODE or BYPASS)
    zeros32 = BitSequence(value=0, length=32)
    idcode = ctrl.shift_register(zeros32)
    print(f"DR after reset (IDCODE?): 0x{int(idcode):08X}")

    # Now test different IR instructions
    print(f"\nTesting IR opcodes (irlen={ir_len})...")
    for opcode in range(2**min(ir_len, 8)):
        # Reset
        ctrl.write_tms(BitSequence('11111'))
        # Go to SHIFT-IR
        ctrl.write_tms(BitSequence('00110'))
        # Load IR opcode
        ir_val = BitSequence(value=opcode, length=ir_len)
        ctrl.shift_register(ir_val, last=True)  # last=True exits SHIFT-IR
        # TMS=1 on last bit -> EXIT1-IR, then TMS=1 -> UPDATE-IR, TMS=0 -> IDLE
        ctrl.write_tms(BitSequence('10'))

        # Go to SHIFT-DR
        ctrl.write_tms(BitSequence('010'))  # IDLE -> DRSELECT -> DRCAPTURE -> DRSHIFT

        # Shift 32 zeros through DR to measure its length and capture value
        tdo = ctrl.shift_register(BitSequence(value=0, length=32))
        dr_val = int(tdo)

        # Shift pattern to detect DR length
        ctrl.write_tms(BitSequence('11'))  # EXIT -> UPDATE
        ctrl.write_tms(BitSequence('0'))   # IDLE
        ctrl.write_tms(BitSequence('010')) # -> SHIFT-DR again

        pat = BitSequence(value=0xA5A5A5A5, length=32)
        tdo2 = ctrl.shift_register(pat)
        dr_pat = int(tdo2)

        if dr_val != 0x05 or dr_pat != 0x05:  # Only print interesting ones
            print(f"  IR=0x{opcode:02X}: DR_capture=0x{dr_val:08X}  DR_shift=0x{dr_pat:08X} ***DIFFERENT***")

    print("\nDone. (Only non-0x05 results shown above)")

    engine.close()

if __name__ == '__main__':
    main()
