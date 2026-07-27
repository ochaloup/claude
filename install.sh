#!/bin/bash
set -e

if [[ "$1" == '-h' || "$1" == '--help' || "$1" == 'help' ]]; then
  echo 'For redefinition of the target dir use env variable $OUT_DIR'
  echo "  OUT_DIR=dir ${BASH_SOURCE[0]}"
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$HOME/.claude}"

mkdir -p "$OUT_DIR"

# it seems that regardless of how the CLAUDE_CONFIG_DIR is configured, the CLAUDE.md from ~/.claude is always run
# check the output of /context clear
# ln -sf "$SCRIPT_DIR/CLAUDE.md" "$OUT_DIR/"

# To get the configured the mcp server github go to ~/.claude.json
# "mcpServers": {
#   "github": {
#     "type": "stdio",
#     "command": "npx",
#     "args": [
#       "-y",
#       "@modelcontextprotocol/server-github"
#     ],
#     "env": {
#       "GITHUB_PERSONAL_ACCESS_TOKEN": "gh auth token"
#     }
#   }
# }

ln -sf "$SCRIPT_DIR/skills" "$OUT_DIR/"
ln -sf "$SCRIPT_DIR/commands" "$OUT_DIR/"
ln -sf "$SCRIPT_DIR/scripts" "$OUT_DIR/"
ln -sf "$SCRIPT_DIR/settings.json" "$OUT_DIR/"

# Later running a different claude code dir with
# alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'


echo "Claude config linked from $SCRIPT_DIR to $OUT_DIR"
