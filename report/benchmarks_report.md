# High-Performance Networking for Distributed AI
## Benchmarking RoCEv2 RDMA and Kernel TCP on a 100 Gb/s Link

**Author:** Nader Almasri
**Date:** 18 May 2026
**Institution:** Télécom Paris — Research Internship

---

## Abstract

This documents research benchmarking study conducted during an internship at Télécom Paris. The study systematically compares two high-performance network transports — RoCEv2 RDMA and kernel TCP — on a back-to-back 100 Gb/s link, evaluating throughput, latency, CPU cost, and collective communication performance via NCCL.

It is structured in four parts:

- **Part 1 — Foundations.** What TCP does in the kernel, what RDMA does instead, and the motivation for each design choice.
- **Part 2 — Methodology.** What was measured, with what tools, and why those tools were chosen.
- **Part 3 — Results.** Every benchmark, with the measured numbers and their technical interpretation.
- **Part 4 — Synthesis.** Summary tables, implications for distributed AI workloads, study limitations, and proposed next steps.

---

# Part 1 — Foundations

## 1.1 The problem we are studying

Modern distributed AI workloads — training a large language model across many GPUs, serving inference at scale, doing distributed gradient updates — are bottlenecked by **data movement** more than by computation. A single A100 GPU can do ~300 teraflops of fp16 compute. A 100 Gb/s NIC, on the other hand, moves at most 12.5 GB/s. The arithmetic intensity (compute per byte) of training a model is typically below 100 ops/byte, so the network often dictates how long a training step takes, especially during the all-reduce step where every GPU has to exchange its gradient with every other GPU.

This means **how bytes are moved between machines matters as much as how fast those machines compute**. The same hardware can deliver wildly different throughput depending on the transport used. Our experiments quantify exactly that.

We compare three transports on the same physical link:

| Transport | What it is | Where the CPU is involved |
|---|---|---|
| **Kernel TCP** | Standard Linux TCP/IP stack | Heavily — every byte passes through the kernel |
| **TCP with `MSG_ZEROCOPY`** | Same TCP, but the kernel skips one copy | Slightly less than kernel TCP |
| **RoCEv2 RDMA** | RDMA over Converged Ethernet v2 | Almost not at all on the data path |

