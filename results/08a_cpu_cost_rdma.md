# Benchmark 08a — CPU cost during RoCEv2 RDMA transfer
Date: 2026-05-18

================================================================================
COMMANDS
================================================================================

Server (node 2):
  mpstat 1 35 > /tmp/cpu_rdma_server.txt &
  ib_send_bw -d mlx5_0 -i 1 -F -R --report_gbits -D 30

Client (node 1):
  mpstat 1 35 > /tmp/cpu_rdma_client.txt &
  ib_send_bw -d mlx5_1 -i 1 -F -R --report_gbits -D 30 192.168.100.2

Duration: 30 s active transfer + ~5 s startup/teardown.
mpstat samples once per second, reports per-core averages across all 8 CPUs.

================================================================================
THROUGHPUT (confirmed steady-state)
================================================================================

Client BW : 98.27 Gb/s
Server BW : 98.04 Gb/s
Messages  : 2,991,867 of 65,536 B in 30 s (= ~99,729 msg/s)
Total     : ~368 GB transferred per direction

================================================================================
CPU UTILIZATION (during active 30 s)
================================================================================

Client (node 1, sender):
  %usr   : ~12.50  (steady)
  %sys   :  ~0.00
  %irq   :  ~0.00
  %soft  :  ~0.00
  %idle  : ~87.50  (= 7 of 8 cores idle)
  Average over the test window: 12.50 % total CPU

Server (node 2, receiver):
  %usr   : ~12.50  (steady)
  %sys   :  ~0.00
  %irq   :  ~0.00
  %soft  :  ~0.00
  %idle  : ~87.50
  Average over the test window: 12.50 % total CPU

Interpretation:
  12.50 % of 8 cores = exactly 1.00 core fully busy.
  Both nodes use the same: one core spinning, seven cores 100% idle.

================================================================================
WHAT THAT 1 CORE IS ACTUALLY DOING
================================================================================

  %usr = 12.50 %, %sys = 0, %soft = 0.

This signature is diagnostic:
  - All CPU time is in user space.
  - Kernel does no protocol work.
  - No softirq from the NIC (no interrupts on data path; polling mode).

The busy core is the ib_send_bw process polling its Completion Queue (CQ).
It is NOT doing any of:
  - copy_to_user / copy_from_user
  - TCP state machine, header construction, ACK handling
  - IP layer, qdisc, routing
  - softirq packet processing

If the application requested event-triggered completions
(ibv_req_notify_cq + epoll) the CPU usage would drop further toward zero
with a small increase in completion latency. Throughput would not change
because the NIC, not the CPU, drives the data path.

================================================================================
CPU COST METRIC
================================================================================

  Cores per Gb/s = (CPU% / 100 × N_cores) / Throughput
                 = (0.125 × 8) / 98.27 Gb/s
                 = 0.01018 cores / (Gb/s)

  Equivalent: 1 core can sustain ~98 Gb/s of RDMA throughput.

  Kernel-side cost: effectively zero (%sys ≈ 0, %soft ≈ 0).

================================================================================
NEXT
================================================================================

Repeat with TCP (1 stream and 8 streams) to compare:
  - cores per Gb/s
  - distribution between %usr / %sys / %soft
  - kernel cost
