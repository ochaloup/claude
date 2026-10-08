---
name: update-default-branches
description: Find every GitHub repository under a directory, up to 3 levels deep by default (--depth N to change), and fast-forward each one's default branch (main/master, read from origin, or from the only remote when there is no origin) to the remote. Runs one script that updates up to 8 repos in parallel — no agents. Never switches branches, stashes, resets or merges anything that is not a fast-forward; anything else is reported, not fixed.
when_to_use: the user wants the local main/master of many checked-out repos brought up to date with GitHub in one go
argument-hint: "[--depth <n>] [<dir>]"
model: haiku
---

# Update default branches

Arguments: $ARGUMENTS

Run, as one bash call, passing the arguments through unchanged. The directory
defaults to the current one; `--depth` counts repo levels below it (0 = the
directory itself) and defaults to 3.

```
bash ~/.claude/skills/update-default-branches/update.sh [--depth <n>] [<dir>]
```

Each output line is `STATUS<TAB>repo<TAB>detail`:

- `UPDATED` — fast-forwarded. Checked out or not, the working tree is never switched.
- `UP-TO-DATE` — nothing to do.
- `NOLOCAL` — no local default branch; only `<remote>/<branch>` was fetched.
- `FAIL` — fetch failed, the branch diverged, or local changes block the fast-forward.
- `SKIP` — no `origin` and not exactly one remote, or the remote is not on GitHub.

Do not fix a `FAIL`. Diverged branches and dirty trees are the user's call — never
stash, reset, rebase or check out to get past one.

## Output

1. One bold line: `<u> updated, <n> up to date, <f> failed, <s> skipped` and the directory.
2. Every `UPDATED` line: repo, branch, commit count.
3. Every `FAIL` line with its reason.
4. `NOLOCAL` and `SKIP` only as counts, unless the user asks for them.
