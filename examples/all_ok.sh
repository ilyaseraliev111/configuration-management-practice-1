#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m src.main --vfs examples/vfs/demo --script examples/stage4.txt --batch
python3 -m src.main --vfs examples/vfs/demo --script examples/stage5.txt --batch
