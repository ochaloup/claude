# Configuration & manifest consistency (YAML/K8s/IaC)

Load this only when the diff touches declarative config: K8s manifests, Helm,
Kustomize, Argo CD, Terraform, CI configs.

Bugs in declarative config are usually inconsistencies *across* files, not within
one. Read sibling files in the same directory and anything the diff transitively
references (Application sources, Kustomize bases, Helm values).

Verify:

- **Enumerated lists match reality.** Explicit lists of namespaces, services,
  envs, accounts, repos (ECR auth CronJob, ApplicationSet generators,
  NetworkPolicy peers, RBAC subjects, Kustomize `resources:`) stay in sync with
  what is actually defined elsewhere.
- **References resolve.** ServiceAccount, Secret, ConfigMap, Role, PVC, Service,
  Ingress backend, image refs point at something that exists in the right
  namespace.
- **New namespaces are enrolled in shared infra.** Image pull secrets, monitoring
  selectors, logging, NetworkPolicies, cert-manager, external-secrets, backups,
  RBAC. Catches `ImagePullBackOff` / no-metrics / default-deny surprises.
- **GitOps picks it up.** New manifests are selected by some Application or
  ApplicationSet (path globs, generators, value files). Otherwise it is dead
  config.
- **Selectors and labels are symmetric.** Service → Pod, NetworkPolicy
  podSelector, HPA target, ServiceMonitor — selectors match the labels actually
  set, and do not over-match.
- **Schema sane.** `apiVersion`/`kind` valid and not deprecated; required fields
  present; image tags pinned in prod; resource requests/limits where the
  namespace enforces them.
- **No plaintext secrets.** Use the repo's external secret convention
  (SealedSecrets, ExternalSecrets, SOPS).

Render-time check: would `kustomize build` / `helm template` /
`kubectl apply --dry-run=server` / `argocd app diff` succeed?
