#!/bin/bash
# Run a reviewed, root-owned copy. Inputs are fixed; no checkout code runs as root.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
umask 022
site=oceanacoustics.vincentmossman.com
account=oceanacoustics
volume=/srv/oceanacoustics
control=/var/lib/oceanacoustics-volume
image=$control/data.ext4
mountunit=srv-oceanacoustics.mount
ng=/etc/nginx/sites-enabled/oceanacoustics.conf
units=/etc/systemd/system
owner=${SUDO_USER:-}
[[ $EUID == 0 && -n $owner && $owner != root ]] || { echo 'Run via sudo from the checkout owner account.' >&2; exit 1; }
cd /
exec 9>/run/lock/oceanacoustics-install.lock
flock -n 9
if [[ ${1:-} == rollback ]]; then
    [[ -f $control/managed-v1 ]] || exit 1
    systemctl disable --now oceanacoustics.timer || true
    systemctl stop oceanacoustics.service || true
    if [[ -e $ng ]]; then
        grep -qx '# Managed by oceanacoustics' "$ng" || exit 1
        mv "$ng" "$control/disabled-nginx-$(date +%s)"
        nginx -t && systemctl reload nginx
    fi
    echo 'Worker and public vhost disabled. Research volume, certificate, backups and units retained.'
    exit