We also test NCCL (NVIDIA's collective communication library, which is what PyTorch DDP uses under the hood) running on top of each transport, to measure what real distributed AI sees.

## 1.2 The hardware

Two identical Dell Precision T5810 workstations, connected back-to-back via one 0.5 m QSFP28 DAC cable (no switch).

![Hardware topology](diagrams/01_topology.png)

Several properties of this hardware directly explain the benchmark results:

- **The RTX 3060 is a consumer card.** It does *not* support GPUDirect RDMA. This means whenever a GPU is involved in a network transfer, the data has to take a detour through host RAM. This will cost us ~50% bandwidth in the NCCL allreduce tests, and we'll quantify exactly how much.
- **The cable is half a meter.** Round-trip latency over the physical wire is about 5 nanoseconds. Anything we measure above that is overhead from the protocol, the host, or the NIC itself. This is why we can measure sub-microsecond latency cleanly.
- **No switch.** Switches add nanoseconds to microseconds of latency and complicate congestion behavior. With a back-to-back link, the protocol is the only variable.
- **Same hardware on both ends.** Everything we compare is apples-to-apples: same NIC, same kernel, same GPU.

## 1.3 What happens when a program calls `send()`

To understand why TCP costs so much CPU, it helps to trace what a program is *actually* doing when it calls `send()`. TCP is often taught at the level of "it's reliable and ordered", but the kernel does a *lot* more than that. The actual data path has seven distinct stages.

![TCP send path — 7 stages, kernel does the protocol work](diagrams/02_tcp_send_path.png)

*Figure 1.3a — The seven stages of a TCP send. Every byte goes through the kernel, gets copied from user space (stage 3), and incurs protocol processing per packet.*

There are **seven distinct stages**, plus a context switch. At 100 Gb/s with average packet sizes of a few KB, this happens millions of times per second. Each stage has its own cost. The most expensive ones are:

- **Step 3, the memory copy from user to kernel.** Your application owns the buffer (so the kernel can't trust it — the application could change it mid-flight). The kernel must take its own copy into an `sk_buff` so that retransmits, queueing, and reliability machinery can work safely. This copy is pure CPU work: the CPU reads bytes from one location in RAM and writes them to another.

- **Step 3 also, the TCP header construction.** For every MTU-sized chunk, the kernel writes 20 bytes of TCP header, calculates a checksum (offloaded to NIC on modern hardware), tracks sequence numbers, etc.

- **Step 6 + step 7's interrupt back on completion.** When the NIC finishes transmitting, it raises an interrupt that wakes the kernel to free the buffer.

This appears in `mpstat` output as `%sys` (system / kernel CPU). In the TCP 8-stream test (Section 3.3), the sender showed `%sys ≈ 57%` and the receiver `%sys ≈ 63%`. That is millions of executions of stages 3–7 per second.

### Receive path — same but mirrored, plus interrupts

When the packet arrives at the destination NIC:

```
1. NIC receives bits from the wire
2. NIC DMA-writes the packet into a kernel ring buffer
3. NIC raises an interrupt (or the kernel polls via NAPI)
4. Kernel softirq processes the packet:
     - parse IP header, look up the route
     - parse TCP header, find the socket
     - check sequence number, possibly reorder
     - move payload to the socket receive queue
5. Your process calls recv() → kernel does copy_to_user (copy #2)
```

The interrupt processing happens in **softirq context**, which is what mpstat reports as `%soft`. In the 8-stream TCP receiver test, `%soft = 33%`. That is the kernel handling 2.3 million packets per second of NIC RX interrupts (batched via NAPI to amortize the cost).

### Key insight #1

Every TCP byte is touched by the CPU at least twice (once on send: user→kernel; once on receive: kernel→user). Plus the kernel does protocol work for every packet. At 100 Gb/s this becomes the bottleneck — not the wire.

## 1.4 Why TCP needs all this machinery

You might ask: "Why does TCP have to be this expensive? Can't it just send bytes?" The answer is that TCP provides a contract that is itself expensive to honor. Specifically, TCP guarantees:

1. **Reliability.** If a packet is lost in the network, TCP retransmits it. To do this, the kernel must keep a copy of every byte it has sent until that byte is acknowledged.
2. **In-order delivery.** Packets can be reordered by routers. TCP must buffer out-of-order packets at the receiver and deliver them in order to the application.
3. **Flow control.** The receiver tells the sender how much it can take. If the sender is too fast, it must slow down. The kernel tracks the receiver's window.
4. **Congestion control.** TCP probes the network for available bandwidth and backs off when it sees loss. This is the famous Reno / Cubic / BBR algorithm family. The kernel runs a congestion controller for every connection.
5. **Stream abstraction.** Your application sends arbitrary bytes; TCP segments them, sends them, and reassembles them on the other side as a continuous stream. This abstraction itself costs bookkeeping.

All five guarantees require **state per connection** that the kernel must maintain. With 8 connections, multiply that by 8.

### Why parallelism (multiple TCP streams) helps

This is why test 05 (8 streams) reached 93 Gb/s while test 04 (1 stream) only reached 34 Gb/s. The wire is the same in both cases. The difference is that **one CPU core can only run so much TCP machinery per second**. With 1 stream, the bottleneck is one core doing all the protocol work. With 8 streams, the kernel can spread the protocol work across multiple cores (via Receive Side Scaling and per-CPU scheduling), and total throughput scales.

But it scales at a cost: more CPU. Your 8-stream test used ~5.8 cores on the sender and ~7.8 cores on the receiver. The CPU cost per Gb of data went up — there's overhead from coordinating across cores. We will see this in test 08.

### Key insight #2

TCP throughput scales with parallelism, but CPU cost scales faster. Going from 1 to 8 streams yields 2.7× more bandwidth but ~6× more CPU.

## 1.5 The kernel-bypass idea: RDMA

RDMA (Remote Direct Memory Access) was designed in the early 2000s to escape exactly the bottleneck we just described. The premise is radical: **what if the application could write directly into the remote machine's memory, with no kernel involvement on either side?**

This requires:

- A NIC smart enough to do protocol processing itself (sequence numbers, retransmits, ordering) — i.e. the NIC implements the transport in hardware, not the OS.
- A way for an application to tell the NIC "send this buffer to that remote address" without the kernel mediating each request.
- A mechanism to pin memory and register it with the NIC so the NIC can DMA into and out of it directly.
- A way for the local NIC and the remote NIC to coordinate (queue pairs, completion queues).

This is what InfiniBand introduced in the late 1990s, and it has since been ported to Ethernet as RoCE (RDMA over Converged Ethernet). The latest version is RoCEv2, which is what the ConnectX-5 cards in this study use.

### What RDMA looks like to an application

The API is called *verbs* (libibverbs). Instead of `socket() / send() / recv()`, the RDMA application:

1. **Register memory.** You tell the NIC: "this region of my address space (say, a 64 MB buffer) is mine, here it is, please pin it and give me a key for it." The kernel pins the pages (so they can't be swapped out) and the NIC records the physical addresses. You get back a memory region (MR) handle.
2. **Create a queue pair (QP).** A QP is the application's endpoint: it has a send queue and a receive queue. This QP is connected to a QP on the remote machine.
3. **Post work requests.** Instead of `send(fd, buf, len)`, the application calls `ibv_post_send(qp, work_request)`. The work request points at the registered memory region and tells the NIC what to do.
4. **The NIC executes the work.** It DMA-reads from the application buffer directly from user memory (no copy), constructs the packet, transmits it. On the other side, the remote NIC DMA-writes directly into the registered memory of the receiving process.
5. **The NIC posts a completion.** It writes a Completion Queue Entry (CQE) into the Completion Queue (CQ). The application polls the CQ to know when the operation is complete.

![RDMA send path — kernel bypass, NIC does all the work](diagrams/03_rdma_send_path.png)

*Figure 1.5 — The RDMA send path: the application writes directly to a memory-mapped doorbell, the NIC DMA-reads the buffer from user RAM, builds the packet, and transmits. The kernel is completely absent from the data path.*

**No kernel anywhere on the data path.** The kernel was involved exactly once: at setup time, to register the memory and create the queue pair. After that, the application talks to the NIC directly through a memory-mapped doorbell. The NIC talks to the network directly. The OS does not see a single byte of the data flow.

### What kernel bypass looks like in CPU measurements

Running the RDMA throughput benchmark with `mpstat` sampling in parallel produces:
- `%usr ≈ 12.5%` (one core busy in user space — that's the application polling its CQ for completions)
- `%sys ≈ 0%` (kernel does nothing on the data path)
- `%soft ≈ 0%` (no NIC interrupts — the application polls instead)

The 12.5% is the application choosing to busy-poll its completion queue rather than sleep. If it instead used `ibv_req_notify_cq` and slept on an eventfd, it would consume essentially zero CPU. We didn't test that, but it's a documented tradeoff: lower latency from polling vs. lower CPU from event-driven completion.

![Side-by-side comparison of TCP and RDMA data paths](diagrams/04_compare_paths.png)

*Figure 1.5b — The same operation, two transports. TCP traverses the kernel twice (send and receive) and pays for memory copies, syscalls, and softirq processing. RDMA skips the kernel entirely on the data path.*

### Key insight #3

In RDMA, the only observable CPU cost is the application's polling overhead. The kernel does literally zero work on the data path. This is structurally different from TCP, where kernel work is mandatory and unavoidable.

## 1.6 RoCEv2: putting RDMA on Ethernet

The original RDMA transport was InfiniBand, a separate wire protocol designed for HPC clusters. To use InfiniBand InfiniBand requires dedicated switches and InfiniBand NICs and InfiniBand cabling, which is expensive and incompatible with everything else.

RoCE (RDMA over Converged Ethernet) was created to run RDMA on standard Ethernet hardware. There are two versions:

- **RoCEv1** encapsulates InfiniBand directly in Ethernet frames. It is not routable (can't cross IP subnets). Essentially deprecated.
- **RoCEv2** encapsulates InfiniBand in UDP/IP, making it routable. This is what we use.

A RoCEv2 packet on the wire looks like this:

![RoCEv2 packet structure](diagrams/05_rocev2_packet.png)

*Figure 1.6 — The RoCEv2 wire format: InfiniBand transport tunneled inside UDP/IP/Ethernet. The destination UDP port 4791 identifies the packet as RoCEv2.*

The destination UDP port `4791` tells receiving NICs "this is RoCEv2, hand it to the InfiniBand stack". The IB Base Transport Header carries the queue pair number, packet sequence number, opcode, etc.

For our test:
- Both NICs are in Ethernet mode (the ConnectX-5 ports can switch between IB and Eth modes; we use Eth).
- The 100G subnet uses 192.168.100.0/24.
- The MTU is 9000 bytes ("jumbo frames"), which is important because each RoCEv2 packet has ~50 bytes of headers; larger MTU means fewer packets for the same data.

### Reliable Connected (RC) transport — the mode we use

The IBTH header includes a "transport service type". The one we use is **Reliable Connected** (RC), the strongest guarantee: it provides reliability, in-order delivery, and is between a fixed pair of endpoints (one queue pair on each side). This is the closest thing in RDMA to TCP semantics, and it is what `ib_send_bw` uses by default.

RC guarantees:
- Every packet sent will eventually be delivered, or an error is returned.
- Packets arrive in the order they were sent.
- Flow control prevents the receiver from being overwhelmed.

All of this is done by the NIC hardware itself. The NIC re-transmits lost packets without the CPU's involvement. The NIC re-orders packets in its receive pipeline. The CPU only sees: "send this", "completion arrived".

### Key insight #4

RoCEv2 RC provides TCP-equivalent guarantees (reliable, in-order) but moves the entire protocol implementation into NIC hardware. The CPU becomes irrelevant on the data path.

## 1.7 GPUDirect RDMA — the missing piece on our hardware

When the data lives in GPU memory (which is the case for distributed AI), there is an additional twist. The GPU has its own memory (12 GB on our RTX 3060s, 80 GB on an A100). For an RDMA transfer to move that GPU memory to another machine, the NIC needs to be able to DMA out of GPU memory directly. This feature is called **GPUDirect RDMA** (GDR).

With GDR, the data path is:
```
GPU memory (node 1) → NIC (node 1) → wire → NIC (node 2) → GPU memory (node 2)
```

Without GDR, the data has to bounce through host RAM:
```
GPU memory (node 1) → [PCIe copy] → host RAM (node 1) → NIC (node 1) → wire 
→ NIC (node 2) → host RAM (node 2) → [PCIe copy] → GPU memory (node 2)
```

GDR requires:
- NVIDIA's `nvidia_peermem` (or older `nv_peer_mem`) kernel module — installed automatically with the driver if the GPU supports it.
- A GPU SKU that actually supports peer-to-peer DMA. **The RTX 3060 does not.** Only Quadro/professional and Tesla/datacenter SKUs do, plus a few RTX A-series and RTX 6000 Ada cards.

This is why our NCCL log shows `GDR 0`:

```
NCCL INFO Connected all rings, use ring PXN 0 GDR 0
```

GDR is off because the hardware can't enable it. We will see in test 09a that this caps our NCCL allreduce at 50 Gb/s — half of the line rate that pure host-to-host RDMA achieved. The 50 Gb/s ceiling is the PCIe bounce.

![GPUDirect RDMA vs. host-bounce data paths](diagrams/06_gdr_paths.png)

*Figure 1.7 — With GPUDirect RDMA (top), the NIC DMA-transfers data directly from GPU memory. Without GDR (bottom, our setup), the data must bounce through host RAM twice, capping NCCL bandwidth at roughly half of line rate.*

### Key insight #5

GPUDirect RDMA is the feature that makes consumer GPUs unsuitable for high-performance distributed training. Without it, even with a 100 Gb/s NIC and full RDMA support, the achievable GPU-to-GPU bandwidth is capped at approximately 50 Gb/s.

---

# Part 2 — Methodology

## 2.1 What we want to measure

To compare two transports rigorously, four quantities must be measured:

1. **Maximum throughput**, in steady state, on a large transfer.
2. **Minimum one-way latency**, for the smallest possible message.
3. **CPU cost per gigabit**, since this is the real differentiator.
4. **What happens to an actual workload**, not just micro-benchmarks. For us: NCCL allreduce, which is what PyTorch DDP uses.

Message size is swept in each test to expose the latency-bound and bandwidth-bound regimes.

## 2.2 Tools we used and what they do

| Tool | What it does |
|---|---|
| `ib_send_bw` | RDMA throughput. Sends back-to-back messages on a single queue pair; reports MB/s and Mpps. |
| `ib_send_lat` | RDMA latency. Sends one message, waits for reply, divides by 2. Reports percentiles. |
| `iperf3` | TCP throughput. Standard tool, can use one or many parallel streams. |
| `iperf3 --zerocopy` | TCP throughput with `sendfile()`-style zero-copy on the send side (the kernel does not need to copy from the user buffer because it reads from a memory-mapped file). |
| `sockperf` | TCP latency. Sends a request, waits for reply, divides by 2. Reports full percentile distribution. |
| `mpstat 1 35` | Sample per-CPU usage once per second for 35 seconds. We start it just before each test to measure CPU cost. |
| `nccl-tests/all_reduce_perf` | NCCL's official benchmark for the allreduce collective. Runs the same algorithm PyTorch DDP uses. |
| `mpirun` | OpenMPI launcher used to start the same nccl-tests binary on both nodes. |

## 2.3 How we set up the environment for clean measurements

A few things had to be in place before any benchmark could give trustworthy numbers:

- **CPU governor set to "performance"** on all cores. Without this, Linux can clock the CPU down when it sees low load, which adds noise to latency tests. We set this on both nodes via `echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`.
- **MTU 9000 (jumbo frames)** on both 100G interfaces. Default MTU is 1500 bytes; at 100 Gb/s that means ~8 million packets per second, which is a lot of per-packet overhead. With 9000-byte MTU, ~1.4 million packets per second.
- **Same kernel and driver versions** on both nodes (Ubuntu 24.04, kernel 6.8.0-111-generic, NVIDIA 580.126.20, DOCA-OFED 26.01).
- **No other workloads running.** We checked this with `ps aux` before each test.

## 2.4 Caveats — what these benchmarks do *not* show

The following limitations apply to this study. The benchmarks measure:

- **Performance on a single back-to-back link with no switch.** Real clusters have switches and multiple paths, which add latency and complicate congestion. Our numbers are best-case for the protocol; real-world numbers will be slightly lower.
- **One pair of endpoints, point-to-point.** We did not test what happens with 4, 8, or 64 nodes all communicating simultaneously, which is where TCP's congestion behavior and RDMA's lossless requirement actually become interesting.
- **Synthetic traffic.** `ib_send_bw` and `iperf3` send the same data over and over. Real applications have varying message sizes, bursts, and idle periods.
- **Consumer GPU.** Without GPUDirect RDMA, our NCCL numbers are not representative of production training clusters.

These are honest limitations of the current study. They also suggest natural follow-on experiments: "what happens at scale?", "what happens with realistic traffic?", "what would the numbers look like with an A100?"

---

# Part 3 — Results

I will walk through each benchmark in order: what we ran, what we measured, and what it means.

## 3.1 Test 01 — RoCEv2 RDMA throughput

### What we ran
On node 2 (server): `ib_send_bw -d mlx5_0 -i 1 -F -R --report_gbits -D 30`
On node 1 (client): `ib_send_bw -d mlx5_1 -i 1 -F -R --report_gbits -D 30 192.168.100.2`

Flag glossary:
- `-d mlx5_0` / `-d mlx5_1`: select the RDMA device on each node.
- `-i 1`: port 1 of the device (each ConnectX-5 has two ports).
- `-F`: don't fail if the CPU frequency isn't exactly fixed — we already set the governor.
- `-R`: use the RDMA Connection Manager (RDMA-CM) for setup. This makes the test go over the IP address, which is convenient and matches what real applications do.
- `--report_gbits`: report throughput in Gb/s instead of MB/s.
- `-D 30`: run for 30 seconds at the default message size of 64 KB.

### What it does

`ib_send_bw` opens one RC queue pair between the two nodes and posts a steady stream of `SEND` work requests of size 64 KB. The NIC executes them as fast as it can, and the tool reports the steady-state throughput.

### Results

| Side | Throughput | Messages |
|---|---|---|
| Client (sender) | **97.76 Gb/s** | 4.46 M @ 64 KB |
| Server (receiver) | 97.51 Gb/s | (same flow) |

98% of the 100 Gb/s line rate, with a single connection, on default settings.

### What it means

This is essentially what the wire can deliver. The ~2% gap to 100 Gb/s comes from RoCEv2 protocol overhead: each 9000-byte packet carries ~50 bytes of headers (Ethernet + IP + UDP + IB BTH), which is about 0.56% overhead. The rest is interframe gap, ACK packets going the other way, and small idle gaps in the NIC pipeline.

The key takeaway is that **the hardware is healthy and the link is clean**. Everything we measure later is relative to this 98 Gb/s baseline.

---

## 3.2 Tests 02 and 03 — RoCEv2 latency

### What we ran

`ib_send_lat -d mlx5_0 -i 1 -F -R` on server, `ib_send_lat -d mlx5_1 -i 1 -F -R 192.168.100.2` on client. With `-a` we got a full size sweep.

### What it does

Sends one 2-byte message from client to server, server replies with a 2-byte message. Tool divides total time by 2 and reports the one-way latency. Repeats thousands of times to get percentiles.

### Results

| Message size | One-way latency (mean) | p99 | p99.9 |
|---|---|---|---|
| 2 B | **0.83 µs** | 1.01 µs | ~2 µs |
| 64 B | 0.83 µs | 1.01 µs | — |
| 128 B | 0.85 µs | — | — |
| 256 B | 1.05 µs | — | — |
| 1 KB | 1.21 µs | — | — |
| 4 KB | 1.81 µs | — | — |
| 64 KB | 7.12 µs | — | — |

### What it means

**Sub-microsecond latency for small messages.** This is what hardware-driven transports give you. The 0.83 µs floor decomposes roughly as:
- ~0.05 µs cable + serializer/deserializer (5 ns / m for the cable, plus NIC PHY)
- ~0.4 µs NIC DMA in + packet construction
- ~0.4 µs receive-side DMA out + completion posting

Note also the discontinuity around 256 B. The ConnectX-5 supports up to **236 bytes of "inline data"**: data that travels inside the work request descriptor itself, avoiding a separate DMA read for the payload. Below 236 bytes the latency stays flat at ~0.83 µs; above it, an extra DMA-read step adds ~200 ns and latency climbs to ~1.05 µs.

For comparison: a normal interrupt-driven kernel TCP receive needs about 5-10 µs just for the interrupt handler. So **RDMA is below the floor of what a kernel TCP implementation can deliver**, no matter how well-tuned.


---

## 3.3 Tests 04, 05, 06 — TCP throughput

### What we ran

| Test | Command |
|---|---|
| 04 | `iperf3 -c 192.168.100.2 -t 30` (1 stream) |
| 05 | `iperf3 -c 192.168.100.2 -t 30 -P 8` (8 parallel streams) |
| 06 | `iperf3 -c 192.168.100.2 -t 30 -P 8 --zerocopy` (8 streams + MSG_ZEROCOPY) |

### Results

| Test | Throughput | Retransmits |
|---|---|---|
| 04 (1 stream) | **34.30 Gb/s** | 0 |
| 05 (8 streams) | **93.30 Gb/s** | 128 |
| 06 (8 streams + zerocopy) | **92.10 Gb/s** | 22 |

### What it means

**Test 04 — single TCP stream tops out at 34 Gb/s.** This is a single-core limit, not a network limit. The wire can do 100 Gb/s, but one CPU core cannot run the TCP send loop fast enough to keep up. Specifically, the kernel TCP send path (steps 3-6 in the diagram in Section 1.3) runs serially on whatever core the application is bound to. At 34 Gb/s with 9000-byte segments, that's ~470,000 packets per second per core. The core is saturated doing TCP work.

**Test 05 — 8 streams gets to 93 Gb/s.** With 8 connections, the kernel can spread the per-connection TCP work across 8 cores using Receive Side Scaling (RSS) on the receive side and per-CPU send queues on the send side. The aggregate matches the wire. The 7% gap to 100 Gb/s is a combination of TCP/IP header overhead (~3-4%) and small inefficiencies from going through the kernel.

**Test 06 — `MSG_ZEROCOPY` is barely faster.** The `--zerocopy` flag tells the kernel "you can read directly from my user buffer; don't copy". This eliminates copy #1 from the send path (user → kernel). In theory this should save CPU and improve throughput. In practice, the throughput is *not* improved (it actually drops by 1%, which is within measurement noise) because the bottleneck wasn't memory copy — it was the protocol processing. But notice the retransmit count drops 6× (from 128 to 22). That's a real effect: with less CPU pressure, the sender keeps up with ACK processing better and avoids spurious retransmissions.


---

## 3.4 Test 07 — TCP latency

### What we ran

`sockperf ping-pong --tcp -i 192.168.100.2 -p 11111 -m 14 -t 10 --full-rtt` from client, after starting `sockperf server` on the other side.

`-m 14` is the payload size in bytes. `-t 10` runs for 10 seconds. `--full-rtt` reports round-trip time so we divide by 2 ourselves.

### Results

| Statistic | One-way (µs) |
|---|---|
| Mean | **12.28** |
| p50 (median) | 12.06 |
| p99 | 16.15 |
| p99.9 | 23.61 |
| Max | **79.16** |

### What it means

**12 µs vs RDMA's 0.83 µs — that's a 15× gap.** The breakdown of TCP's 12 µs is approximately:
- ~1 µs cable + NIC
- ~2-3 µs kernel send path on the sender (steps 1-6)
- ~2-3 µs NIC RX, interrupt, softirq on the receiver
- ~2-3 µs kernel TCP processing, copy to user, wakeup of waiting process
- ~3-4 µs the same in the reverse direction

Almost all of this is the kernel doing its protocol work. The wire itself contributes less than 10% of the latency. **Removing the kernel from the path would bring latency into RDMA territory.**

The tail latency (max 79 µs, p99.9 23.61 µs) reveals another important property: the kernel scheduler is non-deterministic. When the receiving process gets preempted, or when a softirq runs on a contended CPU, individual messages can take much longer. RDMA's max is closer to 2 µs because there is no scheduler involvement.

![Latency comparison RDMA vs TCP](diagrams/10_latency.png)

*Figure 3.4 — One-way latency comparison. RDMA's 0.83 µs mean is 15× lower than TCP's 12.28 µs, and RDMA's worst-case max (~2 µs) is 37× better than TCP's max (79 µs).*


---

## 3.5 Test 08 — CPU cost: the most important comparison

### What we did

For each of the three throughput tests (RDMA, TCP 1-stream, TCP 8-stream) we ran `mpstat 1 35` in parallel with the throughput tool, capturing CPU usage every second for 35 seconds across all 8 logical CPUs.

`mpstat` reports the percentage of CPU time in five categories per second:
- `%usr` — running user-space code (your program's instructions)
- `%sys` — running kernel code (system calls, kernel data structures)
- `%irq` — handling hardware interrupts
- `%soft` — handling soft interrupts (kernel deferred work, networking)
- `%idle` — doing nothing

`100% × 8 cores = 800%` total. So `12.5%` means 1 of 8 cores fully busy; `100%` means all 8 cores fully busy.

### Results (sender side; receiver side is similar but higher for TCP)

| Test | Throughput | `%usr` | `%sys` | `%soft` | Total CPU |
|---|---|---|---|---|---|
| **08a — RDMA** | 98.27 Gb/s | 12.5 | 0.0 | 0.0 | **12.5%** (= 1 core) |
| **08b — TCP 1-stream** | 34.30 Gb/s | 0.25 | 11.1 | 1.3 | **11.8%** (= ~1 core) |
| **08c — TCP 8-stream** | 93.60 Gb/s | 1.0 | 57.0 | 15.6 | **73%** (= ~5.8 cores) |

### What it means

Let me reframe this with a single metric: **cores per Gb/s of throughput.**

| Test | Throughput | Cores used | Cores per Gb/s | Gb/s per core |
|---|---|---|---|---|
| RDMA | 98.3 Gb/s | 1.0 | **0.0102** | 98.3 |
| TCP 1-stream | 34.3 Gb/s | 0.95 | 0.0277 | 36.1 |
| TCP 8-stream | 93.6 Gb/s | 5.84 | **0.0624** | 16.0 |

**RDMA is 6× more CPU-efficient per Gb/s than 8-stream TCP**, and the way that CPU is spent is fundamentally different. Look at the breakdown:

- **RDMA**: all CPU time (12.5%) is in `%usr`. That is the application polling the completion queue. The kernel does *literally nothing*. If we configured the application to use event-driven completions instead of polling, this would drop close to 0% with a small latency cost.

- **TCP 1-stream**: most CPU time is in `%sys` (kernel) plus a small amount in `%soft` (softirq). The application itself uses almost no CPU — it just sits in `send()` while the kernel does everything.

- **TCP 8-stream**: same pattern but ~6× more total CPU. Look especially at the receiver side, which is even worse: in the test, the TCP 8-stream receiver hit `%sys ≈ 63%`, `%soft ≈ 33%`, for a total of ~96% — *7.8 of 8 cores busy*, mostly in kernel softirq. At 100 Gb/s the receiver becomes a kernel-bound machine.

### Why softirq becomes dominant at high speed

When the NIC receives a packet, it raises a hardware interrupt. The interrupt handler is tiny — it just schedules a softirq. The softirq is where the actual TCP processing happens (parse header, find socket, demux, deliver). At a few hundred Mb/s, this is cheap. At 100 Gb/s with 1.4 million packets/sec, a single core cannot keep up, so the kernel spreads softirq processing across multiple cores using RSS (Receive Side Scaling) — the NIC hashes the 5-tuple of each packet and steers it to a specific receive queue, each of which gets its own softirq context on its own core.

This is what `%soft = 33%` means on the receiver: approximately 2.6 cores are constantly running softirq code to process incoming TCP segments. **These cores are not available to the application.** If you're trying to do CPU-bound work (Python interpreter, data loader, image preprocessing) on the same machine, you're losing 2-3 cores to networking.

![CPU cost per Gb/s and where the CPU time goes](diagrams/08_cpu_cost.png)

*Figure 3.5 — Left: cores spent per Gb/s of throughput. RDMA is ~8× more efficient than TCP-8. Right: stacked composition — RDMA cost is in user-space (green, can be eliminated with event-mode), TCP cost is in kernel (orange/red, structurally unavoidable).*

### Headline metric

The most concise comparison is:

```
Same hardware, same wire, same kernel. Different transport:

RDMA:     98 Gb/s on  1 core, 0 kernel cycles.
TCP-8:    94 Gb/s on  6 cores, ~6 cores of kernel cycles.

Per gigabit:
RDMA:     0.01 cores/Gb/s, all user-space, can be reduced to ~0.
TCP-8:    0.06 cores/Gb/s, all kernel-space, structurally unavoidable.
```


---

## 3.6 Test 09a — NCCL allreduce over RDMA

### What we ran

```
mpirun -np 2 -H pc1n:1,pc2n:1 \
  --mca btl_tcp_if_include 192.168.100.0/24 \
  --mca oob_tcp_if_include 192.168.100.0/24 \
  -x NCCL_DEBUG=INFO \
  -x NCCL_IB_HCA=mlx5_1:1,mlx5_0:1 \
  -x NCCL_SOCKET_IFNAME=ens2f1np1,ens2f0np0 \
  -x LD_LIBRARY_PATH \
  bash -c 'cd ~/nccl-tests/build && exec ./all_reduce_perf -b 8 -e 256M -f 2 -g 1'
```

### What it does

`all_reduce_perf` runs the all-reduce collective: every rank starts with a buffer of data, and at the end every rank has the element-wise sum of all initial buffers. This is exactly what gradient synchronization in PyTorch DDP does. The benchmark runs this for message sizes from 8 bytes up to 256 MB, doubling each step.

NCCL transparently picks the best transport. We told it via `NCCL_IB_HCA` to use our ConnectX-5 RDMA HCAs (`mlx5_1` on node 1, `mlx5_0` on node 2). The log confirmed `NET/IB : Using mlx5_X:1/RoCE` and `Connected all rings, use ring PXN 0 GDR 0` — RDMA on, GPUDirect off (because RTX 3060 doesn't support GDR).

### Results

| Size | Time | algBW | busBW |
|---|---|---|---|
| 8 B | 20.9 µs | 0.00 GB/s | 0.00 GB/s |
| 4 KB | 21.9 µs | 0.19 GB/s | 0.19 GB/s |
| 256 KB | 120 µs | 2.19 GB/s | 2.19 GB/s |
| 1 MB | 195 µs | 5.38 GB/s | 5.38 GB/s |
| 64 MB | 10.8 ms | 6.21 GB/s | 6.21 GB/s |
| 256 MB | 42.4 ms | **6.33 GB/s** | **6.33 GB/s** |

**Peak: 6.33 GB/s ≈ 50.6 Gb/s.** The peak is exactly half of what we saw on raw host-to-host RDMA in test 01 (98 Gb/s).

### What it means

Three regimes are visible:

**Latency-bound (size < 8 KB):** Time is flat at ~21 µs regardless of size. The cost is dominated by the per-operation setup, not by moving bytes. The 21 µs is the NCCL framework overhead: launching CUDA kernels for the reduction, copying data from GPU to host, doing the RDMA round-trip, copying back, signaling completion. **Compare to raw RDMA latency of 0.83 µs — NCCL adds 20 µs of per-operation overhead** just to coordinate GPU and CPU.

**Transition (8 KB to 1 MB):** The bandwidth grows roughly linearly with size because the per-op overhead amortizes.

**Bandwidth-bound (> 1 MB):** Plateau at 6.33 GB/s.

**Why only 50 Gb/s when raw RDMA hits 98 Gb/s?**

The bottleneck is not the network. It is the GPU↔host PCIe path, traversed twice per all-reduce step (once on each node) because GDR is off:

```
Node 1: GPU → [PCIe DMA] → host RAM → [RDMA] → wire
Node 2: wire → [RDMA] → host RAM → [PCIe DMA] → GPU
```

The RTX 3060 sits on PCIe Gen3 ×16, which has:
- Theoretical limit: 128 Gb/s (16 lanes × 8 GT/s)
- Practical DMA: ~75-100 Gb/s due to encoding overhead and PCIe protocol overhead
- With NCCL's chunked staging and synchronization, effective: ~50-60 Gb/s

So we're hitting the PCIe ceiling, not the network ceiling. **A server-class GPU with GDR (A100, H100, RTX A6000) would let the NIC DMA directly out of GPU memory, skipping the host bounce entirely, and NCCL would reach ~95 Gb/s.** This is exactly what cloud providers offer: AWS p4d, Azure ND_v4, GCP a2.


---

## 3.7 Test 09b — NCCL allreduce over TCP

### What we ran

Same as 09a, but with one extra environment variable:
```
-x NCCL_IB_DISABLE=1
```

This forces NCCL to fall back to its socket (TCP) transport. The log confirms:
```
NCCL_IB_DISABLE set by environment to 1
Failed to initialize NET plugin IB
NET/Socket : Using ens2fXnpX:192.168.100.X<0>
Using network Socket
Channel 00/0 : 0[0] -> 1[0] [receive] via NET/Socket/0
```

### Results

| Size | Time | busBW | RDMA equivalent (09a) | RDMA/TCP |
|---|---|---|---|---|
| 8 B | 112 µs | 0.00 GB/s | 0.00 GB/s | — |
| 4 KB | 92 µs | 0.04 GB/s | 0.19 GB/s | 4.3× |
| 256 KB | 816 µs | 0.32 GB/s | 2.19 GB/s | 6.8× |
| 1 MB | 1120 µs | 0.94 GB/s | 5.38 GB/s | 5.7× |
| 64 MB | 52 ms | 1.29 GB/s | 6.21 GB/s | 4.8× |
| 256 MB | 208 ms | **1.29 GB/s** (= 10.3 Gb/s) | **6.33 GB/s** (= 50.6 Gb/s) | **4.9×** |

**Peak: 1.29 GB/s ≈ 10.3 Gb/s.** That's roughly 1/5 of NCCL-RDMA, and roughly 1/10 of the raw TCP throughput we measured in test 05 (93 Gb/s).

### What it means

NCCL's socket transport is much slower than raw TCP. Why? Three reasons:

1. **Limited parallelism.** The log shows `2 p2p channels, 1 p2p channels per peer` — NCCL uses only 2 sockets for the ring. Compare to `iperf3 -P 8` which used 8 sockets to saturate the link. With 2 sockets, TCP cannot fill the pipe at 100 Gb/s.

2. **Synchronous chunked transfer.** NCCL sends 128 KB chunks (`P2P Chunksize 131072`) and waits for each to complete before sending the next. This destroys TCP's normal pipelining — at 100 Gb/s with 128 KB chunks the in-flight window is fixed at ~256 KB total, far below TCP's bandwidth-delay product.

3. **Three serialized memory copies per side.** GPU→host_staging→TCP_socket_buffer→NIC, and the mirror on the receive side. Each is a CPU-mediated copy that adds latency.

For NCCL-RDMA the equivalent design has the same chunked structure, but each chunk transfer itself is zero-copy and zero-syscall, so the per-chunk overhead is much lower.

![NCCL allreduce performance vs message size](diagrams/09_nccl_sweep.png)

*Figure 3.7 — NCCL allreduce bandwidth vs message size. RDMA reaches 50.6 Gb/s (capped by no-GDR PCIe bounce); TCP plateaus at 10.3 Gb/s. The ~5× ratio is consistent across the bandwidth-bound regime.*

### Latency comparison

| Min latency (8 B allreduce) |  |
|---|---|
| NCCL over RDMA | 20.9 µs |
| NCCL over TCP | 111.9 µs |
| **Ratio** | **5.4×** |


---

# Part 4 — Synthesis

![Throughput across all transports](diagrams/07_bandwidth_chart.png)

*Figure 4.1 — Headline throughput numbers. RDMA delivers near line-rate on one connection; TCP needs eight parallel streams to match it; NCCL with TCP fallback is dramatically lower.*

## 4.1 The complete table

Table 4.1 summarises all 11 benchmarks.

| # | Test | Measure | Result |
|---|---|---|---|
| 01 | RoCEv2 RDMA throughput | Single QP, 64 KB | **97.76 Gb/s** |
| 02 | RoCEv2 latency | 2 B message, one-way | **0.83 µs** |
| 03 | RoCEv2 latency sweep | Largest size that fits inline | 128 B (0.85 µs) |
| 04 | Kernel TCP throughput | 1 stream | **34.30 Gb/s** |
| 05 | Kernel TCP throughput | 8 streams | **93.30 Gb/s** |
| 06 | TCP `MSG_ZEROCOPY` | 8 streams + zero-copy send | 92.10 Gb/s (no gain, 6× fewer retrx) |
| 07 | TCP latency | sockperf ping-pong, one-way | **12.28 µs** (p99 16.15) |
| 08a | CPU cost — RDMA | At 98 Gb/s steady-state | 12.5% (1 core, all user-space) |
| 08b | CPU cost — TCP-1 | At 34 Gb/s steady-state | 11.8% (~1 core, mostly kernel) |
| 08c | CPU cost — TCP-8 | At 94 Gb/s steady-state | 73% (~6 cores, mostly kernel) |
| 09a | NCCL allreduce — RDMA | Peak (256 MB) | **50.6 Gb/s** (capped by PCIe, no GDR) |
| 09b | NCCL allreduce — TCP | Peak (256 MB) | **10.3 Gb/s** (5× slower than RDMA) |

## 4.2 What costs what — a single comparison table

The most useful direct comparison between the two transports:

| Quantity | RDMA RoCEv2 | Kernel TCP |
|---|---|---|
| Peak throughput (raw) | 98 Gb/s on 1 connection | 93 Gb/s on 8 connections |
| Min one-way latency | 0.83 µs | 12.28 µs (15× worse) |
| Tail latency (max) | ~2 µs | 79 µs (37× worse) |
| CPU per Gb/s of data | 0.01 cores | 0.06 cores at 8 streams (6× worse) |
| Where the CPU time goes | User-space polling (avoidable) | Kernel softirq + sys (mandatory) |
| Memory copies on data path | 0 | 2 per direction |
| Syscalls per packet | 0 | 1+ |
| NCCL allreduce peak | 50.6 Gb/s (PCIe-limited) | 10.3 Gb/s |
| NCCL allreduce latency | 20.9 µs | 111.9 µs |

## 4.3 Why this matters for distributed AI

The core argument, synthesised:

In modern distributed training, a single step takes 50-200 ms. Of that, the all-reduce (gradient synchronization) typically takes 20-50% of the time — and *fully* if the network can't keep up. The all-reduce is exactly the operation we measured in tests 09a and 09b.

Consider a 7-billion-parameter model trained at fp16. The gradient is 14 GB. PyTorch DDP buckets the gradients into ~25 MB chunks and starts the all-reduce on each bucket as soon as it's computed in the backward pass. With 8 GPUs on 2 nodes, the per-step all-reduce traffic is dominated by the inter-node 2-node ring.

```
Per-step network volume   = 14 GB × 2(n-1)/n  ≈ 21 GB  for n=2 nodes
With NCCL+RDMA at 50 Gb/s = 3.4 seconds       (if fully serial — actually overlaps)
With NCCL+TCP at 10 Gb/s  = 17 seconds        (does not overlap, just blocks)

If GPU compute time for the step is 200 ms:
  RDMA: most allreduce overlaps with compute → effective ~200 ms/step
  TCP:  allreduce dominates → ~1500+ ms/step → 7.5× slower training
```

That 7.5× slowdown is exactly what AWS, Azure, and GCP eliminate by shipping their AI training instances with RDMA-capable NICs and GDR-capable GPUs.

## 4.4 Why our consumer GPUs cap NCCL at 50 Gb/s

![Bandwidth ceilings ladder](diagrams/11_ladder.png)

*Figure 4.4 — Each bar represents one bottleneck removed. The 50 → 95 Gb/s jump is exactly the value of GPUDirect RDMA, which is gated to server-class GPUs.*


The full picture of NCCL bandwidth:

```
Raw host-to-host RDMA          : 98 Gb/s   (test 01)
NCCL allreduce + GPU + no GDR  : 50 Gb/s   (test 09a)  ← we are here
NCCL allreduce + GPU + GDR     : ~95 Gb/s  (estimated, server GPU)
NCCL allreduce + GPU + GDR + 
  multiple NICs                : 200+ Gb/s (modern AI clusters)
```

The factor we are *missing* (the gap between 50 and 95 Gb/s) is exactly GPUDirect RDMA. This is the value proposition of every datacenter GPU.

## 4.5 What's a fair criticism of this study?

Any presentation of this work should address the following validity threats:

- **"You only used 2 nodes."** True. Many of the most interesting effects in distributed networking — congestion, incast, hot-spotting — appear only with many nodes. Our results are best-case for the protocols. They are not the worst case.
- **"You used consumer GPUs."** True. We have quantified the GPUDirect RDMA gap (50 vs ~95 Gb/s), but we couldn't measure with GDR ourselves.
- **"You didn't tune TCP."** Slightly true. We could have set larger socket buffers (`net.core.rmem_max`, `tcp_rmem`), or used BBR congestion control instead of Cubic. These might add a few Gb/s. They would not close the latency gap or the CPU gap.
- **"Your latency tests are synthetic."** True. Real applications don't do ping-pong with one byte. But the latency *floor* is a real property of the transport, and it bounds the achievable performance.

These are all fair, and acknowledging them strengthens rather than weakens the work.

## 4.6 What's next

Natural follow-on experiments:

1. **Distributed PyTorch DDP training.** Run a real model (e.g. ResNet-50 on CIFAR or a small transformer) with NCCL backed by RDMA vs TCP. Measure step time, GPU utilization, total time-to-target-accuracy. This closes the loop from "microbenchmark" to "the metric users care about".

2. **CPU cost under realistic load.** Run NCCL while the node is also doing data loading and Python preprocessing. The CPU contention from TCP softirq becomes a real bottleneck here, not just a theoretical one.

3. **Test at scale.** Two nodes is not enough to see TCP's pathologies (incast, congestion collapse) or RDMA's (deadlock under heavy bidirectional traffic, PFC instability). Cloud-rented or supercomputer time would help here.

4. **GPUDirect Storage.** A separate axis: bypass host RAM not only between nodes but also between NIC and NVMe. Relevant for dataset loading at scale.

5. **SmartNIC offload.** ConnectX-6/-7 and BlueField DPUs can offload parts of NCCL itself onto the NIC. Worth investigating.

---

# Appendix A — File map of all benchmark results

These are the files on node 1 under `~/internship/results/`:

```
01_rocev2_send_bw.md           - Single-message-size RDMA throughput
02_rocev2_send_lat.md          - 2 B latency floor
03_rocev2_send_lat_sweep.md    - Latency vs message size
04_tcp_iperf3_baseline.md      - 1-stream TCP
05_tcp_iperf3_parallel8.md     - 8-stream TCP
06_tcp_zerocopy.md             - 8-stream TCP with MSG_ZEROCOPY
07_tcp_sockperf_latency.md     - TCP latency distribution
08a_cpu_cost_rdma.md           - mpstat trace during RDMA
08b_cpu_cost_tcp1.md           - mpstat trace during TCP 1-stream
08c_cpu_cost_tcp8.md           - mpstat trace during TCP 8-stream
09a_nccl_allreduce_rdma.md     - NCCL with RDMA transport
09b_nccl_allreduce_tcp.md      - NCCL with socket transport
```

Each file is the raw command, the raw output, and an analysis section.

# Appendix B — Glossary of every term used

- **BDP (bandwidth-delay product):** how many bytes are "in flight" on a link at any instant. For 100 Gb/s and 10 µs RTT: 100e9 × 10e-6 / 8 = 125 KB. TCP needs window sizes at least this big to saturate the link.
- **BTH (Base Transport Header):** the InfiniBand transport-layer header inside a RoCEv2 packet.
- **busBW (bus bandwidth):** in NCCL, the effective GPU-to-GPU throughput accounting for the algorithm. For all-reduce with n ranks: busBW = algBW × 2(n−1)/n. With n=2: busBW = algBW.
- **algBW (algorithmic bandwidth):** the raw network throughput observed by NCCL: (bytes / time).
- **cwnd (congestion window):** the kernel's estimate of how many unacknowledged bytes can be in flight without overwhelming the network.
- **DMA (Direct Memory Access):** the NIC reads from or writes to RAM without involving the CPU, using its own DMA engine.
- **DPDK (Data Plane Development Kit):** a user-space framework for high-performance packet processing that bypasses the kernel like RDMA does, but using a different programming model (polled, dedicated cores).
- **GDR (GPUDirect RDMA):** a feature that lets the NIC DMA directly into/out of GPU memory, skipping the host RAM bounce.
- **GRO (Generic Receive Offload):** the kernel coalesces multiple incoming TCP segments into one "super-packet" before processing, reducing per-packet overhead.
- **HCA (Host Channel Adapter):** the InfiniBand-world term for what we'd call a NIC; in RDMA tooling, it refers to the RDMA-capable NIC.
- **MR (Memory Region):** a piece of memory registered with the NIC for RDMA access; the kernel pins the pages, the NIC records the physical addresses.
- **MTU (Maximum Transmission Unit):** largest packet that can be sent without fragmentation. 9000 = "jumbo frames".
- **NAPI (New API):** Linux kernel mechanism that switches from interrupt-driven receive to polling under load, to amortize interrupt cost.
- **NCCL (NVIDIA Collective Communication Library):** the library that does multi-GPU collectives (allreduce, allgather, broadcast, etc.). PyTorch DDP uses NCCL under the hood.
- **PFC (Priority Flow Control):** a layer-2 mechanism that prevents packet drops on Ethernet, required for lossless RoCEv2.
- **QP (Queue Pair):** an RDMA endpoint, consisting of a send queue and a receive queue.
- **CQ (Completion Queue):** where the NIC posts a notification each time a work request completes.
- **RC (Reliable Connected):** the strongest RDMA transport type — reliable, in-order, point-to-point. The closest analog to TCP semantics.
- **RDMA-CM (RDMA Connection Manager):** a setup-time protocol that lets RDMA applications find each other by IP address (rather than InfiniBand LID).
- **RoCEv2 (RDMA over Converged Ethernet v2):** RDMA encapsulated in UDP/IP/Ethernet, routable. UDP port 4791.
- **RSS (Receive Side Scaling):** the NIC hashes incoming packets by 5-tuple and steers them to different receive queues, each processed by a different CPU core, enabling parallel softirq processing.
- **softirq:** kernel deferred work, runs in interrupt context but with interrupts enabled; this is where the network receive path lives.
- **TSO (TCP Segmentation Offload):** the NIC splits a large TCP send into MTU-sized segments, freeing the CPU from doing this.
- **Verbs:** the standard low-level RDMA API (libibverbs); contains primitives like `ibv_post_send`, `ibv_post_recv`, `ibv_poll_cq`.
- **WR (Work Request):** the descriptor posted to an RDMA queue to request an operation from the NIC.

---


