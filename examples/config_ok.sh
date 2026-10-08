#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m src.main --vfs examples/vfs/demo --batch
python3 -m src.main --vfs examples/vfs/demo --script examples/stage2.txt --batch
