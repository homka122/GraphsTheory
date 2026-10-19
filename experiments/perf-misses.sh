#!/usr/bin/env bash
# Счётчики промахов кэша (perf, Zen 3) на один прогон алгоритма при разных P.
# Каждая конфигурация запускается с --runs=1 и --runs=2; разность счётчиков — один прогон
# без чтения и разбиения графа. Счётчики — по каждому процессу (perf stat на каждом ранге).
# usage: [RUNS="1 2"] perf-misses.sh <bfs|pagerank> <graph> "<P list>"
# RUNS="1" — один прогон; загрузку графа тогда вычитает analysis/perf_misses.py по другому алгоритму.
# пример: perf-misses.sh pagerank soc-LiveJournal1 "1 6"
source "$(dirname "$0")/common.sh"
alg=$1; name=$2
EVENTS=cycles:u,instructions:u,ls_dmnd_fills_from_sys.lcl_l2:u,ls_dmnd_fills_from_sys.int_cache:u,ls_dmnd_fills_from_sys.mem_io_local:u
case $alg in
  bfs)      app=(bfs-push-dist --delta=1 --startNode=$(start_of "$name")) ;;
  pagerank) app=(pagerank-push-dist --maxIterations=100000000) ;;
  *) echo "unknown algorithm $alg" >&2; exit 1 ;;
esac
cd "$(out_dir perf-misses)"
for p in $3; do
  for runs in ${RUNS:-1 2}; do
    tag=${alg}_${name}_p${p}_runs$runs
    mpirun -n $p --map-by core --bind-to core sh -c \
      'exec perf stat -x, -e '"$EVENTS"' -o '"$tag"'.rank$OMPI_COMM_WORLD_RANK.perf "$@"' _ \
      "$BIN/${app[0]}" "$(graph_path "$name")" "${app[@]:1}" --exec=Sync -t=1 --runs=$runs \
      --statFile=$tag.stats > $tag.out 2>&1
    echo "$tag rc=$?"
  done
done
