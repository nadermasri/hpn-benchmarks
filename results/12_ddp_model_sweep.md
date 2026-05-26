# Benchmark 12 — DDP Training Across Model Sizes
Date: 2026-05-22

## Methodology

Same DDP setup as benchmark 11 (PyTorch 2.4.0, NCCL 2.20.5, batch size 32,
synthetic data on-GPU). The model is varied to expose how the TCP penalty
depends on compute-to-communication ratio.

Three ResNet variants tested, each with both transports:
- ResNet-18  (11.7M params  → 47 MB gradients per step)
- ResNet-50  (25M params    → 100 MB gradients per step)
- ResNet-152 (60.2M params  → 241 MB gradients per step)

Per run: 10 warmup + 40 measured iterations.

## Results

| Model       | Transport | Step (ms) | Forward (ms) | Backward (ms) | Bwd/Fwd |
|-------------|-----------|-----------|--------------|---------------|---------|
| ResNet-18   | single    | 61.47     | 18.85        | 41.24         | 2.19x   |
| ResNet-18   | RDMA      | 65.24     | 18.84        | 45.03         | 2.39x   |
| ResNet-18   | TCP       | 73.12     | 19.23        | 52.29         | 2.72x   |
| ResNet-50   | single    | 172.23    | 58.78        | 110.47        | 1.88x   |
| ResNet-50   | RDMA      | 176.29    | 58.91        | 114.38        | 1.94x   |
| ResNet-50   | TCP       | 181.03    | 59.25        | 118.44        | 2.00x   |
| ResNet-152  | RDMA      | 424.75    | 138.14       | 279.40        | 2.02x   |
| ResNet-152  | TCP       | 431.98    | 138.64       | 285.62        | 2.06x   |

### TCP penalty by model

| Model       | TCP step penalty | Required gradient BW |
|-------------|------------------|----------------------|
| ResNet-18   | +12% (+7.9 ms)   | 47 MB / 41 ms = 9.2 Gb/s  |
| ResNet-50   | +3%  (+4.7 ms)   | 100 MB / 110 ms = 7.3 Gb/s |
| ResNet-152  | +1.7% (+7.2 ms)  | 241 MB / 279 ms = 6.9 Gb/s |

## Analysis — counterintuitive result

The TCP penalty does NOT grow monotonically with model size. ResNet-18,
the smallest model, suffers the largest TCP penalty (12%). ResNet-152,
the largest, has the smallest penalty (1.7%).

This is the opposite of common LLM-training intuition. The explanation
is in the compute-to-communication ratio, not the parameter count.

PyTorch DDP overlaps allreduce with backward propagation. The TCP
penalty only appears when:

    allreduce_time > backward_time

For each model, the required sustained bandwidth (to keep the network
just behind the backward pass) is:

    required_BW = gradient_bytes / backward_time

Computed values:

    ResNet-18  : 47 MB / 41 ms  = 1.15 GB/s = 9.2 Gb/s
    ResNet-50  : 100 MB / 110 ms = 0.91 GB/s = 7.3 Gb/s
    ResNet-152 : 241 MB / 279 ms = 0.86 GB/s = 6.9 Gb/s

NCCL TCP delivers ~10 Gb/s (test 09). All three models are below this
threshold, so TCP "almost" keeps up. But ResNet-18 sits closest to the
limit, so any per-message overhead or jitter pushes it over - hence
its larger relative penalty.

ResNet-152 has a much lower required bandwidth because its deep stack
of small bottleneck blocks computes much longer per byte of gradient
emitted. The backward pass takes 279 ms to produce 241 MB - TCP at
10 Gb/s only needs 193 ms to transfer that, comfortably overlapping.

## Why this matters

The naive heuristic "bigger model = more TCP penalty" is wrong.

The correct heuristic is:

    TCP penalty grows when required_bandwidth approaches or exceeds the
    available transport bandwidth.

The regimes where TCP genuinely breaks down are:

1. Small batches  (backward shrinks, allreduce constant) - shown in
   benchmark 11 (ResNet-50 batch=4 = 33% penalty)
2. Faster GPUs   (backward shrinks for the same compute work)
3. Mixed precision (compute halves, gradients stay the same)
4. Transformer architectures (more comm-heavy than ResNets)
5. More nodes    (allreduce traffic scales)
6. Wider models (parameters concentrated in few large layers)

Modern LLM training (7B+ parameters, batch=1-4 per GPU, fp16, fast GPUs,
attention-heavy) combines several of these factors. That is the regime
where the headline "5x TCP penalty" applies. CNNs at moderate batch
size with deep layer counts are not in that regime - and our data
confirms it.

## Headline

Across three ResNet sizes on 2-node DDP:
- TCP penalty: 12% (ResNet-18), 3% (ResNet-50), 1.7% (ResNet-152)
- The penalty depends on compute-to-communication ratio, not size alone
- Deep models with thin layers (ResNet-152) hide allreduce well
- Wide models with fat layers (ResNet-18) expose TCP more
- The headline "RDMA is 5x faster" only applies when allreduce time
  exceeds backward time - a regime our ResNets do not enter at batch=32