fi
[[ $# == 0 ]] || exit 1
owner_dir=$(getent passwd "$owner" | cut -d: -f6)
repo=$owner_dir/oceanacoustics
pilot=$owner_dir/oceanacoustics-pilot
asowner() { runuser -u "$owner" -- "$@"; }
revision=$(asowner git -C "$repo" rev-parse --verify HEAD)
[[ $revision =~ ^[0-9a-f]{40}$ ]]
asowner git -C "$repo" diff --quiet HEAD --
getent ahosts "$site" >/dev/null
systemctl is-active --quiet nginx
nginx -t
lineage=/etc/letsencrypt/live/$site
renewal=/etc/letsencrypt/renewal/$site.conf
issue_cert=no
if [[ -s $lineage/fullchain.pem && -s $lineage/privkey.pem && -s $renewal ]]; then
    echo "Using existing TLS certificate; scheduled renewal is handled by certbot.timer."
elif [[ -e $lineage || -L $lineage || -e $renewal || -L $renewal || -e /etc/letsencrypt/archive/$site ]]; then
    echo "Incomplete Certbot lineage for $site. Inspect it before deploying." >&2
    exit 1
else
    issue_cert=yes
fi
if [[ ! -f $control/managed-v1 ]]; then
    for p in "$control" "$volume" "$ng" "$units/$mountunit" "$units/oceanacoustics.service" "$units/oceanacoustics.timer" /etc/default/oceanacoustics /var/lib/letsencrypt/oceanacoustics /etc/letsencrypt/renewal/oceanacoustics.vincentmossman.com.conf; do
        [[ ! -e $p && ! -L $p ]] || { echo "Existing unmanaged path: $p"; exit 1; }
    done
    if getent passwd "$account" >/dev/null || getent group "$account" >/dev/null; then echo 'Account collision'; exit 1; fi
    if grep -REqs 'server_name[^;]*oceanacoustics\.vincentmossman\.com' /etc/nginx/{sites-enabled,conf.d}; then echo 'Virtual host collision'; exit 1; fi
    install -d -m 700 "$control"
    touch "$control/managed-v1"
fi
missing=()
for pkg in python3-numpy python3-scipy python3-pil ffmpeg e2fsprogs certbot; do
    [[ $(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true) == 'install ok installed' ]] || missing+=("$pkg")
done
if (( ${#missing[@]} )); then NEEDRESTART_MODE=l apt-get install --no-install-recommends -y "${missing[@]}"; fi
if ! getent passwd "$account" >/dev/null; then
    useradd --system --user-group --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin "$account"
fi
[[ $(id -u "$account") -gt 0 && $(getent passwd "$account" | cut -d: -f7) == /usr/sbin/nologin ]]
backup=$(mktemp -d "$control/backup.XXXXXXXX")
stage=$(mktemp -d "$control/stage.XXXXXXXX")
for path in "$ng" "$units/$mountunit" "$units/oceanacoustics.service" "$units/oceanacoustics.timer" /etc/default/oceanacoustics; do
    if [[ -e $path ]]; then cp -a "$path" "$backup/"; fi
done
echo "Previous project configuration in $backup"
active=no
systemctl is-active --quiet oceanacoustics.timer && active=yes
restore() {
    local rc=$?
    trap - ERR
    set +e
    systemctl disable --now oceanacoustics.timer
    for path in "$ng" "$units/oceanacoustics.service" "$units/oceanacoustics.timer"; do
        if [[ -f $backup/${path##*/} ]]; then cp "$backup/${path##*/}" "$path"; else rm -f "$path"; fi
    done
    systemctl daemon-reload
    nginx -t && systemctl reload nginx
    [[ $active == yes ]] && systemctl enable --now oceanacoustics.timer
    echo "Activation failed. Prior vhost and worker definitions restored. Volume and findings retained." >&2
    exit "$rc"
}
trap restore ERR
if [[ $active == yes ]]; then systemctl stop oceanacoustics.timer; systemctl stop oceanacoustics.service; fi
if [[ ! -f $image ]]; then
    [[ $(df -B1 --output=avail "$control" | tail -1) -ge 70000000000 ]]
    truncate -s 48000000000 "$stage/new.ext4"
    mkfs.ext4 -q -F -m 0 -L oceanacoustics "$stage/new.ext4"
    mv "$stage/new.ext4" "$image"
fi
[[ $(stat -c %s "$image") == 48000000000 ]]
install -d "$volume"
cat > "$units/$mountunit" <<EOF
[Unit]
Description=Bounded Ocean Acoustics research volume
[Mount]
What=$image
Where=$volume
Type=ext4
Options=loop,nodev,nosuid,noexec
[Install]
WantedBy=local-fs.target
EOF
systemctl daemon-reload
systemctl enable --now "$mountunit"
mountpoint -q "$volume"
dev=$(findmnt -nro SOURCE --mountpoint "$volume")
[[ $(losetup -n -O BACK-FILE "$dev") == "$image" ]]
install -d "$volume/releases" "$volume/state"
chown "$account:$account" "$volume/state"
release=$volume/releases/$revision
if [[ ! -d $release ]]; then
    staging=$(mktemp -d "$volume/releases/.stage.XXXXXXXX")
    chown "$account:$account" "$staging"
    asowner git -C "$repo" archive "$revision" | runuser -u "$account" -- tar -x --no-same-owner -C "$staging"
    chmod 755 "$staging"
    mv "$staging" "$release"
fi
# Import only the owner's benchmark state, through an unprivileged extractor.
# Publish it atomically so interrupted imports can be retried.
if [[ ! -e $volume/state/db/results.sqlite && -d $pilot/db ]]; then
    seed=$(mktemp -d "$volume/.seed.XXXXXXXX")
    chown "$account:$account" "$seed"
    asowner flock -n "$pilot/worker.lock" tar -C "$pilot" -cf - db public | runuser -u "$account" -- tar -xf - --no-same-owner -C "$seed"
    [[ -z $(ls -A "$volume/state") ]]
    rmdir "$volume/state"
    mv -T "$seed" "$volume/state"
    chmod 755 "$volume/state"
fi
runuser -u "$account" -- mkdir -p "$volume/state/tmp"
if [[ ! -f /etc/default/oceanacoustics ]]; then
    printf '%s\n' ENABLE_MONITOR=1 ENABLE_BACKFILL=1 BACKFILL_LOAD_LIMIT=4 >/etc/default/oceanacoustics
fi
cat >"$units/oceanacoustics.service" <<EOF
[Unit]
Description=Ocean Acoustics bounded archive analysis
RequiresMountsFor=$volume
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=900
StartLimitBurst=3
[Service]
Type=oneshot
User=$account
Group=$account
WorkingDirectory=$release
EnvironmentFile=/etc/default/oceanacoustics
Environment=OCEAN_TIMER=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
Environment=HOME=$volume/state TMPDIR=$volume/state/tmp XDG_CACHE_HOME=$volume/state/cache
ExecStart=/usr/bin/python3 -B $release/worker.py both --state $volume/state
TimeoutStartSec=4min
Restart=on-failure
RestartSec=60
CPUQuota=50%
MemoryMax=512M
TasksMax=32
Nice=15
IOSchedulingClass=idle
IOWeight=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$volume/state
ProtectHome=yes
PrivateDevices=yes
InaccessiblePaths=/tmp /var/tmp /dev/shm
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
CapabilityBoundingSet=
UMask=0022
StandardOutput=null
StandardError=journal
LogRateLimitIntervalSec=1h
LogRateLimitBurst=20
EOF
cat >"$units/oceanacoustics.timer" <<'EOF'
[Unit]
Description=Schedule delayed and historical ocean observations
[Timer]
OnBootSec=3min
OnUnitInactiveSec=5min
RandomizedDelaySec=20
Unit=oceanacoustics.service
[Install]
WantedBy=timers.target
EOF
acme=/var/lib/letsencrypt/oceanacoustics
install -d "$acme"
cat >"$stage/http" <<EOF
# Managed by oceanacoustics
server {
    listen 80;
    listen [::]:80;
    server_name $site;
    access_log off;
    location ^~ /.well-known/acme-challenge/ { root $acme; try_files \$uri =404; }
    location / { return 301 https://$site\$request_uri; }
}
EOF
# Retain an existing TLS vhost during reinstallation.
if [[ ! -e $ng ]]; then install -m 644 "$stage/http" "$ng"; nginx -t; systemctl reload nginx; fi
if [[ $issue_cert == yes ]]; then
    certbot certonly --webroot -w "$acme" --cert-name "$site" -d "$site" --non-interactive --keep-until-expiring --deploy-hook '/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx'
fi
cp "$stage/http" "$stage/https"
cat >>"$stage/https" <<EOF
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $site;
    ssl_certificate /etc/letsencrypt/live/$site/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$site/privkey.pem;
    root $release/web;
    disable_symlinks on;
    access_log off;
    add_header X-Content-Type-Options nosniff always;
    location / { limit_except GET { deny all; } try_files \$uri \$uri/ =404; }
    location /data/ {
        limit_except GET { deny all; }
        alias $volume/state/public/data/;
        add_header Cache-Control "no-cache";
    }
    location ~ /\. { deny all; }
}
EOF
install -m 644 "$stage/https" "$ng"
systemctl daemon-reload
systemd-analyze verify "$units/oceanacoustics.service" "$units/oceanacoustics.timer"
nginx -t
systemctl reload nginx
systemctl enable --now certbot.timer oceanacoustics.timer
systemctl start oceanacoustics.service
curl -fsS --resolve "$site:443:127.0.0.1" "https://$site/data/observatory.json" >/dev/null
echo "Origin HTTPS and worker passed. For rollback run this same script with argument rollback."
