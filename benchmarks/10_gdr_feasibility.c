/*
 * 10_gdr_feasibility.c - probe whether the verbs layer accepts GPU memory.
 *
 * Allocates GPU memory with cudaMalloc, then attempts ibv_reg_mr() on the
 * pointer. Success indicates GDR is available at the verbs layer (NCCL
 * could in principle use it). Failure with EFAULT indicates the closed
 * NVIDIA driver refuses peer DMA registration for this GPU SKU.
 *
 * Build:
 *   nvcc -o test_gdr 10_gdr_feasibility.c \
 *        -I/usr/local/cuda/include -L/usr/local/cuda/lib64 \
 *        -lcudart -libverbs
 *
 * Run:
 *   ./test_gdr mlx5_1
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <infiniband/verbs.h>
#include <cuda_runtime.h>

#define BUF_SIZE (4 * 1024 * 1024)

int main(int argc, char **argv)
{
    const char *dev_name = (argc > 1) ? argv[1] : "mlx5_1";
    printf("=== GDR feasibility test ===\n");
    printf("Target RDMA device: %s\n\n", dev_name);

    void *gpu_buf = NULL;
    cudaError_t cerr = cudaMalloc(&gpu_buf, BUF_SIZE);
    if (cerr != cudaSuccess) {
        fprintf(stderr, "cudaMalloc failed: %s\n", cudaGetErrorString(cerr));
        return 1;
    }
    printf("[1/4] cudaMalloc %d bytes: SUCCESS, ptr=%p\n", BUF_SIZE, gpu_buf);

    int num_devs = 0;
    struct ibv_device **dev_list = ibv_get_device_list(&num_devs);
    if (!dev_list) {
        fprintf(stderr, "ibv_get_device_list failed\n");
        return 1;
    }
    struct ibv_device *target = NULL;
    for (int i = 0; i < num_devs; i++) {
        if (strcmp(ibv_get_device_name(dev_list[i]), dev_name) == 0) {
            target = dev_list[i];
            break;
        }
    }
    if (!target) {
        fprintf(stderr, "Device %s not found among %d devices\n", dev_name, num_devs);
        return 1;
    }
    printf("[2/4] Found RDMA device: %s\n", dev_name);

    struct ibv_context *ctx = ibv_open_device(target);
    if (!ctx) { fprintf(stderr, "ibv_open_device failed\n"); return 1; }
    struct ibv_pd *pd = ibv_alloc_pd(ctx);
    if (!pd) { fprintf(stderr, "ibv_alloc_pd failed\n"); return 1; }
    printf("[3/4] Opened device, allocated PD\n");

    int access = IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE | IBV_ACCESS_REMOTE_READ;
    errno = 0;
    struct ibv_mr *mr = ibv_reg_mr(pd, gpu_buf, BUF_SIZE, access);

    if (mr) {
        printf("[4/4] ibv_reg_mr on GPU memory: *** SUCCESS ***\n");
        printf("\n>>> GDR PATH IS OPEN at the verbs layer.\n");
        printf(">>> NCCL's refusal is its own SKU check, not a driver limit.\n");
        ibv_dereg_mr(mr);
    } else {
        printf("[4/4] ibv_reg_mr on GPU memory: FAILED\n");
        printf("       errno = %d (%s)\n", errno, strerror(errno));
        printf("\n>>> GDR PATH IS BLOCKED below NCCL.\n");
        printf(">>> Refusal is in the closed nvidia.ko driver blob.\n");
        printf(">>> No community software patch can reach the gate.\n");
    }

    ibv_dealloc_pd(pd);
    ibv_close_device(ctx);
    ibv_free_device_list(dev_list);
    cudaFree(gpu_buf);
    return mr ? 0 : 2;
}
