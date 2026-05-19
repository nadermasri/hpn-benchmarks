# hpn-benchmarks

**High-Performance Networking Benchmarks — RoCEv2 RDMA vs. Kernel TCP at 100 Gb/s**

Research internship, Télécom Paris — May 2026  
*Nader Al Masri · Research Intern, Distributed AI Systems & Networking*

---

## Overview

This repository documents a systematic benchmarking study comparing two high-performance network transports on a back-to-back 100 Gb/s link:

- **RoCEv2 RDMA** (Mellanox ConnectX-5, kernel-bypass via libibverbs)
- **Kernel TCP** (Linux 6.8 standard stack, with and without `MSG_ZEROCOPY`)
- **NCCL allreduce** over both transports (the collective used by PyTorch DDP for gradient synchronisation)

The goal: understand not just *how fast* each transport is, but *why* — tracing the bottleneck to the kernel, the PCIe bus, or the GPU SKU.

---

## Key Results

| # | Test | Transport | Result |
|---|---|---|---|
| 01 | Raw throughput | RoCEv2 RDMA (1 QP, 64 KB) | **97.76 Gb/s** |
| 01 | Raw throughput (peak) | RoCEv2 RDMA (1 QP, 128 KB) | **98.20 Gb/s** |
| 02 | One-way latency | RoCEv2 RDMA (2 B, mean) | **0.83 µs** |
| 04 | Raw throughput | Kernel TCP (1 stream) | **34.8 Gb/s** |
| 05 | Raw throughput | Kernel TCP (8 streams) | **93.3 Gb/s** |
| 06 | Raw throughput | TCP + `MSG_ZEROCOPY` (8 streams) | **92.1 Gb/s** |
| 07 | One-way latency | Kernel TCP (mean / p99 / max) | **12.28 / 16.15 / 79.18 µs** |
| 08a | CPU cost | RoCEv2 RDMA @ 98 Gb/s | **0.0102 cores/Gb/s** (all user-space) |
| 08c | CPU cost | TCP 8-stream RX @ 94 Gb/s | **0.0829 cores/Gb/s** (all kernel) |
| 09a | NCCL allreduce | RDMA, 2 nodes, RTX 3060 | **50.6 Gb/s** (capped by no GPUDirect) |
| 09b | NCCL allreduce | TCP socket fallback | **10.3 Gb/s** |

### Headline comparisons

```
Latency    :  RDMA 0.83 µs  vs  TCP 12.28 µs   →  15× lower mean
Latency p99:  RDMA 1.01 µs  vs  TCP 16.15 µs   →  16× lower p99
CPU/Gb/s   :  RDMA 0.010    vs  TCP-8 0.083     →   8× less CPU per Gb/s
NCCL peak  :  RDMA 50.6 Gb/s vs TCP 10.3 Gb/s  →   5× faster allreduce
```

The RDMA CPU cost is entirely in user-space (application polling its completion queue) and can be reduced further with event-mode completions. The TCP CPU cost is in kernel-space (`%sys` + `%soft`) and is structurally unavoidable.

---

## Hardware

| Component | Spec |
|---|---|
| Nodes | 2× Dell Precision T5810 (identical) |
| CPU | Intel Xeon E5-1620 v3 · Haswell-EP · 4C/8T · 3.5 GHz |
| RAM | 32 GB ECC DDR4 |
| GPU | NVIDIA GeForce RTX 3060 12 GB (GA106) — **no GPUDirect RDMA** |
| NIC | Mellanox ConnectX-5 MT4119 · FW 16.32.1010 · dual-port QSFP28 |
| Cable | FS Q28-PC005 · QSFP28 DAC · 0.5 m copper · **back-to-back, no switch** |
| OS | Ubuntu Server 24.04.4 LTS · kernel 6.8.0-111-generic |
| RDMA stack | DOCA-OFED 26.01 (DOCA-Host 3.3.0) |
| GPU driver | NVIDIA 580.126.20 · CUDA 12.6.85 |
| NCCL | 2.30.4+cuda13.2 |
| MPI | OpenMPI 4.1.6 |

Node 1 (`pc1n`): 100G IP `192.168.100.1`, RDMA device `mlx5_1`  
Node 2 (`pc2n`): 100G IP `192.168.100.2`, RDMA device `mlx5_0`

