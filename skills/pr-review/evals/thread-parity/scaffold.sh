#!/usr/bin/env bash
set -euo pipefail

long_body() {
  printf 'The retry path here worries me. '
  for _ in $(seq 1 40); do
    printf 'When the upstream call times out the counter is reset by the caller, so the backoff never grows past the first attempt and we hammer the service. '
  done
  printf 'Concretely: move the counter into the caller so it survives across attempts. TAILMARK7Q4.'
}

cat > feedback.json <<JSON
{
  "data": { "repository": { "pullRequest": {
    "title": "Add bond settlement claim path",
    "url": "https://github.com/marinade-finance/example/pull/412",
    "reviewThreads": { "nodes": [
      {"id": "RT_res_1", "isResolved": true, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_r1", "body": "Rename this to settlementClaim.", "path": "src/claim.rs", "line": 12, "originalLine": 12, "author": {"login": "reviewer-a"}, "url": "u/1"}]}},
      {"id": "RT_unres_alpha", "isResolved": false, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_a1", "body": "$(long_body)", "path": "src/claim.rs", "line": 48, "originalLine": 48, "author": {"login": "reviewer-a"}, "url": "u/2"}]}},
      {"id": "RT_res_2", "isResolved": true, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_r2", "body": "Fixed in 3a1f9c.", "path": "src/lib.rs", "line": 3, "originalLine": 3, "author": {"login": "reviewer-b"}, "url": "u/3"}]}},
      {"id": "RT_res_3", "isResolved": true, "isOutdated": true,
       "comments": {"nodes": [{"id": "C_r3", "body": "Stale, ignore.", "path": "src/old.rs", "line": 9, "originalLine": 9, "author": {"login": "reviewer-b"}, "url": "u/4"}]}},
      {"id": "RT_unres_bravo", "isResolved": false, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_b1", "body": "nit: this constant should come from the config, not be inlined.", "path": "src/config.rs", "line": 71, "originalLine": 71, "author": {"login": "reviewer-c"}, "url": "u/5"}]}},
      {"id": "RT_res_4", "isResolved": true, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_r4", "body": "Agreed, done.", "path": "src/claim.rs", "line": 90, "originalLine": 90, "author": {"login": "reviewer-a"}, "url": "u/6"}]}},
      {"id": "RT_res_5", "isResolved": true, "isOutdated": false,
       "comments": {"nodes": [{"id": "C_r5", "body": "Good catch, resolved.", "path": "src/claim.rs", "line": 104, "originalLine": 104, "author": {"login": "reviewer-c"}, "url": "u/7"}]}},
      {"id": "RT_unres_charlie", "isResolved": false, "isOutdated": true,
       "comments": {"nodes": [{"id": "C_c1", "body": "This overflow check was dropped when the function moved. Still missing.", "path": "src/math.rs", "line": 22, "originalLine": 19, "author": {"login": "reviewer-b"}, "url": "u/8"}]}}
    ]},
    "reviews": { "nodes": [
      {"id": "RV_overview", "state": "COMMENTED", "body": "## Pull request overview\nThis PR adds a settlement claim path and wires it into the bond account.", "author": {"login": "copilot-pull-request-reviewer"}, "url": "u/9", "submittedAt": "2026-09-01T10:00:00Z"},
      {"id": "RV_changes", "state": "CHANGES_REQUESTED", "body": "Please confirm the claim account is closed on the failure branch as well — otherwise rent is stranded.", "author": {"login": "reviewer-a"}, "url": "u/10", "submittedAt": "2026-09-02T09:00:00Z"}
    ]},
    "comments": { "nodes": [
      {"id": "IC_ping", "body": "Bumping this, any update?", "author": {"login": "reviewer-c"}, "url": "u/11", "createdAt": "2026-09-03T08:00:00Z"},
      {"id": "IC_ask", "body": "Does this need a migration for existing bonds created before the claim path existed?", "author": {"login": "reviewer-b"}, "url": "u/12", "createdAt": "2026-09-03T08:30:00Z"}
    ]}
  }}}
}
JSON
