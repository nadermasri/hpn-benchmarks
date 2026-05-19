# System Tuning Notes

## Applied before every benchmark session

### CPU governor

```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

Without this, Linux may clock cores down when they appear idle (RDMA test
uses only 1 core) and introduce artificial latency spikes.

Verify:
```bash
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort -u
# → performance
```

### MTU

Both 100G interfaces set to MTU 9000 (jumbo frames) via Netplan.

At 100 Gb/s with default MTU 1500, packet rate would be ~8.3 Mpps — higher
than necessary and creates more per-packet overhead. MTU 9000 brings this
to ~1.4 Mpps.

Verify:
```bash
ip link show ens2f1np1 | grep mtu
# → mtu 9000
```

### TCP socket buffers (default — not changed)

Default kernel TCP socket buffer sizes were used throughout. No manual
tuning of `net.core.rmem_max`, `net.ipv4.tcp_rmem`, etc.

This is intentional: the benchmarks reflect what a typical system would
achieve out-of-the-box. TCP tuning could potentially add a few Gb/s to the
single-stream result, but would not materially affect the latency gap or the
CPU-cost comparison.

### Congestion control (default Cubic)

No change from default. Linux 6.8 uses Cubic by default. BBR was not tested.

### IRQ affinity

Not explicitly pinned. RSS (Receive Side Scaling) handles distribution of
receive queues across cores automatically. Explicit IRQ affinity could
marginally improve per-stream consistency but was not required for these
benchmarks.

## What was NOT tuned

- No NUMA binding (`numactl`)
- No huge pages
- No kernel bypass for TCP (e.g. DPDK, io_uring with zerocopy)
- No RDMA event-mode (polling throughout; would reduce CPU cost to ~0)

These represent natural next-step experiments.
