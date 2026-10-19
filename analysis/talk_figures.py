#!/usr/bin/env python3
"""Графики для презентации (talk/) из results/.

usage: talk_figures.py <out_dir>

Пишет в <out_dir> PDF:
  *_time.pdf       время T(P) по графам для каждого алгоритма (bfs, sssp, pr, tc);
  speedup.pdf      ускорение T(1)/T(P) всех четырёх алгоритмов;
  bfs_phases.pdf   BFS при P=6: доли фаз раунда (профилировщик);
  bfs_hosts.pdf    BFS при P=6: время по фазам на каждом процессе;
  bfs_frontier.pdf BFS: ширина фронта по раундам;
  bfs_phases_by_p.pdf BFS: время по фазам при P = 1…6;
  sssp_delta.pdf   SSSP на FLA и E: время от Δ;
  sssp.pdf         SSSP при P=6: доли фаз раунда на FLA и E (профилировщик);
  pr.pdf           PageRank при P=6: доли фаз раунда на LiveJournal, roadNet-PA и RGG (профилировщик);
  tc_hosts.pdf     подсчёт треугольников: время счёта по процессам при P=6;
  rf.pdf           RF (среднее число копий вершины) по P для каждого графа;
  cache_fills.pdf  откуда берутся данные при промахе L1 (perf) на LiveJournal при P=1 и P=6.
"""
import glob
import os
import re
import statistics
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches  # noqa: F401
import matplotlib.lines  # noqa: F401
import matplotlib.ticker  # noqa: F401
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bfs_frontier  # noqa: E402
import perf_misses  # noqa: E402
import phase_report  # noqa: E402
import pr_report  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "results")
PS = [1, 2, 3, 4, 5, 6]

plt.rcParams.update({
    "font.size": 13, "axes.titlesize": 14, "legend.fontsize": 11,
    "axes.grid": True, "grid.alpha": 0.3, "pdf.fonttype": 42,
})

NAMES = {
    "soc-LiveJournal1": "LiveJournal", "roadNet-PA": "roadNet-PA",
    "rgg_n_2_21_s0": "RGG $2^{21}$", "USA-road-d.FLA": "USA-FLA", "USA-road-d.E": "USA-E",
}
COLORS = {
    "soc-LiveJournal1": "#d62728", "roadNet-PA": "#1f77b4", "rgg_n_2_21_s0": "#2ca02c",
    "USA-road-d.FLA": "#1f77b4", "USA-road-d.E": "#ff7f0e",
}


def timers(stats):
    """Все Timer_N, HMAX из файла статистики Galois, мс."""
    text = open(stats).read()
    return [int(m.group(1)) for m in re.finditer(r"Timer_\d+, HMAX, (\d+)", text)]


def medians(pattern):
    """{P: медиана Timer_N} по файлам <...>_p<P>.stats."""
    out = {}
    for f in glob.glob(pattern):
        p = int(re.search(r"_p(\d+)\.stats$", f).group(1))
        ts = timers(f)
        if ts:
            out[p] = statistics.median(ts)
    return out


def sssp_summary(graph):
    """{(P, Δ): (время, раунды, работа)} по сводкам sssp-delta-sweep (грубая и мелкая сетки)."""
    out = {}
    line = re.compile(r"P=(\d+) delta=(\d+) .*time_med=(\d+) rounds=(\d+) work=(\d+)")
    for f in glob.glob(os.path.join(RES, "sssp-delta-sweep", f"{graph}*.summary")):
        for s in open(f):
            m = line.search(s)
            if m:
                p, d, t, r, w = map(int, m.groups())
                out[p, d] = (t, r, w)
    return out


def ideal(ax):
    ax.plot(PS, PS, "k--", lw=1, label="идеал")
    ax.set_xticks(PS)
    ax.set_xlabel("P, процессов")
    ax.set_ylim(0, 6.3)


