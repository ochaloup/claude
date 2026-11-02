#!/usr/bin/env python3
"""Watch SIMD feature gates and SIMD PRs; report changes as a Notion comment on GEN-9543 via claude-work."""
import base64, json, os, struct, subprocess, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

TASK_URL = "https://app.notion.com/p/409e465715a4817f955de5a6c6d415e1"
USER = "user://144e986a-db1a-4872-9b87-0efad80cd2e4"
GATES = {
    "SIMD-0123 block revenue sharing": "Crbnc267wkJvFhYakqwWWX57sx5bkrftJLekzy6yWKLT",
    "SIMD-0550 double disinflation": "ddibiks7RHZR69QXYMCmk4EZNt6WckspTqEEWv6cS38",
    "SIMD-0437-3 rent 2575": "rntCigrTppP5JdZz7K8TyN9sMzLdAcXp8SejYpVpX6D",
    "SIMD-0437-4 rent 1322": "rntD7invRBswCAdKtRsh1G4psKjrPdS3BKqtnA78C7N",
    "SIMD-0437-5 rent 696": "rntTjNZ9boq8owDxjGVFHPfWNQPDaKiM5JcjxmDGg47",
}
SIMD_PRS = {"SIMD-0677 commission history": 677, "SIMD-0511 on-chain epoch stakes": 676}
RPC = {"testnet": "https://api.testnet.solana.com", "mainnet": "https://api.mainnet-beta.solana.com"}
STATE_DIR = Path.home() / ".claude-work" / "simd-gate-watch"
STATE = STATE_DIR / "state.json"
LOG = STATE_DIR / "watch.log"
HEADERS = {"Content-Type": "application/json", "User-Agent": "curl/8.5.0"}


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, body, HEADERS), timeout=60) as r:
        return json.load(r)["result"]


def gate_status(url):
    keys = list(GATES.values())
    accounts = rpc(url, "getMultipleAccounts", [keys, {"encoding": "base64"}])["value"]
    epoch = rpc(url, "getEpochInfo", [])["epoch"]
    out = {}
    for name, acc in zip(GATES, accounts):
        if acc is None:
            out[name] = "not-submitted"
            continue
        raw = base64.b64decode(acc["data"][0])
        if raw and raw[0] == 1:
            out[name] = f"active@slot {struct.unpack('<Q', raw[1:9])[0]}"
        else:
            out[name] = f"pending (activates at epoch {epoch + 1} boundary)"
    return out


def pr_status(number):
    url = f"https://api.github.com/repos/solana-foundation/solana-improvement-documents/pulls/{number}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        pr = json.load(r)
    return "merged" if pr.get("merged_at") else pr["state"]


def kind(status):
    return status.split(" ")[0].split("@")[0]


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    old = json.loads(STATE.read_text()) if STATE.exists() else {}
    new = {f"{c}: {n}": s for c, u in RPC.items() for n, s in gate_status(u).items()}
    new.update({f"github: {n}": pr_status(p) for n, p in SIMD_PRS.items()})
    prev = {k: old.get(k, "open" if k.startswith("github") else "not-submitted") for k in new}
    changes = [(k, prev[k], v) for k, v in new.items() if kind(v) != kind(prev[k])]
    STATE.write_text(json.dumps(new, indent=1))
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG.open("a") as f:
        f.write(f"{stamp} changes={len(changes)} {json.dumps(new)}\n")
    if not changes:
        return
    lines = "\n".join(f"- {k}: {a} → {b}" for k, a, b in changes)
    comment = (f"🤖 claude: SIMD gate watch {stamp[:10]} — status changed, action needed <mention url=\"{USER}\" />:\n{lines}\n"
               "Testnet pending → plan the work. Testnet active → verify on testnet. Mainnet pending → deploy before activation.")
    prompt = (f"Call mcp__claude_ai_Notion__notion-create-comment with page_id {TASK_URL} and markdown set to the "
              f"exact text below. On success print `OK <comment id>` and nothing else.\n\n{comment}")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(Path.home() / ".claude-work"))
    res = subprocess.run([str(Path.home() / ".local/bin/claude"), "-p", prompt, "--model", "sonnet",
                          "--allowedTools", "mcp__claude_ai_Notion__notion-create-comment"],
                         text=True, capture_output=True, env=env, timeout=600)
    with LOG.open("a") as f:
        f.write(f"{stamp} notion rc={res.returncode} out={res.stdout.strip()} err={res.stderr.strip()}\n")
    if res.returncode != 0 or not res.stdout.strip().startswith("OK "):
        STATE.write_text(json.dumps(old, indent=1))
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
