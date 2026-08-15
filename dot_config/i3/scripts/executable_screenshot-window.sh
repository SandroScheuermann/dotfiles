#!/bin/sh

window=$(xdotool getactivewindow 2>/dev/null) || exit 1
maim -i "$window" | xclip -selection clipboard -t image/png -i
notify-send "Screenshot" "Window copied to clipboard." 2>/dev/null
