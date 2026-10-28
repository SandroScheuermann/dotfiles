#!/bin/sh

child_wayland_display=${WAYLAND_DISPLAY:-wayland-1}

export WEZTERM_CHILD_WAYLAND_DISPLAY="$child_wayland_display"
unset WAYLAND_DISPLAY

exec wezterm "$@"
