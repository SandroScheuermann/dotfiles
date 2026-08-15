#!/bin/sh

if ! command -v clipmenu >/dev/null 2>&1; then
    notify-send "Clipboard history" "Install clipmenu to enable clipboard history." 2>/dev/null
    exit 0
fi

CM_LAUNCHER=rofi clipmenu
