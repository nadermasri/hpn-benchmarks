"""
09_ddp_training.py - Distributed ResNet-50 training, RDMA vs TCP.
Synthetic data, ImageNet-style 224x224x3 inputs.

Launch with torchrun from both nodes:

# RDMA:
NCCL_IB_HCA=mlx5_X:1 NCCL_SOCKET_IFNAME=ensXXXX NCCL_NET_GDR_LEVEL=0 \\
torchrun --nnodes=2 --node_rank=N --nproc_per_node=1 \\
    --master_addr=192.168.100.1 --master_port=29500 09_ddp_training.py

# TCP:
NCCL_IB_DISABLE=1 NCCL_SOCKET_IFNAME=ensXXXX \\
torchrun --nnodes=2 --node_rank=N --nproc_per_node=1 \\
    --master_addr=192.168.100.1 --master_port=29500 09_ddp_training.py
"""

import os
import time
import statistics
import torch
import torch.nn as nn
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
import torchvision.models as models


def main():
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    local_rank = int(os.environ["LOCAL_RANK"])
    is_master = (rank == 0)

    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")

    dist.init_process_group(backend="nccl")

    if is_master:
        print(f"World size: {world_size}, backend: nccl", flush=True)
        print(f"Device: {torch.cuda.get_device_name(local_rank)}", flush=True)

    model = models.resnet50(weights=None).to(device)
    model = DDP(model, device_ids=[local_rank], output_device=local_rank)

    optimizer = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    loss_fn = nn.CrossEntropyLoss()

    # Try BATCH=32 first; then BATCH=4 to expose the TCP penalty
    BATCH = 4
    inputs = torch.randn(BATCH, 3, 224, 224, device=device)
    labels = torch.randint(0, 1000, (BATCH,), device=device)

    WARMUP = 10
    MEASURE = 40
    TOTAL = WARMUP + MEASURE

    step_times, fwd_times, bwd_times = [], [], []

    model.train()
    for step in range(TOTAL):
        torch.cuda.synchronize()
        t_start = time.perf_counter()

        out = model(inputs)
        loss = loss_fn(out, labels)
        torch.cuda.synchronize()
        t_fwd = time.perf_counter()

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.cuda.synchronize()
        t_bwd = time.perf_counter()

        optimizer.step()
        torch.cuda.synchronize()
        t_end = time.perf_counter()

        if step >= WARMUP:
            step_times.append((t_end - t_start) * 1000)
            fwd_times.append((t_fwd - t_start) * 1000)
            bwd_times.append((t_bwd - t_fwd) * 1000)

        if is_master and step % 5 == 0:
            print(
                f"step {step:3d}  total={1000*(t_end-t_start):7.1f}ms  "
                f"fwd={1000*(t_fwd-t_start):6.1f}ms  "
                f"bwd+allreduce={1000*(t_bwd-t_fwd):6.1f}ms",
                flush=True,
            )

    if is_master:
        print()
        print("=" * 60)
        print(f"Results over {MEASURE} measured iterations (after {WARMUP} warmup)")
        print("=" * 60)
        print(f"Step time (ms):")
        print(f"  median   : {statistics.median(step_times):7.2f}")
        print(f"  mean     : {statistics.mean(step_times):7.2f}")
        print(f"  stdev    : {statistics.stdev(step_times):7.2f}")
        print(f"  min      : {min(step_times):7.2f}")
        print(f"  max      : {max(step_times):7.2f}")
        print()
        print(f"Forward pass (ms):       median {statistics.median(fwd_times):.2f}")
        print(f"Backward + allreduce:    median {statistics.median(bwd_times):.2f}")
        print()
        ratio = statistics.median(bwd_times) / statistics.median(fwd_times)
        print(f"Backward/Forward ratio:  {ratio:.2f}x")
        print(f"  (single-GPU baseline is ~2.0x; higher = network overhead)")

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
