# Benchmark 02 — RoCEv2 RDMA Send Latency (2-byte messages)
Date: 2026-05-18

================================================================================
COMMAND
================================================================================

Server (node 2):
  ib_send_lat -d mlx5_0 -i 1 -F -R

Client (node 1):
  ib_send_lat -d mlx5_1 -i 1 -F -R 192.168.100.2

Tool configuration:
  Transport type : IB over Ethernet (RoCEv2)
  Connection type: RC (Reliable Connection)
  TX depth       : 1 (synchronous ping-pong, no pipelining)
  MTU            : 4096 B
  Max inline data: 236 B (small msgs fit in WQE, no DMA round-trip)
  Iterations     : 1000

NB: ib_send_lat reports HALF round-trip = one-way latency.

================================================================================
RESULT (client side, 2-byte payload)
================================================================================

  #bytes  #iter  t_min    t_max    t_typical  t_avg   t_stdev  p99     p99.9
  2       1000   0.80 µs  1.89 µs  0.83 µs    0.84 µs ~0       1.01 µs 1.89 µs

Server-side cross-check:
  2       1000   0.81 µs  1.88 µs  0.83 µs    0.84 µs ~0       0.93 µs 1.88 µs

Headline: 0.83 µs one-way latency for 2-byte messages over RoCEv2.

================================================================================
COMPARISON CONTEXT
================================================================================

ICMP ping on same link (192.168.100.x): avg 0.154 ms full RTT = ~77 µs one-way.
RoCEv2 small-msg one-way: 0.83 µs.
Ratio: ~93× lower latency with RDMA versus kernel TCP/ICMP path.

The gap represents the cost of the Linux kernel network stack:
socket layer, TCP state machine, IP layer, qdisc, IRQ, scheduler, copies.
RDMA bypasses all of this; user space writes WQEs that the NIC processes
directly via PCIe doorbells, with hardware-managed reliable delivery.

================================================================================
NEXT
================================================================================

Run latency size sweep: ib_send_lat ... -a
Then move to TCP-side benchmarks (iperf3, iperf3 --zerocopy, sockperf).
