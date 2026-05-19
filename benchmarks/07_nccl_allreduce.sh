#!/usr/bin/env bash
# =============================================================================
# 07_nccl_allreduce.sh
# NCCL allreduce benchmark — RDMA transport and TCP socket fallback
#
# Runs nccl-tests/all_reduce_perf across both nodes via mpirun.
# Tests the exact collective that PyTorch DDP uses for gradient sync.
#
# Run from: node 1 (pc1n)
# Requires: mpirun, nccl-tests built with MPI=1 (at ~/nccl-tests/build/)
#           Passwordless SSH to pc2n, /etc/hosts with 100G IPs
#
# Build nccl-tests (if not already):
#   cd ~/nccl-tests
#   make MPI=1 MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi \
#        CUDA_HOME=/usr/local/cuda NCCL_HOME=/usr -j4
# =============================================================================

set -e

MPIRUN_BASE="mpirun -np 2 -H pc1n:1,pc2n:1 \
  --mca btl_tcp_if_include 192.168.100.0/24 \
  --mca oob_tcp_if_include 192.168.100.0/24 \
  -x LD_LIBRARY_PATH"

NCCL_CMD="bash -c 'cd ~/nccl-tests/build && exec ./all_reduce_perf -b 8 -e 256M -f 2 -g 1'"

echo "=== Test 09 — NCCL allreduce ==="
echo ""

# -------------------------------------------------------------------
# 09a — RDMA transport (default)
# -------------------------------------------------------------------
echo "--- 09a: NCCL over RoCEv2 RDMA ---"
echo "  Transport: NET/IB using mlx5_1 (node 1) and mlx5_0 (node 2)"
echo ""

$MPIRUN_BASE \
  -x NCCL_DEBUG=INFO \
  -x "NCCL_IB_HCA=mlx5_1:1,mlx5_0:1" \
  -x "NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0" \
  $NCCL_CMD 2>&1 | tee /tmp/nccl_rdma.log

echo ""
echo "Expected peak: ~50.6 Gb/s (6.33 GB/s) at 256 MB"
echo "Note: capped at 50 Gb/s (not 98) because RTX 3060 has no GPUDirect RDMA"
echo "Confirm transport: grep 'NET/IB' /tmp/nccl_rdma.log"
echo ""

# -------------------------------------------------------------------
# 09b — TCP socket fallback
# -------------------------------------------------------------------
echo "--- 09b: NCCL over TCP sockets (NCCL_IB_DISABLE=1) ---"
echo ""

$MPIRUN_BASE \
  -x NCCL_DEBUG=INFO \
  -x NCCL_IB_DISABLE=1 \
  -x "NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0" \
  $NCCL_CMD 2>&1 | tee /tmp/nccl_tcp.log

echo ""
echo "Expected peak: ~10.3 Gb/s (1.29 GB/s) at 256 MB"
echo "Confirm transport: grep 'NET/Socket' /tmp/nccl_tcp.log"
echo ""
echo "=== Summary: RDMA/TCP ratio should be ~5x across the bandwidth-bound regime ==="
