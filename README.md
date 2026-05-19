# hpn-benchmarks

Benchmarking RoCEv2 RDMA against kernel TCP on a 100 Gb/s back-to-back link,
with NCCL allreduce for distributed AI workloads.

Part of a research internship at Télécom Paris, May 2026.

## Hardware
- 2× Dell Precision T5810 (Xeon E5-1620 v3, 32 GB, RTX 3060)
- Mellanox ConnectX-5 (100 GbE, RoCEv2)
- QSFP28 DAC 0.5 m, back-to-back (no switch)
- Ubuntu 24.04 · DOCA-OFED 26.01 · CUDA 12.6 · NCCL 2.30

## Key results

| Test | Transport | Result |
|---|---|---|
| Throughput (raw) | RDMA 1 conn | 97.76 Gb/s |
| Throughput (raw) | TCP 8 streams | 93.30 Gb/s |
| Latency (1-way) | RDMA | 0.83 µs |
| Latency (1-way) | TCP | 12.28 µs |
| CPU per Gb/s | RDMA | 0.010 cores |
| CPU per Gb/s | TCP-8 | 0.083 cores |
| NCCL allreduce | RDMA | 50.6 Gb/s |
| NCCL allreduce | TCP | 10.3 Gb/s |

## How to reproduce
See benchmarks/ — each script is self-contained and annotated.
Requires both nodes reachable at 192.168.100.1/2 with passwordless SSH.
