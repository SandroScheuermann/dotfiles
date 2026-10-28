#!/bin/sh

workspace="$1"

if [ -z "$workspace" ]; then
  exit 1
fi

if hyprctl monitors -j | jq -e 'any(.[]; .specialWorkspace.name == "special:obsidian")' >/dev/null 2>&1; then
  hyprctl dispatch togglespecialworkspace obsidian
fi

hyprctl dispatch workspace "$workspace"
