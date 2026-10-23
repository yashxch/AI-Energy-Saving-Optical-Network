from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "AI_Power_Saving_Optical_Networks_Flowchart.png"


def add_box(ax, x, y, width, height, text, color, edge="#d8e5ef", size=10):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.5,
        facecolor=color,
        edgecolor=edge,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        color="#f5f7fa",
        fontsize=size,
        linespacing=1.25,
        wrap=True,
    )


def add_arrow(ax, start, end, label=None, color="#a8c7d9", bend=0.0):
    connection = "arc3,rad={}".format(bend)
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.5,
            color=color,
            connectionstyle=connection,
        )
    )
    if label:
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(
            midpoint[0],
            midpoint[1] + 0.015,
            label,
            ha="center",
            va="center",
            fontsize=8,
            color="#c8d8e3",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "#111d29", "edgecolor": "none", "alpha": 0.9},
        )


def main():
    fig, ax = plt.subplots(figsize=(18, 24), dpi=160)
    fig.patch.set_facecolor("#071018")
    ax.set_facecolor("#071018")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.982,
        "AI-BASED POWER SAVING IN OPTICAL NETWORKS",
        ha="center",
        va="top",
        fontsize=22,
        fontweight="bold",
        color="#67e8f9",
    )
    ax.text(
        0.5,
        0.965,
        "End-to-end system flow: telemetry -> intelligence -> policy validation -> controlled execution",
        ha="center",
        va="top",
        fontsize=11,
        color="#b9cbd6",
    )

    add_box(ax, 0.30, 0.915, 0.40, 0.045, "PHYSICAL OPTICAL NETWORK\n100 devices | 8 nodes | 800G, EDFA, ROADM, filter cards", "#12354a", size=10)
    add_box(ax, 0.30, 0.845, 0.40, 0.045, "NetworkSimulator\nInitializes devices, topology, power modes, faults and telemetry", "#164e63", size=10)
    add_arrow(ax, (0.5, 0.915), (0.5, 0.89), "startup")
    add_arrow(ax, (0.5, 0.845), (0.5, 0.815), "every 1 second")

    add_box(ax, 0.30, 0.765, 0.40, 0.05, "BACKGROUND SIMULATION LOOP\nsimulator.tick() -> diurnal traffic, device telemetry, health and energy accumulation", "#155e75", size=10)
    add_box(ax, 0.08, 0.675, 0.25, 0.055, "Adaptive Baseline\nLearns normal per-device behavior", "#334155", size=9)
    add_box(ax, 0.37, 0.675, 0.26, 0.055, "Digital Twin Synchronization\nCopies telemetry and rebuilds NetworkX topology graph", "#334155", size=9)
    add_box(ax, 0.67, 0.675, 0.25, 0.055, "Fault Injection\nBER spike, overheat, OSNR drop or clear fault", "#5b2636", size=9)
    add_arrow(ax, (0.5, 0.765), (0.205, 0.73), bend=0.0)
    add_arrow(ax, (0.5, 0.765), (0.5, 0.73), bend=0.0)
    add_arrow(ax, (0.5, 0.765), (0.795, 0.73), bend=0.0)

    add_box(ax, 0.24, 0.585, 0.52, 0.05, "FastAPI BACKEND\nREST endpoints expose live device state, analytics, recommendations, FCAPS, digital twin and quantum validation", "#1d4d5f", size=10)
    add_arrow(ax, (0.205, 0.675), (0.35, 0.635), "learned thresholds", bend=0.12)
    add_arrow(ax, (0.5, 0.675), (0.5, 0.635), "cached state", bend=0.0)
    add_arrow(ax, (0.795, 0.675), (0.65, 0.635), "updated health", bend=-0.12)

    add_box(ax, 0.06, 0.47, 0.20, 0.065, "ML ENGINE\nTraffic prediction\n5m / 1h / 24h\nAnomaly detection", "#2f4858", size=9)
    add_box(ax, 0.29, 0.47, 0.20, 0.065, "LLM / RULE ENGINE\nReads telemetry and baselines\nCreates sleep, gain or wake candidates", "#285943", size=9)
    add_box(ax, 0.52, 0.47, 0.20, 0.065, "DIGITAL TWIN\nTemporary what-if clone\nTraffic redistribution and savings", "#3e4c72", size=9)
    add_box(ax, 0.75, 0.47, 0.20, 0.065, "FCAPS MANAGER\nFault alarms, accounting,\nperformance and security logs", "#604052", size=9)
    for x in (0.16, 0.39, 0.62, 0.85):
        add_arrow(ax, (0.5, 0.585), (x, 0.535), bend=0.0)

    add_box(ax, 0.29, 0.365, 0.42, 0.055, "OPTICAL POLICY ENGINE\nQoS / SLA | OSNR >= 14.5 dB | pre-FEC BER <= 1e-4 | link margin | 1+1 protection path", "#754c24", size=9)
    add_arrow(ax, (0.39, 0.47), (0.42, 0.42), "candidate")
    add_arrow(ax, (0.62, 0.47), (0.58, 0.42), "simulated state")
    add_arrow(ax, (0.16, 0.47), (0.32, 0.42), "anomaly risk")

    add_box(ax, 0.08, 0.265, 0.34, 0.055, "REJECT / BLOCK\nReturn reason, keep current power mode,\nwrite DENIED security event", "#6b2737", size=9)
    add_box(ax, 0.58, 0.265, 0.34, 0.055, "APPROVE\nRecommendation is shown to operator\nwith policy checks and estimated savings", "#216e55", size=9)
    add_arrow(ax, (0.4, 0.365), (0.25, 0.32), "failed checks", bend=0.0)
    add_arrow(ax, (0.6, 0.365), (0.75, 0.32), "all checks pass", bend=0.0)

    add_box(ax, 0.58, 0.17, 0.34, 0.055, "OPERATOR / FRONTEND ACTION\nPOST /api/actions/execute or Digital Twin Execute", "#17616f", size=9)
    add_arrow(ax, (0.75, 0.265), (0.75, 0.225), "user confirms")
    add_box(ax, 0.30, 0.08, 0.40, 0.055, "CONTROLLER EXECUTES\nSimulator changes power mode: NORMAL / LOW_GAIN / SLEEP\nFCAPS logs SUCCESS -> next tick reflects new savings", "#176b4c", size=9)
    add_arrow(ax, (0.75, 0.17), (0.5, 0.135), "apply action", bend=0.0)
    add_arrow(ax, (0.30, 0.107), (0.22, 0.765), "feedback loop", color="#49b6a7", bend=0.24)

    add_box(ax, 0.04, 0.005, 0.27, 0.04, "Next.js dashboard\nPolls telemetry endpoints every 2s", "#26384a", size=8)
    add_box(ax, 0.365, 0.005, 0.27, 0.04, "Digital Twin tab\nPolls twin state every 3s; runs what-if scenarios", "#26384a", size=8)
    add_box(ax, 0.69, 0.005, 0.27, 0.04, "Chatbot / Quantum tabs\nChat query or retrieve IBM QPU result for validation", "#26384a", size=8)
    add_arrow(ax, (0.175, 0.045), (0.37, 0.585), "GET APIs", color="#779bb0", bend=-0.25)
    add_arrow(ax, (0.5, 0.045), (0.55, 0.585), "GET/POST APIs", color="#779bb0", bend=-0.1)
    add_arrow(ax, (0.825, 0.045), (0.68, 0.585), "POST branches", color="#779bb0", bend=0.15)

    ax.text(
        0.5,
        0.945,
        "REAL-TIME CONTROL LOOP",
        ha="center",
        va="center",
        fontsize=9,
        color="#7dd3fc",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#0b2330", "edgecolor": "#1d6074"},
    )

    fig.savefig(OUTPUT, dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    print(OUTPUT)


if __name__ == "__main__":
    main()