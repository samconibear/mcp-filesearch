#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PYTHON="${VENV_DIR}/bin/python"

echo "Setting up file-search-mcp from: $REPO_DIR"

# --- find a Python >= 3.10 ---
find_python() {
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if cmd="$(command -v "$candidate" 2>/dev/null)"; then
      ver=$("$cmd" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null)
      if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        echo "$cmd"; return 0
      fi
    fi
  done
  return 1
}

BASE_PYTHON="$(find_python)" || {
  echo "Error: Python 3.10 or newer is required but was not found on PATH." >&2
  echo "Install it (e.g. brew install python@3.12) and re-run this script." >&2
  exit 1
}
echo "Using $BASE_PYTHON ($("$BASE_PYTHON" --version))"

# Setup virtual env
if [ ! -d "$VENV_DIR" ]; then
  "$BASE_PYTHON" -m venv "$VENV_DIR"
  echo "Created venv at $VENV_DIR"
fi

"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet mcp
echo "Dependencies installed."

# modify claude_desktop_config.json
if [ "$(uname)" = "Darwin" ]; then
  CONFIG_DIR="$HOME/Library/Application Support/Claude"
else
  CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude"
fi
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

mkdir -p "$CONFIG_DIR"

NEW_ENTRY="{\"command\":\"$PYTHON\",\"args\":[\"$REPO_DIR/src/main.py\",\"$HOME/\"]}"

if [ ! -f "$CONFIG_FILE" ]; then
  printf '{\n  "mcpServers": {\n    "file-search": %s\n  }\n}\n' "$NEW_ENTRY" > "$CONFIG_FILE"
  echo "Created $CONFIG_FILE"
elif command -v jq &>/dev/null; then
  tmp="$(mktemp)"
  jq --argjson entry "$NEW_ENTRY" '.mcpServers["file-search"] = $entry' "$CONFIG_FILE" > "$tmp"
  mv "$tmp" "$CONFIG_FILE"
  echo "Updated $CONFIG_FILE (via jq)"
else
  content="$(cat "$CONFIG_FILE")"
  BLOCK="\"file-search\": $NEW_ENTRY"
  if printf '%s' "$content" | grep -q '"file-search"'; then
    content="$(printf '%s' "$content" | sed 's|"file-search"[[:space:]]*:[[:space:]]*{[^}]*}|'"$BLOCK"'|')"
  elif printf '%s' "$content" | grep -q '"mcpServers"'; then
    content="$(printf '%s' "$content" | sed 's|"mcpServers"[[:space:]]*:[[:space:]]*{|\0'"$BLOCK"',|')"
  else
    content="$(printf '%s' "$content" | sed 's|}[[:space:]]*$|,\n  "mcpServers": {'"$BLOCK"'}\n}|')"
  fi
  printf '%s\n' "$content" > "$CONFIG_FILE"
  echo "Updated $CONFIG_FILE (via sed)"
fi

echo
echo "Done. Restart Claude Desktop to pick up the new MCP server."
