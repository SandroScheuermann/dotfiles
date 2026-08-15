#!/usr/bin/env bash

set -u

runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
pid_file="$runtime_dir/i3-idle.pid"
lock_script="$HOME/.config/i3/scripts/lock.sh"

if [[ -r "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
        exit 0
    fi
fi

printf '%s\n' "$$" > "$pid_file"

brightness_saved=0
dpms_off=0
suspend_sent=0
lock_pid=""
last_lock=0

cleanup() {
    if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
        kill "$lock_pid" 2>/dev/null || true
    fi
    if ((brightness_saved)); then
        brightnessctl -r >/dev/null 2>&1 || true
    fi
    if ((dpms_off)); then
        xset dpms force on >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file"
}
trap cleanup EXIT INT TERM

command -v xprintidle >/dev/null 2>&1 || exit 0

while :; do
    idle_us=$(xprintidle 2>/dev/null || printf '0')
    [[ "$idle_us" =~ ^[0-9]+$ ]] || idle_us=0
    now=$(date +%s)

    if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
        lock_pid=""
    fi

    if ((idle_us >= 300000000)); then
        if ((brightness_saved == 0)); then
            brightnessctl -s set 10 >/dev/null 2>&1 || true
            brightness_saved=1
        fi
    elif ((brightness_saved)); then
        brightnessctl -r >/dev/null 2>&1 || true
        brightness_saved=0
    fi

    if ((idle_us >= 600000000 && now - last_lock >= 60)) && [[ -z "$lock_pid" ]]; then
        "$lock_script" >/dev/null 2>&1 &
        lock_pid=$!
        last_lock=$now
    fi

    if ((idle_us >= 900000000 && dpms_off == 0)); then
        xset dpms force off >/dev/null 2>&1 || true
        dpms_off=1
    elif ((idle_us < 900000000 && dpms_off)); then
        xset dpms force on >/dev/null 2>&1 || true
        dpms_off=0
    fi

    if ((idle_us >= 1800000000 && suspend_sent == 0)); then
        systemctl suspend >/dev/null 2>&1 &
        suspend_sent=1
    elif ((idle_us < 30000000)); then
        suspend_sent=0
    fi

    sleep 5
done
