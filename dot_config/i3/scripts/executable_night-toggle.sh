#!/bin/sh

state_file="${XDG_RUNTIME_DIR:-/tmp}/i3-night-light.state"

if ! command -v redshift >/dev/null 2>&1; then
    notify-send "Night light" "Install redshift to enable night light." 2>/dev/null
    exit 0
fi

if [ -f "$state_file" ]; then
    redshift -x >/dev/null 2>&1 || true
    rm -f "$state_file"
    notify-send "Night light" "Off" 2>/dev/null
else
    redshift -O 4500 >/dev/null 2>&1 || exit 1
    : > "$state_file"
    notify-send "Night light" "On: 4500K" 2>/dev/null
fi
