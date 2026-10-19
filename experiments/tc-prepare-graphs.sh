#!/usr/bin/env bash
# Графы для подсчёта треугольников: симметричные, без петель и кратных рёбер.
# Из dataset/<g>/<g>.gr делает dataset/<g>/<g>.sym.gr и проверяет результат.
# usage: tc-prepare-graphs.sh "<graph list>"
# пример: tc-prepare-graphs.sh "soc-LiveJournal1 roadNet-PA rgg_n_2_20_s0"
source "$(dirname "$0")/common.sh"
for name in $1; do
  src=$(graph_path "$name"); dst=$(sym_graph_path "$name"); tmp=$dst.tmp
  # gr2sgr добавляет обратные рёбра (у уже симметричного графа появятся дубли), gr2cgr убирает петли и дубли.
  $BIN/graph-convert --gr2sgr "$src" "$tmp" > /dev/null &&
    $BIN/graph-convert --gr2cgr "$tmp" "$dst" > /dev/null || exit
  rm -f "$tmp"
  python3 -I "$ROOT/analysis/gr_check.py" "$dst" || exit
done
