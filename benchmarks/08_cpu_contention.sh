#!/usr/bin/env bash
# =============================================================================
# 08_cpu_contention.sh
# Measure how much network transports steal CPU from a co-running workload.
#
# Simulates a real training node: stress-ng with 4 CPU workers (data loader,
# Python, preprocessing) running while NCCL or iperf3 saturates the network.
#
# Compares: baseline / RDMA / NCCL-TCP / iperf3-TCP-8
#
# Run on BOTH nodes simultaneously.
# Requires: stress-ng, iperf3, nccl-tests, mpirun, passwordless SSH
# =============================================================================

set -e

NODE2="192.168.100.2"
DEV1="mlx5_1"
DEV2="mlx5_0"

echo "=== Test 10 - CPU contention under network load ==="
echo ""

# Baseline (no network)
echo "--- Baseline: stress-ng with no network ---"
stress-ng --cpu 4 --cpu-load 100 --timeout 30 --metrics 2>&1 | grep " cpu " | tail -5
echo ""

# With NCCL RDMA
echo "--- With NCCL RDMA ---"
stress-ng --cpu 4 --cpu-load 100 --timeout 120 --metrics > /tmp/stress_rdma.txt 2>&1 &
mpirun -np 2 -H pc1n:1,pc2n:1 \
    --mca btl_tcp_if_include 192.168.100.0/24 \
    --mca oob_tcp_if_include 192.168.100.0/24 \
    -x NCCL_DEBUG=WARN \
    -x "NCCL_IB_HCA=${DEV1}:1,${DEV2}:1" \
    -x NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0 \
    -x LD_LIBRARY_PATH \
    bash -c 'cd ~/nccl-tests/build && exec ./all_reduce_perf -b 8 -e 256M -f 2 -g 1'
wait
echo "stress-ng under NCCL RDMA:"
grep " cpu " /tmp/stress_rdma.txt | grep metrc
echo ""

# With NCCL TCP
echo "--- With NCCL TCP fallback ---"
stress-ng --cpu 4 --cpu-load 100 --timeout 120 --metrics > /tmp/stress_tcp.txt 2>&1 &
mpirun -np 2 -H pc1n:1,pc2n:1 \
    --mca btl_tcp_if_include 192.168.100.0/24 \
    --mca oob_tcp_if_include 192.168.100.0/24 \
    -x NCCL_DEBUG=WARN \
    -x NCCL_IB_DISABLE=1 \
    -x NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0 \
    -x LD_LIBRARY_PATH \
    bash -c 'cd ~/nccl-tests/build && exec ./all_reduce_perf -b 8 -e 256M -f 2 -g 1'
wait
echo "stress-ng under NCCL TCP:"
grep " cpu " /tmp/stress_tcp.txt | grep metrc
echo ""

# With iperf3 at near line rate (the worst case)
echo "--- With iperf3 TCP 8-stream at near line rate ---"
echo "NOTE: start iperf3 -s on the other node first"
ssh "pc2n@$NODE2" "iperf3 -s &"
sleep 1
stress-ng --cpu 4 --cpu-load 100 --timeout 50 --metrics > /tmp/stress_iperf.txt 2>&1 &
iperf3 -c "$NODE2" -t 40 -P 8
wait
echo "stress-ng under iperf3 TCP-8:"
grep " cpu " /tmp/stress_iperf.txt | grep metrc
echo ""
echo "=== Done. Expected: -28% drop with iperf3 TCP, 0% with RDMA ==="
