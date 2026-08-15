#!/bin/sh

window=$(xdotool getactivewindow 2>/dev/null) || exit 1
xkill -id "$window"
