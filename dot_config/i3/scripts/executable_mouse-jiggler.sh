#!/usr/bin/env bash

set -u

unit=i3-mouse-jiggler.service
state_file="${XDG_RUNTIME_DIR:-/tmp}/i3-mouse-jiggler.state"
idle_threshold_ms=18000

is_active() {
    systemctl --user is-active --quiet "$unit"
}

set_bar_state() {
    local state=$1
    local hook

    case "$state" in
        active) hook=1 ;;
        waiting) hook=2 ;;
        *) state=off; hook=0 ;;
    esac

    printf '%s\n' "$state" > "$state_file"
    command -v polybar-msg >/dev/null 2>&1 || return
    polybar-msg action "#caffeine.hook.$hook" >/dev/null 2>&1 || true
}

refresh_bar() {
    local state

    if ! is_active; then
        set_bar_state off
        rm -f "$state_file"
        return
    fi

    if [[ -r "$state_file" ]]; then
        state=$(cat "$state_file")
    elif (( $(xprintidle 2>/dev/null || printf 0) >= idle_threshold_ms )); then
        state=active
    else
        state=waiting
    fi

    set_bar_state "$state"
}

status() {
    local state

    if ! is_active; then
        printf '\n'
        return
    fi

    state=waiting
    [[ -r "$state_file" ]] && state=$(cat "$state_file")

    case "$state" in
        active) printf '~\n' ;;
        waiting) printf '~/\n' ;;
        *) printf '\n' ;;
    esac
}

random_delay() {
    printf '%s\n' "$((RANDOM % 22 + 46))"
}

move_mouse_imperceptibly() {
    local location x y dx dy

    location=$(xdotool getmouselocation --shell 2>/dev/null) || return
    x=$(printf '%s\n' "$location" | awk -F= '$1 == "X" { print $2 }')
    y=$(printf '%s\n' "$location" | awk -F= '$1 == "Y" { print $2 }')
    [[ "$x" =~ ^-?[0-9]+$ && "$y" =~ ^-?[0-9]+$ ]] || return

    case $((RANDOM % 8)) in
        0) dx=1; dy=0 ;;
        1) dx=-1; dy=0 ;;
        2) dx=0; dy=1 ;;
        3) dx=0; dy=-1 ;;
        4) dx=1; dy=1 ;;
        5) dx=1; dy=-1 ;;
        6) dx=-1; dy=1 ;;
        7) dx=-1; dy=-1 ;;
    esac

    xdotool mousemove "$((x + dx))" "$((y + dy))" >/dev/null 2>&1
    sleep 0.05
    xdotool mousemove "$x" "$y" >/dev/null 2>&1
}

case ${1:-run} in
    start)
        is_active || systemd-run --user --quiet --collect --unit="$unit" "$0" run
        # Pressing the shortcut is user activity, so begin in the waiting state.
        set_bar_state waiting
        exit
        ;;
    stop)
        is_active && systemctl --user --quiet stop "$unit"
        set_bar_state off
        rm -f "$state_file"
        exit
        ;;
    toggle)
        if is_active; then
            "$0" stop
        else
            "$0" start
        fi
        exit
        ;;
    refresh)
        refresh_bar
        exit
        ;;
    status)
        status
        exit
        ;;
    run) ;;
    *)
        printf 'Usage: %s {start|stop|toggle|refresh|status|run}\n' "$0" >&2
        exit 2
        ;;
esac

for command in xdotool xprintidle; do
    command -v "$command" >/dev/null 2>&1 || exit 1
done

previous_idle=$(xprintidle 2>/dev/null || printf 0)
[[ "$previous_idle" =~ ^[0-9]+$ ]] || previous_idle=0
expected_synthetic_reset=false
next_move=0

if ((previous_idle >= idle_threshold_ms)); then
    state=active
    next_move=$(($(date +%s) + $(random_delay)))
else
    state=waiting
fi
set_bar_state "$state"

while :; do
    now=$(date +%s)
    idle=$(xprintidle 2>/dev/null || printf 0)
    [[ "$idle" =~ ^[0-9]+$ ]] || idle=0

    if [[ "$expected_synthetic_reset" == true && "$idle" -lt "$previous_idle" ]]; then
        expected_synthetic_reset=false
    elif [[ "$idle" -lt "$previous_idle" ]]; then
        state=waiting
        next_move=0
        set_bar_state waiting
    fi

    if [[ "$state" == waiting && "$idle" -ge "$idle_threshold_ms" ]]; then
        state=active
        next_move=$((now + $(random_delay)))
        set_bar_state active
    fi

    if [[ "$state" == active && "$now" -ge "$next_move" ]]; then
        move_mouse_imperceptibly
        expected_synthetic_reset=true
        next_move=$((now + $(random_delay)))
    fi

    previous_idle=$idle
    sleep 1
done
