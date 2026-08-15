#!/usr/bin/env bash

set -u

target=${1:-}
workspace_script="$HOME/.config/i3/scripts/workspace-domains.sh"

case "$target" in
    domain|[1-9]|10) ;;
    *) exit 2 ;;
esac

emit() {
    if [[ "$target" == domain ]]; then
        "$workspace_script" domain-status
    else
        "$workspace_script" status "$target"
    fi
}

emit

while :; do
    while IFS= read -r _; do
        emit
    done < <(i3-msg -t subscribe -m '["workspace","window"]' 2>/dev/null)
    sleep 1
done
