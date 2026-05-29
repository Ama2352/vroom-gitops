# Sealed Secrets

All secrets committed to this repo are encrypted `SealedSecret` resources. Plaintext never touches git.

## How sealing works

Sealing happens inside the K3s server VM using the cluster's public key:

```bash
# From the host — triggers the Ansible playbook inside the VM
vagrant provision --provision-with seal-secrets.yml

# The playbook:
# 1. Reads plaintext values from ansible/vars/secrets.yml (gitignored)
# 2. Renders Kubernetes Secret manifests from ansible/templates/db-secret.j2
# 3. Seals each Secret with kubeseal → writes to secrets/<namespace>/
# 4. Commits and pushes to this repo
```

## Scope

All secrets use **strict scope** (name + namespace bound). A secret sealed for `vroom-dev` cannot be decrypted in `vroom-prod`.

## Secret inventory

| Namespace | Secret | Purpose |
|-----------|--------|---------|
| `vroom` | `gitops-git-creds` | Kargo GitHub write access |
| `vroom` | `ghcr-creds` | GHCR image pull (placeholder — seal after cluster up) |
| `vroom-dev/staging/prod` | `*-db-secrets` | PostgreSQL DSNs per service |
| `vroom-kargo` | `kargo-admin-password` | Kargo UI admin password |
| `monitoring` | `alertmanager-slack-secret` | Slack webhook for alerts |
| `monitoring` | `n8n-sealed-secret` | n8n encryption key (placeholder) |
| `monitoring` | `kubectl-executor-secret` | Bearer token for kubectl-executor |

## Fallback (Windows host)

```powershell
# Apply all sealed secrets directly without re-sealing
cd vroom-infra
./scripts/apply-sealed-secrets.ps1
```
