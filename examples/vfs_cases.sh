#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for source in minimal several demo; do
  python3 -m src.main --vfs "examples/vfs/$source" --batch
done
if python3 -m src.main --vfs missing --batch; then exit 1; fi
if python3 -m src.main --vfs examples/error.txt --batch; then exit 1; fi
