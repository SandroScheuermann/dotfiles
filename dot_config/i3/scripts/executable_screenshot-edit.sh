#!/bin/sh

tmp="${XDG_RUNTIME_DIR:-/tmp}/i3shot-edit-$(date +%s).png"
trap 'rm -f "$tmp"' EXIT

maim -s "$tmp" || exit 0

if command -v satty >/dev/null 2>&1; then
    satty --filename "$tmp" --copy-command 'xclip -selection clipboard -t image/png -i' --actions-on-enter save-to-clipboard --actions-on-escape exit --early-exit
elif command -v swappy >/dev/null 2>&1; then
    swappy -f "$tmp"
else
    xclip -selection clipboard -t image/png -i < "$tmp"
    notify-send "Screenshot" "Copied region to clipboard. Install satty or swappy for annotation." 2>/dev/null
fi
