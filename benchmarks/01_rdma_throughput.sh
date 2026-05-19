#!/usr/bin/env bash
# =============================================================================
# 01_rdma_throughput.sh
# RoCEv2 RDMA send bandwidth — single QP, 64 KB default + full size sweep
#
# Run from: node 1 (pc1n)
# Requires: ib_send_bw (perftest package), passwordless SSH to pc2n
# =============================================================================

set -e

NODE2="192.168.100.2"
DEV1="mlx5_1"   # RDMA device on node 1
DEV2="mlx5_0"   # RDMA device on node 2
PORT="1"

echo "=== Test 01 — RoCEv2 RDMA Send Bandwidth ==="
echo "Node 1 (client): $(hostname) / $DEV1"
echo "Node 2 (server): $NODE2 / $DEV2"
echo ""

# -------------------------------------------------------------------
# 1a — Default 64 KB, 1000 iterations
# -------------------------------------------------------------------
echo "--- 1a: 64 KB messages ---"
ssh "pc2n@$NODE2" "ib_send_bw -d $DEV2 -i $PORT -F -R --report_gbits &" 
sleep 1
ib_send_bw -d "$DEV1" -i "$PORT" -F -R --report_gbits "$NODE2"

echo ""

# -------------------------------------------------------------------
# 1b — Full size sweep (2 B to 8 MB)
# -------------------------------------------------------------------
echo "--- 1b: Full size sweep (-a flag) ---"
ssh "pc2n@$NODE2" "ib_send_bw -d $DEV2 -i $PORT -F -R --report_gbits -a &"
sleep 1
ib_send_bw -d "$DEV1" -i "$PORT" -F -R --report_gbits -a "$NODE2"

echo ""
echo "=== Done. Expected: ~97.76 Gb/s at 64 KB, ~98.20 Gb/s at 128 KB ==="
