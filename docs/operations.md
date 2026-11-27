# Operations

## Inspected host and deployment choice

Initial inspection found Ubuntu 24.04, 14 AMD EPYC vCPUs, 70 GiB RAM, 63 GiB swap and about 546 GiB available on the host filesystem. One-minute load was 0.72 in the first sample. Nginx listened on 80/443, Jellyfin and rclone processes were present, the existing Certbot timer was active and a neighboring vhost used a dedicated HTTP-01 webroot. The hostname resolved to Cloudflare addresses. UFW configuration was enabled; detailed live firewall rules require the owner. Deployment adds no listener port or firewall rule. Static Nginx serving avoids an extra application daemon. The host and its neighboring services are shared infrastructure.

## Activation

Review the entire installer and current Git commit. Run a root-owned, reviewed copy from the checkout owner's sudo session. It expects the source checkout at `~/oceanacoustics` and optional benchmark state at `~/oceanacoustics-pilot`. Untracked local files are excluded from the Git archive. It rejects tracked changes. The caller needs an existing usable Certbot account, reachable HTTP-01 routing, ext4 loop-mount support, the existing Nginx installation and at least 70 GB free on initial activation. Package installation uses the configured Ubuntu repositories. On the inspected host the simulated missing-package install comprised SciPy, python3-decorator and liblbfgsb0.

The installer creates the unprivileged service account and a **sparse 48,000,000,000-byte image** under `/var/lib/oceanacoustics-volume`. A dedicated systemd mount attaches it at `/srv/oceanacoustics`. The image grows with actual writes and caps all production releases, cache, SQLite WAL/SHM, logs, temporary work, media and local research state. Shared OS packages, small operator checkout, installer backups, ACME state and rate-limited system journal entries live outside the image. The remaining 2 GB of the global budget is for those external costs. The image caps production state even when an application check fails. It cannot enforce an aggregate host quota on shared system files or arbitrary operator copies. Keep pilot copies and external backups inventoried separately. Back up research findings to existing storage under the operator's policy before replacing or retiring any data.

Only tracked release code is extracted, as the service account. The installer imports pilot DB and public evidence through unprivileged tar processes with the pilot locked. Raw cache and private research excerpts stay in the operator's pilot. The production data tree and code releases reside on separate paths. Worker filesystem access is read-only outside its state and it serves no HTTP API. Nginx exposes only static site assets and published data. The script backs up project configurations, enables the mount and units, issues a certificate on first installation and reuses the existing lineage on updates, checks Nginx before reload and probes the origin.

On activation failure the installer attempts to restore the prior vhost and worker definitions. Read its exit status and inspect the named backup. The root-only control directory retains prior configurations. Running the same reviewed installer with `rollback` disables the timer, stops the worker and withdraws the project vhost. The volume, releases and certificate remain available for recovery. Neither rollback path uninstalls shared dependencies.

## Scheduling, retention and health

Each cycle prioritizes one 60-second window from the latest available daily object, traversing backward from its end. Backfill then selects a least-sampled day of the current historical month, starting at midday before wrapping to midnight. It advances to the next month when full-length windows are exhausted. Monitoring samples recent recordings; the initial cadence cannot provide continuous chronological coverage. Disable either mode with `ENABLE_MONITOR=0` or `ENABLE_BACKFILL=0` in `/etc/default/oceanacoustics`. A backfill pass defers above one-minute host load 4 by default. The timer waits five minutes after completion plus jitter. Production limits are half a vCPU, 512 MiB RAM, 32 tasks, nice 15 and idle I/O. Failed runs retry after 60 seconds with a start-rate limit. A singleton lock prevents overlapping runs.

The worker evicts reproducible raw ranges older than 24 hours or when its raw cache exceeds 19 GB. The 20 GB raw admission cap includes partial downloads. Database admission stops before 4 GB and the evidence tree before 3 GB; this conservative policy suspends work until the operator preserves or expands space within budget. Current spectrograms expire after a ten-minute grace period; evidence spectrograms share the protected clip allocation. The log rotates at 1 MB with three backups. No trained model is installed. Public index data has a 1 GB admission guard. Storage over 40 GB is reported; new work stops at 45 GB, at low volume space, or under 10 GB free on the containing host filesystem in production. Monitor overall filesystem pressure and inspect old releases. Application preflight operates at bounded-window granularity. Never delete protected events or review history for routine acquisition.

```bash
systemctl status oceanacoustics.timer oceanacoustics.service --no-pager
systemctl list-timers oceanacoustics.timer certbot.timer
findmnt /srv/oceanacoustics
df -h /srv/oceanacoustics
python3 deploy/verify.py
```

An inactive oneshot between runs is expected. Check its last result, next trigger, the JSON timestamp, acquisition timestamp and range probe. The heartbeat streak is the interval since the first worker heartbeat in a chain with no gap over 15 minutes. It is sampled, and independent external monitoring would be needed for a website availability percentage.

To test ACME renewal as the operator, run `sudo certbot renew --cert-name oceanacoustics.vincentmossman.com --dry-run`. Verify the public hostname separately from the loopback origin because the public DNS resolves through Cloudflare. Compare Jellyfin health, rclone service state and existing website responses with their pre-install checks.

## Review and recovery

A failed range read leaves a bounded partial keyed by object version and sample offset. The next worker resumes under If-Match. Completed window IDs prevent duplicates. Candidate audio and index files are staged and atomically renamed; retrying reconciles an interrupted publication. Keep the SQLite DB with matching evidence. Use SQLite's online backup API, or stop scheduling and lock the worker before copying DB/WAL and public files together. The public data files are read-only publications. Perform human reviews locally as an authorized writer:

```bash
python3 -m research.review "$STATE" EVENT_ID "Recording artifact" REVIEWER "Evidence and rationale"
python3 -m research.coverage "$STATE"
```

The review trail retains private rationales and identities. Only the current label and review status are public. Reproduce NOAA examples and optional selective 16 kHz follow-ups using the commands in [the source audit](sources.md). The example-acquisition command is for the bounded private development set.
