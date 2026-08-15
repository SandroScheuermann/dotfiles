#!/bin/sh

command -v powerprofilesctl >/dev/null 2>&1 || exit 0

case "${1:-status}" in
    status)
        printf 'PWR %s\n' "$(powerprofilesctl get 2>/dev/null || printf unknown)"
        ;;
    menu)
        choice=$(printf '%s\n' power-saver balanced performance | rofi -dmenu -i -p 'Power profile' -theme "$HOME/.config/rofi/theme.rasi") || exit 0
        [ -n "$choice" ] && powerprofilesctl set "$choice"
        ;;
    set)
        [ -n "${2:-}" ] && powerprofilesctl set "$2"
        ;;
    *)
        exit 2
        ;;
esac
