#!/bin/sh

profile=$1
action=${2:-status}

case "$profile" in
  power-saver) icon="󰌪" ;;
  balanced) icon="󰾅" ;;
  performance) icon="󰓅" ;;
  *) exit 1 ;;
esac

if [ "$action" = "set" ]; then
  powerprofilesctl set "$profile"
  pkill -RTMIN+10 waybar
  exit 0
fi

current=$(powerprofilesctl get 2>/dev/null)

if [ "$current" = "$profile" ]; then
  printf '{"text":"%s","tooltip":"%s","class":"active"}\n' "$icon" "$profile"
else
  printf '{"text":"%s","tooltip":"%s"}\n' "$icon" "$profile"
fi
