#!/usr/bin/env bash
# =============================================================================
# 02_rdma_latency.sh
# RoCEv2 RDMA send latency — 2-byte messages + full size sweep
#
# Run from: node 1 (pc1n)
# Requires: ib_send_lat (perftest package), passwordless SSH to pc2n
# Reports HALF round-trip (one-way latency)
# =============================================================================

set -e

NODE2="192.168.100.2"
DEV1="mlx5_1"
DEV2="mlx5_0"
PORT="1"

echo "=== Test 02/03 — RoCEv2 RDMA Send Latency ==="
echo ""

# -------------------------------------------------------------------
# 2-byte messages (floor latency)
# -------------------------------------------------------------------
echo "--- 2 B messages (latency floor) ---"
ssh "pc2n@$NODE2" "ib_send_lat -d $DEV2 -i $PORT -F -R &"
sleep 1
ib_send_lat -d "$DEV1" -i "$PORT" -F -R "$NODE2"

echo ""
echo "--- Full size sweep (-a flag) ---"
ssh "pc2n@$NODE2" "ib_send_lat -d $DEV2 -i $PORT -F -R -a &"
sleep 1
ib_send_lat -d "$DEV1" -i "$PORT" -F -R -a "$NODE2"

echo ""
echo "=== Done. Expected floor: ~0.83 µs one-way at 2 B ==="
echo "=== Inline regime (≤128 B): flat ~0.83 µs ==="
echo "=== Non-inline jump at 256 B: +0.35 µs from DMA read ==="
