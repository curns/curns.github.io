#!/bin/zsh

set -euo pipefail

cd -- "$(dirname -- "$0")"
/usr/bin/python3 ./sync_best_posts.py "$@"
