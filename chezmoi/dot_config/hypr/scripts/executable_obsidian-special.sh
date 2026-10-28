#!/bin/sh

if hyprctl clients -j | jq -e 'any(.[]; .class == "obsidian")' >/dev/null 2>&1; then
  hyprctl dispatch workspace special:obsidian
  exit 0
fi

hyprctl dispatch workspace special:obsidian
obsidian >/dev/null 2>&1 &
