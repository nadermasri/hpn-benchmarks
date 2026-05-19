# Hardware & Software Setup

## Physical Setup

Two Dell Precision T5810 workstations connected back-to-back via a single
QSFP28 DAC cable. No switch, no router — direct NIC-to-NIC connection.

```
[pc1n] ──── QSFP28 DAC 0.5m ──── [pc2n]
 192.168.100.1                    192.168.100.2
 mlx5_1 (port 1)                 mlx5_0 (port 1)
```

## Node Specifications (identical on both nodes)

| Component | Details |
|---|---|
| Chassis | Dell Precision T5810 |
| CPU | Intel Xeon E5-1620 v3 — Haswell-EP — 4 cores / 8 threads — 3.5 GHz base |
| RAM | 32 GB ECC DDR4 |
| Storage | 1 TB HGST 7200rpm SATA HDD |
| GPU | NVIDIA GeForce RTX 3060 12 GB (GA106) |
| NIC | Mellanox ConnectX-5 MT4119 — dual-port QSFP28 — FW 16.32.1010 |
| Cable | FS Q28-PC005 · QSFP28 passive DAC · 0.5 m copper |

**Important GPU note:** The RTX 3060 is a consumer card. It does NOT support
GPUDirect RDMA. NCCL allreduce traffic must bounce through host RAM,
capping NCCL bandwidth at ~50 Gb/s instead of ~95 Gb/s achievable with
GPUDirect (A100, H100, RTX A6000, etc.).

## Network Addressing

| Node | Hostname | 100G IP | RDMA device | Management IP |
|---|---|---|---|---|
| Node 1 | pc1n | 192.168.100.1/24 | mlx5_1 (port 1) | 137.194.194.44 |
| Node 2 | pc2n | 192.168.100.2/24 | mlx5_0 (port 1) | 137.194.194.134 |

MTU: 9000 (jumbo frames) on both 100G interfaces.

## Software Stack

Installed identically on both nodes:

| Component | Version |
|---|---|
| OS | Ubuntu Server 24.04.4 LTS |
| Kernel | 6.8.0-111-generic |
| RDMA stack | DOCA-OFED 26.01 (DOCA-Host 3.3.0-088000) |
| NVIDIA driver | 580.126.20 |
| CUDA | 12.6.85 |
| NCCL | 2.30.4+cuda13.2 |
| nccl-tests | 2.18.3 |
| OpenMPI | 4.1.6 |
| perftest | system package (ib_send_bw, ib_send_lat) |
| iperf3 | system package |
| sockperf | system package |

## RDMA Configuration

- NIC ports configured in Ethernet mode (not InfiniBand native mode)
- RoCEv2 transport (RDMA over Converged Ethernet v2 — encapsulated in UDP/IP)
- Connection type: Reliable Connected (RC) — same guarantees as TCP but in NIC hardware
- GID index: 3 (IPv4-mapped IPv6 → RoCEv2)

Verify RDMA is working:

```bash
# Check RDMA devices
ibv_devices

# Check port state (should show: PORT_ACTIVE, LinkLayer: Ethernet)
ibv_devinfo -d mlx5_1    # node 1
ibv_devinfo -d mlx5_0    # node 2

# Quick connectivity test (server on node 2, client on node 1)
ib_send_bw -d mlx5_0 -i 1 -F -R --report_gbits         # node 2
ib_send_bw -d mlx5_1 -i 1 -F -R --report_gbits 192.168.100.2  # node 1
```

## Pre-benchmark Tuning

Applied before every benchmark session:

```bash
# CPU governor — performance mode on all cores
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Confirm
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# → performance
```

See `config/tuning.md` for full sysctl and IRQ affinity notes.

## SSH Setup

Passwordless SSH between nodes in both directions (needed for mpirun):

```bash
# Generate key (if not exists)
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519

# Copy to other node
ssh-copy-id pc2n@192.168.100.2   # from node 1
ssh-copy-id pc1n@192.168.100.1   # from node 2

# Add SSH config to map hostnames to correct users
cat >> ~/.ssh/config << 'EOF'
Host pc2n pc2n-100g 192.168.100.2
    User pc2n
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no

Host pc1n pc1n-100g 192.168.100.1
    User pc1n
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
EOF
chmod 600 ~/.ssh/config
```

## Known Issues / Gotchas

**Ubuntu default /etc/hosts:** Ubuntu 24.04 adds `127.0.1.1 hostname` by default.
This breaks OpenMPI — it resolves the hostname to localhost and hangs on bootstrap.
Remove these lines before running mpirun:

```bash
sudo sed -i '/127.0.1.1/d' /etc/hosts
# Then add the 100G IPs instead (see config/etc-hosts)
```

**Temperature sensor:** Both nodes report ~100-112°C on the CPU temperature
sensor. This is a sensor reporting bug, not actual thermal throttling —
the systems run stably through hours of benchmarking.
