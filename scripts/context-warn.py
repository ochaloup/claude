#!/usr/bin/env python3
import json, os, sys

THRESHOLDS = (200_000, 400_000, 600_000)
STATE_DIR = '/tmp/claude-context-warn'


def last_context(path):
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 4_000_000))
        lines = f.read().decode('utf-8', 'replace').splitlines()
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('type') != 'assistant' or r.get('isSidechain'):
            continue
        u = (r.get('message') or {}).get('usage') or {}
        return u.get('input_tokens', 0) + u.get('cache_read_input_tokens', 0) + u.get('cache_creation_input_tokens', 0)
    return 0


def main():
    data = json.load(sys.stdin)
    path, sid = data.get('transcript_path'), data.get('session_id', 'unknown')
    if not path or not os.path.exists(path):
        return
    ctx = last_context(path)
    os.makedirs(STATE_DIR, exist_ok=True)
    state = os.path.join(STATE_DIR, sid)
    try:
        warned = int(open(state).read())
    except (OSError, ValueError):
        warned = 0
    crossed = max((t for t in THRESHOLDS if ctx >= t), default=0)
    if crossed < warned:
        warned = crossed
    if crossed > warned:
        print(json.dumps({'systemMessage': f'Context is {ctx // 1000}K tokens; every turn re-reads all of it. Task done? /save-plan, then /clear.'}))
        warned = crossed
    with open(state, 'w') as f:
        f.write(str(warned))


if __name__ == '__main__':
    main()