def speedup_line(ax, t, graph):
    ps = [p for p in PS if p in t]
    sp = [t[1] / t[p] for p in ps]
    ax.plot(ps, sp, "o-", color=COLORS[graph], label=f"{NAMES[graph]}: {sp[-1]:.2f}")


def fig_speedup(out):
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.0), sharey=True)

    ax = axes[0]
    ideal(ax)
    for g in ["soc-LiveJournal1", "roadNet-PA", "rgg_n_2_21_s0"]:
        t = medians(os.path.join(RES, "bfs-scaling", f"{g}_p*.stats"))
        if 1 in t:
            speedup_line(ax, t, g)
    ax.set_title("BFS")
    ax.set_ylabel("ускорение $T(1)/T(P)$")

    ax = axes[1]
    ideal(ax)
    for g in ["USA-road-d.FLA", "USA-road-d.E"]:
        s = sssp_summary(g)
        t = {p: min(v[0] for (q, _), v in s.items() if q == p) for p in PS if any(q == p for q, _ in s)}
        if 1 in t:
            speedup_line(ax, t, g)
    ax.set_title("SSSP (лучшее Δ при каждом P)")

    ax = axes[2]
    ideal(ax)
    for g in ["soc-LiveJournal1", "roadNet-PA", "rgg_n_2_21_s0"]:
        t = medians(os.path.join(RES, "pagerank-scaling", f"{g}_p*.stats"))
        if 1 in t:
            speedup_line(ax, t, g)
    ax.set_title("PageRank")

    ax = axes[3]
    ideal(ax)
    for g in ["soc-LiveJournal1", "rgg_n_2_21_s0"]:
        t = medians(os.path.join(RES, "tc-scaling-20", f"{g}_p*.stats"))
        if 1 in t:
            speedup_line(ax, t, g)
    ax.set_title("Подсчёт треугольников")

    for ax in axes:
        ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def all_timers(pattern):
    """{P: [Timer_N, ...]} по файлам <...>_p<P>.stats."""
    out = {}
    for f in glob.glob(pattern):
        ts = timers(f)
        if ts:
            out[int(re.search(r"_p(\d+)\.stats$", f).group(1))] = ts
    return out


def sssp_best_timers(graph):
    """{P: [Timer_N, ...]} SSSP при лучшем для данного P значении Δ."""
    s = sssp_summary(graph)
    out = {}
    for p in PS:
        cand = [(v[0], d) for (q, d), v in s.items() if q == p]
        if cand:
            d = min(cand)[1]
            out[p] = timers(os.path.join(RES, "sssp-delta-sweep", f"{graph}_p{p}_d{d}.stats"))
    return out


def fig_time_block(out, series):
    """Время T(P) по графам: по панели на граф, медиана и min–max, пунктир — идеал T(1)/P."""
    fig, axes = plt.subplots(1, len(series), figsize=(4.3 * len(series), 3.9), squeeze=False)
    for ax, (g, t) in zip(axes[0], series):
        ps = sorted(t)
        med = [statistics.median(t[p]) / 1000 for p in ps]
        lo = [m - min(t[p]) / 1000 for m, p in zip(med, ps)]
        hi = [max(t[p]) / 1000 - m for m, p in zip(med, ps)]
        ax.errorbar(ps, med, yerr=[lo, hi], fmt="o-", color=COLORS[g], capsize=3, label="измерено")
        ax.plot(ps, [med[0] / p for p in ps], "k--", lw=1, label="идеал $T(1)/P$")
        for p, m in zip(ps, med):
            ax.annotate(f"{m:.2f}" if m < 10 else f"{m:.1f}", (p, m), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=10)
        ax.set_xticks(PS)
        ax.set_xlabel("P, процессов")
        ax.set_ylim(0, max(med) * 1.2)
        ax.set_title(NAMES[g])
    axes[0][0].set_ylabel("время, с")
    handles = [matplotlib.lines.Line2D([], [], color="gray", marker="o", label="медиана, отрезок — min и max"),
               matplotlib.lines.Line2D([], [], color="k", ls="--", lw=1, label="идеал $T(1)/P$")]
    fig.legend(handles=handles, ncol=2, loc="upper center", fontsize=11, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)
    plt.close(fig)


