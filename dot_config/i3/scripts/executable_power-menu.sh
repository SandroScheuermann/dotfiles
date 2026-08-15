#!/bin/sh

choice=$(printf '%s\n' Lock Logout Shutdown Reboot | rofi \
    -dmenu \
    -i \
    -p Power \
    -theme "$HOME/.config/rofi/theme.rasi") || exit 0

case "$choice" in
    Lock)
        "$HOME/.config/i3/scripts/lock.sh"
        ;;
    Logout)
        i3-msg exit
        ;;
    Shutdown)
        systemctl poweroff
        ;;
    Reboot)
        systemctl reboot
        ;;
esac
