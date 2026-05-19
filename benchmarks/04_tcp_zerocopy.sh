#!/usr/bin/env bash
# =============================================================================
# 04_tcp_zerocopy.sh
# TCP with MSG_ZEROCOPY (iperf3 --zerocopy) — 1 and 8 streams
#
# MSG_ZEROCOPY eliminates the user→kernel copy on the send side.
# Expected result: throughput unchanged (bottleneck is protocol processing,
#                  not memcpy); retransmits reduced ~6x at 8 streams.
#
# Run from: node 1 (pc1n)
# =============================================================================

set -e

NODE2="192.168.100.2"

echo "=== Test 06 — TCP MSG_ZEROCOPY ==="
echo ""

echo "--- 1 stream + zerocopy ---"
ssh "pc2n@$NODE2" "iperf3 -s -1 &"
sleep 1
iperf3 -c "$NODE2" -t 30 --zerocopy

echo ""

echo "--- 8 streams + zerocopy ---"
ssh "pc2n@$NODE2" "iperf3 -s -1 &"
sleep 1
iperf3 -c "$NODE2" -t 30 -P 8 --zerocopy

echo ""
echo "=== Done. Expected: ~34.0 Gb/s (1), ~92.1 Gb/s (8) ==="
echo "=== Key result: retransmits 128 → 22 with zerocopy at 8 streams ==="
