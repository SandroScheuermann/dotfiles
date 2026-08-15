#!/usr/bin/env bash

set -u

class=${1:-}
command=${2:-}

case "$class:$command" in
    obsidian:obsidian|winboat:winboat) ;;
    *) exit 2 ;;
esac

case "$class" in
    obsidian)
        criteria='^(md[.]Obsidian|obsidian)$'
        ;;
    winboat)
        criteria='^winboat$'
        ;;
esac

window_id() {
    i3-msg -t get_tree | jq -r --arg class "$class" '
        first(.. | objects | select(
            .window_properties.class? == $class or
            ($class == "obsidian" and .window_properties.class? == "md.Obsidian")
        ) | .id) // empty
    '
}

if [ -n "$(window_id)" ]; then
    i3-msg "[class=\"$criteria\"] scratchpad show" >/dev/null
    exit 0
fi

"$command" >/dev/null 2>&1 &

for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.2
    if [ -n "$(window_id)" ]; then
        i3-msg "[class=\"$criteria\"] scratchpad show" >/dev/null
        exit 0
    fi
done
