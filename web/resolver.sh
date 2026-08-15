#!/bin/sh
# Tell nginx which DNS server to ask, at run time.
#
# nginx will only re-resolve a hostname if the upstream is written as a
# variable, and it refuses to start with a variable upstream unless a
# `resolver` is configured. The address of that resolver is different on every
# platform — Docker's embedded one under compose, something else on a hosted
# platform — so it cannot be baked into the image and is read from the
# container's own /etc/resolv.conf here instead.
#
# Runs before 20-envsubst-on-templates.sh purely by filename order; both
# happen before nginx starts, which is all that matters.
set -e

conf=/etc/nginx/conf.d/00-resolver.conf

servers=$(awk '/^nameserver/ { print $2 }' /etc/resolv.conf 2>/dev/null | head -3)
# Docker's embedded DNS, which is what compose gives us and a reasonable guess
# if the file is missing or says nothing useful.
[ -z "$servers" ] && servers=127.0.0.11

list=""
for a in $servers; do
    case "$a" in
        *:*) list="$list [$a]" ;;  # nginx wants IPv6 in brackets
        *)   list="$list $a" ;;
    esac
done

# valid=10s: re-ask this often rather than caching the answer for the life of
# the process, which is the whole reason this file exists — a container that
# restarts comes back on a different address.
cat > "$conf" <<EOF
resolver$list valid=10s ipv6=on;
resolver_timeout 5s;
EOF

echo "resolver: using$list"
