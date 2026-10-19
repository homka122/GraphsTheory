#!/usr/bin/env bash
# Сколько раундов BFS push делает на RGG: проверка, что запуски не упираются в maxIterations (1000).
# usage: bfs-rgg-rounds.sh
source "$(dirname "$0")/common.sh"
cd "$(out_dir bfs-rgg-rounds)"
for spec in "rgg_n_2_19_s0 1" "rgg_n_2_20_s0 2" "rgg_n_2_21_s0 4"; do
  read name p <<< "$spec"
  mpirun -n $p --map-by core --bind-to core $BIN/bfs-push-dist \
    "$(graph_path "$name")" --exec=Sync --delta=1 --startNode=$(start_of "$name") -t=1 --runs=1 \
    --statFile=$name.stats > $name.out 2>&1
  echo "$name P=$p rounds=$(stat $name.stats NumIterations_0 HMAX)" \
    "$(grep -h -E 'visited|Max distance' $name.out | sort -u | tr '\n' ' ')"
done