def fig_times(out_dir):
    fig_time_block(os.path.join(out_dir, "bfs_time.pdf"),
                   [(g, all_timers(os.path.join(RES, "bfs-scaling", f"{g}_p*.stats"))) for g in BFS_GRAPHS])
    fig_time_block(os.path.join(out_dir, "sssp_time.pdf"),
                   [(g, sssp_best_timers(g)) for g in ["USA-road-d.FLA", "USA-road-d.E"]])
    fig_time_block(os.path.join(out_dir, "pr_time.pdf"),
                   [(g, all_timers(os.path.join(RES, "pagerank-scaling", f"{g}_p*.stats"))) for g in BFS_GRAPHS])
    fig_time_block(os.path.join(out_dir, "tc_time.pdf"),
                   [(g, all_timers(os.path.join(RES, "tc-scaling-20", f"{g}_p*.stats")))
                    for g in ["soc-LiveJournal1", "rgg_n_2_21_s0"]])


BFS_CATS = [("useful", "полезная работа", "#2ca02c"), ("scan", "пустые проверки", "#bcbd22"),
            ("barrier", "ожидание счёта", "#d62728"), ("sync", "обмен (sync)", "#1f77b4"),
            ("syncwait", "ожидание sync", "#ff7f0e"), ("term", "Allreduce", "#9467bd")]
BFS_GRAPHS = ["soc-LiveJournal1", "roadNet-PA", "rgg_n_2_21_s0"]


def bfs_profile(g):
    """Время по фазам BFS при P=6 по процессам (медианный прогон профилировщика), мкс."""
    hosts = phase_report.load(os.path.join(RES, "bfs-phases-p6", f"{g}_p6"))
    run = phase_report.median_run(hosts)
    return hosts, phase_report.host_totals(hosts, run)


def stacked_legend(fig, cats, ncol=3):
    handles = [matplotlib.patches.Patch(color=c, label=n) for _, n, c in cats]
    fig.legend(handles=handles, ncol=ncol, loc="upper center", fontsize=11, frameon=False)


def fig_phase_shares(out, subdir, graphs):
    """Доли фаз раунда при P=6 по графам (профилировщик), горизонтальные столбцы."""
    fig, ax = plt.subplots(figsize=(11, 1.0 + 0.9 * len(graphs) + 0.6))
    for i, g in enumerate(graphs):
        hosts = phase_report.load(os.path.join(RES, subdir, f"{g}_p6"))
        tot = phase_report.host_totals(hosts, phase_report.median_run(hosts))
        mean = {k: statistics.mean(tot[h][k] for h in tot) for k, _, _ in BFS_CATS}
        total = sum(mean.values())
        left = 0.0
        for k, _, color in BFS_CATS:
            share = 100 * mean[k] / total
            ax.barh(i, share, left=left, color=color)
            if share >= 6:
                ax.text(left + share / 2, i, f"{share:.0f}%", ha="center", va="center", color="white",
                        fontsize=12, fontweight="bold")
            left += share
        ax.text(101, i, f"{total / 1000:.0f} мс", va="center", fontsize=12)
    ax.set_yticks(range(len(graphs)), [NAMES[g] for g in graphs])
    ax.invert_yaxis()
    ax.set_xlim(0, 113)
    ax.set_xlabel("доля времени процесса, %")
    ax.grid(False)
    stacked_legend(fig, BFS_CATS)
    fig.tight_layout(rect=(0, 0, 1, 0.8 if len(graphs) < 3 else 0.82))
    fig.savefig(out)
    plt.close(fig)


def fig_bfs_phases(out):
    fig_phase_shares(out, "bfs-phases-p6", BFS_GRAPHS)


