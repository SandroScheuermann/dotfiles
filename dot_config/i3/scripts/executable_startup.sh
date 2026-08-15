#!/bin/sh

set -u

scripts="$HOME/.config/i3/scripts"
runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"

"$scripts/input-setup.sh"

pkill -x dunst 2>/dev/null || true
dunst >/dev/null 2>&1 &

pkill -x clipmenud 2>/dev/null || true
CM_LAUNCHER=rofi clipmenud >/dev/null 2>&1 &

xset s 0 0 -dpms >/dev/null 2>&1 || true
pkill -x xss-lock 2>/dev/null || true
xss-lock --transfer-sleep-lock -- "$scripts/lock.sh" >/dev/null 2>&1 &

if [ -r "$runtime_dir/i3-idle.pid" ]; then
    old_pid=$(cat "$runtime_dir/i3-idle.pid")
    kill "$old_pid" >/dev/null 2>&1 || true
fi
"$scripts/idle.sh" >/dev/null 2>&1 &

pkill -x polybar 2>/dev/null || true
"$scripts/polybar-launch.sh" >/dev/null 2>&1 &
