# k3s deployment

Runs the app in the `gnarg` k3s cluster (namespace `kia`), reachable at
**https://kia.unixkonsult.se** through the existing host `cloudflared`
(`patchguardian` tunnel) → Traefik → Service.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile`    | amd64 image; adds `tzdata`/`TZ` and symlinks `/app/.env` → `/app/data/.env` |
| `manifests.yaml`| Namespace, PVC (`kia-data`, 1Gi), Deployment (`replicas: 1`, `Recreate`), Service (80→5000), Ingress (`kia.unixkonsult.se`) |
| `deploy.sh`     | build → `k3s ctr images import` → `kubectl apply` → rollout |

No private registry: the image is built with podman and imported straight into
k3s' containerd (`imagePullPolicy: Never`), same as the sibling apps.

## Deploy / update

```bash
k8s/deploy.sh
```

## Configure Kia credentials

Deployed with an empty `.env`. After the first deploy:

1. Open <https://kia.unixkonsult.se/admin> (gear icon).
2. Enter the Kia Connect **e-mail** and **password** (plaintext), then **Save**.
   A 48-char refresh token works in the password field too — the library
   auto-detects which one it is.

`hyundai-kia-connect-api` is pinned to `4.27.2` (see `../requirements.txt`).
Older versions used the legacy IDPConnect `authorize` flow, which Kia's WAF now
blocks as an "abusing request"
([#1273](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api/issues/1273));
4.27.x uses the OneApp/CCI headless login instead.

Credentials are written to `/app/data/.env` on the PVC and reloaded on every
restart. Schedules persist in `/app/data/schedules.json`.

```bash
kubectl -n kia exec deploy/kia-climate-control -- cat /app/data/.env
kubectl -n kia logs -f deploy/kia-climate-control
```

## One-time Cloudflare / host setup

**Done automatically:**

- `/etc/cloudflared/config.yml` on `gnarg` — added an ingress rule
  (`kia.unixkonsult.se` → `http://192.168.2.163`, i.e. Traefik) before the
  `http_status:404` catch-all. Backup at `config.yml.bak.*`.
- `sudo systemctl restart cloudflared` — patchguardian tunnel reconnected, no
  downtime.

**Must be done by hand in the Cloudflare dashboard** (the `cloudflared` cert on
`gnarg` is scoped to the `patchguardian.com` zone only, so it cannot touch
`unixkonsult.se` DNS):

1. Zone **unixkonsult.se → DNS**: edit the `kia` CNAME. Change its target from
   `4b150f78-72ee-4102-80d2-463b42dcd597.cfargotunnel.com` (old Pi tunnel, now
   offline) to `624563ea-59f0-4111-b4ba-3995fefe46b8.cfargotunnel.com`. Keep it
   **proxied** (orange cloud).
2. Zone **patchguardian.com → DNS**: delete the stray CNAME
   `kia.unixkonsult.se.patchguardian.com` (created by a `cloudflared` command
   that appended the wrong zone — harmless but junk).

The existing **Cloudflare Access** application on `kia.unixkonsult.se`
(`andlun.cloudflareaccess.com`, email policy) still applies and needs no change.

The old dedicated `kia-climate` tunnel (`4b150f78-…`) is left in place but
unused — the Pi can be brought back by reverting step 1.

## Rollback

```bash
kubectl delete namespace kia
# then remove the kia.unixkonsult.se block from /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```
