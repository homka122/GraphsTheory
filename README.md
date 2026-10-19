# Масштабируемость распределённого Galois (D-Galois)

Блок 2 «Распределённая обработка графов»: сильная масштабируемость BFS, SSSP, PageRank и подсчёта
треугольников (TC) в [D-Galois](https://github.com/IntelligentSoftwareSystems/Galois/tree/master/lonestar/analytics/distributed)
по числу процессов P = 1…6. Презентация — `talk/talk.pdf`.

```
deps/Galois/    апстрим Galois (git submodule, без наших правок)
patches/        правки апстрима для GCC 15, накатываются автоматически при cmake
src/bfsprof/    профилировщик фаз BFS push (bfs-push-prof-dist)
src/prprof/     профилировщик фаз PageRank push (pagerank-push-prof-dist)
src/ssspprof/   профилировщик фаз SSSP push (sssp-push-prof-dist)
experiments/    скрипты запусков; пути и стартовые вершины — в common.sh
analysis/       обработка логов и графики
results/        логи и .stats запусков, по каталогу на эксперимент
notes/          заметки по алгоритмам и результатам
talk/           презентация (шаблон spbu-se/matmex-diploma-template)
dataset/        графы, в git не хранятся
```

## Сборка

Нужны CMake ≥ 3.13, GCC, Boost, LLVM, Open MPI, Python 3 с matplotlib и numpy.

```sh
git submodule update --init deps/Galois
cmake -S . -B build
make -C build -j12
```

Бинарники — в `build/bin`: немодифицированные `bfs-push-dist`, `sssp-push-dist`, `pagerank-push-dist`,
`triangle-counting-dist` и др. (по ним меряется время), профилировщики `bfs-push-prof-dist`,
`sssp-push-prof-dist`, `pagerank-push-prof-dist` (собираются с теми же флагами, что и оригиналы) и `graph-convert`.

Проверка сборки: `experiments/smoke-test.sh` — BFS и PageRank на решётке 20×20 при P=2.

## Графы

Кладутся в `dataset/<имя>/<имя>.gr` (бинарный формат Galois, `graph-convert`):

| граф | откуда |
|---|---|
| soc-LiveJournal1, roadNet-PA | [SNAP](https://snap.stanford.edu/data/) |
| rgg_n_2_21_s0 | [SuiteSparse](https://sparse.tamu.edu/DIMACS10/rgg_n_2_21_s0) |
| USA-road-d.FLA, USA-road-d.E | [9th DIMACS Challenge](http://www.diag.uniroma1.it/challenge9/download.shtml) |

Для TC нужны симметричные графы без петель и кратных рёбер: `experiments/tc-prepare-graphs.sh "<графы>"`.

## Эксперименты

Все запуски: P MPI-процессов по одному потоку, каждый на своём ядре
(`GALOIS_DO_NOT_BIND_THREADS=1 mpirun -n P --map-by core --bind-to core`), `--exec=Sync`, разбиение OEC.
Время — `Timer_N` из `.stats`, медиана нескольких прогонов.

| что | скрипт | результаты |
|---|---|---|
| BFS: время по P | `RUNS=5 experiments/bfs-scaling.sh "soc-LiveJournal1 roadNet-PA rgg_n_2_21_s0" "1 2 3 4 5 6"` | `results/bfs-scaling/` |
| BFS: фазы раунда при P=1…6 | `bfs-push-prof-dist ... --runs=5 --phaseLog=<префикс>`, `analysis/phase_report.py` | `results/bfs-phases-p6/` |
| BFS: ширина фронта по раундам | `analysis/bfs_frontier.py <out.png> results/bfs-phases-p6/<граф>_p6 ...` | `results/bfs-phases-p6/` |
| BFS: Sync против Async | `experiments/bfs-sync-async.sh "<графы>" "3 6"` | `results/bfs-sync-async/` |
| SSSP: перебор Δ × P | `[RUNS=3] experiments/sssp-delta-sweep.sh USA-road-d.FLA "1 2 3 4 5 6" "<Δ>"` | `results/sssp-delta-sweep/` |
| SSSP: фазы раунда при P=1 и P=6 | `sssp-push-prof-dist ... --delta=<Δ> --phaseLog=<префикс>`, `analysis/phase_report.py` | `results/sssp-phases-p6/` |
| PageRank: время по P | `RUNS=5 experiments/pagerank-scaling.sh "<графы>" "1 2 3 4 5 6"` | `results/pagerank-scaling/` |
| PageRank: фазы раунда | `RUNS=1 experiments/pagerank-prof.sh soc-LiveJournal1 "1 2 3 4 5 6"`, `analysis/pr_report.py` | `results/pagerank-prof/` |
| PageRank: цена ребра по блокам при P=1 | `pagerank-push-prof-dist ... --pushBlocks=<границы>` | `results/pagerank-blocks/` |
| Промахи кэша (perf) | `[RUNS="1 2"] experiments/perf-misses.sh pagerank soc-LiveJournal1 "1 6"` (или `bfs`), `analysis/perf_misses.py` | `results/perf-misses/` |
| TC: время по P | `RUNS=20 experiments/tc-scaling.sh "soc-LiveJournal1 rgg_n_2_21_s0" "1 2 3 4 5 6"` | `results/tc-scaling-20/` |

Логи пишутся в `results/<эксперимент>/`, другой каталог — через `OUT=<каталог>`.

## Презентация

```sh
cd talk
make figures   # графики из results/ (analysis/talk_figures.py)
make           # talk.pdf, нужен XeLaTeX и шрифты CMU
```
