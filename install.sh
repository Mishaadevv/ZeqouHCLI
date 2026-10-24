#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"
python3 -m pip install --user --upgrade .
printf '\nZeqou Harness CLI installed. From a project directory, run: python3 -m zeqouhcli\n'
