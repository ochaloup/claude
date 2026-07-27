---
name: ops-infra-new-service
description: Checklist + templates for adding a new service to marinade-finance/ops-infra (Argo CD + Kustomize). Use when the user asks to add a new service / app / API / workload to ops-infra, registers something under argocd/<name>/, or asks "what do I need to deploy X" in this repo.
when_to_use: working in /home/chalda/marinade/ops-infra and the task is "add a new service", "deploy a new app", "create argocd manifests for X", or reviewing a PR that adds one — to make sure no integration plumbing is missed.
---

# Add a new service to ops-infra

This is a checklist for adding a new k8s workload that Argo CD will sync. The
goal is to make the easy-to-miss integrations (audit-images, ecr-auth, both env
applications) explicit so they don't get dropped.

The repo holds one `argocd/<service>/` directory per service. Each has a
`base/` with shared manifests and `overlays/<env>/` per environment (typically
`dev` and `prod`). Argo CD is told about the service via an `Application`
entry in `argocd/dev.yaml` and `argocd/prod.yaml`.

## Reference templates

When in doubt, copy from a recent similar service:

- `argocd/tx-router/` — plain HTTP service, dev+prod overlays, ingress
- `argocd/recipes-api/` — simplest version of the same shape (PR #2126)
- `argocd/stake-liquidator/` — service with both env overlays
- `argocd/waypoint/` — multi-network overlays (mainnet/testnet/devnet × dev/prod) + admin-ui + redis sidecar. Use only if multi-cluster/multi-network.

## Required files

### Per-service `argocd/<svc>/base/`

1. `kustomization.yaml` — lists every base resource file:
   ```yaml
   resources:
   - ./<svc>.deployment.yaml
   - ./<svc>.ingress.yaml
   - ./<svc>.pdb.yaml
   - ./<svc>.service.yaml
   ```
   Add `- ./<svc>.config.yaml` if a ConfigMap is needed (see tx-router).

2. `<svc>.deployment.yaml` — `apps/v1 Deployment`. Standard requirements (do NOT omit any without a reason):
   - `metadata.labels.app: <svc>` and matching `selector.matchLabels.app: <svc>`
   - Pod-level `securityContext`: `runAsNonRoot: true`, non-zero `runAsUser`/`runAsGroup`, `seccompProfile.type: RuntimeDefault`
   - Container-level `securityContext`: `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`
   - `affinity.podAntiAffinity` by `kubernetes.io/hostname` for the same app label (spreads replicas across nodes)
   - `dnsConfig.options: [{name: ndots, value: "2"}]`
   - **All three probes**: `startupProbe`, `readinessProbe`, `livenessProbe`. Use `httpGet` against a health endpoint when there is one; otherwise `tcpSocket`. Typical values: startup `periodSeconds: 5, failureThreshold: 30`, readiness/liveness `periodSeconds: 15, failureThreshold: 5`, `timeoutSeconds: 3`. Without startupProbe a slow boot kills the pod; without readinessProbe the service routes traffic before it's ready.
   - `resources.requests` + `resources.limits` for `cpu` and `memory`
   - `imagePullPolicy: IfNotPresent`
   - `imagePullSecrets: [{name: eu-central-1-ecr-registry}]` — created by the ecr-auth CronJob (see below)
   - Prometheus pod annotations IF the service exposes metrics: `prometheus.io/scrape: "true"`, `prometheus.io/port: "<metrics-port>"`, `prometheus.io/path: "/metrics"`
   - Image in base: keep a placeholder (`:placeholder`); overlays do the real assignment with a `# env:<env>` comment marker

3. `<svc>.service.yaml` — one `Service` for the app port. Add a SECOND `Service` named `<svc>-metrics` with the prometheus annotations if you also have a metrics port. Both share the same `selector.app: <svc>`.

4. `<svc>.ingress.yaml` — Traefik ingress. Use placeholder `host: KUSTOMIZED` and replace it per-overlay via a JSON6902 patch. Annotation: `kubernetes.io/ingress.class: traefik`.

5. `<svc>.pdb.yaml` — `PodDisruptionBudget`, `maxUnavailable: 1`, selector by `app: <svc>`.

### Per-environment `argocd/<svc>/overlays/<env>/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: <svc>-<env>
resources:
- ../../base
patchesJson6902:
  - target: {kind: Ingress, name: <svc>, namespace: <svc>-<env>}
    patch: |-
      - op: replace
        path: /spec/rules/0/host
        value: <svc>-<env>.marinade.finance
  - target: {kind: Deployment, name: <svc>, namespace: <svc>-<env>}
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/image
        value: 400405091548.dkr.ecr.eu-central-1.amazonaws.com/marinade.finance/<image>:placeholder # env:<env>
  - target: {kind: Deployment, name: <svc>, namespace: <svc>-<env>}
    patch: |-
      - op: replace
        path: /spec/replicas
        value: <N>
```

Note: the image automation bot (which opens PRs titled "Change image revision for marinade.finance/<image> to <sha>") MATCHES on the `# env:<env>` comment marker. Keep it exactly as `# env:dev` / `# env:prod`.

The namespace name does NOT have to match the directory name. Convention is `<svc>-<env>` for new services. (Some older workloads use the shared `dev` / `prod` namespace — don't follow those for new services.)

## Required edits to shared files

These are the easy-to-miss ones. They are where most "I forgot to add the namespace" review comments come from.

### `argocd/dev.yaml` and `argocd/prod.yaml`

Append an `Application` block:

```yaml
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <svc>-<env>
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:marinade-finance/ops-infra.git
    targetRevision: master
    path: argocd/<svc>/overlays/<env>
  destination:
    server: https://kubernetes.default.svc
    namespace: <svc>-<env>
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      selfHeal: true
      prune: true
```

`CreateNamespace=true` lets Argo CD create the namespace itself — but it does NOT also patch the ECR pull secret onto the namespace's default ServiceAccount, hence the next step.

### `argocd/ecr-auth/ecr-auth.cronjob.yaml`

Add the new namespaces to the hardcoded list inside the `set -- ... \` block (currently around lines 28–83). One entry per env, ideally grouped adjacent to a similar dev/prod pair so the list stays scannable. Example:

```yaml
                tx-router-dev \
                tx-router-prod \
                <svc>-dev \
                <svc>-prod \
                stake-liquidator-dev \
```

Why this matters: a CronJob runs every 15 min, fetches an ECR auth token, and for each listed namespace creates the `${region}-ecr-registry` docker-registry secret AND patches it onto that namespace's default ServiceAccount as an `imagePullSecret`. If the namespace is NOT in this list, pods will fail with `ImagePullBackOff` because no pull secret is wired up — even though the deployment references it by name. The CronJob logs "Namespace: <svc>-dev is missing." and silently skips it.

### `argocd/audit-images/audit-images.yaml`

Add ONE image line per env in the relevant `env:dev` block (around line 104) and `env:prod` block (around line 137). Include the `# env:dev` / `# env:prod` marker comment — the image bumper bot uses it. Initially the digest can be a placeholder like `:tobeadded`, but it MUST be the real `tag:abc123@sha256:...` immutable reference matching what the overlay deploys before merge — otherwise the audit job pages on a non-whitelisted image.

```
              400405091548.dkr.ecr.eu-central-1.amazonaws.com/marinade.finance/<image>:tobeadded # env:dev
              400405091548.dkr.ecr.eu-central-1.amazonaws.com/marinade.finance/<image>:tobeadded # env:prod
```

The image string in audit-images must match what the overlay deploys. If those drift, the audit job flags the running pod as non-whitelisted.

## Pre-merge gotchas — copilot/reviewers will catch these

- **Placeholder image tag**: overlays deploy `<image>:placeholder` (or `:tobeadded`) and Argo CD auto-syncs them — Argo will try to pull the placeholder tag and fail. Replace with the real built tag+digest before flipping the Application on, or merge while the Application is still disabled.
- **audit-images vs overlay drift**: if the overlay says `:abc123@sha256:...` and audit-images still says `:tobeadded` (or vice versa), the audit cron will keep flagging the pod.
- **Missing ecr-auth namespace entry**: pods stay in `ImagePullBackOff`. See above.
- **Missing prod-side**: easy to add only dev and forget `argocd/prod.yaml` + the prod overlay + the prod audit-images entry + the prod namespace in ecr-auth. Cross-check every change has a matching prod twin (unless this service is dev-only by design — note that in the PR).
- **Probes**: if the service has a `/health` (or similar), wire all three probes. Don't skip startupProbe.

## Pre-merge checklist (run mentally)

For service `<svc>` deployed to `<svc>-dev` and `<svc>-prod`:

- [ ] `argocd/<svc>/base/` has `kustomization.yaml` + deployment + service + ingress + pdb (+ config if needed)
- [ ] `argocd/<svc>/overlays/dev/kustomization.yaml` with namespace, host patch, image patch (`# env:dev`), replicas patch
- [ ] `argocd/<svc>/overlays/prod/kustomization.yaml` mirror of dev with `# env:prod`
- [ ] `argocd/dev.yaml` has an `Application` for `<svc>-dev`
- [ ] `argocd/prod.yaml` has an `Application` for `<svc>-prod`
- [ ] `argocd/ecr-auth/ecr-auth.cronjob.yaml` lists BOTH `<svc>-dev` and `<svc>-prod`
- [ ] `argocd/audit-images/audit-images.yaml` lists the image under BOTH `# env:dev` and `# env:prod` blocks
- [ ] Overlay image and audit-images image strings reference the same tag+digest (or both are still placeholders, with a follow-up commit before flipping on)
- [ ] Deployment has all three probes, anti-affinity, securityContext (pod + container), resources, ndots:2, imagePullSecrets
- [ ] PDB selector matches the deployment app label
- [ ] If exposing metrics: a second `<svc>-metrics` Service exists and prometheus annotations are on the pod template

## When verifying a PR that adds a service

Diff the PR against this checklist. The most commonly-missed items are:
1. ecr-auth namespace entries
2. prod-side anything (Application, overlay, audit-images)
3. audit-images drift from overlay image
4. Missing startupProbe

If the reviewer asks "is the namespace added in ecr-auth?", they mean step in `argocd/ecr-auth/ecr-auth.cronjob.yaml` above.
