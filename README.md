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

All cluster state is expressed declaratively in this repo. No `kubectl apply` in CI. The flow is:

```
Developer push to vroom-services
  → GitLab CI builds + publishes image to GHCR
  → CI patches apps/<svc>/overlays/dev/ (image tag only)
  → ArgoCD detects diff → syncs vroom-dev namespace

Kargo Warehouse detects new image tag in GHCR
  → Creates Freight object
  → Promotes dev → staging (after prometheus-checks AnalysisRun passes)
  → Promotes staging → prod (after prometheus-checks AnalysisRun passes)
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

Full details: [docs/environments.md](docs/environments.md) · [docs/secrets.md](docs/secrets.md)

---

## Repository Layout

```
vroom-gitops/
├── root-app.yaml           Bootstrap entrypoint — apply this once to seed ArgoCD
│
├── bootstrap/              ArgoCD Application definitions (App-of-Apps pattern)
│   ├── apps-set-dev.yaml       ApplicationSet — one ArgoCD App per service in vroom-dev
│   ├── apps-set-staging.yaml   ApplicationSet — vroom-staging
│   ├── apps-set-prod.yaml      ApplicationSet — vroom-prod
│   ├── infra.yaml              Deploys platform/ (Postgres, Redis, observability, n8n…)
│   ├── kargo-resources.yaml    Deploys delivery/ (Kargo project + stage CRDs)
│   └── vroom-secrets.yaml      Deploys secrets/ (sync wave -2, prune: false)
│
├── apps/                   Per-service Kustomize manifests
│   └── <service>/
│       ├── base/           Deployment, Service, HPA — shared across envs
│       └── overlays/
│           ├── dev/        image: tag patched by CI on every merge
│           ├── staging/    image: tag patched by Kargo on promotion
│           └── prod/       image: tag patched by Kargo on promotion
│
├── platform/               Cluster infrastructure (managed by infra.yaml ArgoCD App)
│   ├── postgres/           PostgreSQL StatefulSet
│   ├── redis/              Redis StatefulSet
│   ├── observability/
│   │   ├── prometheus/     kube-prometheus-stack + ServiceMonitor CRDs
│   │   └── loki/           Loki log aggregation
│   ├── cert-manager/       TLS certificate automation
│   ├── n8n/                Workflow automation — ReAct incident agent orchestrator
│   ├── kubectl-executor/   Allowlist-gated kubectl HTTP gateway
│   └── runbook-retriever/  RAG runbook lookup service
│
├── delivery/               Kargo progressive delivery CRDs
│   ├── warehouse.yaml      Watches ghcr.io/ama2352/vroom-mvp-* for new image tags
│   ├── project.yaml        Kargo Project (namespace: vroom)
│   ├── stages/
│   │   ├── dev.yaml        Stage: auto-promote, no gate
│   │   ├── staging.yaml    Stage: prometheus-checks AnalysisRun required
│   │   └── prod.yaml       Stage: prometheus-checks AnalysisRun required
│   └── analysis/
│       └── prometheus-checks.yaml  AnalysisTemplate: error rate, P95 latency, OOMKill
│
└── secrets/                SealedSecret resources (never plaintext)
    ├── vroom/              Kargo git creds, GHCR image pull
    ├── vroom-dev/          Per-service DB DSNs (dev)
    ├── vroom-staging/      Per-service DB DSNs (staging)
    ├── vroom-prod/         Per-service DB DSNs (prod)
    ├── vroom-kargo/        Kargo admin password
    ├── monitoring/         Alertmanager Slack webhook, n8n encryption key
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

Each Kargo stage (staging, prod) runs a `prometheus-checks` AnalysisRun that must pass before promotion is marked successful:

- HTTP error rate < 1% over a 5-minute window
- P95 request latency < 500 ms
- No OOMKill events in the last 10 minutes

To promote manually:

```bash
kargo promote --project vroom --freight <id> --stage staging
```

---

## Documentation

- [Environments & promotion gates](docs/environments.md)
- [Sealed secrets procedure](docs/secrets.md)
