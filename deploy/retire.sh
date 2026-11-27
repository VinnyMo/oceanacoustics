#!/bin/bash
# Run a reviewed copy installed as /root/oceanacoustics-retire.sh via sudo.
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /
site=oceanacoustics.vincentmossman.com
repo=/home/maestro/oceanacoustics
control=/var/lib/oceanacoustics-volume
volume=/srv/oceanacoustics
units=/etc/systemd/system
mountunit=srv-oceanacoustics.mount
ng=/etc/nginx/sites-enabled/oceanacoustics.conf
[[ $EUID == 0 && ${SUDO_USER:-} == maestro && $0 == /root/oceanacoustics-retire.sh && $# == 0 ]]
[[ $(stat -c '%u:%a' "$0") == 0:700 ]]
exec 9>/run/lock/oceanacoustics-install.lock
flock -n 9
own() { runuser -u maestro -- "$@"; }
gitown() { own git -C "$repo" -c credential.helper= -c 'credential.helper=!gh auth git-credential' "$@"; }
verify_git() {
    local remote
    [[ $(gitown branch --show-current) == main ]]
    [[ $(gitown remote get-url origin) == https://github.com/VinnyMo/oceanacoustics.git ]]
    remote=$(gitown ls-remote --exit-code origin refs/heads/main)
    local tip=${remote%%[[:space:]]*}
    if [[ $tip != "$(gitown rev-parse HEAD)" && ${1:-} == resume ]]; then
        # Retry a final seal whose push failed after its commit was written.
        [[ $(gitown rev-parse HEAD^) == "$tip" && $(gitown log -1 --format=%s) == 'Seal research ledger after stopping the observatory worker' ]]
        [[ $(gitown diff-tree --no-commit-id --name-only -r HEAD) == results/observations.jsonl.gz ]]
        gitown push origin HEAD:main
        verify_git
    else
        [[ $tip == "$(gitown rev-parse HEAD)" ]]
    fi
}
verify_git resume
# Permit a previously interrupted final export; all other checkout changes need review.
[[ -z $(gitown status --porcelain --untracked-files=all -- . ':(exclude)results/observations.jsonl.gz') ]]
[[ -z $(gitown stash list) && $(gitown worktree list --porcelain | grep -c '^worktree ') == 1 ]]
if [[ -e $control ]]; then
    [[ ! -L $control && -f $control/managed-v1 && $(stat -c %u "$control") == 0 ]]
fi
if [[ -e $ng || -L $ng ]]; then
    [[ -f $ng && ! -L $ng ]] && grep -Fxq '# Managed by oceanacoustics' "$ng" || exit 1
fi
if getent passwd oceanacoustics >/dev/null; then
    [[ $(getent passwd oceanacoustics | cut -d: -f6-7) == /nonexistent:/usr/sbin/nologin ]]
fi
if [[ -e /etc/letsencrypt/renewal/$site.conf ]]; then
    san=$(openssl x509 -in "/etc/letsencrypt/live/$site/cert.pem" -noout -ext subjectAltName | tail -n +2 | xargs)
    [[ $san == "DNS:$site" ]] || { echo "Certificate has additional names. Inspect before retirement."; exit 1; }
fi
if [[ -e $units/oceanacoustics.timer ]]; then systemctl disable --now oceanacoustics.timer; fi
if [[ -e $units/oceanacoustics.service ]]; then systemctl stop oceanacoustics.service; fi
if [[ -e $control/data.ext4 && ! -f $control/retired-sealed ]]; then
    mountpoint -q "$volume" || systemctl start "$mountunit"
    dev=$(findmnt -nro SOURCE --mountpoint "$volume")
    [[ $(losetup -n -O BACK-FILE "$dev") == "$control/data.ext4" ]]
    own /usr/bin/python3 "$repo/deploy/export_results.py"
    if ! gitown diff --quiet HEAD -- results/observations.jsonl.gz; then
        gitown add -- results/observations.jsonl.gz
        gitown commit -m 'Seal research ledger after stopping the observatory worker' -- results/observations.jsonl.gz
    fi
    gitown push origin HEAD:main
    verify_git
    touch "$control/retired-sealed"
fi
if [[ -e $ng ]]; then
    mv -T "$ng" "$control/retired-vhost.conf"
    if ! nginx -t || ! systemctl reload nginx; then
        mv -T "$control/retired-vhost.conf" "$ng"
        nginx -t && systemctl reload nginx
        exit 1
    fi
fi
if [[ -e /etc/letsencrypt/renewal/$site.conf ]]; then
    config=$(nginx -T 2>/dev/null)
    [[ $config != *"/letsencrypt/live/$site/"* && $config != *"/letsencrypt/archive/$site/"* ]]
    certbot delete --non-interactive --cert-name "$site"
fi
if mountpoint -q "$volume"; then
    dev=$(findmnt -nro SOURCE --mountpoint "$volume")
    [[ $(losetup -n -O BACK-FILE "$dev") == "$control/data.ext4" ]]
    [[ $(findmnt -Rnr -o TARGET "$volume" | wc -l) -eq 1 ]]
fi
if [[ -e $units/$mountunit ]]; then systemctl disable --now "$mountunit"; fi
if mountpoint -q "$volume"; then echo 'Research volume still mounted'; exit 1; fi
if [[ -e $control/data.ext4 ]]; then
    [[ -f $control/retired-sealed && -z $(losetup -j "$control/data.ext4") ]]
fi
rm -f -- "$units/oceanacoustics.service" "$units/oceanacoustics.timer" "$units/$mountunit" /etc/default/oceanacoustics /root/oceanacoustics-install.sh
systemctl daemon-reload
if [[ -d $volume ]]; then rmdir "$volume"; fi
# Fixed, project-exclusive paths; refuse nested mounts even on the same filesystem.
for dir in "$control" /etc/oceanacoustics /var/lib/letsencrypt/oceanacoustics; do
    if findmnt -rn -o TARGET | awk -v p="$dir" '$0==p || index($0,p"/")==1{seen=1} END{exit !seen}'; then exit 1; fi
    rm -rf --one-file-system -- "$dir"
done
if getent passwd oceanacoustics >/dev/null; then userdel oceanacoustics; fi
if getent group oceanacoustics >/dev/null; then groupdel oceanacoustics; fi
nginx -t
systemctl is-active --quiet nginx
verify_git
[[ -z $(gitown status --porcelain --untracked-files=all) ]]
revision=$(gitown rev-parse HEAD)
own rm -rf --one-file-system -- "$repo" /home/maestro/oceanacoustics-pilot
rm -f -- /run/lock/oceanacoustics-install.lock /root/oceanacoustics-retire.sh
echo "Ocean Acoustics retired. GitHub main: $revision. Nginx active."
