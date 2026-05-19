# Benchmark 08b — CPU cost during 1-stream kernel TCP
Date: 2026-05-18

================================================================================
COMMANDS
================================================================================

Server (node 2):
  mpstat 1 35 > /tmp/cpu_tcp1_server.txt &
  iperf3 -s -1
  (-1 makes iperf3 server exit after one client disconnects, so wait works)

Client (node 1):
  mpstat 1 35 > /tmp/cpu_tcp1_client.txt &
  iperf3 -c 192.168.100.2 -t 30

================================================================================
THROUGHPUT (confirmed steady-state)
================================================================================

Client BW : 34.3 Gb/s sender / 34.3 Gb/s receiver
Total     : 120 GB transferred in 30 s
Retr      : 0 retransmits (no congestion loss)

================================================================================
CPU UTILIZATION (during active 30 s)
================================================================================

Client (sender, node 1):
  %usr     : ~ 0.25
  %sys     : ~11.10  ← dominant
  %soft    : ~ 1.30
  %iowait  : ~ 0.55  (occasional disk sync)
  %idle    : ~87.40

  Total during active phase: ~11.8 % (= ~0.95 cores)
  Average across 35 s including idle tail: 9.47 + 0.20 + 1.13 = 10.80 %

Server (receiver, node 2):
  %usr     : ~ 0.50
  %sys     : ~ 8.30   ← dominant
  %soft    : ~ 1.20
  %idle    : ~89.50

  Total during active phase: ~10.0 % (= ~0.80 cores)
  Average across 35 s including idle tail: 6.60 + 0.39 + 1.09 = 8.08 %

================================================================================
DIRECT COMPARISON: RDMA vs TCP-1 CPU SIGNATURE
================================================================================

                          RoCEv2 RDMA       TCP 1-stream
                          (98.27 Gb/s)      (34.3 Gb/s)
  Total CPU (sender)      12.50 %           11.80 %
  Total CPU (receiver)    12.50 %           10.00 %

  % user (sender)         12.50             0.25
  % sys  (sender)          0.00            11.10  ←  kernel TCP processing
  % soft (sender)          0.00             1.30  ←  softirq packet handling

  % user (receiver)       12.50             0.50
  % sys  (receiver)        0.00             8.30  ←  copy_to_user + TCP
  % soft (receiver)        0.00             1.20

  Per-Gb cost (sender)
     cores / (Gb/s)        0.0102           0.0276
  Throughput per core      ~98 Gb/s         ~36 Gb/s

  Cycles spent on:
     kernel protocol       0                ~all
     copy_to/from_user     0                ~present
     application work      ~all (CQ poll)   minimal

================================================================================
INTERPRETATION
================================================================================

The two tests use similar total CPU percentages but fundamentally different
work:

(1) RDMA sender uses 1 core, all in user space, polling a Completion
    Queue. Kernel %sys = 0, %soft = 0. The NIC moves all data via PCIe
    DMA without invoking any kernel code on the data path.

(2) TCP sender uses ~1 core, almost entirely in kernel space (%sys ~11,
    %soft ~1.3). The kernel runs the TCP state machine, performs the
    copy_from_user, builds segments, processes ACKs, manages cwnd, fires
    softirqs for completion. None of this would be necessary for RDMA.

If the RDMA application requested event-triggered completions (epoll-style
wakeups) instead of polling, its CPU footprint would drop close to zero
with a small latency penalty. TCP cannot do this -- the kernel has no
optional component; %sys cost is mandatory for every packet.

The recurring "%iowait = 3.6 %" spike every ~6 s on the client is
unrelated background disk activity (the live system journal writeback);
ignore for benchmark purposes.

================================================================================
HEADLINE
================================================================================

  Throughput per CPU core:
    RoCEv2 RDMA     ~ 98 Gb/s per core (kernel cost: 0)
    Kernel TCP (1)  ~ 36 Gb/s per core (kernel cost: ~all of it)

  Per Gb/s of throughput, kernel TCP needs 2.7x more CPU than RDMA,
  and that CPU time is in kernel space and unavoidable.
