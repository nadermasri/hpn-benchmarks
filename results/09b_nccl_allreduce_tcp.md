# Benchmark 09b — NCCL allreduce, TCP sockets transport
Date: 2026-05-18

================================================================================
COMMAND
================================================================================

mpirun -np 2 -H pc1n:1,pc2n:1 \
  --mca btl_tcp_if_include 192.168.100.0/24 \
  --mca oob_tcp_if_include 192.168.100.0/24 \
  -x NCCL_DEBUG=INFO \
  -x NCCL_IB_DISABLE=1 \
  -x NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0 \
  -x LD_LIBRARY_PATH \
  bash -c 'cd ~/nccl-tests/build && exec ./all_reduce_perf -b 8 -e 256M -f 2 -g 1'

Change vs 09a: added -x NCCL_IB_DISABLE=1, which forces NCCL to fall back
to its Socket (TCP) transport instead of NET/IB (RDMA).

================================================================================
TRANSPORT CONFIRMATION
================================================================================

NCCL_IB_DISABLE set by environment to 1
Failed to initialize NET plugin IB                      <-- intended
NET/Socket : Using [0]ens2fXnpX:192.168.100.X<0>
Using network Socket
Channel 00/0 : 0[0] -> 1[0] [receive] via NET/Socket/0  <-- TCP confirmed
Channel 01/0 : 0[0] -> 1[0] [receive] via NET/Socket/0
Connected all rings, use ring PXN 0 GDR 0

================================================================================
RESULTS - allreduce performance sweep
================================================================================

   size (B)   time (us)  algBW (GB/s)  busBW (GB/s)
         8      111.91         0.000         0.000
        64       85.55         0.001         0.001
       512      107.62         0.005         0.005
      4096       92.19         0.044         0.044
     32768      252.51         0.130         0.130
    262144      815.69         0.321         0.321
   1048576     1120.60         0.936         0.936
   8388608     6947.27         1.207         1.207
  67108864    52015.50         1.290         1.290
 268435456   208333.00         1.288         1.288    <-- peak

Peak bus bandwidth : 1.29 GB/s = 10.3 Gb/s
Avg bus bandwidth  : 0.504 GB/s (across full sweep)

================================================================================
DIRECT COMPARISON  -  NCCL allreduce, same workload, only transport changes
================================================================================

   size (B)         RDMA busBW (GB/s)    TCP busBW (GB/s)    RDMA / TCP
         8                 0.000                0.000            -
      4096                 0.187                0.044           4.3x
     65536                 1.540                0.270           5.7x
   1048576                 5.379                0.940           5.7x
  16777216                 5.850                1.230           4.8x
 268435456                 6.330                1.290           4.9x

   size (B)         RDMA time (us)       TCP time (us)         TCP / RDMA
         8                21.0                111.9              5.3x
      4096                21.9                 92.2              4.2x
   1048576               195                1120                 5.7x
 268435456             42397              208333                 4.9x

NCCL peak throughput  : RDMA = 6.33 GB/s     vs    TCP = 1.29 GB/s   (4.9x)
NCCL latency floor    : RDMA = 20.9 us       vs    TCP = 85-112 us   (4-5x)

================================================================================
INTERPRETATION
================================================================================

Why is TCP only 10 Gb/s, when raw iperf3 reached 34 Gb/s on a single
stream and 93 Gb/s with 8 streams on the same hardware?

(1) Insufficient parallelism in the NCCL Socket plugin.
    NCCL configured "2 p2p channels, 1 p2p channels per peer" -- only
    two TCP sockets total for the ring. Compare to iperf3 -P 8 which
    used 8 sockets to scale near line rate. With 2 sockets, TCP cannot
    fill the pipe.

(2) Synchronous chunked transfer.
    NCCL transfers 128 KB chunks (P2P Chunksize 131072), each one
    completed before the next ships. This destroys TCP's normal
    pipelining advantage where cwnd worth of data is always in flight.
    With 128 KB chunks, the in-flight window is fixed at ~256 KB total,
    far below TCP's BDP for 100G with 75-100 us RTT.

(3) Three serialized memory copies per side.
    GPU mem -> host staging -> kernel TCP buffer -> NIC
    plus the mirror on the receiver. Each adds latency and consumes
    CPU bandwidth. NCCL's data path here is single-threaded per channel
    per direction.

For RDMA NCCL (Benchmark 09a) the same three issues exist in form, but:
    - The network step itself is zero-copy and zero-syscall.
    - RDMA QPs allow many outstanding sends with hardware-managed
      completion (the proxy thread polls instead of sleeping).
    - Per-chunk CPU overhead is ~0.

The 5x gap is therefore not a property of the network -- both transports
can saturate this 100G fabric in isolation -- but a property of how each
transport interacts with NCCL's chunked-ring allreduce algorithm.

================================================================================
LATENCY-BOUND VS BANDWIDTH-BOUND REGIME
================================================================================

Latency-bound (size < ~8 KB):
   Both RDMA and TCP show a flat plateau; the operation is dominated
   by per-call overhead, not byte transfer time. The 5x ratio between
   RDMA (~21 us) and TCP (~85-110 us) directly reflects the per-syscall
   and per-context-switch overhead of the kernel TCP path.

Bandwidth-bound (size > 1 MB):
   The ratio settles to ~5x. Each chunk pays the overhead of one TCP
   socket transaction; the chunks dominate. RDMA's ratio is preserved
   across sizes because the marginal cost per byte is ~0 with hardware
   offload.

================================================================================
WHY THIS MATTERS FOR DISTRIBUTED TRAINING
================================================================================

A typical training step on a 2-node 8-GPU cluster:
   - Forward pass:    1-10 ms
   - Backward pass:   2-20 ms  (overlaps with allreduce)
   - Allreduce:       depends on gradient size and transport

For a 200 MB gradient bucket (typical PyTorch DDP):
   RDMA allreduce  : 200 MB / 6.3 GB/s = 32 ms
   TCP  allreduce  : 200 MB / 1.3 GB/s = 154 ms

If the backward pass is 50 ms long, RDMA's 32 ms allreduce overlaps
entirely and is "free". TCP's 154 ms exceeds the backward pass by 3x,
stalling the next forward pass and dominating step time.

This is the structural reason every major ML training stack
(PyTorch DDP, FSDP, DeepSpeed, Megatron-LM) ships with NCCL+RDMA as
the default and treats TCP as a degraded-mode fallback.

================================================================================
HEADLINE
================================================================================

  Same hardware. Same NCCL version. Same algorithm. Same data.
  Only the transport changes:

      RDMA RoCEv2  :  50.6 Gb/s peak,  20.9 us min latency
      Kernel TCP   :  10.3 Gb/s peak, 111.9 us min latency

  -> RDMA is 5x faster in both bandwidth and latency for ML collectives.