---

## Repository Structure

```
hpn-benchmarks/
├── README.md
├── hardware/
│   └── setup.md                     ← full hardware/software specs + setup notes
├── config/
│   ├── 100g-netplan.yaml            ← Netplan config for the 100G interface
│   ├── etc-hosts                    ← /etc/hosts used during benchmarks
│   └── tuning.md                    ← MTU, governor, sysctl settings
├── benchmarks/
│   ├── 01_rdma_throughput.sh
│   ├── 02_rdma_latency.sh
│   ├── 03_tcp_throughput.sh
│   ├── 04_tcp_zerocopy.sh
│   ├── 05_tcp_latency.sh
│   ├── 06_cpu_cost.sh
│   └── 07_nccl_allreduce.sh
├── results/                         ← raw output + per-test analysis
│   ├── 01_rocev2_send_bw.md
│   ├── 02_rocev2_send_lat.md
│   ├── 03_rocev2_send_lat_sweep.md
│   ├── 04_tcp_iperf3_baseline.md
│   ├── 05_tcp_iperf3_parallel8.md
│   ├── 06_tcp_zerocopy.md
│   ├── 07_tcp_sockperf_latency.md
│   ├── 08a_cpu_cost_rdma.md
│   ├── 08b_cpu_cost_tcp1.md
│   ├── 08c_cpu_cost_tcp8.md
│   ├── 09a_nccl_allreduce_rdma.md
│   └── 09b_nccl_allreduce_tcp.md
├── diagrams/                        ← generated PNG figures
├── report/
│   └── benchmarks_report.md        ← full technical report
└── analysis/
    └── make_diagrams.py            ← generates all figures from results
```

---

## How to Reproduce

### Prerequisites (both nodes)

```bash
# RDMA tools
sudo apt install -y libibverbs-dev ibverbs-utils perftest

# TCP tools
sudo apt install -y iperf3 sockperf

# NCCL tests
git clone https://github.com/NVIDIA/nccl-tests.git
cd nccl-tests && make MPI=1 \
    MPI_HOME=/usr/lib/x86_64-linux-gnu/openmpi \
    CUDA_HOME=/usr/local/cuda NCCL_HOME=/usr -j4

# CPU governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Network config

Both nodes need the 100G interface at MTU 9000 with static IPs.
See `config/100g-netplan.yaml` and `config/etc-hosts`.

### Running benchmarks

Each script in `benchmarks/` is self-contained and annotated. They assume:
- Node 1 (`pc1n`) at `192.168.100.1`, RDMA device `mlx5_1`
- Node 2 (`pc2n`) at `192.168.100.2`, RDMA device `mlx5_0`
- Passwordless SSH in both directions between the nodes

```bash
# From node 1 — RDMA throughput
bash benchmarks/01_rdma_throughput.sh

# From node 1 — NCCL allreduce (RDMA and TCP)
bash benchmarks/07_nccl_allreduce.sh
```

---

## Key Finding: Why the RTX 3060 Caps NCCL at 50 Gb/s

Raw host-to-host RDMA delivers 98 Gb/s. NCCL allreduce delivers only 50 Gb/s. The gap is not the network — it is the GPU.

The RTX 3060 does not support **GPUDirect RDMA (GDR)**. Without GDR, every GPU-to-network transfer bounces through host RAM:

```
Without GDR (this setup):
  GPU → [PCIe] → host RAM → NIC → wire → NIC → host RAM → [PCIe] → GPU
  ~50 Gb/s  (limited by PCIe Gen3 ×16 host-bounce on both ends)

With GDR (A100, H100, RTX A6000):
  GPU → NIC → wire → NIC → GPU
  ~95 Gb/s  (limited by the wire)
```

GDR support is gated to professional/datacenter SKUs as a product segmentation decision.

---

## Next Steps

- [ ] Distributed PyTorch DDP training (RDMA vs. TCP) — translate network numbers into training step time
- [ ] CPU contention under realistic training load (data loader + Python active)
- [ ] Server-class GPU (A100 / RTX A6000) to validate the 50 → ~95 Gb/s GDR jump

---

*Télécom Paris · Research Internship · May 2026*
