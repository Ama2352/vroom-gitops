# Environments & Promotion Gates

## Three environments

| Environment | Namespace | How image tag is set | Promotion trigger |
|-------------|-----------|---------------------|-------------------|
| **dev** | `vroom-dev` | CI patches `apps/<svc>/overlays/dev/` on every merge | Automatic (ArgoCD sync) |
| **staging** | `vroom-staging` | Kargo promotes from dev | After `prometheus-checks` pass |
| **prod** | `vroom-prod` | Kargo promotes from staging | After `prometheus-checks` pass |

## Verification gates

Each Kargo stage runs a `prometheus-checks` AnalysisRun before marking the promotion successful:

- HTTP error rate < 1% (5-minute window)
- P95 latency < 500 ms
- No OOMKill events in the last 10 minutes

Template: `delivery/analysis/prometheus-checks.yaml`

## Kargo warehouse

`delivery/warehouse.yaml` watches `ghcr.io/ama2352/vroom-mvp-*` for new tags.  
`includePaths` RE2 filter: `^apps/[^/]+/overlays/dev/.*$` — only dev overlay commits trigger a warehouse update.

## Promoting manually

```bash
# CLI
kargo promote --project vroom --freight <id> --stage staging

# UI
# https://192.168.25.133:30088  (Kargo admin UI)
```
