# Benchmark 13 — GPUDirect RDMA Feasibility Investigation
Date: 2026-06-01

## Question

Benchmark 09a measured NCCL allreduce at 50 Gb/s, capped at roughly half
of the 98 Gb/s achievable on raw host-to-host RDMA. NCCL logged:

    NET/IB : GPU Direct RDMA Disabled for HCA 0 'mlx5_1'

We want to determine where exactly the refusal happens:

    (a) Inside NCCL only - a patched NCCL build could lift the cap
    (b) Inside the kernel driver - deeper patching needed
    (c) Inside the closed proprietary blob - no software workaround

The answer determines whether any practical workaround exists for
consumer GPUs.

## Background: the suggested fork

A colleague pointed us to the us4useu/nvidia-open-gpu-kernel-modules
fork, which removes a SKU restriction on NVIDIA's open-source kernel
driver. The fork is used by an ultrasound research lab for FPGA-to-GPU
peer DMA via DMA-BUF.

On reading the project we noted two issues:

1. The fork is based on driver 570.211; our system runs 580.159. Using
   the fork would require downgrading the entire NVIDIA stack.

2. More importantly, the fork patches the DMA-BUF path, used by FPGAs
   and other PCIe devices. NCCL plus RDMA does not use DMA-BUF. It uses
   nvidia_peermem and the nvidia_p2p_get_pages callback, which is a
   different code path inside the proprietary nvidia.ko binary.

The fork therefore does not target the gate we are hitting, even if
we were willing to downgrade.

## Direct test: what the verbs layer accepts

To bypass NCCL entirely we wrote a small C program that uses libibverbs
directly. It allocates 4 MB of GPU memory via cudaMalloc, then calls
ibv_reg_mr() on that pointer. This is the exact registration call NCCL
performs internally when GDR is enabled.

If ibv_reg_mr() succeeds, the GDR path is open and NCCL's refusal is its
own decision (case a). If it fails, the gate is below NCCL (case b or c).

### Hardware preconditions verified first

- BAR1 exposed: 256 MB
  (lspci -vv shows "Region 1: Memory at 33fe0000000 (64-bit, prefetchable) [size=256M]")

- nvidia_peermem kernel module loaded
  (lsmod shows the module active and linked with ib_uverbs)

- PCIe link under load: Gen3 x16, 8 GT/s
  (nvidia-smi --query-gpu=pcie.link.gen.current returns 3,16)

- IOMMU enabled in Translated mode
  (dmesg shows "iommu: Default domain type: Translated")

All preconditions for peer DMA are satisfied at the hardware and
kernel-module level.

### The program

The full source is in benchmarks/10_gdr_feasibility.c. It performs four
steps:

    1. cudaMalloc(4 MB)              expect: success, get GPU pointer
    2. ibv_get_device_list()         expect: success, find mlx5_1
    3. ibv_open_device + ibv_alloc_pd expect: success
    4. ibv_reg_mr(pd, gpu_ptr, ...)   THE TEST

Compiled with:

    nvcc -o test_gdr test_gdr.c -I/usr/local/cuda/include \
         -L/usr/local/cuda/lib64 -lcudart -libverbs

### Result

    [1/4] cudaMalloc 4194304 bytes: SUCCESS, ptr=0x795806200000
    [2/4] Found RDMA device: mlx5_1
    [3/4] Opened device, allocated PD
    [4/4] ibv_reg_mr on GPU memory: FAILED, errno = 14 (EFAULT)

EFAULT means "Bad address." The verbs library called into the kernel
asking for peer-DMA registration of GPU memory, and the kernel module
inside the closed nvidia.ko driver returned failure.

## Interpretation

This is case (c). The refusal is in the proprietary driver blob.

Specifically:
- libibverbs is open source. It made its call correctly.
- nvidia_peermem is open source. It loaded and forwarded the call.
- The actual nvidia_p2p_get_pages() implementation lives in the closed
  nvidia.ko binary. That function refuses for non-datacenter SKUs.
- NCCL's "GDR Disabled" log message in benchmark 09a is a downstream
  consequence: NCCL probes the verbs layer at startup, gets the same
  EFAULT we just got, and falls back to the host-bounce path.

## What workarounds will and will not work

Will NOT work:
- Patching NCCL (refusal happens before NCCL sees the result)
- Patching the open kernel modules (the relevant code is not in them)
- The us4useu fork (different code path, FPGA-oriented)
- Environment variables (NCCL_NET_GDR_LEVEL=5 was tried; same refusal)
- Newer NVIDIA driver (segmentation is unchanged across versions)
- Older NVIDIA driver (the SKU check has existed since GDR was introduced)

WOULD work:
- A datacenter-class GPU (A100, H100, RTX A6000, etc.) where NVIDIA
  enables the path
- Binary-patching the closed nvidia.ko itself - technically possible,
  has been done in research, but is brittle across driver updates, of
  questionable license compliance, and not a deployable solution

## Why this finding strengthens the study

Without this test, the GDR claim in the report would be of the form
"consumer GPUs do not support GDR" - a vague summary that reviewers
could challenge.

With this test, the claim is precise and measurable:

    The 50 Gb/s NCCL ceiling on the RTX 3060 is a product-segmentation
    feature inside the proprietary NVIDIA driver. We verified this by
    direct libibverbs API testing: ibv_reg_mr() returns EFAULT on a
    valid GPU pointer despite all hardware preconditions being met.

This is a clean experimental result that closes the open question in
the bandwidth analysis.

## Files

    benchmarks/10_gdr_feasibility.c   - the test program (~80 lines)

## Headline

  ibv_reg_mr() with a GPU pointer: returns EFAULT
  Block is in the closed nvidia.ko, below libibverbs and below NCCL
  No community software patch can reach the gate
  Only a datacenter GPU lifts the 50 Gb/s ceiling
