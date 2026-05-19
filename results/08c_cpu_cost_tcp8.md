# Benchmark 08c — CPU cost during 8-stream kernel TCP
Date: 2026-05-18

================================================================================
COMMANDS
================================================================================

Server (node 2):
  sudo pkill -9 iperf3 ; sleep 1
  mpstat 1 35 > /tmp/cpu_tcp8_server.txt &
  iperf3 -s -1

Client (node 1):
  mpstat 1 35 > /tmp/cpu_tcp8_client.txt &
  iperf3 -c 192.168.100.2 -t 30 -P 8

================================================================================
THROUGHPUT (steady-state during active 30 s)
================================================================================

Aggregate (8 streams):  93.6 Gb/s sender / 93.6 Gb/s receiver
Total transferred    :  327 GB
Total retransmits    :  47

Per-stream range     : 10.4 - 13.5 Gb/s

================================================================================
CPU UTILIZATION (during active phase)
================================================================================

Sender (node 1):
  %usr   :  ~  1.0
  %sys   :  ~ 57.0    ← kernel TCP, copy_from_user, headers, qdisc
  %soft  :  ~ 15.6    ← NIC TX completion softirq
  %idle  :  ~ 26.4    (= ~2.1 cores idle, 5.9 cores busy)

  Total during test : ~ 73 % of all 8 cores = ~5.8 cores fully busy

Receiver (node 2):
  %usr   :  ~  1.9
  %sys   :  ~ 62.7    ← TCP, copy_to_user, ACK generation
  %soft  :  ~ 32.9    ← NAPI RX poll, very heavy at near-line-rate
  %idle  :  ~  2.4    (= almost zero idle; 7.8 of 8 cores busy)

  Total during test : ~ 97 % of all 8 cores = ~7.8 cores busy

================================================================================
INTERPRETATION — RX-side dominance of softirq
================================================================================

The receiver has a structural disadvantage in kernel TCP:

  - Every received packet triggers NIC RX -> IRQ -> NAPI poll cycle.
    At ~94 Gb/s with average packet size ~5 KB (TSO/GRO active), this is
    ~2.3 million packets/sec. The kernel batches via NAPI but %soft still
    grows to ~33 % across cores.

  - Each stream's TCP processing (in-order delivery, ACK generation, cwnd
    tracking) runs on a CPU determined by Receive Side Scaling (RSS hash
    of the 5-tuple). RSS distributes load across cores but cannot reduce
    total work.

  - copy_to_user runs once per recv() syscall, in process context, on
    whichever core is running iperf3's reader for that stream.

The sender, by contrast, can amortize work better:
  - TSO offloads segmentation to the NIC; the kernel hands large
    "superpackets" to the driver.
  - The application controls when send() returns (cwnd permitting), so
    softirq cost is lower (mostly TX completions, smaller per-packet).

This sender/receiver asymmetry (sender 73 %, receiver 97 %) is a robust
characteristic of large-fan-in TCP servers and is invisible to bandwidth
benchmarks alone.

================================================================================
FULL CPU-COST TABLE (cumulative across benchmarks 08a, 08b, 08c)
================================================================================

                                Throughput  CPU%   Cores  cores/Gb/s  Gb/s/core
  -----------------------------------------------------------------------------
  RoCEv2 RDMA sender             98.27     12.5    1.00    0.0102      98.3
  RoCEv2 RDMA receiver           98.04     12.5    1.00    0.0102      98.0
  TCP 1-stream sender            34.30     11.8    0.95    0.0277      36.1
  TCP 1-stream receiver          34.30     10.0    0.80    0.0233      42.9
  TCP 8-stream sender            93.60     73.0    5.84    0.0624      16.0
  TCP 8-stream receiver          93.60     97.0    7.76    0.0829      12.1

Per Gb/s of throughput delivered:

  RDMA              : 0.0102 cores
  TCP 1-stream      : 0.0277 cores   (2.7x more than RDMA)
  TCP 8-stream RX   : 0.0829 cores   (8.1x more than RDMA)

In addition, the entire CPU cost of RDMA was application polling (%usr).
The entire CPU cost of TCP is kernel work (%sys + %soft) which the
application cannot reclaim.

================================================================================
INTERPRETATION FOR DISTRIBUTED-AI WORKLOADS
================================================================================

On a training node running:
  - 8 GPUs doing forward/backward,
  - data loader and DALI/torchvision preprocessing,
  - Python optimizer and CUDA driver,
  - and a network transport for gradient sync,

the network's CPU cost competes with everything else on the host.

  - With RDMA: ~1 core (or ~0 if event-mode) per 100 Gb/s flow. The host
    CPU remains free for data loading and optimizer/runtime work. GPU
    utilization stays at 95-99 %.

  - With kernel TCP at 8 streams: ~6-8 cores per 100 Gb/s flow. On nodes
    where the CPU is already loaded by data preprocessing, this leads to
    CPU contention, longer host-side latency on gradient packing, and
    observable GPU idle gaps in profile traces. The all-reduce step
    becomes a sequential bottleneck on the host.

This is the structural reason every major cloud provider (AWS p4d/p5,
Azure ND_v4/v5, GCP a2/a3) ships dedicated RDMA NICs for ML training:
not because TCP "isn't fast", but because TCP at line rate steals the
CPU budget required to keep GPUs fed.

================================================================================
HEADLINE
================================================================================

  Throughput per CPU core (sender + receiver, sum of both):

    RoCEv2 RDMA       : 98 Gb/s on 2 cores total = 49 Gb/s/core
    TCP 8-stream      : 94 Gb/s on 14 cores total = 6.7 Gb/s/core
                        -> 7x worse than RDMA

  Where the CPU goes:
    RDMA  : 100 % user-space CQ polling (could be 0 with event mode)
    TCP-8 : 90 %+ kernel (%sys + %soft); mandatory, cannot be eliminated
