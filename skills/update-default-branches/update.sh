#!/usr/bin/env bash
set -uo pipefail

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -o BatchMode=yes"

update_repo() {
  local repo=${1%/.git}
  local remote remotes url branch current before after out
  remotes=$(git -C "$repo" remote)
  if [[ $'\n'$remotes$'\n' == *$'\n'origin$'\n'* ]]; then
    remote=origin
  elif [[ -n $remotes && $remotes != *$'\n'* ]]; then
    remote=$remotes
  else
    printf 'SKIP\t%s\tno origin and not exactly one remote: %s\n' "$repo" "${remotes//$'\n'/ }"; return
  fi
  url=$(git -C "$repo" remote get-url "$remote")
  [[ $url == *github.com* ]] || { printf 'SKIP\t%s\t%s is not on github: %s\n' "$repo" "$remote" "$url"; return; }

  branch=$(git -C "$repo" symbolic-ref --short -q "refs/remotes/$remote/HEAD")
  if [[ -z $branch ]]; then
    git -C "$repo" remote set-head "$remote" --auto >/dev/null 2>&1
    branch=$(git -C "$repo" symbolic-ref --short -q "refs/remotes/$remote/HEAD")
  fi
  branch=${branch#"$remote"/}
  [[ -n $branch ]] || { printf 'FAIL\t%s\tcannot resolve default branch of %s\n' "$repo" "$remote"; return; }

  out=$(git -C "$repo" fetch -q "$remote" "$branch" 2>&1) || { printf 'FAIL\t%s\tfetch %s: %s\n' "$repo" "$branch" "${out##*$'\n'}"; return; }

  before=$(git -C "$repo" rev-parse -q --verify "refs/heads/$branch")
  [[ -n $before ]] || { printf 'NOLOCAL\t%s\t%s: no local branch, %s/%s fetched\n' "$repo" "$branch" "$remote" "$branch"; return; }

  current=$(git -C "$repo" symbolic-ref --short -q HEAD)
  if [[ $current == "$branch" ]]; then
    out=$(git -C "$repo" merge -q --ff-only "$remote/$branch" 2>&1)
  else
    out=$(git -C "$repo" fetch -q "$remote" "$branch:$branch" 2>&1)
  fi
  [[ $? -eq 0 ]] || { printf 'FAIL\t%s\t%s: %s\n' "$repo" "$branch" "${out##*$'\n'}"; return; }

  after=$(git -C "$repo" rev-parse "refs/heads/$branch")
  if [[ $before == "$after" ]]; then
    printf 'UP-TO-DATE\t%s\t%s\n' "$repo" "$branch"
  else
    printf 'UPDATED\t%s\t%s: %s..%s, %s commits\n' "$repo" "$branch" "${before:0:7}" "${after:0:7}" "$(git -C "$repo" rev-list --count "$before..$after")"
  fi
}
export -f update_repo

depth=3
root=.
while [[ $# -gt 0 ]]; do
  case $1 in
    --depth) depth=$2; shift 2 ;;
    *) root=$1; shift ;;
  esac
done
[[ $depth =~ ^[0-9]+$ ]] || { echo "--depth needs a non-negative integer, got: $depth" >&2; exit 2; }

# The .git dir sits one level below its repo, so a repo at depth N has .git at N+1.
find "$root" -maxdepth $((depth + 1)) \( -name node_modules -o -name target -o -name .venv \) -prune -o -type d -name .git -print0 -prune \
  | xargs -0 -P 8 -I{} bash -c 'update_repo "$1"' _ {} \
  | sort
