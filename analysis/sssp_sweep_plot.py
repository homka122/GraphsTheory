#!/usr/bin/env python3
"""Графики перебора Δ для SSSP по сводке experiments/sssp-delta-sweep.sh.

usage: sssp_sweep_plot.py <graph>.summary [<graph>.fine.summary ...] [out.png]

Несколько сводок одного графа (например, грубая и мелкая сетка Δ) объединяются.

Слева время от Δ при каждом P (лог. шкала), справа ускорение T(1, Δ) / T(P, Δ).
Δ = 0 в D-Galois означает «без порога» (Беллман–Форд), на оси он стоит последним как ∞.
"""
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LINE = re.compile(r"(\S+) P=(\d+) delta=(\d+) .*time_med=(\d+) rounds=(\d+) work=(\d+)")


def main():
    srcs = [a for a in sys.argv[1:] if not a.endswith(".png")]
    outs = [a for a in sys.argv[1:] if a.endswith(".png")]
    out = outs[0] if outs else re.sub(r"\.summary$", "", srcs[0]) + ".png"

    graph, t = None, {}
    for src in srcs:
        for line in open(src):
            m = LINE.search(line)
            if m:
                graph = m.group(1)
                p, dl, ms = int(m.group(2)), int(m.group(3)), int(m.group(4))
                t[p, dl] = ms
    procs = sorted({p for p, _ in t})
    deltas = sorted({d for _, d in t}, key=lambda d: d or float("inf"))
    labels = [str(d) if d else "∞" for d in deltas]
    xs = range(len(deltas))

    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 5.5))
    cmap = plt.get_cmap("viridis")

    for i, p in enumerate(procs):
        ys = [t[p, d] for d in deltas]
        left.plot(xs, ys, "o-", color=cmap(i / max(1, len(procs) - 1)), label=f"P={p}")
        best = min(range(len(deltas)), key=lambda k: ys[k])
        left.plot(best, ys[best], "o", ms=12, mfc="none", mec="red")
    left.set_yscale("log")
    left.set_xticks(list(xs), labels)
    left.set_xlabel("Δ")
    left.set_ylabel("время, мс (медиана из 3)")
    left.set_title(f"{graph}: время от Δ (красный кружок — лучшее Δ)")
    left.grid(True, which="both", alpha=0.3)
    left.legend()

    right.plot(procs, procs, "k--", label="идеал")
    for k, d in enumerate(deltas):
        right.plot(procs, [t[1, d] / t[p, d] for p in procs], "o-",
                   color=plt.get_cmap("plasma")(k / max(1, len(deltas) - 1)), label=f"Δ={labels[k]}")
    right.set_xlabel("P (процессов)")
    right.set_ylabel("ускорение T(1, Δ) / T(P, Δ)")
    right.set_title(f"{graph}: ускорение при фиксированном Δ")
    right.grid(True, alpha=0.3)
    right.legend()

    fig.suptitle("SSSP push, D-Galois, --exec=Sync, по 1 потоку на процесс")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
