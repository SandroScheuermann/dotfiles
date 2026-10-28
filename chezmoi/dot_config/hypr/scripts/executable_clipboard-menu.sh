#!/bin/sh

if ! command -v cliphist >/dev/null 2>&1 || ! command -v wl-copy >/dev/null 2>&1; then
  notify-send "Clipboard history" "Install cliphist to enable clipboard history." 2>/dev/null
  exit 0
fi

limit=${CLIPBOARD_HISTORY_LIMIT:-120}

if command -v hyprlauncher >/dev/null 2>&1; then
  cliphist list | head -n "$limit" | hyprlauncher --dmenu --quiet | cliphist decode | wl-copy
  exit 0
fi

cliphist list | head -n "$limit" | wofi --dmenu --insensitive --prompt "Clipboard" | cliphist decode | wl-copy
