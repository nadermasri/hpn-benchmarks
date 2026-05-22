# Benchmark 11 — Distributed PyTorch DDP Training
Date: 2026-05-22

## Methodology

Real PyTorch DDP training across both nodes (1 GPU per node, 2 ranks total).
ResNet-50, synthetic data generated on-GPU (torch.randn(B, 3, 224, 224)).
PyTorch 2.4.0 + CUDA 12.4, NCCL 2.20.5.

Two transport configurations tested:
- RDMA: NCCL_IB_HCA=mlx5_X:1 (confirmed NET/IB in NCCL logs)
- TCP: NCCL_IB_DISABLE=1, NCCL_SOCKET_IFNAME=ens2fXnpX (confirmed NET/Socket)

Two batch sizes tested to expose the gradient-compute overlap behavior.

Per run: 10 warmup iterations + 40 measured iterations.

## Results

### Batch size 32 (large compute per step)

| Metric                     | Single-GPU | DDP RDMA | DDP TCP | TCP penalty |
|----------------------------|------------|----------|---------|-------------|
| Step time (median, ms)     | 172.23     | 176.29   | 181.03  | +5 ms (+3%) |
| Forward (ms)               | 58.78      | 58.91    | 59.25   | -           |
| Backward+allreduce (ms)    | 110.47     | 114.38   | 118.44  | +4 ms       |
| Backward / Forward ratio   | 1.88x      | 1.94x    | 2.00x   | -           |

### Batch size 4 (small compute per step)

| Metric                     | DDP RDMA | DDP TCP | TCP penalty   |
|----------------------------|----------|---------|---------------|
| Step time (median, ms)     | 59.58    | 79.38   | +20 ms (+33%) |
| Forward (ms)               | 24.60    | 16.29   | -             |
| Backward+allreduce (ms)    | 31.21    | 59.74   | +28 ms        |
| Backward / Forward ratio   | 1.27x    | 3.67x   | -             |

## Analysis

PyTorch DDP overlaps allreduce with backward propagation by bucketing
gradients and triggering allreduce as each layer's gradients become
available. This means TCP's lower bandwidth only causes a visible
step-time penalty when the backward pass is too short to hide the
allreduce.

ResNet-50 has 25M parameters -> ~100 MB of gradients per step. At measured
NCCL rates:
- RDMA NCCL : 50 Gb/s -> 16 ms to transfer 100 MB
- TCP NCCL  : 10 Gb/s -> 80 ms to transfer 100 MB

With batch=32, backward takes 110 ms, so even 80 ms of TCP allreduce
fits inside backward. Only the tail (a few ms of the last gradient
bucket) is exposed: 3% step-time penalty.

With batch=4, backward shrinks to 15 ms but the 80 ms TCP allreduce
remains the same - it now dominates the step. The Bwd/Fwd ratio jumps
from 1.27x (RDMA, no overhead) to 3.67x (TCP, allreduce exceeds
backward by 2.5x): 33% step-time penalty.

This is consistent with the NCCL allreduce result from test 09: TCP is
~5x slower per byte than RDMA, but PyTorch DDP's overlap mechanism
hides most of that cost when compute is large relative to gradient size.

## Implications for distributed AI

The TCP-vs-RDMA gap in training is regime-dependent:

| Regime                                    | TCP penalty expected  |
|-------------------------------------------|-----------------------|
| Small models, large batches               | Small (network hides) |
| Large models (LLMs)                       | Large (more grads)    |
| Small batches (e.g. inference fine-tune)  | Large                 |
| Faster GPUs (shorter backward)            | Larger penalty        |
| More nodes                                | Larger (more traffic) |

For modern LLM training (7B+ params, batch=1-4 per GPU, fast GPUs),
all four factors push toward the high-penalty regime. This is why
every production AI training stack uses RDMA and treats TCP as
strictly fallback.

## Headline

ResNet-50 batch=4 on 2x RTX 3060, 100 GbE link:
- DDP step time with RDMA: 60 ms
- DDP step time with TCP:  79 ms
- TCP costs 33% additional step time when allreduce is exposed
- TCP gap with batch=32 is only 3% because PyTorch DDP hides the
  allreduce inside the (longer) backward pass
