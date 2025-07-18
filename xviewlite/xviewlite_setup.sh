#!/bin/bash

ENV_NAME="2025-2.2-py312-tiled"
ALIAS_NAME='xviewlite'
BASHRC='$HOME/.bashrc'
TAG_START="# ===== XViewLite Launcher ====="
TAG_END="# ===== END XViewLite Launcher ====="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XVIEWLITE_DIR="$SCRIPT_DIR"
XAS_DIR="$(realpath "$SCRIPT_DIR/..xas")"
XVIEW_SCRIPT="XVIEWLITE_DIR/xviewlite/xview.py"

if [ ! -f "$XVIEW_SCRIPT" ]; then
  echo "Launch script not found: $XVIEW_SCRIPT"
  exit 1
fi

if [ ! -d "$XAS_DIR"]; then
  echo "Expected 'xas' folder not found: $XAS_DIR"
  exit 1
fi

if grep -q "$TAG_START" "$BASHRC"; then
  echo "Alias '$ALIAS_NAME' already exists in $BASHRC."
  exit 0
fi

{
  echo ""
  echo "$TAG_START"
  echo "alias $ ALIAS_NAME='source \$(conda info --base)/etc/profile.d/conda.sh && \\"
  echo " export PYTHONPATH=\"\$PYTHONPATH:$XAS_DIR:$XVIEWLITE_DIR\" && \\"
  echo " python3 $XVIEW_SCRIPT'"
  echo "$TAG_END"
} >> "$BASHRC"

echo " Installed alias '$ALIAS_NAME' to $BASHRC"
echo " Run: source ~/.bashrc"
echo " Then: $ALIAS_NAME"

