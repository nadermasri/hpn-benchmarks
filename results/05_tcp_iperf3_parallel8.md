# Benchmark 05 — Kernel TCP throughput, 8 parallel streams
Date: 2026-05-18

================================================================================
COMMAND
================================================================================

Server (node 2):  iperf3 -s
Client (node 1):  iperf3 -c 192.168.100.2 -t 30 -P 8

Identical hardware, cable, MTU, and CPU governor as Tests 01–04.

================================================================================
RESULT
================================================================================

Aggregate (8 streams summed):
  Total transferred:    326 GBytes in 30.00 s
  Average bitrate:      93.3 Gb/s
  Total retransmits:    128 (sender side)
  Per-second range:     92.2 – 94.4 Gb/s

Per-stream breakdown:
  Stream  5: 12.6 Gb/s     7 retr
  Stream  7: 14.2 Gb/s     7 retr
  Stream  9: 10.1 Gb/s    44 retr   ← contended
  Stream 11: 11.6 Gb/s     0 retr
  Stream 13: 10.2 Gb/s    37 retr   ← contended
  Stream 15: 11.5 Gb/s     1 retr
  Stream 17: 10.9 Gb/s    27 retr
  Stream 19: 12.1 Gb/s     5 retr

Spread: min 10.1, max 14.2, ratio 1.40× → 40 % imbalance between fastest
and slowest streams.

================================================================================
COMPARISON ACROSS ALL TESTS SO FAR
================================================================================

  Transport / config        Throughput  % line rate  Retransmits  Jitter
  ----------------------------------------------------------------------
  RoCEv2 (1 QP, 128 KB)     98.2 Gb/s   98.2 %       0            < 1 %
  RoCEv2 (1 QP, 64 KB)      97.8 Gb/s   97.8 %       0            < 1 %
  TCP (8 streams, default)  93.3 Gb/s   93.3 %       128          ~ 2 %
  TCP (1 stream, default)   34.8 Gb/s   34.8 %       0            ~ 7 %

================================================================================
ANALYSIS — Why parallelism rescued TCP, and what gap remains
================================================================================

Going from 1 stream to 8 streams gave a 2.7x throughput increase. The
single-stream test was CPU-bound on one core; 8 streams distribute receive-
side processing across the 8 hardware threads of the Xeon E5-1620 v3 via
Receive Side Scaling (RSS, which hashes 5-tuples to RX queues). All cores
now share the TCP processing load.

However, three things still distinguish TCP from RDMA even at parallel scale:

(1) Residual ~5% throughput gap (93.3 vs 98.2 Gb/s).
    This is the irreducible cost of the kernel stack: socket buffers, TCP
    state machines, IP, qdisc, IRQ handling, scheduling. The RDMA NIC does
    none of this in software; verbs are translated into PCIe transactions
    directly. The gap will not close, regardless of how many streams.

(2) 128 retransmits per 30 s.
    With multiple streams sharing the link, TCP cwnd dynamics cause brief
    oversubscription; packets are dropped at the NIC queue or in the
    kernel; TCP detects loss and retransmits. RDMA Reliable Connection uses
    hardware credit-based flow control: the sender literally cannot
    transmit if the receiver has no buffer credit, so loss-and-recovery
    is structurally impossible at this layer.

(3) 40% imbalance between streams.
    Stream scheduling depends on which core handles RX for that flow,
    cache locality, and other kernel internals. No comparable variability
    exists for RDMA queue pairs, which are independent and deterministic.

================================================================================
HEADLINE
================================================================================

  - 1-stream TCP : 34.8 Gb/s (34.8 % of line rate)
  - 8-stream TCP : 93.3 Gb/s (93.3 % of line rate)
  - RoCEv2 RDMA  : 97.8 Gb/s (97.8 % of line rate)

Kernel TCP can approach line rate when sufficiently parallelized, but
retains a ~5% throughput gap, higher jitter, and ~128 retransmits per
30 seconds versus zero for RDMA.

================================================================================
NEXT
================================================================================

06: iperf3 --zerocopy     →  does MSG_ZEROCOPY close the 5 % gap?
07: sockperf TCP latency  →  TCP latency vs RoCE 0.83 µs floor
08: CPU usage with mpstat →  quantify CPU cost per gigabit
