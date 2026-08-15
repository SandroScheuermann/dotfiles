#!/bin/sh

set -- -c 18191c -f -u -n
wallpaper="$HOME/.config/hypr/wallpapers/wallpaper.jpg"

if [ -f "$wallpaper" ]; then
    set -- "$@" -i "$wallpaper"
fi

exec i3lock "$@"
