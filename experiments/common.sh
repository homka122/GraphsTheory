# Общие пути и окружение для экспериментов, подключать через source.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BIN=$ROOT/build/bin
DATA=$ROOT/dataset

# Привязку к ядрам делает mpirun (--bind-to core). Собственная привязка Galois
# сажает сетевой поток D-Galois на одно ядро с вычислительным, и всё замедляется в ~100 раз.
export GALOIS_DO_NOT_BIND_THREADS=1

# graph_path <name>: бинарный .gr графа из dataset/.
graph_path() { echo "$DATA/$1/$1.gr"; }

# sym_graph_path <name>: симметричная версия без петель и кратных рёбер (делает tc-prepare-graphs.sh).
sym_graph_path() { echo "$DATA/$1/$1.sym.gr"; }

# start_of <name>: стартовая вершина — максимальной степени, при равенстве с меньшим номером.
start_of() {
  case $1 in
    soc-LiveJournal1) echo 10009 ;;
    roadNet-PA)       echo 674502 ;;
    rgg_n_2_19_s0)    echo 125796 ;;
    rgg_n_2_20_s0)    echo 764285 ;;
    rgg_n_2_21_s0)    echo 1767915 ;;
    USA-road-d.NY)    echo 140960 ;;
    USA-road-d.FLA)   echo 316606 ;;
    USA-road-d.E)     echo 3300125 ;;
    USA-road-d.W)     echo 5901424 ;;
    *) echo "start_of: unknown graph $1" >&2; return 1 ;;
  esac
}

# out_dir <experiment>: каталог для логов, по умолчанию results/<experiment>, можно задать через OUT.
out_dir() {
  local d=${OUT:-$ROOT/results/$1}
  mkdir -p "$d" && echo "$d"
}

# stat <file.stats> <name> <HMAX|HSUM|...>: итоговое значение статистики Galois.
stat() { grep -E "$2, $3" "$1" | head -1 | awk -F', ' '{print $NF}'; }
