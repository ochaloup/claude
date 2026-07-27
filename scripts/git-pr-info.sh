#!/bin/bash
BRANCH=$(git branch --show-current)

# Try to get remote from tracking branch of main/master
REMOTE=$(git for-each-ref --format='%(upstream:remotename)' refs/heads/main refs/heads/master 2>/dev/null | grep -v '^$' | head -1)

# Fallback: use 'origin' if nothing found, or list remotes and pick first
if [ -z "$REMOTE" ]; then
  REMOTE=$(git remote | head -1)
fi

if [ -z "$REMOTE" ]; then
  echo "ERROR: no remote found" >&2
  exit 1
fi

OWNER_REPO=$(git remote get-url "$REMOTE" | sed 's|.*github\.com[:/]\(.*\)\.git$|\1|; s|.*github\.com[:/]\(.*\)$|\1|')

echo "BRANCH=$BRANCH"
echo "REMOTE=$REMOTE"
echo "OWNER_REPO=$OWNER_REPO"
