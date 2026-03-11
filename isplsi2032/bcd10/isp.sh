#!/bin/bash
# isp.sh — ispLSI 2032 ISP test sequence
# Run on HOST (not chroot!) — needs pyftdi + USB access
#
# Usage: bash isp.sh
#
# Each step depends on the previous one passing.
# Stops on first failure.

set -e

cd "$(dirname "$0")"

echo "============================================"
echo " ispLSI 2032 — ISP Test Sequence"
echo " $(date)"
echo "============================================"
echo

# Step 0: Unbind ftdi_sio if loaded
if lsmod | grep -q ftdi_sio; then
    echo ">>> Unloading ftdi_sio kernel module..."
    sudo rmmod ftdi_sio
    echo
fi

# Step 1: Self-test (ID + FLOWTHRU + spot read)
echo ">>> STEP 1: Self-test"
echo "--------------------------------------------"
python3 isp.py --test
echo
echo ">>> STEP 1: PASSED"
echo

# Step 2: Bulk erase + verify
echo ">>> STEP 2: Erase + verify"
echo "--------------------------------------------"
python3 isp.py --erase
echo
echo ">>> STEP 2: PASSED"
echo

# Step 3: Read erased chip — save baseline
echo ">>> STEP 3: Read erased chip (baseline)"
echo "--------------------------------------------"
python3 isp.py --read -o erased_v2.fuse
echo
echo ">>> STEP 3: PASSED"
echo

# Step 4: Write/read pattern test
echo ">>> STEP 4: Write/read pattern test"
echo "--------------------------------------------"
python3 isp.py --write-test
echo
echo ">>> STEP 4: PASSED"
echo

# Step 5: Final read after erase (write-test erases at end)
echo ">>> STEP 5: Final read (should be erased)"
echo "--------------------------------------------"
python3 isp.py --read -o final.fuse
echo
echo ">>> STEP 5: PASSED"
echo

echo "============================================"
echo " ALL STEPS PASSED"
echo "============================================"
