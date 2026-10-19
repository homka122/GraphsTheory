#!/usr/bin/env bash
# Фазы раундов BFS push (BSP, delta=1): профилировщик и сводка phase_report.py.
# usage: bfs-phases.sh <graph> <P> [runs]
# пример: bfs-phases.sh soc-LiveJournal1 6 5
source "$(dirname "$0")/common.sh"
name=$1; p=$2; runs=${3:-5}
start=$(start_of "$name") || exit 1
cd "$(out_dir bfs-phases)"
tag=${name}_p${p}
mpirun -n $p --map-by core --bind-to core $BIN/bfs-push-prof-dist \
  "$(graph_path "$name")" --exec=Sync --delta=1 --startNode=$start -t=1 --runs=$runs \
  --phaseLog=$tag --statFile=$tag.stats > $tag.out 2>&1 || exit
python3 -I "$ROOT/analysis/phase_report.py" "$tag"
