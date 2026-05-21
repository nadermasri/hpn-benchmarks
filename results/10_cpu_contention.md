# Benchmark 10 — CPU Contention Under Network Load
Date: 2026-05-20

## Methodology

Simulated a realistic training node by running stress-ng with 4 CPU workers
(representing data loading, preprocessing, Python interpreter work) while
network transport runs in parallel.

Metric: stress-ng bogo ops/s. Higher means the application got more CPU.

Baseline (no network active):
- Node 1: 5,689 ops/s
- Node 2: 5,858 ops/s

## Results

| Test                       | Node 1 ops/s | Node 2 ops/s | Net BW    | Retrx |
|----------------------------|--------------|--------------|-----------|-------|
| Baseline (no network)      | 5,689        | 5,858        | -         | -     |
| + NCCL RDMA                | ~5,689       | ~5,858       | 51.8 Gb/s | 0     |
| + NCCL TCP                 | 5,522        | 5,587        | 10.6 Gb/s | -     |
| + iperf3 TCP 8-stream      | 4,107        | 4,137        | 66.7 Gb/s | 4,055 |

Drop versus baseline:
- RDMA: ~0% on both nodes
- NCCL TCP: -2.9% (node 1), -4.6% (node 2)
- iperf3 TCP-8: -27.8% (node 1), -29.4% (node 2); network also dropped -28.5%

## Key findings

1. RDMA causes zero CPU contention. %sys = 0.66 percent during NCCL RDMA.
The application work is completely unaffected. The kernel never touches
the data path.

2. NCCL TCP causes small contention (3 to 5 percent) because NCCL's