def fig_bfs_hosts(out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.0))
    for ax, g in zip(axes, ["soc-LiveJournal1", "roadNet-PA"]):
        hosts, tot = bfs_profile(g)
        hs = sorted(tot)
        bottom = [0.0] * len(hs)
        for k, _, color in BFS_CATS:
            vals = [tot[h][k] / 1000 for h in hs]
            ax.bar(hs, vals, bottom=bottom, color=color)
            bottom = [x + y for x, y in zip(bottom, vals)]
        ax.set_xticks(hs, [f"{h}\n{int(hosts[h]['meta']['masters']) / 1e6:.2f} М" for h in hs], fontsize=11)
        ax.set_xlabel("процесс; мастеров на процессе")
        ax.set_ylabel("мс за прогон")
        ax.set_title(NAMES[g])
    stacked_legend(fig, BFS_CATS)
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    fig.savefig(out)
    plt.close(fig)


def fig_bfs_frontier(out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [1, 2]})
    for ax, graphs in zip(axes, [["soc-LiveJournal1"], ["roadNet-PA", "rgg_n_2_21_s0"]]):
        for g in graphs:
            n, ks, act, _ = bfs_frontier.frontier(os.path.join(RES, "bfs-phases-p6", f"{g}_p6"))
            ax.plot(ks, [100 * x / n for x in act], "o-" if len(ks) < 50 else "-", ms=4,
                    color=COLORS[g], label=f"{NAMES[g]}: {len(ks)} раундов")
        ax.set_yscale("log")
        ax.set_xlabel("раунд")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc="lower center")
    axes[0].set_ylabel("фронт, % вершин графа")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_bfs_phases_by_p(out):
    """BFS: время по фазам при P = 1…6, среднее по процессам, по панели на граф."""
    fig, axes = plt.subplots(1, len(BFS_GRAPHS), figsize=(13, 4.2))
    for ax, g in zip(axes, BFS_GRAPHS):
        ps = [p for p in PS if glob.glob(os.path.join(RES, "bfs-phases-p6", f"{g}_p{p}.host*.csv"))]
        bottom = [0.0] * len(ps)
        means = []
        for p in ps:
            hosts = phase_report.load(os.path.join(RES, "bfs-phases-p6", f"{g}_p{p}"))
            tot = phase_report.host_totals(hosts, phase_report.median_run(hosts))
            means.append({k: statistics.mean(tot[h][k] for h in tot) / 1000 for k, _, _ in BFS_CATS})
        for k, _, color in BFS_CATS:
            vals = [m[k] for m in means]
            ax.bar(ps, vals, bottom=bottom, color=color)
            bottom = [x + y for x, y in zip(bottom, vals)]
        for p, b in zip(ps, bottom):
            ax.text(p, b, f"{b:.0f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(ps)
        ax.set_xlabel("P, процессов")
        ax.set_title(NAMES[g])
        ax.set_ylim(0, max(bottom) * 1.12)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("мс, среднее по процессам")
    stacked_legend(fig, BFS_CATS, ncol=6)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)
    plt.close(fig)


def cache_fills_per_edge(alg, p, edges, graph="soc-LiveJournal1"):
    """Заполнения строк L1 из L2, L3 и DRAM на ребро за один прогон (perf, сумма по процессам).

    Если прогона с --runs=2 нет, загрузка графа вычитается по оценке из BFS на том же графе и P.
    """
    d = os.path.join(RES, "perf-misses")
    r1, r2 = perf_misses.ranks(d, alg, graph, p, 1), perf_misses.ranks(d, alg, graph, p, 2)
    if r2:
        one = [{k: b[k] - a[k] for k in a} for a, b in zip(r1, r2)]
    else:
        l1, l2 = perf_misses.ranks(d, "bfs", graph, p, 1), perf_misses.ranks(d, "bfs", graph, p, 2)
        load = [{k: 2 * a[k] - b[k] for k in a} for a, b in zip(l1, l2)]
        one = [{k: a[k] - c[k] for k in a} for a, c in zip(r1, load)]
    return {k: sum(x[k] for x in one) / edges for k in ("L2", "L3", "DRAM")}


