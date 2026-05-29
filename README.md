# vroom-gitops

GitOps source of truth for the **Vroom** ride-hailing platform. ArgoCD reads this repo to deploy and reconcile all cluster state. Kargo reads it to promote images across environments.

Part of a three-repo setup:
- [vroom-services](https://github.com/Ama2352/vroom-services) — application source + CI
- **vroom-gitops** (this repo) — delivery manifests
- [vroom-infra](https://github.com/Ama2352/vroom-infra) — K3s cluster provisioning

---

## Repository Layout

```
vroom-gitops/
├── root-app.yaml       ArgoCD bootstrap — apply this once to seed the cluster
├── bootstrap/          ArgoCD Application and ApplicationSet definitions
│   ├── apps-set-*.yaml   ApplicationSets (one per environment)
│   ├── infra.yaml        Deploys platform/
│   ├── kargo-resources.yaml  Deploys delivery/
│   └── vroom-secrets.yaml    Deploys secrets/ (sync wave -2)
├── apps/               Kustomize base + overlays per service
│   └── <service>/
│       ├── base/
│       └── overlays/{dev,staging,prod}/
├── platform/           Cluster infrastructure
│   ├── postgres/         PostgreSQL
│   ├── redis/            Redis
│   ├── observability/    Prometheus + Loki + Grafana + Tempo
│   │   ├── prometheus/   kube-prometheus-stack, ServiceMonitors
│   │   └── loki/         Loki chart
│   ├── cert-manager/
│   ├── n8n/              Workflow automation (ReAct agent orchestrator)
│   ├── kubectl-executor/ Allowlist kubectl gateway
│   └── runbook-retriever/ RAG runbook service
├── delivery/           Kargo project CRDs
│   ├── warehouse.yaml    Watches GHCR for new image tags
│   ├── stages/           dev → staging → prod with verification gates
│   └── analysis/         AnalysisTemplates (prometheus-checks)
└── secrets/            SealedSecrets per namespace (never plaintext)
    ├── vroom-dev/  vroom-staging/  vroom-prod/
    ├── vroom-kargo/  monitoring/  platform/
    └── kustomization.yaml
```

---

## How deployment works

```
GitLab CI builds image → pushes to GHCR
  → CI patches apps/<svc>/overlays/dev/ (image tag)
  → ArgoCD syncs vroom-dev namespace
  → Kargo Warehouse detects new tag → promotes dev→staging→prod
  → Each stage gate: prometheus-checks AnalysisRun must pass
```

---

## Bootstrap a new cluster

```bash
# 1. Install Sealed Secrets controller (required to decrypt secrets)
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml

# 2. Seed ArgoCD — it takes over from here
kubectl apply -f root-app.yaml
```

---

## Documentation

- [Environments & promotion gates](docs/environments.md)
- [Sealed secrets procedure](docs/secrets.md)
