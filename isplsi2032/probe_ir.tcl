# Probe IR length and opcodes for ispLSI2032
# Run with: openocd -f cfg... -c "init" -f probe_ir.tcl

# Step 1: Determine IR length
# Method: shift 32 ones into IR, then shift 32 zeros.
# Count how many ones come back = IR length.
# We use raw JTAG operations via irscan with known irlen.

echo "=== IR Length Detection ==="
echo "Shifting pattern through IR to detect length..."

# Since OpenOCD's irscan doesn't return captured value,
# we use a different trick: shift known data through DR
# with different irlen assumptions and see which one
# produces consistent results.

# Step 2: Brute-force all IR opcodes
# For current irlen setting, try each opcode and check DR
echo ""
echo "=== DR Probe for all IR opcodes ==="
set irlen [dict get [jtag cget auto0.tap -event setup] -irlen]

# Get current irlen from scan chain
echo "Current irlen from config: testing all opcodes 0..31"

set num_opcodes 32
for {set op 0} {$op < $num_opcodes} {incr op} {
    # Load IR
    irscan auto0.tap $op

    # Read DR: shift 32 zeros, capture output
    set dr [drscan auto0.tap 32 0x00000000]

    # Shift pattern to detect DR length
    set dr2 [drscan auto0.tap 32 0xDEADBEEF]

    # Shift zeros again to get the pattern back
    set dr3 [drscan auto0.tap 32 0x00000000]

    # Check if this opcode gives different behavior
    set hex_op [format "0x%02X" $op]
    if {$dr ne "00000005" || $dr2 ne "adbeef05" || $dr3 ne "00000005"} {
        echo "*** IR=$hex_op: dr_cap=$dr dr_pat=$dr2 dr_flush=$dr3 ***"
    } else {
        echo "    IR=$hex_op: BYPASS-like (8-bit, capture=0x05)"
    }
}

echo ""
echo "=== DR Length Measurement ==="
echo "Shifting increasing lengths to find exact DR size..."

# For BYPASS instruction (0x1F), measure exact DR length
irscan auto0.tap 0x1F
for {set bits 1} {$bits <= 16} {incr bits} {
    # Create input: single 1 bit at position 0
    set dr [drscan auto0.tap $bits 0x0001]
    echo "  DR bits=$bits input=0x0001 output=0x$dr"
}

echo ""
echo "=== Done ==="
shutdown
