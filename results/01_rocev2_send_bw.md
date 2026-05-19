# Benchmark 01 — RoCEv2 RDMA Send Bandwidth
Date: 2026-05-18
Operator: Nader Almasri
Internship: Research Intern — High-Performance Networking & Distributed AI Systems
Institution: Télécom Paris

================================================================================
HARDWARE & ENVIRONMENT
================================================================================

Topology: 2-node back-to-back over 100G QSFP28 DAC (FS Q28-PC005, 0.5m copper)

Node 1 (pc1n)
  Chassis    : Dell Precision T5810
  CPU        : Intel Xeon E5-1620 v3 (Haswell-EP, 4C/8T, 3.5 GHz)
  RAM        : 32 GB ECC DDR4
  GPU        : NVIDIA GeForce RTX 3060 (12 GB, GA106)
  NIC        : Mellanox ConnectX-5 (MT4119), FW 16.32.1010
  Benchmark IF: ens2f1np1 (mlx5_1), IP 192.168.100.1/24, MTU 9000
  Mgmt IP    : 137.194.194.44

Node 2 (pc2n)
  Chassis    : Dell Precision T5810
  CPU        : Intel Xeon E5-1620 v3 (Haswell-EP, 4C/8T, 3.5 GHz)
  RAM        : 32 GB ECC DDR4
  GPU        : NVIDIA GeForce RTX 3060 (12 GB, GA106)
  NIC        : Mellanox ConnectX-5 (MT4119), FW 16.32.1010
  Benchmark IF: ens2f0np0 (mlx5_0), IP 192.168.100.2/24, MTU 9000
  Mgmt IP    : 137.194.194.134

Software stack (both nodes, identical)
  OS         : Ubuntu Server 24.04.4 LTS
  Kernel     : 6.8.0-111-generic
  OFED       : DOCA-OFED 26.01 (DOCA-Host 3.3.0-088000)
  NVIDIA drv : 580.126.20
  CUDA       : 12.6.85
  RDMA stack : ib_core, mlx5_ib, rdma_cm loaded; openibd active

Pre-test conditions
  CPU governor: performance (all 8 cores per node)
  Link status : Active, LinkUp, Rate 100 Gb/s, Link layer Ethernet (RoCEv2)
  ICMP RTT    : 0.154 ms avg over 192.168.100.0/24
  MTU         : 9000 on Ethernet; 4096 path MTU used by RoCE

================================================================================
TEST 1a — Default 64 KB message size
================================================================================

Command (server, node 2):
  ib_send_bw -d mlx5_0 -i 1 -F -R --report_gbits

Command (client, node 1):
  ib_send_bw -d mlx5_1 -i 1 -F -R --report_gbits 192.168.100.2

Configuration reported by tool:
  Transport type : IB (over Ethernet → RoCEv2)
  Connection type: RC (Reliable Connection)
  Queue pairs    : 1
  TX depth       : 128
  CQ moderation  : 1
  Mtu            : 4096 B
  GID index      : 3 (IPv4-mapped IPv6 → RoCEv2)
  rdma_cm QPs    : ON
  Iterations     : 1000

Result:
  #bytes   #iter   BW peak[Gb/s]   BW avg[Gb/s]   MsgRate[Mpps]
  65536    1000    97.76           97.76          0.186467

Server-side report (confirming):
  65536    1000     0.00           98.02          0.186956

Headline: 97.76 Gb/s sustained = 97.76% of 100 Gb/s line rate.

================================================================================
TEST 1b — Full message-size sweep (2 B to 8 MB, -a flag)
================================================================================

Command (server, node 2):
  ib_send_bw -d mlx5_0 -i 1 -F -R --report_gbits -a

Command (client, node 1):
  ib_send_bw -d mlx5_1 -i 1 -F -R --report_gbits -a 192.168.100.2

Configuration changes from 1a:
  CQ moderation  : 100  (auto-set by tool in sweep mode)

