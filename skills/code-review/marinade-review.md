# Marinade conformance

Load this only when the repo owner is `marinade-finance`. It applies to the diff
and to every suggested fix — a fix that breaks one of these rules is rewritten
before it is reported.

## Shared libraries

- **TypeScript.** For each new helper, grep `~/marinade/typescript-common/packages/*/src`
  for its name and its concept word (config loading, CLI, logging, web3/kit wrappers,
  JWT, NestJS modules, test utils). One grep per helper; read only the hits. An
  equivalent exists → P3 finding naming the package and export, and whether
  `package.json` already depends on it.
- **Rust.** The same against `~/marinade/rust-common`. Domain logic with no generic
  part needs no grep — say so in one line.
- **Lint and tooling.** A local eslint/tsconfig/jest setup where `eslint-config` or a
  shared preset already exists.

## Deployability

Find where the service is deployed: `~/marinade/gitops-apps/clusters/*/services/<svc>/`
(`values.yaml` plus region overlays) and `~/marinade/ops-infra/argocd/<svc>/overlays/*`.
Check every location found — a service in both is mid-migration, and both still deploy.
Neither → `Deployability: not verified — no manifests found for <svc>`.

- **Env vars and config keys** the diff reads, new or renamed → set in every cluster
  that deploys the service — under `env:`, or inside an inline config file such as
  `config.data.config.yaml` — or defaulted in code (`#[serde(default)]`, an `Option`,
  a `??` or schema default in the config loader). Missing with no default is P1: the
  pod fails on boot in that cluster.
- **Rollout order.** During a rolling deploy old and new replicas run together. A new
  config key, message field or storage format that old replicas reject, drop or
  overwrite is a finding; name the order that is safe.
- **Secrets** → an `externalSecrets:` entry, never plaintext in values.
- **New outbound host** → allowed by the `networkPolicy` egress rules.
- **Port, probe or metrics path** changed → `containerPort`, the probes and
  `serviceMonitor` still match.
- **Memory limit.** Only when a hunk adds a buffer, a cache, a collect-into-memory or
  more concurrency: compare its worst case against `resources.limits.memory`, and
  name the input size that would exceed it.
- **Shutdown behaviour** changed → `terminationGracePeriodSeconds` still covers it.
- **A new service** → check it against the `ops-infra-new-service` skill.

A needed manifest change is a finding naming the gitops file and key. It lands in a
separate gitops PR, so it never blocks this one on its own.

## Calls to Marinade services

When the diff adds or changes a call to another Marinade service or program — HTTP or
GraphQL client, SDK, on-chain program through its IDL — match the host or package name
to a repo under `~/marinade/` and read the callee at its default branch:

- **Contract.** Path, params, field names, nullability, pagination, error shape — in the
  callee's handler, DTO or IDL, not in the caller's assumptions.
- **Units.** Lamports vs SOL, epoch vs slot, basis points vs percent, seconds vs ms.
- **Client.** An existing client in the callee repo or typescript-common before a
  hand-written one.
- **Behaviour.** Timeouts, retries and caching on the call fit the callee's rate limits
  and latency.

Callee repo not checked out → `not verified` with the repo name.

## Complexity

- A second mechanism for a concept the repo or a shared library already handles — a
  second retry loop, config loader, cache or HTTP wrapper.
- A config option, flag or abstraction with exactly one user.
