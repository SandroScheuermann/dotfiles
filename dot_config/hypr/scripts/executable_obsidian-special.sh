#!/bin/sh

if hyprctl clients -j | jq -e 'any(.[]; .class == "md.Obsidian")' >/dev/null 2>&1; then
  hyprctl dispatch 'hl.dsp.window.move({ workspace = "special:obsidian", follow = false, window = "class:^md\\.Obsidian$" })'
  hyprctl dispatch 'hl.dsp.workspace.toggle_special("obsidian")'
  exit 0
fi

hyprctl dispatch 'hl.dsp.workspace.toggle_special("obsidian")'
obsidian >/dev/null 2>&1 &
