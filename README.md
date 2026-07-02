# vroom-gitops

GitOps source of truth for the **Vroom** ride-hailing platform. This repo contains no application code — it contains only the declarations of desired cluster state. ArgoCD continuously reconciles the cluster to match what is here. Kargo promotes images across environments using the same Git-as-the-source-of-truth principle.

Part of a three-repo setup:

| Repo | Responsibility |
|------|---------------|
| [vroom-services](https://github.com/Ama2352/vroom-services) | Application source code + CI pipeline |
| **vroom-gitops** (this repo) | Cluster manifests — ArgoCD reads and reconciles this |
| [vroom-infra](https://github.com/Ama2352/vroom-infra) | Vagrant + Ansible K3s provisioning |

---

## GitOps Model

All cluster state is expressed declaratively in this repo. No `kubectl apply` in CI, and no CI-to-gitops push at all — build/publish (`vroom-services`) and delivery (this repo, via Kargo) are fully decoupled:

```
Developer push to vroom-services
  → GitLab CI builds + publishes image to GHCR (ghcr.io/ama2352/vroom-mvp-*)

Kargo Warehouse polls GHCR for new image tags
  → Creates a Freight object
  → Promotes into dev (auto, as soon as Freight appears)
  → Promotes dev → staging (auto, after dev's Freight passes prometheus-checks)
  → Promotes staging → prod (after staging's Freight passes prometheus-checks,
    and after human approval via `kargo approve`)
```

### Applied patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **App-of-Apps** | `root-app.yaml` + `bootstrap/` | One `kubectl apply` seeds the entire cluster; ArgoCD manages itself and everything else |
| **ApplicationSet** | `bootstrap/apps-set-*.yaml` | Generates one ArgoCD Application per service per environment from a template |
| **Kustomize overlays** | `apps/<svc>/base/` + `overlays/{dev,staging,prod}/` | Base manifests shared; only image tag and replica count differ per environment |
| **Progressive delivery** | `delivery/` (Kargo) | Automated promotion gated on real Prometheus metrics — not just "pod is Running" |
| **Sealed Secrets** | `secrets/` | All secrets are encrypted at rest in Git; plaintext never committed |
| **Sync waves** | `vroom-secrets` at wave -2 | Secrets are decrypted and applied before any workload starts |

---

## Repository Layout

```
vroom-gitops/
├── root-app.yaml           Bootstrap entrypoint — apply this once to seed ArgoCD
│
├── bootstrap/               ArgoCD Application definitions (App-of-Apps pattern)
│   ├── apps-set-dev.yaml        ApplicationSet — one ArgoCD App per service in vroom-dev
│   ├── apps-set-staging.yaml    ApplicationSet — vroom-staging
│   ├── apps-set-prod.yaml       ApplicationSet — vroom-prod
│   ├── infra.yaml               Deploys platform/ (Postgres, Redis, observability, n8n…)
│   ├── kargo-resources.yaml     Deploys delivery/ (Kargo project + stage CRDs)
│   └── vroom-secrets.yaml       Deploys secrets/ (sync wave -2, prune: false)
│
├── apps/                    Per-service Kustomize manifests
│   └── <service>/
│       ├── base/            Deployment, Service, HPA — shared across envs
│       └── overlays/
│           ├── dev/         image: tag patched by Kargo on promotion
│           ├── staging/     image: tag patched by Kargo on promotion
│           └── prod/        image: tag patched by Kargo on promotion
│
├── platform/                Cluster infrastructure (managed by infra.yaml ArgoCD App)
│   ├── postgres/            PostgreSQL StatefulSet
│   ├── redis/               Redis StatefulSet
│   ├── observability/
│   │   ├── prometheus/      kube-prometheus-stack + ServiceMonitor CRDs
│   │   ├── loki/            Loki log aggregation
│   │   └── tempo/           Distributed tracing backend
│   ├── cert-manager/        TLS certificate automation
│   ├── argo-rollouts/       Analysis engine — processes the AnalysisRun objects Kargo creates
│   ├── kargo-chart/         Kargo itself (Helm chart)
│   ├── n8n/                 Workflow automation — incident response orchestrator
│   ├── kubectl-executor/    Allowlist-gated kubectl HTTP gateway
│   └── incident-agent/      SRE diagnostics agent (source: vroom-services/incident-diagnosis/)
│
├── delivery/                Kargo progressive delivery CRDs
│   ├── warehouse.yaml           Watches ghcr.io/ama2352/vroom-mvp-* for new app-service tags
│   ├── platform-warehouse.yaml  Watches ghcr.io/ama2352/vroom-mvp-incident-agent separately
│   ├── project.yaml             Kargo Project (namespace: vroom)
│   ├── project-config.yaml      Promotion policies — auto-promotion enabled for dev + staging
│   ├── rbac/                    Kargo project-scoped RBAC
│   ├── stages/
│   │   ├── dev.yaml          Stage: promotes on new Freight, prometheus-checks verification
│   │   ├── staging.yaml      Stage: promotes after dev's Freight is verified
│   │   ├── prod.yaml         Stage: requires `kargo approve`, prometheus-checks verification
│   │   └── platform.yaml     Stage for the incident-agent image
│   └── analysis/
│       └── prometheus-checks.yaml  AnalysisTemplate: error rate, P95 latency, OOMKill
│
└── secrets/                 SealedSecret resources (never plaintext)
    ├── vroom/                Kargo git creds, GHCR image pull
    ├── vroom-dev/            Per-service DB DSNs (dev)
    ├── vroom-staging/        Per-service DB DSNs (staging)
    ├── vroom-prod/           Per-service DB DSNs (prod)
    ├── vroom-kargo/          Kargo admin password
    ├── platform/             Per-service DB DSNs (shared platform namespace)
    ├── monitoring/           Alertmanager Slack webhook, n8n encryption key, kubectl-executor token, LLM API keys (Groq, OpenRouter)
    └── kustomization.yaml
```

---

## Bootstrap a new cluster

```bash
# 1. Install Sealed Secrets controller — must be first (decrypts secrets before ArgoCD starts)
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml

# 2. Apply the root app — ArgoCD takes over from here and deploys everything else
kubectl apply -f root-app.yaml
```

ArgoCD syncs `bootstrap/` first (sync wave 0), which deploys `infra.yaml` and `vroom-secrets.yaml`. The `vroom-secrets` app runs at wave -2 so all SealedSecrets are decrypted before any workload pod starts.

---

## Promotion gates

Each Kargo stage runs a `prometheus-checks` AnalysisRun before marking the promotion successful:

- HTTP error rate < 1% over a 5-minute window
- P95 request latency < 500 ms
- No OOMKill events in the last 10 minutes

Dev and staging promote automatically once their upstream Freight passes verification (`delivery/project-config.yaml`). Prod requires an explicit approval:

```bash
kargo promote --project vroom --freight <id> --stage staging
kargo approve --project vroom --stage prod --freight <id>
```

---

## Sealed secrets

All secrets committed to this repo are encrypted `SealedSecret` resources — plaintext never touches git. Sealing happens inside the K3s server VM using the cluster's public key (`vroom-infra`'s `ansible/playbooks/seal-secrets.yml`), which reads plaintext from `vroom-infra/ansible/vars/secrets.yml`, renders manifests, seals them with `kubeseal`, and pushes here. All secrets use **strict scope** (name + namespace bound) — a secret sealed for `vroom-dev` cannot be decrypted in `vroom-prod`.

| Namespace | Secret | Purpose |
|-----------|--------|---------|
| `vroom` | `gitops-git-creds` | Kargo GitHub write access |
| `vroom` | `ghcr-creds` | GHCR image pull |
| `vroom-dev` / `vroom-staging` / `vroom-prod` / `platform` | `notification-db-secrets`, `ride-db-secrets`, `user-db-secrets` | PostgreSQL DSNs per service, per environment |
| `vroom-kargo` | `kargo-admin-password` | Kargo UI admin password |
| `monitoring` | `alertmanager-slack-secret` | Slack webhook for alerts |
| `monitoring` | `n8n-sealed-secret` | n8n encryption key |
| `monitoring` | `kubectl-executor-secret` | Bearer token for kubectl-executor |
| `monitoring` | `groq-secret` | Groq LLM API key (incident diagnosis agent) |
| `monitoring` | `openrouter-secret` | OpenRouter LLM API key (incident diagnosis agent, free-tier fallback models) |
