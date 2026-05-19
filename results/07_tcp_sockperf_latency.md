# Benchmark 07 — Kernel TCP latency (sockperf ping-pong)
Date: 2026-05-18

================================================================================
COMMANDS
================================================================================

Server (node 2):
  sockperf server --tcp -i 192.168.100.2 -p 11111

Client (node 1):
  sockperf ping-pong --tcp -i 192.168.100.2 -p 11111 -m 14 -t 10 --full-rtt

Configuration:
  Protocol     : TCP (default kernel settings, blocking sockets)
  Message size : 14 B (sockperf minimum)
  Duration     : 10 s (9.55 s after warmup discard)
  Sample count : 378,016 valid ping-pong exchanges
  Reporting    : --full-rtt   → full round-trip time

================================================================================
RESULT (sockperf raw)
================================================================================

Average RTT       :  25.127 µs (std-dev 2.021 µs)
Min RTT           :  21.581 µs
p50 RTT (median)  :  24.557 µs
p75 RTT           :  25.504 µs
p90 RTT           :  27.606 µs
p99 RTT           :  32.292 µs
p99.9 RTT         :  39.572 µs
p99.99 RTT        :  58.809 µs
p99.999 RTT       :  88.202 µs
Max RTT           : 158.363 µs

Dropped messages  : 0
Duplicated/OOO    : 0

================================================================================
DERIVED — One-way latency (RTT / 2) and direct comparison with RoCEv2
================================================================================

  Percentile   TCP one-way     RDMA one-way     Ratio TCP/RDMA
  ----------------------------------------------------------------
  min          10.79 µs        0.80 µs          13.5x
  p50          12.28 µs        0.83 µs          14.8x
  p99          16.15 µs        1.01 µs          16.0x
  p99.9        19.79 µs        ~2.14 µs (max)   ~9x
  max          79.18 µs        2.14 µs          37x

================================================================================
ANALYSIS
================================================================================

The 15x mean-latency gap between kernel TCP and RoCEv2 represents the full
cost of the Linux network stack at this hardware/load:

  Application (sendmsg)
    -> copy_from_user                   (one memcpy of 14 B)
    -> socket layer
    -> TCP layer (cwnd, headers, ACK clock)
    -> IP layer
    -> qdisc
    -> driver TX (build descriptor)
    -> NIC TX  (only at this point is it the same as RDMA)
    ===wire===
    -> NIC RX
    -> IRQ
    -> NAPI poll
    -> driver RX
    -> IP layer
    -> TCP layer
    -> socket receive queue
    -> wake recv() blocker
    -> scheduler context switch
    -> copy_to_user                     (one memcpy of 14 B)
    -> Application (recvmsg returns)

RDMA replaces all of the above (except the wire) with:

  Application -> WQE write -> doorbell -> NIC -> wire ->
  NIC -> CQE -> Application polls completion.

The 14 B physical serialization time on 100G is 1.12 ns. Cable propagation
across 0.5 m of copper is ~2.5 ns. Together, the unavoidable physics costs
~4 ns — i.e., ~0.004 µs. The remainder of the latency is software/firmware.

Tail behaviour:

The TCP std-dev is 2.0 µs and the max is 158 µs (= ~7x the mean). The RDMA
std-dev rounded to zero and the max was 2.5x the mean. Tail latency is
dominated for TCP by kernel-scheduler events: IRQ coalescing windows,
NAPI batching, scheduler timeslice boundaries, RCU grace periods. These
do not affect RDMA because no kernel code runs on the data path.

For distributed-AI workloads:
  - Parameter-server gradient pushes are latency-bound at small message
    sizes; the 15x mean gap maps almost directly to slower per-step time.
  - Synchronous allreduce in NCCL exposes the *tail* of the per-link
    latency; the 37x worst-case gap is what causes "straggler" effects in
    cluster training even when bandwidth is sufficient.

================================================================================
HEADLINE
================================================================================

  Mean one-way latency, 14 B message:
    RoCEv2 RDMA : 0.83 µs
    Kernel TCP  : 12.28 µs
    Gap         : 14.8x

  Tail (p99 one-way):
    RoCEv2 RDMA : 1.01 µs
    Kernel TCP  : 16.15 µs
    Gap         : 16.0x

  Worst-case (max one-way):
    RoCEv2 RDMA :  2.14 µs (occurred at 8 B)
    Kernel TCP  : 79.18 µs
    Gap         : 37x
