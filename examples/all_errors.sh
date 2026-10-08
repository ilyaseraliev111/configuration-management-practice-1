#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for script in examples/errors/*.txt; do
  if python3 -m src.main --vfs examples/vfs/demo --script "$script" --batch; then
    echo "Ожидалась ошибка: $script"
    exit 1
  fi
done
