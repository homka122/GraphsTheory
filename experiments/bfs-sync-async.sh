#!/usr/bin/env bash
# BFS push при delta=1: BSP (Sync) против BASP (Async), время и раскрытые рёбра по процессам.
# usage: bfs-sync-async.sh "<graph list>" "<P list>"
# пример: bfs-sync-async.sh "soc-LiveJournal1 roadNet-PA" "3 6"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
cd "$(out_dir bfs-sync-async)"
for name in $1; do
  start=$(start_of "$name") || exit 1
  for p in $2; do
    for ex in Sync Async; do
      tag=${name}_p${p}_$ex
      timeout 600 mpirun -n $p --map-by core --bind-to core $BIN/bfs-push-dist \
        "$(graph_path "$name")" --exec=$ex --delta=1 --startNode=$start -t=1 --runs=3 \
        --statFile=$tag.stats > $tag.out 2>&1
      echo "$name P=$p $ex rc=$? $(grep -h 'Max distance' $tag.out | sort -u | tr '\n' ' ')"
    done
  done
done
