#!/bin/sh

tmp="${XDG_RUNTIME_DIR:-/tmp}/i3shot-$$.png"
trap 'rm -f "$tmp"' EXIT

maim -s "$tmp" || exit 0
xclip -selection clipboard -t image/png -i < "$tmp"
notify-send "Screenshot" "Region copied to clipboard." 2>/dev/null
