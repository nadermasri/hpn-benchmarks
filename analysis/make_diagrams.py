#!/usr/bin/env python3
"""Generate technical diagrams for the benchmarks report."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, FancyArrow
from matplotlib.lines import Line2D
import numpy as np

OUTDIR = "/home/claude/diagrams"

# Palette
USER_BLUE = "#e8f0fe"
USER_STROKE = "#1a73e8"
KERN_GREY = "#f1f3f4"
KERN_STROKE = "#5f6368"
HW_GREEN = "#e6f4ea"
HW_STROKE = "#188038"
NIC_ORANGE = "#fef7e0"
NIC_STROKE = "#e8710a"
WIRE = "#34495e"
TEXT = "#202124"
GPU_PURPLE = "#f3e8fd"
GPU_STROKE = "#8430ce"
RED = "#d93025"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
})

def setup_ax(ax, xlim=(0, 10), ylim=(0, 10)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("auto")

def box(ax, x, y, w, h, label, fc=USER_BLUE, ec=USER_STROKE, fontsize=9, fontweight="normal"):
    bb = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1",
                         facecolor=fc, edgecolor=ec, linewidth=1.4)
    ax.add_patch(bb)
    ax.text(x + w/2, y + h/2, label, ha="center", va="center",
            fontsize=fontsize, fontweight=fontweight, color=TEXT, wrap=True)

def arrow(ax, x1, y1, x2, y2, color=TEXT, lw=1.4, style="->"):
    arr = FancyArrowPatch((x1, y1), (x2, y2),
                          arrowstyle=style, mutation_scale=12,
                          color=color, linewidth=lw)
    ax.add_patch(arr)

def hline(ax, y, x1, x2, color=KERN_STROKE, ls="--", lw=1.2, label=None):
    ax.plot([x1, x2], [y, y], color=color, linestyle=ls, linewidth=lw)
    if label:
        ax.text(x2 - 0.05, y + 0.05, label, ha="right", va="bottom",
                fontsize=8, color=color, fontstyle="italic")


# =========================================================================
# 1. Hardware topology
# =========================================================================
def diagram_topology():
    fig, ax = plt.subplots(figsize=(11, 4.4), dpi=180)
    setup_ax(ax, xlim=(0, 11), ylim=(0, 4.6))

    # Node 1 (left)
    box(ax, 0.3, 0.3, 4.4, 4.0, "", fc="white", ec=USER_STROKE)
    ax.text(2.5, 4.05, "Node 1  —  pc1n", ha="center", fontsize=11, fontweight="bold", color=USER_STROKE)
    box(ax, 0.6, 3.0, 1.7, 0.7, "Xeon E5-1620 v3\n4C / 8T  3.5GHz", fc=USER_BLUE, ec=USER_STROKE, fontsize=8)
    box(ax, 2.5, 3.0, 1.7, 0.7, "32 GB ECC\nDDR4 RAM", fc=USER_BLUE, ec=USER_STROKE, fontsize=8)
    box(ax, 0.6, 2.0, 1.7, 0.7, "NVIDIA RTX 3060\n12 GB  (no GDR)", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=8)
    box(ax, 2.5, 2.0, 1.7, 0.7, "PCIe Gen3 ×16\n~100 Gb/s", fc=KERN_GREY, ec=KERN_STROKE, fontsize=8)
    box(ax, 0.6, 0.8, 3.6, 0.9, "Mellanox ConnectX-5\nmlx5_1  ·  100 GbE  ·  RoCEv2", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9, fontweight="bold")
    ax.text(2.5, 0.5, "192.168.100.1/24   MTU 9000", ha="center", fontsize=8, color=TEXT, fontstyle="italic")

    # Node 2 (right)
    box(ax, 6.3, 0.3, 4.4, 4.0, "", fc="white", ec=USER_STROKE)
    ax.text(8.5, 4.05, "Node 2  —  pc2n", ha="center", fontsize=11, fontweight="bold", color=USER_STROKE)
    box(ax, 6.6, 3.0, 1.7, 0.7, "Xeon E5-1620 v3\n4C / 8T  3.5GHz", fc=USER_BLUE, ec=USER_STROKE, fontsize=8)
    box(ax, 8.5, 3.0, 1.7, 0.7, "32 GB ECC\nDDR4 RAM", fc=USER_BLUE, ec=USER_STROKE, fontsize=8)
    box(ax, 6.6, 2.0, 1.7, 0.7, "NVIDIA RTX 3060\n12 GB  (no GDR)", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=8)
    box(ax, 8.5, 2.0, 1.7, 0.7, "PCIe Gen3 ×16\n~100 Gb/s", fc=KERN_GREY, ec=KERN_STROKE, fontsize=8)
    box(ax, 6.6, 0.8, 3.6, 0.9, "Mellanox ConnectX-5\nmlx5_0  ·  100 GbE  ·  RoCEv2", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9, fontweight="bold")
    ax.text(8.5, 0.5, "192.168.100.2/24   MTU 9000", ha="center", fontsize=8, color=TEXT, fontstyle="italic")

    # Cable
    ax.plot([4.2, 6.6], [1.25, 1.25], color=WIRE, linewidth=3, zorder=1)
    ax.text(5.4, 1.55, "QSFP28 DAC, 0.5 m, back-to-back",
            ha="center", fontsize=9, color=WIRE, fontweight="bold")
    ax.text(5.4, 0.85, "100 Gb/s line rate", ha="center", fontsize=8, color=WIRE, fontstyle="italic")

    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/01_topology.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 2. TCP send path (the seven stages)
# =========================================================================
def diagram_tcp_send():
    fig, ax = plt.subplots(figsize=(8.5, 11), dpi=180)
    setup_ax(ax, xlim=(0, 10), ylim=(0, 14))

    # Zone labels (left vertical bars)
    ax.add_patch(Rectangle((0, 12.2), 9.6, 1.4, facecolor=USER_BLUE, alpha=0.4, edgecolor="none"))
    ax.text(0.15, 12.9, "USER SPACE", fontsize=8, color=USER_STROKE, fontweight="bold", rotation=0)

    ax.add_patch(Rectangle((0, 2.6), 9.6, 9.0, facecolor=KERN_GREY, alpha=0.5, edgecolor="none"))
    ax.text(0.15, 7.1, "KERNEL SPACE", fontsize=8, color=KERN_STROKE, fontweight="bold", rotation=90)

    ax.add_patch(Rectangle((0, 0.4), 9.6, 1.7, facecolor=HW_GREEN, alpha=0.4, edgecolor="none"))
    ax.text(0.15, 1.2, "HARDWARE", fontsize=8, color=HW_STROKE, fontweight="bold", rotation=90)

    # Stages
    y_stage = 12.7
    box(ax, 1.2, y_stage, 7.5, 0.7,
        "(1)  Your process calls  send(fd, buf, 65536)\nbuf lives in your process's virtual address space",
        fc=USER_BLUE, ec=USER_STROKE, fontsize=9, fontweight="bold")

    # Syscall arrow with annotation
    arrow(ax, 5, 12.55, 5, 11.5, color=RED, lw=1.6)
    ax.text(5.2, 11.95, "syscall instruction\nuser → kernel mode switch",
            fontsize=8, color=RED, fontstyle="italic", va="center")
    # Dashed kernel boundary
    ax.plot([0.3, 9.4], [12.2, 12.2], "--", color=RED, linewidth=1, alpha=0.7)

    y_stage = 10.5
    box(ax, 1.2, y_stage, 7.5, 0.9,
        "(2)  sys_sendto() looks up the socket from fd, dispatches to TCP",
        fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 5, y_stage, 5, y_stage - 0.5, color=TEXT, lw=1.2)

    y_stage = 8.6
    box(ax, 1.2, y_stage, 7.5, 1.4,
        "(3)  tcp_sendmsg()  — TCP layer\n"
        "  • COPY 1:  copy_from_user(skb, buf, 65536)      ← memory copy\n"
        "  • split into MSS-sized segments\n"
        "  • build TCP headers (seq, ack, flags, checksum)\n"
        "  • check congestion window (cwnd)",
        fc=KERN_GREY, ec=RED, fontsize=8.5, fontweight="normal")
    ax.text(8.9, y_stage + 0.7, "MOST\nEXPENSIVE", fontsize=8, color=RED, fontweight="bold",
            ha="center", va="center")
    arrow(ax, 5, y_stage, 5, y_stage - 0.5, color=TEXT, lw=1.2)

    y_stage = 7.1
    box(ax, 1.2, y_stage, 7.5, 0.9,
        "(4)  ip_output()  — IP layer\nbuild IP header, routing decision",
        fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 5, y_stage, 5, y_stage - 0.5, color=TEXT, lw=1.2)

    y_stage = 5.7
    box(ax, 1.2, y_stage, 7.5, 0.8,
        "(5)  dev_queue_xmit()  — qdisc queue / scheduling",
        fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 5, y_stage, 5, y_stage - 0.5, color=TEXT, lw=1.2)

    y_stage = 4.0
    box(ax, 1.2, y_stage, 7.5, 1.1,
        "(6)  NIC driver  (mlx5_core)\n"
        "  • build DMA descriptor\n"
        "  • write to NIC TX ring  +  doorbell",
        fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 5, y_stage, 5, y_stage - 0.6, color=RED, lw=1.4)
    ax.text(5.2, y_stage - 0.3, "PCIe DMA + doorbell",
            fontsize=8, color=RED, fontstyle="italic", va="center")
    ax.plot([0.3, 9.4], [2.6, 2.6], "--", color=RED, linewidth=1, alpha=0.7)

    y_stage = 1.0
    box(ax, 1.2, y_stage, 7.5, 1.1,
        "(7)  NIC hardware\n"
        "  • DMA-reads payload from RAM\n"
        "  • serializes onto the wire  →  100 Gb/s",
        fc=HW_GREEN, ec=HW_STROKE, fontsize=9, fontweight="bold")

    ax.set_title("TCP send path — 7 stages, kernel does protocol work",
                 fontsize=11, fontweight="bold", pad=10)
    plt.savefig(f"{OUTDIR}/02_tcp_send_path.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 3. RDMA send path (kernel bypass)
# =========================================================================
def diagram_rdma_send():
    fig, ax = plt.subplots(figsize=(8.5, 9), dpi=180)
    setup_ax(ax, xlim=(0, 10), ylim=(0, 11))

    # Zone backgrounds
    ax.add_patch(Rectangle((0, 9.0), 9.6, 1.8, facecolor=USER_BLUE, alpha=0.4, edgecolor="none"))
    ax.text(0.15, 9.9, "USER SPACE", fontsize=8, color=USER_STROKE, fontweight="bold", rotation=90)

    ax.add_patch(Rectangle((0, 5.8), 9.6, 3.0, facecolor=KERN_GREY, alpha=0.3, edgecolor="none"))
    ax.text(0.15, 7.3, "KERNEL SPACE\n(skipped on data path)", fontsize=8, color=KERN_STROKE,
            fontweight="bold", rotation=90, va="center")
    # Big "BYPASS" arrow
    ax.text(5, 7.3, "❌  KERNEL BYPASSED ENTIRELY",
            ha="center", fontsize=12, color=RED, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=RED, linewidth=1.2))

    ax.add_patch(Rectangle((0, 0.4), 9.6, 5.2, facecolor=HW_GREEN, alpha=0.3, edgecolor="none"))
    ax.text(0.15, 3.0, "HARDWARE  (NIC)", fontsize=8, color=HW_STROKE, fontweight="bold", rotation=90, va="center")

    # Stage 1: app posts WR
    box(ax, 1.0, 9.4, 7.8, 1.1,
        "(1)  App calls  ibv_post_send(qp, work_request)\n"
        "  work_request points to your buffer  ·  no memory copy",
        fc=USER_BLUE, ec=USER_STROKE, fontsize=9.5, fontweight="bold")

    # Direct arrow user → NIC, bypassing kernel zone
    arrow(ax, 5, 9.4, 5, 5.3, color=USER_STROKE, lw=2.5)
    ax.text(5.3, 7.3, "memory-mapped\ndoorbell write",
            fontsize=8.5, color=USER_STROKE, fontstyle="italic", va="center", fontweight="bold")

    # Stages in NIC
    box(ax, 1.0, 4.3, 7.8, 0.9,
        "(2)  NIC reads the work request",
        fc=HW_GREEN, ec=HW_STROKE, fontsize=9)
    arrow(ax, 5, 4.3, 5, 3.9, color=TEXT)

    box(ax, 1.0, 2.9, 7.8, 1.0,
        "(3)  NIC DMA-reads payload directly from user RAM  ← no copy",
        fc=HW_GREEN, ec=RED, fontsize=9, fontweight="bold")
    arrow(ax, 5, 2.9, 5, 2.5, color=TEXT)

    box(ax, 1.0, 1.5, 7.8, 1.0,
        "(4)  NIC builds RoCEv2 packet  (Eth + IP + UDP + IB BTH)",
        fc=HW_GREEN, ec=HW_STROKE, fontsize=9)
    arrow(ax, 5, 1.5, 5, 1.1, color=TEXT)

    box(ax, 1.0, 0.5, 7.8, 0.6,
        "(5)  NIC transmits on the wire  →  100 Gb/s",
        fc=HW_GREEN, ec=HW_STROKE, fontsize=9, fontweight="bold")

    ax.set_title("RDMA send path — NIC does the work, kernel does nothing",
                 fontsize=11, fontweight="bold", pad=10)
    plt.savefig(f"{OUTDIR}/03_rdma_send_path.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 4. Side-by-side TCP vs RDMA comparison
# =========================================================================
def diagram_compare_paths():
    fig, ax = plt.subplots(figsize=(11, 8), dpi=180)
    setup_ax(ax, xlim=(0, 12), ylim=(0, 9))

    # Headers
    ax.text(3, 8.5, "Kernel TCP", ha="center", fontsize=13, fontweight="bold", color=USER_STROKE)
    ax.text(9, 8.5, "RDMA (RoCEv2)", ha="center", fontsize=13, fontweight="bold", color=HW_STROKE)
    # Divider
    ax.plot([6, 6], [0.3, 8.4], color="lightgrey", linewidth=1, linestyle=":")

    # ============ LEFT: TCP ============
    box(ax, 0.3, 7.6, 5.4, 0.6, "send(fd, buf, len)", fc=USER_BLUE, ec=USER_STROKE, fontsize=9.5, fontweight="bold")
    arrow(ax, 3, 7.55, 3, 7.15, color=RED)
    ax.text(3.4, 7.35, "syscall", fontsize=8, color=RED, fontstyle="italic")

    box(ax, 0.3, 6.4, 5.4, 0.7, "TCP/IP stack: copy, headers, cwnd", fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 3, 6.35, 3, 5.95)
    box(ax, 0.3, 5.2, 5.4, 0.7, "IP layer, qdisc, driver", fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 3, 5.15, 3, 4.75)
    box(ax, 0.3, 4.0, 5.4, 0.7, "NIC TX", fc=HW_GREEN, ec=HW_STROKE, fontsize=9, fontweight="bold")
    arrow(ax, 3, 3.95, 3, 3.55)
    box(ax, 0.3, 2.8, 5.4, 0.7, "Wire", fc=KERN_GREY, ec=WIRE, fontsize=9)
    arrow(ax, 3, 2.75, 3, 2.35)
    box(ax, 0.3, 1.6, 5.4, 0.7, "NIC RX → softirq → TCP → copy → recv()", fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 3, 1.55, 3, 1.15)
    box(ax, 0.3, 0.4, 5.4, 0.7, "recv() returns to app", fc=USER_BLUE, ec=USER_STROKE, fontsize=9.5, fontweight="bold")

    # Cost annotations
    ax.text(5.85, 6.75, "2× copy", fontsize=8, color=RED, fontweight="bold", va="center")
    ax.text(5.85, 5.55, "syscalls", fontsize=8, color=RED, fontweight="bold", va="center")
    ax.text(5.85, 1.95, "softirq\nstorm", fontsize=8, color=RED, fontweight="bold", va="center")

    # Bottom summary
    ax.text(3, -0.1, "1 core busy mostly in kernel\n~12 µs one-way latency", ha="center",
            fontsize=10, color=RED, fontweight="bold")

    # ============ RIGHT: RDMA ============
    box(ax, 6.3, 7.6, 5.4, 0.6, "ibv_post_send(qp, wr)", fc=USER_BLUE, ec=USER_STROKE, fontsize=9.5, fontweight="bold")
    arrow(ax, 9, 7.55, 9, 4.75, color=USER_STROKE, lw=2.2)
    ax.text(9.4, 6.2, "doorbell write\n(no syscall, no copy)", fontsize=8.5,
            color=USER_STROKE, fontstyle="italic", va="center", fontweight="bold")

    # Greyed-out "kernel" zone with strikethrough effect
    ax.add_patch(Rectangle((6.3, 5.6), 5.4, 1.5, facecolor="#f0f0f0", alpha=0.4, edgecolor=KERN_STROKE, linewidth=0.5, linestyle="--"))
    ax.text(9, 6.35, "KERNEL SKIPPED", ha="center", va="center", fontsize=11,
            color=KERN_STROKE, fontweight="bold", alpha=0.6)

    box(ax, 6.3, 4.0, 5.4, 0.7, "NIC DMA from user RAM + RoCEv2 build", fc=HW_GREEN, ec=HW_STROKE, fontsize=9, fontweight="bold")
    arrow(ax, 9, 3.95, 9, 3.55)
    box(ax, 6.3, 2.8, 5.4, 0.7, "Wire", fc=KERN_GREY, ec=WIRE, fontsize=9)
    arrow(ax, 9, 2.75, 9, 2.35)
    box(ax, 6.3, 1.6, 5.4, 0.7, "NIC RX → DMA into user RAM → CQE", fc=HW_GREEN, ec=HW_STROKE, fontsize=9, fontweight="bold")
    arrow(ax, 9, 1.55, 9, 1.15)
    box(ax, 6.3, 0.4, 5.4, 0.7, "App polls CQ, sees completion", fc=USER_BLUE, ec=USER_STROKE, fontsize=9.5, fontweight="bold")

    ax.text(9, -0.1, "1 core polling in user-space, 0 kernel\n~0.8 µs one-way latency", ha="center",
            fontsize=10, color=HW_STROKE, fontweight="bold")

    ax.set_ylim(-0.5, 9)
    ax.set_title("Same operation, two transports", fontsize=12, fontweight="bold", pad=10)
    plt.savefig(f"{OUTDIR}/04_compare_paths.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 5. RoCEv2 packet structure
# =========================================================================
def diagram_packet():
    fig, ax = plt.subplots(figsize=(12, 2.8), dpi=180)
    setup_ax(ax, xlim=(0, 14), ylim=(0, 4))

    headers = [
        ("Ethernet\nheader", "14 B", "#e8eaf6", "#3949ab"),
        ("IPv4\nheader", "20 B", "#fce4ec", "#c2185b"),
        ("UDP\nheader\ndst=4791", "8 B", "#fff3e0", "#e65100"),
        ("IB Base Transport\nHeader (BTH)\nQP num, PSN, opcode", "12 B", "#e8f5e9", "#2e7d32"),
        ("Payload\n(your data)\nup to ~8900 B with MTU 9000", "...", "#e3f2fd", "#1565c0"),
    ]
    widths = [1.4, 1.4, 1.4, 2.4, 6.6]
    x = 0.5
    for (label, size, fc, ec), w in zip(headers, widths):
        ax.add_patch(FancyBboxPatch((x, 1.2), w, 1.8, boxstyle="round,pad=0.02",
                                     facecolor=fc, edgecolor=ec, linewidth=1.5))
        ax.text(x + w/2, 2.4, label, ha="center", va="center", fontsize=9.5, color=TEXT, fontweight="bold")
        ax.text(x + w/2, 1.5, size, ha="center", va="center", fontsize=8.5, color=ec, fontweight="bold")
        x += w + 0.05

    ax.text(7, 3.4, "RoCEv2 wire packet — InfiniBand transport tunneled over UDP/IP/Ethernet",
            ha="center", fontsize=11, fontweight="bold", color=TEXT)
    ax.text(7, 0.75, "→ goes over standard Ethernet switches  ·  destination UDP port 4791 identifies as RoCEv2",
            ha="center", fontsize=9, color=TEXT, fontstyle="italic")

    plt.savefig(f"{OUTDIR}/05_rocev2_packet.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 6. GDR vs no-GDR data path
# =========================================================================
def diagram_gdr():
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=180)
    setup_ax(ax, xlim=(0, 14), ylim=(0, 7))

    # Top: with GDR (server GPU)
    ax.text(7, 6.4, "With GPUDirect RDMA  (A100, H100, RTX A6000, …)",
            ha="center", fontsize=12, fontweight="bold", color=HW_STROKE)

    box(ax, 0.5, 4.7, 2.0, 0.9, "GPU\nmemory", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=9.5, fontweight="bold")
    box(ax, 5.0, 4.7, 2.0, 0.9, "NIC", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9.5, fontweight="bold")
    arrow(ax, 2.5, 5.15, 5.0, 5.15, color=HW_STROKE, lw=2.5)
    ax.text(3.75, 5.4, "NIC DMA  direct\n(no host bounce)", ha="center", fontsize=8.5, color=HW_STROKE, fontweight="bold")

    box(ax, 7.5, 4.7, 1.8, 0.9, "Wire", fc=KERN_GREY, ec=WIRE, fontsize=9.5, fontweight="bold")
    arrow(ax, 7.0, 5.15, 7.5, 5.15, color=WIRE, lw=2)
    arrow(ax, 9.3, 5.15, 9.8, 5.15, color=WIRE, lw=2)

    box(ax, 9.8, 4.7, 2.0, 0.9, "NIC", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9.5, fontweight="bold")
    box(ax, 12.0, 4.7, 1.5, 0.9, "GPU\nmem", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=9.5, fontweight="bold")
    arrow(ax, 11.8, 5.15, 12.0, 5.15, color=HW_STROKE, lw=2.5)

    ax.text(7, 4.3, "≈ 95 Gb/s peak NCCL allreduce  ·  PCIe touched twice, but only by NIC",
            ha="center", fontsize=10, color=HW_STROKE, fontweight="bold")

    # Divider
    ax.plot([0.3, 13.7], [3.8, 3.8], color="lightgrey", linewidth=1.2, linestyle="-")

    # Bottom: without GDR (our RTX 3060)
    ax.text(7, 3.3, "Without GPUDirect RDMA  (RTX 3060, consumer GPUs)",
            ha="center", fontsize=12, fontweight="bold", color=RED)

    box(ax, 0.3, 1.6, 1.7, 0.9, "GPU mem", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=9, fontweight="bold")
    arrow(ax, 2.0, 2.05, 2.5, 2.05, color=RED, lw=2)
    box(ax, 2.5, 1.6, 1.7, 0.9, "host RAM", fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 4.2, 2.05, 4.7, 2.05, color=RED, lw=2)
    box(ax, 4.7, 1.6, 1.4, 0.9, "NIC", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9)
    arrow(ax, 6.1, 2.05, 6.6, 2.05, color=WIRE, lw=2)
    box(ax, 6.6, 1.6, 1.2, 0.9, "Wire", fc=KERN_GREY, ec=WIRE, fontsize=9)
    arrow(ax, 7.8, 2.05, 8.3, 2.05, color=WIRE, lw=2)
    box(ax, 8.3, 1.6, 1.4, 0.9, "NIC", fc=NIC_ORANGE, ec=NIC_STROKE, fontsize=9)
    arrow(ax, 9.7, 2.05, 10.2, 2.05, color=RED, lw=2)
    box(ax, 10.2, 1.6, 1.7, 0.9, "host RAM", fc=KERN_GREY, ec=KERN_STROKE, fontsize=9)
    arrow(ax, 11.9, 2.05, 12.4, 2.05, color=RED, lw=2)
    box(ax, 12.4, 1.6, 1.3, 0.9, "GPU mem", fc=GPU_PURPLE, ec=GPU_STROKE, fontsize=9, fontweight="bold")

    # Annotate the two PCIe bounces
    ax.annotate("PCIe bounce #1\n(GPU→host)", xy=(3.35, 1.6), xytext=(3.35, 0.7),
                ha="center", fontsize=8.5, color=RED, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1))
    ax.annotate("PCIe bounce #2\n(host→GPU)", xy=(11.05, 1.6), xytext=(11.05, 0.7),
                ha="center", fontsize=8.5, color=RED, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1))

    ax.text(7, 0.15, "≈ 50 Gb/s peak NCCL allreduce  ·  half of raw RDMA, capped by PCIe Gen3 ×16",
            ha="center", fontsize=10, color=RED, fontweight="bold")

    plt.savefig(f"{OUTDIR}/06_gdr_paths.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 7. Bandwidth comparison bar chart
# =========================================================================
def chart_bandwidth():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=180)

    tests = [
        ("RoCEv2 RDMA\n(1 conn, raw)",          98.27, HW_STROKE),
        ("Kernel TCP\n(8 streams, raw)",        93.30, USER_STROKE),
        ("TCP zero-copy\n(8 streams, raw)",     92.10, USER_STROKE),
        ("NCCL allreduce\nRDMA (no GDR)",       50.6,  GPU_STROKE),
        ("Kernel TCP\n(1 stream, raw)",         34.30, USER_STROKE),
        ("NCCL allreduce\nTCP sockets",         10.3,  RED),
    ]
    names = [t[0] for t in tests]
    vals = [t[1] for t in tests]
    colors = [t[2] for t in tests]

    bars = ax.barh(names, vals, color=colors, edgecolor="black", linewidth=0.7, alpha=0.85)
    ax.invert_yaxis()
    ax.set_xlim(0, 110)
    ax.set_xlabel("Throughput (Gb/s)", fontsize=11)
    ax.axvline(100, color="red", linestyle="--", linewidth=1, alpha=0.6)
    ax.text(100, -0.45, "line rate", color="red", fontsize=9, ha="center", fontstyle="italic")

    for bar, val in zip(bars, vals):
        ax.text(val + 1.5, bar.get_y() + bar.get_height()/2,
                f"{val:.1f} Gb/s", va="center", fontsize=10, fontweight="bold")

    ax.set_title("Throughput across all transports — 100 Gb/s link",
                 fontsize=12, fontweight="bold", pad=12)
    ax.grid(axis="x", alpha=0.3)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_visible(True)

    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/07_bandwidth_chart.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 8. CPU cost comparison
# =========================================================================
def chart_cpu_cost():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=180)

    # LEFT: cores per Gb/s
    tests = ["RoCEv2\nRDMA", "TCP\n1 stream", "TCP\n8 streams\n(sender)", "TCP\n8 streams\n(receiver)"]
    cost = [0.0102, 0.0277, 0.0624, 0.0829]
    colors_l = [HW_STROKE, USER_STROKE, USER_STROKE, RED]

    bars = ax1.bar(tests, cost, color=colors_l, alpha=0.85, edgecolor="black", linewidth=0.7)
    for bar, v in zip(bars, cost):
        ax1.text(bar.get_x() + bar.get_width()/2, v + 0.002,
                 f"{v:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax1.set_ylabel("CPU cores per Gb/s of throughput", fontsize=10.5)
    ax1.set_title("CPU cost per Gb/s\n(lower is better)", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 0.10)
    ax1.grid(axis="y", alpha=0.3)
    ax1.spines["bottom"].set_visible(True)
    ax1.spines["left"].set_visible(True)

    # Annotation showing the ratio
    ax1.annotate("", xy=(0, 0.092), xytext=(3, 0.092),
                  arrowprops=dict(arrowstyle="<->", color="black", lw=1.2))
    ax1.text(1.5, 0.095, "8× more CPU per Gb/s",
              ha="center", fontsize=9.5, fontweight="bold", color=RED)

    # RIGHT: stacked composition
    tests2 = ["RDMA\n(98 Gb/s)", "TCP 1-str\n(34 Gb/s)", "TCP 8-str sender\n(94 Gb/s)", "TCP 8-str RX\n(94 Gb/s)"]
    pct_usr = [12.5, 0.25, 1.0, 1.9]
    pct_sys = [0.0, 11.1, 57.0, 62.7]
    pct_soft = [0.0, 1.3, 15.6, 32.9]

    x = np.arange(len(tests2))
    width = 0.5
    p1 = ax2.bar(x, pct_usr, width, label="%usr (application)", color="#4caf50", alpha=0.85, edgecolor="black", linewidth=0.7)
    p2 = ax2.bar(x, pct_sys, width, bottom=pct_usr, label="%sys (kernel TCP/IP)", color="#ff9800", alpha=0.85, edgecolor="black", linewidth=0.7)
    p3 = ax2.bar(x, pct_soft, width, bottom=[a+b for a,b in zip(pct_usr, pct_sys)],
                  label="%soft (kernel softirq)", color="#f44336", alpha=0.85, edgecolor="black", linewidth=0.7)

    totals = [a+b+c for a,b,c in zip(pct_usr, pct_sys, pct_soft)]
    for i, t in enumerate(totals):
        ax2.text(i, t + 1.5, f"{t:.1f}%", ha="center", fontsize=10, fontweight="bold")

    ax2.set_xticks(x)
    ax2.set_xticklabels(tests2, fontsize=9)
    ax2.set_ylabel("% of total CPU (= 800% over 8 cores)", fontsize=10.5)
    ax2.set_title("Where the CPU time goes\n(stacked composition)", fontsize=11, fontweight="bold")
    ax2.set_ylim(0, 110)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(axis="y", alpha=0.3)
    ax2.spines["bottom"].set_visible(True)
    ax2.spines["left"].set_visible(True)

    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/08_cpu_cost.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 9. NCCL allreduce comparison (size sweep)
# =========================================================================
def chart_nccl_sweep():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=180)

    sizes = np.array([8, 64, 512, 4096, 32768, 262144, 1048576, 8388608, 67108864, 268435456])
    rdma  = np.array([0.000, 0.003, 0.024, 0.187, 1.064, 2.185, 5.379, 5.463, 6.205, 6.331])
    tcp   = np.array([0.000, 0.001, 0.005, 0.044, 0.130, 0.321, 0.936, 1.207, 1.290, 1.288])

    ax.semilogx(sizes, rdma * 8, "o-", color=HW_STROKE, linewidth=2.5, markersize=8,
                label="NCCL over RDMA  (peak 50.6 Gb/s)")
    ax.semilogx(sizes, tcp * 8, "s-", color=RED, linewidth=2.5, markersize=8,
                label="NCCL over TCP  (peak 10.3 Gb/s)")

    ax.axhline(98, color="grey", linestyle=":", alpha=0.5, linewidth=1)
    ax.text(8, 95, "raw RDMA ceiling (98 Gb/s)", fontsize=8.5, color="grey", fontstyle="italic")

    ax.set_xlabel("Message size (bytes, log scale)", fontsize=11)
    ax.set_ylabel("Bus bandwidth (Gb/s)", fontsize=11)
    ax.set_title("NCCL allreduce performance — RDMA vs TCP, same hardware",
                 fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper left", fontsize=10, framealpha=0.95)
    ax.grid(True, which="both", alpha=0.3)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_visible(True)
    ax.set_ylim(0, 105)

    # Annotate the ~5× gap region
    ax.annotate("", xy=(2e8, 50.6), xytext=(2e8, 10.3),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.4))
    ax.text(2.6e8, 30, "≈ 5×\ngap", fontsize=11, fontweight="bold", color="black")

    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/09_nccl_sweep.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 10. Latency comparison
# =========================================================================
def chart_latency():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=180)

    categories = ["RDMA\nmean", "RDMA\np99", "RDMA\nmax", "TCP\nmean", "TCP\np99", "TCP\nmax"]
    values = [0.83, 1.01, 2.0, 12.28, 16.15, 79.16]
    colors_b = [HW_STROKE]*3 + [RED]*3

    bars = ax.bar(categories, values, color=colors_b, alpha=0.85, edgecolor="black", linewidth=0.7)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, v + 1.5,
                f"{v:.2f} µs", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylabel("One-way latency (µs)", fontsize=11)
    ax.set_title("Latency comparison — sub-µs RDMA vs ~12 µs TCP",
                 fontsize=12, fontweight="bold", pad=10)
    ax.set_ylim(0, 95)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_visible(True)

    # Divider line
    ax.axvline(2.5, color="lightgrey", linestyle="--", alpha=0.7)

    # Annotate ratio
    ax.annotate("", xy=(0, 88), xytext=(3, 88),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.3))
    ax.text(1.5, 90, "15× lower\n(mean)", ha="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/10_latency.png", bbox_inches="tight", facecolor="white")
    plt.close()


# =========================================================================
# 11. NCCL bandwidth ceiling ladder
# =========================================================================
def chart_ladder():
    fig, ax = plt.subplots(figsize=(11, 4.5), dpi=180)

    ceilings = [
        ("Raw host-to-host RDMA",              98,  HW_STROKE, "test 01"),
        ("NCCL + GPU + GDR (server GPU)",      95,  HW_STROKE, "estimated"),
        ("NCCL + GPU, no GDR (RTX 3060)",      51,  GPU_STROKE, "test 09a — we are here"),
        ("NCCL + TCP fallback",                10,  RED, "test 09b"),
    ]
    names = [c[0] for c in ceilings]
    vals = [c[1] for c in ceilings]
    colors_l = [c[2] for c in ceilings]
    labels = [c[3] for c in ceilings]

    y = np.arange(len(names))
    bars = ax.barh(y, vals, color=colors_l, alpha=0.85, edgecolor="black", linewidth=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Throughput (Gb/s)", fontsize=11)
    ax.set_xlim(0, 115)
    ax.axvline(100, color="red", linestyle="--", linewidth=1, alpha=0.5)
    ax.text(100, -0.45, "line rate", color="red", fontsize=9, ha="center", fontstyle="italic")

    for bar, v, lab in zip(bars, vals, labels):
        ax.text(v + 1.5, bar.get_y() + bar.get_height()/2,
                f"{v} Gb/s   ({lab})", va="center", fontsize=10)

    ax.set_title("Bandwidth ceilings — each line is one bottleneck removed",
                 fontsize=12, fontweight="bold", pad=10)
    ax.grid(axis="x", alpha=0.3)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_visible(True)
    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/11_ladder.png", bbox_inches="tight", facecolor="white")
    plt.close()


if __name__ == "__main__":
    diagram_topology()
    print("✓ 01 topology")
    diagram_tcp_send()
    print("✓ 02 TCP send path")
    diagram_rdma_send()
    print("✓ 03 RDMA send path")
    diagram_compare_paths()
    print("✓ 04 side-by-side comparison")
    diagram_packet()
    print("✓ 05 RoCEv2 packet")
    diagram_gdr()
    print("✓ 06 GDR vs no-GDR")
    chart_bandwidth()
    print("✓ 07 bandwidth chart")
    chart_cpu_cost()
    print("✓ 08 CPU cost")
    chart_nccl_sweep()
    print("✓ 09 NCCL sweep")
    chart_latency()
    print("✓ 10 latency")
    chart_ladder()
    print("✓ 11 bandwidth ladder")
    print("\nAll diagrams generated.")
