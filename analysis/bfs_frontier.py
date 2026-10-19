#!/usr/bin/env python3
"""Ширина фронта BFS по раундам из логов bfs-push-prof-dist.

usage: bfs_frontier.py <out.png|out.pdf> <prefix> [<prefix> ...]

Фронт раунда — сумма active (вершин, которые в этом раунде рассылали расстояние) по всем
процессам, рёбра — сумма edges. В режиме Sync с --delta=1 фронт от P не зависит, поэтому
годятся логи при любом P. Берётся прогон 0. Печатает сводку по каждому графу.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phase_report  # noqa: E402

NAMES = {"soc-LiveJournal1": "LiveJournal", "roadNet-PA": "roadNet-PA", "rgg_n_2_21_s0": "RGG $2^{21}$"}


def frontier(prefix):
    hosts = phase_report.load(prefix)
    n = sum(int(h["meta"]["masters"]) for h in hosts.values())
    rounds = {}
    for h in hosts.values():
        for r in h["rows"]:
            if r["run"] == "0":
                a = rounds.setdefault(int(r["round"]), [0, 0])
                a[0] += int(r["active"])
                a[1] += int(r["edges"])
    ks = sorted(rounds)
    return n, ks, [rounds[k][0] for k in ks], [rounds[k][1] for k in ks]


def main():
    out, prefixes = sys.argv[1], sys.argv[2:]
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.5))
    for prefix in prefixes:
        name = os.path.basename(prefix).rsplit("_p", 1)[0]
        n, ks, act, edges = frontier(prefix)
        label = NAMES.get(name, name)
        a.plot(ks, [100 * x / n for x in act], label=label)
        b.plot([100 * k / ks[-1] for k in ks], [100 * x / n for x in act], label=label)
        busy = sorted(act, reverse=True)
        print(f"{label}: вершин {n}, раундов {len(ks)}, фронт: макс {max(act)} ({100 * max(act) / n:.1f}%), "
              f"медиана {sorted(act)[len(act) // 2]} ({100 * sorted(act)[len(act) // 2] / n:.3f}%), "
              f"средний {sum(act) / len(act):.0f} ({100 * sum(act) / len(act) / n:.3f}%); "
              f"раундов с фронтом < 0.1% вершин: {sum(x < n / 1000 for x in act)}")
    for ax in (a, b):
        ax.set_yscale("log")
        ax.set_ylabel("фронт, % вершин графа")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()
    a.set_xlabel("раунд")
    a.set_title("Фронт BFS по раундам")
    b.set_xlabel("раунд, % от числа раундов")
    b.set_title("То же, ось раундов нормирована")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(out)


if __name__ == "__main__":
    main()
