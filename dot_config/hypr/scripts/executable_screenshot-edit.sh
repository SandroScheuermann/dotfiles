#!/bin/sh

tmp="${XDG_RUNTIME_DIR:-/tmp}/hyprshot-edit-$(date +%s).png"

if ! command -v grim >/dev/null 2>&1 || ! command -v slurp >/dev/null 2>&1; then
  hyprshot -m region --clipboard-only
  exit $?
fi

grim -g "$(slurp)" "$tmp" || exit 1

if command -v satty >/dev/null 2>&1; then
  satty --filename "$tmp" --copy-command wl-copy --actions-on-enter save-to-clipboard --actions-on-escape exit --early-exit
elif command -v swappy >/dev/null 2>&1; then
  swappy -f "$tmp"
else
  wl-copy < "$tmp"
  notify-send "Screenshot" "Copied region to clipboard. Install satty or swappy for annotation." 2>/dev/null
fi