def fig_cache_fills(out):
    data = {("PageRank", p): cache_fills_per_edge("pagerank", p, 4.30e9) for p in (1, 6)}
    data.update({("BFS", p): cache_fills_per_edge("bfs", p, 68175771) for p in (1, 6)})
    cols = {"L2": "#2ca02c", "L3": "#1f77b4", "DRAM": "#d62728"}
    names = {"L2": "из L2", "L3": "из L3 (общий на 6 ядер, 32 МБ)", "DRAM": "из памяти (DRAM)"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    for ax, alg in zip(axes, ["PageRank", "BFS"]):
        bottom = [0.0, 0.0]
        for k in ("L2", "L3", "DRAM"):
            v = [data[alg, 1][k], data[alg, 6][k]]
            ax.bar([0, 1], v, bottom=bottom, color=cols[k], width=0.55, label=names[k])
            for i in (0, 1):
                ax.text(i, bottom[i] + v[i] / 2, f"{v[i]:.2f}", ha="center", va="center", color="white",
                        fontweight="bold")
            bottom = [a + b for a, b in zip(bottom, v)]
        ax.set_xticks([0, 1], ["P = 1", "P = 6"])
        ax.set_ylabel("строк кэша на ребро")
        ax.set_title(f"{alg}, LiveJournal")
        ax.grid(axis="x", visible=False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="upper center", frameon=False, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out)
    plt.close(fig)


def fig_sssp_delta(out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.9))
    cmap = plt.get_cmap("viridis")
    for ax, g in zip(axes, ["USA-road-d.FLA", "USA-road-d.E"]):
        s = sssp_summary(g)
        for i, p in enumerate([1, 2, 4, 6]):
            ds = sorted(d for (q, d) in s if q == p and d)
            ys = [s[p, d][0] / 1000 for d in ds]
            ax.plot(ds, ys, "o-", ms=4, color=cmap(i / 3.5), label=f"P={p}")
            k = min(range(len(ds)), key=lambda j: ys[j])
            ax.plot(ds[k], ys[k], "o", ms=12, mfc="none", mec="red")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Δ (шаг порога расстояния)")
        ax.set_ylabel("время, с")
        ax.set_title(NAMES[g])
        xt = [500, 1000, 2000, 4000, 8000, 16000] if g == "USA-road-d.FLA" else [1000, 2000, 3000, 4000, 6000, 8000]
        yt = [0.5, 1, 2, 5, 10, 20] if g == "USA-road-d.FLA" else [15, 20, 30, 40, 50, 60]
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xticks(xt, [f"{v:g}" for v in xt])
        ax.set_yticks(yt, [f"{v:g}" for v in yt])
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_sssp(out):
    fig_phase_shares(out, "sssp-phases-p6", ["USA-road-d.FLA", "USA-road-d.E"])


def fig_pr(out):
    graphs = ["soc-LiveJournal1", "roadNet-PA", "rgg_n_2_21_s0"]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    for i, g in enumerate(graphs):
        metas, rounds = pr_report.analyse(os.path.join(RES, "pagerank-prof", f"{g}_p6_r1"))
        tot = pr_report.totals(rounds)
        total = sum(tot.values())
        left = 0.0
        for k, _, color in pr_report.CATS:
            share = 100 * tot[k] / total
            ax.barh(i, share, left=left, color=color)
            if share >= 6:
                ax.text(left + share / 2, i, f"{share:.0f}%", ha="center", va="center", color="white",
                        fontsize=12, fontweight="bold")
            left += share
        ax.text(101, i, f"{total / 1000:.0f} мс", va="center", fontsize=12)
    ax.set_yticks(range(len(graphs)), [NAMES[g] for g in graphs])
    ax.invert_yaxis()
    ax.set_xlim(0, 113)
    ax.set_xlabel("доля времени процесса, %")
    ax.grid(False)
    stacked_legend(fig, pr_report.CATS, ncol=4)
    fig.tight_layout(rect=(0, 0, 1, 0.82))
    fig.savefig(out)
    plt.close(fig)


