#!/usr/bin/env bash
set -euo pipefail

mkdir -p plans

filler() {
  for _ in $(seq 1 12); do
    printf 'Assessment: CONFIRMED. The handler writes through the raw pool rather than the scoped wrapper, so the authority never travels with the connection and the invariant documented on the wrapper is not enforced anywhere on this path. '
  done
  printf '\n'
}

{
  echo '# demo / widget-refactor (PR #99): Review — Round 2'
  echo
  echo 'Generated: 2026-09-01 10:00 CEST'
  echo
  echo '## Section A: Conversation Status'
  echo
  echo '### A1 — Your items'
  for n in $(seq 1 11); do
    echo
    echo "#### P2-R2#${n} [PRESENT] [MY_THREAD] [INLINE-THREAD]"
    echo "\`src/module_${n}.rs:${n}0\`"
    filler
    echo "Fix plan: Route the call through the scoped wrapper in \`src/module_${n}.rs\` and add a mismatch test."
  done
  echo
  echo '### A2 — Others inline threads'
  echo
  echo '#### P1-R2#12 [PRESENT] [OTHERS_THREAD] [INLINE-THREAD]'
  echo '`bot/src/commands/consume_orders.rs:44`'
  filler
  echo 'Fix plan: Keep the consumer own abort handle so the sender drops and the workers exit. ENDMARK5X8.'
} > plans/demo--widget-refactor--pr-99--REVIEW.md

{
  echo '# demo / widget-refactor (PR #99): Review — Round 1'
  echo
  echo '## Section A: Conversation Status'
  echo
  echo '#### P9-R1#99 [ADDRESSED] [MY_THREAD] [INLINE-THREAD]'
  echo '`src/gone.rs:1`'
  echo 'Fix plan: Already addressed in round 1, superseded by the round 2 file.'
} > plans/demo--widget-refactor--pr-99-r1--REVIEW.md

touch -d '2026-09-01 10:00' plans/demo--widget-refactor--pr-99--REVIEW.md
touch -d '2026-08-01 10:00' plans/demo--widget-refactor--pr-99-r1--REVIEW.md
