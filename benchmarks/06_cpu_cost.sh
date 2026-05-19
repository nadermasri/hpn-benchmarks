#!/usr/bin/env bash
# =============================================================================
# 06_cpu_cost.sh
# CPU cost measurement during RDMA and TCP transfers
#
# Uses mpstat to sample CPU usage every second during a 30-second run.
# Key metric: cores per Gb/s, and the split between %usr / %sys / %soft.
#
# Run from: node 1 (pc1n)
# Run SIMULTANEOUSLY on node 2 for the server-side numbers.
# =============================================================================

set -e

NODE2="192.168.100.2"
DEV1="mlx5_1"
DEV2="mlx5_0"

echo "=== Test 08 — CPU Cost Analysis ==="
echo "NOTE: On node 2, run the matching 'server' commands in parallel."
echo ""

# -------------------------------------------------------------------
# 08a — RDMA
# -------------------------------------------------------------------
echo "--- 08a: RDMA CPU cost ---"
echo "  Start on node 2: ib_send_bw -d $DEV2 -i 1 -F -R --report_gbits -D 30"
echo "  Then run this block on node 1:"
echo ""

mpstat 1 35 > /tmp/cpu_rdma_client.txt &
MPSTAT_PID=$!
ib_send_bw -d "$DEV1" -i 1 -F -R --report_gbits -D 30 "$NODE2"
wait $MPSTAT_PID

echo ""
echo "--- RDMA CPU usage (tail of mpstat) ---"
tail -10 /tmp/cpu_rdma_client.txt
echo ""
echo "Expected: %usr ~12.5%, %sys ~0.0%, %soft ~0.0%"
echo ""

# -------------------------------------------------------------------
# 08b — TCP 1-stream
# -------------------------------------------------------------------
echo "--- 08b: TCP 1-stream CPU cost ---"
ssh "pc2n@$NODE2" "mpstat 1 35 > /tmp/cpu_tcp1_server.txt & iperf3 -s -1" &
sleep 2

mpstat 1 35 > /tmp/cpu_tcp1_client.txt &
MPSTAT_PID=$!
iperf3 -c "$NODE2" -t 30
wait $MPSTAT_PID

echo ""
echo "--- TCP 1-stream CPU usage ---"
tail -10 /tmp/cpu_tcp1_client.txt
echo ""
echo "Expected: %sys ~11%, %soft ~1.3%, %usr ~0.25%"
echo ""

# -------------------------------------------------------------------
# 08c — TCP 8-stream
# -------------------------------------------------------------------
echo "--- 08c: TCP 8-stream CPU cost ---"
ssh "pc2n@$NODE2" "mpstat 1 35 > /tmp/cpu_tcp8_server.txt & iperf3 -s -1" &
sleep 2

mpstat 1 35 > /tmp/cpu_tcp8_client.txt &
MPSTAT_PID=$!
iperf3 -c "$NODE2" -t 30 -P 8
wait $MPSTAT_PID

echo ""
echo "--- TCP 8-stream CPU usage (sender) ---"
tail -10 /tmp/cpu_tcp8_client.txt
echo ""
echo "Expected sender: %sys ~57%, %soft ~16% (total ~73%, ~5.8 cores)"
echo "Expected receiver (check node 2): %sys ~63%, %soft ~33% (total ~97%)"
