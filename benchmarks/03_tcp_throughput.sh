#!/usr/bin/env bash
# =============================================================================
# 03_tcp_throughput.sh
# Kernel TCP throughput — 1 stream and 8 parallel streams
#
# Run from: node 1 (pc1n)
# Requires: iperf3, passwordless SSH to pc2n
# =============================================================================

set -e

NODE2="192.168.100.2"

echo "=== Test 04/05 — Kernel TCP Throughput ==="
echo ""

# -------------------------------------------------------------------
# Single stream (30 s)
# -------------------------------------------------------------------
echo "--- Single stream ---"
ssh "pc2n@$NODE2" "iperf3 -s -1 &"
sleep 1
iperf3 -c "$NODE2" -t 30

echo ""

# -------------------------------------------------------------------
# 8 parallel streams (30 s)
# -------------------------------------------------------------------
echo "--- 8 parallel streams ---"
ssh "pc2n@$NODE2" "iperf3 -s -1 &"
sleep 1
iperf3 -c "$NODE2" -t 30 -P 8

echo ""
echo "=== Done. Expected: ~34.8 Gb/s (1 stream), ~93.3 Gb/s (8 streams) ==="
