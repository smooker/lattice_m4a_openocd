#!/bin/bash
# Probe IR length by running OpenOCD with different irlen values
# and checking if any IR opcode produces non-BYPASS DR behavior.
#
# For each irlen, we test opcodes that should be ISC_ENABLE, ISC_ADDRESS_SHIFT etc
# and see if DR changes from the default 8-bit/0x05 pattern.

CFG="../../ft2232h/ft2232h_smooker.cfg"
RESULTS="/tmp/irlen_probe_results.txt"
> "$RESULTS"

for IRLEN in 3 4 5 6 7 8 9 10; do
    echo "=== Testing irlen=$IRLEN ==="

    # Start OpenOCD in background
    openocd \
        -f "$CFG" \
        -c "ftdi layout_signal nSRST -data 0x0010 -oe 0x0010" \
        -c "adapter speed 1000; transport select jtag" \
        -c "jtag newtap auto0 tap -irlen $IRLEN -expected-id 0 -ircapture 0x01 -irmask 0x01" \
        -c "init" \
        -l /tmp/openocd_probe.log 2>/dev/null &
    OCD_PID=$!

    # Wait for telnet port
    for i in $(seq 1 20); do
        (echo > /dev/tcp/localhost/4444) 2>/dev/null && break
        sleep 0.2
    done

    # Build test commands
    MAX_IR=$((1 << IRLEN))
    if [ $MAX_IR -gt 256 ]; then MAX_IR=256; fi

    # Send all opcodes and collect DR responses
    {
        exec 3<>/dev/tcp/localhost/4444
        for opcode in $(seq 0 $((MAX_IR - 1))); do
            hex=$(printf "0x%02X" $opcode)
            echo "irscan auto0.tap $hex" >&3
            sleep 0.02
            echo "drscan auto0.tap 16 0xCAFE" >&3
            sleep 0.02
        done
        echo "shutdown" >&3
        sleep 1
        cat <&3
        exec 3>&-
    } 2>/dev/null | grep -v "^>" | grep -v "^$" | grep -v "Open On" | sort -u > /tmp/irlen_${IRLEN}_dr.txt

    # Check if all DR results are the same
    UNIQUE=$(cat /tmp/irlen_${IRLEN}_dr.txt | grep -v shutdown | sort -u | wc -l)
    DR_VALS=$(cat /tmp/irlen_${IRLEN}_dr.txt | grep -v shutdown | sort -u | tr '\n' ' ')

    echo "  irlen=$IRLEN: $UNIQUE unique DR values: $DR_VALS" | tee -a "$RESULTS"

    # Make sure OpenOCD is dead
    kill $OCD_PID 2>/dev/null
    wait $OCD_PID 2>/dev/null
    sleep 0.5
done

echo ""
echo "=== Summary ==="
cat "$RESULTS"
