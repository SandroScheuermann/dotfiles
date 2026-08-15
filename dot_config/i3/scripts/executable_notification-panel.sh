#!/bin/sh

command -v dunstctl >/dev/null 2>&1 || exit 0

if dunstctl is-paused 2>/dev/null | grep -q true; then
    dnd_label="Do not disturb: on"
else
    dnd_label="Do not disturb: off"
fi

choice=$(printf '%s\n' "$dnd_label" "Show history" "Clear all" | rofi \
    -dmenu \
    -i \
    -p Notifications \
    -theme "$HOME/.config/rofi/theme.rasi") || exit 0

case "$choice" in
    "Do not disturb: on")
        dunstctl set-paused false
        ;;
    "Do not disturb: off")
        dunstctl set-paused true
        ;;
    "Show history")
        dunstctl history | rofi -dmenu -i -p History -markup-rows -theme "$HOME/.config/rofi/theme.rasi" >/dev/null
        ;;
    "Clear all")
        dunstctl close-all
        ;;
esac
