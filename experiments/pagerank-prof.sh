#!/usr/bin/env bash
# PageRank push по фазам раунда: время, полезные и пустые вершины по раундам и процессам.
# Каждый прогон — отдельный mpirun; после каждого перерисовывается results/pagerank-prof/index.html.
# usage: [RUNS=5] pagerank-prof.sh "<graph list>" "<P list>"
# пример: RUNS=5 pagerank-prof.sh soc-LiveJournal1 "1 2 3 4 5 6"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
runs=${RUNS:-5}
dir=$(out_dir pagerank-prof)
cd "$dir"
for name in $1; do
  for p in $2; do
    for r in $(seq 1 $runs); do
      tag=${name}_p${p}_r$r
      timeout 3600 mpirun -n $p --map-by core --bind-to core $BIN/pagerank-push-prof-dist \
        "$(graph_path "$name")" -t=1 --exec=Sync --maxIterations=100000000 --runs=1 \
        --statFile=$tag.stats --phaseLog=$tag > $tag.out 2>&1
      rc=$?
      echo "$name P=$p run=$r rc=$rc time=$(stat $tag.stats Timer_0 HMAX)" \
        "rounds=$(grep -h 'NumIterations_0' $tag.stats | awk -F', ' '{print $NF}' | head -1)"
      nice -n 19 python3 "$ROOT/analysis/pr_report.py" "$dir" "$name" > /dev/null
    done
  done
done
