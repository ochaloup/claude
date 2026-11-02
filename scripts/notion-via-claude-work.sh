#!/bin/bash
WORK_DIR="$HOME/.claude-work"

if [ "$CLAUDE_CONFIG_DIR" = "$WORK_DIR" ]; then
  echo "ERROR: already running as claude-work, no other account to fall back to" >&2
  exit 1
fi

if [ ! -f "$1" ]; then
  echo "ERROR: usage: notion-via-claude-work.sh <prompt-file>" >&2
  exit 1
fi

CLAUDE_CONFIG_DIR="$WORK_DIR" exec claude -p --model sonnet --allowedTools 'mcp__notion__*' 'mcp__claude_ai_Notion__*' 'Read' < "$1"
