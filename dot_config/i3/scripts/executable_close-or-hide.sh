#!/usr/bin/env bash

class=$(i3-msg -t get_tree | jq -r 'first(.. | objects | select(.focused == true and .window_properties != null) | .window_properties.class) // empty')

case "$class" in
    md.Obsidian|obsidian|winboat|winboat-*)
        i3-msg move scratchpad >/dev/null
        ;;
    *)
        i3-msg kill >/dev/null
        ;;
esac
