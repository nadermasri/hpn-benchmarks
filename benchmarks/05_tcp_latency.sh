#!/usr/bin/env bash
# =============================================================================
# 05_tcp_latency.sh
# Kernel TCP latency — sockperf ping-pong
#
# Reports full RTT; divide by 2 for one-way.
# Minimum message size with sockperf is 14 bytes.
#
# Run from: node 1 (pc1n)
# Requires: sockperf, passwordless SSH to pc2n
# =============================================================================

set -e

NODE2="192.168.100.2"
PORT="11111"

echo "=== Test 07 — Kernel TCP Latency (sockperf) ==="
echo ""

# Start server on node 2
ssh "pc2n@$NODE2" "sockperf server --tcp -i $NODE2 -p $PORT &"
sleep 1

# Run ping-pong for 10 seconds
sockperf ping-pong --tcp -i "$NODE2" -p "$PORT" \
    -m 14 -t 10 --full-rtt

echo ""
echo "=== Done. Expected: ~12.28 µs one-way mean (half the RTT shown above) ==="
echo "=== Compare with RDMA: 0.83 µs → ~15x gap ==="

# Cleanup server
ssh "pc2n@$NODE2" "pkill sockperf" 2>/dev/null || true
