#!/bin/sh
# Builds this folder with the environment's build.py: ./build.sh, or ./build.sh debug.
exec python3 "$(dirname "$0")/../build.py" "$(dirname "$0")" "$@"
