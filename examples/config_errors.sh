#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if python3 -m src.main --vfs examples/vfs/demo --script examples/error.txt --batch; then
  exit 1
fi
if python3 -m src.main --vfs examples/vfs/demo --script missing.txt --batch; then
  exit 1
fi
