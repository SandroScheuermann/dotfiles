#!/bin/sh

setxkbmap -layout us -variant intl >/dev/null 2>&1 || true

if ! command -v xinput >/dev/null 2>&1; then
    exit 0
fi

for id in $(xinput list --id-only 2>/dev/null); do
    properties=$(xinput list-props "$id" 2>/dev/null || true)
    printf '%s\n' "$properties" | grep -q 'libinput Natural Scrolling Enabled' && \
        xinput set-prop "$id" 'libinput Natural Scrolling Enabled' 0 >/dev/null 2>&1 || true
    printf '%s\n' "$properties" | grep -q 'libinput Tapping Enabled' && \
        xinput set-prop "$id" 'libinput Tapping Enabled' 1 >/dev/null 2>&1 || true
    printf '%s\n' "$properties" | grep -q 'libinput Accel Profile Enabled' && \
        xinput set-prop "$id" 'libinput Accel Profile Enabled' 0 1 >/dev/null 2>&1 || true
    printf '%s\n' "$properties" | grep -q 'libinput Accel Speed' && \
        xinput set-prop "$id" 'libinput Accel Speed' 0 >/dev/null 2>&1 || true
done
