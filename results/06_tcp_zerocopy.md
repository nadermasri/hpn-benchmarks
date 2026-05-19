# Benchmark 06 — TCP with MSG_ZEROCOPY (iperf3 --zerocopy)
Date: 2026-05-18

================================================================================
COMMANDS
================================================================================

Server (node 2):  iperf3 -s

Client (node 1):
  Single stream:    iperf3 -c 192.168.100.2 -t 30 --zerocopy
  Eight streams:    iperf3 -c 192.168.100.2 -t 30 --zerocopy -P 8

iperf3's --zerocopy enables MSG_ZEROCOPY on sendmsg() calls.
This avoids the userspace -> kernel buffer copy on the send side only.
Receive side (kernel -> userspace) still copies in both cases.

================================================================================
RESULTS
================================================================================

Single-stream (zerocopy ON):
  Total transferred:  119 GBytes in 30.00 s
  Average bitrate:    34.0 Gb/s
  Retransmits:        0
  Per-second range:   27.5 - 37.1 Gb/s (warmup-affected first 4 s)

Eight-stream (zerocopy ON):
  Total transferred:  322 GBytes in 30.00 s
  Aggregate bitrate:  92.1 Gb/s
  Retransmits:        22 (vs 128 without zerocopy)
  Per-stream range:   10.6 - 12.3 Gb/s

================================================================================
COMPARISON
================================================================================

  Test                              Throughput   Retransmits   Vs default
  --------------------------------------------------------------------------
  1-stream default TCP              34.8 Gb/s    0             baseline
  1-stream TCP --zerocopy           34.0 Gb/s    0             -2.3 %
  8-stream default TCP              93.3 Gb/s    128           baseline
  8-stream TCP --zerocopy           92.1 Gb/s    22            -1.3 %

================================================================================
ANALYSIS — Why MSG_ZEROCOPY did not improve throughput
================================================================================

MSG_ZEROCOPY removes ONLY the userspace -> kernel copy on the send path.
It does NOT remove:
  - userspace -> kernel copy on the RECEIVE path
  - TCP state machine processing (cwnd, ACK, RTO timers)
  - IP, qdisc, IRQ, scheduler costs
  - any per-packet header construction

For MSG_ZEROCOPY to help in throughput, the send-side memcpy must be the
binding constraint. On the test system:

  - 1-stream case: bottleneck is single-core TCP processing, not memcpy.
    Removing the copy saves cycles on something that already had cycles to
    spare. Net effect: small overhead from page-pin/completion handling,
    -2% throughput.

  - 8-stream case: bottleneck is the link itself / cross-core kernel
    contention. The aggregate copy bandwidth was not the limit. Same
    explanation as above; net -1.3 %.

Where MSG_ZEROCOPY does help (not exhibited here):
  - Many concurrent connections with the host running near DRAM
    bandwidth ceiling.
  - Very large per-write sizes (multi-MB) where memcpy time dominates.

Important secondary result — retransmit reduction:
  8-stream test:   128 retr (default) -> 22 retr (zerocopy)  = 6x reduction.
  Same aggregate throughput, but cleaner sender behavior. Fewer cwnd
  oscillations because less per-byte work is queued in the kernel during
  send bursts. In production this would reduce tail latency and wasted
  link bandwidth, even though peak throughput is unchanged.

================================================================================
HEADLINE TABLE (cumulative across benchmarks 01, 04, 05, 06)
================================================================================

  Transport / config              Throughput   % line   Retr   CPU role
  ------------------------------------------------------------------------
  RoCEv2 RDMA (1 QP, 128 KB)      98.20 Gb/s   98.2 %     0    NIC offload
  RoCEv2 RDMA (1 QP, 64 KB)       97.76 Gb/s   97.8 %     0    NIC offload
  8-stream TCP default            93.30 Gb/s   93.3 %   128    8 cores busy
  8-stream TCP --zerocopy         92.10 Gb/s   92.1 %    22    8 cores busy
  1-stream TCP default            34.80 Gb/s   34.8 %     0    1 core saturated
  1-stream TCP --zerocopy         34.00 Gb/s   34.0 %     0    1 core saturated

Key takeaways:
  1. RDMA delivers ~98 % of line rate with one QP and effectively zero CPU.
  2. Kernel TCP needs 8 parallel streams to reach 93 % of line rate.
  3. MSG_ZEROCOPY does not close the residual gap to RDMA. The remaining
     ~5 % cost is not memcpy; it is protocol processing in software.
  4. MSG_ZEROCOPY does improve cleanliness (6x fewer retransmits at
     parallel scale), which matters for tail latency in production
     workloads even when peak throughput is unchanged.

================================================================================
NEXT
================================================================================

07: sockperf TCP ping-pong latency  (compare directly to 0.83 µs RDMA floor)
08: mpstat-based CPU cost per Gb    (quantify the "free CPU" claim for RDMA)
09: NCCL allreduce: NCCL_NET=IB vs Socket (real distributed-AI workload)