def rf_of(stats):
    m = re.search(r"ReplicationFactor, HOST_0, ([\d.]+)", open(stats).read())
    return float(m.group(1)) if m else 1.0


def rf_table():
    """{граф: {P: RF}} при разбиении OEC (из логов BFS и SSSP)."""
    out = {}
    for g in BFS_GRAPHS:
        out[g] = {p: rf_of(os.path.join(RES, "bfs-scaling", f"{g}_p{p}.stats")) for p in PS}
    for g in ["USA-road-d.FLA", "USA-road-d.E"]:
        out[g] = {p: rf_of(sorted(glob.glob(os.path.join(RES, "sssp-delta-sweep", f"{g}_p{p}_d*.stats")))[0])
                  for p in PS}
    return out


def fig_rf(out):
    fig, ax = plt.subplots(figsize=(8, 4.0))
    for g, rf in rf_table().items():
        ax.plot(PS, [rf[p] for p in PS], "o-" if g != "USA-road-d.FLA" else "s--",
                color=COLORS[g] if g != "roadNet-PA" else "#17becf", label=f"{NAMES[g]}: {rf[6]:.2f}")
    ax.set_xticks(PS)
    ax.set_xlabel("P, процессов")
    ax.set_ylabel("RF")
    ax.set_ylim(0.9, 3.2)
    ax.legend(loc="upper left", fontsize=10, title="RF при P = 6", title_fontsize=10)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def host_values(stats, name):
    """Значения статистики по процессам (HostValues) для каждого прогона: [[h0, h1, ...], ...]."""
    out = []
    for line in open(stats):
        m = re.search(rf"{name}, Time, HostValues, (.*)$", line)
        if m:
            out.append([int(x) for x in m.group(1).split(";")])
    return out


def fig_tc_hosts(out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4), sharey=False)
    for ax, g in zip(axes, ["soc-LiveJournal1", "rgg_n_2_21_s0"]):
        stats = os.path.join(RES, "tc-scaling-20", f"{g}_p6.stats")
        vals = []
        for i in range(20):
            hv = host_values(stats, f"TC_{i}")
            if hv:
                vals.append(hv[0])
        per_host = [statistics.median(v[h] for v in vals) / 1000 for h in range(6)]
        mean = statistics.mean(per_host)
        ax.bar(range(6), per_host, color=COLORS[g])
        ax.axhline(mean, color="k", ls="--", lw=1, label=f"среднее; max/среднее = {max(per_host) / mean:.2f}")
        ax.set_xticks(range(6))
        ax.set_xlabel("процесс")
        ax.set_ylabel("время счёта, с")
        ax.set_title(f"{NAMES[g]}, P=6")
        ax.set_ylim(0, max(per_host) * 1.3)
        ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    fig_times(out)
    fig_speedup(os.path.join(out, "speedup.pdf"))
    fig_bfs_phases(os.path.join(out, "bfs_phases.pdf"))
    fig_bfs_hosts(os.path.join(out, "bfs_hosts.pdf"))
    fig_bfs_frontier(os.path.join(out, "bfs_frontier.pdf"))
    fig_bfs_phases_by_p(os.path.join(out, "bfs_phases_by_p.pdf"))
    fig_sssp_delta(os.path.join(out, "sssp_delta.pdf"))
    fig_sssp(os.path.join(out, "sssp.pdf"))
    fig_pr(os.path.join(out, "pr.pdf"))
    fig_tc_hosts(os.path.join(out, "tc_hosts.pdf"))
    fig_rf(os.path.join(out, "rf.pdf"))
    fig_cache_fills(os.path.join(out, "cache_fills.pdf"))
    print(out)


if __name__ == "__main__":
    main()
