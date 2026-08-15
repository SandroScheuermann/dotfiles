#!/bin/sh

set -u

config="$HOME/.config/polybar/config.ini"

if ! command -v polybar >/dev/null 2>&1; then
    exit 0
fi

monitors=$(polybar --list-monitors 2>/dev/null || true)
if [ -z "$monitors" ]; then
    polybar --reload main >/dev/null 2>&1 &
    exit 0
fi

printf '%s\n' "$monitors" | while IFS=: read -r monitor _; do
    MONITOR="$monitor" polybar -c "$config" --reload main >/dev/null 2>&1 &
done

(sleep 1; "$HOME/.config/i3/scripts/mouse-jiggler.sh" refresh) >/dev/null 2>&1 &
