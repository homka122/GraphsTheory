#!/usr/bin/env python3
"""Графики масштабируемости подсчёта треугольников по логам experiments/tc-scaling.sh.

usage: tc_plot.py <results/tc-scaling> <graph> [out.png]

Слева время подсчёта (медиана по прогонам, усы мин–макс) и построения графа от P,
в центре ускорение (фактическое, идеал и «без перекоса» = T(1) / среднее compute),
справа compute каждого процесса (медиана по прогонам).
Compute по процессам — статистика "TC_1, Time": подсчёт идёт одним do_all на прогон,
поэтому округление таймера Galois до мс на неё не влияет.
"""
import glob
import os
import re
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def host_values(path, key):
    for line in open(path):
        if key in line and "HostValues" in line:
            return [float(x) for x in line.rsplit(", ", 1)[1].split(";")]
    return None


def main():
    d, graph = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(d, f"{graph}.png")

    runs = {}
    for f in glob.glob(os.path.join(d, f"{graph}_p*.stats")):
        p = int(re.search(r"_p(\d+)\.stats$", f).group(1))
        n = sum(1 for line in open(f) if re.search(r"TC, Timer_\d+, HostValues", line))
        timers = [host_values(f, f"TC, Timer_{r},")[0] for r in range(n)]
        # compute каждого процесса — медиана по прогонам
        per_run = [host_values(f, f"TC_{r}, Time") for r in range(n)]
        runs[p] = dict(time=statistics.median(timers), tmin=min(timers), tmax=max(timers), runs=n,
                       construct=host_values(f, "GraphConstructTime")[0],
                       hosts=[statistics.median(h) for h in zip(*per_run)])
    procs = sorted(runs)
    t1 = runs[1]["time"]

    fig, (a, b, c) = plt.subplots(1, 3, figsize=(17, 5.2))

    a.errorbar(procs, [runs[p]["time"] / 1000 for p in procs],
               yerr=[[(runs[p]["time"] - runs[p]["tmin"]) / 1000 for p in procs],
                     [(runs[p]["tmax"] - runs[p]["time"]) / 1000 for p in procs]],
               fmt="o-", capsize=4, label=f"подсчёт (медиана из {runs[1]['runs']}, мин–макс)")
    a.plot(procs, [runs[p]["construct"] / 1000 for p in procs], "s-", label="построение графа")
    a.plot(procs, [t1 / p / 1000 for p in procs], "k--", alpha=0.6, label="идеал подсчёта T(1)/P")
    a.set_xlabel("P (процессов)")
    a.set_ylabel("время, с")
    a.set_title("Время")
    a.grid(True, alpha=0.3)
    a.legend()

    b.plot(procs, procs, "k--", label="идеал")
    b.plot(procs, [t1 / statistics.mean(runs[p]["hosts"]) for p in procs], "^-",
           label="без перекоса: T(1) / среднее compute")
    b.plot(procs, [t1 / runs[p]["time"] for p in procs], "o-", label="фактическое: T(1) / T(P)")
    for p in procs:
        b.annotate(f"{t1 / runs[p]['time']:.2f}", (p, t1 / runs[p]["time"]),
                   textcoords="offset points", xytext=(0, -14), ha="center", fontsize=9)
    b.set_xlabel("P (процессов)")
    b.set_ylabel("ускорение")
    b.set_title("Ускорение подсчёта")
    b.grid(True, alpha=0.3)
    b.legend()

    width = 0.8
    for p in procs:
        hosts = runs[p]["hosts"]
        w = width / len(hosts)
        for i, h in enumerate(hosts):
            x = p - width / 2 + w * (i + 0.5)
            c.bar(x, h / 1000, w * 0.9, color="tab:red" if h == max(hosts) else "tab:blue")
        c.hlines(statistics.mean(hosts) / 1000, p - width / 2, p + width / 2, colors="k", linestyles=":")
        c.annotate(f"max/ср {max(hosts) / statistics.mean(hosts):.2f}", (p, max(hosts) / 1000),
                   textcoords="offset points", xytext=(0, 4), ha="center", fontsize=8)
    c.set_xticks(procs)
    c.set_xlabel("P (процессов)")
    c.set_ylabel("compute, с")
    c.set_title("Compute по процессам\n(красный — самый медленный, пунктир — среднее)", fontsize=11)
    c.grid(True, axis="y", alpha=0.3)

    fig.suptitle(f"Подсчёт треугольников, D-Galois, {graph}, по 1 потоку на процесс")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