Result (client-side, what hits the wire):

  #bytes      #iter   BW peak[Gb/s]   BW avg[Gb/s]   MsgRate[Mpps]
  2           1000    0.092           0.091          5.680527
  4           1000    0.25            0.24           7.599312
  8           1000    0.51            0.50           7.872245
  16          1000    1.01            1.00           7.839870
  32          1000    2.00            1.95           7.599180
  64          1000    4.04            4.01           7.834394
  128         1000    8.05            8.02           7.830258
  256         1000    15.65           15.58          7.607306
  512         1000    32.00           31.89          7.785529
  1024        1000    63.29           63.16          7.709930
  2048        1000    89.88           89.67          5.472855
  4096        1000    96.62           96.59          2.947557
  8192        1000    97.36           97.34          1.485304
  16384       1000    97.73           97.73          0.745586
  32768       1000    97.99           97.99          0.373796
  65536       1000    98.16           98.15          0.187212
  131072      1000    98.20           98.20          0.093654   ← peak
  262144      1000    96.85           96.82          0.046165
  524288      1000    96.50           96.49          0.023005
  1048576     1000    96.37           96.36          0.011487
  2097152     1000    96.39           96.36          0.005743
  4194304     1000    96.22           96.22          0.002868
  8388608     1000    96.16           96.14          0.001433

Result (server-side, for cross-check):

  #bytes      #iter   BW peak[Gb/s]   BW avg[Gb/s]   MsgRate[Mpps]
  2           1000    0.000           0.095          5.918027
  4           1000    0.00            0.25           7.759056
  8           1000    0.00            0.51           8.017208
  16          1000    0.00            1.02           7.970978
  32          1000    0.00            2.00           7.826600
  64          1000    0.00            4.11           8.029908
  128         1000    0.00            8.20           8.012500
  256         1000    0.00            15.87          7.751163
  512         1000    0.00            32.69          7.981925
  1024        1000    0.00            64.35          7.855088
  2048        1000    0.00            90.94          5.550715
  4096        1000    0.00            97.30          2.969304
  8192        1000    0.00            98.13          1.497402
  16384       1000    0.00            98.15          0.748859
  32768       1000    0.00            98.14          0.374362
  65536       1000    0.00            98.14          0.187188
  131072      1000    0.00            98.14          0.093591   ← peak
  262144      1000    0.00            96.72          0.046118
  524288      1000    0.00            96.38          0.022978
  1048576     1000    0.00            96.25          0.011473
  2097152     1000    0.00            96.23          0.005736
  4194304     1000    0.00            96.10          0.002864
  8388608     1000    0.00            96.01          0.001431

(Note: server-side BW peak shows 0.00 because the receiver doesn't measure
peak in send_bw; that's a tool reporting quirk, not a real difference.)

================================================================================
ANALYSIS
================================================================================

Three operating regimes are visible in the curve:

(1) pps-bound (2 B – 1 KB):
    Message rate stays roughly constant at ~7.7 Mpps independent of size.
    Bandwidth scales linearly with message size in this regime.
    Implication: per-message overhead (BTH header, doorbell, ACK, CQE) caps
    the rate at which messages can be issued, regardless of payload.

(2) Bandwidth-bound (2 KB – 128 KB):
    Crossover to link-saturated regime occurs around 4 KB, which matches the
    RoCE path MTU. Once a single message spans multiple frames, header
    overhead becomes a small fraction of work.
    Peak observed: 98.20 Gb/s @ 128 KB messages (98.2% of 100 Gb/s).

(3) Slight regression (256 KB – 8 MB):
    Bandwidth drops to ~96.1 Gb/s for very large messages. The link itself
    is not the bottleneck here (it carried 98.2 Gb/s earlier). The most
    likely cause is the CPU/cache hierarchy: 256 KB exceeds the per-core L2
    cache on Haswell-EP, so the data path becomes DRAM → PCIe → NIC instead
    of cache → PCIe → NIC. Memory bandwidth on a single-socket E5-1620 v3
    is the constraining resource here.

Headline numbers to cite:
  - Sustained 64 KB throughput     : 97.76 Gb/s
  - Peak throughput (128 KB)       : 98.20 Gb/s
  - Bandwidth-bound crossover      : ~4 KB (= path MTU)
  - Max small-message rate         : ~7.7 Mpps

================================================================================
FILES
================================================================================

Raw client output : see above
Raw server output : see above
Next test         : 02_rocev2_send_lat (latency, ib_send_lat)
