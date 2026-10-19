#!/usr/bin/env python3
"""График сильной масштабируемости PageRank по experiments/pagerank-scaling.sh.

usage: pr_scaling_plot.py <dir> <graph>

Читает <dir>/<graph>_p<P>.stats (Timer_N, HMAX — все прогоны), пишет <dir>/<graph>.png:
слева время (медиана, min–max), справа ускорение T(1) / T(P).
"""
import glob
import os
import re
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    d, graph = sys.argv[1], sys.argv[2]
    t = {}
    for f in glob.glob(os.path.join(d, f"{graph}_p*.stats")):
        p = int(re.search(r"_p(\d+)\.stats$", f).group(1))
        ts = [int(m.group(1)) for m in re.finditer(r"Timer_\d+, HMAX, (\d+)", open(f).read())]
        if ts:
            t[p] = ts
    ps = sorted(t)
    med = {p: statistics.median(t[p]) for p in ps}

    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5))
    a.errorbar(ps, [med[p] / 1000 for p in ps],
               yerr=[[(med[p] - min(t[p])) / 1000 for p in ps], [(max(t[p]) - med[p]) / 1000 for p in ps]],
               fmt="o-", color="k", capsize=4)
    for p in ps:
        a.annotate(f"{med[p] / 1000:.1f}", (p, med[p] / 1000), textcoords="offset points", xytext=(6, 6))
    a.set_xlabel("P (процессов)")
    a.set_ylabel(f"время, с (медиана из {len(t[ps[0]])}, min–max)")
    a.set_title("Время PageRank (Timer_N)")
    a.set_ylim(bottom=0)
    a.grid(alpha=0.3)

    if 1 in med:
        b.plot(ps, ps, "k--", label="идеал")
        sp = [med[1] / med[p] for p in ps]
        b.plot(ps, sp, "o-", label="ускорение")
        for p, s in zip(ps, sp):
            b.annotate(f"{s:.2f}", (p, s), textcoords="offset points", xytext=(6, -12))
        b.set_xlabel("P (процессов)")
        b.set_ylabel("T(1) / T(P)")
        b.set_title("Ускорение")
        b.grid(alpha=0.3)
        b.legend()

    fig.suptitle(f"{graph}: PageRank push, --exec=Sync, 1 поток на процесс")
    fig.tight_layout()
    out = os.path.join(d, f"{graph}.png")
    fig.savefig(out + ".tmp.png", dpi=110)
    os.replace(out + ".tmp.png", out)
    print(out)


if __name__ == "__main__":
    main()
